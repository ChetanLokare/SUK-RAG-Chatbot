"""
Dynamic Top-K Retrieval Controller

Determines how many documents to retrieve
based on query complexity and intent.

Used by the hybrid retrieval pipeline.
"""

import re
from typing import List


# =========================================================
# CONFIGURATION
# =========================================================

# Hard safety limits
MIN_TOP_K = 6
MAX_TOP_K = 25

# Tokenization
TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


# =========================================================
# TOKENIZER
# =========================================================

def tokenize(text: str) -> List[str]:
    """
    Basic tokenizer for query analysis.
    """

    if not text:
        return []

    return TOKEN_PATTERN.findall(text.lower())


# =========================================================
# NORMALIZE
# =========================================================

def _normalize(text: str) -> str:
    """
    Normalize query text.
    """

    if not text:
        return ""

    return re.sub(r"\s+", " ", text.lower()).strip()


# =========================================================
# QUERY COMPLEXITY
# =========================================================

def estimate_query_complexity(query: str) -> float:
    """
    Estimate query complexity between 0 and 1.
    """

    tokens = tokenize(query)

    if not tokens:
        return 0.0

    length_score = min(len(tokens) / 14.0, 1.0)

    question_words = {
        "what",
        "how",
        "when",
        "where",
        "who",
        "which",
        "why",
        "will",
    }

    question_bonus = 0.2 if any(w in tokens for w in question_words) else 0.0

    complexity = min(length_score + question_bonus, 1.0)

    return complexity


# =========================================================
# INTENT DETECTION
# =========================================================

CONTACT_HINTS = [
    "email",
    "phone",
    "contact",
    "hod",
    "faculty",
    "staff",
]

DEADLINE_HINTS = [
    "deadline",
    "last date",
    "apply before",
    "due date",
]

FACT_HINTS = [
    "who",
    "when",
    "where",
]

TEMPORAL_HINTS = [
    "next",
    "upcoming",
    "schedule",
    "timetable",
    "calendar",
]

EVENT_HINTS = [
    "event",
    "seminar",
    "conference",
    "workshop",
]

BROAD_INFO_HINTS = [
    "information",
    "details",
    "tell me",
    "tell me about",
    "explain",
    "describe",
]


def detect_query_intent(query: str) -> str:
    """
    Detect approximate query intent.
    """

    q = _normalize(query)

    if not q:
        return "general"

    tokens = tokenize(q)

    # Contact queries
    if any(x in q for x in CONTACT_HINTS):
        return "contact"

    # Deadline queries
    if any(x in q for x in DEADLINE_HINTS):
        return "deadline"

    # Temporal queries
    if any(x in q for x in TEMPORAL_HINTS):
        return "temporal"

    # Event queries
    if any(x in q for x in EVENT_HINTS):
        return "event"

    # Fact queries
    if any(x in tokens for x in FACT_HINTS):
        return "fact"

    # Broad informational queries
    if any(x in q for x in BROAD_INFO_HINTS):
        return "broad"

    return "general"


# =========================================================
# QUERY LENGTH SIGNAL
# =========================================================

def _query_length_signal(query: str) -> int:
    """
    Estimate query length in tokens.
    """

    tokens = tokenize(query)

    return len(tokens)


# =========================================================
# SAFETY BOUND
# =========================================================

def _clamp_top_k(value: int) -> int:
    """
    Ensure top_k stays within safe bounds.
    """

    if value < MIN_TOP_K:
        return MIN_TOP_K

    if value > MAX_TOP_K:
        return MAX_TOP_K

    return value


# =========================================================
# MAIN ADAPTIVE TOP-K
# =========================================================

def dynamic_top_k(query: str) -> int:
    """
    Determine retrieval size based on
    query complexity and intent.
    """

    if not query:
        return MIN_TOP_K

    complexity = estimate_query_complexity(query)

    intent = detect_query_intent(query)

    length = _query_length_signal(query)

    # -----------------------------------------------------
    # CONTACT QUERIES
    # -----------------------------------------------------

    if intent == "contact":
        return _clamp_top_k(6)

    # -----------------------------------------------------
    # DEADLINE QUERIES
    # -----------------------------------------------------

    if intent == "deadline":
        return _clamp_top_k(10)

    # -----------------------------------------------------
    # FACT QUERIES
    # -----------------------------------------------------

    if intent == "fact":
        return _clamp_top_k(10)

    # -----------------------------------------------------
    # TEMPORAL / EVENT
    # -----------------------------------------------------

    if intent in ("temporal", "event"):
        return _clamp_top_k(12)

    # -----------------------------------------------------
    # BROAD INFORMATION
    # -----------------------------------------------------

    if intent == "broad":
        return _clamp_top_k(18)

    # -----------------------------------------------------
    # LONG QUERIES
    # -----------------------------------------------------

    if length >= 10:
        return _clamp_top_k(20)

    # -----------------------------------------------------
    # HIGH COMPLEXITY
    # -----------------------------------------------------

    if complexity > 0.75:
        return _clamp_top_k(18)

    if complexity > 0.45:
        return _clamp_top_k(14)

    # -----------------------------------------------------
    # DEFAULT
    # -----------------------------------------------------

    return _clamp_top_k(25)