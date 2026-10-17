# backend/ingestion/date_extractor.py

import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional


# ============================================================
# MONTH MAP
# ============================================================

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


# ============================================================
# DEADLINE KEYWORDS
# ============================================================

DEADLINE_KEYWORDS = [
    "last date",
    "deadline",
    "apply before",
    "extended till",
    "extended upto",
    "submission deadline",
    "closing date",
    "important date",
    "date of examination",
]


# ============================================================
# DATE PATTERNS
# ============================================================

# 12/03/2026 or 12-03-2026
NUMERIC_DATE_PATTERN = r"\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})\b"

# 12 March 2026
TEXTUAL_DATE_PATTERN = r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b"

# March 12, 2026
TEXTUAL_REVERSE_PATTERN = r"\b([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b"

# within 15 days
RELATIVE_PATTERN = r"\bwithin\s+(\d{1,3})\s+days\b"


# ============================================================
# DATE PARSER HELPERS
# ============================================================

def _safe_datetime(year: int, month: int, day: int) -> Optional[datetime]:
    try:
        return datetime(year, month, day)
    except Exception:
        return None


def _parse_numeric_date(match) -> Optional[datetime]:
    day, month, year = match.groups()

    day = int(day)
    month = int(month)
    year = int(year)

    if year < 100:
        year += 2000

    return _safe_datetime(year, month, day)


def _parse_textual_date(match) -> Optional[datetime]:
    day, month_str, year = match.groups()

    month = MONTH_MAP.get(month_str.lower())
    if not month:
        return None

    return _safe_datetime(int(year), month, int(day))


def _parse_reverse_textual_date(match) -> Optional[datetime]:
    month_str, day, year = match.groups()

    month = MONTH_MAP.get(month_str.lower())
    if not month:
        return None

    return _safe_datetime(int(year), month, int(day))


def _parse_relative_date(match) -> datetime:
    days = int(match.group(1))
    return datetime.utcnow() + timedelta(days=days)


# ============================================================
# MAIN EXTRACTION FUNCTION
# ============================================================

def extract_dates(text: str) -> List[Dict]:
    """
    Extracts all date occurrences from text.

    Returns list of:
    {
        "date": datetime,
        "date_str": ISO format,
        "is_deadline": bool,
        "context": snippet,
    }
    """

    if not text:
        return []

    results = []
    lower_text = text.lower()

    # --------------------------------------------------------
    # NUMERIC DATES
    # --------------------------------------------------------

    for match in re.finditer(NUMERIC_DATE_PATTERN, text):
        dt = _parse_numeric_date(match)
        if not dt:
            continue

        snippet = text[max(0, match.start() - 60): match.end() + 60]

        results.append({
            "date": dt,
            "date_str": dt.isoformat(),
            "is_deadline": any(k in snippet.lower() for k in DEADLINE_KEYWORDS),
            "context": snippet.strip(),
        })

    # --------------------------------------------------------
    # TEXTUAL DATES (12 March 2026)
    # --------------------------------------------------------

    for match in re.finditer(TEXTUAL_DATE_PATTERN, text):
        dt = _parse_textual_date(match)
        if not dt:
            continue

        snippet = text[max(0, match.start() - 60): match.end() + 60]

        results.append({
            "date": dt,
            "date_str": dt.isoformat(),
            "is_deadline": any(k in snippet.lower() for k in DEADLINE_KEYWORDS),
            "context": snippet.strip(),
        })

    # --------------------------------------------------------
    # TEXTUAL REVERSE (March 12, 2026)
    # --------------------------------------------------------

    for match in re.finditer(TEXTUAL_REVERSE_PATTERN, text):
        dt = _parse_reverse_textual_date(match)
        if not dt:
            continue

        snippet = text[max(0, match.start() - 60): match.end() + 60]

        results.append({
            "date": dt,
            "date_str": dt.isoformat(),
            "is_deadline": any(k in snippet.lower() for k in DEADLINE_KEYWORDS),
            "context": snippet.strip(),
        })

    # --------------------------------------------------------
    # RELATIVE DATES
    # --------------------------------------------------------

    for match in re.finditer(RELATIVE_PATTERN, lower_text):
        dt = _parse_relative_date(match)

        snippet = text[max(0, match.start() - 60): match.end() + 60]

        results.append({
            "date": dt,
            "date_str": dt.isoformat(),
            "is_deadline": True,
            "context": snippet.strip(),
        })

    return results


# ============================================================
# DEADLINE PICKER
# ============================================================

def extract_primary_deadline(text: str) -> Optional[Dict]:
    """
    Returns the most relevant upcoming deadline.
    """

    dates = extract_dates(text)

    if not dates:
        return None

    now = datetime.utcnow()

    # Prefer future deadlines
    future_deadlines = [
        d for d in dates
        if d["date"] >= now and d["is_deadline"]
    ]

    if future_deadlines:
        future_deadlines.sort(key=lambda x: x["date"])
        return future_deadlines[0]

    # Otherwise return nearest future date
    future_dates = [
        d for d in dates
        if d["date"] >= now
    ]

    if future_dates:
        future_dates.sort(key=lambda x: x["date"])
        return future_dates[0]

    return None