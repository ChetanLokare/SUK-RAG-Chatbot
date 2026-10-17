from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import threading

from backend.core.config import MAX_CONCURRENT_QUERIES, QUERY_QUEUE_WAIT_SECONDS
from backend.core.conversation import (
    normalize_history,
    build_retrieval_query,
    format_history,
)

from backend.search.hybrid_search import hybrid_search
from backend.retrieval.context_compressor import compress_contexts
from backend.retrieval.adaptive_topk import dynamic_top_k

from backend.core.answer_synthesizer import synthesize_answer
from backend.services.llm_service import call_llm
from backend.core.answer_guard import ensure_answer, NOT_FOUND_MESSAGE


router = APIRouter(tags=["Query"])


# ============================================================
# CONCURRENCY LIMIT
# ============================================================
# Replaces the old global lock, which allowed ONE request at a time and
# answered "System is busy" to everyone else. Now up to
# MAX_CONCURRENT_QUERIES run together; extra requests wait briefly.

query_slots = threading.BoundedSemaphore(MAX_CONCURRENT_QUERIES)


# ============================================================
# REQUEST MODEL
# ============================================================

class HistoryMessage(BaseModel):
    role: str = "user"                # "user" | "bot" | "assistant"
    text: Optional[str] = None        # the frontend sends "text"
    content: Optional[str] = None     # also accepted


class QueryRequest(BaseModel):
    question: str = Field(..., max_length=2000)
    category: Optional[str] = None
    language: Optional[str] = None
    top_k: Optional[int] = None
    history: Optional[List[HistoryMessage]] = Field(default=None, max_length=50)


# ============================================================
# CONSTANTS (🔥 OPTIMIZED)
# ============================================================

MIN_RETRIEVAL_K = 6
MAX_RETRIEVAL_K = 12   # 🔥 reduced
MAX_CONTEXT_CHUNKS = 5 # 🔥 reduced
MAX_CONTEXT_CHARS = 1200  # 🔥 reduced


# ============================================================
# SAFE TOP-K
# ============================================================

def _safe_top_k(value: int) -> int:
    try:
        value = int(value)
    except Exception:
        return 10

    if value < MIN_RETRIEVAL_K:
        return MIN_RETRIEVAL_K

    if value > MAX_RETRIEVAL_K:
        return MAX_RETRIEVAL_K

    return value


# ============================================================
# DEDUPE CITATIONS
# ============================================================

