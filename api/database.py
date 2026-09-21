"""Database configuration for user and authentication data.

The organization registry remains read-only and is loaded from CSV files. This
module owns only application data such as user accounts and login sessions.
"""
from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DATABASE_PATH = (_ROOT / "storage" / "users.db").resolve()
DEFAULT_DATABASE_URL = f"sqlite:///{_DEFAULT_DATABASE_PATH.as_posix()}"


def _normalize_database_url(database_url: str) -> str:
    """Use SQLAlchemy's explicit psycopg 3 driver for Render Postgres URLs."""

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


DATABASE_URL = _normalize_database_url(
    os.getenv("USER_DATABASE_URL", DEFAULT_DATABASE_URL).strip() or DEFAULT_DATABASE_URL
)


class Base(DeclarativeBase):
    """Base class for application database models."""


def _ensure_sqlite_directory(database_url: str) -> None:
    if not database_url.startswith("sqlite:///") or database_url == "sqlite:///:memory:":
        return
    database_path = database_url.removeprefix("sqlite:///")
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory(DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)


if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _configure_sqlite(connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def initialize_database() -> None:
    """Create missing application tables without touching existing records."""

    # Import models here so their metadata has been registered before create_all.
    from api import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_database() -> Generator[Session, None, None]:
    """FastAPI dependency that provides one database session per request."""

    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
