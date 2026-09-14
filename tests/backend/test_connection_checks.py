from types import SimpleNamespace

import pytest

from lifeos.diagnostics import connection_checks
from lifeos.providers import ProviderError


class Providers:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    async def _google(self, owner, method, url, **kwargs):
        self.calls.append((method, url))
        if self.fail:
            raise ProviderError("private-token-must-never-appear", "AUTHENTICATION_ERROR")
        return {}

    def _discord_headers(self):
        return {}

    async def _request(self, method, url, **kwargs):
        self.calls.append(("GET", "discord"))
        if self.fail:
            raise ProviderError("private-channel-must-never-appear", "AUTHORIZATION_ERROR")
        return []

    async def _route_context(self):
        self.calls.append(("COMPUTE_ROUTE", "maps"))
        return {"duration_minutes": 10}

    async def check_whatsapp(self):
        self.calls.append(("CHECK_CHAT", "whatsapp"))
        return True


def settings(**overrides):
    return SimpleNamespace(
        mode="live",
        discord_bot_token="configured",
        discord_channel_id="configured",
        google_maps_api_key="configured",
        maps_origin="",
        maps_destination="",
        whatsapp_enabled=False,
        **overrides,
    )


@pytest.mark.asyncio
async def test_missing_route_addresses_are_not_invented_and_checks_never_send():
    provider = Providers()
    result = await connection_checks(settings(), provider, "owner")
    assert next(item for item in result if item["id"] == "maps")["status"] == "needs_attention"
    assert next(item for item in result if item["id"] == "gmail")["status"] == "read_access_verified"
    assert all(method == "GET" for method, _ in provider.calls)


@pytest.mark.asyncio
async def test_provider_exceptions_do_not_leak_and_other_results_survive():
    result = await connection_checks(settings(), Providers(fail=True), "owner")
    assert len(result) == 6
    assert "private-token" not in str(result)
    assert "private-channel" not in str(result)
    assert next(item for item in result if item["id"] == "gmail")["status"] == "not_connected"
    assert next(item for item in result if item["id"] == "discord")["status"] == "needs_attention"


@pytest.mark.asyncio
async def test_whatsapp_check_verifies_chat_without_sending():
    provider = Providers()
    config = settings()
    config.whatsapp_enabled = True
    result = await connection_checks(config, provider, "owner")
    assert next(item for item in result if item["id"] == "whatsapp")["status"] == "read_access_verified"
    assert ("CHECK_CHAT", "whatsapp") in provider.calls
    assert not any(method == "POST" for method, _ in provider.calls)


def test_connection_checks_require_csrf(client):
    assert client.post("/api/integrations/check").status_code == 200
    client.headers.pop("X-CSRF-Token")
    assert client.post("/api/integrations/check").status_code == 403


def test_recent_connection_check_survives_refresh_without_rechecking(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    from fastapi.testclient import TestClient
    from lifeos.config import Settings
    from lifeos.main import create_app

    calls = []

    async def checked(*args):
        calls.append(True)
        return [
            {"id": "whatsapp", "name": "WhatsApp", "status": "read_access_verified", "mode": "live", "description": "Exact chat verified."},
            {"id": "maps", "name": "Maps", "status": "needs_attention", "mode": "live", "description": "Routes denied."},
        ]

    monkeypatch.setattr("lifeos.diagnostics.connection_checks", checked)
    app = create_app(Settings(
        _env_file=None,
        mode="live",
        environment="test",
        database_url=f"sqlite:///{tmp_path}/connections.db",
        auth_password="test-workspace-password",
        encryption_key=Fernet.generate_key().decode(),
        whatsapp_enabled=True,
        whatsapp_contact="Family",
        google_maps_api_key="configured",
    ))
    with TestClient(app) as browser:
        login = browser.post("/api/auth/login", json={"password": "test-workspace-password"})
        assert login.status_code == 200
        browser.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        assert browser.get("/api/integrations").json()[2]["status"] == "configured_unverified"
        assert browser.post("/api/integrations/check").status_code == 200
        for _ in range(5):
            statuses = {item["id"]: item["status"] for item in browser.get("/api/integrations").json()}
            assert statuses["whatsapp"] == "read_access_verified"
            assert statuses["maps"] == "needs_attention"
        assert calls == [True]


@pytest.mark.asyncio
async def test_checks_do_not_wait_for_execution_and_reject_duplicate_checks(monkeypatch):
    import asyncio
    import httpx
    from lifeos.config import Settings
    from lifeos.main import create_app

    app = create_app(Settings(database_url="sqlite:///:memory:"))
    started, finish = asyncio.Event(), asyncio.Event()

    async def slow_check(*args):
        started.set()
        await finish.wait()
        return []

    monkeypatch.setattr("lifeos.diagnostics.connection_checks", slow_check)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        session = (await client.get("/api/session")).json()
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        async with app.state.engine.lock(session["user"]["id"]):
            first = asyncio.create_task(client.post("/api/integrations/check"))
            try:
                await asyncio.wait_for(started.wait(), 1)
                assert (await client.post("/api/integrations/check")).status_code == 429
            finally:
                finish.set()
                assert (await first).status_code == 200
    app.state.db.engine.dispose()