def _dedupe_citations(citations: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []

    for c in citations:
        key = (c.get("source_value"), c.get("page_number"))

        if key in seen:
            continue

        seen.add(key)
        unique.append(c)

    return unique


# ============================================================
# BUILD RAW CONTEXT
# ============================================================

def _build_raw_context(chunks: List[Dict]) -> str:

    if not chunks:
        return ""

    parts = []

    for c in chunks[:MAX_CONTEXT_CHUNKS]:
        text = (c.get("text") or "").strip()

        if text:
            parts.append(text)

    context = "\n\n".join(parts)

    # 🔥 HARD LIMIT
    return context[:MAX_CONTEXT_CHARS]


# ============================================================
# MAIN QUERY ENDPOINT
# ============================================================

@router.post("/query")
def query_system(request: QueryRequest):

    # Wait briefly for a free slot instead of rejecting everyone while
    # one request is running (old behaviour).
    if not query_slots.acquire(timeout=QUERY_QUEUE_WAIT_SECONDS):
        return {
            "answer": "The system is busy right now. Please try again in a few seconds.",
            "verified": False,
            "citations": [],
        }

    try:

        question = (request.question or "").strip()

        if not question:
            return {
                "answer": "Please provide a valid question.",
                "verified": False,
                "citations": [],
            }

        print("\n🔍 QUERY:", question)

        # ---------------------------------------------------------
        # 0️⃣ CONVERSATION CONTEXT (follow-up questions)
        # ---------------------------------------------------------

        history = normalize_history(request.history, question)

        # Short follow-ups ("and the fees?") borrow the previous question
        # for SEARCH only; the LLM still sees the user's real question.
        search_query = build_retrieval_query(question, history)

        if search_query != question:
            print("🔗 Follow-up → retrieval query:", search_query)

        # ---------------------------------------------------------
        # 1️⃣ DETERMINE TOP-K
        # ---------------------------------------------------------

        try:
            if request.top_k is not None:
                retrieval_k = _safe_top_k(request.top_k)
            else:
                retrieval_k = dynamic_top_k(search_query)
        except Exception as e:
            print("⚠️ Top-K fallback:", e)
            retrieval_k = 10

        print("📊 Retrieval K:", retrieval_k)

        # ---------------------------------------------------------
        # 2️⃣ RETRIEVAL
        # ---------------------------------------------------------

        try:
            retrieved_chunks = hybrid_search(
                query=search_query,
                top_k=retrieval_k,
                category=request.category,
            )
        except Exception as e:
            print("❌ Retrieval failed:", e)
            retrieved_chunks = []

        print("📦 Retrieved chunks:", len(retrieved_chunks))

        # ---------------------------------------------------------
        # 3️⃣ COMPRESS CONTEXT
        # ---------------------------------------------------------

        if retrieved_chunks:
            try:
                retrieved_chunks = compress_contexts(
                    search_query,
                    retrieved_chunks,
                    max_contexts=10,
                )
            except Exception as e:
                print("⚠️ Compression failed:", e)

        print("🧠 Contexts after compression:", len(retrieved_chunks))

        # ---------------------------------------------------------
        # 4️⃣ BUILD RAW CONTEXT
        # ---------------------------------------------------------

        raw_context = _build_raw_context(retrieved_chunks)

        print("🧠 Raw context length:", len(raw_context))

        # ---------------------------------------------------------
        # 5️⃣ SYNTHESIZE PROMPT
        # ---------------------------------------------------------

        prompt = ""
        citations: List[Dict] = []

        if retrieved_chunks:
            try:
                synthesis = synthesize_answer(
                    query=question,
                    contexts=retrieved_chunks,
                )

                prompt = synthesis.get("prompt") or ""
                citations = synthesis.get("citations", []) or []

            except Exception as e:
                print("⚠️ Synthesis failed:", e)

        citations = _dedupe_citations(citations)

        history_block = format_history(history)

        if prompt and history_block:
            prompt = f"{history_block}\n\n{prompt}"

        # ---------------------------------------------------------
        # 6️⃣ PRIMARY LLM CALL (ONLY ONCE)
        # ---------------------------------------------------------

        answer = None

        if prompt:
            try:
                print("🤖 LLM primary")
                answer = call_llm(prompt, question)
            except Exception as e:
                print("❌ LLM failed:", e)

        # ---------------------------------------------------------
        # 7️⃣ RETRY ONLY IF NEEDED (ONCE)
        # ---------------------------------------------------------

        if (not answer or len(answer.strip()) < 30) and raw_context:

            try:
                print("🔁 LLM retry")

                simple_prompt = f"""
Answer using ONLY this information. If it does not contain the answer,
say so plainly. Do not invent details.

{raw_context}

Question: {question}
"""

                answer = call_llm(simple_prompt, question)

            except Exception as e:
                print("❌ Retry failed:", e)

        # ---------------------------------------------------------
        # 8️⃣ FINAL ANSWER GUARD
        # ---------------------------------------------------------

        final_answer = ensure_answer(
            question=question,
            context=raw_context,
            answer=answer,
        ).strip()

        # When nothing grounded was found, do not present sources as if
        # they supported the answer.
        found = bool(retrieved_chunks) and final_answer != NOT_FOUND_MESSAGE

        # ---------------------------------------------------------
        # RESPONSE
        # ---------------------------------------------------------

        return {
            "answer": final_answer,
            "verified": found,
            "citations": citations if found else [],
        }

    finally:
        query_slots.release()
