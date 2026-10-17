# backend/services/translation_service.py

from backend.services.llm_service import call_llm


def translate_text(text: str, target_lang: str) -> str:

    prompt = f"""
Translate the following text to {target_lang}.
Keep meaning intact. Do not add explanation.

Text:
{text}
"""

    return call_llm(prompt)
