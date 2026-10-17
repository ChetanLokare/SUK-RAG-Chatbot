# backend/utils/query_normalize.py
"""
Query abbreviation expansion.

Fixes a bug in the old implementation, which used str.replace() and so
rewrote *parts of words*: "with" -> "wiinformation technologyh",
"admit" -> "admiinformation technology", "cs" inside "physics", etc.

Rules now:
  - only whole words are expanded (regex word boundaries)
  - the original word is kept and the expansion is appended
    ("cs" -> "cs computer science"), so exact-match search still works
  - "IT" is only expanded when written in capitals, because lowercase
    "it" is an ordinary English word ("is it open?")
"""

import re
from typing import Dict

_ABBREVIATIONS: Dict[str, str] = {
    "cs": "computer science",
    "dept": "department",
    "hod": "head of department",
}

# Expanded only when the user typed it in capitals.
_CASE_SENSITIVE: Dict[str, str] = {
    "IT": "information technology",
}

_WORD = re.compile(r"\b\w+\b", flags=re.UNICODE)


def expand_abbreviations(text: str) -> str:
    """Append the full form after each known abbreviation (whole words only)."""

    if not text:
        return ""

    def _replace(match: "re.Match[str]") -> str:
        word = match.group(0)

        full = _CASE_SENSITIVE.get(word) or _ABBREVIATIONS.get(word.lower())

        if full:
            return f"{word} {full}"

        return word

    return _WORD.sub(_replace, text)
