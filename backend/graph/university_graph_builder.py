"""
Automatic University Knowledge Graph Builder (FINAL PRODUCTION VERSION)

Features:
• context-aware linking (window-based)
• noise filtering
• safe entity normalization
• controlled relationship creation
• deduplicated graph edges
"""

import re
from typing import Dict, List, Set

from backend.graph.knowledge_graph import graph_instance


# =========================================================
# CONFIG
# =========================================================

WINDOW_SIZE = 400
MAX_RELATIONS_PER_WINDOW = 50


# =========================================================
# REGEX PATTERNS
# =========================================================

DEPARTMENT_PATTERN = re.compile(
    r"(Department of [A-Za-z &\-]+|Dept\.? of [A-Za-z &\-]+|School of [A-Za-z &\-]+)",
    re.IGNORECASE
)

FACULTY_PATTERN = re.compile(
    r"(Dr\.?\s+[A-Z][A-Za-z\.\-]+\s+[A-Z][A-Za-z\.\-]+|Prof\.?\s+[A-Z][A-Za-z\.\-]+\s+[A-Z][A-Za-z\.\-]+)",
    re.IGNORECASE
)

COURSE_PATTERN = re.compile(
    r"\b(B\.?Sc\.?|M\.?Sc\.?|BCA|MCA|MBA|BBA|Ph\.?D\.?)\b",
    re.IGNORECASE
)

EMAIL_PATTERN = re.compile(
    r"\b[\w\.-]+@[\w\.-]+\.\w+\b"
)

PHONE_PATTERN = re.compile(
    r"\b(?:\+91[- ]?)?\d{10}\b"
)

SCHOLARSHIP_PATTERN = re.compile(
    r"([A-Za-z ]+ Scholarship)",
    re.IGNORECASE
)

HOD_PATTERN = re.compile(
    r"\b(Head of Department|HOD)\b",
    re.IGNORECASE
)


# =========================================================
# NORMALIZATION
# =========================================================

def _normalize(text: str) -> str:

    if not text:
        return ""

    text = text.strip()
    text = re.sub(r"\s+", " ", text)

    return text


def _is_valid(text: str) -> bool:
    return bool(text and len(text) > 2)


# =========================================================
# ENTITY EXTRACTION
# =========================================================

def extract_entities(text: str) -> Dict[str, List[str]]:

    if not text:
        return {}

    return {
        "departments": list({_normalize(x) for x in DEPARTMENT_PATTERN.findall(text)}),
        "faculty": list({_normalize(x) for x in FACULTY_PATTERN.findall(text)}),
        "courses": list({_normalize(x) for x in COURSE_PATTERN.findall(text)}),
        "emails": list({_normalize(x) for x in EMAIL_PATTERN.findall(text)}),
        "phones": list({_normalize(x) for x in PHONE_PATTERN.findall(text)}),
        "scholarships": list({_normalize(x) for x in SCHOLARSHIP_PATTERN.findall(text)}),
        "roles": list({_normalize(x) for x in HOD_PATTERN.findall(text)}),
    }


# =========================================================
# WINDOW SPLIT
# =========================================================

def _split_into_windows(text: str) -> List[str]:

    return [
        text[i:i + WINDOW_SIZE]
        for i in range(0, len(text), WINDOW_SIZE)
    ]


# =========================================================
# SAFE RELATION ADD
# =========================================================

def _safe_add_relation(source: str, relation: str, target: str, seen: Set):

    if not (_is_valid(source) and _is_valid(target)):
        return

    key = (source, relation, target)

    if key in seen:
        return

    seen.add(key)

    try:
        graph_instance.add_relation(source, relation, target)
    except Exception:
        pass


# =========================================================
# GRAPH BUILDER
# =========================================================

def build_university_graph(text: str):

    if not text or len(text) < 100:
        return

    # -----------------------------------------------------
    # GLOBAL ENTITY REGISTRATION
    # -----------------------------------------------------

    entities = extract_entities(text)

    for dept in entities.get("departments", []):
        graph_instance.add_entity("department", dept)

    for person in entities.get("faculty", []):
        graph_instance.add_entity("person", person)

    for course in entities.get("courses", []):
        graph_instance.add_entity("course", course)

    for email in entities.get("emails", []):
        graph_instance.add_entity("email", email)

    for phone in entities.get("phones", []):
        graph_instance.add_entity("phone", phone)

    for scholarship in entities.get("scholarships", []):
        graph_instance.add_entity("scholarship", scholarship)

    # -----------------------------------------------------
    # CONTEXT WINDOWS
    # -----------------------------------------------------

    windows = _split_into_windows(text)

    for window in windows:

        e = extract_entities(window)

        departments = e.get("departments", [])
        faculty = e.get("faculty", [])
        courses = e.get("courses", [])
        emails = e.get("emails", [])
        phones = e.get("phones", [])
        scholarships = e.get("scholarships", [])
        roles = e.get("roles", [])

        relation_seen = set()
        relation_count = 0

        # -------------------------------
        # Department relationships
        # -------------------------------

        for dept in departments:

            for course in courses:
                _safe_add_relation(dept, "offers", course, relation_seen)

            for person in faculty:
                _safe_add_relation(dept, "has_faculty", person, relation_seen)

            for email in emails:
                _safe_add_relation(dept, "contact_email", email, relation_seen)

            for phone in phones:
                _safe_add_relation(dept, "contact_phone", phone, relation_seen)

        # -------------------------------
        # Faculty relationships
        # -------------------------------

        for person in faculty:

            for email in emails:
                _safe_add_relation(person, "email", email, relation_seen)

            for phone in phones:
                _safe_add_relation(person, "phone", phone, relation_seen)

            # HOD linking (ONLY if department present)
            if roles and departments:
                for dept in departments:
                    _safe_add_relation(person, "head_of", dept, relation_seen)

        # -------------------------------
        # Scholarship relationships
        # -------------------------------

        for scholarship in scholarships:

            for course in courses:
                _safe_add_relation(scholarship, "applies_to", course, relation_seen)

        # -------------------------------
        # LIMIT RELATIONS (ANTI-NOISE)
        # -------------------------------

        relation_count += len(relation_seen)

        if relation_count > MAX_RELATIONS_PER_WINDOW:
            break

    # -----------------------------------------------------
    # SAVE GRAPH
    # -----------------------------------------------------

    try:
        graph_instance.save()
    except Exception:
        pass