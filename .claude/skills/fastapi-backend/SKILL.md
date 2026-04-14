# Skill: FastAPI Backend Patterns

## Projekt-Struktur Konvention

```
app/
├── main.py              # FastAPI-App, Middleware, Router-Registrierung
├── api/
│   └── routes/
│       ├── bauplan.py   # Bauplan-Endpunkte
│       ├── projekte.py  # Projekt-Management
│       └── health.py
├── core/
│   ├── config.py        # Settings via pydantic-settings
│   ├── database.py      # DB-Session, Engine
│   ├── dependencies.py  # FastAPI Dependencies (Auth, DB-Session)
│   └── exceptions.py    # Custom Exceptions + Handler
├── models/              # SQLAlchemy ORM-Modelle
├── schemas/             # Pydantic Schemas (Request/Response)
└── services/            # Business Logic (kein SQL hier)
```

---

## Async Database mit SQLAlchemy

```python
# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=40,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Dependency für Routes
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

---

## Dependency Injection Pattern

```python
# app/core/dependencies.py
from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> str:
    """Clerk JWT validieren und User-ID zurückgeben.
    Im Dev-Mode (kein CLERK_SECRET_KEY): gibt 'dev-user' zurück.
    Implementierung: siehe app/core/auth.py"""
    ...

# In Route verwenden:
@router.post("/upload")
async def upload(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ...
```

---

## Fehlerbehandlung

```python
# app/core/exceptions.py
from fastapi import Request
from fastapi.responses import JSONResponse

class LaneCoreError(Exception):
    """Base Exception."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code

class AnalyseError(LaneCoreError):
    """Claude-Analyse fehlgeschlagen."""
    def __init__(self, message: str, job_id: str):
        super().__init__(message, 422)
        self.job_id = job_id

# In main.py registrieren:
@app.exception_handler(LaneCoreError)
async def lanecore_exception_handler(request: Request, exc: LaneCoreError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
    )
```

---

## Background Tasks für lange Analysen

```python
from fastapi import BackgroundTasks
import asyncio

@router.post("/upload")
async def upload_and_analyse(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    # 1. PDF sofort speichern
    job = await create_analyse_job(db, filename=file.filename)

    # 2. Analyse im Hintergrund starten (non-blocking)
    background_tasks.add_task(run_analyse_pipeline, job.id, await file.read())

    # 3. Sofort mit Job-ID antworten (202 Accepted)
    return JSONResponse(
        status_code=202,
        content={"job_id": str(job.id), "status": "pending"},
    )

async def run_analyse_pipeline(job_id: str, pdf_bytes: bytes):
    """Läuft im Hintergrund — aktualisiert DB-Status."""
    async with AsyncSessionLocal() as db:
        await update_job_status(db, job_id, "processing")
        try:
            result = await bauplan_service.analyse(pdf_bytes)
            await save_result(db, job_id, result)
            await update_job_status(db, job_id, "completed")
        except Exception as e:
            await update_job_status(db, job_id, "failed", error=str(e))
```

---

## File Upload mit Validierung

```python
from fastapi import UploadFile, File
from app.core.config import settings

async def validate_pdf_upload(file: UploadFile = File(...)) -> bytes:
    """Dependency: PDF validieren und lesen."""
    if not file.content_type == "application/pdf":
        raise HTTPException(422, "Nur PDF-Dateien erlaubt")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)

    if size_mb > settings.max_pdf_size_mb:
        raise HTTPException(422, f"Datei zu groß: {size_mb:.1f}MB (Max: {settings.max_pdf_size_mb}MB)")

    return content
```

---

## Testing Pattern

```python
# tests/test_bauplan_routes.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_upload_pdf(client, sample_pdf_bytes):
    response = await client.post(
        "/api/v1/bauplan/upload",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 202
    assert "job_id" in response.json()
```
