# backend/ingestion/pdf_semantic_chunker.py

import re
from typing import List, Tuple, Dict


# ============================================================
# HEADING PATTERNS (🔥 EXPANDED)
# ============================================================

HEADING_PATTERNS = [
    r"^\d+\.\s+.+",                      # 1. Introduction
    r"^\d+\.\d+\s+.+",                  # 1.1 Overview
    r"^\d+\)\s+.+",                     # 1) Item
    r"^[IVX]+\.\s+.+",                  # I. Section
    r"^[A-Z][A-Z\s]{5,}$",              # ALL CAPS
    r"^Department of .+",
    r"^Faculty of .+",
    r"^About .+",
    r"^Course(s)? Offered",
    r"^Eligibility",
    r"^Contact",
    r"^Duration",
    r"^Fees?",
    r"^Syllabus",
    r"^Notice",
    r"^Circular",
    r"^Scholarship",
    r"^Event",
]

heading_regex = re.compile("|".join(HEADING_PATTERNS), re.IGNORECASE)


# ============================================================
# CLEAN LINE
# ============================================================

def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


# ============================================================
# HEADING DETECTOR (🔥 IMPROVED)
# ============================================================

def is_heading(line: str) -> bool:

    if not line:
        return False

    line = _clean_line(line)

    if len(line) < 4:
        return False

    # Pattern match
    if heading_regex.match(line):
        return True

    # Title Case (short)
    if len(line) < 80 and line.istitle():
        return True

    # Ends with colon → strong signal
    if line.endswith(":") and len(line) < 100:
        return True

    # Mixed caps (e.g., "Course Details")
    words = line.split()
    if len(words) <= 8 and all(w[0].isupper() for w in words if w.isalpha()):
        return True

    return False


# ============================================================
# MERGE SMALL BLOCKS
# ============================================================

def _merge_small_sections(sections: List[Dict]) -> List[Dict]:

    merged = []
    buffer = None

    for sec in sections:

        text = sec["text"].strip()

        # If very small → merge with previous
        if len(text) < 80 and buffer:

            buffer["text"] += "\n" + text

        else:

            if buffer:
                merged.append(buffer)

            buffer = sec

    if buffer:
        merged.append(buffer)

    return merged


# ============================================================
# MAIN CHUNKER
# ============================================================

def chunk_by_sections(text_blocks: List[Tuple[int, str]]) -> List[Dict]:

    sections: List[Dict] = []

    current_heading = "General"
    buffer = []
    current_page = -1

    for page_no, text in text_blocks:

        # 🔥 CLEAN SPLIT
        lines = [
            _clean_line(l)
            for l in text.split("\n")
            if _clean_line(l)
        ]

        for line in lines:

            if is_heading(line):

                # SAVE PREVIOUS SECTION
                if buffer:
                    sections.append({
                        "heading": current_heading,
                        "text": "\n".join(buffer).strip(),
                        "page": current_page
                    })
                    buffer = []

                current_heading = line
                current_page = page_no

            else:
                buffer.append(line)

    # FINAL SECTION
    if buffer:
        sections.append({
            "heading": current_heading,
            "text": "\n".join(buffer).strip(),
            "page": current_page
        })

    # --------------------------------------------------------
    # 🔥 POST PROCESSING (CRITICAL)
    # --------------------------------------------------------

    # Remove empty
    sections = [
        s for s in sections
        if s["text"] and len(s["text"].strip()) > 20
    ]

    # Merge small noisy chunks
    sections = _merge_small_sections(sections)

    return sections