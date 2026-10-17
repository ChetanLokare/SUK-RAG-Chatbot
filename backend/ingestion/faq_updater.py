# backend/ingestion/faq_updater.py

import re
from typing import List, Tuple
from sqlalchemy.orm import Session

from backend.registry.models import FAQ
from backend.services.llm_service import call_llm


# ============================================================
# PARSE LLM FAQ OUTPUT SAFELY
# ============================================================

def _parse_faq_output(text: str) -> List[Tuple[str, str]]:
    """
    Parses LLM output into (question, answer) pairs.

    Expected format:

    Q: ...
    A: ...

    Returns clean list of tuples.
    """

    if not text:
        return []

    # Normalize spacing
    text = text.strip()

    # Split on Q:
    blocks = re.split(r"\n?\s*Q\s*:\s*", text, flags=re.IGNORECASE)

    faqs = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        parts = re.split(r"\n?\s*A\s*:\s*", block, flags=re.IGNORECASE)

        if len(parts) != 2:
            continue

        question = parts[0].strip()
        answer = parts[1].strip()

        if len(question) < 10 or len(answer) < 10:
            continue

        faqs.append((question, answer))

    return faqs


# ============================================================
# GENERATE FAQ FROM CONTENT
# ============================================================

def _generate_faqs_from_content(text: str) -> List[Tuple[str, str]]:
    """
    Calls LLM to generate FAQs from content.
    """

    if not text or len(text) < 300:
        return []

    prompt = f"""
You are generating FAQs for a university knowledge system.

Generate 5 clear question-answer pairs from the content below.

Rules:
- Questions must be clear and specific.
- Answers must be factual and concise.
- Do NOT invent information.
- Use format strictly:

Q: ...
A: ...

Content:
{text}
"""

    try:
        response = call_llm(prompt)
    except Exception:
        return []

    return _parse_faq_output(response)


# ============================================================
# MAIN FAQ UPDATE FUNCTION
# ============================================================

def update_faqs(
    db: Session,
    source_id: str,
    full_text: str,
):
    """
    Regenerates FAQs when URL content changes.

    Safe:
    ✔ Never crashes ingestion
    ✔ Clears old FAQs
    ✔ Deduplicates
    ✔ Commits once
    """

    try:
        # -----------------------------------------------
        # 1️⃣ Generate new FAQs
        # -----------------------------------------------

        faq_pairs = _generate_faqs_from_content(full_text)

        if not faq_pairs:
            return {
                "status": "no_faq_generated",
                "faqs_created": 0,
            }

        # -----------------------------------------------
        # 2️⃣ Remove old FAQs for this source
        # -----------------------------------------------

        db.query(FAQ).filter(
            FAQ.source_id == source_id
        ).delete()

        # -----------------------------------------------
        # 3️⃣ Deduplicate before insert
        # -----------------------------------------------

        seen = set()
        created = 0

        for question, answer in faq_pairs:

            normalized = question.lower().strip()

            if normalized in seen:
                continue

            seen.add(normalized)

            faq = FAQ(
                source_id=source_id,
                question=question.strip(),
                answer=answer.strip(),
            )

            db.add(faq)
            created += 1

        db.commit()

        return {
            "status": "faqs_updated",
            "faqs_created": created,
        }

    except Exception:
        # Never break ingestion because FAQ failed
        db.rollback()

        return {
            "status": "faq_generation_failed",
            "faqs_created": 0,
        }
