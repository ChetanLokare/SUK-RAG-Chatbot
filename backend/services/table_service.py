# backend/services/table_service.py

from typing import Optional, List, Dict

from backend.search.hybrid_search import hybrid_search
from backend.services.llm_service import call_llm


# ============================================================
# TABLE QUESTION DETECTION
# ============================================================

TABLE_KEYWORDS = [
    "fee",
    "fees",
    "scholarship",
    "eligibility",
    "criteria",
    "cutoff",
    "reservation",
    "quota",
    "documents",
    "last date",
    "deadline",
    "table",
    "amount",
    "structure",
    "admission process",
    "hostel fee",
    "exam fee",
]


def is_table_question(query: str) -> bool:
    """
    Detect whether question likely expects structured answer.
    """

    if not query:
        return False

    q = query.lower()

    return any(keyword in q for keyword in TABLE_KEYWORDS)


# ============================================================
# FORMAT STRUCTURED RESPONSE
# ============================================================

def _build_table_prompt(query: str, context: str) -> str:
    """
    Prompt that forces structured output.
    """

    return f"""
You are answering a university information question.

The user expects structured/tabular information.

Instructions:
- Extract structured data.
- Return answer in clean markdown table OR bullet format.
- Do NOT write long paragraphs.
- If numeric data exists, keep exact numbers.
- If eligibility or criteria exists, list clearly.

Question:
{query}

Context:
{context}
"""


# ============================================================
# FILTER TABLE-RELEVANT CHUNKS
# ============================================================

def _filter_table_chunks(results: List[Dict]) -> List[Dict]:
    """
    Prioritize chunks marked as table content.
    """

    if not results:
        return []

    # Prefer table-type metadata if exists
    table_chunks = [
        r for r in results
        if r.get("metadata", {}).get("content_type") == "table"
    ]

    if table_chunks:
        return table_chunks

    return results


# ============================================================
# MAIN TABLE ANSWER FUNCTION
# ============================================================

def answer_table_question(
    query: str,
    category: Optional[str] = None,
    language: Optional[str] = None,
    top_k: int = 6,
):
    """
    Returns structured answer if table-type question.

    Safe, production-ready.
    """

    try:
        # --------------------------------------------
        # 1️⃣ Retrieve Hybrid Search Results
        # --------------------------------------------

        results = hybrid_search(
            query=query,
            top_k=top_k,
            category=category,
            language=language,
        )

        if not results:
            return None

        # --------------------------------------------
        # 2️⃣ Prefer table-type content
        # --------------------------------------------

        filtered_results = _filter_table_chunks(results)

        # --------------------------------------------
        # 3️⃣ Build Context
        # --------------------------------------------

        context_parts = []

        for r in filtered_results:
            text = r.get("text")
            if not text:
                continue

            context_parts.append(text.strip())

        if not context_parts:
            return None

        context = "\n\n".join(context_parts)

        # --------------------------------------------
        # 4️⃣ Call LLM for structured formatting
        # --------------------------------------------

        prompt = _build_table_prompt(query, context)

        answer = call_llm(
            prompt=prompt,
            temperature=0.2,
        )

        if not answer:
            return None

        return answer.strip()

    except Exception as e:
        # Never crash chat endpoint
        print("TABLE SERVICE ERROR:", e)
        return None
