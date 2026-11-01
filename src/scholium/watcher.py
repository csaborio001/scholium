"""Foreground watching: events are hints; hashes and stable-file checks are authoritative."""

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
import math
import os
from pathlib import Path
import threading
import time
import zipfile

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .indexing import freshness, ingest, now
from .docx_reader import source_hash
from .revisions import recover_renames
from .storage import IndexError, connect


def relevant(event) -> bool:
    if event.event_type not in {"created", "modified", "deleted", "moved", "closed"}:
        return False
    if event.is_directory:
        return True  # A folder rename can relocate many chapters.
    return any(
        Path(path).suffix.lower() == ".docx" and not Path(path).name.startswith("~$")
        for path in (event.src_path, getattr(event, "dest_path", ""))
        if path
    )


class Hints(FileSystemEventHandler):
    def __init__(self):
        self.lock = threading.Lock()
        self.latest = None

    def on_any_event(self, event):
        if relevant(event):
            with self.lock:
                self.latest = time.monotonic()

    def consume_if_quiet(self, current, settle):
        with self.lock:
            if self.latest is not None and current - self.latest >= settle:
                self.latest = None
                return True
        return False


@contextmanager
def watch_lock(config):
    config.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = config.data_dir / "watch.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise IndexError(
                "Another watcher holds this book lock. Stop it before starting another."
            ) from exc
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
        yield
    finally:
        os.close(fd)  # OS releases lock even on crashes; retain inode to avoid lock-file races.


def signature(path: Path):
    first = path.stat()
    digest = source_hash(path)
    last = path.stat()
    if (first.st_size, first.st_mtime_ns, first.st_ino) != (
        last.st_size,
        last.st_mtime_ns,
        last.st_ino,
    ):
        raise OSError("Source is changing")
    return digest, last.st_size, last.st_mtime_ns, last.st_ino


@dataclass
class Pending:
    fingerprint: tuple
    ready_at: float
    attempts: int = 0


class Engine:
    def __init__(self, config, emit, settle=1.0, retries=3, retry_base=1.0):
        self.config, self.emit = config, emit
        self.settle, self.retries, self.retry_base = settle, retries, retry_base
        self.pending = {}
        self.attempted = {}
        self.last_state = None

    def reconcile(self, current):
        for rename in recover_renames(self.config):
            self.emit("renamed", **rename)
        state = freshness(self.config)
        state_key = json.dumps(
            {
                "documents": [
                    (r["path"], r["state"], r.get("revision"), r.get("last_error"))
                    for r in state["documents"]
                ],
                "scan_errors": state["scan_errors"],
            },
            sort_keys=True,
        )
        if state_key != self.last_state:
            self.emit("status", freshness=state)
            self.last_state = state_key
        present = set()
        for record in state["documents"]:
            path = Path(record["path"])
            present.add(path)
            if record["state"] == "current":
                self.pending.pop(path, None)
                self.attempted.pop(path, None)
                continue
            if record["state"] in {"missing", "unavailable", "out_of_scope"}:
                self.pending.pop(path, None)
                continue
            try:
                fingerprint = signature(path)
            except OSError:
                continue
            if self.attempted.get(path) == fingerprint:
                continue  # Bounded retry per unchanged fingerprint; restart retries it again.
            queued = self.pending.get(path)
            if queued is None or queued.fingerprint != fingerprint:
                self.pending[path] = Pending(fingerprint, current + self.settle)
        for path in list(self.pending):
            if path not in present:
                self.pending.pop(path)

    def tick(self, current):
        changed = False
        for path, pending in list(self.pending.items()):
            if current < pending.ready_at:
                continue
            try:
                fingerprint = signature(path)
                if fingerprint != pending.fingerprint:
                    self.pending[path] = Pending(fingerprint, current + self.settle)
                    continue
                valid = zipfile.is_zipfile(path)
            except OSError:
                valid = False
            pending.attempts += 1
            if not valid and pending.attempts < self.retries:
                self.emit(
                    "retry",
                    path=str(path),
                    attempt=pending.attempts,
                    reason="File is unavailable or not yet a complete DOCX ZIP",
                )
                pending.ready_at = current + min(8.0, self.retry_base * 2 ** (pending.attempts - 1))
                continue
            # Final failure is recorded by ingestion, preserving the previous successful revision.
            result = ingest(self.config, str(path))
            self.emit("ingest", **result_without_envelope(result))
            changed = True
            if not result["ok"] and pending.attempts < self.retries:
                pending.ready_at = current + min(8.0, self.retry_base * 2 ** (pending.attempts - 1))
            else:
                self.attempted[path] = pending.fingerprint
                self.pending.pop(path, None)
        return changed


