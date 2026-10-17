# _archive

Code that is **not imported by the running app**. It was moved here (not deleted)
during cleanup because it duplicates something that is now the single source of truth:

| Archived | Replaced by |
|---|---|
| `core/llm_router.py` | `services/llm_service.py` (same OpenAI -> Gemini fallback) |
| `api/chat.py` | `/query` in `api/query.py` (now also handles follow-ups via `history`) |
| `nlp/*` | `search/hybrid_search.py` + `utils/query_normalize.py` |
| `retrieval/{retriever,query_engine,ranker,reranker,hybrid_ranker,context_builder,...}` | `search/hybrid_search.py`, `retrieval/context_compressor.py`, `retrieval/temporal_ranker.py` |
| `search/{query_expander,query_intent,query_router}` | `retrieval/adaptive_topk.py`, `utils/query_normalize.py` |
| `maintenance/{repair_service,retry_worker}.py` | nothing: both were broken (imported `core.file_utils` / `ingestion.ingest_manager`, which never existed, and used `Source.retry_count` / `last_error_type`, which are not in the model) |
| `tasks.py` | nothing (it was an empty Celery stub) |

Files here import each other with `backend.<package>.<module>` paths, so they will not
run from this folder as-is. To revive one, move it back to its original location.
Safe to delete the whole folder once you are sure you do not need it.
