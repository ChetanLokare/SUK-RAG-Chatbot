import zipfile
from pathlib import Path
from sqlalchemy.orm import Session

from backend.core.config import ZIP_DIR
from backend.core.file_hash import compute_file_hash

from backend.ingestion.ingest_pdf import ingest_pdf
from backend.ingestion.ingest_tabular import ingest_tabular

from backend.registry.repository import (
    create_source,
    mark_ingested,
)


# ==========================================================
# FILE TYPE DETECTION (CONTENT BASED)
# ==========================================================

def detect_file_type(file_path: Path):

    """
    Detect file type using magic bytes instead of extension
    """

    try:
        with open(file_path, "rb") as f:
            header = f.read(8)

        # -------------------------
        # PDF
        # -------------------------
        if header.startswith(b"%PDF"):
            return "pdf"

        # -------------------------
        # XLSX / XLS / CSV
        # Excel files are ZIP containers
        # -------------------------
        if header.startswith(b"PK"):
            return "tabular"

        # -------------------------
        # CSV / text fallback
        # -------------------------
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            sample = f.read(2048)

        if "," in sample or "|" in sample or "\t" in sample:
            return "tabular"

    except Exception:
        pass

    return None


# ==========================================================
# ZIP INGESTION
# ==========================================================

def ingest_zip(db: Session, source):

    """
    Production ZIP ingestion

    ✔ Safe extraction
    ✔ File type auto-detection
    ✔ Supports PDF + CSV + Excel
    ✔ Duplicate prevention via hash
    ✔ Full path preservation
    ✔ Child failures do not break ZIP
    """

    zip_path = Path(ZIP_DIR) / source.source_value

    if not zip_path.exists():
        raise Exception(f"ZIP not found: {zip_path}")

    # ------------------------------------------------------
    # Extract directory
    # ------------------------------------------------------

    extracted_dir = ZIP_DIR / f"{source.id}_extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extracted_dir)

    created = 0
    ingested = 0

    # ------------------------------------------------------
    # Walk extracted files
    # ------------------------------------------------------

    for file in extracted_dir.rglob("*"):

        if not file.is_file():
            continue

        # --------------------------------------------------
        # Detect file type using content
        # --------------------------------------------------

        detected_type = detect_file_type(file)

        if detected_type not in ["pdf", "tabular"]:
            continue

        # --------------------------------------------------
        # Compute file hash
        # --------------------------------------------------

        try:
            file_hash = compute_file_hash(file)
        except Exception:
            continue

        # --------------------------------------------------
        # Create child source
        # --------------------------------------------------

        try:
            child = create_source(
                db=db,
                source_type=detected_type,
                source_value=str(file.resolve()),
                origin="discovered",
                parent_id=source.id,
                category=source.category,
                file_name=file.name,
                file_hash=file_hash,
            )
        except Exception:
            continue

        if not child:
            continue

        created += 1

        # --------------------------------------------------
        # Ingest child
        # --------------------------------------------------

        try:

            if detected_type == "pdf":
                ingest_pdf(db, child)

            else:
                ingest_tabular(db, child)

            ingested += 1

        except Exception:
            # Child ingestion must never break ZIP
            continue

    # ------------------------------------------------------
    # Mark parent ZIP ingested
    # ------------------------------------------------------

    mark_ingested(db, source.id)

    return {
        "zip": source.source_value,
        "extracted_to": str(extracted_dir),
        "files_created": created,
        "files_ingested": ingested,
    }