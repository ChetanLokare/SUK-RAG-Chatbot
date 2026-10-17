# backend/ingestion/site_structure_discovery.py

import re
from urllib.parse import urljoin, urlparse, urlunparse
from typing import List, Set

from bs4 import BeautifulSoup

from backend.core.hybrid_fetch import hybrid_fetch


# ============================================================
# CONFIG
# ============================================================

MAX_DISCOVERY_LINKS = 300

SECTION_HINTS = (
    "/exam",
    "/examination",
    "/result",
    "/results",
    "/circular",
    "/circulars",
    "/notification",
    "/notifications",
    "/admission",
    "/admissions",
    "/tender",
    "/tenders",
    "/research",
    "/department",
    "/faculty",
    "/school",
    "/institute",
    "/centre",
    "/downloads",
    "/upload",
)

IGNORE_EXTENSIONS = (
    ".pdf",
    ".xls",
    ".xlsx",
    ".csv",
    ".zip",
    ".doc",
    ".docx",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
)


# ============================================================
# URL NORMALIZATION
# ============================================================

def _normalize_url(url: str) -> str:

    try:

        parsed = urlparse(url)

        parsed = parsed._replace(fragment="")

        return urlunparse(parsed)

    except Exception:
        return url


# ============================================================
# FILTER NON-PAGE LINKS
# ============================================================

def _is_page_candidate(url: str) -> bool:

    lower = url.lower()

    if any(lower.endswith(ext) for ext in IGNORE_EXTENSIONS):
        return False

    return True


# ============================================================
# SECTION DETECTOR
# ============================================================

def _looks_like_section(url: str) -> bool:

    lower = url.lower()

    if any(hint in lower for hint in SECTION_HINTS):
        return True

    return False


# ============================================================
# EXTRACT LINKS FROM NAVIGATION AREAS
# ============================================================

def _extract_navigation_links(soup: BeautifulSoup, base_url: str) -> Set[str]:

    links = set()

    nav_blocks = []

    try:

        nav_blocks.extend(soup.find_all("nav"))

        nav_blocks.extend(soup.find_all("header"))

        nav_blocks.extend(soup.find_all("footer"))

        nav_blocks.extend(
            soup.find_all("div", class_=re.compile("menu|nav|header|footer", re.I))
        )

        nav_blocks.extend(
            soup.find_all("ul", class_=re.compile("menu|nav", re.I))
        )

    except Exception:
        pass


    for block in nav_blocks:

        try:

            for a in block.find_all("a", href=True):

                href = a.get("href")

                if not href:
                    continue

                try:

                    full = urljoin(base_url, href)

                    full = _normalize_url(full)

                    links.add(full)

                except Exception:
                    continue

        except Exception:
            continue


    return links


# ============================================================
# EXTRACT ALL PAGE LINKS
# ============================================================

def _extract_all_links(soup: BeautifulSoup, base_url: str) -> Set[str]:

    links = set()

    try:

        for a in soup.find_all("a", href=True):

            href = a.get("href")

            if not href:
                continue

            try:

                full = urljoin(base_url, href)

                full = _normalize_url(full)

                links.add(full)

            except Exception:
                continue

    except Exception:
        pass

    return links


# ============================================================
# SCRIPT URL EXTRACTION
# ============================================================

SCRIPT_URL_PATTERN = re.compile(
    r"(https?://[^\s\"']+)",
    re.IGNORECASE,
)


def _extract_script_links(soup: BeautifulSoup) -> Set[str]:

    links = set()

    try:

        for script in soup.find_all("script"):

            text = script.string

            if not text:
                continue

            for match in SCRIPT_URL_PATTERN.findall(text):

                links.add(match)

    except Exception:
        pass

    return links


# ============================================================
# DISCOVER SITE STRUCTURE
# ============================================================

def discover_site_structure(seed_url: str) -> List[str]:

    discovered_sections = set()

    try:

        response = hybrid_fetch(seed_url)

        html = response.text

        soup = BeautifulSoup(html, "lxml")

    except Exception:

        return []


    base_domain = urlparse(seed_url).netloc


    navigation_links = _extract_navigation_links(soup, seed_url)

    page_links = _extract_all_links(soup, seed_url)

    script_links = _extract_script_links(soup)


    candidate_links = set()

    candidate_links.update(navigation_links)

    candidate_links.update(page_links)

    candidate_links.update(script_links)


    for link in candidate_links:

        try:

            parsed = urlparse(link)

            if parsed.netloc != base_domain:
                continue

            link = _normalize_url(link)

            if not _is_page_candidate(link):
                continue

            if _looks_like_section(link):

                discovered_sections.add(link)

            if len(discovered_sections) >= MAX_DISCOVERY_LINKS:
                break

        except Exception:
            continue


    return list(discovered_sections)