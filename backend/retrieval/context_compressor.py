import re
import hashlib
from typing import List, Dict


# =========================================================
# CONFIG
# =========================================================

MAX_SENTENCES_PER_DOC = 8
MIN_SENTENCE_LENGTH = 10   # 🔥 relaxed
MAX_SENTENCE_LENGTH = 600
STRUCTURED_PRIORITY_BOOST = 1.5
SECTION_PRIORITY_BOOST = 1.3
MAX_CONTEXTS = 30

FALLBACK_CHARS = 500
MIN_DOC_LENGTH = 20


# =========================================================
# REGEX
# =========================================================

TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)
SENTENCE_SPLIT_PATTERN = re.compile(r'(?<=[\.\!\?।])\s+')

EMAIL_PATTERN = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b")
PHONE_PATTERN = re.compile(r"\b\d{3,4}[- ]?\d{6,8}\b")
DATE_PATTERN = re.compile(r"\b\d{1,2}[-/ ]\d{1,2}[-/ ]\d{2,4}\b")

WHITESPACE = re.compile(r"\s+")


# =========================================================
# HELPERS
# =========================================================

def _safe_float(v):
    try:
        return float(v)
    except:
        return 0.0


def _normalize(text: str) -> str:
    return WHITESPACE.sub(" ", (text or "").lower()).strip()


def tokenize(text: str) -> List[str]:
    return TOKEN_PATTERN.findall((text or "").lower())


# =========================================================
# SENTENCE SPLIT
# =========================================================

def split_sentences(text: str) -> List[str]:

    if not text:
        return []

    # 🔥 DO NOT SPLIT TABLE DATA
    if "TABLE DATA" in text:
        return [text]

    text = text.replace("।", "। ")

    parts = SENTENCE_SPLIT_PATTERN.split(text)

    out = []

    for s in parts:
        s = WHITESPACE.sub(" ", s).strip()

        if len(s) < MIN_SENTENCE_LENGTH:
            continue

        if len(s) > MAX_SENTENCE_LENGTH:
            continue

        out.append(s)

    return out


# =========================================================
# STRUCTURED DETECTION
# =========================================================

def contains_structured_info(text: str) -> bool:

    t = text.lower()

    return (
        EMAIL_PATTERN.search(text)
        or PHONE_PATTERN.search(text)
        or DATE_PATTERN.search(text)
        or "deadline" in t
        or "last date" in t
    )


# =========================================================
# SCORING
# =========================================================

def sentence_score(query: str, sentence: str) -> float:

    q_tokens = set(tokenize(query))
    s_tokens = set(tokenize(sentence))

    if not q_tokens or not s_tokens:
        return 0.0

    matches = len(q_tokens & s_tokens)

    score = matches / len(q_tokens)

    if contains_structured_info(sentence):
        score *= STRUCTURED_PRIORITY_BOOST

    return score


# =========================================================
# COMPRESS DOCUMENT
# =========================================================

def compress_document(query: str, text: str, meta: Dict) -> List[str]:

    if not text or len(text) < MIN_DOC_LENGTH:
        return []

    # 🔥 tables preserved as-is
    if meta.get("table_data"):
        return [text]

    sentences = split_sentences(text)

    if not sentences:
        return [text[:FALLBACK_CHARS]]

    scored = []

    for s in sentences:

        score = sentence_score(query, s)

        # 🔥 RELAXED (CRITICAL FIX)
        if score <= 0:
            score = 0.05

        # 🔥 SECTION BOOST
        if meta.get("section_heading"):
            score *= SECTION_PRIORITY_BOOST

        scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [s for _, s in scored[:MAX_SENTENCES_PER_DOC]]


# =========================================================
# DEDUP
# =========================================================

def deduplicate(sentences: List[str]):

    seen = set()
    out = []

    for s in sentences:

        key = hashlib.md5(_normalize(s).encode()).hexdigest()

        if key in seen:
            continue

        seen.add(key)
        out.append(s)

    return out


# =========================================================
# MAIN
# =========================================================

def compress_contexts(
    query: str,
    contexts: List[Dict],
    max_contexts: int = MAX_CONTEXTS
) -> List[Dict]:

    if not contexts:
        return []

    compressed = []

    for ctx in contexts:

        text = ctx.get("text", "")
        meta = ctx.get("metadata", {}) or {}
        base_score = _safe_float(ctx.get("score"))

        if not text:
            continue

        sentences = compress_document(query, text, meta)
        sentences = deduplicate(sentences)

        if not sentences:
            sentences = [text[:FALLBACK_CHARS]]

        final_text = " ".join(sentences)

        if not final_text:
            final_text = text[:FALLBACK_CHARS]

        boost = 1.2 if contains_structured_info(final_text) else 1.0

        compressed.append({
            "text": final_text,
            "metadata": meta,
            "score": base_score * boost
        })

    # 🔥 NEVER EMPTY (GLOBAL FALLBACK)
    if not compressed:
        c = contexts[0]
        return [{
            "text": c.get("text", "")[:FALLBACK_CHARS],
            "metadata": c.get("metadata", {}),
            "score": _safe_float(c.get("score")),
        }]

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    compressed.sort(
        key=lambda x: _safe_float(x.get("score")),
        reverse=True
    )

    return compressed[:max_contexts]