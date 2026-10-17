from typing import List, Tuple
from pathlib import Path

import pdfplumber
import pytesseract
import numpy as np
import cv2

from pdf2image import convert_from_path


# ============================================================
# CONFIG
# ============================================================

MIN_TEXT_BLOCK = 40
MIN_TABLE_ROW_LENGTH = 10
TABLE_CHUNK_SIZE = 6

OCR_LANGUAGES = "eng+mar+hin"

OCR_TRIGGER_MIN_TEXT = 80   # trigger OCR only if weak extraction


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

def preprocess_image(img):
    img = np.array(img)

    # safety check
    if len(img.shape) == 2:
        gray = img
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        11,
        2
    )

    return thresh


# ============================================================
# COLUMN SPLIT (IMPROVED)
# ============================================================

def _split_columns(words):

    if not words:
        return [words]

    xs = [w["x0"] for w in words]

    min_x, max_x = min(xs), max(xs)

    if max_x - min_x < 100:  # too narrow → single column
        return [words]

    mid = (min_x + max_x) / 2

    left = [w for w in words if w["x0"] <= mid]
    right = [w for w in words if w["x0"] > mid]

    # avoid false split
    if len(left) < 15 or len(right) < 15:
        return [words]

    return [left, right]


# ============================================================
# LINE GROUPING
# ============================================================

def _group_words_into_lines(words):

    lines = []
    current = []
    current_top = None

    for w in words:

        if not w.get("text"):
            continue

        top = round(w["top"], 1)

        if current_top is None:
            current_top = top

        if abs(top - current_top) <= 6:
            current.append(w["text"])
        else:
            if current:
                lines.append(" ".join(current))
            current = [w["text"]]
            current_top = top

    if current:
        lines.append(" ".join(current))

    return lines


# ============================================================
# MULTI COLUMN EXTRACTION
# ============================================================

def extract_multicolumn_text(page) -> List[str]:

    blocks = []

    try:
        words = page.extract_words()

        if not words:
            return []

        columns = _split_columns(words)

        for col in columns:

            col = sorted(col, key=lambda w: (round(w["top"], 1), w["x0"]))

            lines = _group_words_into_lines(col)

            buffer = []
            size = 0

            for line in lines:

                line = line.strip()

                if len(line) < 5:
                    continue

                buffer.append(line)
                size += len(line)

                if size >= MIN_TEXT_BLOCK:
                    blocks.append(" ".join(buffer))
                    buffer = []
                    size = 0

            if buffer:
                blocks.append(" ".join(buffer))

    except Exception:
        pass

    return blocks


# ============================================================
# TABLE EXTRACTION
# ============================================================

def extract_tables(page) -> List[str]:

    rows = []

    try:
        tables = page.extract_tables()

        for table in tables:

            if not table:
                continue

            for row in table:

                cleaned = [
                    str(c).strip() for c in row if c and str(c).strip()
                ]

                if len(cleaned) < 2:
                    continue

                row_text = " | ".join(cleaned)

                if len(row_text) >= MIN_TABLE_ROW_LENGTH:
                    rows.append(row_text)

    except Exception:
        pass

    return rows


# ============================================================
# OCR (SINGLE PASS)
# ============================================================

def run_ocr(pdf_path: Path):

    text_blocks = []
    table_rows = []

    try:
        images = convert_from_path(pdf_path, dpi=250)

        for i, img in enumerate(images, start=1):

            processed = preprocess_image(img)

            text = pytesseract.image_to_string(
                processed,
                lang=OCR_LANGUAGES,
                config="--oem 3 --psm 6"
            )

            lines = text.split("\n")

            paragraph = []

            for line in lines:

                line = line.strip()

                if not line:
                    continue

                # detect tables
                if "|" in line or "\t" in line or ":" in line:
                    if len(line) >= MIN_TABLE_ROW_LENGTH:
                        table_rows.append(line)
                    continue

                paragraph.append(line)

                if len(" ".join(paragraph)) >= MIN_TEXT_BLOCK:
                    text_blocks.append((i, " ".join(paragraph)))
                    paragraph = []

            if paragraph:
                text_blocks.append((i, " ".join(paragraph)))

    except Exception:
        pass

    return text_blocks, table_rows


# ============================================================
# MAIN PARSER (FINAL)
# ============================================================

def parse_pdf_layout(pdf_path: Path) -> Tuple[List[Tuple[int, str]], List[str]]:

    text_blocks = []
    table_rows = []

    total_text_len = 0

    # ---------------- NORMAL EXTRACTION ----------------
    try:
        with pdfplumber.open(pdf_path) as pdf:

            for i, page in enumerate(pdf.pages, start=1):

                blocks = extract_multicolumn_text(page)

                for b in blocks:
                    if b.strip():
                        text_blocks.append((i, b))
                        total_text_len += len(b)

                rows = extract_tables(page)
                table_rows.extend(rows)

    except Exception:
        pass

    print("📄 Extracted text length:", total_text_len)

    # ---------------- OCR (SAFE FALLBACK) ----------------
    if total_text_len < OCR_TRIGGER_MIN_TEXT:

        print("🧠 OCR triggered")

        ocr_text, ocr_tables = run_ocr(pdf_path)

        # 🔥 IMPORTANT FIX: DO NOT overwrite if OCR worse
        if ocr_text and len(ocr_text) > len(text_blocks):
            text_blocks = ocr_text

        if ocr_tables:
            table_rows.extend(ocr_tables)

    # ---------------- TABLE CHUNKS ----------------
    chunks = []
    buffer = []

    for row in table_rows:

        buffer.append(row)

        if len(buffer) >= TABLE_CHUNK_SIZE:
            chunks.append("\n".join(buffer))
            buffer = []

    if buffer:
        chunks.append("\n".join(buffer))

    return text_blocks, chunks