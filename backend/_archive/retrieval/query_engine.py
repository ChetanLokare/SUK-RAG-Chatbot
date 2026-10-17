"""
Query Engine (FINAL PRODUCTION VERSION)

Handles:
• retrieval orchestration
• cross-document reranking
• temporal + category boosting
• PDF page merging
• context trimming
• optional highlighting

Safe, stable, and optimized for RAG pipelines.
"""

from typing import List, Dict
from datetime import datetime, timedelta
import re
from collections import defaultdict

from backend.retrieval.retriever import retrieve


# ============================================================
# CONFIG
# ============================================================

MAX_CONTEXT_CHARS = 12000
MAX_FINAL_CONTEXTS = 8

DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*\d{0,4})",
    re.IGNORECASE,
)

CATEGORY_KEYWORDS = {
    "scholarship": ["scholarship", "grant", "fund"],
    "admission": ["admission", "apply", "enrollment"],
    "exam": ["exam", "examination", "result"],
    "event": ["event", "seminar", "conference", "workshop"],
    "notice": ["notice", "circular", "announcement"],
}


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


# ============================================================
# DATE EXTRACTION (🔥 IMPROVED)
# ============================================================

def _extract_dates(text: str) -> List[datetime]:

    if not text:
        return []

    matches = DATE_PATTERN.findall(text)

    parsed_dates = []

    for match in matches:

        for fmt in [
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d-%m-%y",
            "%d %b %Y",
            "%d %B %Y",
            "%d %b",
        ]:
            try:
                parsed = datetime.strptime(match.strip(), fmt)

                # if year missing → assume current year
                if parsed.year == 1900:
                    parsed = parsed.replace(year=datetime.now().year)

                parsed_dates.append(parsed)
                break

            except Exception:
                continue

    return parsed_dates


# ============================================================
# TEMPORAL BOOST
# ============================================================

def _temporal_boost(query: str, context: Dict) -> float:

    query_lower = (query or "").lower()
    text = context.get("text", "")

    dates = _extract_dates(text)

    if not dates:
        return 1.0

    now = datetime.now()

    boost = 1.0

    for d in dates:

        # upcoming queries
        if any(x in query_lower for x in ["upcoming", "next", "latest"]):
            if now <= d <= now + timedelta(days=30):
                boost *= 1.4

        # weekly queries
        if "this week" in query_lower:
            if now <= d <= now + timedelta(days=7):
                boost *= 1.5

        # deadline queries
        if any(x in query_lower for x in ["deadline", "last date"]):
            if d >= now:
                boost *= 1.3

    return boost


# ============================================================
# CATEGORY BOOST
# ============================================================

def _category_boost(query: str, context: Dict) -> float:

    query_lower = (query or "").lower()
    meta = context.get("metadata", {}) or {}

    category = str(meta.get("category", "")).lower()

    boost = 1.0

    for cat, keywords in CATEGORY_KEYWORDS.items():

        if any(k in query_lower for k in keywords):

            if category == cat:
                boost *= 1.35

    return boost


# ============================================================
# PDF GROUPING (🔥 FIXED SAFE VERSION)
# ============================================================

def _group_pdf_pages(contexts: List[Dict]) -> List[Dict]:

    grouped = defaultdict(list)

    for c in contexts:

        meta = c.get("metadata", {}) or {}

        if meta.get("source_type") == "pdf":
            key = meta.get("source_id") or id(c)
            grouped[key].append(c)
        else:
            grouped[id(c)].append(c)

    merged = []

    for _, group in grouped.items():

        if len(group) == 1:
            merged.append(group[0])
            continue

        texts = []
        total_len = 0

        for g in group:

            text = g.get("text", "")

            if not text:
                continue

            if total_len > 3000:
                break

            texts.append(text)
            total_len += len(text)

        combined_text = "\n\n".join(texts)

        if not combined_text:
            continue

        best_score = max(_safe_float(g.get("score")) for g in group)

        merged.append({
            "text": combined_text,
            "metadata": group[0].get("metadata", {}),
            "score": best_score,
        })

    return merged


# ============================================================
# CONTEXT TRIMMER (SAFE)
# ============================================================

def _trim_contexts(contexts: List[Dict]) -> List[Dict]:

    total = 0
    final = []

    for c in contexts:

        text = c.get("text", "")

        if not text:
            continue

        if total + len(text) > MAX_CONTEXT_CHARS:
            break

        final.append(c)
        total += len(text)

        if len(final) >= MAX_FINAL_CONTEXTS:
            break

    return final


# ============================================================
# CROSS-DOCUMENT RERANK
# ============================================================

def _cross_document_rerank(query: str, contexts: List[Dict]) -> List[Dict]:

    for c in contexts:

        base_score = _safe_float(c.get("score"))

        boost = 1.0
        boost *= _temporal_boost(query, c)
        boost *= _category_boost(query, c)

        c["score"] = base_score * boost

    contexts.sort(key=lambda x: _safe_float(x.get("score")), reverse=True)

    return contexts


# ============================================================
# HIGHLIGHT
# ============================================================

def _highlight_query_terms(query: str, text: str) -> str:

    if not text:
        return ""

    words = set(query.lower().split())

    def repl(match):
        word = match.group(0)
        return f"**{word}**" if word.lower() in words else word

    return re.sub(r"\b\w+\b", repl, text)


# ============================================================
# MAIN QUERY ENGINE
# ============================================================

def query_engine(
    query: str,
    top_k: int = 10,
    highlight: bool = True,
) -> Dict:

    if not query or not query.strip():
        return {
            "query": query,
            "answer": None,
            "contexts": [],
            "total_contexts": 0,
        }

    query = query.strip()

    # --------------------------------------------------------
    # 1️⃣ RETRIEVE
    # --------------------------------------------------------

    contexts = retrieve(query, top_k=top_k)

    if not contexts:
        return {
            "query": query,
            "answer": None,
            "contexts": [],
            "total_contexts": 0,
        }

    # --------------------------------------------------------
    # 2️⃣ CROSS RERANK
    # --------------------------------------------------------

    contexts = _cross_document_rerank(query, contexts)

    # --------------------------------------------------------
    # 3️⃣ GROUP PDF
    # --------------------------------------------------------

    contexts = _group_pdf_pages(contexts)

    # --------------------------------------------------------
    # 4️⃣ TRIM
    # --------------------------------------------------------

    contexts = _trim_contexts(contexts)

    # --------------------------------------------------------
    # 5️⃣ HIGHLIGHT
    # --------------------------------------------------------

    if highlight:
        for c in contexts:
            c["text"] = _highlight_query_terms(query, c.get("text", ""))

    # --------------------------------------------------------
    # 6️⃣ BUILD ANSWER (INTERMEDIATE)
    # --------------------------------------------------------

    combined_context = "\n\n".join(c.get("text", "") for c in contexts)

    return {
        "query": query,
        "answer": combined_context[:3000],
        "contexts": contexts,
        "total_contexts": len(contexts),
    }