import json
import os
import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from signals.signal1_groq import score_semantic_tropes

load_dotenv()

app = Flask(__name__)

AUDIT_LOG = "audit.jsonl"


def _classify(confidence: float) -> tuple[str, str]:
    """Map a confidence score to (attribution, label)."""
    if confidence < 0.40:
        return (
            "human_original",
            "High-Confidence Human Original: Our system indicates this content aligns "
            "closely with natural human writing patterns, colloquial conversational flow, "
            "and structural stylistic variance. This text is classified as a human-authored draft.",
        )
    if confidence <= 0.75:
        return (
            "uncertain",
            "Verification Uncertain: This text features mixed stylistic markers. It utilizes "
            "rigid, highly structured professional phrasings often found in standard corporate "
            "templates, heavily edited drafts, or collaborative human-AI setups. Classification "
            "cannot be definitively determined automatically.",
        )
    return (
        "likely_ai",
        "AI-Generated Notification: This text displays high statistical uniformity, a complete "
        "lack of conversational contractions, and structural boilerplate highly characteristic "
        "of automated language models. The system has classified this content as machine-generated.",
    )


def _append_audit(event: dict) -> None:
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(event) + "\n")


def _get_log() -> list[dict]:
    if not os.path.exists(AUDIT_LOG):
        return []
    with open(AUDIT_LOG) as f:
        return [json.loads(line) for line in f if line.strip()]


@app.post("/submit")
def submit():
    body = request.get_json(silent=True)
    if not body or "text" not in body:
        return jsonify({"error": "Request body must include a 'text' field."}), 400
    if "creator_id" not in body:
        return jsonify({"error": "Request body must include a 'creator_id' field."}), 400

    text = body["text"].strip()
    creator_id = str(body["creator_id"]).strip()

    if not text:
        return jsonify({"error": "'text' must not be empty."}), 400
    if not creator_id:
        return jsonify({"error": "'creator_id' must not be empty."}), 400

    content_id = str(uuid.uuid4())

    # --- Signal 1: Groq LLM semantic tropes ---
    try:
        signal1 = score_semantic_tropes(text)
    except Exception as exc:
        return jsonify({"error": f"Signal 1 failed: {str(exc)}"}), 502

    llm_score = signal1["score"]

    # Signals 2 & 3 are stubs until Milestone 4; confidence is Signal 1 only for now.
    # Formula will become: (0.50 * s1) + (0.30 * s2) + (0.20 * s3)
    confidence = round(llm_score, 4)

    attribution, label = _classify(confidence)

    _append_audit({
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "status": "classified",
    })

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
        "signals": {
            "signal1": {"score": llm_score, "reasoning": signal1["reasoning"]},
            "signal2": {"score": None},
            "signal3": {"score": None},
        },
    }), 200


@app.get("/log")
def log():
    return jsonify({"entries": _get_log()})


if __name__ == "__main__":
    app.run(debug=True)
