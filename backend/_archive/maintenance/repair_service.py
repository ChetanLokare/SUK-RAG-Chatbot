from pathlib import Path
from sqlalchemy.orm import Session

from backend.core.config import PDF_DIR
from backend.core.hybrid_fetch import hybrid_fetch
from backend.core.file_utils import compute_file_hash
from backend.registry.models import Source
from backend.registry.repository import mark_failed


def repair_missing_files(db: Session):

    repaired = []
    failed = []

    pdf_sources = db.query(Source).filter(
        Source.source_type == "pdf"
    ).all()

    for source in pdf_sources:

        pdf_path = PDF_DIR / f"{source.id}.pdf"

        if pdf_path.exists():
            continue

        # If we don't have URL, can't repair
        if not source.source_value.startswith("http"):
            failed.append(source.id)
            continue

        try:
            response = hybrid_fetch(source.source_value)

            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            with open(pdf_path, "wb") as f:
                f.write(response.content)

            source.file_hash = compute_file_hash(pdf_path)
            db.commit()

            repaired.append(source.id)

        except Exception:
            failed.append(source.id)
            mark_failed(db, source.id, "repair_failed")

    return {
        "repaired": repaired,
        "failed": failed,
    }
