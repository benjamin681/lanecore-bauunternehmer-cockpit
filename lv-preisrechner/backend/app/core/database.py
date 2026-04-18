"""SQLite + SQLAlchemy Setup."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Shared SQLAlchemy base for all ORM models.

    Alle Tabellen werden mit Prefix `lvp_` angelegt (LV-Preisrechner),
    um Kollisionen mit anderen Anwendungen in derselben Postgres-DB
    zu vermeiden (z.B. geteilte Cockpit-DB).
    """


def _build_engine():
    """Engine mit DB-spezifischer Konfiguration."""
    if settings.is_sqlite:
        return create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False, "timeout": 30},
            echo=False,
        )
    # PostgreSQL / andere: Connection Pool, Pre-Ping gegen stale connections
    return create_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=False,
    )


engine = _build_engine()


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    """WAL-Modus + busy_timeout: nur auf SQLite anwenden."""
    if not settings.is_sqlite:
        return
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:  # noqa: BLE001
        pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency: DB-Session pro Request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Lege Tabellen an. Idempotent — kann mehrfach aufgerufen werden."""
    # Import models so SQLAlchemy knows about them
    from app.models import (  # noqa: F401
        user,
        tenant,
        price_list,
        price_entry,
        lv,
        position,
        job,
    )

    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    # `python -m app.core.database` legt Tabellen an
    init_db()
    print(f"DB initialisiert: {settings.database_url}")
