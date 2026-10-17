"""
Graph-aware query expansion (NetworkX ONLY - PRODUCTION VERSION)

Uses in-memory knowledge graph to expand queries.

Features:
• fast entity matching
• multi-hop expansion
• safe graph access
• no Neo4j dependency
"""

import re
from typing import List, Set

from backend.graph.knowledge_graph import graph_instance


# ============================================================
# CONFIG
# ============================================================

MAX_GRAPH_EXPANSIONS = 10
MAX_GRAPH_HOPS = 2
MAX_ENTITY_MATCH = 5


# ============================================================
# NORMALIZE
# ============================================================

def _normalize(text: str) -> str:

    if not text:
        return ""

    text = text.lower().strip()
    return re.sub(r"\s+", " ", text)


# ============================================================
# TOKENIZE
# ============================================================

def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


# ============================================================
# MATCH ENTITIES (OPTIMIZED)
# ============================================================

def _match_entities(query: str) -> List[str]:
    """
    Find relevant graph nodes inside query.

    Optimized:
    • avoids full expensive matching
    • limits matches
    """

    matches = []

    try:

        q = _normalize(query)

        for node in graph_instance.graph.nodes:

            node_norm = _normalize(node)

            # strict but flexible match
            if node_norm in q or q in node_norm:
                matches.append(node)

                if len(matches) >= MAX_ENTITY_MATCH:
                    break

    except Exception:
        pass

    return matches


# ============================================================
# NETWORKX EXPANSION
# ============================================================

def _expand_networkx(entity: str) -> Set[str]:

    expansions: Set[str] = set()

    try:

        related = graph_instance.find_related(entity)

        for _, target in related:

            if target:
                expansions.add(target)

    except Exception:
        pass

    return expansions


# ============================================================
# MULTI-HOP EXPANSION
# ============================================================

def _multi_hop_expand(entity: str) -> Set[str]:

    expansions: Set[str] = set()

    frontier = {entity}
    visited = {entity}

    for _ in range(MAX_GRAPH_HOPS):

        new_frontier = set()

        for node in frontier:

            neighbors = _expand_networkx(node)

            for n in neighbors:

                if n not in visited:
                    visited.add(n)
                    new_frontier.add(n)
                    expansions.add(n)

        frontier = new_frontier

        if not frontier:
            break

    return expansions


# ============================================================
# EXPAND QUERY
# ============================================================

def expand_query_with_graph(query: str) -> List[str]:
    """
    Expand query using knowledge graph.
    """

    if not query:
        return [query]

    base = _normalize(query)

    expansions: Set[str] = {base}

    matched_entities = _match_entities(query)

    for entity in matched_entities:

        expansions.update(_expand_networkx(entity))
        expansions.update(_multi_hop_expand(entity))

    # --------------------------------------------------------
    # CLEAN + DEDUP
    # --------------------------------------------------------

    normalized = []
    seen = set()

    for e in expansions:

        e = _normalize(e)

        if not e or e in seen:
            continue

        seen.add(e)
        normalized.append(e)

    return normalized[:MAX_GRAPH_EXPANSIONS]


# ============================================================
# BUILD FINAL QUERIES
# ============================================================

def build_graph_queries(query: str) -> List[str]:
    """
    Build enriched queries using graph expansions.

    Output example:
    [
        "computer science",
        "bsc computer science",
        "msc computer science",
        "computer science courses bsc computer science"
    ]
    """

    if not query:
        return []

    base = _normalize(query)

    graph_expansions = expand_query_with_graph(query)

    queries = {base}

    for g in graph_expansions:

        queries.add(g)

        # combined query (important for retrieval)
        if g != base:
            queries.add(f"{base} {g}")

    return list(queries)