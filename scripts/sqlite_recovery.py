#!/usr/bin/env python3
"""Create, verify, and restore encrypted SQLite recovery archives.

This script deliberately uses sqlite3.Connection.backup(), so a backup is a
consistent online snapshot even when the application has a WAL file.
"""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import hashlib
import json
import os
import sqlite3
import struct
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


MAGIC = b"LIFEOS-SQLITE-RECOVERY\x01"
CHUNK_SIZE = 1024 * 1024
DEFAULT_RETENTION_DAYS = 30


class RecoveryError(RuntimeError):
    """An archive cannot safely be created, verified, or restored."""


def operator_key(value: str) -> bytes:
    """Read a URL-safe base64 encoded, exactly 32-byte AES-256 operator key."""
    try:
        key = base64.urlsafe_b64decode(value.encode("ascii"))
    except Exception as error:
        raise RecoveryError("backup key must be URL-safe base64") from error
    if len(key) != 32:
        raise RecoveryError("backup key must decode to exactly 32 bytes")
    return key


def key_from_environment(name: str) -> bytes:
    value = os.environ.get(name)
    if not value:
        raise RecoveryError(f"required operator key environment variable {name} is unset")
    return operator_key(value)


def require_external_destination(destination: Path, database: Path) -> Path:
    """Require a mounted destination and reject the Railway application volume."""
    destination = destination.resolve()
    database = database.resolve()
    if not destination.is_dir():
        raise RecoveryError("destination must already exist (mount external storage before running)")
    app_data = Path("/app/data")
    try:
        destination.relative_to(app_data)
        raise RecoveryError("destination must be outside /app/data")
    except ValueError:
        pass
    try:
        destination.relative_to(database.parent)
        raise RecoveryError("destination must be outside the database directory")
    except ValueError:
        pass
    return destination


def sqlite_integrity(database: Path) -> None:
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchall()
    finally:
        connection.close()
    if result != [("ok",)]:
        raise RecoveryError(f"SQLite integrity check failed: {result!r}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def temporary_path(directory: Path, prefix: str, suffix: str) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
    os.close(descriptor)
    return Path(name)


@contextmanager
def private_temporary_directory():
    """Make a local, owner-only work area for transient plaintext databases."""
    with tempfile.TemporaryDirectory(prefix="lifeos-recovery-") as directory:
        path = Path(directory)
        try:
            os.chmod(path, 0o700)
        except OSError:
            # Windows ACLs and some managed filesystems do not support POSIX modes.
            pass
        yield path


def online_snapshot(database: Path, directory: Path) -> Path:
    """Copy via SQLite's online backup API; never copy a live DB file directly."""
    snapshot = temporary_path(directory, "lifeos-snapshot-", ".db")
    try:
        source = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target, pages=256, sleep=0.05)
        finally:
            target.close()
            source.close()
        sqlite_integrity(snapshot)
        return snapshot
    except Exception:
        snapshot.unlink(missing_ok=True)
        raise


def write_archive(snapshot: Path, archive: Path, key: bytes, metadata: dict[str, object]) -> None:
    nonce = os.urandom(12)
    header = json.dumps({"nonce": base64.b64encode(nonce).decode(), **metadata}, separators=(",", ":"), sort_keys=True).encode()
    if len(header) > 65535:
        raise RecoveryError("archive metadata is unexpectedly large")
    aad = MAGIC + struct.pack(">H", len(header)) + header
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(aad)
    temporary = archive.with_suffix(archive.suffix + ".partial")
    try:
        with temporary.open("wb") as destination, snapshot.open("rb") as source:
            os.chmod(temporary, 0o600)
            destination.write(aad)
            for block in iter(lambda: source.read(CHUNK_SIZE), b""):
                destination.write(encryptor.update(block))
            destination.write(encryptor.finalize())
            destination.write(encryptor.tag)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)


def read_header(source) -> tuple[dict[str, object], bytes, int]:
    magic = source.read(len(MAGIC))
    if magic != MAGIC:
        raise RecoveryError("not a LifeOS SQLite recovery archive")
    raw_length = source.read(2)
    if len(raw_length) != 2:
        raise RecoveryError("archive header is truncated")
    length = struct.unpack(">H", raw_length)[0]
    header = source.read(length)
    if len(header) != length:
        raise RecoveryError("archive header is truncated")
    try:
        metadata = json.loads(header)
        nonce = base64.b64decode(metadata["nonce"], validate=True)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RecoveryError("archive header is invalid") from error
    if len(nonce) != 12:
        raise RecoveryError("archive nonce is invalid")
    return metadata, magic + raw_length + header, source.tell()


