"""Bauplan upload endpoint tests."""

import pytest


async def test_upload_pdf_accepted(client, sample_pdf_bytes):
    """Valid PDF upload should return 202 with job_id."""
    response = await client.post(
        "/api/v1/bauplan/upload",
        files={"file": ("grundriss.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert response.status_code in (200, 202)
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"


async def test_upload_non_pdf_rejected(client):
    """Non-PDF files should return 422."""
    response = await client.post(
        "/api/v1/bauplan/upload",
        files={"file": ("photo.jpg", b"fake-image-data", "image/jpeg")},
    )
    assert response.status_code == 422


async def test_upload_no_file_rejected(client):
    """Request without file should fail."""
    response = await client.post("/api/v1/bauplan/upload")
    assert response.status_code == 422


async def test_status_unknown_job(client):
    """Querying unknown job_id should return 404 or valid pending status."""
    response = await client.get("/api/v1/bauplan/nonexistent-id/status")
    # Acceptable: 404 (not found) or 200 with status
    assert response.status_code in (200, 404)


async def test_result_unknown_job(client):
    """Querying unknown job_id result should return 404."""
    response = await client.get("/api/v1/bauplan/nonexistent-id/result")
    assert response.status_code == 404
