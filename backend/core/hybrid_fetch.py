# backend/core/hybrid_fetch.py

import re
import time
import random
import requests
import certifi

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


# ============================================================
# CONFIG
# ============================================================

CRAWL_DELAY = (0.3, 1.0)

FILE_EXTENSIONS = (
    ".pdf",
    ".csv",
    ".xlsx",
    ".xls",
    ".zip",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".jpg",
    ".jpeg",
    ".png",
    ".tiff",
)


# ============================================================
# SESSION CREATION
# ============================================================

def create_secure_session() -> requests.Session:

    session = requests.Session()

    retry_strategy = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=20,
        pool_maxsize=20,
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.verify = certifi.where()

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-IN,en;q=0.9",
    })

    return session


# ============================================================
# URL FILE DETECTION
# ============================================================

def _url_looks_like_file(url: str) -> bool:

    path = urlparse(url).path.lower()

    return any(path.endswith(ext) for ext in FILE_EXTENSIONS)


# ============================================================
# RESPONSE FILE DETECTION
# ============================================================

def _is_file_response(response: requests.Response) -> bool:

    content_type = (response.headers.get("content-type") or "").lower()

    if any(x in content_type for x in [
        "application/pdf",
        "application/octet-stream",
        "application/vnd",
        "application/zip",
        "text/csv",
        "image/",
    ]):
        return True

    # Magic byte detection
    try:
        head = response.content[:8]

        if head.startswith(b"%PDF"):
            return True

        if head.startswith(b"PK"):
            return True  # zip / xlsx

    except Exception:
        pass

    return False


# ============================================================
# REQUEST FETCH
# ============================================================

def fetch_with_requests(url: str) -> requests.Response:

    session = create_secure_session()

    time.sleep(random.uniform(*CRAWL_DELAY))

    response = session.get(
        url,
        timeout=(15, 60),
        allow_redirects=True,
        stream=False,
    )

    response.raise_for_status()

    return response


# ============================================================
# PLAYWRIGHT FETCH
# ============================================================

def fetch_with_playwright(url: str):

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            ignore_https_errors=True
        )

        page = context.new_page()

        page.goto(url, timeout=60000)

        page.wait_for_load_state("networkidle")

        html = page.content()

        final_url = page.url

        browser.close()

    class FakeResponse:

        def __init__(self, text: str, url: str):

            self.text = text
            self.content = text.encode("utf-8")
            self.url = url
            self.headers = {"content-type": "text/html"}
            self.status_code = 200

    return FakeResponse(html, final_url)


# ============================================================
# ASP.NET SHELL DETECTION
# ============================================================

def _looks_like_aspnet_shell(html: str) -> bool:

    if not html:
        return True

    markers = [
        "__VIEWSTATE",
        "__EVENTVALIDATION",
        "ctl00_ContentPlaceHolder",
        "aspnetForm",
        "WebResource.axd",
    ]

    score = sum(1 for m in markers if m.lower() in html.lower())

    visible_text = re.sub(r"\s+", " ", html)

    text_ratio = len(visible_text) / max(len(html), 1)

    return score >= 2 and text_ratio < 0.6


# ============================================================
# MAIN HYBRID FETCH
# ============================================================

def hybrid_fetch(url: str):
    """
    Hybrid fetch strategy.

    Flow:

    1) If URL looks like file → use requests only
    2) Try requests
    3) If file → return
    4) If HTML but looks like JS shell → Playwright
    5) Otherwise return requests response
    """

    force_file_mode = _url_looks_like_file(url)

    # --------------------------------------------------------
    # TRY REQUESTS
    # --------------------------------------------------------

    try:

        response = fetch_with_requests(url)

    except Exception as e:

        print("REQUEST ERROR:", e)

        if not force_file_mode:

            try:
                return fetch_with_playwright(url)

            except Exception:
                raise

        raise


    # --------------------------------------------------------
    # FILE RESPONSE
    # --------------------------------------------------------

    if _is_file_response(response):

        return response


    content_type = (response.headers.get("content-type") or "").lower()


    # --------------------------------------------------------
    # HTML RESPONSE
    # --------------------------------------------------------

    if "text/html" in content_type and not force_file_mode:

        html = response.text

        if (
            len(html.strip()) < 1800
            or _looks_like_aspnet_shell(html)
        ):
            try:

                return fetch_with_playwright(url)

            except Exception:

                return response

    return response