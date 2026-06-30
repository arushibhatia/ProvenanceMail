"""
Run with:  .venv/bin/pytest tests/test_signal1.py -v
"""
import pytest
from dotenv import load_dotenv

load_dotenv()

from signals.signal1_groq import score_semantic_tropes


CORPORATE_BOILERPLATE = (
    "I hope this email finds you well. I am writing to inform you that the quarterly "
    "deliverables have been completed. Furthermore, please note that the attached report "
    "outlines the key performance indicators for Q3. In conclusion, I look forward to "
    "your feedback."
)


def test_signal1_returns_valid_score_and_reasoning():
    result = score_semantic_tropes(CORPORATE_BOILERPLATE)

    print(result)
    
    assert isinstance(result, dict), "result must be a dict"
    assert "score" in result, "result must contain 'score'"
    assert "reasoning" in result, "result must contain 'reasoning'"

    score = result["score"]
    assert isinstance(score, float), f"score must be a float, got {type(score)}"
    assert 0.0 <= score <= 1.0, f"score {score} is outside [0.0, 1.0]"

    reasoning = result["reasoning"]
    assert isinstance(reasoning, str) and reasoning.strip(), "reasoning must be a non-empty string"
