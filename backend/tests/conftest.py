"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """Async HTTP test client for FastAPI."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Minimal valid PDF for upload tests."""
    # Minimal valid PDF (1 page, blank)
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n190\n%%EOF"
    )


@pytest.fixture
def large_pdf_bytes() -> bytes:
    """PDF exceeding size limit (>50MB)."""
    # Fake a large file (just enough to fail validation)
    return b"x" * (51 * 1024 * 1024)


@pytest.fixture
def fixture_dir() -> Path:
    """Path to test fixtures directory."""
    return Path(__file__).parent.parent.parent / "tests" / "fixtures"
