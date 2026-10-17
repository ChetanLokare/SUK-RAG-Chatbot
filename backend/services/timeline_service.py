# backend/services/timeline_service.py

import re
from datetime import datetime
from typing import List, Dict, Optional

from backend.services.llm_service import call_llm


# ==========================================================
# MULTILINGUAL MONTH MAPPING
# ==========================================================

MONTH_MAP = {
    # English
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,

    # Hindi
    "जनवरी": 1, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4,
    "मई": 5, "जून": 6, "जुलाई": 7, "अगस्त": 8,
    "सितंबर": 9, "अक्टूबर": 10, "नवंबर": 11, "दिसंबर": 12,

    # Marathi
    "जानेवारी": 1, "फेब्रुवारी": 2, "मार्च": 3, "एप्रिल": 4,
    "मे": 5, "जून": 6, "जुलै": 7, "ऑगस्ट": 8,
    "सप्टेंबर": 9, "ऑक्टोबर": 10, "नोव्हेंबर": 11, "डिसेंबर": 12,
}


# ==========================================================
# DATE PATTERNS
# ==========================================================

# 12 January 2025
TEXT_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\s+([A-Za-z\u0900-\u097F]+)\s+(\d{4})\b",
    re.IGNORECASE
)

# 12/01/2025 or 12-01-2025
NUMERIC_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"
)

# Year only (used carefully)
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


# ==========================================================
# SAFE DATE PARSER
# ==========================================================

def _parse_text_date(day: str, month_str: str, year: str) -> Optional[datetime]:

    month_key = month_str.lower()

    if month_key not in MONTH_MAP:
        return None

    try:
        return datetime(
            int(year),
            MONTH_MAP[month_key],
            int(day)
        )
    except Exception:
        return None


def _parse_numeric_date(day: str, month: str, year: str) -> Optional[datetime]:
    try:
        return datetime(
            int(year),
            int(month),
            int(day)
        )
    except Exception:
        return None


# ==========================================================
# EXTRACT RAW DATE OCCURRENCES
# ==========================================================

def extract_dates(text: str) -> List[Dict]:
    """
    Returns list of:
    {
        "date": datetime,
        "raw": original_string,
        "context": nearby_text
    }
    """

    results = []

    # ---- Text-based dates ----
    for match in TEXT_DATE_PATTERN.finditer(text):

        day, month_str, year = match.groups()
        parsed = _parse_text_date(day, month_str, year)

        if not parsed:
            continue

        start = max(match.start() - 120, 0)
        end = min(match.end() + 120, len(text))

        context = text[start:end].strip()

        results.append({
            "date": parsed,
            "raw": match.group(0),
            "context": context
        })

    # ---- Numeric dates ----
    for match in NUMERIC_DATE_PATTERN.finditer(text):

        day, month, year = match.groups()
        parsed = _parse_numeric_date(day, month, year)

        if not parsed:
            continue

        start = max(match.start() - 120, 0)
        end = min(match.end() + 120, len(text))

        context = text[start:end].strip()

        results.append({
            "date": parsed,
            "raw": match.group(0),
            "context": context
        })

    return results


# ==========================================================
# SORT TIMELINE
# ==========================================================

def _sort_events(events: List[Dict]) -> List[Dict]:
    return sorted(events, key=lambda x: x["date"])


# ==========================================================
# BUILD STRUCTURED TIMELINE (LLM ASSISTED)
# ==========================================================

def build_timeline_from_text(text: str) -> str:
    """
    Extracts events + dates.
    Uses LLM to summarize event description.
    Returns formatted chronological timeline.
    """

    extracted = extract_dates(text)

    if not extracted:
        return "No timeline information found."

    events = []

    for item in extracted:

        prompt = f"""
Extract the key event related to the date below.
Be concise.
Return only the event description.

Text:
{item["context"]}
"""

        try:
            event_summary = call_llm(prompt)
        except Exception:
            event_summary = item["context"][:200]

        events.append({
            "date": item["date"],
            "event": event_summary.strip(),
        })

    # Sort chronologically
    events = _sort_events(events)

    # Format output
    formatted = []
    for e in events:
        formatted.append(
            f"{e['date'].strftime('%d %B %Y')} - {e['event']}"
        )

    return "\n".join(formatted)


# ==========================================================
# SMART TIMELINE ANSWER (FOR CHAT)
# ==========================================================

def answer_timeline_query(query: str, context: str) -> str:
    """
    Generates timeline answer in same language as query.
    """

    base_timeline = build_timeline_from_text(context)

    if not base_timeline:
        return "No relevant timeline found."

    prompt = f"""
Answer in the SAME language as the query.

User query:
{query}

Timeline:
{base_timeline}
"""

    try:
        return call_llm(prompt)
    except Exception:
        return base_timeline
