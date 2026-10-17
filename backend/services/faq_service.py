# backend/services/faq_service.py

from typing import List, Dict
from sqlalchemy.orm import Session

from backend.registry.models import FAQ
from backend.services.llm_service import call_llm


# ============================================================
# PARSE LLM FAQ RESPONSE SAFELY
# ============================================================

def _parse_faq_response(raw_text: str) -> List[Dict[str, str]]:
    """
    Parses LLM response safely.

    Expected format:

    Q: Question text
    A: Answer text

    Returns:
        [
            {"question": "...", "answer": "..."},
            ...
        ]
    """

    if not raw_text:
        return []

    faqs = []

    blocks = raw_text.split("Q:")

    for block in blocks:
        block = block.strip()

        if not block:
            continue

        if "A:" not in block:
            continue

        parts = block.split("A:", 1)

        question = parts[0].strip()
        answer = parts[1].strip()

        if len(question) < 10 or len(answer) < 20:
            continue

        faqs.append({
            "question": question,
            "answer": answer,
        })

    return faqs


# ============================================================
# GENERATE FAQ FROM CONTENT
# ============================================================

def generate_faqs_from_content(text: str) -> List[Dict[str, str]]:
    """
    Uses LLM to generate structured FAQs.

    Returns list of {question, answer}
    """

    if not text or len(text) < 500:
        return []

    prompt = f"""
Generate 5 high-quality FAQ pairs from the content below.

Rules:
- Use same language as content.
- Questions must be meaningful and specific.
- Answers must be factual and based only on the content.
- Do NOT invent information.
- Format strictly as:

Q: Question text
A: Answer text

Content:
{text[:6000]}
"""

    try:
        raw_response = call_llm(prompt)
    except Exception:
        return []

    return _parse_faq_response(raw_response)


# ============================================================
# UPDATE FAQS FOR SOURCE
# ============================================================

def update_faqs_for_source(
    db: Session,
    source_id: str,
    full_text: str,
) -> int:
    """
    Regenerates FAQs for a source.

    - Deletes old FAQs
    - Generates new ones
    - Saves them safely

    Returns number of FAQs saved.
    """

    if not full_text or len(full_text) < 500:
        return 0

    # Generate FAQs
    faq_items = generate_faqs_from_content(full_text)

    if not faq_items:
        return 0

    # Delete old FAQs
    db.query(FAQ).filter(
        FAQ.source_id == source_id
    ).delete()

    # Insert new FAQs
    saved_count = 0

    for item in faq_items:

        faq = FAQ(
            source_id=source_id,
            question=item["question"],
            answer=item["answer"],
        )

        db.add(faq)
        saved_count += 1

    db.commit()

    return saved_count


# ============================================================
# FETCH FAQS FOR QUERY MATCHING
# ============================================================

def search_faqs(
    db: Session,
    query: str,
    category: str | None = None,
):
    """
    Lightweight FAQ search.

    Used before hybrid search to quickly answer common questions.
    """

    query_lower = query.lower()

    faqs = db.query(FAQ).all()

    matched = []

    for faq in faqs:
        if query_lower in faq.question.lower():
            matched.append({
                "question": faq.question,
                "answer": faq.answer,
            })

    return matched
