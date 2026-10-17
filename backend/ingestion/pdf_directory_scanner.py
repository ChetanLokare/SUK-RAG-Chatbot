import re
from urllib.parse import urljoin, urlparse, urlunparse
from typing import List, Tuple, Set

from bs4 import BeautifulSoup

from backend.core.hybrid_fetch import hybrid_fetch


# ============================================================
# CONFIG
# ============================================================

MAX_DIRECTORY_DEPTH = 2

PDF_EXT = (".pdf",)

EXCEL_EXT = (
    ".xls",
    ".xlsx",
    ".csv",
)

DOC_EXT = (
    ".doc",
    ".docx",
)

ZIP_EXT = (
    ".zip",
    ".rar",
    ".7z",
)

IMAGE_EXT = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".tiff",
)

DIRECTORY_HINTS = (
    "/uploads/",
    "/download/",
    "/downloads/",
    "/files/",
    "/documents/",
    "/docs/",
)


# ============================================================
# 🔥 DOMAIN FIX (CRITICAL)
# ============================================================

def _fix_domain(url: str) -> str:
    """
    Fix broken university links:
    unishivaji.ac.in → www.unishivaji.ac.in
    """
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
# NORMALIZE URL
# ============================================================

def _normalize_url(url: str) -> str:

    try:
        parsed = urlparse(url)
        parsed = parsed._replace(fragment="")
        return urlunparse(parsed)
    except Exception:
        return url


# ============================================================
# FILE TYPE DETECTOR
# ============================================================

def _detect_file_type(url: str):

    lower = url.lower()

    if lower.endswith(PDF_EXT) or ".pdf" in lower:
        return "pdf"

    if lower.endswith(EXCEL_EXT) or any(x in lower for x in EXCEL_EXT):
        return "excel"

    if lower.endswith(DOC_EXT) or any(x in lower for x in DOC_EXT):
        return "excel"

    if lower.endswith(ZIP_EXT) or any(x in lower for x in ZIP_EXT):
        return "excel"

    if lower.endswith(IMAGE_EXT):
        return "image"

    return "page"


# ============================================================
# DIRECTORY DETECTOR
# ============================================================

def _looks_like_directory(url: str) -> bool:

    lower = url.lower()

    return any(x in lower for x in DIRECTORY_HINTS)


# ============================================================
# EXTRACT LINKS FROM PAGE (🔥 FIXED)
# ============================================================

def _extract_links(soup: BeautifulSoup, base_url: str):

    urls = set()

    for a in soup.find_all("a", href=True):

        href = a.get("href")

        if not href:
            continue

        try:
            full = urljoin(base_url, href)

            full = _normalize_url(full)

            # 🔥 CRITICAL FIX
            full = _fix_domain(full)

            urls.add(full)

        except Exception:
            continue

    return urls


# ============================================================
# SCAN DIRECTORY PAGE
# ============================================================

def _scan_directory(
    url: str,
    base_domain: str,
    visited: Set[str],
    depth: int
):

    pdf_links = set()
    excel_links = set()
    page_links = set()

    if depth > MAX_DIRECTORY_DEPTH:
        return pdf_links, excel_links, page_links

    if url in visited:
        return pdf_links, excel_links, page_links

    visited.add(url)

    try:
        response = hybrid_fetch(url)
        html = response.text
        soup = BeautifulSoup(html, "lxml")

    except Exception:
        return pdf_links, excel_links, page_links

    discovered = _extract_links(soup, url)

    for link in discovered:

        try:
            parsed = urlparse(link)

            if parsed.netloc != base_domain:
                continue

            link = _normalize_url(link)
            link = _fix_domain(link)   # 🔥 DOUBLE SAFETY

            file_type = _detect_file_type(link)

            if file_type == "pdf":
                pdf_links.add(link)

            elif file_type == "excel":
                excel_links.add(link)

            elif file_type == "image":
                continue

            else:
                if _looks_like_directory(link):

                    sub_pdf, sub_excel, sub_pages = _scan_directory(
                        link,
                        base_domain,
                        visited,
                        depth + 1
                    )

                    pdf_links.update(sub_pdf)
                    excel_links.update(sub_excel)
                    page_links.update(sub_pages)

                else:
                    page_links.add(link)

        except Exception:
            continue

    return pdf_links, excel_links, page_links


# ============================================================
# PUBLIC DIRECTORY SCANNER
# ============================================================

def scan_pdf_directories(seed_url: str) -> Tuple[List[str], List[str], List[str]]:

    pdf_links = set()
    excel_links = set()
    page_links = set()

    visited = set()

    try:
        seed_url = _fix_domain(seed_url)   # 🔥 FIX ENTRY POINT

        response = hybrid_fetch(seed_url)
        html = response.text
        soup = BeautifulSoup(html, "lxml")

    except Exception:
        return [], [], []

    base_domain = urlparse(seed_url).netloc

    initial_links = _extract_links(soup, seed_url)

    for link in initial_links:

        try:
            link = _fix_domain(link)

            if _looks_like_directory(link):

                sub_pdf, sub_excel, sub_pages = _scan_directory(
                    link,
                    base_domain,
                    visited,
                    depth=0
                )

                pdf_links.update(sub_pdf)
                excel_links.update(sub_excel)
                page_links.update(sub_pages)

        except Exception:
            continue

    return (
        sorted(pdf_links),
        sorted(excel_links),
        sorted(page_links),
    )