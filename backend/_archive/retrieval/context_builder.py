from typing import List, Tuple, Dict
import re
import hashlib


# =========================================================
# CONFIG
# =========================================================

MIN_TEXT_LENGTH = 40
STRUCTURED_BOOST = 1.3


# =========================================================
# CLEAN DICT
# =========================================================

def _clean_dict(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


# =========================================================
# STRUCTURED DETECTION
# =========================================================

STRUCTURED_PATTERNS = [
    r"email", r"e-mail", r"phone", r"contact", r"mobile",
    r"\bhod\b", r"head", r"director", r"coordinator",
    r"prof", r"dr\.",
    r"fee", r"amount", r"eligibility", r"last date",
    r"important date",
    r"scholarship", r"grant", r"fund",
    r"@", r"\d{3,}[-\s]\d{3,}", r"\d{6,}",
    r"kolhapur", r"department", r"university",
    r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}",
]

STRUCTURED_REGEX = [re.compile(p, re.IGNORECASE) for p in STRUCTURED_PATTERNS]


def _is_structured(text: str) -> bool:
    if not text:
        return False

    return any(p.search(text) for p in STRUCTURED_REGEX)


# =========================================================
# STRONG DEDUP
# =========================================================

def _deduplicate_chunks(chunks: List[dict]) -> List[dict]:

    seen = set()
    cleaned = []

    for c in chunks:

        text = (c.get("text") or "").strip()

        if not text:
            continue

        key = hashlib.md5(text[:300].lower().encode()).hexdigest()

        if key in seen:
            continue

        seen.add(key)
        cleaned.append(c)

    return cleaned


# =========================================================
# GROUP BY SOURCE (SORTED)
# =========================================================

def _group_by_source(chunks: List[dict]) -> Dict[str, List[dict]]:

    grouped: Dict[str, List[dict]] = {}

    for item in chunks:

        meta = item.get("metadata") or {}
        source = meta.get("source_value")

        if not source:
            continue

        grouped.setdefault(source, []).append(item)

    # 🔥 sort each group by score
    for source in grouped:
        grouped[source].sort(
            key=lambda x: x.get("score", 0),
            reverse=True
        )

    return grouped


# =========================================================
# BUILD CONTEXT
# =========================================================

def build_context(
    retrieved_chunks: List[dict],
    max_chunks: int = 20,
    max_per_source: int = 4,
    max_total_chars: int = 15000,
) -> Tuple[str, List[dict]]:

    if not retrieved_chunks:
        return "", []

    # -----------------------------------------------------
    # GLOBAL SORT
    # -----------------------------------------------------

    retrieved_chunks = sorted(
        retrieved_chunks,
        key=lambda x: x.get("score", 0),
        reverse=True,
    )

    # -----------------------------------------------------
    # DEDUP
    # -----------------------------------------------------

    retrieved_chunks = _deduplicate_chunks(retrieved_chunks)

    # -----------------------------------------------------
    # GROUP
    # -----------------------------------------------------

    grouped_sources = _group_by_source(retrieved_chunks)

    context_blocks: List[str] = []
    citations: List[dict] = []

    seen_citations = set()

    total_chars = 0
    total_chunks = 0
    source_index = 1

    # -----------------------------------------------------
    # BUILD CONTEXT
    # -----------------------------------------------------

    for source_value, items in grouped_sources.items():

        used_from_source = 0

        for item in items:

            if total_chunks >= max_chunks:
                break

            text = (item.get("text") or "").strip()
            meta = item.get("metadata") or {}

            if not text:
                continue

            # -------------------------------------------------
            # FILTER LOW VALUE TEXT
            # -------------------------------------------------

            if len(text) < MIN_TEXT_LENGTH and not _is_structured(text):
                continue

            # -------------------------------------------------
            # LIMIT PER SOURCE
            # -------------------------------------------------

            if used_from_source >= max_per_source:
                break

            # -------------------------------------------------
            # GLOBAL LIMIT
            # -------------------------------------------------

            if total_chars + len(text) > max_total_chars:
                break

            # -------------------------------------------------
            # BUILD BLOCK (🔥 CRITICAL FIX)
            # -------------------------------------------------

            page = meta.get("page_number", -1)

            citation_label = source_value
            if page != -1:
                citation_label += f" (page {page})"

            block = f"[Source {source_index}] {citation_label}\n{text}"

            context_blocks.append(block)

            total_chars += len(text)
            used_from_source += 1
            total_chunks += 1

            # -------------------------------------------------
            # CITATIONS
            # -------------------------------------------------

            citation_key = (source_value, page)

            if citation_key not in seen_citations:

                seen_citations.add(citation_key)

                citations.append(_clean_dict({
                    "source_type": meta.get("source_type"),
                    "source_value": source_value,
                    "page_number": page,
                    "category": meta.get("category"),
                }))

            source_index += 1

        if total_chunks >= max_chunks:
            break

    # -----------------------------------------------------
    # FINAL CONTEXT
    # -----------------------------------------------------

    combined_context = "\n\n".join(context_blocks)

    # 🚨 SAFETY FALLBACK
    if not combined_context:
        combined_context = "No relevant university data found."

    return combined_context, citations