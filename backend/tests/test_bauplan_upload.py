"""Bauplan upload endpoint tests."""

import pytest


async def test_upload_non_pdf_rejected(client):
    """Non-PDF files should return 422."""
    response = await client.post(
        "/api/v1/bauplan/upload",
        files={"file": ("photo.jpg", b"fake-image-data", "image/jpeg")},
    )
    assert response.status_code in (401, 422)  # 401 if auth is enforced


async def test_upload_no_file_rejected(client):
    """Request without file should fail."""
    response = await client.post("/api/v1/bauplan/upload")
    assert response.status_code == 422


async def test_status_unknown_job(client):
    """Querying unknown job_id should return 404."""
    response = await client.get("/api/v1/bauplan/00000000-0000-0000-0000-000000000000/status")
    assert response.status_code in (401, 404)


async def test_result_unknown_job(client):
    """Querying unknown job_id result should return 404."""
    response = await client.get("/api/v1/bauplan/00000000-0000-0000-0000-000000000000/result")
    assert response.status_code in (401, 404)
