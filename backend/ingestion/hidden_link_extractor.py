# backend/ingestion/hidden_link_extractor.py

import re
from urllib.parse import urljoin, urlparse, urlunparse


# ============================================================
# FILE EXTENSIONS
# ============================================================

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


# ============================================================
# JAVASCRIPT PATTERNS
# ============================================================

WINDOW_OPEN_PATTERN = re.compile(
    r"window\.open\(['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

LOCATION_HREF_PATTERN = re.compile(
    r"location\.href\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

GENERIC_FILE_PATTERN = re.compile(
    r"['\"]([^'\"]+\.(pdf|xls|xlsx|csv|doc|docx|zip|rar|7z))['\"]",
    re.IGNORECASE,
)

AJAX_URL_PATTERN = re.compile(
    r"(https?://[^\s\"']+)",
    re.IGNORECASE,
)


# ============================================================
# URL NORMALIZATION
# ============================================================

def _normalize_url(url: str):

    try:

        parsed = urlparse(url)

        parsed = parsed._replace(fragment="")

        return urlunparse(parsed)

    except Exception:
        return url


# ============================================================
# FILE DETECTOR
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
# EXTRACT FROM HTML ATTRIBUTES
# ============================================================

def _extract_from_attributes(tag, base_url):

    links = []

    try:

        # onclick handler
        onclick = tag.get("onclick")

        if onclick:

            match = WINDOW_OPEN_PATTERN.search(onclick)
            if match:
                links.append(urljoin(base_url, match.group(1)))

            match = LOCATION_HREF_PATTERN.search(onclick)
            if match:
                links.append(urljoin(base_url, match.group(1)))

            for m in GENERIC_FILE_PATTERN.findall(onclick):
                links.append(urljoin(base_url, m[0]))

        # data-href
        data_href = tag.get("data-href")

        if data_href:
            links.append(urljoin(base_url, data_href))

        # data-url
        data_url = tag.get("data-url")

        if data_url:
            links.append(urljoin(base_url, data_url))

    except Exception:
        pass

    return links


# ============================================================
# SCRIPT BLOCK EXTRACTION
# ============================================================

def _extract_from_scripts(soup, base_url):

    links = set()

    try:

        for script in soup.find_all("script"):

            script_text = script.string

            if not script_text:
                continue

            # detect direct file references
            for m in GENERIC_FILE_PATTERN.findall(script_text):

                try:
                    links.add(urljoin(base_url, m[0]))
                except Exception:
                    pass

            # detect ajax urls
            for m in AJAX_URL_PATTERN.findall(script_text):

                try:
                    links.add(urljoin(base_url, m))
                except Exception:
                    pass

    except Exception:
        pass

    return links


# ============================================================
# MAIN HIDDEN LINK EXTRACTOR
# ============================================================

def extract_hidden_links(soup, base_url: str):

    pdf_links = set()
    excel_links = set()
    page_links = set()

    if not soup:
        return [], [], []

    # --------------------------------------------------------
    # SCAN ALL TAGS FOR HIDDEN ATTRIBUTES
    # --------------------------------------------------------

    for tag in soup.find_all(True):

        try:

            hidden_links = _extract_from_attributes(tag, base_url)

            for url in hidden_links:

                url = _normalize_url(url)

                file_type = _detect_file_type(url)

                if file_type == "pdf":
                    pdf_links.add(url)

                elif file_type == "excel":
                    excel_links.add(url)

                elif file_type == "image":
                    continue

                else:
                    page_links.add(url)

        except Exception:
            continue


    # --------------------------------------------------------
    # SCRIPT DISCOVERY
    # --------------------------------------------------------

    script_links = _extract_from_scripts(soup, base_url)

    for link in script_links:

        try:

            link = _normalize_url(link)

            file_type = _detect_file_type(link)

            if file_type == "pdf":
                pdf_links.add(link)

            elif file_type == "excel":
                excel_links.add(link)

            elif file_type == "image":
                continue

            else:
                page_links.add(link)

        except Exception:
            continue


    return (
        list(pdf_links),
        list(excel_links),
        list(page_links),
    )