"""Exclusive, process-bound lease for a persistent browser profile."""

import os
from pathlib import Path
from typing import BinaryIO


class ProfileInUse(RuntimeError):
    """Another process owns this persistent browser profile."""


class ProfileLease:
    def __init__(self, profile: Path):
        self.path = profile / ".lifeos-profile.lock"
        self._file: BinaryIO | None = None

    def acquire(self) -> None:
        if self._file is not None:
            return
        handle = self.path.open("a+b")
        try:
            handle.seek(0)
            if not handle.read(1):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise ProfileInUse("WhatsApp profile is already open in another process") from exc
        self._file = handle

    def release(self) -> None:
        handle = self._file
        if handle is None:
            return
        self._file = None
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
