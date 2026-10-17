# backend/nlp/entity_extractor.py

"""
Entity extraction + knowledge graph builder.

Extracts structured entities from text and stores them in the graph.

Entity types supported:
- departments
- courses
- monetary amounts
- academic years
"""

from typing import Dict, Set
import re
import logging

from backend.graph.knowledge_graph import graph_instance
from backend.nlp.entity_normalizer import normalize_entity
from backend.nlp.translation_cache import translate_to_english


logger = logging.getLogger(__name__)


# =========================================================
# PATTERNS
# =========================================================

DEPARTMENT_PATTERNS = [
    r"\bFaculty of [A-Za-z &\-]+",
    r"\bDepartment of [A-Za-z &\-]+",
]

COURSE_PATTERN = r"\b(B\.A\.|B\.Com\.|B\.Sc\.|M\.A\.|M\.Com\.|M\.Sc\.|MCA|BBA|BCA|Ph\.D\.?)\b"

AMOUNT_PATTERN = r"(₹\s?\d+(?:,\d+)*|\d+(?:,\d+)*\s?INR)"

YEAR_PATTERN = r"\b(20\d{2}(?:[-–]\d{2})?)\b"


# =========================================================
# SAFE REGEX FIND
# =========================================================

def _safe_find(pattern: str, text: str):

    try:
        return re.findall(pattern, text, flags=re.IGNORECASE)
    except Exception:
        return []


# =========================================================
# MAIN ENTITY EXTRACTION
# =========================================================

def extract_entities_and_build_graph(text: str) -> Dict[str, Set[str]]:
    """
    Extract entities from text and update knowledge graph.
    """

    if not text:
        return {}

    try:
        text = translate_to_english(text)
    except Exception:
        pass

    extracted_entities: Dict[str, Set[str]] = {
        "departments": set(),
        "courses": set(),
        "amounts": set(),
        "years": set(),
    }

    # -----------------------------------------------------
    # DEPARTMENTS
    # -----------------------------------------------------

    for pattern in DEPARTMENT_PATTERNS:

        matches = _safe_find(pattern, text)

        for dept in matches:

            normalized = normalize_entity(dept)

            extracted_entities["departments"].add(normalized)

            try:
                graph_instance.add_entity("department", normalized)
            except Exception:
                pass

    # -----------------------------------------------------
    # COURSES
    # -----------------------------------------------------

    courses = _safe_find(COURSE_PATTERN, text)

    for course in courses:

        extracted_entities["courses"].add(course)

        try:
            graph_instance.add_entity("course", course)
        except Exception:
            pass

    # -----------------------------------------------------
    # AMOUNTS
    # -----------------------------------------------------

    amounts = _safe_find(AMOUNT_PATTERN, text)

    for amount in amounts:

        extracted_entities["amounts"].add(amount)

        try:
            graph_instance.add_entity("amount", amount)
        except Exception:
            pass

    # -----------------------------------------------------
    # YEARS
    # -----------------------------------------------------

    years = _safe_find(YEAR_PATTERN, text)

    for year in years:

        extracted_entities["years"].add(year)

        try:
            graph_instance.add_entity("year", year)
        except Exception:
            pass

    # -----------------------------------------------------
    # RELATIONSHIPS
    # -----------------------------------------------------

    try:

        for dept in extracted_entities["departments"]:
            for course in extracted_entities["courses"]:

                graph_instance.add_relation(
                    source=dept,
                    relation="offers",
                    target=course,
                )

    except Exception:
        pass

    # -----------------------------------------------------
    # SAVE GRAPH
    # -----------------------------------------------------

    try:
        graph_instance.save()
    except Exception:
        logger.warning("Graph save failed")

    return extracted_entities