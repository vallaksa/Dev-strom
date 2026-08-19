"""
Database connection service.

Exposes:
  - get_engine() : lazily-created SQLAlchemy engine (use for raw SQL or Alembic)
  - Base         : declarative base for ORM models
  - get_session(): context manager that auto-commits on success, rolls back on error
  - ping()       : trivial connectivity check, used by GET /ready

The engine is created LAZILY (on first use) rather than at import time, so
`import app` / `import app.api` never crashes just because DATABASE_URL is
unset — e.g. running the idea-generation graph without a database, or
importing the module for a health check. Anything that actually needs the
database (get_session(), ping()) raises a clear RuntimeError if DATABASE_URL
was never configured.
"""

from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Resolve .env relative to this file's location so it works from any CWD.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# ── lazy engine ────────────────────────────────────────────────────────────────
# DATABASE_URL is read from typed config (app.config.settings), which in turn
# reads it from the environment / .env — no hardcoded credentials anywhere.
# Format: postgresql://user:password@host:port/dbname
_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine, creating it on first use.

    Raises:
        RuntimeError: if DATABASE_URL is not configured.
    """
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL is not set. Configure it in .env to use "
                "database-backed features (runs, expanded ideas, history)."
            )
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,      # test connections before use (handles stale connections)
            pool_size=5,             # max permanent connections in pool
            max_overflow=10,         # extra connections allowed under burst load
            echo=False,              # set True to log every SQL statement for debugging
        )
    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _SessionFactory


# ── declarative base ───────────────────────────────────────────────────────────
# ORM model classes created in V3-3 will inherit from this.
class Base(DeclarativeBase):
    pass


# ── session context manager ────────────────────────────────────────────────────
@contextmanager
def get_session():
    """Open a database session, commit on success, roll back on any error.

    Usage:
        with get_session() as session:
            session.add(some_model_instance)
            # commit happens automatically on exit

    Raises:
        RuntimeError: if DATABASE_URL is not configured.
        Any exception from the database layer — callers should handle or let
        it propagate to the FastAPI exception handler.
    """
    session: Session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── connectivity smoke test ─────────────────────────────────────────────────────
def ping() -> str:
    """Run a trivial query to verify the database is reachable.
    Returns the PostgreSQL server version string on success.

    Raises:
        RuntimeError: if DATABASE_URL is not configured.
    """
    with get_engine().connect() as conn:
        row = conn.execute(text("SELECT version()")).scalar()
    return row
