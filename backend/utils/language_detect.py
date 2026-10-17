"""
Language Detection Utility

Purpose
-------
Detect the language of a user query or text input.

Used by:
- query pipeline
- LLM router
- multilingual response control

Supported Languages
-------------------
en  -> English
mr  -> Marathi
hi  -> Hindi
unknown -> fallback

Design Goals
------------
• fast detection
• stable for short queries
• never crash pipeline
• normalize language codes
"""

from langdetect import detect, DetectorFactory, LangDetectException
import re


# ============================================================
# ENSURE STABLE RESULTS
# ============================================================

DetectorFactory.seed = 0


# ============================================================
# SCRIPT DETECTION
# ============================================================

DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")
LATIN_REGEX = re.compile(r"[a-zA-Z]")


def _contains_devanagari(text: str) -> bool:
    """
    Detect if text contains Devanagari script.
    """

    if not text:
        return False

    return bool(DEVANAGARI_REGEX.search(text))


def _contains_latin(text: str) -> bool:
    """
    Detect if text contains Latin characters.
    """

    if not text:
        return False

    return bool(LATIN_REGEX.search(text))


# ============================================================
# TEXT CLEANING
# ============================================================

_whitespace_regex = re.compile(r"\s+")


def _clean_text(text: str) -> str:
    """
    Normalize input text.
    """

    if not text:
        return ""

    text = _whitespace_regex.sub(" ", text)

    return text.strip()


# ============================================================
# NORMALIZE LANGUAGE
# ============================================================

def _normalize_language(lang: str) -> str:
    """
    Normalize language codes returned by langdetect.
    """

    if not lang:
        return "unknown"

    lang = lang.lower()

    if lang.startswith("en"):
        return "en"

    if lang.startswith("mr"):
        return "mr"

    if lang.startswith("hi"):
        return "hi"

    return "unknown"


# ============================================================
# MAIN LANGUAGE DETECTOR
# ============================================================

def detect_query_language(text: str) -> str:
    """
    Detect language of user query.

    Returns
    -------
    en | mr | hi | unknown
    """

    if not text:
        return "unknown"

    cleaned = _clean_text(text)

    if len(cleaned) < 3:
        return "unknown"

    # --------------------------------------------------------
    # DEVANAGARI QUICK PATH
    # --------------------------------------------------------

    if _contains_devanagari(cleaned):

        try:
            lang = detect(cleaned)

            normalized = _normalize_language(lang)

            if normalized != "unknown":
                return normalized

        except LangDetectException:
            pass

        # fallback guess
        return "mr"

    # --------------------------------------------------------
    # LATIN SCRIPT
    # --------------------------------------------------------

    if _contains_latin(cleaned):

        try:
            lang = detect(cleaned)
            return _normalize_language(lang)

        except LangDetectException:
            return "unknown"

    return "unknown"


# ============================================================
# RESPONSE LANGUAGE HELPER
# ============================================================

def get_response_language(query: str) -> str:
    """
    Determine which language the assistant should reply in.

    Ensures responses match the user's query language.
    """

    lang = detect_query_language(query)

    if lang == "unknown":
        return "en"

    return lang


# ============================================================
# DEBUG / TEST
# ============================================================

if __name__ == "__main__":

    tests = [
        "give info about university",
        "विद्यापीठाबद्दल माहिती द्या",
        "विश्वविद्यालय के बारे में जानकारी दें",
        "Kolhapur information",
        "शिष्यवृत्ती",
        "Scholarship details",
    ]

    for t in tests:

        print("Query:", t)
        print("Detected:", detect_query_language(t))
        print("-" * 40)