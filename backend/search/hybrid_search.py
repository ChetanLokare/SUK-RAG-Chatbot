from typing import List, Dict, Optional
import re

from rank_bm25 import BM25Okapi

from backend.core.chroma_client import get_collection
from backend.retrieval.temporal_ranker import apply_temporal_ranking
from backend.utils.query_normalize import expand_abbreviations


# ============================================================
# CONFIG
# ============================================================

MIN_TEXT_LENGTH = 20
MIN_SCORE_THRESHOLD = 0.02
MAX_CANDIDATES_MULTIPLIER = 5
DEFAULT_TOP_K = 8


# ============================================================
# TOKENIZER
# ============================================================

TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


def tokenize(text: str) -> List[str]:
    return TOKEN_PATTERN.findall((text or "").lower())


# ============================================================
# QUERY EXPANSION (🔥 CRITICAL)
# ============================================================

def expand_query(q: str) -> str:
    """
    Expand abbreviations (whole words only) and lowercase.

    Expansion happens BEFORE lowercasing so that "IT" (department) can be
    told apart from "it" (the English word).
    """

    return expand_abbreviations(q).lower()


# ============================================================
# NORMALIZE
# ============================================================

def normalize_scores(scores: List[float]) -> List[float]:

    if not scores:
        return []

    mx, mn = max(scores), min(scores)

    if mx == mn:
        return [1.0] * len(scores)

    return [(s - mn) / (mx - mn) for s in scores]


# ============================================================
# BOOST FUNCTIONS
# ============================================================

def _query_boost(query: str, text: str) -> float:

    q_tokens = tokenize(query)
    t = text.lower()

    matches = sum(1 for w in q_tokens if w in t)

    boost = 1.0 + (matches / (len(q_tokens) + 1))

    if " ".join(q_tokens) in t:
        boost *= 1.4

    return boost


def _section_boost(meta: Dict) -> float:

    boost = 1.0

    if meta.get("section_heading"):
        boost += 0.4

    if meta.get("document_type") == "syllabus":
        boost += 0.5

    return boost


def _table_penalty(meta: Dict, text: str) -> float:

    if meta.get("table_data"):
        if len(text) < 200:
            return 0.5
    return 1.0


def _source_boost(meta: Dict) -> float:

    stype = (meta.get("source_type") or "").lower()

    # 🔥 FIX: do NOT penalize PDFs
    if stype == "pdf":
        return 1.1

    if stype == "url":
        return 1.2

    return 1.0


# ============================================================
# FILTER CLEANER
# ============================================================

def _clean_filter(value: Optional[str]) -> Optional[str]:

    if not value:
        return None

    v = str(value).strip().lower()

    if v in ["none", "null", "undefined", "", "string"]:
        return None

    return v


# ============================================================
# SAFE QUERY
# ============================================================

def _query_collection(collection, query, n_results, where):

    try:
        res = collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where if where else None,
        )

        if res and res.get("ids") and res["ids"][0]:
            return res

    except Exception as e:
        print("⚠️ Query failed:", e)

    return None


# ============================================================
# MAIN SEARCH
# ============================================================

def hybrid_search(
    query: str,
    top_k: int = 8,
    alpha: float = 0.65,
    category: Optional[str] = None,
    language: Optional[str] = None,
) -> List[Dict]:

    if not query:
        return []

    query = expand_query(query.strip())

    if not top_k or top_k <= 0:
        top_k = DEFAULT_TOP_K

    collection = get_collection()

    if collection.count() == 0:
        return []

    category = _clean_filter(category)
    language = _clean_filter(language)

    where = {}

    if category:
        where["category"] = category

    if language:
        where["language"] = language

    print("\n🔍 QUERY:", query)

    # --------------------------------------------------------
    # VECTOR SEARCH
    # --------------------------------------------------------

    results = _query_collection(
        collection,
        query,
        top_k * MAX_CANDIDATES_MULTIPLIER,
        where
    )

    if not results:
        return []

    ids = results["ids"][0]
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]

    # --------------------------------------------------------
    # VECTOR SCORE
    # --------------------------------------------------------

    v_scores = normalize_scores([
        1 / (1 + float(d)) for d in dists
    ])

    # --------------------------------------------------------
    # BM25
    # --------------------------------------------------------

    tokenized_docs = [tokenize(d or "") for d in docs]

    bm25 = BM25Okapi(tokenized_docs) if any(tokenized_docs) else None

    bm25_scores = bm25.get_scores(tokenize(query)) if bm25 else [0]*len(docs)
    bm25_scores = normalize_scores(list(bm25_scores))

    # --------------------------------------------------------
    # COMBINE
    # --------------------------------------------------------

    final = []

    for i in range(len(ids)):

        text = docs[i] or ""
        meta = metas[i] or {}

        if len(text) < MIN_TEXT_LENGTH:
            continue

        v = v_scores[i]
        b = bm25_scores[i]

        score = alpha * v + (1 - alpha) * b

        # 🔥 APPLY BOOSTS
        score *= _query_boost(query, text)
        score *= _section_boost(meta)
        score *= _source_boost(meta)
        score *= _table_penalty(meta, text)

        if score < MIN_SCORE_THRESHOLD:
            continue

        final.append({
            "id": ids[i],
            "text": text,
            "metadata": meta,
            "score": float(score),
        })

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    final.sort(key=lambda x: x["score"], reverse=True)

    print("📊 Results:", len(final))

    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    unique = []
    seen = set()

    for r in final:

        key = (r["metadata"].get("source_value"), r["text"][:100])

        if key in seen:
            continue

        seen.add(key)
        unique.append(r)

    final = unique[:top_k]

    # --------------------------------------------------------
    # TEMPORAL BOOST
    # --------------------------------------------------------

    try:
        final = apply_temporal_ranking(final)
    except Exception:
        pass

    return final