"""Custom exception hierarchy for LaneCore AI."""

from fastapi import Request
from fastapi.responses import JSONResponse


class LaneCoreError(Exception):
    """Base exception for all LaneCore errors."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class PDFValidationError(LaneCoreError):
    """PDF upload validation failed (wrong format, too large, encrypted)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)


class AnalyseError(LaneCoreError):
    """Claude analysis failed or returned unusable result."""

    def __init__(self, message: str, job_id: str | None = None) -> None:
        super().__init__(message, status_code=500)
        self.job_id = job_id


class JobNotFoundError(LaneCoreError):
    """Requested analysis job does not exist."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"Analyse-Job '{job_id}' nicht gefunden.", status_code=404)
        self.job_id = job_id


class StorageError(LaneCoreError):
    """S3/storage operation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class AuthenticationError(LaneCoreError):
    """Auth token invalid or missing."""

    def __init__(self, message: str = "Nicht authentifiziert.") -> None:
        super().__init__(message, status_code=401)


# --- FastAPI Exception Handlers ---

async def lanecore_exception_handler(request: Request, exc: LaneCoreError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
    )
