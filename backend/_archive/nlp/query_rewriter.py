"""
Query Rewriting / Query Expansion module (FINAL PRODUCTION VERSION)

Improves retrieval recall by generating multiple search queries.

Features:
• LLM-based rewriting
• safe fallback
• deduplication
• injection-safe input handling
• deterministic limits
"""

from typing import List
import re
import logging
import time

from openai import OpenAI

from backend.core.config import OPENAI_API_KEY


# ============================================================
# CONFIG
# ============================================================

MAX_QUERY_VARIANTS = 5
MIN_QUERY_LENGTH = 2

MODEL_NAME = "gpt-4o-mini"

TEMPERATURE = 0.2
MAX_TOKENS = 120

MAX_RETRIES = 2
RETRY_DELAY = 1.0


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# CLIENT (SAFE INIT)
# ============================================================

client = None

if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        client = None


# ============================================================
# PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a search query optimizer for a document retrieval system.

Rewrite the user query into improved search queries.

Rules:
- Preserve original meaning
- Expand abbreviations
- Use different wording
- Do NOT invent facts
- Do NOT answer the query

Output:
- 3 to 5 queries
- Each on a new line
- No numbering
- No explanation
"""


# ============================================================
# CLEAN QUERY (🔥 SAFE)
# ============================================================

def _clean_query(query: str) -> str:

    if not query:
        return ""

    query = query.strip()

    # remove newlines / injection attempts
    query = query.replace("\n", " ").replace("\r", " ")

    # normalize spaces
    query = re.sub(r"\s+", " ", query)

    # truncate overly long queries
    if len(query) > 300:
        query = query[:300]

    return query


# ============================================================
# NORMALIZE
# ============================================================

def _normalize(q: str) -> str:
    return re.sub(r"\s+", " ", (q or "").lower().strip())


# ============================================================
# PARSE LLM OUTPUT
# ============================================================

def _parse_queries(text: str) -> List[str]:

    if not text:
        return []

    lines = text.split("\n")

    queries = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # remove numbering
        line = re.sub(r"^\d+[\).\s-]*", "", line)

        if len(line) < MIN_QUERY_LENGTH:
            continue

        queries.append(line)

    return queries


# ============================================================
# DEDUPLICATE
# ============================================================

def _deduplicate(queries: List[str]) -> List[str]:

    seen = set()
    result = []

    for q in queries:

        norm = _normalize(q)

        if not norm or norm in seen:
            continue

        seen.add(norm)
        result.append(q.strip())

    return result


# ============================================================
# FALLBACK (🔥 IMPROVED)
# ============================================================

def _fallback(query: str) -> List[str]:

    tokens = query.split()

    variations = [query]

    if len(tokens) >= 2:
        variations.append(" ".join(tokens[:2]))

    if len(tokens) >= 3:
        variations.append(" ".join(tokens[:3]))

    # simple synonym hints
    if "hod" in query.lower():
        variations.append(query.replace("hod", "head of department"))

    if "cs" in query.lower():
        variations.append(query.replace("cs", "computer science"))

    return _deduplicate(variations)[:MAX_QUERY_VARIANTS]


# ============================================================
# LLM CALL (SAFE)
# ============================================================

def _call_llm(query: str) -> List[str]:

    if not client:
        return []

    for _ in range(MAX_RETRIES):

        try:

            response = client.chat.completions.create(
                model=MODEL_NAME,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
            )

            if not response.choices:
                continue

            text = response.choices[0].message.content

            queries = _parse_queries(text)

            if queries:
                return queries

        except Exception as e:
            logger.warning("Query rewrite error: %s", str(e))

        time.sleep(RETRY_DELAY)

    return []


# ============================================================
# MAIN FUNCTION
# ============================================================

def rewrite_query(query: str) -> List[str]:

    if not query:
        return []

    query = _clean_query(query)

    if len(query) < MIN_QUERY_LENGTH:
        return [query]

    # --------------------------------------------------------
    # TRY LLM
    # --------------------------------------------------------

    queries = _call_llm(query)

    if not queries:
        return _fallback(query)

    # always include original query
    queries.insert(0, query)

    queries = _deduplicate(queries)

    return queries[:MAX_QUERY_VARIANTS]