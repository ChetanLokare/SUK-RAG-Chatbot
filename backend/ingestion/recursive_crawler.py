
# backend/ingestion/recursive_crawler.py

import time
import random
from typing import List, Set
from urllib.parse import urlparse, urldefrag, urljoin

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from backend.core.hybrid_fetch import hybrid_fetch

from backend.ingestion.link_extractor import extract_links
from backend.ingestion.hidden_link_extractor import extract_hidden_links
from backend.ingestion.pdf_directory_scanner import scan_pdf_directories
from backend.ingestion.site_structure_discovery import discover_site_structure

from backend.registry.repository import create_source


# ============================================================
# CONFIG
# ============================================================

MAX_CRAWL_DEPTH = 2
MAX_PAGES_PER_LEVEL = 80

CRAWL_DELAY = (0.3, 1.2)


# ============================================================
# URL NORMALIZATION
# ============================================================

def _normalize(url: str) -> str:

    try:

        url = urldefrag(url)[0].strip()

        if url.endswith("/"):
            url = url[:-1]

        return url

    except Exception:
        return url


# ============================================================
# DOMAIN FILTER
# ============================================================

def _same_domain(base_domain: str, url: str) -> bool:

    try:

        parsed = urlparse(url)

        if not parsed.netloc:
            return False

        return parsed.netloc.endswith(base_domain)

    except Exception:
        return False


# ============================================================
# REGISTER SOURCE
# ============================================================

def _register(
    db: Session,
    parent_id,
    category: str,
    url: str,
    stype: str,
):

    try:

        create_source(
            db=db,
            source_type=stype,
            source_value=url,
            category=category,
            origin="crawl",
            parent_id=parent_id,
        )

    except Exception:
        # crawler should never crash ingestion
        pass


# ============================================================
# FETCH PAGE
# ============================================================

def _crawl_page(url: str):

    try:

        response = hybrid_fetch(url)

        if not response:
            return None

        content_type = (response.headers.get("content-type") or "").lower()

        if "html" not in content_type:
            return None

        html = response.text

        soup = BeautifulSoup(html, "lxml")

        return soup

    except Exception:
        return None


# ============================================================
# MAIN RECURSIVE CRAWLER
# ============================================================

def run_recursive_crawler(
    db: Session,
    seed_url: str,
    source_id: str,
    category: str,
):

    visited: Set[str] = set()

    queue: List[str] = [_normalize(seed_url)]

    base_domain = urlparse(seed_url).netloc

    depth = 0

    discovered_pdfs: Set[str] = set()
    discovered_excels: Set[str] = set()
    discovered_pages: Set[str] = set()

    while queue and depth <= MAX_CRAWL_DEPTH:

        next_queue: List[str] = []

        processed = 0

        for url in queue:

            if processed >= MAX_PAGES_PER_LEVEL:
                break

            url = _normalize(url)

            if url in visited:
                continue

            if not _same_domain(base_domain, url):
                continue

            visited.add(url)

            processed += 1

            time.sleep(random.uniform(*CRAWL_DELAY))

            soup = _crawl_page(url)

            if not soup:
                continue

            # --------------------------------------------------
            # NORMAL LINK EXTRACTION
            # --------------------------------------------------

            try:

                pdf_links, excel_links, page_links = extract_links(
                    soup,
                    base_url=url,
                )

            except Exception:

                pdf_links, excel_links, page_links = [], [], []

            # --------------------------------------------------
            # HIDDEN LINK EXTRACTION
            # --------------------------------------------------

            try:

                h_pdf, h_excel, h_pages = extract_hidden_links(
                    soup,
                    base_url=url,
                )

                pdf_links.extend(h_pdf)
                excel_links.extend(h_excel)
                page_links.extend(h_pages)

            except Exception:
                pass

            # --------------------------------------------------
            # DIRECTORY SCANNING
            # --------------------------------------------------

            try:

                d_pdf, d_excel, d_pages = scan_pdf_directories(url)

                pdf_links.extend(d_pdf)
                excel_links.extend(d_excel)
                page_links.extend(d_pages)

            except Exception:
                pass

            # --------------------------------------------------
            # SITE STRUCTURE DISCOVERY
            # --------------------------------------------------

            try:

                sections = discover_site_structure(url)

                page_links.extend(sections)

            except Exception:
                pass

            # --------------------------------------------------
            # NORMALIZE LINKS
            # --------------------------------------------------

            pdf_links = {_normalize(x) for x in pdf_links if x}
            excel_links = {_normalize(x) for x in excel_links if x}
            page_links = {_normalize(x) for x in page_links if x}

            # --------------------------------------------------
            # REGISTER FILE SOURCES
            # --------------------------------------------------

            for link in pdf_links:

                if link not in discovered_pdfs:

                    discovered_pdfs.add(link)

                    _register(
                        db=db,
                        parent_id=source_id,
                        category=category,
                        url=link,
                        stype="pdf",
                    )

            for link in excel_links:

                if link not in discovered_excels:

                    discovered_excels.add(link)

                    _register(
                        db=db,
                        parent_id=source_id,
                        category=category,
                        url=link,
                        stype="excel",
                    )

            # --------------------------------------------------
            # REGISTER PAGE LINKS
            # --------------------------------------------------

            for link in page_links:

                if not _same_domain(base_domain, link):
                    continue

                if link in visited:
                    continue

                if link not in discovered_pages:

                    discovered_pages.add(link)

                    next_queue.append(link)

                    _register(
                        db=db,
                        parent_id=source_id,
                        category=category,
                        url=link,
                        stype="url",
                    )

        queue = list(set(next_queue))

        depth += 1

    return {

        "seed": seed_url,
        "depth_reached": depth,
        "pages_crawled": len(visited),
        "pdfs_found": len(discovered_pdfs),
        "excels_found": len(discovered_excels),
        "pages_discovered": len(discovered_pages),
    }