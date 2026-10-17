# backend/crawler/site_knowledge_mapper.py

"""
Autonomous Website Knowledge Mapper

Builds a structural map of the university website.

Used to:
• detect departments
• detect faculty directories
• detect exam/result sections
• detect document repositories
• guide crawler expansion
"""

from urllib.parse import urlparse
from collections import defaultdict
from typing import Dict, List
import re


# =========================================================
# STRUCTURE PATTERNS
# =========================================================

SECTION_PATTERNS = {

    "department": [
        "department",
        "dept",
        "faculty",
        "school"
    ],

    "exam": [
        "exam",
        "result",
        "timetable",
        "hallticket",
        "evaluation"
    ],

    "circular": [
        "circular",
        "notice",
        "notification",
        "announcement"
    ],

    "scholarship": [
        "scholarship",
        "financial-aid",
        "grant"
    ],

    "documents": [
        "uploads",
        "documents",
        "files",
        "download",
        "pdf"
    ]
}


# segments that should be ignored
IGNORE_SEGMENTS = {
    "index",
    "home",
    "page",
}


# =========================================================
# CLEAN SEGMENT
# =========================================================

def _clean_segment(segment: str) -> str:

    segment = segment.lower().strip()

    # remove file extension
    segment = re.sub(r"\.(html?|php|aspx?|jsp|pdf|docx?|xlsx?)$", "", segment)

    # remove numbers-only segments
    if segment.isdigit():
        return ""

    if segment in IGNORE_SEGMENTS:
        return ""

    return segment


# =========================================================
# STRUCTURE MAP
# =========================================================

class SiteKnowledgeMapper:

    def __init__(self):

        # domain -> section -> set(paths)
        self.domain_map: Dict[str, Dict[str, set]] = defaultdict(
            lambda: defaultdict(set)
        )

    # =====================================================
    # NORMALIZE PATH
    # =====================================================

    def _get_path_segments(self, url: str) -> List[str]:

        try:

            parsed = urlparse(url)

            path = parsed.path

            if not path:
                return []

            segments = path.strip("/").split("/")

            cleaned = []

            for seg in segments:

                seg = _clean_segment(seg)

                if not seg:
                    continue

                cleaned.append(seg)

            return cleaned

        except Exception:

            return []

    # =====================================================
    # CLASSIFY SECTION
    # =====================================================

    def _classify_segment(self, segment: str) -> str:

        if not segment:
            return "general"

        segment = segment.lower()

        for section, keywords in SECTION_PATTERNS.items():

            for k in keywords:

                if k in segment:
                    return section

        return "general"

    # =====================================================
    # REGISTER URL
    # =====================================================

    def register_url(self, url: str):

        try:

            parsed = urlparse(url)

            domain = parsed.netloc.lower()

            if not domain:
                return

            segments = self._get_path_segments(url)

            if not segments:
                return

            for segment in segments:

                section = self._classify_segment(segment)

                self.domain_map[domain][section].add(segment)

        except Exception:
            return

    # =====================================================
    # GET STRUCTURE
    # =====================================================

    def get_structure(self, domain: str) -> Dict[str, List[str]]:

        domain = domain.lower()

        if domain not in self.domain_map:
            return {}

        return {
            section: sorted(list(paths))
            for section, paths in self.domain_map[domain].items()
        }

    # =====================================================
    # PRIORITY SECTIONS
    # =====================================================

    def get_priority_sections(self, domain: str) -> List[str]:

        domain = domain.lower()

        structure = self.get_structure(domain)

        priority = []

        for section in ["department", "exam", "circular", "scholarship"]:

            if section in structure:

                priority.extend(structure[section])

        return list(set(priority))

    # =====================================================
    # DEBUG MAP
    # =====================================================

    def debug_print(self, domain: str):

        structure = self.get_structure(domain)

        print("\n📊 Site Structure Map")

        for section, paths in structure.items():

            print(f"\n[{section.upper()}]")

            for p in paths:
                print(" -", p)


# =========================================================
# GLOBAL INSTANCE
# =========================================================

site_mapper = SiteKnowledgeMapper()