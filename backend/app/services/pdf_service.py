"""PDF processing: validation, conversion to images, enhancement."""

import base64
import io
from dataclasses import dataclass

import pypdf
import structlog
from pdf2image import convert_from_bytes
from PIL import Image, ImageEnhance

from app.core.config import settings
from app.core.exceptions import PDFValidationError

log = structlog.get_logger()


@dataclass
class PDFInfo:
    """Metadata from a PDF before full analysis."""
    num_pages: int
    is_encrypted: bool
    has_text: bool
    size_mb: float
    page_format: str  # e.g. "A0", "A1", "A3", "Custom"


@dataclass
class PageImage:
    """A single PDF page rendered as base64 PNG."""
    page_num: int        # 1-based
    image_base64: str    # PNG base64
    width_px: int
    height_px: int


def validate_pdf(pdf_bytes: bytes) -> PDFInfo:
    """
    Validate a PDF for analysis. Raises PDFValidationError on failure.
    Returns PDFInfo with metadata.
    """
    size_mb = len(pdf_bytes) / (1024 * 1024)

    if size_mb > settings.max_pdf_size_mb:
        raise PDFValidationError(
            f"PDF zu groß: {size_mb:.1f}MB (Max: {settings.max_pdf_size_mb}MB)"
        )

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    except Exception as e:
        raise PDFValidationError(f"PDF kann nicht gelesen werden: {e}") from e

    if reader.is_encrypted:
        raise PDFValidationError(
            "PDF ist passwortgeschützt. Bitte entfernen Sie den Schutz vor dem Upload."
        )

    num_pages = len(reader.pages)
    if num_pages == 0:
        raise PDFValidationError("PDF enthält keine Seiten.")

    if num_pages > settings.max_pages_per_plan:
        raise PDFValidationError(
            f"PDF hat zu viele Seiten: {num_pages} (Max: {settings.max_pages_per_plan})"
        )

    # Check if text-based or scanned
    has_text = False
    for page in reader.pages[:3]:
        text = page.extract_text()
        if text and text.strip():
            has_text = True
            break

    # Determine page format from first page
    first_page = reader.pages[0]
    width_mm = float(first_page.mediabox.width) * 0.352778  # pt → mm
    height_mm = float(first_page.mediabox.height) * 0.352778
    page_format = _classify_page_format(width_mm, height_mm)

    log.info(
        "pdf_validated",
        pages=num_pages,
        size_mb=round(size_mb, 1),
        has_text=has_text,
        format=page_format,
    )

    return PDFInfo(
        num_pages=num_pages,
        is_encrypted=False,
        has_text=has_text,
        size_mb=round(size_mb, 2),
        page_format=page_format,
    )


def pdf_to_images(pdf_bytes: bytes, dpi: int = 200) -> list[PageImage]:
    """
    Convert all PDF pages to base64-encoded PNG images.

    Memory-efficient: converts one page at a time.

    Args:
        pdf_bytes: Raw PDF file content
        dpi: Resolution. 200 = standard, 300 = for poor quality plans

    Returns:
        List of PageImage with base64 data
    """
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    num_pages = len(reader.pages)
    results: list[PageImage] = []

    for page_idx in range(num_pages):
        page_num = page_idx + 1
        log.info("converting_page", page=page_num, total=num_pages, dpi=dpi)

        # Convert single page (memory-efficient, single thread for low-RAM servers)
        images = convert_from_bytes(
            pdf_bytes,
            dpi=dpi,
            first_page=page_num,
            last_page=page_num,
            fmt="PNG",
            thread_count=1,
        )

        if not images:
            log.warning("page_conversion_failed", page=page_num)
            continue

        img = images[0]

        # Enhance for better OCR
        img = _enhance_for_analysis(img)

        # Scale down if too large for Claude Vision (max ~2048px on longest side)
        img = _scale_for_vision(img, max_size=2048)

        # Encode to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        results.append(PageImage(
            page_num=page_num,
            image_base64=image_base64,
            width_px=img.width,
            height_px=img.height,
        ))

        # Free memory
        del images, img, buffer

    log.info("pdf_conversion_complete", pages_converted=len(results), total_pages=num_pages)
    return results


def _enhance_for_analysis(img: Image.Image) -> Image.Image:
    """Improve contrast and sharpness for better plan readability."""
    img = ImageEnhance.Contrast(img).enhance(1.4)
    img = ImageEnhance.Sharpness(img).enhance(1.2)
    return img


def _scale_for_vision(img: Image.Image, max_size: int = 2048) -> Image.Image:
    """Scale image so longest side ≤ max_size pixels."""
    longest = max(img.size)
    if longest <= max_size:
        return img

    ratio = max_size / longest
    new_size = (int(img.width * ratio), int(img.height * ratio))
    log.info("image_scaled", original=img.size, scaled=new_size)
    return img.resize(new_size, Image.LANCZOS)


def _classify_page_format(width_mm: float, height_mm: float) -> str:
    """Determine DIN format from page dimensions."""
    long_side = max(width_mm, height_mm)
    short_side = min(width_mm, height_mm)

    formats = {
        "A4": (297, 210),
        "A3": (420, 297),
        "A2": (594, 420),
        "A1": (841, 594),
        "A0": (1189, 841),
    }

    for name, (l, s) in formats.items():
        if abs(long_side - l) < 15 and abs(short_side - s) < 15:
            return name
    return "Custom"
