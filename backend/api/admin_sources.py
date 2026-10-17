# backend/api/admin_sources.py

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone, timedelta

from backend.core.database import get_db
from backend.auth.deps import require_admin

from backend.registry.repository import (
    get_all_sources,
    get_source_by_id,
    update_source_category,
    bulk_update_status,
    delete_sources,
    mark_failed,
    mark_ingested,
    search_sources,
)

from backend.ingestion.ingest_url import ingest_url
from backend.ingestion.ingest_pdf import ingest_pdf
from backend.ingestion.ingest_tabular import ingest_tabular
from backend.ingestion.ingest_zip import ingest_zip

from backend.registry.schemas import SourceResponse
from backend.registry.models import Source


router = APIRouter(prefix="/admin/sources", tags=["Admin Sources"], dependencies=[Depends(require_admin)])


# ============================================================
# SCHEMAS
# ============================================================

class CategoryUpdateRequest(BaseModel):
    category: str


class BulkIdsRequest(BaseModel):
    source_ids: List[str]
    force: bool = False


class BulkCategoryUpdateRequest(BaseModel):
    source_ids: List[str]
    category: str


class RefreshConfigRequest(BaseModel):
    refresh_interval_hours: int
    priority: Optional[str] = "normal"


# ============================================================
# INGEST ROUTER
# ============================================================

def _run_ingestion(db: Session, source: Source):

    stype = (source.source_type or "").lower()

    if stype == "url":
        return ingest_url(db, source)

    if stype == "pdf":
        return ingest_pdf(db, source)

    if stype == "zip":
        return ingest_zip(db, source)

    if stype in {"csv", "excel", "xlsx", "xls"}:
        return ingest_tabular(db, source)

    raise Exception(f"Unsupported type: {stype}")


# ============================================================
# SEARCH
# ============================================================

@router.get("/search")
def search_sources_api(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
):
    return search_sources(db, q)


# ============================================================
# BULK STATUS OPERATIONS
# ============================================================

@router.post("/bulk/approve")
def bulk_approve(payload: BulkIdsRequest, db: Session = Depends(get_db)):
    count = bulk_update_status(db, payload.source_ids, "approved")
    return {"approved": count}


@router.post("/bulk/disable")
def bulk_disable(payload: BulkIdsRequest, db: Session = Depends(get_db)):
    count = bulk_update_status(db, payload.source_ids, "disabled")
    return {"disabled": count}


@router.post("/bulk/delete")
def bulk_delete(payload: BulkIdsRequest, db: Session = Depends(get_db)):
    deleted = delete_sources(db, payload.source_ids)
    return {"deleted": deleted}


@router.post("/bulk/category")
def bulk_category_update(
    payload: BulkCategoryUpdateRequest,
    db: Session = Depends(get_db),
):
    updated = 0

    for sid in payload.source_ids:

        if update_source_category(db, sid, payload.category):
            updated += 1

    return {"updated": updated}


# ============================================================
# BULK INGEST
# ============================================================

@router.post("/bulk/ingest")
def bulk_ingest(payload: BulkIdsRequest, db: Session = Depends(get_db)):
    report = {
        "requested": len(payload.source_ids),
        "ingested": 0,
        "failed": [],
        "skipped": [],
        "missing": [],
    }

    for source_id in payload.source_ids:

        source = get_source_by_id(db, source_id)

        if not source:
            report["missing"].append(source_id)
            continue

        if not payload.force and source.status not in ("approved", "failed"):
            report["skipped"].append(
                {"id": source_id, "reason": f"status={source.status}"}
            )
            continue

        try:

            result = _run_ingestion(db, source)

            if result is None:
                raise Exception("Ingestion returned None")

            mark_ingested(db, source_id)

            report["ingested"] += 1

        except Exception as e:

            mark_failed(db, source_id, str(e))

            report["failed"].append(
                {"id": source_id, "error": str(e)}
            )

    return report


# ============================================================
# LIST SOURCES
# ============================================================

