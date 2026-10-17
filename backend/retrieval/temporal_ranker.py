"""
Temporal ranking module for hybrid RAG retrieval (FINAL PRODUCTION VERSION)

Boosts documents based on:
• recency (newer documents preferred)
• deadlines (upcoming events strongly boosted)
• category importance (exam, admission, etc.)
• query intent awareness (time-based queries get stronger boosts)

Safe, stable, and compatible with full RAG pipeline.
"""

from typing import List, Dict
from datetime import datetime, timezone


# ============================================================
# CONFIG
# ============================================================

RECENCY_DECAY_DAYS = 90

MAX_RECENCY_BOOST = 1.30
MIN_RECENCY_BOOST = 0.85

DEADLINE_BOOST = 1.30
UPCOMING_DEADLINE_BOOST = 1.50
EXPIRED_DEADLINE_PENALTY = 0.85

MAX_FINAL_MULTIPLIER = 3.0  # safety cap


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_int(value):
    try:
        return int(value)
    except Exception:
        return None


def _safe_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


# ============================================================
# RECENCY BOOST
# ============================================================

def _calculate_recency_boost(indexed_ts: int) -> float:
    """
    Recency decay curve.

    New → boosted
    Old → slight decay (not harsh)
    """

    if not indexed_ts:
        return 1.0

    now_ts = int(datetime.now(timezone.utc).timestamp())

    age_days = (now_ts - indexed_ts) / 86400

    # future-safe
    if age_days <= 0:
        return MAX_RECENCY_BOOST

    decay_ratio = max(0.0, 1.0 - (age_days / RECENCY_DECAY_DAYS))

    boost = 1.0 + (decay_ratio * (MAX_RECENCY_BOOST - 1.0))

    return max(MIN_RECENCY_BOOST, min(boost, MAX_RECENCY_BOOST))


# ============================================================
# DEADLINE BOOST
# ============================================================

def _calculate_deadline_boost(meta: Dict) -> float:

    deadline_ts = _safe_int(meta.get("deadline_ts"))
    has_deadline = bool(meta.get("has_deadline"))

    if not has_deadline or not deadline_ts:
        return 1.0

    now_ts = int(datetime.now(timezone.utc).timestamp())

    # --------------------------------------------------------
    # FUTURE DEADLINE
    # --------------------------------------------------------

    if deadline_ts >= now_ts:

        days_remaining = (deadline_ts - now_ts) / 86400

        if days_remaining <= 7:
            return UPCOMING_DEADLINE_BOOST

        if days_remaining <= 30:
            return DEADLINE_BOOST

        return 1.05

    # --------------------------------------------------------
    # EXPIRED
    # --------------------------------------------------------

    return EXPIRED_DEADLINE_PENALTY


# ============================================================
# CATEGORY BOOST
# ============================================================

def _category_priority_boost(meta: Dict) -> float:

    category = str(meta.get("category", "")).lower()

    if category in ["exam", "result"]:
        return 1.25

    if category in ["admission"]:
        return 1.25

    if category in ["scholarship"]:
        return 1.30

    if category in ["circular", "notice"]:
        return 1.20

    if category in ["event"]:
        return 1.15

    return 1.0


# ============================================================
# TEMPORAL INTENT BOOST (🔥 NEW)
# ============================================================

def _temporal_query_boost(query: str) -> float:
    """
    Boost if query is time-sensitive.
    """

    if not query:
        return 1.0

    q = query.lower()

    time_keywords = [
        "next",
        "upcoming",
        "latest",
        "today",
        "recent",
        "deadline",
        "last date",
        "schedule",
        "timetable",
        "when",
    ]

    if any(k in q for k in time_keywords):
        return 1.15

    return 1.0


# ============================================================
# APPLY TEMPORAL RANKING
# ============================================================

def apply_temporal_ranking(
    query: str,
    results: List[Dict]
) -> List[Dict]:
    """
    Applies temporal boosts to retrieval results.

    Input:
        query: user query
        results: list of retrieved contexts

    Output:
        ranked results with updated scores
    """

    if not results:
        return []

    ranked_results = []

    query_boost = _temporal_query_boost(query)

    for result in results:

        base_score = _safe_float(result.get("score"))
        meta = result.get("metadata") or {}

        indexed_ts = _safe_int(meta.get("indexed_at_ts"))

        recency_boost = _calculate_recency_boost(indexed_ts)
        deadline_boost = _calculate_deadline_boost(meta)
        category_boost = _category_priority_boost(meta)

        final_score = base_score
        final_score *= recency_boost
        final_score *= deadline_boost
        final_score *= category_boost
        final_score *= query_boost

        # 🔥 SAFETY CLAMP
        final_score = min(final_score, base_score * MAX_FINAL_MULTIPLIER)

        new_result = dict(result)
        new_result["score"] = float(final_score)

        # Preserve + extend debug info
        ranking_details = dict(result.get("ranking_details") or {})

        ranking_details.update({
            "temporal_base_score": base_score,
            "recency_boost": recency_boost,
            "deadline_boost": deadline_boost,
            "category_boost": category_boost,
            "query_temporal_boost": query_boost,
        })

        new_result["ranking_details"] = ranking_details

        ranked_results.append(new_result)

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    ranked_results.sort(
        key=lambda x: _safe_float(x.get("score")),
        reverse=True
    )

    return ranked_results