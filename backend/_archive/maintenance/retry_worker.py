import time
from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.registry.models import Source
from backend.ingestion.ingest_manager import submit_ingestion


MAX_RETRIES = 3


def retry_failed_sources():

    db: Session = SessionLocal()

    try:
        sources = db.query(Source).filter(
            Source.status == "failed",
            Source.retry_count < MAX_RETRIES,
            Source.last_error_type == "network",
        ).all()

        for source in sources:
            submit_ingestion(source)
            time.sleep(0.5)  # basic rate limit

    finally:
        db.close()
