# backend/retrieval/late_chunking.py

"""
Late Chunking Retrieval Module

Instead of chunking documents during ingestion,
this module chunks retrieved documents dynamically
based on the query.

Advantages
----------

• Better semantic relevance
• Query-aware chunk scoring
• Improved context retrieval
• Reduces chunk fragmentation
• Never returns empty output
"""

import re
from typing import List, Dict


# ============================================================
# CONFIG
# ============================================================

MAX_CHUNK_SIZE = 900
MIN_CHUNK_SIZE = 120
OVERLAP_SIZE = 120

# 🔥 NEW SAFETY CONFIG
FALLBACK_CHARS = 300
MIN_DOC_LENGTH = 40


# ============================================================
# TOKENIZER
# ============================================================

def tokenize(text: str) -> List[str]:

    if not text:
        return []

    return re.findall(r"\w+", text.lower())


# ============================================================
# SENTENCE SPLITTER
# ============================================================

def split_sentences(text: str) -> List[str]:

    if not text:
        return []

    text = text.replace("।", "। ")

    sentences = re.split(r'(?<=[\.\?\!।])\s+', text)

    results = []

    for s in sentences:

        s = s.strip()

        if not s:
            continue

        # 🔥 relaxed filter
        if len(s) < 25:
            continue

        results.append(s)

    return results


# ============================================================
# BUILD LATE CHUNKS (🔥 FIXED OVERLAP)
# ============================================================

def build_late_chunks(text: str) -> List[str]:

    if not text or len(text) < MIN_DOC_LENGTH:
        return []

    sentences = split_sentences(text)

    if not sentences:
        return [text[:FALLBACK_CHARS]]

    chunks = []
    current = []
    char_count = 0

    for sentence in sentences:

        if char_count + len(sentence) > MAX_CHUNK_SIZE:

            if current:

                chunk = " ".join(current).strip()

                if len(chunk) >= MIN_CHUNK_SIZE:
                    chunks.append(chunk)

                # 🔥 FIXED overlap → sentence-level not char slicing
                overlap_sentences = current[-2:] if len(current) >= 2 else current
                current = overlap_sentences.copy()
                char_count = sum(len(s) for s in current)

        current.append(sentence)
        char_count += len(sentence)

    if current:

        chunk = " ".join(current).strip()

        if len(chunk) >= MIN_CHUNK_SIZE:
            chunks.append(chunk)

    # 🔥 fallback safety
    if not chunks:
        return [text[:FALLBACK_CHARS]]

    return chunks


# ============================================================
# RELEVANCE SCORE (🔥 IMPROVED)
# ============================================================

def chunk_relevance_score(query: str, chunk: str) -> float:

    query_tokens = tokenize(query)
    chunk_tokens = tokenize(chunk)

    if not query_tokens or not chunk_tokens:
        return 0.0

    q_set = set(query_tokens)
    c_set = set(chunk_tokens)

    matches = len(q_set.intersection(c_set))

    base_score = matches / max(len(q_set), 1)

    # 🔥 phrase boost
    q_text = " ".join(query_tokens)
    c_text = " ".join(chunk_tokens)

    if q_text and q_text in c_text:
        base_score *= 1.5

    # 🔥 partial phrase boost
    if matches >= 3:
        base_score *= 1.3
    elif matches >= 2:
        base_score *= 1.15

    return base_score


# ============================================================
# RANK LATE CHUNKS (🔥 NEVER EMPTY)
# ============================================================

def rank_late_chunks(query: str, text: str, top_k: int = 5) -> List[Dict]:

    chunks = build_late_chunks(text)

    if not chunks:
        return [{
            "text": text[:FALLBACK_CHARS],
            "score": 0.1
        }]

    scored_chunks = []

    for chunk in chunks:

        score = chunk_relevance_score(query, chunk)

        # 🔥 relaxed filtering
        if score <= 0 and len(chunk) < 200:
            continue

        scored_chunks.append({
            "text": chunk,
            "score": score
        })

    # 🔥 fallback if nothing scored
    if not scored_chunks:
        return [{
            "text": text[:FALLBACK_CHARS],
            "score": 0.1
        }]

    ranked = sorted(
        scored_chunks,
        key=lambda x: x["score"],
        reverse=True
    )

    return ranked[:top_k]


# ============================================================
# PROCESS RETRIEVED DOCUMENTS (🔥 FIXED)
# ============================================================

def late_chunk_documents(
    query: str,
    retrieved_docs: List[Dict],
    top_k_chunks: int = 5
) -> List[Dict]:

    if not retrieved_docs:
        return []

    final_chunks = []
    seen = set()

    for doc in retrieved_docs:

        text = doc.get("text", "")
        metadata = doc.get("metadata", {}) or {}

        if not text:
            continue

        ranked_chunks = rank_late_chunks(query, text, top_k_chunks)

        for c in ranked_chunks:

            chunk_text = c["text"].strip()

            # 🔥 dedupe
            key = chunk_text[:120]

            if key in seen:
                continue

            seen.add(key)

            final_chunks.append({
                "text": chunk_text,
                "score": c["score"],
                "metadata": metadata
            })

    # 🔥 global fallback
    if not final_chunks:

        fallback = retrieved_docs[0]

        return [{
            "text": fallback.get("text", "")[:FALLBACK_CHARS],
            "score": 0.1,
            "metadata": fallback.get("metadata", {})
        }]

    final_chunks = sorted(
        final_chunks,
        key=lambda x: x["score"],
        reverse=True
    )

    return final_chunks[:top_k_chunks]