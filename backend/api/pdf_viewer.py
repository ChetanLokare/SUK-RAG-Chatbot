from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from pathlib import Path
import mimetypes
from urllib.parse import unquote

from backend.citation.pdf_locator import resolve_citation, locate_source

router = APIRouter(prefix="/pdf", tags=["Document Viewer"])


# ============================================================
# MIME TYPE DETECTION
# ============================================================

def _get_media_type(path: Path) -> str:
    """
    Determine MIME type for file response.
    """

    mime, _ = mimetypes.guess_type(str(path))

    if mime:
        return mime

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return "application/pdf"

    if suffix == ".csv":
        return "text/csv"

    if suffix in (".xlsx", ".xls"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    return "application/octet-stream"


# ============================================================
# MAIN DOCUMENT VIEWER
# ============================================================

@router.get("/{filename}")
def serve_document(
    filename: str,
    page: int | None = Query(None, description="PDF page number"),
):
    """
    Serve documents referenced by citations.

    Supports:
    • PDF
    • CSV
    • Excel
    • Remote URLs
    """

    # --------------------------------------------------------
    # Decode URL encoding
    # --------------------------------------------------------

    decoded_name = unquote(filename)

    # Prevent path traversal
    safe_name = Path(decoded_name).name

    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # --------------------------------------------------------
    # Resolve citation source
    # --------------------------------------------------------

    source_type, resolved = resolve_citation(safe_name)

    # fallback search if resolver failed
    if not source_type:

        resolved = locate_source(safe_name)

        if not resolved:
            raise HTTPException(status_code=404, detail="File not found")

        source_type = "file"

    # --------------------------------------------------------
    # Remote URL → redirect
    # --------------------------------------------------------

    if source_type == "url":
        return RedirectResponse(url=resolved)

    # --------------------------------------------------------
    # Local file
    # --------------------------------------------------------

    if source_type == "file":

        path: Path = resolved

        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        media_type = _get_media_type(path)

        # ----------------------------------------------------
        # PDF page navigation
        # ----------------------------------------------------

        if page and path.suffix.lower() == ".pdf":

            # Use browser page anchor
            return RedirectResponse(
                url=f"/pdf/{safe_name}#page={page}"
            )

        # ----------------------------------------------------
        # Serve file INLINE (not download)
        # ----------------------------------------------------

        return FileResponse(
            path=str(path),
            media_type=media_type
        )

    # --------------------------------------------------------
    # Safety fallback
    # --------------------------------------------------------

    raise HTTPException(status_code=500, detail="Unknown source type")