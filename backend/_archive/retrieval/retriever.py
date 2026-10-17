"""
Main retrieval pipeline for the RAG system (FINAL PRODUCTION VERSION)
"""

from typing import List, Dict
from datetime import datetime, timezone
import hashlib
import re

from rank_bm25 import BM25Okapi

from backend.core.chroma_client import get_collection

from backend.search.query_expander import expand_query
from backend.retrieval.graph_retriever import build_graph_queries
from backend.retrieval.late_chunking import late_chunk_documents
from backend.retrieval.ranker import rerank_results
from backend.retrieval.temporal_ranker import apply_temporal_ranking
from backend.retrieval.context_compressor import compress_contexts
from backend.retrieval.adaptive_topk import dynamic_top_k
from backend.search.query_intent import temporal_score


# =========================================================
# CONFIG
# =========================================================

MAX_QUERY_VARIANTS = 10
MAX_VECTOR_RESULTS_MULTIPLIER = 6


# =========================================================
# TOKENIZATION
# =========================================================

TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return TOKEN_PATTERN.findall(text.lower())


# =========================================================
# NORMALIZE
# =========================================================

def _normalize_scores(values: List[float]) -> List[float]:

    if not values:
        return []

    max_v = max(values)
    min_v = min(values)

    if max_v == min_v:
        return [1.0] * len(values)

    return [(v - min_v) / (max_v - min_v) for v in values]


# =========================================================
# BM25
# =========================================================

def _bm25_rank(query: str, docs: List[str]) -> List[float]:

    if not docs:
        return []

    try:
        tokenized = [_tokenize(d) for d in docs]
        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(_tokenize(query))
        return list(scores)
    except Exception:
        return [0.0] * len(docs)


# =========================================================
# QUERY MATCH BOOST
# =========================================================

def _query_match_boost(query: str, text: str) -> float:

    q_words = set(_tokenize(query))
    t = (text or "").lower()

    if not q_words:
        return 1.0

    matches = sum(1 for w in q_words if w in t)

    return 1.0 + (matches / (len(q_words) + 1))


# =========================================================
# FILTER BAD RESULTS
# =========================================================

def _filter_bad(query: str, text: str, meta: Dict) -> bool:

    if not text or len(text.strip()) < 80:
        return False

    if len(text.split()) < 20:
        return False

    src = (meta.get("source_value") or "").lower()

    # Remove CV noise
    if any(x in src for x in ["cv", "resume", "biodata"]):
        if not any(k in query.lower() for k in ["faculty", "staff"]):
            return False

    return True


# =========================================================
# BOOSTS
# =========================================================

def _source_boost(meta: Dict) -> float:

    stype = (meta.get("source_type") or "").lower()
    url = (meta.get("source_value") or "").lower()

    score = 1.0

    if stype == "url":
        score += 1.8

    if "department" in url:
        score += 1.3

    if "contact" in url:
        score += 1.3

    if "faculty" in url:
        score += 0.8

    if stype == "pdf":
        score -= 0.7

    return score


def _intent_boost(query: str, text: str) -> float:

    q = query.lower()
    t = (text or "").lower()

    score = 1.0

    if "contact" in q and any(x in t for x in ["email", "phone", "contact"]):
        score *= 1.35

    if "department" in q and "department" in t:
        score *= 1.2

    if "exam" in q and "exam" in t:
        score *= 1.2

    return score


def _deadline_boost(meta: Dict) -> float:

    ts = meta.get("deadline_ts")

    if not ts:
        return 1.0

    try:
        d = datetime.fromtimestamp(int(ts), timezone.utc)
        now = datetime.now(timezone.utc)

        days = (d - now).days

        if days < 0:
            return 0.85

        if days <= 7:
            return 1.25

        return 1.1

    except Exception:
        return 1.0


# =========================================================
# VECTOR SEARCH
# =========================================================

