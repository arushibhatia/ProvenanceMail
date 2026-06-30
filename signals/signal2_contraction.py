import re

# Explicit enumeration — avoids false positives from possessives ("John's report")
_CONTRACTION_RE = re.compile(
    r"\b("
    r"ain't|aren't|can't|can't|cannot|couldn't|couldn't|"
    r"didn't|didn't|doesn't|doesn't|don't|don't|"
    r"hadn't|hadn't|hasn't|hasn't|haven't|haven't|"
    r"he'd|he'll|he's|here's|how's|"
    r"i'd|i'll|i'm|i've|"
    r"isn't|isn't|it's|"
    r"let's|mightn't|mustn't|"
    r"shan't|she'd|she'll|she's|shouldn't|shouldn't|"
    r"that's|there's|they'd|they'll|they're|they've|"
    r"wasn't|wasn't|we'd|we'll|we're|we've|weren't|weren't|"
    r"what's|when's|where's|who'd|who'll|who's|who've|why's|"
    r"won't|won't|wouldn't|wouldn't|"
    r"y'all|you'd|you'll|you're|you've|"
    r"could've|should've|would've|might've|must've"
    r")\b",
    re.IGNORECASE,
)


def score_contraction_density(text: str) -> float:
    """
    Signal 2: Contraction Density heuristic.

    Returns 0.0 (high contraction density → human) to 1.0 (zero contractions → robotic).
    Formula from spec: max(0.0, 1.0 - contraction_count / (total_words * 0.05))
    """
    words = text.split()
    total_words = len(words)
    if total_words == 0:
        return 1.0

    contraction_count = len(_CONTRACTION_RE.findall(text))
    raw = 1.0 - (contraction_count / (total_words * 0.05))
    return round(max(0.0, raw), 4)
