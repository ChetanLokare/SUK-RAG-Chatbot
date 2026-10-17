# backend/utils/temporal_utils.py

import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

# ============================================================
# CONFIG
# ============================================================

UTC = timezone.utc

# Indian & common formats supported
DATE_PATTERNS = [
    r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",              # 12-05-2025
    r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s*\d{2,4}\b",  # 12 March 2025
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s*\d{2,4}\b",  # March 12, 2025
]

DATE_REGEX = re.compile("|".join(DATE_PATTERNS), re.IGNORECASE)

RELATIVE_KEYWORDS = {
    "today": 0,
    "tomorrow": 1,
    "day after tomorrow": 2,
    "next week": 7,
    "this week": 0,
    "next month": 30,
}

DEADLINE_KEYWORDS = [
    "last date",
    "deadline",
    "important date",
    "closing date",
    "final date",
]

# ============================================================
# SAFE DATE PARSER
# ============================================================

def _safe_parse(date_str: str) -> Optional[datetime]:
    """
    Tries multiple formats safely.
    """

    formats = [
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%m-%y",
        "%d/%m/%y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.replace(",", ""), fmt)
            return dt.replace(tzinfo=UTC)
        except Exception:
            continue

    return None


# ============================================================
# EXTRACT DATES FROM TEXT
# ============================================================

def extract_dates(text: str) -> List[datetime]:
    """
    Extracts all valid parsed dates from text.
    """

    if not text:
        return []

    matches = DATE_REGEX.findall(text)
    parsed_dates = []

    for match in matches:
        parsed = _safe_parse(match)
        if parsed:
            parsed_dates.append(parsed)

    return parsed_dates


# ============================================================
# DETECT DEADLINE TYPE
# ============================================================

def is_deadline_text(text: str) -> bool:
    """
    Detects if text likely represents deadline content.
    """

    t = text.lower()
    return any(keyword in t for keyword in DEADLINE_KEYWORDS)


# ============================================================
# UPCOMING FILTER
# ============================================================

def filter_upcoming(
    dates: List[datetime],
    days_ahead: int = 30,
) -> List[datetime]:
    """
    Returns only future dates within range.
    """

    now = datetime.now(UTC)
    future_limit = now + timedelta(days=days_ahead)

    return [
        d for d in dates
        if now <= d <= future_limit
    ]


# ============================================================
# EXPIRED FILTER
# ============================================================

def filter_expired(dates: List[datetime]) -> List[datetime]:
    now = datetime.now(UTC)
    return [d for d in dates if d < now]


# ============================================================
# RELATIVE QUERY DETECTION
# ============================================================

def detect_relative_query_window(query: str) -> Optional[Tuple[datetime, datetime]]:
    """
    Returns date window if query contains relative phrase.
    Example:
        "this week"
        "next month"
        "tomorrow"
    """

    if not query:
        return None

    query_lower = query.lower()
    now = datetime.now(UTC)

    for phrase, offset in RELATIVE_KEYWORDS.items():
        if phrase in query_lower:

            if phrase == "this week":
                start = now
                end = now + timedelta(days=7)
                return start, end

            if phrase == "next week":
                start = now + timedelta(days=7)
                end = start + timedelta(days=7)
                return start, end

            if phrase == "next month":
                start = now + timedelta(days=30)
                end = start + timedelta(days=30)
                return start, end

            # single day
            target = now + timedelta(days=offset)
            return target.replace(hour=0, minute=0, second=0), \
                   target.replace(hour=23, minute=59, second=59)

    return None


# ============================================================
# DATE BOOST SCORE
# ============================================================

def calculate_date_boost(
    query: str,
    text: str,
) -> float:
    """
    Returns multiplier boost based on date relevance.
    Used inside retriever or query engine.
    """

    boost = 1.0

    dates = extract_dates(text)

    if not dates:
        return boost

    now = datetime.now(UTC)

    # 1️⃣ Upcoming boost
    upcoming = filter_upcoming(dates, days_ahead=45)

    if upcoming:
        boost *= 1.15

    # 2️⃣ Deadline boost
    if is_deadline_text(text):
        boost *= 1.2

    # 3️⃣ Relative query boost
    window = detect_relative_query_window(query)

    if window:
        start, end = window

        for d in dates:
            if start <= d <= end:
                boost *= 1.4
                break

    # 4️⃣ Expired penalty
    if all(d < now for d in dates):
        boost *= 0.85

    return boost


# ============================================================
# SORT BY NEAREST FUTURE DATE
# ============================================================

def sort_by_nearest_future(
    contexts: List[dict],
) -> List[dict]:
    """
    Sorts contexts by closest future date.
    Keeps original score weight.
    """

    now = datetime.now(UTC)

    def nearest_date_score(ctx):
        dates = extract_dates(ctx.get("text", ""))

        future_dates = [d for d in dates if d >= now]

        if not future_dates:
            return float("inf")

        nearest = min(future_dates)
        return (nearest - now).total_seconds()

    return sorted(contexts, key=nearest_date_score)