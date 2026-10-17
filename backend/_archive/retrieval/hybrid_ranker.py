from typing import List, Dict
import time
import math

NOW = int(time.time())


# =========================================================
# RECENCY BOOST
# =========================================================

def recency_score(metadata: Dict) -> float:

    deadline_ts = metadata.get("deadline_ts")

    if not deadline_ts:
        return 0.0

    days = (deadline_ts - NOW) / 86400

    # future exam
    if days >= 0:
        return min(2.0, days / 30)

    # recently passed
    if days >= -30:
        return -0.2

    # old exam
    if days >= -365:
        return -1.0

    return -2.0


# =========================================================
# DOCUMENT TYPE BOOST
# =========================================================

TYPE_BOOST = {
    "timetable": 1.0,
    "exam_result": 0.8,
    "circular": 0.5,
    "admission_notice": 0.6,
    "syllabus": 0.3,
    "general": 0.0,
}


def type_score(metadata: Dict) -> float:

    doc_type = metadata.get("document_type")

    return TYPE_BOOST.get(doc_type, 0.0)


# =========================================================
# FINAL SCORE
# =========================================================

def compute_score(vector_score: float, bm25_score: float, metadata: Dict):

    r = recency_score(metadata)
    t = type_score(metadata)

    return (
        0.6 * vector_score
        + 0.3 * bm25_score
        + 0.1 * t
        + 0.2 * r
    )


# =========================================================
# RANK RESULTS
# =========================================================

def hybrid_rank(results: List[Dict]) -> List[Dict]:

    ranked = []

    for item in results:

        metadata = item.get("metadata", {})

        vector_score = item.get("vector_score", 0)
        bm25_score = item.get("bm25_score", 0)

        score = compute_score(vector_score, bm25_score, metadata)

        item["final_score"] = score

        ranked.append(item)

    ranked.sort(key=lambda x: x["final_score"], reverse=True)

    return ranked