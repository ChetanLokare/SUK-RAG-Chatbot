# backend/ingestion/language_detector.py

import re


# ============================================================
# UNICODE RANGES
# ============================================================

DEVANAGARI_RANGE = r"\u0900-\u097F"
LATIN_RANGE = r"A-Za-z"


# ============================================================
# COMMON WORD HINTS (VERY IMPORTANT)
# ============================================================

HINDI_HINTS = [
    "है", "था", "थे", "किया", "करना", "विभाग", "विश्वविद्यालय"
]

MARATHI_HINTS = [
    "आहे", "होते", "होती", "विभाग", "विद्यापीठ", "माहिती"
]


# ============================================================
# CLEAN TEXT (IMPORTANT)
# ============================================================

def _prepare_text(text: str) -> str:
    """
    Remove numbers / symbols that confuse detection.
    """

    text = text.strip()

    # remove urls
    text = re.sub(r"https?://\S+", " ", text)

    # remove numbers heavy tables noise
    text = re.sub(r"\d+", " ", text)

    # collapse spaces
    text = re.sub(r"\s+", " ", text)

    return text


# ============================================================
# SCRIPT COUNT
# ============================================================

def _script_counts(text: str):

    devanagari_chars = re.findall(f"[{DEVANAGARI_RANGE}]", text)
    latin_chars = re.findall(f"[{LATIN_RANGE}]", text)

    return len(devanagari_chars), len(latin_chars)


# ============================================================
# HINT DETECTION
# ============================================================

def _has_hint(text: str, hints: list[str]) -> bool:
    text_lower = text.lower()
    return any(h in text_lower for h in hints)


# ============================================================
# MAIN DETECTOR
# ============================================================

def detect_language(text: str) -> str:
    """
    Production lightweight language detection.

    Returns:
    - en
    - mr
    - hi
    - mixed
    - unknown
    """

    if not text:
        return "unknown"

    text = _prepare_text(text)

    # Short text safety
    if len(text) < 40:
        # quick heuristic
        dev, lat = _script_counts(text)

        if dev == 0 and lat == 0:
            return "unknown"
        if lat > dev:
            return "en"
        if dev > lat:
            return "mr"

        return "mixed"

    dev_count, latin_count = _script_counts(text)

    if dev_count == 0 and latin_count == 0:
        return "unknown"

    total = dev_count + latin_count

    dev_ratio = dev_count / total if total else 0
    lat_ratio = latin_count / total if total else 0

    # ========================================================
    # CLEAR ENGLISH
    # ========================================================

    if lat_ratio > 0.85:
        return "en"

    # ========================================================
    # CLEAR DEVANAGARI
    # ========================================================

    if dev_ratio > 0.85:

        # Try Hindi vs Marathi hints
        if _has_hint(text, HINDI_HINTS):
            return "hi"

        if _has_hint(text, MARATHI_HINTS):
            return "mr"

        # University default → Marathi
        return "mr"

    # ========================================================
    # MIXED CONTENT (VERY COMMON FOR UNIVERSITY)
    # ========================================================

    if 0.25 < dev_ratio < 0.75:
        return "mixed"

    # ========================================================
    # SOFT DEVANAGARI DOMINANT
    # ========================================================

    if dev_ratio > lat_ratio:

        if _has_hint(text, HINDI_HINTS):
            return "hi"

        return "mr"

    # ========================================================
    # FALLBACK
    # ========================================================

    if latin_count > dev_count:
        return "en"

    return "mixed"