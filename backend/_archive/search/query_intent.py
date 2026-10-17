"""
Query Intent Detection (FINAL PRODUCTION VERSION)

Detects whether a query is temporal (time-based).

Used for:
• boosting recent results
• prioritizing deadlines
• ranking upcoming events

Examples:
- "next exam date"
- "when is result"
- "last date for admission"
"""

import re


# ============================================================
# KEYWORDS (🔥 FULL LIST)
# ============================================================

TIME_KEYWORDS = [

    # ----------------------------------------
    # Future / upcoming
    # ----------------------------------------
    "next",
    "upcoming",
    "future",
    "soon",
    "later",

    # ----------------------------------------
    # Dates / deadlines
    # ----------------------------------------
    "deadline",
    "last date",
    "due date",
    "closing date",
    "final date",

    # ----------------------------------------
    # Schedule / timing
    # ----------------------------------------
    "schedule",
    "timetable",
    "time table",
    "calendar",
    "routine",

    # ----------------------------------------
    # Questions
    # ----------------------------------------
    "when",
    "when is",
    "when will",
    "what date",
    "which date",

    # ----------------------------------------
    # Results / exams
    # ----------------------------------------
    "result date",
    "exam date",
    "exam schedule",

    # ----------------------------------------
    # Relative time
    # ----------------------------------------
    "today",
    "tomorrow",
    "this week",
    "this month",
    "this year",
]


# ============================================================
# REGEX PATTERNS (🔥 IMPORTANT)
# ============================================================

TIME_REGEX = [

    r"\bwhen\s+(is|will|are)\b",
    r"\bwhat\s+date\b",
    r"\bwhich\s+date\b",
    r"\bnext\s+\w+\b",
    r"\blast\s+date\b",
    r"\bdeadline\b",
    r"\bexam\s+date\b",
    r"\bresult\s+date\b",
]


# ============================================================
# NORMALIZE
# ============================================================

def _normalize(query: str) -> str:

    if not query:
        return ""

    query = query.lower().strip()
    query = re.sub(r"\s+", " ", query)

    return query


# ============================================================
# BOOLEAN CHECK
# ============================================================

def is_temporal_query(query: str) -> bool:
    """
    Returns True if query is time-related.
    """

    q = _normalize(query)

    if not q:
        return False

    # keyword match
    if any(word in q for word in TIME_KEYWORDS):
        return True

    # regex match
    for pattern in TIME_REGEX:
        if re.search(pattern, q):
            return True

    return False


# ============================================================
# INTENT SCORE (🔥 ADVANCED)
# ============================================================

def temporal_score(query: str) -> float:
    """
    Returns a score indicating how strongly
    the query is temporal (0 → 1.5+).
    """

    q = _normalize(query)

    if not q:
        return 0.0

    score = 0.0

    # keyword scoring
    for word in TIME_KEYWORDS:
        if word in q:
            score += 0.3

    # regex scoring
    for pattern in TIME_REGEX:
        if re.search(pattern, q):
            score += 0.5

    return min(score, 2.0)