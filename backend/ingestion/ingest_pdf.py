import hashlib
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from langdetect import detect, LangDetectException

from backend.core.config import PDF_DIR
from backend.core.hybrid_fetch import hybrid_fetch

from backend.ingestion.indexer import index_document
from backend.ingestion.semantic_document_classifier import classify_document_semantic
from backend.ingestion.pdf_layout_parser import parse_pdf_layout
from backend.ingestion.pdf_semantic_chunker import chunk_by_sections

from backend.registry.repository import mark_failed
from backend.registry.models import Source


# ============================================================
# CONFIG
# ============================================================

MIN_FILE_SIZE = 5000
MAX_CLASSIFIER_TEXT = 3000
MAX_SECTION_LENGTH = 2000

DOWNLOAD_RETRIES = 2
RETRY_DELAY = 1.5


# ============================================================
# DOMAIN FIX
# ============================================================

def _fix_domain(url: str) -> str:
    try:
        if "unishivaji.ac.in" in url and "www." not in url:
            return url.replace(
                "https://unishivaji.ac.in",
                "https://www.unishivaji.ac.in"
            )
    except Exception:
        pass
    return url


# ============================================================
# HELPERS
# ============================================================

def detect_language(text: str) -> str:
    try:
        if not text.strip():
            return "unknown"
        return detect(text)
    except LangDetectException:
        return "unknown"


def compute_file_hash(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _resolve_local_path(source: Source) -> Path:
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    if source.source_value.startswith("http"):
        filename = Path(urlparse(source.source_value).path).name
        if not filename.endswith(".pdf"):
            filename = f"{source.id}.pdf"
        return PDF_DIR / filename

    return PDF_DIR / Path(source.source_value).name


# ============================================================
# SAFE DOWNLOAD
# ============================================================

def _download_pdf(url: str, path: Path):

    fixed_url = _fix_domain(url)

    for attempt in range(DOWNLOAD_RETRIES):

        try:
            print(f"🌐 Download attempt {attempt+1}: {fixed_url}")

            response = hybrid_fetch(fixed_url)

            if not response or not response.content:
                raise RuntimeError("Empty response")

            if b"<html" in response.content[:200].lower():
                raise RuntimeError("Received HTML instead of PDF")

            with open(path, "wb") as f:
                f.write(response.content)

            return True

        except Exception as e:
            print(f"⚠️ Download failed attempt {attempt+1}: {e}")
            time.sleep(RETRY_DELAY)

    return False


# ============================================================
# TABLE CHUNKING
# ============================================================

def build_table_chunks(rows: List[str]) -> List[str]:

    chunks = []
    buffer = []

    for row in rows:

        if not row or len(row.strip()) < 5:
            continue

        buffer.append(row.strip())

        if len(buffer) >= 6:
            chunks.append("TABLE DATA:\n" + "\n".join(buffer))
            buffer = []

    if buffer:
        chunks.append("TABLE DATA:\n" + "\n".join(buffer))

    return chunks


# ============================================================
# MAIN INGEST
# ============================================================

def ingest_pdf(db: Session, source: Source):

    try:

        pdf_path = _resolve_local_path(source)

        print("\n📄 INGEST PDF:", source.source_value)

        # ---------------- DOWNLOAD ----------------

        if source.source_value.startswith("http") and not pdf_path.exists():

            success = _download_pdf(source.source_value, pdf_path)

            if not success:
                mark_failed(db, source.id, "download_failed")
                return {"status": "failed"}

        # ---------------- VALIDATION ----------------

        if not pdf_path.exists():
            mark_failed(db, source.id, "pdf_not_found")
            return {"status": "failed"}

        if pdf_path.stat().st_size < MIN_FILE_SIZE:
            mark_failed(db, source.id, "pdf_too_small")
            return {"status": "failed"}

        # ---------------- HASH (🔥 FIXED) ----------------

        new_hash = compute_file_hash(pdf_path)

        # ✅ ONLY skip if already SUCCESSFULLY ingested
        if source.file_hash == new_hash and source.status == "ingested":
            print("⚡ Skipping (already ingested)")
            return {"status": "unchanged", "chunks_indexed": 0}

        # ---------------- PARSE ----------------

        text_blocks, table_rows = parse_pdf_layout(pdf_path)

        print("📄 TEXT BLOCKS:", len(text_blocks))
        print("📊 TABLE ROWS:", len(table_rows))

        if not text_blocks and not table_rows:
            mark_failed(db, source.id, "no_text")
            return {"status": "failed"}

        # ---------------- SECTIONS ----------------

        sections = chunk_by_sections(text_blocks)

        print("📚 Sections:", len(sections))

        combined_text = " ".join(
            s["text"] for s in sections if s.get("text")
        )

        language = detect_language(combined_text)

        document_type = classify_document_semantic(
            combined_text[:MAX_CLASSIFIER_TEXT]
        )

        total_chunks = 0

        # ---------------- TEXT ----------------

        for i, section in enumerate(sections):

            text = section.get("text", "").strip()

            if not text:
                continue

            if len(text) > MAX_SECTION_LENGTH:
                text = text[:MAX_SECTION_LENGTH]

            enriched = f"""
SECTION: {section.get('heading', 'General')}

{text}
"""

            result = index_document(
                source_id=source.id,
                source_type="pdf",
                category=source.category,
                language=language,
                source_value=source.source_value,
                page_number=section.get("page", -1),
                text=enriched,
                extra_metadata={
                    "section_heading": section.get("heading"),
                    "document_type": document_type,
                },
                is_first_page=(i == 0),
            )

            total_chunks += result.get("chunks_indexed", 0)

        # ---------------- TABLES ----------------

        table_chunks = build_table_chunks(table_rows)

        for i, chunk in enumerate(table_chunks):

            result = index_document(
                source_id=source.id,
                source_type="pdf",
                category=source.category,
                language=language,
                source_value=source.source_value,
                page_number=-1,
                text=chunk,
                extra_metadata={
                    "table_data": True,
                    "document_type": document_type,
                },
                is_first_page=(i == 0 and total_chunks == 0),
            )

            total_chunks += result.get("chunks_indexed", 0)

        if total_chunks == 0:
            mark_failed(db, source.id, "no_chunks")
            return {"status": "failed"}

        # ---------------- SUCCESS ----------------

        source.file_hash = new_hash
        source.language = language
        source.status = "ingested"
        source.last_ingested_at = datetime.now(timezone.utc)
        source.error_message = None

        db.commit()

        print("✅ PDF INGEST SUCCESS:", total_chunks)

        return {
            "status": "ingested",
            "chunks_indexed": total_chunks,
            "sections": len(sections),
            "tables": len(table_chunks),
        }

    except Exception as e:

        print("❌ PDF INGEST ERROR:", e)

        mark_failed(db, source.id, str(e))

        return {"status": "failed"}