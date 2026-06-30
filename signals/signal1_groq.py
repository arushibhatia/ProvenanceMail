import json
import os
from groq import Groq

_client = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client

SYSTEM_PROMPT = """You are a linguistic provenance classifier. Analyze the provided email text and evaluate it for semantic tropes characteristic of AI generation: holistic semantic uniformity, predictable corporate transitions ("Furthermore", "In conclusion", "I hope this email finds you well"), and boilerplate phrasing symmetry.

Return ONLY a strict, minified JSON block — no explanation outside the JSON, no markdown fences:
{"score": <float 0.0-1.0>, "reasoning": "<one sentence>"}

Score guide:
  0.0 = Highly conversational, irregular, colloquial human writing
  1.0 = Pure machine signature with uniform structure and boilerplate transitions"""

def score_semantic_tropes(text: str) -> dict:
    """
    Signal 1: Groq LLM semantic tropes detector.
    Returns {"score": float, "reasoning": str}
    """
    client = _get_client()

    chat_completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )

    raw = chat_completion.choices[0].message.content.strip()

    # Strip markdown code fences if the model wraps its output anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed = json.loads(raw)
    score = float(parsed["score"])
    reasoning = str(parsed["reasoning"])

    if not (0.0 <= score <= 1.0):
        raise ValueError(f"Signal 1 score out of range: {score}")

    return {"score": score, "reasoning": reasoning}
