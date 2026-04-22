# syntax=docker/dockerfile:1.6
#
# B+4.3.2b-1: Multi-Stage-Dockerfile fuer Hetzner-Deployment.
#
# Kompatibel mit Render.com (wird weiterhin ueber render.yaml geplant).
# Erweiterungen gegenueber dem vorherigen Single-Stage-Build:
#   * Multi-Stage (builder + runtime) reduziert das Runtime-Image
#     (gcc, build-essential, libpq-dev bleiben im Builder).
#   * Non-root User `appuser` (UID 1000) im Runtime-Image.
#   * HEALTHCHECK-Directive gegen /api/v1/health.
#   * Dependency-Layer separat gecacht: pyproject.toml + minimales
#     app/__init__.py im Builder triggern pip install. Der echte
#     app-Code wird erst in der Runtime-Stage kopiert, mit
#     PYTHONPATH-Priorisierung damit der aktuelle Code gegenueber
#     dem ausinstallierten Stub gewinnt.

# =========================================================================
# Stage 1 — Builder: Python-Deps in venv installieren
# =========================================================================
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN /opt/venv/bin/pip install --upgrade pip

WORKDIR /build

# Nur pyproject.toml + Stub-App-Paket kopieren. So wird der
# Dependency-Install-Layer gecacht, solange pyproject.toml gleich bleibt.
# Der echte App-Code wird erst in der Runtime-Stage nachgezogen.
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py
RUN /opt/venv/bin/pip install .

# =========================================================================
# Stage 2 — Runtime: schlankes Laufzeit-Image
# =========================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000 \
    # PYTHONPATH priorisiert den Code im WORKDIR ueber den ausinstallierten
    # Stub in /opt/venv/lib/.../site-packages — so laeuft immer der
    # aktuelle Code, selbst wenn pip install . ein leeres Stub-Package
    # in venv hinterlassen hat.
    PYTHONPATH=/home/appuser/app

# Runtime-Deps: poppler fuer PDF-Rendering, libpq5 (runtime libraries fuer
# psycopg2), curl fuer HEALTHCHECK. build-essential + libpq-dev wurden
# bewusst weggelassen.
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 appuser

# venv aus dem Builder uebernehmen
COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv

WORKDIR /home/appuser/app
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini ./

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/v1/health" || exit 1

# Migrations laufen beim Start, dann Uvicorn. Render injiziert PORT;
# Hetzner / docker-compose nutzt den Default 8000 aus ENV.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
