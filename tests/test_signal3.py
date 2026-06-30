"""
Run with:  .venv/bin/pytest tests/test_signal3.py -v -s
"""
from signals.signal3_punctuation import score_punctuation_spark


def test_no_markers_returns_one():
    text = "Please review the attached document and provide your feedback by Friday."
    assert score_punctuation_spark(text) == 1.0


def test_two_marker_types_returns_zero():
    # exclamation + ellipsis
    text = "Great news! We finally got the approval... can't wait to share more."
    assert score_punctuation_spark(text) == 0.0


def test_all_three_marker_types_returns_zero():
    text = "Sounds good! I'll follow up later (probably after the meeting)... let me know."
    assert score_punctuation_spark(text) == 0.0


def test_one_marker_type_returns_half():
    # only parenthetical
    text = "The report (attached below) covers the full quarter."
    assert score_punctuation_spark(text) == 0.5


def test_score_is_valid_for_ai_text():
    ai = (
        "Artificial intelligence represents a transformative paradigm shift in modern society. "
        "It is important to note that while the benefits of AI are numerous, it is equally "
        "essential to consider the ethical implications."
    )
    score = score_punctuation_spark(ai)
    print(f"\n[AI text]    signal3={score}")
    assert score == 1.0


def test_score_is_valid_for_human_text():
    human = (
        "ok so i finally tried that new ramen place downtown and honestly? "
        "underwhelming (the broth was way too salty)... probably won't go back!"
    )
    score = score_punctuation_spark(human)
    print(f"\n[Human text] signal3={score}")
    assert score == 0.0
