# backend/core/chroma_client.py

from pathlib import Path
from typing import Dict, Any

import torch
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from backend.core.config import CHROMA_DIR


# ============================================================
# GLOBAL SINGLETONS
# ============================================================

_client = None
_collection_cache: Dict[str, Any] = {}
_embedding_function = None


# ============================================================
# DEVICE DETECTION
# ============================================================

def _get_device() -> str:
    """
    Auto detect best device.
    Supports CUDA if available.
    """

    try:
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass

    return "cpu"


# ============================================================
# EMBEDDING FUNCTION
# ============================================================

def _get_embedding_function():
    """
    Multilingual SentenceTransformer embeddings.

    ✔ Marathi
    ✔ Hindi
    ✔ English
    ✔ GPU enabled
    ✔ Singleton
    ✔ Cosine normalized
    """

    global _embedding_function

    if _embedding_function is not None:
        return _embedding_function

    device = _get_device()

    _embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        device=device,
        normalize_embeddings=True,
    )

    return _embedding_function


# ============================================================
# CHROMA CLIENT
# ============================================================

def get_chroma_client():
    """
    Returns persistent Chroma client.
    """

    global _client

    if _client is not None:
        return _client

    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)

    _client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True,
        ),
    )

    return _client


# ============================================================
# COLLECTION ACCESS
# ============================================================

def get_collection(name: str = "suk_rag"):
    """
    Returns persistent collection.

    ✔ cached
    ✔ multilingual embeddings
    ✔ cosine similarity
    ✔ corruption recovery
    """

    global _collection_cache

    if name in _collection_cache:
        return _collection_cache[name]

    client = get_chroma_client()
    embedding_function = _get_embedding_function()

    try:

        collection = client.get_or_create_collection(
            name=name,
            embedding_function=embedding_function,
            metadata={
                "hnsw:space": "cosine"
            },
        )

    except Exception:

        # Attempt recovery
        try:
            client.delete_collection(name)
        except Exception:
            pass

        collection = client.get_or_create_collection(
            name=name,
            embedding_function=embedding_function,
            metadata={
                "hnsw:space": "cosine"
            },
        )

    _collection_cache[name] = collection

    return collection


# ============================================================
# DELETE VECTORS
# ============================================================

def delete_vectors_by_source_id(source_id: str, name: str = "suk_rag"):
    """
    Delete vectors belonging to source.
    """

    try:

        collection = get_collection(name)

        collection.delete(
            where={"source_id": source_id}
        )

    except Exception:
        pass


# ============================================================
# VECTOR DATABASE STATS
# ============================================================

def get_vector_stats(name: str = "suk_rag"):
    """
    Return vector DB statistics.
    """

    try:

        collection = get_collection(name)

        return {
            "collection": collection.name,
            "documents": collection.count(),
            "device": _get_device(),
        }

    except Exception:

        return {
            "collection": name,
            "documents": 0,
            "device": _get_device(),
        }


# ============================================================
# DELETE VECTOR DB
# ============================================================

def delete_vector_db(name: str = "suk_rag"):
    """
    Delete entire vector collection.
    """

    global _collection_cache
    global _embedding_function

    client = get_chroma_client()

    try:
        client.delete_collection(name)
    except Exception:
        pass

    if name in _collection_cache:
        del _collection_cache[name]

    # reset embedding model
    _embedding_function = None

    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


# ============================================================
# HARD RESET (DEV ONLY)
# ============================================================

def hard_reset():
    """
    Reset full Chroma client state.
    """

    global _client
    global _collection_cache
    global _embedding_function

    try:
        if _client:
            _client.reset()
    except Exception:
        pass

    _client = None
    _collection_cache = {}
    _embedding_function = None

    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass