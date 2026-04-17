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
    """A single PDF page rendered as base64 image."""
    page_num: int        # 1-based
    image_base64: str    # base64-encoded image
    width_px: int
    height_px: int
    media_type: str = "image/png"  # "image/png" or "image/jpeg"


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

    Memory-efficient: converts one page at a time with explicit GC.

    Args:
        pdf_bytes: Raw PDF file content
        dpi: Resolution. 200 = standard, 300 = for poor quality plans

    Returns:
        List of PageImage with base64 data
    """
    import gc

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

        try:
            # Enhance for better OCR
            img = _enhance_for_analysis(img)

            # Claude Vision accepts up to 8000x8000 px and 5MB per image.
            # For construction plans we want MAX detail — only scale if really huge.
            # Target: ~3500px longest side keeps plan legibility without hitting 5MB.
            import os as _os
            max_px = int(_os.getenv("VISION_MAX_PX", "3500"))
            img = _scale_for_vision(img, max_size=max_px)

            # Encode to base64 — keep trying lower quality until under 4.5MB
            image_base64, buffer, media_type = _encode_under_limit(img, max_bytes=int(4.5 * 1024 * 1024))
            png_bytes = buffer.getvalue() if buffer else b""

            results.append(PageImage(
                page_num=page_num,
                image_base64=image_base64,
                width_px=img.width,
                height_px=img.height,
                media_type=media_type,
            ))
        finally:
            # Always free memory, also on exceptions
            try:
                img.close()
            except Exception:
                pass
            for pil_img in images:
                try:
                    pil_img.close()
                except Exception:
                    pass
            del images, img, buffer, png_bytes
            gc.collect()

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


def _encode_under_limit(img: Image.Image, max_bytes: int = 4_500_000) -> tuple[str, io.BytesIO, str]:
    """Encode image to base64; progressively reduce size if over max_bytes.

    Returns (base64_str, buffer, media_type).

    Strategy:
      1. Try PNG optimized
      2. If too big → JPEG q=92
      3. If still too big → scale down 15% and retry JPEG
    """
    # Attempt 1: PNG
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    data = buffer.getvalue()
    if len(data) <= max_bytes:
        return base64.b64encode(data).decode("utf-8"), buffer, "image/png"

    # Attempt 2: JPEG q=92 (baupläne sind mostly B/W, kompression OK)
    buffer2 = io.BytesIO()
    img_rgb = img.convert("RGB") if img.mode != "RGB" else img
    img_rgb.save(buffer2, format="JPEG", quality=92, optimize=True)
    data = buffer2.getvalue()
    if len(data) <= max_bytes:
        log.info("image_encoded_jpeg", reason="png_too_big", size_mb=round(len(data)/1_000_000, 2))
        return base64.b64encode(data).decode("utf-8"), buffer2, "image/jpeg"

    # Attempt 3: Scale 85% + JPEG q=90
    new_w = int(img.width * 0.85)
    new_h = int(img.height * 0.85)
    img_scaled = img.resize((new_w, new_h), Image.LANCZOS)
    img_scaled_rgb = img_scaled.convert("RGB") if img_scaled.mode != "RGB" else img_scaled
    buffer3 = io.BytesIO()
    img_scaled_rgb.save(buffer3, format="JPEG", quality=90, optimize=True)
    data = buffer3.getvalue()
    log.warning("image_shrunk_to_fit", final_size_mb=round(len(data)/1_000_000, 2), new_dim=(new_w, new_h))
    return base64.b64encode(data).decode("utf-8"), buffer3, "image/jpeg"


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
