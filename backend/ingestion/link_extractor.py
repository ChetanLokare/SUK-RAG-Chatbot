import re
from urllib.parse import urljoin, urlparse, urlunparse


# ============================================================
# URL REGEX (PDF / TEXT EXTRACTION)
# ============================================================

URL_REGEX = re.compile(
    r"(https?://[^\s\)\]\}\>\"']+)",
    re.IGNORECASE,
)


# ============================================================
# JAVASCRIPT LINK PATTERNS
# ============================================================

JS_WINDOW_OPEN = re.compile(
    r"window\.open\(['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

JS_LOCATION = re.compile(
    r"location\.href\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

JS_GENERIC_FILE = re.compile(
    r"['\"]([^'\"]+\.(pdf|xls|xlsx|csv|doc|docx|zip|rar|7z))['\"]",
    re.IGNORECASE,
)


# ============================================================
# FILE EXTENSIONS
# ============================================================

PDF_EXT = (".pdf",)
EXCEL_EXT = (".xls", ".xlsx", ".csv")
DOC_EXT = (".doc", ".docx")
ZIP_EXT = (".zip", ".rar", ".7z")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".tiff", ".gif")


# ============================================================
# SUK DOMAIN NORMALIZER
# Fix duplicates like:
#   http://www.unishivaji.ac.in
#   http://unishivaji.ac.in:80
# ============================================================

def _fix_unishivaji_host(url: str):

    try:
        parsed = urlparse(url)

        if "unishivaji.ac.in" in parsed.netloc:

            parsed = parsed._replace(
                scheme="https",
                netloc="unishivaji.ac.in",
            )

        parsed = parsed._replace(fragment="")

        return urlunparse(parsed)

    except Exception:
        return url


# ============================================================
# NORMALIZE URL
# ============================================================

def _normalize_url(url: str):

    try:
        parsed = urlparse(url)

        parsed = parsed._replace(fragment="")

        if parsed.query:
            if any(x in parsed.query.lower() for x in ["utm_", "session", "ref"]):
                parsed = parsed._replace(query="")

        return urlunparse(parsed)

    except Exception:
        return url


# ============================================================
# FILE DETECTOR
# Handles:
#   .pdf
#   download?id=xxx
#   ?file=xxx.pdf
# ============================================================

def _is_file(url: str, extensions: tuple):

    lower = url.lower()

    if lower.endswith(extensions):
        return True

    if any(ext in lower for ext in extensions):
        return True

    return False


# ============================================================
# EXTRACT LINKS FROM ATTRIBUTES
# Handles onclick, data-href, javascript
# ============================================================

def _extract_from_attributes(tag, base_url):

    links = []

    try:

        # onclick
        onclick = tag.get("onclick")

        if onclick:

            match = JS_WINDOW_OPEN.search(onclick)
            if match:
                links.append(urljoin(base_url, match.group(1)))

            match = JS_LOCATION.search(onclick)
            if match:
                links.append(urljoin(base_url, match.group(1)))

            for m in JS_GENERIC_FILE.findall(onclick):
                links.append(urljoin(base_url, m[0]))

        # data-href
        data_href = tag.get("data-href")
        if data_href:
            links.append(urljoin(base_url, data_href))

    except Exception:
        pass

    return links


# ============================================================
# SCRIPT LINK EXTRACTION
# Finds hidden PDF endpoints inside JS
# ============================================================

def _extract_from_scripts(soup, base_url):

    links = set()

    try:

        for script in soup.find_all("script"):

            text = script.string

            if not text:
                continue

            for match in JS_GENERIC_FILE.findall(text):
                links.add(urljoin(base_url, match[0]))

    except Exception:
        pass

    return links


# ============================================================
# MAIN HTML LINK EXTRACTOR
# ============================================================

def extract_links(soup, base_url: str):

    pdf_links = set()
    excel_links = set()
    page_links = set()

    if not soup:
        return [], [], []

    # --------------------------------------------------------
    # STANDARD <a href>
    # --------------------------------------------------------

    for a in soup.find_all("a"):

        href = a.get("href")

        if href:
            href = href.strip()

            if href.startswith(("#", "mailto:", "tel:")):
                href = None

        extracted = []

        if href:
            extracted.append(urljoin(base_url, href))

        extracted.extend(_extract_from_attributes(a, base_url))

        for full_url in extracted:

            try:

                full_url = _fix_unishivaji_host(full_url)
                full_url = _normalize_url(full_url)

                parsed = urlparse(full_url)

                if not parsed.scheme.startswith("http"):
                    continue

                lower = full_url.lower()

                if _is_file(lower, PDF_EXT):
                    pdf_links.add(full_url)

                elif _is_file(lower, EXCEL_EXT):
                    excel_links.add(full_url)

                elif _is_file(lower, DOC_EXT):
                    excel_links.add(full_url)

                elif _is_file(lower, ZIP_EXT):
                    excel_links.add(full_url)

                elif _is_file(lower, IMAGE_EXT):
                    continue

                else:
                    page_links.add(full_url)

            except Exception:
                continue

    # --------------------------------------------------------
    # SCRIPT LINKS
    # --------------------------------------------------------

    script_links = _extract_from_scripts(soup, base_url)

    for link in script_links:

        try:

            link = _fix_unishivaji_host(link)
            link = _normalize_url(link)

            lower = link.lower()

            if _is_file(lower, PDF_EXT):
                pdf_links.add(link)

            elif _is_file(lower, EXCEL_EXT):
                excel_links.add(link)

            else:
                page_links.add(link)

        except Exception:
            continue

    return list(pdf_links), list(excel_links), list(page_links)


# ============================================================
# TEXT URL EXTRACTOR
# Used for OCR / PDF extracted text
# ============================================================

def extract_links_from_text(text: str):

    urls = set()

    if not text:
        return []

    for match in URL_REGEX.findall(text):

        try:

            parsed = urlparse(match)

            if not parsed.scheme.startswith("http"):
                continue

            url = _fix_unishivaji_host(match)
            url = _normalize_url(url)

            urls.add(url)

        except Exception:
            continue

    return list(urls)