@router.get("/", response_model=List[SourceResponse])
def list_sources(
    category: Optional[str] = None,
    source_type: Optional[str] = Query(None, alias="type"),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return get_all_sources(db, category, source_type, status)


@router.get("/ids")
def list_source_ids(
    category: Optional[str] = None,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    sources = get_all_sources(db, category, source_type, status)

    return {"source_ids": sorted({s.id for s in sources})}


# ============================================================
# SOURCES DUE FOR RE-INGEST
# ============================================================

@router.get("/due")
def sources_due_for_refresh(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)

    sources = (
        db.query(Source)
        .filter(
            Source.next_reingest_at.isnot(None),
            Source.next_reingest_at <= now,
            Source.status == "ingested",
        )
        .order_by(Source.priority.desc(), Source.next_reingest_at.asc())
        .all()
    )

    return {
        "due_count": len(sources),
        "source_ids": [s.id for s in sources],
    }


# ============================================================
# CONFIGURE REFRESH POLICY
# ============================================================

@router.post("/{source_id}/refresh-config")
def configure_refresh(
    source_id: str,
    payload: RefreshConfigRequest,
    db: Session = Depends(get_db),
):
    source = get_source_by_id(db, source_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source.refresh_interval_hours = payload.refresh_interval_hours
    source.priority = payload.priority

    if payload.refresh_interval_hours > 0:

        source.next_reingest_at = (
            datetime.now(timezone.utc)
            + timedelta(hours=payload.refresh_interval_hours)
        )

    else:
        source.next_reingest_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "status": "updated",
        "refresh_interval_hours": source.refresh_interval_hours,
        "priority": source.priority,
    }


# ============================================================
# EXPORT SOURCES
# ============================================================

@router.get("/export/json")
def export_json(db: Session = Depends(get_db)):
    sources = get_all_sources(db)

    return JSONResponse(
        content={
            "sources": [
                {
                    "id": s.id,
                    "type": s.source_type,
                    "value": s.source_value,
                    "status": s.status,
                    "category": s.category,
                    "priority": s.priority,
                    "next_reingest_at": (
                        s.next_reingest_at.isoformat()
                        if s.next_reingest_at
                        else None
                    ),
                }
                for s in sources
            ]
        },
        headers={
            "Content-Disposition": "attachment; filename=sources.json"
        },
    )


@router.get("/export/txt")
def export_txt(db: Session = Depends(get_db)):
    sources = get_all_sources(db)

    lines = [
        f"{s.id} | {s.source_type} | {s.source_value}"
        for s in sources
    ]

    return PlainTextResponse(
        "\n".join(lines),
        headers={
            "Content-Disposition": "attachment; filename=sources.txt"
        },
    )


# ============================================================
# VIEW SOURCE
# ============================================================

@router.get("/view/{source_id}")
def view_source(source_id: str, db: Session = Depends(get_db)):
    source = get_source_by_id(db, source_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    info = {
        "id": source.id,
        "type": source.source_type,
        "value": source.source_value,
        "status": source.status,
        "category": source.category,
        "priority": source.priority,
        "refresh_interval_hours": source.refresh_interval_hours,
        "next_reingest_at": source.next_reingest_at,
        "language": source.language,
        "error": source.error_message,
    }

    try:
        path = Path(source.source_value)

        if path.exists():
            info["file_exists"] = True
            info["file_size"] = path.stat().st_size
        else:
            info["file_exists"] = False

    except Exception:
        info["file_exists"] = False

    return info


# ============================================================
# SINGLE INGEST
# ============================================================

@router.post("/{source_id}/ingest")
def ingest_single(
    source_id: str,
    force: bool = False,
    db: Session = Depends(get_db),
):
    source = get_source_by_id(db, source_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if not force and source.status not in ("approved", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Status {source.status} cannot be ingested",
        )

    try:

        result = _run_ingestion(db, source)

        if result is None:
            raise Exception("Ingestion returned None")

        mark_ingested(db, source_id)

        return {
            "status": "ingested",
            "result": result,
        }

    except Exception as e:

        mark_failed(db, source_id, str(e))

        raise HTTPException(status_code=500, detail=str(e))