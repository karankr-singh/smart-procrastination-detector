"""Engine, sessions, schema initialisation and migrations.

Schema update strategy
----------------------
The schema version lives in SQLite's ``PRAGMA user_version``. ``SCHEMA_VERSION`` is the version the
code expects. ``MIGRATIONS[n]`` is a function that upgrades a database from version n-1 to n.
A fresh database is created from the models (already at SCHEMA_VERSION); an older database runs the
missing migrations in order inside one transaction. To change the schema: update models.py, bump
SCHEMA_VERSION, and add a migration (usually an ``ALTER TABLE``) to MIGRATIONS.
"""
from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

import config
from database.models import Base

SCHEMA_VERSION = 1
MIGRATIONS: dict[int, Callable] = {}   # e.g. {2: lambda conn: conn.execute(text("ALTER TABLE ..."))}


class DatabaseError(RuntimeError):
    """Wraps low-level database errors with a message that is safe to show to the user."""


_engine = None
_SessionLocal = None
_db_path: Path | None = None


def configure(db_path: str | Path | None = None):
    """(Re)point the module at a database file and make sure the schema exists."""
    global _engine, _SessionLocal, _db_path
    _db_path = Path(db_path) if db_path else config.DB_PATH
    if str(_db_path) != ":memory:":
        _db_path.parent.mkdir(parents=True, exist_ok=True)
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(f"sqlite:///{_db_path}", connect_args={"check_same_thread": False}, future=True)

    @event.listens_for(_engine, "connect")
    def _fk_on(dbapi_conn, _):  # SQLite ignores foreign keys unless asked
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    _init_schema()
    return _engine


def _init_schema() -> None:
    with _engine.begin() as conn:
        existing = inspect(conn).get_table_names()
        current = conn.execute(text("PRAGMA user_version")).scalar() or 0
        if not existing:
            Base.metadata.create_all(conn)
            conn.execute(text(f"PRAGMA user_version={SCHEMA_VERSION}"))
            return
        Base.metadata.create_all(conn)   # adds any wholly new tables
        for version in range(current + 1, SCHEMA_VERSION + 1):
            migration = MIGRATIONS.get(version)
            if migration:
                migration(conn)
        conn.execute(text(f"PRAGMA user_version={SCHEMA_VERSION}"))


def get_engine():
    if _engine is None:
        configure()
    return _engine


def db_path() -> Path:
    get_engine()
    return _db_path


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commits on success, rolls back on any error."""
    get_engine()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise DatabaseError(f"Database error: {exc.__class__.__name__}. Your change was not saved.") from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def backup_database(dest_dir: Path | None = None) -> Path:
    """Write a consistent copy of the database using SQLite's online backup API."""
    src = db_path()
    dest_dir = Path(dest_dir or config.BACKUP_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"spd_backup_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"
    src_conn = sqlite3.connect(src)
    dst_conn = sqlite3.connect(dest)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    return dest


def restore_hint() -> str:
    return "To restore, stop the app and replace the database file with a backup copy."
