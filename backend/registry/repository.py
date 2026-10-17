# backend/registry/repository.py

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.registry.models import Source
from backend.core.chroma_client import delete_vectors_by_source_id


# ============================================================
# TIME UTILITY
# ============================================================

def utc_now():
    return datetime.now(timezone.utc)


# ============================================================
# CREATE SOURCE
# ============================================================

def create_source(
    db: Session,
    source_type: str,
    source_value: str,
    category: str | None = None,
    origin: str = "manual",
    parent_id: str | None = None,
):
    """
    Source creation logic.

    ✔ URL dedup by exact string
    ✔ File dedup by (type + value)
    ✔ Supports origin tracking
    ✔ Supports parent crawler tracking
    ✔ No file hash here (handled in ingestion)
    ✔ Default status = pending
    """

    source_type = source_type.strip().lower()
    source_value = source_value.strip()

    # =========================================================
    # URL SOURCE
    # =========================================================

    if source_type == "url":

        existing = db.query(Source).filter(
            Source.source_type == "url",
            Source.source_value == source_value,
        ).first()

        if existing:
            return existing

        source = Source(
            source_type="url",
            source_value=source_value,
            category=category,
            origin=origin,
            parent_id=parent_id,
            status="pending",
            created_at=utc_now(),
        )

        db.add(source)
        db.commit()
        db.refresh(source)
        return source

    # =========================================================
    # FILE SOURCES (csv / excel / pdf / zip)
    # =========================================================

    existing = db.query(Source).filter(
        Source.source_type == source_type,
        Source.source_value == source_value,
    ).first()

    if existing:
        return existing

    source = Source(
        source_type=source_type,
        source_value=source_value,
        category=category,
        origin=origin,
        parent_id=parent_id,
        status="pending",
        created_at=utc_now(),
    )

    db.add(source)
    db.commit()
    db.refresh(source)
    return source


# ============================================================
# READ
# ============================================================

def get_source_by_id(db: Session, source_id: str):
    return db.query(Source).filter(Source.id == source_id).first()


def get_all_sources(
    db: Session,
    category: str | None = None,
    source_type: str | None = None,
    status: str | None = None,
):
    query = db.query(Source)

    if category:
        query = query.filter(Source.category == category)

    if source_type:
        query = query.filter(Source.source_type == source_type)

    if status:
        query = query.filter(Source.status == status)

    return query.order_by(Source.created_at.desc()).all()


# ============================================================
# STATUS MANAGEMENT
# ============================================================

def mark_ingested(db: Session, source_id: str):

    source = get_source_by_id(db, source_id)
    if not source:
        return None

    source.status = "ingested"
    source.error_message = None
    source.last_ingested_at = utc_now()

    db.commit()
    db.refresh(source)
    return source


def mark_failed(db: Session, source_id: str, error_message: str):

    source = get_source_by_id(db, source_id)
    if not source:
        return None

    source.status = "failed"
    source.error_message = (error_message or "")[:2000]

    db.commit()
    db.refresh(source)
    return source


# ============================================================
# UPDATE CATEGORY
# ============================================================

def update_source_category(db: Session, source_id: str, category: str):

    source = get_source_by_id(db, source_id)
    if not source:
        return None

    source.category = category

    db.commit()
    db.refresh(source)
    return source


# ============================================================
# BULK STATUS UPDATE
# ============================================================

def bulk_update_status(db: Session, source_ids: list[str], status: str):

    updated = 0

    for source_id in source_ids:
        source = get_source_by_id(db, source_id)
        if not source:
            continue

        source.status = status
        updated += 1

    db.commit()
    return updated


# ============================================================
# SEARCH
# ============================================================

def search_sources(db: Session, query: str):

    query = f"%{query.strip()}%"

    return db.query(Source).filter(
        or_(
            Source.source_value.ilike(query),
            Source.category.ilike(query),
            Source.id.ilike(query),
        )
    ).order_by(Source.created_at.desc()).all()


# ============================================================
# DELETE SOURCE
# ============================================================

def delete_sources(db: Session, source_ids: list[str]):
    """
    Safe delete:
    ✔ Remove vectors from Chroma
    ✔ Remove DB record
    ✔ Never crash deletion
    """

    deleted_count = 0

    for source_id in source_ids:

        source = get_source_by_id(db, source_id)
        if not source:
            continue

        # Remove vectors first
        try:
            delete_vectors_by_source_id(source.id)
        except Exception:
            pass

        db.delete(source)
        deleted_count += 1

    db.commit()
    return deleted_count


# ============================================================
# URL CONTENT CHANGE CHECK
# ============================================================

def update_url_hash(db: Session, source_id: str, new_hash: str):
    """
    Used by URL ingestion.
    Returns True if content changed.
    Returns False if unchanged.
    """

    source = get_source_by_id(db, source_id)
    if not source:
        return False

    if source.content_hash == new_hash:
        return False

    source.content_hash = new_hash
    db.commit()

    return True
