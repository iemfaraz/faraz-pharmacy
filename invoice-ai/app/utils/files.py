"""File handling utilities: validation, safe storage, preview rendering.

Kept separate from the UI so Milestone 3+ (and later the FastAPI layer)
can reuse the same logic without importing Streamlit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import pymupdf as fitz  # modern import name; "fitz" alias kept for brevity
from PIL import Image

import config


@dataclass
class ValidationResult:
    ok: bool
    error: str = ""


def validate_upload(filename: str, size_bytes: int) -> ValidationResult:
    """Check extension and size against config limits."""
    ext = Path(filename).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(config.ALLOWED_EXTENSIONS))
        return ValidationResult(False, f"Unsupported file type '{ext}'. Allowed: {allowed}")

    max_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        actual_mb = size_bytes / (1024 * 1024)
        return ValidationResult(
            False, f"File is {actual_mb:.1f} MB — limit is {config.MAX_FILE_SIZE_MB} MB."
        )
    if size_bytes == 0:
        return ValidationResult(False, "File is empty.")
    return ValidationResult(True)


def save_upload(file_bytes: bytes, original_filename: str) -> Path:
    """Store bytes under a UUID name (never trust client filenames).

    Returns the saved path. Original extension is preserved (lowercased)
    so downstream code can branch on suffix.
    """
    ext = Path(original_filename).suffix.lower()
    dest = config.UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(file_bytes)
    return dest


def is_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


def pdf_page_count(path: Path) -> int:
    with fitz.open(path) as doc:
        return doc.page_count


def render_pdf_page(path: Path, page_number: int = 0, dpi: int | None = None) -> Image.Image:
    """Rasterize one PDF page (0-indexed) to a PIL image.

    Used for preview now (Milestone 2) and OCR input later (Milestone 3),
    which is why DPI comes from config rather than being hardcoded.
    """
    dpi = dpi or config.PDF_RENDER_DPI
    with fitz.open(path) as doc:
        if not 0 <= page_number < doc.page_count:
            raise ValueError(f"Page {page_number} out of range (document has {doc.page_count})")
        page = doc[page_number]
        pix = page.get_pixmap(dpi=dpi)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def load_preview(path: Path, page_number: int = 0) -> Image.Image:
    """Return a PIL image for any supported upload (image or PDF page)."""
    if is_pdf(path):
        return render_pdf_page(path, page_number)
    return Image.open(path)
