"""
Run with:  .venv/bin/pytest tests/test_signal2.py -v -s
"""
from dotenv import load_dotenv
load_dotenv()

from signals.signal2_contraction import score_contraction_density

AI_TEXT = (
    "Artificial intelligence represents a transformative paradigm shift in modern society. "
    "It is important to note that while the benefits of AI are numerous, it is equally "
    "essential to consider the ethical implications. Furthermore, stakeholders across "
    "various sectors must collaborate to ensure responsible deployment."
)

HUMAN_TEXT = (
    "ok so i finally tried that new ramen place downtown and honestly? "
    "underwhelming. the broth was fine but they put WAY too much sodium in it and "
    "i was thirsty for like three hours after. my friend got the spicy version and "
    "said it was better. probably won't go back unless someone drags me there"
)

BORDERLINE_FORMAL = (
    "The relationship between monetary policy and asset price inflation has been "
    "extensively studied in the literature. Central banks face a fundamental tension "
    "between their mandate for price stability and the unintended consequences of "
    "prolonged low interest rates on equity and real estate valuations."
)

BORDERLINE_EDITED_AI = (
    "I've been thinking a lot about remote work lately. There are genuine tradeoffs — "
    "flexibility and no commute on one side, isolation and blurred work-life boundaries "
    "on the other. Studies show productivity varies widely by individual and role type."
)


def test_ai_text_scores_high():
    score = score_contraction_density(AI_TEXT)
    print(f"\n[AI text]           signal2={score:.4f}  (expect ~1.0 — no contractions)")
    assert score == 1.0, f"Expected 1.0 for zero-contraction AI text, got {score}"


def test_human_text_scores_lower_than_ai():
    ai_score = score_contraction_density(AI_TEXT)
    human_score = score_contraction_density(HUMAN_TEXT)
    print(f"\n[Human text]        signal2={human_score:.4f}  (expect < {ai_score:.4f})")
    assert human_score < ai_score, (
        f"Human text ({human_score}) should score lower than AI text ({ai_score})"
    )


def test_borderline_formal_scores_high():
    score = score_contraction_density(BORDERLINE_FORMAL)
    print(f"\n[Formal human]      signal2={score:.4f}  (expect ~1.0 — contractions absent by convention)")
    # Formal academic prose has no contractions — this is a known blind spot
    assert score >= 0.75, f"Formal text should score high (robotic-looking), got {score}"


def test_edited_ai_scores_lower_due_to_contraction():
    score = score_contraction_density(BORDERLINE_EDITED_AI)
    print(f"\n[Lightly edited AI] signal2={score:.4f}  (expect < 1.0 — contains \"I've\")")
    assert score < 1.0, f"Text with 'I\\'ve' should score below 1.0, got {score}"


def test_score_is_valid_float_in_range():
    for label, text in [
        ("AI", AI_TEXT), ("human", HUMAN_TEXT),
        ("formal", BORDERLINE_FORMAL), ("edited_ai", BORDERLINE_EDITED_AI),
    ]:
        score = score_contraction_density(text)
        assert isinstance(score, float), f"{label}: score must be float"
        assert 0.0 <= score <= 1.0, f"{label}: score {score} out of [0.0, 1.0]"
