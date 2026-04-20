"""Pytest conftest: In-Memory-DB pro Test, FastAPI TestClient."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Generator

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-dummy")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def tmp_sqlite(monkeypatch) -> Generator[Path, None, None]:
    """Pro Test frische DB unter tmp-Dir."""
    tmpdir = tempfile.TemporaryDirectory()
    data_dir = Path(tmpdir.name)
    monkeypatch.setattr("app.core.config.settings.data_dir", data_dir)
    # SQLite-URL wird aus data_dir gelesen
    yield data_dir
    tmpdir.cleanup()


@pytest.fixture
def client(tmp_sqlite) -> Generator[TestClient, None, None]:
    # Engine/Session für diesen Test neu bauen
    from app.core import database

    engine = create_engine(
        f"sqlite:///{tmp_sqlite / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    database.engine = engine
    database.SessionLocal = TestSession

    # Re-bind SessionLocal in Modulen, die es statisch importiert haben.
    # Wichtig fuer Background-Worker, die ueber `from ... import SessionLocal`
    # eine fruehe Referenz auf die urspruengliche Session-Factory halten.
    import sys
    for mod_name in list(sys.modules.keys()):
        if not mod_name.startswith("app."):
            continue
        mod = sys.modules[mod_name]
        if hasattr(mod, "SessionLocal"):
            try:
                setattr(mod, "SessionLocal", TestSession)
            except Exception:  # noqa: BLE001
                pass

    database.init_db()

    from app.main import app

    with TestClient(app) as c:
        yield c
