"""
Semantic Document Classifier

Uses sentence embeddings to classify academic documents.

More accurate than keyword matching.
"""

from typing import List, Dict
import numpy as np

from sentence_transformers import SentenceTransformer


# ============================================================
# MODEL
# ============================================================

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model = None


def get_model():

    global _model

    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)

    return _model


# ============================================================
# DOCUMENT TYPES
# ============================================================

DOCUMENT_TYPES: Dict[str, List[str]] = {

    "exam_result": [
        "exam result merit list",
        "rank list result announcement",
        "marks statement examination",
        "candidate result list"
    ],

    "timetable": [
        "exam timetable schedule",
        "examination time table",
        "paper schedule examination"
    ],

    "circular": [
        "official circular notice",
        "administrative notification",
        "important circular issued"
    ],

    "syllabus": [
        "course syllabus structure",
        "programme syllabus document",
        "course curriculum details"
    ],

    "admission_notice": [
        "admission notification",
        "application form admission",
        "eligibility criteria admission"
    ],

    "scholarship": [
        "scholarship notification",
        "financial assistance scholarship",
        "student fellowship scheme"
    ]
}


# ============================================================
# PRECOMPUTE CATEGORY EMBEDDINGS
# ============================================================

_category_embeddings = None


def _build_category_embeddings():

    model = get_model()

    category_vectors = {}

    for category, examples in DOCUMENT_TYPES.items():

        embeddings = model.encode(examples)

        category_vectors[category] = np.mean(embeddings, axis=0)

    return category_vectors


def get_category_embeddings():

    global _category_embeddings

    if _category_embeddings is None:
        _category_embeddings = _build_category_embeddings()

    return _category_embeddings


# ============================================================
# COSINE SIMILARITY
# ============================================================

def cosine_similarity(a, b):

    denom = np.linalg.norm(a) * np.linalg.norm(b)

    if denom == 0:
        return 0.0

    return float(np.dot(a, b) / denom)


# ============================================================
# CLASSIFY DOCUMENT
# ============================================================

def classify_document_semantic(text: str) -> str:

    if not text or len(text) < 200:
        return "general"

    model = get_model()

    category_vectors = get_category_embeddings()

    # use only first part of document for classification
    text = text[:3000]

    doc_embedding = model.encode(text)

    best_category = "general"
    best_score = 0

    for category, vector in category_vectors.items():

        score = cosine_similarity(doc_embedding, vector)

        if score > best_score:

            best_score = score
            best_category = category

    # confidence threshold
    if best_score < 0.35:
        return "general"

    return best_category