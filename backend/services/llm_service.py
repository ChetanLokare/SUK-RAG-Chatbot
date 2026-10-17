import os
from typing import Optional

from openai import OpenAI
from google import genai

from backend.utils.language_detect import get_response_language


# =========================================================
# CONFIG
# =========================================================

# Keys are loaded from .env by backend.core.config
from backend.core.config import OPENAI_API_KEY, GEMINI_API_KEY

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

PRIMARY_MODEL = "gpt-4o-mini"
GEMINI_MODEL = "gemini-2.5-flash"

MAX_OUTPUT_TOKENS = 800

# 🔥 GLOBAL FLAG (CRITICAL FIX)
OPENAI_DISABLED = False


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT_BASE = """
You are an AI assistant that helps users find information about Shivaji University.

IMPORTANT:
- You are NOT an official source. Do not claim to be an official chatbot.

RULES:
- Answer ONLY from the provided context.
- Do NOT invent or guess names, dates, fees, phone numbers, e-mail addresses
  or rules. If a detail is not in the context, leave it out.
- If the context does not contain the answer, say so plainly and suggest
  checking the official university website.
- Combine information from several sources when they agree; mention it if
  they conflict.

FORMAT:
- Short, clear, structured answer. Use bullet points where they help.
- Simple questions get short answers; do not pad.
"""


# =========================================================
# LANGUAGE
# =========================================================

def _language_instruction(language: str) -> str:
    if language == "mr":
        return "Respond completely in Marathi."
    if language == "hi":
        return "Respond completely in Hindi."
    return "Respond completely in English."


# =========================================================
# OPENAI CALL
# =========================================================

def _call_openai(system_prompt: str, prompt: str) -> Optional[str]:

    global OPENAI_DISABLED

    if not openai_client or OPENAI_DISABLED:
        return None

    try:
        response = openai_client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=MAX_OUTPUT_TOKENS,
        )

        if not response or not response.choices:
            return None

        content = response.choices[0].message.content

        if not content:
            return None

        return content.strip()

    except Exception as e:
        print("❌ OpenAI error:", e)

        # 🔥 STOP ON QUOTA ERROR (VERY IMPORTANT)
        if "insufficient_quota" in str(e) or "429" in str(e):
            print("🚫 OpenAI quota exhausted → disabling OpenAI")
            OPENAI_DISABLED = True

        return None


# =========================================================
# GEMINI FALLBACK
# =========================================================

def _call_gemini(system_prompt: str, prompt: str) -> Optional[str]:

    if not gemini_client:
        return None

    try:
        combined_prompt = f"{system_prompt}\n\n{prompt}"

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=combined_prompt,
        )

        text = getattr(response, "text", None)

        if not text:
            return None

        return text.strip()

    except Exception as e:
        print("❌ Gemini error:", e)
        return None


# =========================================================
# ANSWER QUALITY CHECK
# =========================================================

def _is_bad_answer(answer: str) -> bool:
    """
    Only empty/very short replies count as bad (-> try the other provider).

    An honest "this is not in the documents" is a GOOD answer. Treating it
    as bad (old behaviour) pushed the pipeline towards making something up.
    """

    if not answer:
        return True

    return len(answer.strip()) < 25


# =========================================================
# MAIN LLM CALL (FINAL SAFE)
# =========================================================

def call_llm(
    prompt: str,
    question: Optional[str] = None,
    temperature: float = 0.3,
) -> Optional[str]:

    if not prompt:
        return None

    # -----------------------------------------------------
    # LANGUAGE DETECTION
    # -----------------------------------------------------

    language = "en"

    if question:
        try:
            language = get_response_language(question)
        except Exception:
            pass

    system_prompt = (
        SYSTEM_PROMPT_BASE
        + "\n\n"
        + _language_instruction(language)
    )

    print("🤖 LLM START")

    # -----------------------------------------------------
    # 1️⃣ OPENAI (ONLY ONCE)
    # -----------------------------------------------------

    result = _call_openai(system_prompt, prompt)

    if result and not _is_bad_answer(result):
        print("✅ OpenAI success")
        return result

    # -----------------------------------------------------
    # 2️⃣ GEMINI FALLBACK
    # -----------------------------------------------------

    print("🔁 Switching to Gemini")

    result = _call_gemini(system_prompt, prompt)

    if result and not _is_bad_answer(result):
        print("✅ Gemini success")
        return result

    # -----------------------------------------------------
    # FINAL FAIL
    # -----------------------------------------------------

    print("❌ ALL LLM FAILED")

    return None