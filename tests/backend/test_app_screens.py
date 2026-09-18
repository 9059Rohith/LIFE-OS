from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from playwright.async_api import TimeoutError as BrowserTimeoutError

from lifeos.config import Settings
from lifeos.main import create_app


def test_live_gmail_and_discord_screens_are_bounded_and_read_only(tmp_path):
    app = create_app(Settings(
        _env_file=None, mode="live", environment="test",
        database_url=f"sqlite:///{tmp_path}/screens.db",
        auth_password="test-workspace-password",
        encryption_key=Fernet.generate_key().decode(),
        discord_bot_token="fixture-bot", discord_channel_id="12345",
    ))
    provider = app.state.engine.providers
    calls = []

    async def google(owner, method, url, **kwargs):
        calls.append((owner, method, url))
        if url.endswith("/messages"):
            return {"messages": [{"id": "mail-1"}]}
        return {"id": "mail-1", "snippet": "A short preview", "internalDate": "1700000000000", "payload": {"headers": [
            {"name": "From", "value": "Sender <sender@example.test>"},
            {"name": "Subject", "value": "Flight update"},
        ]}}

    async def discord(method, url, **kwargs):
        calls.append(("bot", method, url))
        if url.endswith("/messages"):
            return [{"id": "discord-1", "content": "Team update", "timestamp": "2026-09-13T12:00:00Z", "author": {"id": "123456", "avatar": "a_avatarhash", "username": "Colleague"}}]
        return {"id": "12345", "name": "team"}

    provider._google = google
    provider._request = discord
    with TestClient(app) as browser:
        assert browser.get("/api/apps/gmail").status_code == 401
        login = browser.post("/api/auth/login", json={"password": "test-workspace-password"})
        assert login.status_code == 200
        gmail = browser.get("/api/apps/gmail")
        assert gmail.status_code == 200
        assert gmail.json()["items"][0]["subject"] == "Flight update"
        assert gmail.json()["items"][0]["from"] == "Sender <sender@example.test>"
        channel = browser.get("/api/apps/discord")
        assert channel.status_code == 200
        assert channel.json()["title"] == "#team"
        assert channel.json()["items"][0]["content"] == "Team update"
        assert channel.json()["items"][0]["avatar_url"] == "https://cdn.discordapp.com/avatars/123456/a_avatarhash.png?size=64"
        assert all(method == "GET" for _, method, _ in calls)
        assert all("12345" in url for owner, method, url in calls if owner == "bot")


def test_whatsapp_browser_navigation_timeout_is_a_bounded_screen_error(tmp_path):
    app = create_app(Settings(
        _env_file=None, mode="live", environment="test",
        database_url=f"sqlite:///{tmp_path}/whatsapp-screen.db",
        auth_password="test-workspace-password",
        encryption_key=Fernet.generate_key().decode(),
        whatsapp_enabled=True, whatsapp_contact="Allowed test chat",
    ))

    async def timed_out():
        raise BrowserTimeoutError("Page.goto timed out")

    app.state.engine.providers.read_whatsapp_messages = timed_out
    with TestClient(app, raise_server_exceptions=False) as browser:
        assert browser.post("/api/auth/login", json={"password": "test-workspace-password"}).status_code == 200
        response = browser.get("/api/apps/whatsapp")
        assert response.status_code == 502
        assert "unavailable" in response.json()["detail"].lower()


def test_calendar_write_probe_requires_session_and_csrf_and_audits_success(tmp_path):
    app = create_app(Settings(
        _env_file=None, mode="live", environment="test",
        database_url=f"sqlite:///{tmp_path}/calendar-probe.db",
        auth_password="test-workspace-password",
        encryption_key=Fernet.generate_key().decode(),
    ))
    calls = []

    async def probe(owner):
        calls.append(owner)
        return {"status": "write_access_verified", "event_removed": True}

    app.state.engine.providers.verify_calendar_write_access = probe
    with TestClient(app) as browser:
        url = "/api/apps/calendar/verify-write"
        assert browser.post(url).status_code == 401
        login = browser.post("/api/auth/login", json={"password": "test-workspace-password"})
        assert login.status_code == 200
        assert browser.post(url).status_code == 403
        response = browser.post(url, headers={"X-CSRF-Token": login.json()["csrf_token"]})
        assert response.status_code == 200
        assert response.json() == {"status": "write_access_verified", "event_removed": True}
        assert calls == ["owner"]
        assert any(entry["stage"] == "calendar_write_verified" for entry in app.state.db.list("owner", "audit"))


def test_calendar_reschedule_route_saves_review_plan_without_provider_mutation(tmp_path):
    app = create_app(Settings(
        _env_file=None, mode="live", environment="test",
        database_url=f"sqlite:///{tmp_path}/calendar-plan.db",
        auth_password="test-workspace-password",
        encryption_key=Fernet.generate_key().decode(),
    ))
    calls = []

    async def calendar_read(owner, method, url, **kwargs):
        calls.append((owner, method, url))
        if url.endswith("/events/event-1"):
            return {
                "id": "event-1", "etag": "etag-1", "status": "confirmed",
                "summary": "My meeting",
                "start": {"dateTime": "2030-01-15T09:00:00+05:30"},
                "end": {"dateTime": "2030-01-15T10:00:00+05:30"},
            }
        return {"items": []}

    app.state.engine.providers._google = calendar_read
    url = "/api/apps/calendar/reschedule-plan"
    body = {
        "event_id": "event-1", "expected_etag": "etag-1",
        "new_start": "2030-01-15T14:00:00+05:30",
        "new_end": "2030-01-15T15:00:00+05:30",
        "timezone": "Asia/Kolkata",
    }
    with TestClient(app) as browser:
        assert browser.post(url, json=body).status_code == 401
        login = browser.post("/api/auth/login", json={"password": "test-workspace-password"})
        assert browser.post(url, json=body).status_code == 403
        response = browser.post(url, json=body, headers={"X-CSRF-Token": login.json()["csrf_token"]})
        assert response.status_code == 200
        plan = response.json()
        assert plan["status"] == "awaiting_approval"
        assert [action["application"] for action in plan["actions"]] == ["calendar"]
        assert browser.get(f"/api/events/{plan['id']}").json()["id"] == plan["id"]
        assert calls and all(owner == "owner" and method == "GET" for owner, method, _ in calls)


def test_secondary_account_cannot_open_primary_provider_screens_or_plan(tmp_path):
    settings = Settings(
        _env_file=None, mode="live", environment="test",
        database_url=f"sqlite:///{tmp_path}/secondary-screens.db",
        auth_password="test-workspace-password",
        encryption_key=Fernet.generate_key().decode(),
        user_registration=True,
    )
    app = create_app(settings)
    with TestClient(app) as secondary:
        registered = secondary.post("/api/auth/register", json={
            "username": "alice", "password": "a-different-strong-password",
        })
        assert registered.status_code == 200
        settings.user_registration = False
        assert secondary.get("/api/apps/calendar").status_code == 403
        assert secondary.get("/api/apps/gmail").status_code == 403
        assert secondary.get("/api/apps/discord").status_code == 403
        csrf = {"X-CSRF-Token": registered.json()["csrf_token"]}
        assert secondary.post("/api/apps/calendar/verify-write", headers=csrf).status_code == 403
        assert secondary.post("/api/apps/calendar/reschedule-plan", headers=csrf, json={
            "event_id": "event-1", "new_start": "2030-01-15T14:00:00+05:30",
            "new_end": "2030-01-15T15:00:00+05:30", "timezone": "Asia/Kolkata",
        }).status_code == 403
