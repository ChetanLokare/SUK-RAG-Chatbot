# backend/api/search.py

from fastapi import APIRouter, Query
from typing import Optional, Dict, Any, List

from backend.search.hybrid_search import hybrid_search

router = APIRouter(prefix="/search", tags=["Search"])


# ============================================================
# CLEAN FILTER VALUE
# Prevent swagger default "string"
# ============================================================

def _clean_filter_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    value = value.strip()

    if value.lower() in ["string", "none", "null", ""]:
        return None

    return value


# ============================================================
# RESPONSE NORMALIZER
# Keeps API stable even if hybrid changes
# ============================================================

def _normalize_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []

    for r in results:
        meta = r.get("metadata") or {}

        normalized.append({
            "id": r.get("id"),
            "score": float(r.get("score", 0)),
            "text_preview": (r.get("text") or "")[:400],
            "source_type": meta.get("source_type"),
            "source_value": meta.get("source_value"),
            "category": meta.get("category"),
            "language": meta.get("language"),
            "page_number": meta.get("page_number"),
        })

    return normalized


# ============================================================
# SEARCH ENDPOINT
# ============================================================

@router.get("/")
def search(
    q: str = Query(..., min_length=2),
    top_k: int = Query(5, ge=1, le=50),
    category: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
):
    """
    Generic search endpoint.

    Supports:
    - All categories (url/pdf/csv/excel/etc)
    - Optional category filtering
    - Optional language filtering
    """

    query = (q or "").strip()

    if not query:
        return {
            "query": q,
            "results": [],
        }

    category = _clean_filter_value(category)
    language = _clean_filter_value(language)

    try:
        results = hybrid_search(
            query=query,
            top_k=top_k,
            category=category,
            language=language,
        )
    except Exception as e:
        return {
            "query": query,
            "results": [],
            "error": str(e),
        }

    return {
        "query": query,
        "count": len(results),
        "results": _normalize_results(results),
    }