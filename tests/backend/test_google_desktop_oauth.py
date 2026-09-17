import json
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from lifeos.config import Settings
from lifeos.main import create_app


def test_google_callback_from_system_browser_consumes_owner_bound_state(tmp_path, monkeypatch):
    settings = Settings(
        mode="live",
        auth_password="a-strong-test-password-only",
        encryption_key=Fernet.generate_key().decode(),
        database_url=f"sqlite:///{tmp_path}/oauth.db",
        google_client_id="123-example.apps.googleusercontent.com",
        google_client_secret="test-client-secret",
        google_redirect_uri="http://testserver/api/integrations/google/callback",
    )

    async def exchange(_settings, code, verifier):
        assert code == "google-authorization-code"
        assert verifier
        return {"access_token": "test-access-token", "refresh_token": "test-refresh-token"}

    monkeypatch.setattr("lifeos.oauth.exchange_code", exchange)
    app = create_app(settings)
    with TestClient(app, base_url="http://testserver") as owner:
        login = owner.post("/api/auth/login", json={"password": settings.auth_password})
        assert login.status_code == 200
        started = owner.get("/api/integrations/google/connect")
        assert started.status_code == 200
        state = parse_qs(urlsplit(started.json()["url"]).query)["state"][0]

        # The system browser has no cookie from Electron's isolated workspace.
        external = TestClient(app, base_url="http://testserver")
        assert external.get("/api/integrations/google/callback", params={
            "code": "google-authorization-code", "state": "wrong-state",
        }).status_code == 403
        callback = external.get("/api/integrations/google/callback", params={
            "code": "google-authorization-code", "state": state,
        })
        assert callback.status_code == 200
        assert "return to the LIFEOS desktop window" in callback.text
        assert external.get("/api/integrations/google/callback", params={
            "code": "google-authorization-code", "state": state,
        }).status_code == 403

        stored = app.state.db.get("owner", "token", "owner:token:google")
        token = json.loads(Fernet(settings.encryption_key.encode()).decrypt(stored["encrypted"].encode()))
        assert token["refresh_token"] == "test-refresh-token"
