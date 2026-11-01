"""Verified private backups and restore-to-new-directory recovery; no source edits."""

from contextlib import contextmanager, ExitStack, closing
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import sqlite3
import uuid

from . import __version__
from .storage import IndexError
from .locks import book_lock

FILES = {"index.sqlite3", "analysis.sqlite3", "scholium.toml"}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def allowed_output(config, output):
    output = output.expanduser().resolve()
    for source in config.source_dirs:
        if output == source or source in output.parents or output in source.parents:
            raise IndexError("Backup/recovery output must not overlap manuscript source folders.")
    return output


@contextmanager
def new_directory(output):
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        output.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise IndexError(
            "Output already exists. Choose a new directory; nothing is overwritten."
        ) from exc
    try:
        marker = output / ".incomplete"
        write_private(marker, b"Incomplete operation; do not use this directory.\n")
        yield output
        marker.unlink()
    except BaseException:
        shutil.rmtree(output)
        raise


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def copy_private(source, destination):
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(source_fd, "rb") as src:
        target_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(target_fd, "wb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
            dst.flush()
            os.fsync(dst.fileno())


def inspect_db(path, kind):
    if path.is_symlink() or not path.is_file():
        raise IndexError("Backup databases must be ordinary files.")
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            version = db.execute("pragma user_version").fetchone()[0]
            application = db.execute("pragma application_id").fetchone()[0]
            expected = (1396918348, (1, 2)) if kind == "index" else (1396918349, (1,))
            if application != expected[0] or version not in expected[1]:
                raise IndexError(
                    "Unsupported backup database schema; use its compatible app version."
                )
            if (
                db.execute("pragma integrity_check").fetchone()[0] != "ok"
                or db.execute("pragma foreign_key_check").fetchall()
            ):
                raise IndexError("Backup database failed integrity validation.")
            if kind == "index":
                return dict(
                    schema=version,
                    revisions=db.execute("select count(*) from revisions").fetchone()[0],
                )
            return dict(
                schema=version,
                analyses=db.execute("select count(*) from analyses").fetchone()[0],
                reviews=db.execute("select count(*) from reviews").fetchone()[0],
            )
    except sqlite3.Error as exc:
        raise IndexError(
            "Database cannot be validated. Preserve it and recover into a new directory."
        ) from exc


def verify(directory, *, incomplete=False):
    directory = directory.expanduser().resolve()
    if (directory / ".incomplete").exists() and not incomplete:
        raise IndexError("Backup is incomplete; do not restore it.")
    manifest = directory / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 65536:
        raise IndexError("Missing or invalid backup manifest.")
    try:
        data = json.loads(manifest.read_text())
        if (
            not isinstance(data, dict)
            or type(data.get("schema_version")) is not int
            or data.get("schema_version") != 1
            or not isinstance(data.get("files"), dict)
        ):
            raise ValueError
        files = data["files"]
        if not {"index.sqlite3", "scholium.toml"} <= files.keys() or files.keys() - FILES:
            raise ValueError
        if set(p.name for p in directory.iterdir()) - (
            set(files) | {"manifest.json", ".incomplete"}
        ):
            raise ValueError
        for name, expected in files.items():
            path = directory / name
            if (
                not isinstance(expected, dict)
                or path.is_symlink()
                or not path.is_file()
                or path.stat().st_size != expected["bytes"]
                or digest(path) != expected["sha256"]
            ):
                raise ValueError
        index = inspect_db(directory / "index.sqlite3", "index")
        analysis = (
            inspect_db(directory / "analysis.sqlite3", "analysis")
            if "analysis.sqlite3" in files
            else None
        )
        if analysis:
            with (
                closing(
                    sqlite3.connect((directory / "index.sqlite3").as_uri() + "?mode=ro", uri=True)
                ) as main,
                closing(
                    sqlite3.connect(
                        (directory / "analysis.sqlite3").as_uri() + "?mode=ro", uri=True
                    )
                ) as side,
            ):
                for (payload,) in side.execute("select payload from analyses"):
                    for dep in json.loads(payload)["dependencies"]:
                        row = main.execute(
                            "select source_hash from revisions where id=? and document_id=?",
                            (dep["revision"], dep["document_id"]),
                        ).fetchone()
                        if row is None or row[0] != dep["source_hash"]:
                            raise IndexError(
                                "Backup analysis references missing or mismatched source revisions."
                            )
    except IndexError:
        raise
    except (ValueError, KeyError, TypeError, UnicodeError, sqlite3.Error) as exc:
        raise IndexError(
            "Backup verification failed; files or manifest are damaged or inconsistent."
        ) from exc
    return dict(
        schema_version=1,
        command="backup-check",
        ok=True,
        directory=str(directory),
        index=index,
        analysis=analysis,
        manifest=data,
    )


def backup(config, output=None):
    with book_lock(config.data_dir, exclusive=True):
        return _backup(config, output)


def _backup(config, output=None):
    output = allowed_output(
        config, output or config.data_dir / "backups" / ("book-" + str(uuid.uuid4()))
    )
    paths = [config.data_dir / "index.sqlite3"]
    if (config.data_dir / "analysis.sqlite3").is_symlink():
        raise IndexError("Analysis database must not be a symlink.")
    if (config.data_dir / "analysis.sqlite3").exists():
        paths.append(config.data_dir / "analysis.sqlite3")
    try:
        with ExitStack() as locks:
            # Reserve both writers in fixed order while separate readers take SQLite snapshots.
            for path in paths:
                inspect_db(path, "index" if path.name == "index.sqlite3" else "analysis")
                guard = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=5)
                locks.callback(guard.close)
                guard.execute("BEGIN IMMEDIATE")
            with new_directory(output):
                for path in paths:
                    target = output / path.name
                    write_private(target, b"")
                    with (
                        closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as src,
                        closing(sqlite3.connect(target)) as dst,
                    ):
                        src.backup(dst)
                write_private(output / "scholium.toml", config.path.read_bytes())
                files = {
                    p.name: dict(bytes=p.stat().st_size, sha256=digest(p))
                    for p in output.iterdir()
                    if p.name != ".incomplete"
                }
                metadata = dict(
                    schema_version=1,
                    app_version=__version__,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    original_config=str(config.path),
                    files=files,
                    scope="Index, analyses/review history if present, and configuration. No Word originals or standalone exports.",
                )
                write_private(output / "manifest.json", json.dumps(metadata, indent=2).encode())
                result = verify(output, incomplete=True)
    except sqlite3.Error as exc:
        raise IndexError(
            "Backup could not lock/read the databases. Stop competing writers and retry; existing data retained."
        ) from exc
    result["command"] = "backup"
    return result


def restore(config, directory, output):
    directory = directory.expanduser().resolve()
    output = allowed_output(config, output)
    if (
        output == config.data_dir
        or config.data_dir in output.parents
        or output in config.data_dir.parents
    ):
        raise IndexError("Restore into a new data directory outside the current data directory.")
    if output == directory or directory in output.parents or output in directory.parents:
        raise IndexError("Restore output must not overlap the backup directory.")
    verified = verify(directory)
    with new_directory(output):
        for name in verified["manifest"]["files"]:
            copy_private(directory / name, output / name)
        copy_private(directory / "manifest.json", output / "manifest.json")
        verify(output, incomplete=True)  # Also catches source backup changes during copying.
    return dict(
        schema_version=1,
        command="restore",
        ok=True,
        output=str(output),
        next_step="Recovered into a separate directory. The active book is unchanged. Set storage.data_dir in your existing book configuration to this absolute path, then run status. The copied scholium.toml is a historical reference, not an automatically activated configuration.",
        index=verified["index"],
        analysis=verified["analysis"],
    )
