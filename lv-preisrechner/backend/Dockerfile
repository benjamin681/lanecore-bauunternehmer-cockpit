FROM python:3.12-slim

# System-Deps: poppler für PDF-Rendering, libpq für Postgres, Build-Tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Source + pyproject zusammen kopieren (pip install . braucht app/)
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# Render / Fly injecten PORT — fallback 8000
ENV PORT=8000
EXPOSE 8000

# Beim Start: Migrations, dann Uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
