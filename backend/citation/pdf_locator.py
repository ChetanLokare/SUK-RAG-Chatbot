"""
Citation File Locator

Purpose
-------
Resolve citation sources into actual filesystem paths
or URLs that can be opened by the viewer.

Supports
--------
• PDF files
• CSV files
• Excel files
• URLs

Used by
-------
- pdf_viewer API
- citation renderer
- admin preview tools
"""

from pathlib import Path
from urllib.parse import urlparse, unquote
from typing import Optional, Tuple

from backend.core.config import PDF_DIR, CSV_DIR, EXCEL_DIR


# ============================================================
# HELPERS
# ============================================================

def _is_url(value: str) -> bool:
    """
    Detect whether a citation value is a URL.
    """

    if not value:
        return False

    try:
        parsed = urlparse(value)
        return parsed.scheme in ("http", "https")
    except Exception:
        return False


def _safe_filename(value: str) -> str:
    """
    Extract a safe filename from a path or URL.

    Prevents path traversal and decodes URL encoding.
    """

    if not value:
        return ""

    # Decode URL encoding
    value = unquote(value)

    name = Path(value).name

    # Prevent traversal
    name = name.replace("..", "")

    return name.strip()


def _normalize_filename(name: str) -> str:
    """
    Normalize filenames for fuzzy matching.

    Handles:
    - spaces
    - case
    - URL encoding
    """

    name = unquote(name)
    name = name.lower()
    name = name.replace(" ", "")
    return name


def _matches_stored_filename(stored_name: str, requested_name: str) -> bool:
    """
    Match filenames even if storage added a UUID prefix
    or if spacing differs.

    Example
    -------
    stored:    8d31a_file.pdf
    request:   file.pdf

    stored:    file  name.pdf
    request:   file name.pdf
    """

    stored_lower = stored_name.lower()
    requested_lower = requested_name.lower()

    if stored_lower == requested_lower:
        return True

    # uuid_filename.pdf case
    if "_" in stored_lower:
        possible = stored_lower.split("_", 1)[1]
        if possible == requested_lower:
            return True

    # fuzzy match ignoring spaces
    if _normalize_filename(stored_lower) == _normalize_filename(requested_lower):
        return True

    return False


# ============================================================
# MAIN LOCATOR
# ============================================================

def locate_source(source_value: str) -> Optional[Path]:
    """
    Resolve a citation source into a local file path.

    Returns
    -------
    Path if found, otherwise None.
    """

    if not source_value:
        return None

    # --------------------------------------------------------
    # Extract filename
    # --------------------------------------------------------

    if _is_url(source_value):

        parsed = urlparse(source_value)
        filename = _safe_filename(parsed.path)

    else:

        filename = _safe_filename(source_value)

    if not filename:
        return None

    # --------------------------------------------------------
    # Direct search
    # --------------------------------------------------------

    search_dirs = [
        PDF_DIR,
        CSV_DIR,
        EXCEL_DIR,
    ]

    for directory in search_dirs:

        try:

            if not directory.exists():
                continue

            direct_path = directory / filename

            if direct_path.exists() and direct_path.is_file():
                return direct_path

        except Exception:
            continue

    # --------------------------------------------------------
    # Fuzzy search (handles UUID prefix, spacing differences)
    # --------------------------------------------------------

    for directory in search_dirs:

        try:

            if not directory.exists():
                continue

            for file in directory.iterdir():

                if not file.is_file():
                    continue

                if _matches_stored_filename(file.name, filename):
                    return file

        except Exception:
            continue

    return None


# ============================================================
# URL RESOLUTION
# ============================================================

def resolve_citation(source_value: str) -> Tuple[Optional[str], Optional[object]]:
    """
    Resolve citation into either:

        ("file", Path)
        ("url", str)
        (None, None)
    """

    if not source_value:
        return None, None

    # --------------------------------------------------------
    # Remote URL
    # --------------------------------------------------------

    if _is_url(source_value):
        return "url", source_value

    # --------------------------------------------------------
    # Local file
    # --------------------------------------------------------

    path = locate_source(source_value)

    if path:
        return "file", path

    return None, None


# ============================================================
# PAGE SUPPORT
# ============================================================

def build_pdf_page_link(source_value: str, page_number: Optional[int]):
    """
    Build a PDF link including page navigation.

    Used by PDF viewer.
    """

    path = locate_source(source_value)

    if not path:
        return None

    if page_number and page_number > 0:
        return f"{path.as_posix()}#page={page_number}"

    return path.as_posix()