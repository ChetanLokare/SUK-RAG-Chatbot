# backend/ingestion/hierarchical_chunker.py

"""
Hierarchical chunking system for RAG ingestion (FINAL PRODUCTION VERSION)

Fixes
-----
• prevents single-section collapse
• improves heading detection
• forces chunk creation even if no headings
• avoids large unchunked sections
• guarantees minimum chunk count
"""

import re
from typing import List, Dict

from backend.ingestion.semantic_chunker import semantic_chunk_text


# =========================================================
# CONFIG (🔥 FIXED)
# =========================================================

MAX_HEADING_LENGTH = 120

# 🔥 LOWERED → ensures sections are not discarded
MIN_SECTION_CHARS = 40

DEFAULT_SECTION_TITLE = "General"


# =========================================================
# TEXT CLEANING
# =========================================================

_whitespace = re.compile(r"\s+")


def _clean_text(text: str) -> str:

    if not text:
        return ""

    text = text.replace("\r", "\n")

    lines = []

    for line in text.split("\n"):
        line = _whitespace.sub(" ", line).strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


# =========================================================
# STRUCTURED CONTENT DETECTION
# =========================================================

STRUCTURED_PATTERNS = [
    r"@",
    r"\d{6,}",
    r"\bemail\b",
    r"\bphone\b",
    r"\bmobile\b",
    r"\bfax\b",
]

STRUCTURED_REGEX = [re.compile(p, re.IGNORECASE) for p in STRUCTURED_PATTERNS]


def _is_structured(line: str) -> bool:

    if not line:
        return False

    for r in STRUCTURED_REGEX:
        if r.search(line):
            return True

    if ":" in line:
        return True

    return False


# =========================================================
# HEADING DETECTION (🔥 IMPROVED)
# =========================================================

def _looks_like_heading(line: str) -> bool:

    if not line:
        return False

    line = line.strip()

    if len(line) > MAX_HEADING_LENGTH:
        return False

    if _is_structured(line):
        return False

    words = line.split()

    if len(words) > 12:
        return False

    # ALL CAPS
    if line.isupper() and len(words) <= 10:
        return True

    # numbered headings
    if re.match(r"^\d+(\.\d+)*\s+[A-Za-z]", line):
        return True

    # colon headings
    if line.endswith(":") and len(words) <= 10:
        return True

    # Title case headings
    if re.match(r"^[A-Z][A-Za-z0-9\s\-&,]{3,}$", line):
        return True

    # 🔥 NEW: short lines without punctuation
    if (
        len(line) < 80
        and not re.search(r"[\.?!।]", line)
        and len(words) <= 8
    ):
        return True

    return False


# =========================================================
# SPLIT DOCUMENT INTO SECTIONS (🔥 FIXED)
# =========================================================

def split_into_sections(text: str) -> List[Dict]:

    if not text:
        return []

    text = text.replace("\r", "\n")

    lines = text.split("\n")

    sections: List[Dict] = []

    current_title = DEFAULT_SECTION_TITLE
    buffer: List[str] = []

    for line in lines:

        stripped = line.strip()

        if not stripped:
            continue

        if _looks_like_heading(stripped):

            if buffer:

                section_text = " ".join(buffer).strip()

                if section_text:
                    sections.append({
                        "section_title": current_title,
                        "content": section_text
                    })

                buffer = []

            current_title = stripped.rstrip(":").strip()
            continue

        buffer.append(stripped)

    if buffer:

        section_text = " ".join(buffer).strip()

        if section_text:
            sections.append({
                "section_title": current_title,
                "content": section_text
            })

    # 🔥 CRITICAL FIX: if only 1 section → split artificially
    if len(sections) == 1:

        content = sections[0]["content"]

        if len(content) > 1200:

            parts = re.split(r'(?<=[\.\?\!।])\s+', content)

            mid = len(parts) // 2

            return [
                {
                    "section_title": sections[0]["section_title"],
                    "content": " ".join(parts[:mid])
                },
                {
                    "section_title": sections[0]["section_title"],
                    "content": " ".join(parts[mid:])
                }
            ]

    return sections


# =========================================================
# BUILD HIERARCHICAL CHUNKS (🔥 FIXED)
# =========================================================

def build_hierarchical_chunks(
    text: str,
    source_id: str,
    source_type: str
) -> List[Dict]:

    if not text:
        return []

    sections = split_into_sections(text)

    chunks: List[Dict] = []
    chunk_index = 0

    for section in sections:

        title = section["section_title"]
        content = section["content"]

        if not content or len(content.strip()) < MIN_SECTION_CHARS:
            continue

        try:
            semantic_chunks = semantic_chunk_text(content)
        except Exception:
            semantic_chunks = []

        # 🔥 FORCE fallback if semantic fails
        if not semantic_chunks:
            semantic_chunks = [content]

        for chunk in semantic_chunks:

            chunk = chunk.strip()

            if not chunk:
                continue

            chunks.append({
                "chunk_text": f"{title}\n\n{chunk}",
                "section_title": title,
                "chunk_index": chunk_index,
                "source_id": source_id,
                "source_type": source_type
            })

            chunk_index += 1

    # 🔥 FINAL SAFETY (CRITICAL)
    if not chunks:

        return [{
            "chunk_text": text[:1500],
            "section_title": DEFAULT_SECTION_TITLE,
            "chunk_index": 0,
            "source_id": source_id,
            "source_type": source_type
        }]

    return chunks


# =========================================================
# MAIN ENTRY (🔥 FINAL FIX)
# =========================================================

def hierarchical_chunk_text(
    text: str,
    source_id: str,
    source_type: str
) -> List[Dict]:

    if not text:
        return []

    text = _clean_text(text)

    try:
        chunks = build_hierarchical_chunks(
            text=text,
            source_id=source_id,
            source_type=source_type
        )
    except Exception:
        chunks = []

    # 🔥 HARD FALLBACK
    if not chunks:

        try:
            semantic_chunks = semantic_chunk_text(text)
        except Exception:
            semantic_chunks = []

        if not semantic_chunks:
            semantic_chunks = [text[:1500]]

        return [
            {
                "chunk_text": chunk,
                "section_title": DEFAULT_SECTION_TITLE,
                "chunk_index": i,
                "source_id": source_id,
                "source_type": source_type
            }
            for i, chunk in enumerate(semantic_chunks)
        ]

    return chunks