#  backend/ingestion/chunker.py

"""
Robust text chunking engine for RAG ingestion.

Features
--------
• heading-aware chunking
• structured data preservation
• multilingual sentence splitting
• overlap for embedding continuity
• navigation/UI noise removal
• chunk deduplication
• safe handling of tabular/structured data
"""

import re
import hashlib
from typing import List, Tuple


# ==========================================================
# CONFIG
# ==========================================================

MIN_SENTENCE_LEN = 25
MIN_SECTION_LEN = 100   # lowered → improves chunk count
MIN_FINAL_CHUNK = 100   # lowered → avoids chunk drop

OVERLAP_CHARS = 120
MAX_LINE_LENGTH = 5000


# ==========================================================
# NAVIGATION CLEANER
# ==========================================================

NAVIGATION_PATTERNS = [
    r"Skip to Content",
    r"Skip to Navigation",
    r"Screen Reader Access",
    r"Email Login",
    r"Powered by.*",
    r"Copyright.*",
    r"All Rights Reserved.*",
    r"Visitors\s*:\s*\d+",
]


def _clean_navigation(text: str) -> str:

    if not text:
        return ""

    for pattern in NAVIGATION_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    text = re.sub(r"\b(Home|HOME)\b(\s+\1\b)+", "", text)

    text = re.sub(r"-{3,}", "", text)
    text = re.sub(r"\*{3,}", "", text)
    text = re.sub(r"\|{2,}", "", text)

    text = text.replace("\r", "\n")

    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


# ==========================================================
# STRUCTURED DETECTION
# ==========================================================

STRUCTURED_PATTERNS = [
    r"\bemail\b", r"\bphone\b", r"\bcontact\b",
    r"\bhod\b", r"\bprof\b", r"\bdr\b",
    r"\bfee\b", r"\beligibility\b",
    r"\bdeadline\b", r"\bscholarship\b",
    r"@", r"\d{3,}", r":"
]

STRUCTURED_REGEX = [re.compile(p, re.IGNORECASE) for p in STRUCTURED_PATTERNS]


def _is_structured(text: str) -> bool:

    if not text:
        return False

    for pattern in STRUCTURED_REGEX:
        if pattern.search(text):
            return True

    return False


# ==========================================================
# SENTENCE SPLITTING
# ==========================================================

SENTENCE_SPLIT_REGEX = re.compile(
    r'(?<=[\.\?\!।])\s+',
    flags=re.UNICODE
)


def _split_sentences(text: str) -> List[str]:

    if not text:
        return []

    text = text.replace("।", "। ")

    sentences = SENTENCE_SPLIT_REGEX.split(text)

    cleaned = []

    for s in sentences:

        s = s.strip()

        if not s:
            continue

        if len(s) < MIN_SENTENCE_LEN and not _is_structured(s):
            continue

        if re.fullmatch(r"\d+", s):
            continue

        cleaned.append(s)

    return cleaned


# ==========================================================
# HEADING DETECTION
# ==========================================================

def _looks_like_heading(line: str) -> bool:

    if not line:
        return False

    line = line.strip()

    if len(line) > 90:
        return False

    if _is_structured(line):
        return False

    if line.isupper() and len(line.split()) <= 10:
        return True

    if (
        len(line) < 70
        and not re.search(r"[\.?!।]", line)
        and len(line.split()) <= 8
    ):
        return True

    return False


# ==========================================================
# SPLIT INTO SECTIONS
# ==========================================================

def _split_by_headings(text: str) -> List[Tuple[str, str]]:

    lines = text.split("\n")

    sections: List[Tuple[str, str]] = []

    current_heading = "General"
    buffer: List[str] = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        if len(line) > MAX_LINE_LENGTH:
            continue

        if _looks_like_heading(line):

            if buffer:
                sections.append((current_heading, " ".join(buffer)))
                buffer = []

            current_heading = line
            continue

        buffer.append(line)

    if buffer:
        sections.append((current_heading, " ".join(buffer)))

    return sections


# ==========================================================
# SENTENCE CHUNK BUILDER
# ==========================================================

def _build_chunks_from_sentences(
    heading: str,
    content: str,
    max_chars: int,
) -> List[str]:

    sentences = _split_sentences(content)

    if not sentences:
        return []

    chunks = []
    current = []
    char_count = 0

    for sentence in sentences:

        if _is_structured(sentence) and current:
            chunks.append(" ".join(current).strip())
            current = []
            char_count = 0

        if char_count + len(sentence) > max_chars:

            if current:
                chunk_text = " ".join(current).strip()
                chunks.append(chunk_text)

                overlap = chunk_text[-OVERLAP_CHARS:]
                current = [overlap]
                char_count = len(overlap)

            else:
                current = []
                char_count = 0

        current.append(sentence)
        char_count += len(sentence)

    if current:
        chunks.append(" ".join(current).strip())

    if chunks:
        chunks[0] = f"{heading}\n\n{chunks[0]}"

    return chunks


# ==========================================================
# FLAT CHUNK BUILDER
# ==========================================================

def _build_flat_chunks(text: str, max_chars: int) -> List[str]:

    lines = text.split("\n")

    chunks = []
    current = []
    char_count = 0

    for line in lines:

        line = line.strip()

        if not line:
            continue

        if len(line) < 10 and not _is_structured(line):
            continue

        if char_count + len(line) > max_chars:

            if current:
                chunk_text = " ".join(current).strip()
                chunks.append(chunk_text)

                overlap = chunk_text[-OVERLAP_CHARS:]
                current = [overlap]
                char_count = len(overlap)

            else:
                current = []
                char_count = 0

        current.append(line)
        char_count += len(line)

    if current:
        chunks.append(" ".join(current).strip())

    return chunks


# ==========================================================
# DEDUPLICATION
# ==========================================================

def _deduplicate_chunks(chunks: List[str]) -> List[str]:

    seen = set()
    final = []

    for chunk in chunks:

        normalized = re.sub(r"\s+", " ", chunk.lower().strip())

        if not normalized:
            continue

        key = hashlib.md5(normalized.encode()).hexdigest()

        if key in seen:
            continue

        seen.add(key)
        final.append(chunk.strip())

    return final


# ==========================================================
# MAIN FUNCTION
# ==========================================================

def chunk_text(
    text: str,
    source_type: str = "url",
) -> List[str]:

    if not text:
        return []

    text = _clean_navigation(text)

    # CSV / tabular mode
    if source_type == "csv":
        chunks = _build_flat_chunks(text, 2200)
        return _deduplicate_chunks(chunks)

    if source_type == "pdf":
        max_chars = 2200
    elif source_type == "url":
        max_chars = 1700
    else:
        max_chars = 1800

    sections = _split_by_headings(text)

    all_chunks = []

    for heading, content in sections:

        if len(content) < MIN_SECTION_LEN and not _is_structured(content):
            continue

        section_chunks = _build_chunks_from_sentences(
            heading=heading,
            content=content,
            max_chars=max_chars,
        )

        all_chunks.extend(section_chunks)

    # fallback if no sections worked
    if not all_chunks:
        all_chunks = _build_flat_chunks(text, max_chars)

    filtered = [
        c for c in all_chunks
        if len(c) >= MIN_FINAL_CHUNK or _is_structured(c)
    ]

    # final fallback (VERY IMPORTANT)
    if not filtered and text:
        filtered = [text[:max_chars]]

    return _deduplicate_chunks(filtered)