def decrypt_archive(archive: Path, output: Path, key: bytes) -> dict[str, object]:
    size = archive.stat().st_size
    with archive.open("rb") as source:
        metadata, aad, ciphertext_offset = read_header(source)
        if size < ciphertext_offset + 16:
            raise RecoveryError("archive is truncated")
        source.seek(size - 16)
        tag = source.read(16)
        source.seek(ciphertext_offset)
        nonce = base64.b64decode(str(metadata["nonce"]), validate=True)
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(aad)
        remaining = size - ciphertext_offset - 16
        try:
            with output.open("wb") as destination:
                os.chmod(output, 0o600)
                while remaining:
                    block = source.read(min(CHUNK_SIZE, remaining))
                    if not block:
                        raise RecoveryError("archive ciphertext is truncated")
                    destination.write(decryptor.update(block))
                    remaining -= len(block)
                destination.write(decryptor.finalize())
                destination.flush()
                os.fsync(destination.fileno())
        except Exception:
            output.unlink(missing_ok=True)
            raise
    expected = metadata.get("sha256")
    if not isinstance(expected, str) or sha256_file(output) != expected:
        output.unlink(missing_ok=True)
        raise RecoveryError("decrypted database checksum does not match archive metadata")
    sqlite_integrity(output)
    return metadata


def prune_archives(destination: Path, retention_days: int) -> int:
    if retention_days < 0:
        raise RecoveryError("retention days cannot be negative")
    if retention_days == 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    removed = 0
    for archive in destination.glob("lifeos-*.sqlite.aesgcm"):
        if datetime.fromtimestamp(archive.stat().st_mtime, UTC) < cutoff:
            archive.unlink()
            removed += 1
    return removed


def backup(database: Path, destination: Path, key: bytes, retention_days: int) -> dict[str, object]:
    database = database.resolve()
    if not database.is_file():
        raise RecoveryError("database file does not exist")
    destination = require_external_destination(destination, database)
    with private_temporary_directory() as work_directory:
        snapshot = online_snapshot(database, work_directory)
        try:
            created = datetime.now(UTC)
            archive = destination / f"lifeos-{created.strftime('%Y%m%dT%H%M%S%fZ')}.sqlite.aesgcm"
            metadata: dict[str, object] = {
                "version": 1,
                "created_at": created.isoformat(),
                "sha256": sha256_file(snapshot),
                "database_bytes": snapshot.stat().st_size,
            }
            write_archive(snapshot, archive, key, metadata)
        finally:
            snapshot.unlink(missing_ok=True)
    return {"archive": str(archive), "sha256": metadata["sha256"], "pruned": prune_archives(destination, retention_days)}


def verify(archive: Path, key: bytes) -> dict[str, object]:
    if not archive.is_file():
        raise RecoveryError("archive file does not exist")
    with private_temporary_directory() as work_directory:
        temporary = temporary_path(work_directory, "lifeos-verify-", ".db")
        temporary.unlink()
        try:
            metadata = decrypt_archive(archive, temporary, key)
            return {"archive": str(archive), "sha256": metadata["sha256"], "database_bytes": metadata["database_bytes"]}
        finally:
            temporary.unlink(missing_ok=True)


def restore(archive: Path, database: Path, key: bytes) -> dict[str, object]:
    """Verify first, then atomically replace a stopped application's database."""
    database = database.resolve()
    if not database.parent.is_dir():
        raise RecoveryError("restore database parent directory does not exist")
    staging = temporary_path(database.parent, "lifeos-restore-", ".db")
    staging.unlink()
    try:
        metadata = decrypt_archive(archive, staging, key)
        # A stopped application must not leave old WAL state paired with the restored main DB.
        for suffix in ("-wal", "-shm"):
            database.with_name(database.name + suffix).unlink(missing_ok=True)
        os.replace(staging, database)
        return {"database": str(database), "sha256": metadata["sha256"], "restored": True}
    finally:
        staging.unlink(missing_ok=True)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--key-env", default="LIFEOS_BACKUP_KEY", help="environment variable holding the AES-256 operator key")
    actions = command.add_subparsers(dest="action", required=True)
    backup_command = actions.add_parser("backup")
    backup_command.add_argument("--database", required=True, type=Path)
    backup_command.add_argument("--destination", required=True, type=Path)
    backup_command.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    verify_command = actions.add_parser("verify")
    verify_command.add_argument("--archive", required=True, type=Path)
    restore_command = actions.add_parser("restore")
    restore_command.add_argument("--archive", required=True, type=Path)
    restore_command.add_argument("--database", required=True, type=Path)
    return command


def main() -> int:
    args = parser().parse_args()
    try:
        key = key_from_environment(args.key_env)
        if args.action == "backup":
            result = backup(args.database, args.destination, key, args.retention_days)
        elif args.action == "verify":
            result = verify(args.archive, key)
        else:
            result = restore(args.archive, args.database, key)
    except (OSError, sqlite3.Error, RecoveryError) as error:
        print(f"recovery failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