def _vector_search(collection, query: str, limit: int):

    try:
        return collection.query(
            query_texts=[query],
            n_results=limit,
        )
    except Exception:
        return None


# =========================================================
# BUILD CONTEXTS
# =========================================================

def _build_contexts(query: str, results) -> List[Dict]:

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    if not docs:
        return []

    bm25 = _normalize_scores(_bm25_rank(query, docs))

    contexts = []

    for i, text in enumerate(docs):

        meta = metas[i] if i < len(metas) else {}

        if not _filter_bad(query, text, meta):
            continue

        try:
            dist = float(dists[i])
            vec = 1 / (1 + dist)
        except Exception:
            vec = 0.0

        bm = bm25[i] if i < len(bm25) else 0.0

        score = (0.65 * vec) + (0.35 * bm)

        score *= _query_match_boost(query, text)
        score *= _source_boost(meta)
        score *= _intent_boost(query, text)
        score *= _deadline_boost(meta)

        contexts.append({
            "text": text,
            "metadata": meta,
            "score": float(score),
        })

    return contexts


# =========================================================
# MAIN RETRIEVE
# =========================================================

def retrieve(query: str, top_k: int = None) -> List[Dict]:

    if not query or not query.strip():
        return []

    query = query.strip()

    # safe top_k
    try:
        top_k = int(top_k) if top_k else dynamic_top_k(query)
    except Exception:
        top_k = 12

    top_k = max(4, min(top_k, 30))

    collection = get_collection()

    try:
        if collection.count() == 0:
            return []
    except Exception:
        return []

    # -----------------------------------------------------
    # MULTI QUERY (SAFE LIMIT)
    # -----------------------------------------------------

    queries = list(set(
        [query] +
        (expand_query(query) or []) +
        (build_graph_queries(query) or [])
    ))[:MAX_QUERY_VARIANTS]

    all_ctx = []

    for q in queries:

        res = _vector_search(collection, q, top_k * MAX_VECTOR_RESULTS_MULTIPLIER)

        if not res:
            continue

        ctx = _build_contexts(q, res)

        all_ctx.extend(ctx)

    if not all_ctx:
        return []

    # -----------------------------------------------------
    # DEDUP (STRONG)
    # -----------------------------------------------------

    seen = set()
    dedup = []

    for c in all_ctx:

        text = (c.get("text") or "").strip()

        if not text:
            continue

        key = hashlib.md5(text[:300].lower().encode()).hexdigest()

        if key in seen:
            continue

        seen.add(key)
        dedup.append(c)

    # -----------------------------------------------------
    # QUERY TEMPORAL INTENT BOOST
    # -----------------------------------------------------

    try:
        t_score = temporal_score(query)
    except Exception:
        t_score = 0.0

    if t_score > 0:
        for c in dedup:
            c["score"] *= (1 + min(t_score, 1.0) * 0.2)

    # -----------------------------------------------------
    # TEMPORAL RANKING (FIXED)
    # -----------------------------------------------------

    ranked = apply_temporal_ranking(dedup)

    # -----------------------------------------------------
    # RERANK
    # -----------------------------------------------------

    ranked = rerank_results(query, ranked)

    # -----------------------------------------------------
    # LATE CHUNK
    # -----------------------------------------------------

    ranked = late_chunk_documents(query, ranked)

    # -----------------------------------------------------
    # COMPRESS
    # -----------------------------------------------------

    ranked = compress_contexts(query, ranked, max_contexts=25)

    # -----------------------------------------------------
    # FINAL SORT
    # -----------------------------------------------------

    ranked.sort(key=lambda x: float(x.get("score", 0)), reverse=True)

    # -----------------------------------------------------
    # URL PRIORITY (SAFE)
    # -----------------------------------------------------

    urls = [r for r in ranked if (r.get("metadata") or {}).get("source_type") == "url"]
    others = [r for r in ranked if r not in urls]

    ranked = urls + others

    return ranked[:top_k]