# backend/nlp/entity_normalizer.py

"""
Entity normalization module.

Normalizes multilingual entity names into canonical form.
"""

from typing import Dict
import logging

from openai import OpenAI
from backend.core.config import OPENAI_API_KEY


logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

_normalization_cache: Dict[str, str] = {}


# =========================================================
# CANONICAL MAP
# =========================================================

CANONICAL_MAP = {
    "shivaji university": "Shivaji University Kolhapur",
    "shivaji vidyapeeth": "Shivaji University Kolhapur",
    "शिवाजी विद्यापीठ": "Shivaji University Kolhapur",
    "suk": "Shivaji University Kolhapur",
}


# =========================================================
# LLM NORMALIZATION
# =========================================================

def _llm_normalize(name: str) -> str:

    try:

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Normalize university-related entity names. "
                        "Translate to English if needed. "
                        "Return only the canonical entity name."
                    ),
                },
                {
                    "role": "user",
                    "content": name,
                },
            ],
        )

        content = response.choices[0].message.content

        return content.strip() if content else name

    except Exception as e:

        logger.warning("LLM normalization failed: %s", str(e))

        return name


# =========================================================
# MAIN NORMALIZER
# =========================================================

def normalize_entity(name: str) -> str:

    if not name:
        return name

    name_clean = name.strip()

    name_lower = name_clean.lower()

    # direct canonical
    if name_lower in CANONICAL_MAP:
        return CANONICAL_MAP[name_lower]

    # cache
    if name_clean in _normalization_cache:
        return _normalization_cache[name_clean]

    # LLM normalization
    normalized = _llm_normalize(name_clean)

    normalized_lower = normalized.lower()

    if normalized_lower in CANONICAL_MAP:
        normalized = CANONICAL_MAP[normalized_lower]

    _normalization_cache[name_clean] = normalized

    return normalized