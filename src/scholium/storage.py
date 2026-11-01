"""Versioned SQLite storage. Read operations never create or migrate a database."""

from contextlib import contextmanager, nullcontext
import os
from pathlib import Path
import sqlite3
import uuid
from datetime import datetime, timezone

SCHEMA_VERSION = 2
APPLICATION_ID = 1396918348


class IndexError(ValueError):
    """Actionable index failure, safe to show without manuscript content."""


SCHEMA = [
    """CREATE TABLE documents (
        id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, chapter TEXT NOT NULL UNIQUE,
        current_revision TEXT REFERENCES revisions(id),
        observed_hash TEXT, last_attempt TEXT, error TEXT)""",
    """CREATE TABLE revisions (
        id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
        source_hash TEXT NOT NULL, parser_version TEXT NOT NULL,
        indexed_at TEXT NOT NULL, previous_revision TEXT REFERENCES revisions(id),
        canonical_json TEXT NOT NULL,
        UNIQUE(document_id, source_hash, parser_version))""",
    """CREATE TABLE blocks (
        revision_id TEXT NOT NULL REFERENCES revisions(id), id TEXT NOT NULL,
        number INTEGER NOT NULL, text TEXT NOT NULL, record_json TEXT NOT NULL,
        PRIMARY KEY(revision_id, id))""",
    """CREATE TABLE notes (
        revision_id TEXT NOT NULL REFERENCES revisions(id), id TEXT NOT NULL,
        type TEXT NOT NULL, word_id TEXT NOT NULL, text TEXT NOT NULL, record_json TEXT NOT NULL,
        PRIMARY KEY(revision_id, id))""",
    """CREATE VIRTUAL TABLE search_records USING fts5(
        document_id UNINDEXED, revision_id UNINDEXED, kind UNINDEXED, locator UNINDEXED,
        text, tokenize='unicode61 remove_diacritics 0')""",
    "CREATE INDEX revisions_document ON revisions(document_id)",
]


EVENT_SCHEMA = """CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id), happened_at TEXT NOT NULL,
    kind TEXT NOT NULL, from_revision TEXT REFERENCES revisions(id),
    to_revision TEXT REFERENCES revisions(id), old_path TEXT, new_path TEXT)"""
SCHEMA.append(EVENT_SCHEMA)


def migrate(connection, data_dir: Path) -> None:
    """Back up schema 1 before an atomic, additive migration. Never mutate on reads."""
    directory = data_dir / "backups"
    directory.mkdir(mode=0o700, exist_ok=True)
    backup_path = directory / f"schema1-{uuid.uuid4()}.sqlite3"
    fd = os.open(backup_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    backup = sqlite3.connect(backup_path)
    try:
        connection.backup(backup)
        if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise IndexError(
                "Pre-migration backup failed integrity validation; index not migrated."
            )
    finally:
        backup.close()
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("PRAGMA user_version").fetchone()[0] == 1:
            connection.execute(EVENT_SCHEMA)
            connection.execute(
                """INSERT INTO events(document_id,happened_at,kind,to_revision,new_path)
                SELECT id,?,'migration_baseline',current_revision,path FROM documents
                WHERE current_revision IS NOT NULL""",
                (datetime.now(timezone.utc).isoformat(),),
            )
            connection.execute("PRAGMA user_version=2")


def db_path(data_dir: Path) -> Path:
    return data_dir / "index.sqlite3"


@contextmanager
def connect(data_dir: Path, *, writable: bool = False):
    from .locks import book_lock

    with book_lock(data_dir) if writable else nullcontext():
        with _connect(data_dir, writable=writable) as connection:
            yield connection


@contextmanager
def _connect(data_dir: Path, *, writable: bool = False):
    path = db_path(data_dir)
    created = False
    if writable:
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(data_dir, 0o700)
        if path.is_symlink():
            raise IndexError("Index file must not be a symlink.")
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            created = True
        except FileExistsError:
            pass
    elif not path.is_file():
        raise IndexError("No index exists. Run scholium ingest --all first.")
    connection = None
    try:
        connection = sqlite3.connect(
            path.as_uri() + ("?mode=rw" if writable else "?mode=ro"), uri=True, timeout=10
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        if created:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                for statement in SCHEMA:
                    connection.execute(statement)
                connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        application = connection.execute("PRAGMA application_id").fetchone()[0]
        if application == APPLICATION_ID and version == 1:
            if not writable:
                raise IndexError(
                    "Index schema 1 needs migration; run scholium ingest --all or watch. A backup will be kept."
                )
            migrate(connection, data_dir)
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version != SCHEMA_VERSION or application != APPLICATION_ID:
            raise IndexError(
                "Unsupported index schema. Keep the database and use its compatible scholium version."
            )
        if not writable:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")  # One consistent snapshot across all retrieval queries.
        yield connection
    except sqlite3.Error as exc:
        raise IndexError(
            "SQLite operation failed; check index integrity, permissions and concurrent writers. Previous committed data is retained."
        ) from exc
    finally:
        if connection is not None:
            connection.close()
