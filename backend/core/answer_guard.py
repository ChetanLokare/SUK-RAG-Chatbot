"""
Answer Guard (grounded version)

Goal: the user never sees an empty answer, but we also never make up
university facts to avoid one.

Order of attempts:
  1. Good answer from the main LLM call            -> return it
  2. One grounded retry using ONLY the context      -> return it
  3. Sentences extracted from the context (no LLM)  -> return them
  4. The LLM's own honest "not found" reply          -> return it
  5. A fixed "please check the official site" text

The old version had a final "give a general academic explanation" LLM
fallback and "Add useful details" prompts. Those invited the model to
invent fees, dates and contacts, so they were removed.
"""

from typing import Optional
import logging
import re

from backend.services.llm_service import call_llm
from backend.utils.query_normalize import expand_abbreviations


logger = logging.getLogger(__name__)


# =========================================================
# CONFIG
# =========================================================

MIN_ANSWER_LENGTH = 40
MIN_RETRY_LENGTH = 40
MAX_CONTEXT_CHARS = 3000

NOT_FOUND_MESSAGE = (
    "I could not find this in the university documents I have. "
    "Please check the official university website or try asking a more "
    "specific question."
)

# Phrases that mean "the model honestly said it does not know".
_DECLINE_PATTERNS = (
    "i don't know",
    "i do not know",
    "not sure",
    "no information",
    "cannot find",
    "could not find",
    "couldn't find",
    "not available in",
    "not mentioned",
    "does not contain",
    "do not contain",
)


# =========================================================
# HELPERS
# =========================================================

def _is_decline(answer: Optional[str]) -> bool:
    if not answer:
        return False
    a = answer.lower()
    return any(p in a for p in _DECLINE_PATTERNS)


def _is_weak(answer: Optional[str]) -> bool:
    """Empty, very short, or an honest 'I don't know'."""
    if not answer:
        return True
    if len(answer.strip()) < MIN_ANSWER_LENGTH:
        return True
    return _is_decline(answer)


def _safe_llm(prompt: str, question: str) -> Optional[str]:
    """Single LLM call, never raises, no loops."""
    try:
        result = call_llm(prompt=prompt, question=question)

        if not result:
            return None

        result = result.strip()

        return result if len(result) >= 20 else None

    except Exception as e:
        logger.warning("LLM failed: %s", e)
        return None


def _truncate_context(context: str) -> str:
    return (context or "")[:MAX_CONTEXT_CHARS]


def _normalize_query(question: str) -> str:
    """Whole-word abbreviation expansion (fixes the old substring bug)."""
    if not question:
        return ""
    return expand_abbreviations(question.strip()).lower()


def _extract_from_context(context: str, question: str) -> Optional[str]:
    """Pick the context sentences that overlap most with the question."""

    if not context:
        return None

    sentences = re.split(r"(?<=[\.\!\?])\s+", context)
    q_words = set(re.findall(r"\w+", question.lower()))

    scored = []

    for s in sentences:
        overlap = len(q_words & set(re.findall(r"\w+", s.lower())))
        if overlap > 0:
            scored.append((overlap, s))

    if not scored:
        return None  # unrelated text is not an answer

    scored.sort(key=lambda x: x[0], reverse=True)

    return " ".join(s for _, s in scored[:5])


# =========================================================
# MAIN FUNCTION
# =========================================================

def ensure_answer(
    question: str,
    context: Optional[str],
    answer: Optional[str],
) -> str:

    context = _truncate_context(context or "")
    question_clean = _normalize_query(question)

    # 1. Good answer -> done
    if not _is_weak(answer):
        return answer.strip()

    logger.warning("Weak or empty answer, trying grounded recovery")

    # 2. One grounded retry (only if we actually have sources)
    if context:
        prompt = f"""
Answer the question using ONLY the university context below.

QUESTION:
{question_clean}

CONTEXT:
{context}

RULES:
- Use only facts that appear in the context.
- Do NOT invent names, dates, fees, phone numbers or e-mail addresses.
- If the context does not contain the answer, say clearly that it is not
  in the documents.
- Keep it clear and structured.
"""
        retried = _safe_llm(prompt, question_clean)

        if retried and len(retried) >= MIN_RETRY_LENGTH and not _is_decline(retried):
            return retried

    # 3. Extract relevant sentences straight from the context (no LLM)
    extracted = _extract_from_context(context, question_clean)

    if extracted:
        return extracted

    # 4. The model's own honest decline is better than a made-up answer
    if answer and _is_decline(answer) and len(answer.strip()) >= 20:
        return answer.strip()

    # 5. Fixed fallback
    logger.error("No grounded answer available")
    return NOT_FOUND_MESSAGE
