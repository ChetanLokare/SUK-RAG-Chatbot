# backend/ingestion/ingest_url.py

import hashlib
import re
import time
import random

from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urldefrag

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from backend.core.hybrid_fetch import hybrid_fetch
from backend.core.chroma_client import delete_vectors_by_source_id

from backend.ingestion.link_extractor import (
    extract_links,
    extract_links_from_text,
)

from backend.ingestion.hidden_link_extractor import extract_hidden_links

from backend.ingestion.indexer import index_document
from backend.ingestion.language_detector import detect_language
from backend.ingestion.date_extractor import extract_primary_deadline

from backend.registry.repository import (
    create_source,
    mark_failed,
    update_url_hash,
)

from backend.registry.models import Source


# ============================================================
# CONFIG
# ============================================================

FETCH_RETRIES = 3
RETRY_DELAY = 2
CRAWL_DELAY = (0.3, 0.9)

MIN_PAGE_CHARS = 80
TABLE_CHUNK_ROWS = 6


# ============================================================
# CLEAN TEXT
# ============================================================

def _clean_text(text: str):
    text = re.sub(r"\r", "", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ============================================================
# REMOVE NOISE
# ============================================================

def _remove_noise(soup):

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    for tag in soup.select(
        "header, footer, nav, .menu, .navigation, .sidebar, .top-nav"
    ):
        tag.decompose()


# ============================================================
# TABLE EXTRACTION
# ============================================================

def _extract_tables(soup):

    results = []

    for table in soup.find_all("table"):

        rows = []

        for tr in table.find_all("tr"):

            cells = []

            for cell in tr.find_all(["td", "th"]):

                txt = cell.get_text(" ", strip=True)

                if txt:
                    cells.append(txt)

            if len(cells) >= 2:
                rows.append(" | ".join(cells))

        if rows:

            buffer = []

            for r in rows:
                buffer.append(r)

                if len(buffer) >= TABLE_CHUNK_ROWS:
                    results.append("\n".join(buffer))
                    buffer = []

            if buffer:
                results.append("\n".join(buffer))

    return results


# ============================================================
# CONTENT EXTRACTION
# ============================================================

def _extract_visible_text(html: str):

    soup = BeautifulSoup(html, "lxml")

    _remove_noise(soup)

    body = soup.body
    if not body:
        return ""

    blocks = []

    for h in body.find_all(["h1", "h2", "h3", "h4"]):
        txt = h.get_text(" ", strip=True)
        if txt and len(txt) > 5:
            blocks.append(txt)

    for tag in body.find_all(["p", "span", "div"]):
        txt = tag.get_text(" ", strip=True)
        if txt and len(txt) > 50:
            blocks.append(txt)

    for li in body.find_all("li"):
        txt = li.get_text(" ", strip=True)
        if txt and len(txt) > 20:
            blocks.append(txt)

    table_chunks = _extract_tables(soup)
    blocks.extend(table_chunks)

    if len(" ".join(blocks)) < 200:
        fallback = body.get_text(" ", strip=True)
        if fallback:
            blocks.append(fallback)

    return _clean_text("\n\n".join(blocks))


# ============================================================
# HASH
# ============================================================

def _hash(text: str):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ============================================================
# FETCH
# ============================================================

def _fetch_with_retry(url: str):

    last_error = None

    for attempt in range(FETCH_RETRIES):

        try:
            time.sleep(random.uniform(*CRAWL_DELAY))
            print(f"🌐 Fetching → {url}")
            return hybrid_fetch(url)

        except Exception as e:
            last_error = e
            print(f"⚠ FETCH RETRY {attempt+1} → {e}")
            time.sleep(RETRY_DELAY)

    raise last_error


# ============================================================
# MAIN INGEST
# ============================================================

def ingest_url(db: Session, source: Source):

    start_time = time.time()

    url = source.source_value

    print("\n================================================")
    print(f"🔎 INGEST URL → {url}")
    print("================================================")

    try:
        response = _fetch_with_retry(url)

        html = response.text
        content_type = (response.headers.get("content-type") or "").lower()

        if "html" not in content_type:
            return {"status": "failed", "reason": "not_html"}

    except Exception as e:
        return {"status": "failed", "reason": f"fetch_error: {e}"}

    if not html:
        return {"status": "failed", "reason": "empty_html"}

    # ========================================================
    # TEXT EXTRACTION
    # ========================================================

    full_text = _extract_visible_text(html)
    char_count = len(full_text)

    print(f"📄 Extracted characters → {char_count}")

    preview = full_text[:300]

    if char_count < MIN_PAGE_CHARS:
        soup = BeautifulSoup(html, "lxml")
        fallback = soup.get_text(" ", strip=True)

        if fallback:
            full_text = fallback
            char_count = len(full_text)

    if char_count < 50:
        return {"status": "failed", "reason": "too_small"}

    # ========================================================
    # LINK EXTRACTION
    # ========================================================

    soup = BeautifulSoup(html, "lxml")

    pdf_links, excel_links, page_links = [], [], []

    try:
        pdf_links, excel_links, page_links = extract_links(soup, base_url=url)
    except:
        pass

    try:
        h_pdf, h_excel, h_pages = extract_hidden_links(soup, base_url=url)
        pdf_links.extend(h_pdf)
        excel_links.extend(h_excel)
        page_links.extend(h_pages)
    except:
        pass

    try:
        text_links = extract_links_from_text(full_text)
        page_links.extend(text_links)
    except:
        pass

    pdf_links = list(set(pdf_links))
    excel_links = list(set(excel_links))
    page_links = list(set(page_links))

    print(f"🔗 PDFs → {len(pdf_links)}")
    print(f"📊 Excel → {len(excel_links)}")
    print(f"🌐 URLs → {len(page_links)}")

    # ========================================================
    # HASH CHECK
    # ========================================================

    new_hash = _hash(full_text or url)

    changed = update_url_hash(db, source.id, new_hash)
    db.commit()

    if not changed:
        print("⚡ No change detected")
        return {"status": "unchanged"}

    try:
        delete_vectors_by_source_id(source.id)
    except:
        pass

    # ========================================================
    # INDEX
    # ========================================================

    print("🧠 Indexing...")

    language = detect_language(full_text)

    result = index_document(
        source_id=source.id,
        source_type="url",
        category=source.category,
        language=language,
        source_value=url,
        page_number=None,
        text=full_text,
    )

    chunks = result.get("chunks_indexed", 0)

    # ========================================================
    # REGISTER LINKS
    # ========================================================

    base_domain = urlparse(url).netloc
    registered = 0

    def _register(link, stype):
        nonlocal registered
        try:
            create_source(
                db=db,
                source_type=stype,
                source_value=link,
                category=source.category,
                origin="crawl",
                parent_id=source.id,
            )
            registered += 1
        except:
            pass

    for link in pdf_links:
        _register(link, "pdf")

    for link in excel_links:
        _register(link, "excel")

    for link in page_links:
        if urlparse(link).netloc == base_domain:
            _register(link, "url")

    # ========================================================
    # FINALIZE
    # ========================================================

    source.last_ingested_at = datetime.now(timezone.utc)
    source.status = "ingested"
    source.error_message = None
    db.commit()

    elapsed = round(time.time() - start_time, 2)

    print("✅ INGEST COMPLETE")
    print(f"⏱ Time: {elapsed}s")
    print(f"📦 Chunks: {chunks}")

    return {
        "status": "success",
        "url": url,
        "text_length": char_count,
        "text_preview": preview,
        "chunks_indexed": chunks,
        "pdfs_found": len(pdf_links),
        "excels_found": len(excel_links),
        "urls_found": len(page_links),
        "links_registered": registered,
        "language": language,
        "time_taken_sec": elapsed,
    }