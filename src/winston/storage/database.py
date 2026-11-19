"""Database connection and session management."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from winston.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            str(settings.database_url),
            echo=False,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _session_factory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a database session with automatic cleanup.
    
    Usage:
        with get_session() as session:
            # do work
            session.commit()
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database() -> None:
    """Initialize the database schema using Alembic migrations."""
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    
    # Find alembic.ini relative to this file
    alembic_ini = Path(__file__).parent.parent.parent.parent / "alembic.ini"
    
    if not alembic_ini.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")
    
    alembic_cfg = Config(str(alembic_ini))
    command.upgrade(alembic_cfg, "head")


def check_connection() -> dict[str, Any]:
    """Check database connection and return status."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            return {
                "status": "ok",
                "connected": True,
                "version": version,
            }
    except Exception as e:
        return {
            "status": "error",
            "connected": False,
            "error": str(e),
        }


def reset_connection() -> None:
    """Reset the database connection (useful for testing)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
