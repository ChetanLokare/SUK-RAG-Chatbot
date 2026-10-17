# backend/services/language_service.py

from langdetect import detect


def detect_query_language(text: str) -> str:
    """
    Returns: en | mr | hi | unknown
    """

    try:
        lang = detect(text)

        if lang.startswith("mr"):
            return "mr"
        if lang.startswith("hi"):
            return "hi"
        if lang.startswith("en"):
            return "en"

        return "unknown"

    except Exception:
        return "unknown"
