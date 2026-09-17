import asyncio
import time
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from lifeos.config import Settings
from lifeos.desktop_bridge import DesktopBridge
from lifeos.main import create_app
from lifeos.providers import ProviderError
from lifeos.providers import LiveProviders


@pytest.mark.asyncio
async def test_desktop_bridge_delivers_one_job_and_rejects_replay():
    bridge = DesktopBridge()
    poll = asyncio.create_task(bridge.next_job(1))
    await asyncio.sleep(0)
    request = asyncio.create_task(bridge.request("check", {"contact": "Allowed chat"}, 1))
    job = await poll
    assert job["operation"] == "check"
    assert job["payload"] == {"contact": "Allowed chat"}
    assert bridge.complete(job["id"], {"ok": True, "result": {"verified": True}})
    assert await request == {"verified": True}
    assert not bridge.complete(job["id"], {"ok": True, "result": {"verified": True}})
    bridge.close()


@pytest.mark.asyncio
async def test_desktop_bridge_fails_closed_when_offline_or_reply_is_lost():
    bridge = DesktopBridge()
    with pytest.raises(ProviderError, match="Open the LIFEOS desktop"):
        await bridge.request("send", {"contact": "Allowed chat"})
    poll = asyncio.create_task(bridge.next_job(1))
    await asyncio.sleep(0)
    pending = asyncio.create_task(bridge.request("send", {"contact": "Allowed chat"}, 0.02))
    await poll
    with pytest.raises(ProviderError) as failure:
        await pending
    assert failure.value.uncertain is True
    bridge.close()


def test_desktop_bridge_routes_require_owner_session_csrf_and_pending_job(tmp_path):
    app = create_app(Settings(
        mode="live", database_url=f"sqlite:///{tmp_path}/bridge.db",
        auth_password="strong-test-password-123", encryption_key=Fernet.generate_key().decode(),
        whatsapp_bridge_enabled=True, whatsapp_contact="Allowed chat",
    ))

    async def no_job(_timeout=10):
        return None

    app.state.desktop_bridge.next_job = no_job
    with TestClient(app) as client:
        assert client.post("/api/desktop/bridge/next").status_code == 401
        login = client.post("/api/auth/login", json={"password": "strong-test-password-123"})
        assert login.status_code == 200
        assert client.post("/api/desktop/bridge/next").status_code == 403
        assert client.post("/api/desktop/bridge/next", headers={
            "X-CSRF-Token": login.json()["csrf_token"]}).json() == {"job": None}
        payload = {"id": "long-enough-nonexistent-id", "ok": True, "result": {"verified": True}}
        assert client.post("/api/desktop/bridge/result", json=payload).status_code == 403
        reply = client.post("/api/desktop/bridge/result", json=payload,
                            headers={"X-CSRF-Token": login.json()["csrf_token"]})
        assert reply.status_code == 409


def test_whatsapp_integration_reports_current_desktop_availability(tmp_path):
    app = create_app(Settings(
        mode="live", database_url=f"sqlite:///{tmp_path}/status.db",
        auth_password="strong-test-password-123", encryption_key=Fernet.generate_key().decode(),
        whatsapp_bridge_enabled=True, whatsapp_contact="Allowed chat",
    ))
    with TestClient(app) as client:
        client.post("/api/auth/login", json={"password": "strong-test-password-123"})
        offline = {row["id"]: row for row in client.get("/api/integrations").json()}
        assert offline["whatsapp"]["status"] == "needs_attention"
        app.state.desktop_bridge._last_poll = time.monotonic()
        online = {row["id"]: row for row in client.get("/api/integrations").json()}
        assert online["whatsapp"]["status"] == "configured_unverified"


@pytest.mark.asyncio
async def test_provider_uses_desktop_result_only_for_exact_allowlisted_chat():
    class Bridge:
        def __init__(self):
            self.calls = []

        async def request(self, operation, payload, timeout):
            self.calls.append((operation, payload))
            if operation == "check":
                return {"verified": True}
            if operation == "read":
                return {"application": "whatsapp", "title": "Allowed chat", "items": []}
            if operation == "send":
                return {"id": "real-message-id", "contact": payload["contact"],
                        "body": payload["body"], "idempotency_key": payload["idempotency_key"]}
            return {"verified": True, "provider_id": payload["id"]}

    async def unused(*_args):
        return None

    settings = SimpleNamespace(mode="live", whatsapp_bridge_enabled=True,
                               whatsapp_enabled=False, whatsapp_contact="Allowed chat")
    bridge = Bridge()
    provider = LiveProviders(settings, unused, unused, bridge)
    try:
        assert await provider.check_whatsapp()
        assert (await provider.read_whatsapp_messages())["items"] == []
        action = {"application": "whatsapp", "type": "send", "_authorized": True,
                  "arguments": {"contact": "Allowed chat", "body": "Approved message"}}
        result = await provider.execute("owner", action, "approved-key")
        evidence = await provider.verify("owner", action, result)
        assert evidence["verified"] is True
        assert [name for name, _ in bridge.calls] == ["check", "read", "send", "verify"]
        action["arguments"]["contact"] = "Different chat"
        with pytest.raises(ProviderError, match="target or message"):
            await provider.execute("owner", action, "approved-key")
        assert len(bridge.calls) == 4
    finally:
        await provider.close()
