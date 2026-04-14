FROM python:3.12-slim

# poppler for PDF → image conversion, libpq for PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir hatchling && pip install --no-cache-dir .

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head 2>/dev/null; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
