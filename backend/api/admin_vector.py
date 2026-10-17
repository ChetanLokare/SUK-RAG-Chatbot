# backend/api/admin_vector.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth.deps import require_admin
from backend.core.database import get_db
from backend.core.chroma_client import (
    get_vector_stats,
    delete_vector_db,
    get_collection,
)
from backend.registry.repository import get_all_sources
from backend.ingestion.ingest_url import ingest_url
from backend.ingestion.ingest_pdf import ingest_pdf


router = APIRouter(
    prefix="/admin/vector",
    tags=["Admin Vector DB"],
    dependencies=[Depends(require_admin)],
)


# =========================================================
# VECTOR STATS
# =========================================================

@router.get("/stats")
def vector_stats():
    """
    Returns vector collection stats.
    """
    try:
        return get_vector_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# DELETE VECTOR DB
# =========================================================

@router.delete("/delete")
def delete_vector():
    """
    Completely deletes vector collection.
    """
    try:
        delete_vector_db()
        return {
            "status": "deleted",
            "message": "Vector database deleted",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# REBUILD VECTOR DB
# =========================================================

@router.post("/rebuild")
def rebuild_vector_db(
    db: Session = Depends(get_db),
):
    """
    Rebuild vector DB from Source Registry.

    ⚠️ Important:
    - Deletes entire vector DB
    - Re-indexes all APPROVED or INGESTED sources
    """

    # -----------------------------------------------------
    # 1️⃣ Delete vector DB
    # -----------------------------------------------------

    try:
        delete_vector_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")

    # Force recreation
    try:
        collection = get_collection()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recreate failed: {e}")

    if collection is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to recreate vector collection",
        )

    # -----------------------------------------------------
    # 2️⃣ Fetch eligible sources
    # -----------------------------------------------------

    sources = get_all_sources(db)

    rebuilt = 0
    failed = 0
    skipped = 0

    for source in sources:

        # Only rebuild URL + PDF
        if source.source_type not in ["url", "pdf"]:
            skipped += 1
            continue

        # Only rebuild previously valid ones
        if source.status not in ["ingested", "approved"]:
            skipped += 1
            continue

        try:
            if source.source_type == "url":
                result = ingest_url(db, source)

            elif source.source_type == "pdf":
                result = ingest_pdf(db, source)

            # Hard check
            if result is None:
                failed += 1
                continue

            rebuilt += 1

        except Exception:
            failed += 1

    # -----------------------------------------------------
    # 3️⃣ Final stats
    # -----------------------------------------------------

    final_stats = get_vector_stats()

    return {
        "status": "rebuilt",
        "sources_reindexed": rebuilt,
        "failed": failed,
        "skipped": skipped,
        "final_vector_count": final_stats.get("documents", 0),
    }
