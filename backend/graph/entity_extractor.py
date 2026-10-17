"""
Lightweight Entity Extractor for Knowledge Graph (PRODUCTION VERSION)

Extracts structured entities and builds clean relationships.

Improvements:
• context-aware linking
• better normalization
• avoids noisy graph edges
• supports Indian formats
"""

import re
from typing import Dict, List

from backend.graph.knowledge_graph import graph_instance


# =========================================================
# CONFIG
# =========================================================

WINDOW_SIZE = 300


# =========================================================
# PATTERNS (IMPROVED)
# =========================================================

DEPARTMENT_PATTERNS = [
    r"Faculty of [A-Za-z &\-]+",
    r"Department of [A-Za-z &\-]+",
    r"Dept\.? of [A-Za-z &\-]+",
    r"School of [A-Za-z &\-]+",
]

COURSE_PATTERN = r"\b(B\.?Sc\.?|M\.?Sc\.?|BCA|MCA|MBA|BBA|Ph\.?D\.?)\b"

AMOUNT_PATTERN = r"(₹\s?\d+(?:,\d+)*|\d+(?:,\d+)*\s?(?:INR|Rs\.?))"

YEAR_PATTERN = r"\b(20\d{2}(?:[-–]\d{2,4})?)\b"


# =========================================================
# NORMALIZATION HELPERS
# =========================================================

def _normalize(text: str) -> str:
    if not text:
        return ""

    text = text.strip()
    text = re.sub(r"\s+", " ", text)

    return text


def _normalize_course(course: str) -> str:
    course = course.upper().replace(".", "")

    mapping = {
        "BSC": "B.Sc",
        "MSC": "M.Sc",
        "BCA": "BCA",
        "MCA": "MCA",
        "MBA": "MBA",
        "BBA": "BBA",
        "PHD": "PhD",
    }

    return mapping.get(course, course)


def _normalize_amount(amount: str) -> str:
    amount = amount.replace("Rs.", "₹").replace("INR", "₹")
    return _normalize(amount)


# =========================================================
# WINDOW SPLIT
# =========================================================

def _split_windows(text: str) -> List[str]:
    return [
        text[i:i + WINDOW_SIZE]
        for i in range(0, len(text), WINDOW_SIZE)
    ]


# =========================================================
# ENTITY EXTRACTION
# =========================================================

def _extract_entities(text: str) -> Dict[str, List[str]]:

    departments = set()
    courses = set()
    amounts = set()
    years = set()

    # ----------------------------
    # departments
    # ----------------------------

    for pattern in DEPARTMENT_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            departments.add(_normalize(m))

    # ----------------------------
    # courses
    # ----------------------------

    matches = re.findall(COURSE_PATTERN, text, re.IGNORECASE)
    for m in matches:
        courses.add(_normalize_course(m))

    # ----------------------------
    # amounts
    # ----------------------------

    matches = re.findall(AMOUNT_PATTERN, text, re.IGNORECASE)
    for m in matches:
        amounts.add(_normalize_amount(m))

    # ----------------------------
    # years
    # ----------------------------

    matches = re.findall(YEAR_PATTERN, text)
    for m in matches:
        years.add(_normalize(m))

    return {
        "departments": list(departments),
        "courses": list(courses),
        "amounts": list(amounts),
        "years": list(years),
    }


# =========================================================
# GRAPH BUILDER (SMART LINKING)
# =========================================================

def extract_entities_and_build_graph(text: str):

    if not text or len(text) < 50:
        return

    # ---------------------------------------------------------
    # GLOBAL ENTITY REGISTRATION
    # ---------------------------------------------------------

    global_entities = _extract_entities(text)

    for dept in global_entities["departments"]:
        graph_instance.add_entity("department", dept)

    for course in global_entities["courses"]:
        graph_instance.add_entity("course", course)

    for amount in global_entities["amounts"]:
        graph_instance.add_entity("amount", amount)

    for year in global_entities["years"]:
        graph_instance.add_entity("year", year)

    # ---------------------------------------------------------
    # CONTEXT-AWARE RELATIONS (WINDOW BASED)
    # ---------------------------------------------------------

    windows = _split_windows(text)

    for window in windows:

        e = _extract_entities(window)

        departments = e["departments"]
        courses = e["courses"]
        amounts = e["amounts"]
        years = e["years"]

        # ----------------------------
        # dept → course
        # ----------------------------

        for dept in departments:
            for course in courses:
                graph_instance.add_relation(dept, "offers", course)

        # ----------------------------
        # course → fee
        # ----------------------------

        for course in courses:
            for amount in amounts:
                graph_instance.add_relation(course, "fee_amount", amount)

        # ----------------------------
        # course → year
        # ----------------------------

        for course in courses:
            for year in years:
                graph_instance.add_relation(course, "academic_year", year)

    # ---------------------------------------------------------
    # SAVE GRAPH
    # ---------------------------------------------------------

    try:
        graph_instance.save()
    except Exception:
        pass