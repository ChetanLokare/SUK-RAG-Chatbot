# backend/core/llm_router.py

"""
LLM Router (FINAL PRODUCTION VERSION)

Purpose
-------
Routes requests between:
• OpenAI (primary)
• Gemini (fallback)

Supports:
• RAG mode (with context)
• Fallback mode (no context)

Key Improvements
----------------
• No over-strict "ONLY context" restriction
• Allows intelligent completion when context is partial
• Better failure handling
• Compatible with Answer Guard
"""

from typing import Optional
import logging

from openai import OpenAI
from google import genai

from backend.core.config import OPENAI_API_KEY, GEMINI_API_KEY
from backend.utils.language_detect import get_response_language


# =========================================================
# LOGGER
# =========================================================

logger = logging.getLogger(__name__)


# =========================================================
# CLIENT INITIALIZATION
# =========================================================

openai_client = None
gemini_client = None

if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        logger.warning("OpenAI init failed: %s", str(e))
        openai_client = None

if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.warning("Gemini init failed: %s", str(e))
        gemini_client = None


# =========================================================
# LANGUAGE HELPER
# =========================================================

def _language_instruction(language: str) -> str:

    if language == "mr":
        return "Respond in Marathi."

    if language == "hi":
        return "Respond in Hindi."

    return "Respond in English."


# =========================================================
# OPENAI CORE
# =========================================================

def _ask_openai(system_prompt: str, user_prompt: str) -> Optional[str]:

    if not openai_client:
        return None

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1200,
        )

        if not response.choices:
            return None

        content = response.choices[0].message.content

        if not content:
            return None

        return content.strip()

    except Exception as e:
        logger.warning("OpenAI call failed: %s", str(e))
        return None


# =========================================================
# GEMINI CORE
# =========================================================

def _ask_gemini(system_prompt: str, user_prompt: str) -> Optional[str]:

    if not gemini_client:
        return None

    try:
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=combined_prompt,
        )

        text = getattr(response, "text", None)

        if not text:
            return None

        return text.strip()

    except Exception as e:
        logger.warning("Gemini call failed: %s", str(e))
        return None


# =========================================================
# RAG MODE (WITH CONTEXT)
# =========================================================

def ask_llm(question: str, context: str) -> Optional[str]:
    """
    Generate answer using RAG context.
    """

    if not context or len(context.strip()) < 20:
        return None

    try:
        language = get_response_language(question)
    except Exception:
        language = "en"

    # 🔥 RELAXED RULES (CRITICAL FIX)
    system_prompt = (
        "You are the official AI assistant for Shivaji University.\n\n"
        "GUIDELINES:\n"
        "- Use the provided context as primary source\n"
        "- You MAY slightly enhance the answer if context is incomplete\n"
        "- Do NOT hallucinate specific facts\n"
        "- Combine multiple pieces of information\n"
        "- Provide clear, structured answers\n\n"
        "RESPONSE FORMAT:\n"
        "1. Overview\n"
        "2. Key Details\n"
        "3. Additional Info (if available)\n\n"
        + _language_instruction(language)
    )

    user_prompt = f"""
CONTEXT:
{context}

QUESTION:
{question}

INSTRUCTIONS:
- Extract as much useful information as possible
- If context is partial, still provide a helpful answer
- Use bullet points where useful
"""

    # -----------------------------------------------------
    # OpenAI FIRST
    # -----------------------------------------------------

    answer = _ask_openai(system_prompt, user_prompt)

    if answer:
        return answer

    # -----------------------------------------------------
    # Gemini fallback
    # -----------------------------------------------------

    answer = _ask_gemini(system_prompt, user_prompt)

    if answer:
        return answer

    return None


# =========================================================
# FALLBACK MODE (NO CONTEXT)
# =========================================================

def ask_llm_fallback(question: str) -> Optional[str]:
    """
    General knowledge fallback.
    """

    try:
        language = get_response_language(question)
    except Exception:
        language = "en"

    system_prompt = (
        "You are a helpful assistant.\n"
        "Answer clearly and helpfully.\n"
        "Do NOT fabricate specific university facts.\n"
        "If unsure, provide general guidance.\n\n"
        + _language_instruction(language)
    )

    user_prompt = f"""
QUESTION:
{question}

Provide a helpful and clear answer.
"""

    answer = _ask_openai(system_prompt, user_prompt)

    if answer:
        return answer

    answer = _ask_gemini(system_prompt, user_prompt)

    if answer:
        return answer

    return None