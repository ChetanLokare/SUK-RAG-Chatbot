# backend/api/chat.py

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Dict

from backend.search.hybrid_search import hybrid_search
from backend.core.answer_synthesizer import synthesize_answer


# ============================================================
# OPTIONAL SERVICES (SAFE FALLBACKS)
# ============================================================

# ---- language ----
try:
    from backend.services.language_service import detect_query_language
except Exception:
    def detect_query_language(text: str) -> str:
        return "en"


# ---- translation ----
try:
    from backend.services.translation_service import translate_text
except Exception:
    def translate_text(text: str, target_language: str = "English") -> str:
        _ = target_language
        return text


# ---- llm ----
try:
    from backend.services.llm_service import call_llm
except Exception:
    def call_llm(prompt: str) -> str:
        _ = prompt
        return "LLM service not configured."


# ---- memory ----
try:
    from backend.services.memory_service import add_message, get_memory
except Exception:
    def add_message(session_id: str, role: str, content: str) -> None:
        return None

    def get_memory(session_id: str):
        return []


# ---- table ----
try:
    from backend.services.table_service import (
        is_table_question,
        answer_table_question
    )
except Exception:
    def is_table_question(text: str) -> bool:
        return False

    def answer_table_question(query: str, category: Optional[str] = None):
        _ = category
        return None


# ---- timeline ----
try:
    from backend.services.timeline_service import (
        is_timeline_question,
        answer_timeline_question
    )
except Exception:
    def is_timeline_question(text: str) -> bool:
        return False

    def answer_timeline_question(query: str, category: Optional[str] = None):
        _ = category
        return None


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(prefix="/chat", tags=["Chat"])


# ============================================================
# REQUEST MODEL
# ============================================================

class ChatRequest(BaseModel):
    query: str
    session_id: str
    category: Optional[str] = None


# ============================================================
# CLEAN CATEGORY (Swagger fix)
# ============================================================

def _clean_filter(value: Optional[str]) -> Optional[str]:

    if not value:
        return None

    value = value.strip()

    if value.lower() in ["string", "none", "null", ""]:
        return None

    return value


# ============================================================
# DEDUPE SOURCES
# ============================================================

def _dedupe_sources(sources: List[Dict]) -> List[Dict]:

    seen = set()
    unique = []

    for s in sources:

        key = (s.get("source_value"), s.get("page_number"))

        if key not in seen:
            seen.add(key)
            unique.append(s)

    return unique


# ============================================================
# BUILD SOURCES LIST
# ============================================================

def _extract_sources(results: List[Dict]):

    sources = []

    for i, r in enumerate(results):

        meta = r.get("metadata") or {}

        sources.append({
            "index": i + 1,
            "source_type": meta.get("source_type"),
            "source_value": meta.get("source_value"),
            "page_number": meta.get("page_number"),
            "category": meta.get("category"),
        })

    return _dedupe_sources(sources)


# ============================================================
# MAIN CHAT ENDPOINT
# ============================================================

@router.post("/")
def chat(request: ChatRequest):

    query_text = (request.query or "").strip()

    if not query_text:
        return {
            "answer": "Empty query.",
            "sources": [],
            "detected_language": "unknown",
        }

    category = _clean_filter(request.category)

    # =========================================================
    # 1️⃣ Detect language
    # =========================================================

    query_lang = detect_query_language(query_text)

    # =========================================================
    # 2️⃣ Translate for retrieval
    # =========================================================

    search_query = query_text

    if query_lang in ["mr", "hi"]:
        try:
            search_query = translate_text(
                query_text,
                target_language="English"
            )
        except Exception:
            pass

    # =========================================================
    # 3️⃣ Structured handlers
    # =========================================================

    if is_table_question(search_query):

        ans = answer_table_question(
            query=search_query,
            category=category
        )

        if ans:

            add_message(request.session_id, "user", query_text)
            add_message(request.session_id, "assistant", ans)

            return {
                "answer": ans,
                "sources": [],
                "detected_language": query_lang,
            }

    if is_timeline_question(search_query):

        ans = answer_timeline_question(
            query=search_query,
            category=category
        )

        if ans:

            add_message(request.session_id, "user", query_text)
            add_message(request.session_id, "assistant", ans)

            return {
                "answer": ans,
                "sources": [],
                "detected_language": query_lang,
            }

    # =========================================================
    # 4️⃣ Retrieval
    # =========================================================

    results = hybrid_search(
        query=search_query,
        top_k=6,
        category=category,
        language=None,
    )

    if not results:
        return {
            "answer": "No relevant information found.",
            "sources": [],
            "detected_language": query_lang,
        }

    if results[0].get("score", 0) < 0.08:
        return {
            "answer": "No strong matching information found in university documents.",
            "sources": [],
            "detected_language": query_lang,
        }

    # =========================================================
    # 5️⃣ Extract sources
    # =========================================================

    sources = _extract_sources(results)

    # =========================================================
    # 6️⃣ Memory
    # =========================================================

    memory = get_memory(request.session_id)[-10:]

    memory_text = "\n".join(
        f"{m['role']}: {m['content']}"
        for m in memory
    )

    # =========================================================
    # 7️⃣ Answer synthesizer
    # =========================================================

    synth = synthesize_answer(search_query, results)

    base_prompt = synth.get("prompt", "")

    target_language = (
        "Marathi" if query_lang == "mr"
        else "Hindi" if query_lang == "hi"
        else "English"
    )

    prompt = f"""
Conversation history:
{memory_text}

{base_prompt}

Respond in {target_language}.
"""

    # =========================================================
    # 8️⃣ LLM
    # =========================================================

    try:
        answer = call_llm(prompt)

    except Exception:

        return {
            "answer": "LLM generation failed.",
            "sources": sources,
            "detected_language": query_lang,
        }

    if not answer:
        answer = "Information not available in provided sources."

    # =========================================================
    # 9️⃣ Save memory
    # =========================================================

    add_message(request.session_id, "user", query_text)
    add_message(request.session_id, "assistant", answer)

    # =========================================================
    # 🔟 Return
    # =========================================================

    return {
        "answer": answer.strip(),
        "sources": sources,
        "detected_language": query_lang,
    }