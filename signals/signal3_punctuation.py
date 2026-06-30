import re

_EXCLAMATION = re.compile(r"!")
_PARENTHETICAL = re.compile(r"\([^)]+\)")
_ELLIPSIS = re.compile(r"\.{3}|…")


def score_punctuation_spark(text: str) -> float:
    """
    Signal 3: Punctuation Spark heuristic.

    Counts how many distinct expressive marker types are present:
      ! (exclamation), (...) (parenthetical aside), ... or … (ellipsis)

    Scoring:
      0 types present → 1.0  (rigid machine uniformity)
      1 type  present → 0.5  (partial human signal)
      2+ types present → 0.0 (active human punctuation signature)
    """
    distinct = sum([
        bool(_EXCLAMATION.search(text)),
        bool(_PARENTHETICAL.search(text)),
        bool(_ELLIPSIS.search(text)),
    ])

    if distinct == 0:
        return 1.0
    if distinct == 1:
        return 0.5
    return 0.0
