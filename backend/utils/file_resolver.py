"""
File Resolver Utility

Purpose
-------
Resolves citation filenames to the actual file
stored on disk.

Handles cases where files are stored as:

    <uuid>_filename.pdf

but citations reference:

    filename.pdf

Search locations include:

• data/pdfs
• data/csvs
• data/excels
• storage/sources/pdf
• storage/sources/csv
• storage/sources/zip
"""

from pathlib import Path
from typing import Optional

from backend.core.config import (
    PDF_DIR,
    CSV_DIR,
    EXCEL_DIR,
)

# optional directories (exist in many builds)
BASE_DIR = Path(__file__).resolve().parents[2]

STORAGE_PDF = BASE_DIR / "backend" / "storage" / "sources" / "pdf"
STORAGE_CSV = BASE_DIR / "backend" / "storage" / "sources" / "csv"
STORAGE_ZIP = BASE_DIR / "backend" / "storage" / "sources" / "zip"


# ============================================================
# SEARCH DIRECTORIES
# ============================================================

SEARCH_DIRECTORIES = [
    PDF_DIR,
    CSV_DIR,
    EXCEL_DIR,
    STORAGE_PDF,
    STORAGE_CSV,
    STORAGE_ZIP,
]


# ============================================================
# SAFE FILE MATCH
# ============================================================

def _matches_filename(stored_name: str, requested_name: str) -> bool:
    """
    Handles UUID prefix case.

    Example:
        stored:  cc086d52-file.pdf
        request: file.pdf
    """

    stored_name = stored_name.lower()
    requested_name = requested_name.lower()

    if stored_name == requested_name:
        return True

    # handle uuid_filename.ext
    if "_" in stored_name:
        possible = stored_name.split("_", 1)[1]
        if possible == requested_name:
            return True

    return False


# ============================================================
# MAIN RESOLVER
# ============================================================

def resolve_file_path(source_value: str) -> Optional[Path]:
    """
    Resolve a citation source_value to a real file path.

    Supports:

    • full path
    • filename
    • uuid_filename
    """

    if not source_value:
        return None

    # if already absolute path
    p = Path(source_value)

    if p.exists():
        return p

    filename = p.name

    # search directories
    for directory in SEARCH_DIRECTORIES:

        if not directory or not directory.exists():
            continue

        # direct match
        direct = directory / filename
        if direct.exists():
            return direct

        # scan directory
        try:
            for file in directory.iterdir():

                if not file.is_file():
                    continue

                if _matches_filename(file.name, filename):
                    return file

        except Exception:
            continue

    return None


# ============================================================
# FILE EXISTS CHECK
# ============================================================

def file_exists(source_value: str) -> bool:

    return resolve_file_path(source_value) is not None


# ============================================================
# DEBUG TOOL
# ============================================================

def debug_resolve(source_value: str) -> dict:
    """
    Helpful debug output for resolving issues.
    """

    path = resolve_file_path(source_value)

    return {
        "requested": source_value,
        "resolved_path": str(path) if path else None,
        "exists": bool(path),
    }