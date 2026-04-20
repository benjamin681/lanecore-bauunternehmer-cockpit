"""Bauplan upload endpoint tests."""

import pytest


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


async def test_unknown_job_status_and_result(client):
    """Querying unknown job_id should return 404 for both status and result."""
    # Status endpoint
    resp_status = await client.get("/api/v1/bauplan/00000000-0000-0000-0000-000000000000/status")
    assert resp_status.status_code == 404

    # Result endpoint (same session, avoids event loop issue)
    resp_result = await client.get("/api/v1/bauplan/00000000-0000-0000-0000-000000000000/result")
    assert resp_result.status_code == 404