def result_without_envelope(result):
    return {key: value for key, value in result.items() if key not in {"schema_version", "command"}}


def run(
    config,
    *,
    settle=1.0,
    interval=30.0,
    retries=3,
    duration=None,
    polling=False,
    emit=None,
    stop_event=None,
):
    if not config.source_dirs:
        raise IndexError("Configure source folders before starting watch.")
    if any(not math.isfinite(x) or x <= 0 for x in (settle, interval)) or not 1 <= retries <= 10:
        raise IndexError(
            "Watch settle/interval must be finite positive seconds; retries must be 1–10."
        )
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise IndexError("--duration must be finite positive seconds.")
    stop = stop_event or threading.Event()
    callback = emit or (lambda event: print(json.dumps(event), flush=True))

    def send(event, **values):
        callback(dict(schema_version=1, command="watch", event=event, time=now(), **values))

    observer, watched = None, set()
    hints = Hints()
    engine = Engine(config, send, settle, retries)
    reason = "duration" if duration is not None else "stop_requested"
    with watch_lock(config):
        with connect(config.data_dir, writable=True):
            pass  # Initialize/migrate before observer startup; never rewrite source files.
        if not polling:
            try:
                observer = Observer()
                observer.start()
            except (OSError, RuntimeError):
                observer = None
                send(
                    "warning",
                    message="Native watcher unavailable; periodic hash reconciliation remains active.",
                )
        start = time.monotonic()
        next_scan = start
        send(
            "started",
            mode="watchdog+hash-reconciliation" if observer else "hash-reconciliation",
            settle_seconds=settle,
            interval_seconds=interval,
            retries=retries,
        )
        try:
            while not stop.is_set():
                current = time.monotonic()
                if duration is not None and current - start >= duration:
                    break
                if current >= next_scan or hints.consume_if_quiet(current, settle):
                    if observer is not None:
                        for root in config.source_dirs:
                            if root not in watched and root.is_dir():
                                try:
                                    observer.schedule(hints, str(root), recursive=True)
                                    watched.add(root)
                                except (OSError, RuntimeError):
                                    send(
                                        "warning",
                                        message="Cannot observe a source folder; hash reconciliation will continue.",
                                        path=str(root),
                                    )
                    try:
                        engine.reconcile(current)
                    except (IndexError, OSError) as exc:
                        send(
                            "error",
                            message=str(exc)
                            if isinstance(exc, IndexError)
                            else "Reconciliation failed; retrying next interval.",
                        )
                    next_scan = current + interval
                try:
                    if engine.tick(current):
                        next_scan = min(next_scan, current + settle)
                except (IndexError, OSError) as exc:
                    send(
                        "error",
                        message=str(exc)
                        if isinstance(exc, IndexError)
                        else "Ingestion temporarily unavailable; prior index retained.",
                    )
                    for pending in engine.pending.values():
                        pending.ready_at = current + min(8.0, interval)
                stop.wait(min(0.1, settle, interval))
        except KeyboardInterrupt:
            reason = "interrupted"
        finally:
            if observer is not None:
                observer.stop()
                observer.join(timeout=5)
        state = freshness(config)
        send("stopped", reason=reason, pending_files=len(engine.pending), freshness=state)
        return 130 if reason == "interrupted" else 0 if state["current"] else 1


def readable(event):
    name = event["event"]
    if name in {"status", "stopped"}:
        from .search import freshness_message

        return (
            f"watch {name}"
            + (f" ({event['reason']})" if name == "stopped" else "")
            + "\n"
            + "\n".join(freshness_message(event["freshness"]))
        )
    if name == "ingest":
        return "\n".join(
            f"watch {r['state']}: {r['chapter']} · {r.get('revision') or r.get('error')}"
            for r in event["results"]
        )
    return f"watch {name}: " + json.dumps(
        {k: v for k, v in event.items() if k not in {"schema_version", "command", "event", "time"}},
        ensure_ascii=False,
    )
