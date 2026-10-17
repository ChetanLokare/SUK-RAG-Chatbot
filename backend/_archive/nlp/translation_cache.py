# backend/nlp/translation_cache.py

"""
Translation utility for multilingual text.

Used before entity extraction to ensure consistent processing.
"""

from typing import Dict
import logging

from openai import OpenAI
from backend.core.config import OPENAI_API_KEY


logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

_translation_cache: Dict[str, str] = {}


# =========================================================
# TRANSLATION
# =========================================================

def translate_to_english(text: str) -> str:

    if not text:
        return text

    if text in _translation_cache:
        return _translation_cache[text]

    try:

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "Translate the following text to English.",
                },
                {
                    "role": "user",
                    "content": text,
                },
            ],
        )

        translated = response.choices[0].message.content.strip()

        _translation_cache[text] = translated

        return translated

    except Exception as e:

        logger.warning("Translation failed: %s", str(e))

        return text