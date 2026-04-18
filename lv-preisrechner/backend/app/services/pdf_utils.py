"""PDF-Helpers: PDF → Seiten-Bilder (base64) für Claude Vision."""

from __future__ import annotations

import base64
import gc
import hashlib
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import fitz  # PyMuPDF
import structlog

log = structlog.get_logger()


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pdf_to_page_images(
    pdf_bytes: bytes,
    *,
    dpi: int = 200,
    max_pages: int = 60,
    max_pixels_single: int = 3500,
    max_pixels_multi: int = 1800,
) -> list[dict]:
    """Rendert jede PDF-Seite als PNG und gibt Claude-kompatible Image-Blöcke zurück.

    Claude begrenzt bei Multi-Image-Requests die Dimensionen auf 2000px pro Seite.
    Wir downsamplen auf 1800px wenn >1 Seite, ansonsten bis 3500px.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    blocks: list[dict] = []
    try:
        total_pages = min(doc.page_count, max_pages)
        max_pixels = max_pixels_single if total_pages == 1 else max_pixels_multi

        for i in range(total_pages):
            page = doc.load_page(i)
            # DPI → scale: 72 DPI = 1.0
            scale = dpi / 72.0
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            # Downscale wenn zu groß
            if max(pix.width, pix.height) > max_pixels:
                ratio = max_pixels / max(pix.width, pix.height)
                mat = fitz.Matrix(scale * ratio, scale * ratio)
                pix = page.get_pixmap(matrix=mat, alpha=False)
            png_bytes = pix.tobytes("png")
            b64 = base64.b64encode(png_bytes).decode("ascii")
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64,
                    },
                }
            )
        if doc.page_count > max_pages:
            log.warning(
                "pdf_truncated",
                total=doc.page_count,
                processed=max_pages,
            )
        return blocks
    finally:
        doc.close()


def pdf_total_pages(pdf_bytes: bytes, max_pages: int = 80) -> int:
    """Schneller Pagecount ohne Rendering."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return min(doc.page_count, max_pages)
    finally:
        doc.close()


def pdf_batch_images(
    pdf_bytes: bytes,
    *,
    batch_start: int,
    batch_size: int,
    dpi: int = 200,
    max_pixels: int = 1800,
) -> list[dict]:
    """Rendert nur einen Seiten-Batch on-demand (spart RAM bei großen PDFs)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total = doc.page_count
        end = min(batch_start + batch_size, total)
        blocks: list[dict] = []
        for i in range(batch_start, end):
            page = doc.load_page(i)
            scale = dpi / 72.0
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            if max(pix.width, pix.height) > max_pixels:
                ratio = max_pixels / max(pix.width, pix.height)
                mat = fitz.Matrix(scale * ratio, scale * ratio)
                pix = page.get_pixmap(matrix=mat, alpha=False)
            png_bytes = pix.tobytes("png")
            blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(png_bytes).decode("ascii"),
                },
            })
            del pix, png_bytes
        gc.collect()
        return blocks
    finally:
        doc.close()


def save_upload(pdf_bytes: bytes, dest_dir: Path, suggested_name: str) -> Path:
    """Speichert die Upload-Datei mit sicherem Dateinamen."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    sha = compute_sha256(pdf_bytes)
    safe = "".join(c for c in suggested_name if c.isalnum() or c in "._- ")[:80]
    if not safe.lower().endswith(".pdf"):
        safe = f"{safe}.pdf"
    filename = f"{sha[:12]}_{safe}"
    path = dest_dir / filename
    path.write_bytes(pdf_bytes)
    return path


def extract_text_per_page(pdf_bytes: bytes) -> list[str]:
    """Extrahiert Text pro Seite via PyMuPDF (schneller als pdfplumber, ähnliche Qualität)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [doc.load_page(i).get_text("text") for i in range(doc.page_count)]
    finally:
        doc.close()
