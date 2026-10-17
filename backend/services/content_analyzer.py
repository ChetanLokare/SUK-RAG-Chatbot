# backend/services/content_analyzer.py

import re
from typing import Dict, Optional


# ==========================================================
# QUERY TYPE KEYWORDS
# ==========================================================

TABLE_KEYWORDS = [
    "amount",
    "fee",
    "fees",
    "scholarship",
    "eligibility",
    "criteria",
    "cutoff",
    "marks",
    "reservation",
    "quota",
    "list",
    "table",
    "structure",
    "details",
]

TIMELINE_KEYWORDS = [
    "date",
    "deadline",
    "last date",
    "schedule",
    "timeline",
    "important dates",
    "start",
    "end",
    "when",
    "admission date",
]

FAQ_PATTERNS = [
    r"what is",
    r"how to",
    r"who is",
    r"where is",
    r"can i",
    r"is there",
]


# Hindi / Marathi timeline hints
INDIC_TIMELINE_WORDS = [
    "तारीख",
    "दिनांक",
    "शेवटची तारीख",
    "अंतिम तिथि",
    "प्रवेश तारीख",
    "तारीख कब",
]


# ==========================================================
# LANGUAGE DETECTION (LIGHTWEIGHT)
# ==========================================================

def detect_language(text: str) -> str:
    """
    Lightweight language detection.
    No heavy models.
    """

    if not text:
        return "english"

    # Marathi/Hindi Unicode range
    if re.search(r"[\u0900-\u097F]", text):
        # Try detecting Marathi vs Hindi heuristically

        # Marathi common words
        if re.search(r"\b(आहे|करावे|विद्यापीठ|महाविद्यालय)\b", text):
            return "marathi"

        # Hindi common words
        if re.search(r"\b(है|करना|विश्वविद्यालय|महाविद्यालय)\b", text):
            return "hindi"

        return "hindi"

    return "english"


# ==========================================================
# QUERY TYPE DETECTION
# ==========================================================

def is_table_query(query: str) -> bool:
    q = query.lower()

    for keyword in TABLE_KEYWORDS:
        if keyword in q:
            return True

    return False


def is_timeline_query(query: str) -> bool:
    q = query.lower()

    for keyword in TIMELINE_KEYWORDS:
        if keyword in q:
            return True

    for word in INDIC_TIMELINE_WORDS:
        if word in query:
            return True

    return False


def is_faq_query(query: str) -> bool:
    q = query.lower()

    for pattern in FAQ_PATTERNS:
        if re.search(pattern, q):
            return True

    # Very short queries often FAQ style
    if len(q.split()) <= 6:
        return True

    return False


# ==========================================================
# DATE EXTRACTION (FOR TIMELINE SERVICE)
# ==========================================================

DATE_PATTERNS = [
    # 12/03/2025 or 12-03-2025
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",

    # 12 March 2025
    r"\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",

    # March 12, 2025
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",

    # Marathi / Hindi numeric date
    r"\b\d{1,2}\s+(मार्च|एप्रिल|मे|जून|जुलै|ऑगस्ट|सप्टेंबर|ऑक्टोबर|नोव्हेंबर|डिसेंबर)\s+\d{4}\b",

    r"\b\d{1,2}\s+(जनवरी|फ़रवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|अक्टूबर|नवंबर|दिसंबर)\s+\d{4}\b",
]


def extract_dates(text: str):
    """
    Extract all date-like strings.
    Lightweight regex based.
    """

    found = []

    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            if isinstance(matches[0], tuple):
                # When regex groups return tuple
                matches = [" ".join(m) for m in matches]
            found.extend(matches)

    return list(set(found))


# ==========================================================
# MAIN ANALYZER ENTRY
# ==========================================================

def analyze_query(query: str) -> Dict[str, Optional[str]]:
    """
    Central decision function.

    Returns:
    {
        "language": "...",
        "query_type": "table" | "timeline" | "faq" | "general"
    }
    """

    language = detect_language(query)

    if is_table_query(query):
        query_type = "table"
    elif is_timeline_query(query):
        query_type = "timeline"
    elif is_faq_query(query):
        query_type = "faq"
    else:
        query_type = "general"

    return {
        "language": language,
        "query_type": query_type,
    }
