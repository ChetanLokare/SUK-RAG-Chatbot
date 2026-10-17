"""
Unified ranking pipeline for RAG retrieval (FINAL PRODUCTION VERSION)

Combines:
1) Base score (vector + BM25)
2) Temporal ranking (query-aware)
3) Section importance
4) Entity matching
5) Source prioritization (URL > PDF)
6) Query relevance boost
7) Diversity filtering

Safe, stable, and production-ready.
"""

from typing import List, Dict

from backend.retrieval.temporal_ranker import apply_temporal_ranking


# ============================================================
# CONFIG
# ============================================================

SECTION_IMPORTANCE = {
    "important dates": 1.35,
    "deadline": 1.35,
    "eligibility": 1.25,
    "application": 1.20,
    "contact": 1.25,
    "about": 1.05,
}

ENTITY_KEYWORD_BOOST = {
    "hod": 1.25,
    "email": 1.20,
    "phone": 1.20,
    "contact": 1.20,
}

MAX_SCORE_MULTIPLIER = 3.0  # safety cap


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _normalize(text: str) -> str:
    if not text:
        return ""
    return text.lower().strip()


# ============================================================
# FILTER BAD RESULTS
# ============================================================

def _filter_bad(query: str, text: str, meta: Dict) -> bool:

    if not text or len(text.strip()) < 80:
        return False

    src = (meta.get("source_value") or "").lower()
    q = query.lower()

    # remove CV noise
    if any(x in src for x in ["cv", "resume", "biodata"]):
        if not any(k in q for k in ["faculty", "staff", "teacher"]):
            return False

    return True


# ============================================================
# QUERY MATCH BOOST (🔥 IMPORTANT)
# ============================================================

def _query_match_boost(query: str, text: str) -> float:

    q_words = set(_normalize(query).split())
    t = _normalize(text)

    if not q_words:
        return 1.0

    matches = sum(1 for w in q_words if w in t)

    return 1.0 + (matches / (len(q_words) + 1))


# ============================================================
# SOURCE BOOST
# ============================================================

def _source_boost(meta: Dict) -> float:

    stype = (meta.get("source_type") or "").lower()
    url = (meta.get("source_value") or "").lower()

    score = 1.0

    if stype == "url":
        score += 1.6

    if "department" in url:
        score += 1.2

    if "contact" in url:
        score += 1.3

    if "faculty" in url:
        score += 0.8

    if stype == "pdf":
        score -= 0.7

    return score


# ============================================================
# SECTION BOOST
# ============================================================

def _section_boost(meta: Dict) -> float:

    section = str(meta.get("section_title", "")).lower()

    for key, boost in SECTION_IMPORTANCE.items():
        if key in section:
            return boost

    return 1.0


# ============================================================
# ENTITY BOOST
# ============================================================

def _entity_boost(query: str, text: str) -> float:

    query = _normalize(query)
    text = _normalize(text)

    boost = 1.0

    for word, multiplier in ENTITY_KEYWORD_BOOST.items():
        if word in query and word in text:
            boost *= multiplier

    return boost


# ============================================================
# DIVERSITY FILTER
# ============================================================

def _deduplicate_sources(
    results: List[Dict],
    max_per_source: int = 3
) -> List[Dict]:

    source_counter = {}
    filtered = []

    for r in results:

        meta = r.get("metadata") or {}
        source_id = meta.get("source_id")

        if not source_id:
            filtered.append(r)
            continue

        count = source_counter.get(source_id, 0)

        if count >= max_per_source:
            continue

        source_counter[source_id] = count + 1
        filtered.append(r)

    return filtered


# ============================================================
# MAIN RERANK
# ============================================================

def rerank_results(
    query: str,
    results: List[Dict],
    top_k: int = 12
) -> List[Dict]:

    if not results:
        return []

    # --------------------------------------------------------
    # FILTER BAD RESULTS
    # --------------------------------------------------------

    results = [
        r for r in results
        if _filter_bad(query, r.get("text", ""), r.get("metadata", {}))
    ]

    if not results:
        return []

    # --------------------------------------------------------
    # TEMPORAL RANKING (🔥 FIXED)
    # --------------------------------------------------------

    try:
        results = apply_temporal_ranking(query, results)
    except Exception:
        pass

    ranked = []

    # --------------------------------------------------------
    # APPLY BOOSTS
    # --------------------------------------------------------

    for r in results:

        base_score = _safe_float(r.get("score"))

        text = r.get("text", "") or ""
        meta = r.get("metadata") or {}

        section_mul = _section_boost(meta)
        entity_mul = _entity_boost(query, text)
        source_mul = _source_boost(meta)
        match_mul = _query_match_boost(query, text)

        final_score = base_score
        final_score *= section_mul
        final_score *= entity_mul
        final_score *= source_mul
        final_score *= match_mul

        # 🔥 SAFETY CLAMP
        final_score = min(final_score, base_score * MAX_SCORE_MULTIPLIER)

        new_r = dict(r)
        new_r["score"] = float(final_score)

        # Debug metadata
        details = dict(r.get("ranking_details") or {})
        details.update({
            "base_score": base_score,
            "section_boost": section_mul,
            "entity_boost": entity_mul,
            "source_boost": source_mul,
            "query_match_boost": match_mul,
        })

        new_r["ranking_details"] = details

        ranked.append(new_r)

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    ranked.sort(
        key=lambda x: _safe_float(x.get("score")),
        reverse=True
    )

    # --------------------------------------------------------
    # DIVERSITY CONTROL
    # --------------------------------------------------------

    ranked = _deduplicate_sources(ranked)

    # --------------------------------------------------------
    # SAFE URL PRIORITY (NO DUPLICATES)
    # --------------------------------------------------------

    urls = []
    others = []

    for r in ranked:
        if (r.get("metadata") or {}).get("source_type") == "url":
            urls.append(r)
        else:
            others.append(r)

    ranked = urls + others

    # --------------------------------------------------------
    # FINAL SLICE
    # --------------------------------------------------------

    return ranked[:top_k]