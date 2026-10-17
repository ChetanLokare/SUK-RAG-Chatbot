"""
Production-grade query expansion module (FINAL VERSION)

Improves retrieval recall using:
• synonym expansion
• abbreviation expansion
• phrase expansion
• knowledge graph expansion

Designed for university RAG systems.
"""

import re
from typing import List, Set

from backend.graph.knowledge_graph import graph_instance


# ============================================================
# CONFIG
# ============================================================

MAX_EXPANSIONS = 10


# ============================================================
# SYNONYM MAP (🔥 FULL + IMPORTANT)
# ============================================================

SYNONYM_MAP = {

    # ----------------------------------------
    # Academic roles
    # ----------------------------------------
    "hod": [
        "head of department",
        "department head",
        "department chair"
    ],
    "faculty": [
        "teaching staff",
        "professors",
        "academic staff"
    ],

    # ----------------------------------------
    # Departments
    # ----------------------------------------
    "cs": [
        "computer science",
        "department of computer science"
    ],
    "it": [
        "information technology",
        "department of information technology"
    ],

    # ----------------------------------------
    # Fees
    # ----------------------------------------
    "fee": [
        "fees",
        "tuition fee",
        "course fee",
        "program fee",
        "fee structure"
    ],

    # ----------------------------------------
    # Scholarships
    # ----------------------------------------
    "scholarship": [
        "financial aid",
        "student grant",
        "funding",
        "scholarship scheme"
    ],

    # ----------------------------------------
    # Exams
    # ----------------------------------------
    "exam": [
        "examination",
        "university exam",
        "semester exam"
    ],

    "result": [
        "exam result",
        "examination result",
        "semester result"
    ],

    # ----------------------------------------
    # Admissions
    # ----------------------------------------
    "admission": [
        "apply",
        "application",
        "enrollment",
        "admission process"
    ],

    # ----------------------------------------
    # Contact
    # ----------------------------------------
    "contact": [
        "phone number",
        "email address",
        "contact details"
    ],
}


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
# TOKENIZE
# ============================================================

def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


# ============================================================
# SAFE WORD REPLACEMENT (🔥 FIX)
# ============================================================

def _replace_word(query: str, word: str, replacement: str) -> str:

    pattern = r"\b" + re.escape(word) + r"\b"

    return re.sub(pattern, replacement, query)


# ============================================================
# SYNONYM EXPANSION
# ============================================================

def _expand_synonyms(query: str) -> Set[str]:

    expansions: Set[str] = set()
    words = _tokenize(query)

    for word in words:

        if word in SYNONYM_MAP:

            for synonym in SYNONYM_MAP[word]:

                expanded = _replace_word(query, word, synonym)
                expansions.add(expanded)

    return expansions


# ============================================================
# PHRASE EXPANSION
# ============================================================

def _expand_phrases(query: str) -> Set[str]:

    expansions: Set[str] = set()

    PHRASE_RULES = {
        "dept": "department",
        "uni": "university",
        "university": "shivaji university",
    }

    for key, value in PHRASE_RULES.items():

        if key in query:
            expansions.add(_replace_word(query, key, value))

    return expansions


# ============================================================
# GRAPH EXPANSION (SAFE)
# ============================================================

def _expand_graph_entities(query: str) -> Set[str]:

    expansions: Set[str] = set()

    try:

        for node in graph_instance.graph.nodes:

            node_lower = node.lower()

            if node_lower in query:

                related = graph_instance.find_related(node)

                for _, target in related:

                    if not target:
                        continue

                    t = target.lower().strip()

                    if len(t) > 2:
                        expansions.add(t)

    except Exception:
        pass

    return expansions


# ============================================================
# DEDUPLICATE
# ============================================================

def _deduplicate(queries: Set[str]) -> List[str]:

    seen = set()
    results = []

    for q in queries:

        normalized = _normalize_query(q)

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        results.append(normalized)

    return results


# ============================================================
# MAIN FUNCTION
# ============================================================

def expand_query(query: str) -> List[str]:
    """
    Expand query into multiple semantically useful queries.
    """

    if not query or len(query.strip()) < 2:
        return [query]

    query = _normalize_query(query)

    expansions: Set[str] = {query}

    # ----------------------------------------
    # Apply expansions
    # ----------------------------------------

    expansions.update(_expand_synonyms(query))
    expansions.update(_expand_phrases(query))
    expansions.update(_expand_graph_entities(query))

    expanded_list = _deduplicate(expansions)

    return expanded_list[:MAX_EXPANSIONS]