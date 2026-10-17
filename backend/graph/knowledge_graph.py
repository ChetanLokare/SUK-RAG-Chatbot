# backend/graph/knowledge_graph.py

"""
University Knowledge Graph

Lightweight graph storage using NetworkX.

Stores:
• departments
• faculty
• courses
• scholarships
• contacts
• relationships between them

Used for:
• graph-based retrieval boosting
• entity relationship queries
• structured knowledge extraction
"""

import pickle
import threading
from pathlib import Path
from typing import List, Tuple, Dict

import networkx as nx


# =========================================================
# GRAPH STORAGE PATH
# =========================================================

GRAPH_PATH = Path("data/knowledge_graph.pkl")


# =========================================================
# NORMALIZATION
# =========================================================

def _normalize_entity(name: str) -> str:

    if not name:
        return ""

    name = name.strip()

    # collapse whitespace
    name = " ".join(name.split())

    return name


# =========================================================
# UNIVERSITY GRAPH
# =========================================================

class UniversityGraph:

    def __init__(self):

        self.graph = nx.DiGraph()

        # thread safety for FastAPI workers
        self._lock = threading.Lock()

        self._load()

    # =====================================================
    # LOAD GRAPH
    # =====================================================

    def _load(self):

        try:

            if GRAPH_PATH.exists():

                with open(GRAPH_PATH, "rb") as f:

                    obj = pickle.load(f)

                    if isinstance(obj, nx.DiGraph):

                        self.graph = obj

        except Exception:

            # corrupted graph fallback
            self.graph = nx.DiGraph()

    # =====================================================
    # SAVE GRAPH
    # =====================================================

    def save(self):

        try:

            GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)

            with self._lock:

                with open(GRAPH_PATH, "wb") as f:

                    pickle.dump(self.graph, f)

        except Exception:
            pass

    # =====================================================
    # ADD ENTITY
    # =====================================================

    def add_entity(self, entity_type: str, name: str):

        name = _normalize_entity(name)

        if not name:
            return

        with self._lock:

            if name not in self.graph:

                self.graph.add_node(
                    name,
                    type=entity_type,
                )

            else:

                # update entity type if missing
                if "type" not in self.graph.nodes[name]:
                    self.graph.nodes[name]["type"] = entity_type

    # =====================================================
    # ADD RELATIONSHIP
    # =====================================================

    def add_relation(self, source: str, relation: str, target: str):

        source = _normalize_entity(source)
        target = _normalize_entity(target)

        if not source or not target or not relation:
            return

        with self._lock:

            if source not in self.graph:
                self.graph.add_node(source)

            if target not in self.graph:
                self.graph.add_node(target)

            # prevent duplicate edge conflicts
            if self.graph.has_edge(source, target):

                self.graph[source][target]["relation"] = relation

            else:

                self.graph.add_edge(
                    source,
                    target,
                    relation=relation
                )

    # =====================================================
    # FIND RELATED ENTITIES
    # =====================================================

    def find_related(self, entity: str) -> List[Tuple[str, str]]:

        entity = _normalize_entity(entity)

        if entity not in self.graph:
            return []

        related = []

        for neighbor in self.graph.successors(entity):

            relation = self.graph[entity][neighbor].get("relation", "")

            related.append((relation, neighbor))

        return related

    # =====================================================
    # REVERSE RELATIONSHIP
    # =====================================================

    def find_parents(self, entity: str) -> List[Tuple[str, str]]:

        entity = _normalize_entity(entity)

        if entity not in self.graph:
            return []

        parents = []

        for predecessor in self.graph.predecessors(entity):

            relation = self.graph[predecessor][entity].get("relation", "")

            parents.append((relation, predecessor))

        return parents

    # =====================================================
    # SEARCH ENTITY
    # =====================================================

    def search_entity(self, text: str) -> List[str]:

        text = text.lower()

        results = []

        for node in self.graph.nodes:

            if text in node.lower():

                results.append(node)

        return results

    # =====================================================
    # GRAPH STATISTICS
    # =====================================================

    def stats(self) -> Dict:

        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
        }

    # =====================================================
    # CLEAR GRAPH
    # =====================================================

    def clear(self):

        with self._lock:

            self.graph.clear()

        self.save()


# =========================================================
# GLOBAL GRAPH INSTANCE
# =========================================================

graph_instance = UniversityGraph()