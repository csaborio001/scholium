"""Incremental ingestion and explicit source-hash reconciliation."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

from .config import Config
from .docx_reader import PARSER_VERSION, ExtractionError, extract, source_hash
from .storage import IndexError, connect, db_path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def in_sources(path: Path, config: Config) -> bool:
    return any(root == path or root in path.parents for root in config.source_dirs)


def scan(config: Config) -> tuple[list[Path], list[dict]]:
    files, errors, seen = [], [], set()
    for root in config.source_dirs:
        if not root.is_dir():
            errors.append(dict(path=str(root), error="Source directory unavailable"))
            continue

        def onerror(error):
            errors.append(dict(path=str(error.filename), error="Cannot scan source directory"))

        for directory, dirs, names in os.walk(root, followlinks=False, onerror=onerror):
            dirs[:] = sorted(name for name in dirs if not (Path(directory) / name).is_symlink())
            for name in sorted(names):
                if name.startswith("~$") or Path(name).suffix.lower() != ".docx":
                    continue
                path = (Path(directory) / name).resolve()
                if not in_sources(path, config):
                    errors.append(
                        dict(path=str(path), error="Source link points outside configured folders")
                    )
                    continue
                try:
                    stat = path.stat()
                    identity = (stat.st_dev, stat.st_ino)
                    if identity not in seen:
                        seen.add(identity)
                        files.append(path)
                except OSError:
                    errors.append(dict(path=str(path), error="Source file unavailable"))
    return sorted(files), errors


def ensure_document(connection, path: Path):
    row = connection.execute("SELECT * FROM documents WHERE path=?", (str(path),)).fetchone()
    if row:
        return row
    identifier = str(uuid.uuid4())
    chapter = path.stem
    if connection.execute("SELECT 1 FROM documents WHERE chapter=?", (chapter,)).fetchone():
        chapter += "-" + identifier
    connection.execute(
        "INSERT INTO documents(id,path,chapter) VALUES(?,?,?)", (identifier, str(path), chapter)
    )
    return connection.execute("SELECT * FROM documents WHERE id=?", (identifier,)).fetchone()


def save_revision(connection, row, document: dict) -> str:
    """Called inside a transaction; all records and current pointer change together."""
    revision = str(uuid.uuid5(uuid.UUID(row["id"]), document["revision"]))
    document = dict(
        document,
        document_id=row["id"],
        chapter=row["chapter"],
        extraction_revision=document["revision"],
        revision=revision,
    )
    exists = connection.execute("SELECT 1 FROM revisions WHERE id=?", (revision,)).fetchone()
    if not exists:
        connection.execute(
            "INSERT INTO revisions VALUES(?,?,?,?,?,?,?)",
            (
                revision,
                row["id"],
                document["source"]["sha256"],
                document["parser_version"],
                now(),
                row["current_revision"],
                json.dumps(document, ensure_ascii=False),
            ),
        )
        for block in document["blocks"]:
            connection.execute(
                "INSERT INTO blocks VALUES(?,?,?,?,?)",
                (
                    revision,
                    block["id"],
                    block["number"],
                    block["text"],
                    json.dumps(block, ensure_ascii=False),
                ),
            )
            connection.execute(
                "INSERT INTO search_records VALUES(?,?,?,?,?)",
                (row["id"], revision, "block", block["id"], block["text"]),
            )
        for note in document["notes"]:
            connection.execute(
                "INSERT INTO notes VALUES(?,?,?,?,?,?)",
                (
                    revision,
                    note["id"],
                    note["type"],
                    note["word_id"],
                    note["text"],
                    json.dumps(note, ensure_ascii=False),
                ),
            )
            connection.execute(
                "INSERT INTO search_records VALUES(?,?,?,?,?)",
                (row["id"], revision, "note", note["id"], note["text"]),
            )
    if row["current_revision"] != revision:
        connection.execute(
            """INSERT INTO events(document_id,happened_at,kind,from_revision,to_revision,new_path)
            VALUES(?,?,'indexed',?,?,?)""",
            (row["id"], now(), row["current_revision"], revision, row["path"]),
        )
    connection.execute(
        "UPDATE documents SET current_revision=?, observed_hash=?, last_attempt=?, error=NULL WHERE id=?",
        (revision, document["source"]["sha256"], now(), row["id"]),
    )
    return revision


def ingest(config: Config, file: str | None = None) -> dict:
    if not config.source_dirs:
        raise IndexError("Configure manuscript.source_dirs before ingestion.")
    renames = []
    if file is None:
        from .revisions import recover_renames

        renames = recover_renames(config)
    files, errors = scan(config)
    if file:
        requested = Path(file).expanduser().resolve()
        if (
            not in_sources(requested, config)
            or requested.suffix.lower() != ".docx"
            or requested.name.startswith("~$")
        ):
            raise IndexError(
                "--file must select a DOCX inside configured source folders, not a Word lock file."
            )
        files = [requested]
        errors = []  # Explicit file ingestion does not claim to reconcile the rest of the corpus.
    results = []
    with connect(config.data_dir, writable=True) as connection:
        for path in files:
            observed = None
            try:
                observed = source_hash(path)
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    row = ensure_document(connection, path)
                    current = connection.execute(
                        "SELECT * FROM revisions WHERE id=?", (row["current_revision"],)
                    ).fetchone()
                    if (
                        current
                        and current["source_hash"] == observed
                        and current["parser_version"] == PARSER_VERSION
                    ):
                        connection.execute(
                            "UPDATE documents SET observed_hash=?,last_attempt=?,error=NULL WHERE id=?",
                            (observed, now(), row["id"]),
                        )
                        results.append(
                            dict(
                                path=str(path),
                                chapter=row["chapter"],
                                state="unchanged",
                                revision=current["id"],
                            )
                        )
                        continue
                    document = extract(path, row["chapter"])
                    if document["source"]["sha256"] != observed:
                        raise ExtractionError(
                            "Source changed during ingestion; retry after saving finishes."
                        )
                    revision = save_revision(connection, row, document)
                    if source_hash(path) != observed:
                        raise ExtractionError(
                            "Source changed before commit; previous index retained."
                        )
                    results.append(
                        dict(
                            path=str(path),
                            chapter=row["chapter"],
                            state="indexed",
                            revision=revision,
                            blocks=len(document["blocks"]),
                            notes=len(document["notes"]),
                            warnings=document["warnings"],
                        )
                    )
            except (OSError, ExtractionError) as exc:
                message = (
                    str(exc)
                    if isinstance(exc, ExtractionError)
                    else "Source unavailable; check file permissions/download state"
                )
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    row = ensure_document(connection, path)
                    connection.execute(
                        "UPDATE documents SET observed_hash=?,last_attempt=?,error=? WHERE id=?",
                        (observed, now(), message, row["id"]),
                    )
                results.append(
                    dict(
                        path=str(path),
                        chapter=row["chapter"],
                        state="error",
                        error=message,
                        retained_revision=row["current_revision"],
                    )
                )
        if file is None:
            present = {str(path) for path in files}
            for known in connection.execute("SELECT * FROM documents ORDER BY chapter"):
                if known["path"] in present:
                    continue
                path = Path(known["path"])
                state = (
                    "out_of_scope"
                    if not in_sources(path, config)
                    else "missing"
                    if not path.exists()
                    else None
                )
                if state:
                    results.append(
                        dict(
                            path=str(path),
                            chapter=known["chapter"],
                            state=state,
                            error=(
                                "Source is missing or no longer configured; indexed revision retained"
                                if known["current_revision"]
                                else "Source is missing or no longer configured; no successful revision exists"
                            ),
                            retained_revision=known["current_revision"],
                        )
                    )
    ok = not errors and all(item["state"] in {"indexed", "unchanged"} for item in results)
    return dict(
        schema_version=1,
        command="ingest",
        ok=ok,
        results=results,
        scan_errors=errors,
        renames=renames,
    )


def freshness(config: Config, connection=None) -> dict:
    if connection is None and db_path(config.data_dir).exists():
        with connect(config.data_dir) as db:
            return freshness(config, db)
    files, errors = scan(config)
    rows = (
        connection.execute("""SELECT d.*,r.source_hash,r.parser_version,r.indexed_at
        FROM documents d LEFT JOIN revisions r ON r.id=d.current_revision ORDER BY d.chapter""").fetchall()
        if connection is not None
        else []
    )
    indexed_paths, records = set(), []
    for row in rows:
        path = Path(row["path"])
        indexed_paths.add(path)
        observed = None
        try:
            observed = source_hash(path)
            state = (
                "current"
                if observed == row["source_hash"] and row["parser_version"] == PARSER_VERSION
                else "stale"
            )
        except FileNotFoundError:
            state = "missing"
        except OSError:
            state = "unavailable"
        if not in_sources(path, config):
            state = "out_of_scope"
        elif row["error"] and state not in {"missing", "unavailable"}:
            state = "error"
        if not row["current_revision"] and state not in {
            "missing",
            "unavailable",
            "out_of_scope",
            "error",
        }:
            state = "unindexed"
        records.append(
            dict(
                chapter=row["chapter"],
                document_id=row["id"],
                path=str(path),
                state=state,
                observed_hash=observed,
                indexed_hash=row["source_hash"],
                revision=row["current_revision"],
                indexed_at=row["indexed_at"],
                last_error=row["error"],
            )
        )
    for path in files:
        if path not in indexed_paths:
            observed, error, state = None, None, "unindexed"
            try:
                observed = source_hash(path)
            except OSError:
                state, error = "unavailable", "Source could not be read"
            records.append(
                dict(
                    path=str(path),
                    chapter=None,
                    state=state,
                    revision=None,
                    observed_hash=observed,
                    last_error=error,
                )
            )
    if not config.source_dirs:
        errors.append(dict(error="No source folders configured"))
    return dict(
        checked_at=now(),
        index_exists=connection is not None,
        current=connection is not None
        and not errors
        and all(r["state"] == "current" for r in records),
        documents=records,
        scan_errors=errors,
    )
