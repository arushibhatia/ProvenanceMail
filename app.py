import json
import os
import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

from signals.signal1_groq import score_semantic_tropes
from signals.signal2_contraction import score_contraction_density
from signals.signal3_punctuation import score_punctuation_spark

load_dotenv()

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

AUDIT_LOG = "audit.jsonl"


# ---------------------------------------------------------------------------
# Label generation — text strings are verbatim from the spec
# ---------------------------------------------------------------------------

LABEL_HUMAN = (
    "High-Confidence Human Original: Our system indicates this content aligns closely"
    " with natural human writing patterns, colloquial conversational flow, and structural"
    " stylistic variance. This text is classified as a human-authored draft."
)

LABEL_UNCERTAIN = (
    "Verification Uncertain: This text features mixed stylistic markers. It utilizes"
    " rigid, highly structured professional phrasings often found in standard corporate"
    " templates, heavily edited drafts, or collaborative human-AI setups. Classification"
    " cannot be definitively determined automatically."
)

LABEL_AI = (
    "AI-Generated Notification: This text displays high statistical uniformity, a complete"
    " lack of conversational contractions, and structural boilerplate highly characteristic"
    " of automated language models. The system has classified this content as machine-generated."
)


def classify(confidence: float) -> tuple[str, str]:
    """
    Map a confidence score to (attribution, label).

    Thresholds from spec:
      [0.00, 0.40)  → human_original
      [0.40, 0.75]  → uncertain
      (0.75, 1.00]  → likely_ai
    """
    if confidence < 0.40:
        return "human_original", LABEL_HUMAN
    if confidence <= 0.75:
        return "uncertain", LABEL_UNCERTAIN
    return "likely_ai", LABEL_AI


# ---------------------------------------------------------------------------
# Audit log helpers
# ---------------------------------------------------------------------------

def _append_audit(event: dict) -> None:
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(event) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _get_log() -> list[dict]:
    """
    Compile the append-only log into a current-state map.
    SUBMISSION events seed each entry; APPEAL_FILED events update status
    and attach appeal fields — without mutating the raw ledger.
    """
    if not os.path.exists(AUDIT_LOG):
        return []

    state: dict[str, dict] = {}
    order: list[str] = []

    with open(AUDIT_LOG) as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            event = json.loads(raw)
            cid = event.get("content_id")
            if not cid:
                continue

            etype = event.get("event_type", "SUBMISSION")

            if etype == "SUBMISSION" and cid not in state:
                state[cid] = event.copy()
                order.append(cid)
            elif etype == "APPEAL_FILED" and cid in state:
                state[cid]["status"] = "under_review"
                state[cid]["appeal_reasoning"] = event.get("appeal_reasoning")
                state[cid]["appeal_timestamp"] = event.get("timestamp")

    return [state[cid] for cid in order]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/submit")
@limiter.limit("10 per minute; 100 per day")
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

    try:
        signal1 = score_semantic_tropes(text)
    except Exception as exc:
        return jsonify({"error": f"Signal 1 failed: {str(exc)}"}), 502

    llm_score = signal1["score"]
    contraction_score = score_contraction_density(text)
    punctuation_score = score_punctuation_spark(text)

    # Full weighted formula from spec:
    confidence = round(
        (0.50 * llm_score) + (0.30 * contraction_score) + (0.20 * punctuation_score),
        4,
    )

    attribution, label = classify(confidence)

    _append_audit({
        "event_type": "SUBMISSION",
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": _now(),
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "contraction_score": contraction_score,
        "punctuation_score": punctuation_score,
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
            "signal2": {"score": contraction_score},
            "signal3": {"score": punctuation_score},
        },
    }), 200


@app.post("/appeal")
def appeal():
    body = request.get_json(silent=True) or {}
    content_id = str(body.get("content_id", "")).strip()
    creator_reasoning = str(body.get("creator_reasoning", "")).strip()

    if not content_id:
        return jsonify({"error": "content_id is required."}), 400
    if not creator_reasoning:
        return jsonify({"error": "creator_reasoning is required."}), 400

    known_ids = {e["content_id"] for e in _get_log()}
    if content_id not in known_ids:
        return jsonify({"error": f"content_id '{content_id}' not found."}), 404

    _append_audit({
        "event_type": "APPEAL_FILED",
        "content_id": content_id,
        "timestamp": _now(),
        "status": "under_review",
        "appeal_reasoning": creator_reasoning,
    })

    return jsonify({
        "message": "Appeal received. This submission has been flagged for human review.",
        "content_id": content_id,
        "status": "under_review",
    }), 202


@app.get("/log")
def log():
    return jsonify({"entries": _get_log()})


if __name__ == "__main__":
    app.run(debug=True)
