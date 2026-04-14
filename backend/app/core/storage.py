"""S3-compatible storage operations for PDF uploads."""

import aioboto3
import structlog

from app.core.config import settings
from app.core.exceptions import StorageError

log = structlog.get_logger()


class StorageService:
    """Async S3 operations for PDF storage."""

    def __init__(self) -> None:
        self._session = aioboto3.Session()

    def _client_kwargs(self) -> dict:
        return {
            "region_name": settings.aws_region,
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }

    async def upload_pdf(self, pdf_bytes: bytes, job_id: str, filename: str) -> str:
        """Upload PDF to S3. Returns the S3 key."""
        key = f"uploads/{job_id}/{filename}"

        try:
            async with self._session.client("s3", **self._client_kwargs()) as s3:
                await s3.put_object(
                    Bucket=settings.s3_bucket_name,
                    Key=key,
                    Body=pdf_bytes,
                    ContentType="application/pdf",
                    ServerSideEncryption="AES256",
                )
        except Exception as e:
            log.error("s3_upload_failed", key=key, error=str(e))
            raise StorageError(f"PDF-Upload fehlgeschlagen: {e}") from e

        log.info("pdf_uploaded", key=key, size_bytes=len(pdf_bytes))
        return key

    async def download_pdf(self, key: str) -> bytes:
        """Download PDF from S3."""
        try:
            async with self._session.client("s3", **self._client_kwargs()) as s3:
                response = await s3.get_object(Bucket=settings.s3_bucket_name, Key=key)
                return await response["Body"].read()
        except Exception as e:
            log.error("s3_download_failed", key=key, error=str(e))
            raise StorageError(f"PDF-Download fehlgeschlagen: {e}") from e

    async def delete_pdf(self, key: str) -> None:
        """Delete PDF from S3."""
        try:
            async with self._session.client("s3", **self._client_kwargs()) as s3:
                await s3.delete_object(Bucket=settings.s3_bucket_name, Key=key)
        except Exception as e:
            log.error("s3_delete_failed", key=key, error=str(e))
            raise StorageError(f"PDF-Löschung fehlgeschlagen: {e}") from e


storage = StorageService()
