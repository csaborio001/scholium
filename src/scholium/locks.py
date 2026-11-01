"""Coordinate maintenance snapshots with application writers without blocking readers."""

from contextlib import contextmanager
import fcntl
import os


@contextmanager
def book_lock(directory, exclusive=False):
    # Import lazily to avoid a storage/lock import cycle.
    from .storage import IndexError

    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(directory / ".maintenance.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise IndexError(
                "Book maintenance or writing is active. Wait for it to finish and retry."
            ) from exc
        yield
    finally:
        os.close(fd)
