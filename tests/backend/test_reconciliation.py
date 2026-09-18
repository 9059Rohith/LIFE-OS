import time

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient

from lifeos.config import Settings
from lifeos.engine import Engine
from lifeos.main import create_app
from lifeos.store import Database, digest


class ReadbackProvider:
    def __init__(self):
        self.sends = 0
        self.reads = 0
        self.reported_id = None

    async def preflight(self, *_args):
        return None

    async def execute(self, *_args):
        self.sends += 1
        return {"id": "provider-message-1", "channel_id": "approved-channel", "content": "irrelevant response text"}

    async def verify(self, _owner, _action, result):
        self.reads += 1
        assert result["id"] == "provider-message-1"
        assert result["channel_id"] == "approved-channel"
        return {"verified": self.reads > 1, "provider_id": self.reported_id or result["id"], "detail": "Provider read-back"}


@pytest.mark.asyncio
async def test_uncertain_send_can_be_rechecked_by_provider_id_without_resending(tmp_path):
    args = {"channel_id": "approved-channel", "body": "Approved message"}
    provider = ReadbackProvider()
    db = Database(f"sqlite:///{tmp_path}/reconcile.db")
    settings = type("Settings", (), {"mode": "live", "approval_seconds": 600})()
    engine = Engine(db, settings, provider)
    action = {
        "id": "action-1", "application": "discord", "type": "send", "title": "Notify",
        "status": "approved", "requires_approval": True, "risk": "medium", "reversible": False,
        "dependencies": [], "arguments": args, "arguments_hash": digest(args), "evidence": None,
        "approval": {"version": 1, "hash": digest(args), "expires": time.time() + 600},
    }
    event = {
        "id": "event-1", "version": 1, "status": "approved", "simulation": False,
        "actions": [action], "context": [], "timeline": [], "summary": "",
    }
    engine.save("owner", event)

    first = await engine.execute("owner", event)
    assert first["status"] == "partial_failure"
    assert first["actions"][0]["status"] == "uncertain"
    assert first["actions"][0]["provider_result"] == {
        "id": "provider-message-1", "channel_id": "approved-channel",
    }
    assert provider.sends == 1

    recovered = await engine.reconcile("owner", engine.event("owner", "event-1"), "action-1")
    assert recovered["status"] == "resolved"
    assert recovered["actions"][0]["status"] == "verified"
    assert provider.sends == 1
    assert provider.reads == 2
    assert engine.event("owner", "event-1")["status"] == "resolved"


@pytest.mark.asyncio
async def test_uncertain_action_without_provider_result_cannot_be_rechecked(tmp_path):
    db = Database(f"sqlite:///{tmp_path}/missing-receipt.db")
    provider = ReadbackProvider()
    engine = Engine(db, type("Settings", (), {"mode": "live"})(), provider)
    event = {"id": "event-2", "status": "partial_failure", "actions": [{"id": "action-1", "status": "uncertain"}]}
    with pytest.raises(HTTPException) as error:
        await engine.reconcile("owner", event, "action-1")
    assert error.value.status_code == 409
    assert provider.sends == provider.reads == 0


def test_reconciliation_route_requires_login_and_csrf_and_only_reads_provider(tmp_path):
    app = create_app(Settings(
        mode="live", database_url=f"sqlite:///{tmp_path}/route.db",
        auth_password="strong-password-for-test", encryption_key=Fernet.generate_key().decode(),
    ))
    provider = ReadbackProvider()
    provider.reads = 1
    app.state.engine.providers = provider
    args = {"channel_id": "approved-channel", "body": "Approved message"}
    action = {
        "id": "action-1", "application": "discord", "type": "send", "title": "Notify",
        "status": "uncertain", "requires_approval": True, "risk": "medium", "reversible": False,
        "dependencies": [], "arguments": args, "arguments_hash": digest(args), "evidence": None,
        "provider_result": {"id": "provider-message-1", "channel_id": "approved-channel"},
    }
    app.state.db.put("owner", "event", "event-1", {
        "id": "event-1", "version": 1, "status": "partial_failure", "simulation": False,
        "actions": [action], "context": [], "timeline": [], "summary": "",
    })
    path = "/api/events/event-1/actions/action-1/reconcile"
    with TestClient(app) as client:
        assert client.post(path).status_code == 401
        login = client.post("/api/auth/login", json={"password": "strong-password-for-test"})
        assert login.status_code == 200
        assert client.post(path).status_code == 403
        checked = client.post(path, headers={"X-CSRF-Token": login.json()["csrf_token"]})
        assert checked.status_code == 200
        assert checked.json()["actions"][0]["status"] == "verified"
        assert provider.sends == 0
        assert provider.reads == 2


@pytest.mark.asyncio
async def test_readback_for_a_different_provider_id_does_not_resolve_delivery(tmp_path):
    db = Database(f"sqlite:///{tmp_path}/wrong-id.db")
    provider = ReadbackProvider()
    provider.reads = 1
    provider.reported_id = "different-message"
    engine = Engine(db, type("Settings", (), {"mode": "live"})(), provider)
    args = {"channel_id": "approved-channel", "body": "Approved message"}
    event = {
        "id": "event-3", "version": 1, "status": "partial_failure", "simulation": False,
        "actions": [{
            "id": "action-1", "application": "discord", "type": "send", "status": "uncertain",
            "arguments": args, "arguments_hash": digest(args), "risk": "medium", "evidence": None,
            "provider_result": {"id": "provider-message-1", "channel_id": "approved-channel"},
        }], "timeline": [], "summary": "",
    }
    recovered = await engine.reconcile("owner", event, "action-1")
    assert recovered["actions"][0]["status"] == "uncertain"
    assert provider.sends == 0
