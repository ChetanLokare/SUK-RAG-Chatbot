from typing import List, Dict, Optional
import hashlib
import re
from datetime import datetime, timezone

from backend.core.chroma_client import get_collection

from backend.ingestion.chunker import chunk_text
from backend.ingestion.hierarchical_chunker import hierarchical_chunk_text
from backend.ingestion.language_detector import detect_language

from backend.graph.entity_extractor import extract_entities_and_build_graph
from backend.graph.university_graph_builder import build_university_graph


# =========================================================
# CONFIG
# =========================================================

MAX_TEXT_LENGTH = 300_000
MIN_CHUNK_LENGTH = 20
BATCH_SIZE = 32
MIN_TOTAL_CHUNKS = 3


# =========================================================
# UTILS
# =========================================================

_whitespace = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    return _whitespace.sub(" ", text.replace("\r", " ")).strip()


def _looks_structured(text: str) -> bool:
    if not text:
        return False

    t = text.lower()

    return (
        "@" in text
        or ":" in text
        or re.search(r"\d{3,}", text)
        or any(k in t for k in [
            "email", "phone", "contact", "hod",
            "department", "prof", "dr"
        ])
    )


# =========================================================
# FORCE SPLIT
# =========================================================

def _force_split(text: str, size: int = 1200) -> List[str]:
    return [text[i:i + size].strip() for i in range(0, len(text), size) if text[i:i + size].strip()]


# =========================================================
# DEDUP CHUNKS
# =========================================================

def _deduplicate_chunks(chunks: List[str]) -> List[str]:
    seen = set()
    results = []

    for chunk in chunks:
        norm = _whitespace.sub(" ", chunk.lower().strip())
        if not norm:
            continue

        key = hashlib.md5(norm.encode()).hexdigest()
        if key in seen:
            continue

        seen.add(key)
        results.append(chunk.strip())

    return results


# =========================================================
# GENERATE CHUNKS
# =========================================================

def _generate_chunks(text: str, source_id: str, source_type: str) -> List[str]:

    chunks = []

    try:
        records = hierarchical_chunk_text(text, source_id, source_type)
        chunks = [r["chunk_text"] for r in records]
        print(f"🧠 hierarchical chunks → {len(chunks)}")
    except Exception as e:
        print("⚠️ hierarchical failed:", e)

    if not chunks:
        try:
            chunks = chunk_text(text=text, source_type=source_type)
            print(f"🧠 fallback chunks → {len(chunks)}")
        except Exception as e:
            print("⚠️ chunk_text failed:", e)

    if not chunks:
        print("⚠️ FORCE SPLIT TRIGGERED")
        chunks = _force_split(text)

    if len(chunks) < MIN_TOTAL_CHUNKS and len(text) > 500:
        print("⚠️ LOW CHUNK COUNT → forcing split")
        chunks = _force_split(text)

    return chunks


# =========================================================
# CATEGORY NORMALIZATION
# =========================================================

def _normalize_category(category: Optional[str]) -> str:
    if not category:
        return "general"

    mapping = {
        "scholarships": "scholarship",
        "events": "event",
        "admissions": "admission",
        "exams": "exam",
        "notices": "notice",
        "circulars": "circular",
    }

    return mapping.get(category.strip().lower(), category.strip().lower())


# =========================================================
# ID GENERATOR
# =========================================================

def _generate_chunk_id(source_id, page_number, chunk_text, position):
    base = f"{source_id}|{page_number}|{position}|{chunk_text}"
    h = hashlib.sha256(base.encode()).hexdigest()
    return f"{source_id}_{h[:24]}"


# =========================================================
# 🔥 FIXED DELETE (CRITICAL)
# =========================================================

def _delete_existing_chunks(collection, source_id):
    try:
        print(f"🗑 Deleting old vectors for source_id={source_id}")
        collection.delete(where={"source_id": source_id})
    except Exception as e:
        print("⚠️ delete failed:", e)


# =========================================================
# MAIN INDEX FUNCTION
# =========================================================

def index_document(
    source_id: str,
    source_type: str,
    category: Optional[str],
    language: Optional[str],
    source_value: str,
    page_number: Optional[int],
    text: str,
    extra_metadata: Optional[Dict] = None,

    # 🔥 NEW PARAM (CRITICAL FIX)
    is_first_page: bool = False,
):

    print("\n📥 INDEX START:", source_id)

    if not text or len(text.strip()) < 30:
        raise RuntimeError("Text too small for indexing")

    text = _normalize_text(text)

    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]

    collection = get_collection()

    # =====================================================
    # 🔥 DELETE ONLY ONCE (CRITICAL FIX)
    # =====================================================

    if is_first_page:
        _delete_existing_chunks(collection, source_id)

    # =====================================================
    # CHUNKING
    # =====================================================

    chunks = _generate_chunks(text, source_id, source_type)
    chunks = _deduplicate_chunks(chunks)

    chunks = [
        c for c in chunks
        if len(c) >= MIN_CHUNK_LENGTH or _looks_structured(c)
    ]

    if not chunks:
        chunks = _force_split(text)

    # =====================================================
    # BUILD
    # =====================================================

    ids, documents, metadatas = [], [], []

    ts = int(datetime.now(timezone.utc).timestamp())

    for i, chunk in enumerate(chunks):

        chunk_id = _generate_chunk_id(source_id, page_number, chunk, i)

        try:
            extract_entities_and_build_graph(chunk)
            build_university_graph(chunk)
        except Exception:
            pass

        chunk_language = language or "unknown"

        if not language:
            try:
                chunk_language = detect_language(chunk)
            except Exception:
                pass

        metadata = {
            "source_id": source_id,
            "source_type": source_type,
            "category": _normalize_category(category),
            "language": chunk_language,
            "source_value": source_value,
            "page_number": page_number or -1,
            "chunk_position": i,
            "chunk_length": len(chunk),
            "indexed_at_ts": ts,
        }

        if extra_metadata:
            metadata.update(extra_metadata)

        ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append(metadata)

    if not documents:
        raise RuntimeError("NO DOCUMENTS TO INSERT")

    # =====================================================
    # INSERT
    # =====================================================

    try:
        for i in range(0, len(documents), BATCH_SIZE):
            collection.add(
                ids=ids[i:i+BATCH_SIZE],
                documents=documents[i:i+BATCH_SIZE],
                metadatas=metadatas[i:i+BATCH_SIZE],
            )

    except Exception as e:
        print("❌ CHROMA INSERT FAILED:", e)
        raise RuntimeError(f"Chroma add failed: {e}")

    print("✅ INDEX COMPLETE\n")

    return {
        "chunks_indexed": len(documents),
        "source_id": source_id,
    }