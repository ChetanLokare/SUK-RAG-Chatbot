"""
Cross-Encoder Semantic Reranker (PRODUCTION VERSION)

Improves retrieval precision by directly scoring:
(query, chunk) pairs.

Uses sentence-transformers cross encoder.

Designed for stability, speed, and high-quality ranking.
"""

from typing import List, Dict
from sentence_transformers import CrossEncoder


# =========================================================
# CONFIG
# =========================================================

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

MAX_TEXT_LENGTH = 1200   # truncate long chunks
ALPHA = 0.6              # weight of existing score
BETA = 0.4               # weight of cross encoder score


# =========================================================
# MODEL (LAZY LOAD)
# =========================================================

_cross_encoder = None


def _get_model():

    global _cross_encoder

    if _cross_encoder is None:
        try:
            _cross_encoder = CrossEncoder(MODEL_NAME)
        except Exception:
            _cross_encoder = None

    return _cross_encoder


# =========================================================
# SAFE TEXT
# =========================================================

def _safe_text(text: str) -> str:

    if not text:
        return ""

    text = text.strip()

    if len(text) > MAX_TEXT_LENGTH:
        return text[:MAX_TEXT_LENGTH]

    return text


# =========================================================
# NORMALIZE SCORES
# =========================================================

def _normalize(scores: List[float]) -> List[float]:

    if not scores:
        return []

    max_s = max(scores)
    min_s = min(scores)

    if max_s == min_s:
        return [0.5 for _ in scores]

    return [(s - min_s) / (max_s - min_s) for s in scores]


# =========================================================
# RERANK FUNCTION
# =========================================================

def cross_encoder_rerank(
    query: str,
    contexts: List[Dict],
    top_k: int = 20,
) -> List[Dict]:
    """
    Semantic reranking using cross encoder.

    Parameters
    ----------
    query : user query
    contexts : retrieved chunks
    top_k : max contexts to rerank

    Returns
    -------
    reranked contexts
    """

    if not contexts or not query:
        return contexts or []

    model = _get_model()

    # If model failed to load → fallback safely
    if model is None:
        return contexts

    # -----------------------------------------------------
    # LIMIT CONTEXTS (speed)
    # -----------------------------------------------------

    contexts = contexts[:top_k]

    # -----------------------------------------------------
    # BUILD PAIRS
    # -----------------------------------------------------

    pairs = []

    for ctx in contexts:
        text = _safe_text(ctx.get("text", ""))
        pairs.append((query, text))

    # -----------------------------------------------------
    # PREDICT
    # -----------------------------------------------------

    try:
        scores = model.predict(pairs)
    except Exception:
        return contexts

    # -----------------------------------------------------
    # NORMALIZE CROSS SCORES
    # -----------------------------------------------------

    norm_scores = _normalize([float(s) for s in scores])

    # -----------------------------------------------------
    # COMBINE SCORES
    # -----------------------------------------------------

    for ctx, raw_score, norm_score in zip(contexts, scores, norm_scores):

        base_score = float(ctx.get("score", 0.0))

        final_score = (ALPHA * base_score) + (BETA * norm_score)

        new_ctx = ctx

        new_ctx["score"] = float(final_score)
        new_ctx["cross_score_raw"] = float(raw_score)
        new_ctx["cross_score"] = float(norm_score)

        # preserve ranking debug
        ranking_details = dict(ctx.get("ranking_details") or {})
        ranking_details.update({
            "cross_encoder_raw": float(raw_score),
            "cross_encoder_norm": float(norm_score),
        })

        new_ctx["ranking_details"] = ranking_details

    # -----------------------------------------------------
    # SORT
    # -----------------------------------------------------

    contexts.sort(
        key=lambda x: float(x.get("score", 0)),
        reverse=True
    )

    return contexts