"""Tests for PDF processing service."""

import pytest
from app.services.pdf_service import validate_pdf, _classify_page_format
from app.core.exceptions import PDFValidationError


def test_validate_pdf_valid(sample_pdf_bytes):
    """Valid minimal PDF should pass validation."""
    info = validate_pdf(sample_pdf_bytes)
    assert info.num_pages == 1
    assert info.is_encrypted is False
    assert info.size_mb < 1.0


def test_validate_pdf_too_large(large_pdf_bytes):
    """PDF over 50MB should be rejected."""
    with pytest.raises(PDFValidationError, match="zu groß"):
        validate_pdf(large_pdf_bytes)


def test_validate_pdf_not_a_pdf():
    """Non-PDF bytes should be rejected."""
    with pytest.raises(PDFValidationError, match="nicht gelesen"):
        validate_pdf(b"this is not a PDF")


def test_validate_pdf_empty():
    """Empty bytes should be rejected."""
    with pytest.raises(PDFValidationError):
        validate_pdf(b"")


def test_classify_page_format_a0():
    assert _classify_page_format(1189, 841) == "A0"


def test_classify_page_format_a1():
    assert _classify_page_format(841, 594) == "A1"


def test_classify_page_format_a3():
    assert _classify_page_format(420, 297) == "A3"


def test_classify_page_format_a4():
    assert _classify_page_format(297, 210) == "A4"


def test_classify_page_format_a4_landscape():
    """Landscape orientation should still detect correct format."""
    assert _classify_page_format(210, 297) == "A4"


def test_classify_page_format_custom():
    assert _classify_page_format(500, 400) == "Custom"


def test_classify_page_format_tolerance():
    """Should detect A3 even with small deviation."""
    assert _classify_page_format(425, 300) == "A3"
