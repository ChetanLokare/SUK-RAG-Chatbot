from typing import List, Dict
import re
import hashlib


# =========================================================
# CONFIG
# =========================================================

MAX_CONTEXTS = 18
MAX_CONTEXT_CHARS = 14000


# =========================================================
# CLEAN
# =========================================================

_ws = re.compile(r"\s+")


def clean(text: str) -> str:
    return _ws.sub(" ", (text or "")).strip()


# =========================================================
# QUERY SCORE
# =========================================================

def query_score(query: str, text: str) -> float:

    q = set(query.lower().split())
    t = text.lower()

    matches = sum(1 for w in q if w in t)

    return matches / (len(q) + 1)


# =========================================================
# FILTER
# =========================================================

def filter_contexts(query: str, contexts: List[Dict]) -> List[Dict]:

    out = []
    q = query.lower()

    for c in contexts:

        meta = c.get("metadata", {}) or {}
        text = clean(c.get("text", ""))

        if not text or len(text) < 30:   # 🔥 relaxed
            continue

        # 🚫 Remove CV noise
        src = (meta.get("source_value") or "").lower()
        if "cv" in src or "resume" in src:
            if "faculty" not in q:
                continue

        score = float(c.get("score", 0))
        score += query_score(query, text)

        # 🔥 SECTION BOOST
        if meta.get("section_heading"):
            score *= 1.3

        # 🔥 PDF BOOST (FIXED)
        if meta.get("source_type") == "pdf":
            score *= 1.2

        out.append({
            "text": text,
            "metadata": meta,
            "score": score
        })

    return out


# =========================================================
# DEDUP
# =========================================================

def dedupe(contexts: List[Dict]):

    seen = set()
    out = []

    for c in contexts:

        key = hashlib.md5(c["text"][:200].lower().encode()).hexdigest()

        if key in seen:
            continue

        seen.add(key)
        out.append(c)

    return out


# =========================================================
# SORT + LIMIT
# =========================================================

def rank_contexts(contexts: List[Dict]):

    contexts.sort(key=lambda x: x["score"], reverse=True)

    total = 0
    out = []

    for c in contexts:

        txt = c["text"]

        if total + len(txt) > MAX_CONTEXT_CHARS:
            break

        out.append(c)
        total += len(txt)

        if len(out) >= MAX_CONTEXTS:
            break

    return out


# =========================================================
# BUILD CONTEXT BLOCK (🔥 SECTION AWARE)
# =========================================================

def build_context(contexts: List[Dict]):

    parts = []

    for i, c in enumerate(contexts, 1):

        meta = c["metadata"]

        src = meta.get("source_value", "unknown")
        page = meta.get("page_number")
        heading = meta.get("section_heading", "")

        label = f"[Source {i}] {src}"

        if page not in (None, -1):
            label += f" (page {page})"

        if heading:
            label += f"\nSECTION: {heading}"

        parts.append(f"{label}\n{c['text']}")

    return "\n\n".join(parts)


# =========================================================
# PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are an AI assistant that helps users find information about Shivaji University.
You are not an official source.

STRICT RULES:
- Use ONLY the given sources. Never add facts from your own knowledge.
- Combine multiple sources; say so if they conflict.
- Never invent names, dates, fees, phone numbers or e-mail addresses.
- If the sources do not contain the answer, say so plainly.

FORMAT:
- Start with a direct answer.
- Then key details, contact information (only if it appears in the sources)
  and notes. Skip any section that has nothing to say.
"""


def build_prompt(query: str, contexts: List[Dict]):

    contexts = filter_contexts(query, contexts)
    contexts = dedupe(contexts)
    contexts = rank_contexts(contexts)

    ctx_block = build_context(contexts)

    if not ctx_block:
        ctx_block = "No relevant data found."

    return f"""
{SYSTEM_PROMPT}

QUESTION:
{query}

CONTEXT:
{ctx_block}

Answer using only the context above:
""".strip()


# =========================================================
# MAIN
# =========================================================

def synthesize_answer(query: str, contexts: List[Dict]) -> Dict:

    contexts = filter_contexts(query, contexts)
    contexts = dedupe(contexts)
    contexts = rank_contexts(contexts)

    prompt = build_prompt(query, contexts)

    citations = []

    for c in contexts[:6]:
        m = c["metadata"]

        citations.append({
            "source_type": m.get("source_type"),
            "source_value": m.get("source_value"),
            "page_number": m.get("page_number"),
            "category": m.get("category"),
        })

    return {
        "prompt": prompt,
        "contexts_used": len(contexts),
        "citations": citations,
    }