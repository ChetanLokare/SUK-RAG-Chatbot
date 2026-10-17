# backend/search/query_router.py

"""
Query Router for RAG system.

Responsibilities
----------------
• classify query intent
• route query to correct retrieval strategy
• apply routing hints (temporal, entity, contact)

This improves retrieval precision for
university knowledge systems.
"""

import re
from typing import Dict, List


# ============================================================
# QUERY TYPES
# ============================================================

QUERY_FACT = "fact"
QUERY_CONTACT = "contact"
QUERY_DEADLINE = "deadline"
QUERY_LATEST = "latest"
QUERY_EVENT = "event"
QUERY_TEMPORAL = "temporal"
QUERY_GENERAL = "general"


# ============================================================
# TOKENIZER
# ============================================================

TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


def _tokenize(text: str) -> List[str]:

    if not text:
        return []

    return TOKEN_PATTERN.findall(text.lower())


# ============================================================
# NORMALIZE QUERY
# ============================================================

def _normalize_query(query: str) -> str:

    if not query:
        return ""

    query = query.lower().strip()

    query = re.sub(r"\s+", " ", query)

    return query


# ============================================================
# KEYWORD PATTERNS
# ============================================================

CONTACT_KEYWORDS = [
    "contact",
    "email",
    "phone",
    "mobile",
    "hod",
    "head",
    "director",
    "faculty",
    "staff",
]

DEADLINE_KEYWORDS = [
    "last date",
    "deadline",
    "due date",
    "apply before",
    "important date",
    "closing date",
]

LATEST_KEYWORDS = [
    "latest",
    "recent",
    "new",
    "newest",
    "current",
]

EVENT_KEYWORDS = [
    "event",
    "seminar",
    "conference",
    "workshop",
    "program",
]

TEMPORAL_KEYWORDS = [
    "next",
    "upcoming",
    "when",
    "schedule",
    "timetable",
    "calendar",
]


# ============================================================
# KEYWORD DETECTION
# ============================================================

def _contains_keyword(query: str, keywords: List[str]) -> bool:

    if not query:
        return False

    for keyword in keywords:

        if keyword in query:
            return True

    return False


# ============================================================
# ENTITY QUERY DETECTION
# ============================================================

def _looks_like_entity_query(query: str) -> bool:
    """
    Detects short entity-style queries.

    Examples:
    "oza"
    "computer science hod"
    "bsc syllabus"
    """

    tokens = _tokenize(query)

    if not tokens:
        return False

    # avoid classifying questions as entity queries
    question_words = {"who", "what", "when", "where", "why", "how"}

    if tokens[0] in question_words:
        return False

    # short queries likely entity lookup
    if len(tokens) <= 3:
        return True

    return False


# ============================================================
# QUERY CLASSIFICATION
# ============================================================

def classify_query(query: str) -> str:
    """
    Classifies query intent.
    """

    q = _normalize_query(query)

    if not q:
        return QUERY_GENERAL

    # contact queries
    if _contains_keyword(q, CONTACT_KEYWORDS):
        return QUERY_CONTACT

    # deadline queries
    if _contains_keyword(q, DEADLINE_KEYWORDS):
        return QUERY_DEADLINE

    # temporal queries
    if _contains_keyword(q, TEMPORAL_KEYWORDS):
        return QUERY_TEMPORAL

    # latest queries
    if _contains_keyword(q, LATEST_KEYWORDS):
        return QUERY_LATEST

    # event queries
    if _contains_keyword(q, EVENT_KEYWORDS):
        return QUERY_EVENT

    # entity queries
    if _looks_like_entity_query(q):
        return QUERY_FACT

    return QUERY_GENERAL


# ============================================================
# ROUTE QUERY
# ============================================================

def route_query(query: str) -> Dict:
    """
    Returns routing instructions for retrieval.

    Example output:

    {
        "query_type": "deadline",
        "use_temporal_boost": True,
        "entity_boost": False,
        "contact_priority": False,
        "expand_query": True,
        "use_graph": True
    }
    """

    query_type = classify_query(query)

    route = {
        "query_type": query_type,
        "use_temporal_boost": False,
        "entity_boost": False,
        "contact_priority": False,
        "expand_query": True,
        "use_graph": True,
    }

    # --------------------------------------------------------
    # CONTACT
    # --------------------------------------------------------

    if query_type == QUERY_CONTACT:

        route["entity_boost"] = True
        route["contact_priority"] = True

    # --------------------------------------------------------
    # DEADLINE
    # --------------------------------------------------------

    elif query_type == QUERY_DEADLINE:

        route["use_temporal_boost"] = True

    # --------------------------------------------------------
    # TEMPORAL
    # --------------------------------------------------------

    elif query_type == QUERY_TEMPORAL:

        route["use_temporal_boost"] = True

    # --------------------------------------------------------
    # LATEST
    # --------------------------------------------------------

    elif query_type == QUERY_LATEST:

        route["use_temporal_boost"] = True

    # --------------------------------------------------------
    # FACT
    # --------------------------------------------------------

    elif query_type == QUERY_FACT:

        route["entity_boost"] = True

    # --------------------------------------------------------
    # EVENT
    # --------------------------------------------------------

    elif query_type == QUERY_EVENT:

        route["use_temporal_boost"] = True

    return route