from typing import List, Dict
import math


# =========================================================
# SIMPLE SEMANTIC RERANKER (FAST + NO MODEL)
# =========================================================

def _tokenize(text: str):
    return set(text.lower().split())


def _score(query: str, text: str) -> float:
    q = _tokenize(query)
    t = _tokenize(text)

    if not q or not t:
        return 0.0

    overlap = len(q & t)

    return overlap / (len(q) + 1)


def rerank_contexts(query: str, contexts: List[Dict]) -> List[Dict]:

    if not contexts:
        return []

    reranked = []

    for c in contexts:

        text = (c.get("text") or "").strip()

        if not text:
            continue

        base_score = float(c.get("score", 0))

        semantic_score = _score(query, text)

        # 🔥 combined scoring
        final_score = base_score + (semantic_score * 2.5)

        c["score"] = final_score
        reranked.append(c)

    reranked.sort(key=lambda x: x["score"], reverse=True)

    return reranked