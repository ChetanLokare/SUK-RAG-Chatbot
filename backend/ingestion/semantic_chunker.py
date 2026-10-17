# backend/ingestion/semantic_chunker.py

"""
Semantic chunking engine for RAG ingestion (FINAL PRODUCTION VERSION)

Improvements
------------
• prevents over-merging of content
• enforces chunk splitting for large documents
• guarantees minimum chunk count
• better overlap for retrieval continuity
• stable fallback behavior
"""

from typing import List
import re
import threading
import numpy as np

from sentence_transformers import SentenceTransformer


# =========================================================
# CONFIG (🔥 FIXED)
# =========================================================

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# 🔥 LOWERED (prevents everything merging into one chunk)
SIMILARITY_THRESHOLD = 0.55

# 🔥 REDUCED (forces more chunks)
MAX_CHUNK_CHARS = 1200
MIN_CHUNK_CHARS = 120

# 🔥 INCREASED (better context continuity)
OVERLAP_SENTENCES = 2

MAX_SENTENCE_LENGTH = 1200


# =========================================================
# MODEL LOADING
# =========================================================

_model = None
_model_lock = threading.Lock()


def get_model():
    global _model

    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer(MODEL_NAME)

    return _model


# =========================================================
# TEXT CLEANING
# =========================================================

_whitespace = re.compile(r"\s+")


def _clean_text(text: str) -> str:

    if not text:
        return ""

    text = text.replace("\r", " ")
    text = _whitespace.sub(" ", text)

    return text.strip()


# =========================================================
# SENTENCE SPLITTER
# =========================================================

def split_sentences(text: str) -> List[str]:

    if not text:
        return []

    text = _clean_text(text)

    text = text.replace("।", "। ")

    sentences = re.split(r'(?<=[\.\?\!।])\s+', text)

    cleaned = []

    for s in sentences:

        s = s.strip()

        if not s:
            continue

        if len(s) < 25:
            continue

        if len(s) > MAX_SENTENCE_LENGTH:

            parts = re.split(r"[;,]", s)

            for p in parts:
                p = p.strip()
                if len(p) >= 25:
                    cleaned.append(p)

            continue

        cleaned.append(s)

    return cleaned


# =========================================================
# COSINE SIMILARITY
# =========================================================

def cosine_similarity(a, b):

    a = np.asarray(a)
    b = np.asarray(b)

    denom = np.linalg.norm(a) * np.linalg.norm(b)

    if denom == 0:
        return 0.0

    return float(np.dot(a, b) / denom)


# =========================================================
# SEMANTIC GROUPING
# =========================================================

def group_semantic_sentences(sentences: List[str]) -> List[List[str]]:

    if not sentences:
        return []

    model = get_model()

    embeddings = model.encode(
        sentences,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True
    )

    groups: List[List[str]] = []

    current_group = [sentences[0]]
    current_embeddings = [embeddings[0]]

    for i in range(1, len(sentences)):

        centroid = np.mean(current_embeddings, axis=0)
        sim = cosine_similarity(centroid, embeddings[i])

        if sim >= SIMILARITY_THRESHOLD:
            current_group.append(sentences[i])
            current_embeddings.append(embeddings[i])
        else:
            groups.append(current_group)
            current_group = [sentences[i]]
            current_embeddings = [embeddings[i]]

    if current_group:
        groups.append(current_group)

    return groups


# =========================================================
# CHUNK BUILDER
# =========================================================

def build_chunks(groups: List[List[str]]) -> List[str]:

    chunks: List[str] = []

    current: List[str] = []
    char_count = 0

    for group in groups:

        group_text = " ".join(group).strip()

        if not group_text:
            continue

        if char_count + len(group_text) > MAX_CHUNK_CHARS:

            if current:

                chunk = " ".join(current).strip()

                if len(chunk) >= MIN_CHUNK_CHARS:
                    chunks.append(chunk)

                # 🔥 BETTER OVERLAP
                overlap = current[-OVERLAP_SENTENCES:] if len(current) >= OVERLAP_SENTENCES else current
                current = overlap.copy()
                char_count = sum(len(x) for x in current)

            else:
                current = []
                char_count = 0

        current.append(group_text)
        char_count += len(group_text)

    if current:
        chunk = " ".join(current).strip()
        if len(chunk) >= MIN_CHUNK_CHARS:
            chunks.append(chunk)

    return chunks


# =========================================================
# FORCE SPLIT LARGE CHUNKS (🔥 CRITICAL)
# =========================================================

def _force_split_large_chunks(chunks: List[str]) -> List[str]:

    final = []

    for chunk in chunks:

        if len(chunk) <= MAX_CHUNK_CHARS:
            final.append(chunk)
            continue

        sentences = split_sentences(chunk)

        temp = []
        size = 0

        for s in sentences:

            if size + len(s) > MAX_CHUNK_CHARS:

                if temp:
                    final.append(" ".join(temp))

                temp = []
                size = 0

            temp.append(s)
            size += len(s)

        if temp:
            final.append(" ".join(temp))

    return final


# =========================================================
# MAIN FUNCTION (🔥 FIXED)
# =========================================================

def semantic_chunk_text(text: str) -> List[str]:

    if not text:
        return []

    text = _clean_text(text)

    sentences = split_sentences(text)

    if not sentences:
        return []

    groups = group_semantic_sentences(sentences)

    chunks = build_chunks(groups)

    # 🔥 CRITICAL FIX
    chunks = _force_split_large_chunks(chunks)

    # 🔥 GUARANTEE MINIMUM CHUNKS
    if len(chunks) <= 1 and len(sentences) > 6:

        mid = len(sentences) // 2

        chunks = [
            " ".join(sentences[:mid]),
            " ".join(sentences[mid:])
        ]

    return chunks