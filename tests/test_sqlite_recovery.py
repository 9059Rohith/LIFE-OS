import base64
import importlib.util
import sqlite3
from pathlib import Path

import pytest

from lifeos.store import Database


RECOVERY_PATH = Path(__file__).parents[1] / "scripts" / "sqlite_recovery.py"
SPEC = importlib.util.spec_from_file_location("sqlite_recovery", RECOVERY_PATH)
recovery = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(recovery)


def test_backup_verify_and_restore_actual_application_schema_and_data(tmp_path):
    source = tmp_path / "data" / "lifeos.db"
    source.parent.mkdir()
    application = Database(f"sqlite:///{source}")
    application.put("alice", "work", "work-1", {"id": "work-1", "title": "Restore proof", "state": "done"})
    application.put("alice", "audit", "audit-1", {"id": "audit-1", "hash": "a" * 64})
    destination = tmp_path / "external-recovery-mount"
    destination.mkdir()
    key = b"k" * 32

    result = recovery.backup(source, destination, key, retention_days=30)
    archive = Path(result["archive"])
    assert archive.parent == destination
    assert source.read_bytes() != archive.read_bytes()
    assert list(destination.glob("*.db")) == []
    assert recovery.verify(archive, key)["sha256"] == result["sha256"]
    assert list(destination.glob("*.db")) == []

    restored = tmp_path / "restored" / "lifeos.db"
    restored.parent.mkdir()
    recovery.restore(archive, restored, key)
    restored_application = Database(f"sqlite:///{restored}")
    assert restored_application.get("alice", "work", "work-1") == {
        "id": "work-1", "title": "Restore proof", "state": "done"
    }
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT version FROM schema_revision WHERE id = 1").fetchone() == (2,)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_tampered_archive_and_wrong_key_do_not_restore(tmp_path):
    source = tmp_path / "data" / "lifeos.db"
    source.parent.mkdir()
    Database(f"sqlite:///{source}").put("alice", "note", "n1", {"id": "n1", "text": "private"})
    destination = tmp_path / "external"
    destination.mkdir()
    key = b"p" * 32
    archive = Path(recovery.backup(source, destination, key, retention_days=0)["archive"])
    contents = bytearray(archive.read_bytes())
    contents[-17] ^= 1
    archive.write_bytes(contents)
    target = tmp_path / "restore" / "lifeos.db"
    target.parent.mkdir()
    with pytest.raises(Exception):
        recovery.restore(archive, target, b"q" * 32)
    assert not target.exists()


def test_refuses_backup_to_database_volume_and_decodes_operator_key(tmp_path):
    database = tmp_path / "data" / "lifeos.db"
    database.parent.mkdir()
    Database(f"sqlite:///{database}")
    with pytest.raises(recovery.RecoveryError, match="outside the database directory"):
        recovery.backup(database, database.parent, b"x" * 32, retention_days=30)
    encoded = base64.urlsafe_b64encode(b"x" * 32).decode()
    assert recovery.operator_key(encoded) == b"x" * 32
