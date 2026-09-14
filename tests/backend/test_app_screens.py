from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

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
