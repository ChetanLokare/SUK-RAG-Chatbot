from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
import hashlib
from urllib.parse import urlparse
import re

from backend.core.database import get_db
from backend.auth.deps import require_admin
from backend.core.config import CSV_DIR, PDF_DIR, ZIP_DIR
from backend.registry.repository import create_source
from backend.registry.models import Source

from pydantic import BaseModel, HttpUrl

router = APIRouter(prefix="/admin/upload", tags=["Admin Uploads"], dependencies=[Depends(require_admin)])


# ============================================================
# UTILITIES
# ============================================================

def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _compute_file_hash(path: Path) -> str:
    sha = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)

    return sha.hexdigest()


def _safe_filename(filename: str) -> str:
    """
    Normalize filenames for safe filesystem usage.
    """

    name = filename.strip()

    name = name.replace(" ", "_")
    name = name.replace("/", "_")
    name = name.replace("\\", "_")

    name = re.sub(r"[^a-zA-Z0-9_\-.]", "", name)

    return name


def _resolve_duplicate_filename(directory: Path, filename: str) -> str:
    """
    Resolve duplicate filenames.

    Example:
        data.csv
        data_1.csv
        data_2.csv
    """

    path = directory / filename

    if not path.exists():
        return filename

    stem = path.stem
    suffix = path.suffix

    counter = 1

    while True:

        candidate = f"{stem}_{counter}{suffix}"

        if not (directory / candidate).exists():
            return candidate

        counter += 1


# ============================================================
# URL UPLOAD
# ============================================================

class UrlUploadRequest(BaseModel):
    url: HttpUrl
    category: str | None = None


@router.post("/url")
def upload_url(payload: UrlUploadRequest, db: Session = Depends(get_db)):

    url_str = str(payload.url)

    parsed = urlparse(url_str)

    source = create_source(
        db=db,
        source_type="url",
        source_value=url_str,
        category=payload.category,
        origin="manual",
    )

    return {
        "status": "registered",
        "source_id": source.id,
        "domain": parsed.netloc,
    }


# ============================================================
# CSV UPLOAD
# ============================================================

@router.post("/csv")
def upload_csv(
    file: UploadFile = File(...),
    category: str | None = Form(None),
    db: Session = Depends(get_db),
):

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    _ensure_dir(CSV_DIR)

    safe_name = _safe_filename(file.filename)

    safe_name = _resolve_duplicate_filename(CSV_DIR, safe_name)

    target_path = CSV_DIR / safe_name

    try:

        with open(target_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    finally:
        file.file.close()

    file_hash = _compute_file_hash(target_path)

    existing = db.query(Source).filter(Source.file_hash == file_hash).first()

    if existing:

        target_path.unlink(missing_ok=True)

        return {
            "status": "duplicate",
            "existing_source_id": existing.id,
        }

    source = create_source(
        db=db,
        source_type="csv",
        source_value=safe_name,
        category=category,
        origin="manual",
    )

    source.file_hash = file_hash

    db.commit()
    db.refresh(source)

    return {
        "status": "uploaded",
        "file": safe_name,
        "source_id": source.id,
    }


# ============================================================
# EXCEL UPLOAD
# ============================================================

@router.post("/excel")
def upload_excel(
    file: UploadFile = File(...),
    category: str | None = Form(None),
    db: Session = Depends(get_db),
):

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing")

    allowed = (".xlsx", ".xls")

    if not file.filename.lower().endswith(allowed):
        raise HTTPException(
            status_code=400,
            detail="Only Excel files (.xlsx, .xls) allowed"
        )

    _ensure_dir(CSV_DIR)

    safe_name = _safe_filename(file.filename)

    safe_name = _resolve_duplicate_filename(CSV_DIR, safe_name)

    target_path = CSV_DIR / safe_name

    try:

        with open(target_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    finally:
        file.file.close()

    file_hash = _compute_file_hash(target_path)

    existing = db.query(Source).filter(Source.file_hash == file_hash).first()

    if existing:

        target_path.unlink(missing_ok=True)

        return {
            "status": "duplicate",
            "existing_source_id": existing.id,
        }

    source = create_source(
        db=db,
        source_type="excel",
        source_value=safe_name,
        category=category,
        origin="manual",
    )

    source.file_hash = file_hash

    db.commit()
    db.refresh(source)

    return {
        "status": "uploaded",
        "file": safe_name,
        "source_id": source.id,
    }


# ============================================================
# PDF UPLOAD
# ============================================================

@router.post("/pdf")
def upload_pdf(
    file: UploadFile = File(...),
    category: str | None = Form(None),
    db: Session = Depends(get_db),
):

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    _ensure_dir(PDF_DIR)

    safe_name = _safe_filename(file.filename)

    safe_name = _resolve_duplicate_filename(PDF_DIR, safe_name)

    target_path = PDF_DIR / safe_name

    try:

        with open(target_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    finally:
        file.file.close()

    file_hash = _compute_file_hash(target_path)

    existing = db.query(Source).filter(Source.file_hash == file_hash).first()

    if existing:

        target_path.unlink(missing_ok=True)

        return {
            "status": "duplicate",
            "existing_source_id": existing.id,
        }

    source = create_source(
        db=db,
        source_type="pdf",
        source_value=safe_name,
        category=category,
        origin="manual",
    )

    source.file_hash = file_hash

    db.commit()
    db.refresh(source)

    return {
        "status": "uploaded",
        "file": safe_name,
        "source_id": source.id,
    }


# ============================================================
# ZIP UPLOAD
# ============================================================

@router.post("/zip")
def upload_zip(
    file: UploadFile = File(...),
    category: str | None = Form(None),
    db: Session = Depends(get_db),
):

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing")

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files allowed")

    _ensure_dir(ZIP_DIR)

    safe_name = _safe_filename(file.filename)

    safe_name = _resolve_duplicate_filename(ZIP_DIR, safe_name)

    target_path = ZIP_DIR / safe_name

    try:

        with open(target_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    finally:
        file.file.close()

    file_hash = _compute_file_hash(target_path)

    existing = db.query(Source).filter(Source.file_hash == file_hash).first()

    if existing:

        target_path.unlink(missing_ok=True)

        return {
            "status": "duplicate",
            "existing_source_id": existing.id,
        }

    source = create_source(
        db=db,
        source_type="zip",
        source_value=safe_name,
        category=category,
        origin="manual",
    )

    source.file_hash = file_hash

    db.commit()
    db.refresh(source)

    return {
        "status": "uploaded",
        "file": safe_name,
        "source_id": source.id,
    }