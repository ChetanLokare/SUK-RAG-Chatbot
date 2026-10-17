"""
Document classifier for SUK RAG system.

Automatically detects document type based on content.
Used during ingestion for metadata enrichment.
"""

import re
from typing import Dict


# ============================================================
# CATEGORY KEYWORDS
# ============================================================

CATEGORY_RULES: Dict[str, list] = {

    "exam_result": [
        "merit list",
        "rank list",
        "result",
        "marks statement",
        "seat number",
        "candidate name",
        "marks obtained",
    ],

    "timetable": [
        "time table",
        "timetable",
        "exam schedule",
        "examination schedule",
        "date and time",
        "paper code",
    ],

    "circular": [
        "circular",
        "notification",
        "important notice",
        "official notice",
        "office order",
    ],

    "syllabus": [
        "syllabus",
        "course structure",
        "course content",
        "programme structure",
        "credit structure",
    ],

    "admission_notice": [
        "admission",
        "application form",
        "eligibility criteria",
        "last date of application",
    ],

    "scholarship": [
        "scholarship",
        "financial assistance",
        "stipend",
        "fellowship",
    ]
}


# ============================================================
# NORMALIZE TEXT
# ============================================================

def _normalize(text: str) -> str:

    text = text.lower()

    text = re.sub(r"\s+", " ", text)

    return text


# ============================================================
# CLASSIFY DOCUMENT
# ============================================================

def classify_document(text: str) -> str:
    """
    Detect document type from content.

    Returns:
        exam_result
        timetable
        circular
        syllabus
        admission_notice
        scholarship
        general
    """

    if not text:
        return "general"

    text = _normalize(text)

    scores = {}

    for category, keywords in CATEGORY_RULES.items():

        score = 0

        for keyword in keywords:

            if keyword in text:
                score += 1

        if score > 0:
            scores[category] = score

    if not scores:
        return "general"

    # return highest scoring category
    return max(scores, key=scores.get)