# backend/api/faq.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.auth.deps import require_admin
from backend.core.database import get_db
from backend.registry.models import FAQ, Source


router = APIRouter(
    prefix="/faq",
    tags=["FAQ"],
)


# ============================================================
# GET FAQs BY SOURCE
# ============================================================

@router.get("/{source_id}")
def get_faqs_by_source(
    source_id: str,
    db: Session = Depends(get_db),
):
    """
    Returns FAQs generated for a specific source.
    """

    # Validate source exists
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    faqs = (
        db.query(FAQ)
        .filter(FAQ.source_id == source_id)
        .order_by(FAQ.created_at.desc())
        .all()
    )

    return {
        "source_id": source_id,
        "total": len(faqs),
        "faqs": [
            {
                "id": faq.id,
                "question": faq.question,
                "answer": faq.answer,
                "created_at": faq.created_at,
            }
            for faq in faqs
        ],
    }


# ============================================================
# GET ALL FAQs (OPTIONAL FILTERING)
# ============================================================

@router.get("/")
def get_all_faqs(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Returns all FAQs.
    Optional filtering by category.
    """

    query = db.query(FAQ)

    if category:
        query = query.join(Source).filter(Source.category == category)

    faqs = (
        query.order_by(FAQ.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "total": len(faqs),
        "faqs": [
            {
                "id": faq.id,
                "source_id": faq.source_id,
                "question": faq.question,
                "answer": faq.answer,
                "created_at": faq.created_at,
            }
            for faq in faqs
        ],
    }


# ============================================================
# DELETE FAQs FOR A SOURCE (ADMIN USE)
# ============================================================

@router.delete("/{source_id}", dependencies=[Depends(require_admin)])
def delete_faqs_for_source(
    source_id: str,
    db: Session = Depends(get_db),
):
    """
    Deletes all FAQs linked to a source. ADMIN ONLY.
    Useful when regenerating FAQs.
    """

    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    deleted = (
        db.query(FAQ)
        .filter(FAQ.source_id == source_id)
        .delete()
    )

    db.commit()

    return {
        "source_id": source_id,
        "deleted_faqs": deleted,
    }
