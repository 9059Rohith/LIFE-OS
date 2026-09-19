from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pytest
from lifeos.config import Settings
from lifeos.main import create_app
from lifeos.planning import extract
from test_core import plan, approve


def test_expired_approval_and_changed_calendar(client):
    event = plan(client)
    approve(client, event)
    owner = client.get("/api/session").json()["user"]["id"]
    engine = client.app.state.engine
    event = engine.event(owner, event["id"])
    next(a for a in event["actions"] if a["requires_approval"])["approval"]["expires"] = 0
    engine.save(owner, event)
    assert client.post(f"/api/events/{event['id']}/execute").status_code == 409
    approve(client, event)
    app = engine.db.get(owner, "app", owner + ":app:calendar")
    app["records"][0]["etag"] = "changed-externally"
    engine.db.put(owner, "app", owner + ":app:calendar", app)
    assert client.post(f"/api/events/{event['id']}/execute").status_code == 409
    assert all(a.get("attempts", 0) == 0 for a in engine.event(owner, event["id"])["actions"])


def test_recipient_tampering_and_unknown_fields(client):
    event = plan(client)
    action = next(a for a in event["actions"] if a["application"] == "gmail")
    args = action["arguments"] | {"recipient": "attacker@example.com"}
    assert (
        client.patch(
            f"/api/events/{event['id']}/actions/{action['id']}", json={"arguments": args}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/events", json={"text": "My flight moved to 8 AM", "approved": True}).status_code
        == 422
    )
    assert client.post(
        "/api/events", json={"text": "Flight AI-742 tomorrow moved to 8 AM", "source": "gmail"}
    ).status_code == 422
    assert (
        client.post(
            "/api/events",
            json={"text": "My flight moved to 8 AM"},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )


def test_uncertain_send_blocks_retry(client, monkeypatch):
    event = plan(client)
    approve(client, event)
    engine = client.app.state.engine
    original = engine.execute_local

    def timeout(owner, action, key):
        result = original(owner, action, key)
        if action["application"] == "gmail":
            raise TimeoutError("Secret provider payload must not escape")
        return result

    monkeypatch.setattr(engine, "execute_local", timeout)
    event = client.post(f"/api/events/{event['id']}/execute").json()
    assert event["status"] == "partial_failure"
    gmail = next(a for a in event["actions"] if a["application"] == "gmail")
    assert gmail["status"] == "uncertain"
    assert "Secret" not in gmail["error"]
    assert client.post(f"/api/events/{event['id']}/retry").status_code == 409
    records = next(a["records"] for a in client.get("/api/demo/apps").json() if a["application"] == "gmail")
    assert len([r for r in records if r.get("status") == "sent"]) == 1


def test_cancel_and_rejected_dependency(client):
    event = plan(client)
    assert client.post(f"/api/events/{event['id']}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/api/events/{event['id']}/execute").status_code == 409
    event = plan(client)
    calendar = next(a for a in event["actions"] if a["application"] == "calendar")
    event = client.post(f"/api/events/{event['id']}/actions/{calendar['id']}/reject").json()
    approve(client, event)
    result = client.post(f"/api/events/{event['id']}/execute").json()
    assert next(a for a in result["actions"] if a["application"] == "gmail")["status"] == "blocked_dependency"


def test_live_auth_and_guard(tmp_path):
    with pytest.raises(ValueError):
        Settings(mode="demo", environment="production")
    with pytest.raises(ValueError):
        Settings(mode="live")
    settings = Settings(
        mode="live",
        auth_password="a-strong-test-password-only",
        encryption_key=Fernet.generate_key().decode(),
        database_url=f"sqlite:///{tmp_path}/live.db",
    )
    with TestClient(create_app(settings)) as c:
        assert c.get("/api/session").status_code == 401
        assert c.post("/api/auth/login", json={"password": "incorrect"}).status_code == 401
        session = c.post("/api/auth/login", json={"password": settings.auth_password})
        assert session.status_code == 200
        assert "httponly" in session.headers["set-cookie"].lower()
        c.headers["X-CSRF-Token"] = session.json()["csrf_token"]
        assert c.post("/api/demo/run", json={"scenario": "flight"}).status_code == 403
        assert c.get("/api/demo/apps").json() == []


def test_live_workspace_can_enter_isolated_demo_without_owner_login(tmp_path):
    settings = Settings(
        mode="live",
        auth_password="a-strong-test-password-only",
        encryption_key=Fernet.generate_key().decode(),
        database_url=f"sqlite:///{tmp_path}/live-demo-button.db",
    )
    with TestClient(create_app(settings)) as c:
        assert c.get("/api/session").status_code == 401
        entered = c.post("/api/auth/demo")
        assert entered.status_code == 200
        assert entered.json()["mode"] == "demo"
        assert entered.json()["user"]["id"] != "owner"
        c.headers["X-CSRF-Token"] = entered.json()["csrf_token"]

        event = c.post("/api/demo/run", json={"scenario": "flight"})
        assert event.status_code == 200
        payload = event.json()
        approved = c.post(
            f"/api/events/{payload['id']}/approve",
            json={
                "version": payload["version"],
                "action_ids": [a["id"] for a in payload["actions"] if a["requires_approval"]],
            },
        )
        assert approved.status_code == 200
        resolved = c.post(f"/api/events/{payload['id']}/execute")
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "resolved"


def test_registered_users_receive_isolated_sessions_and_work_records(tmp_path):
    settings = Settings(
        mode="live",
        auth_password="a-strong-test-password-only",
        encryption_key=Fernet.generate_key().decode(),
        user_registration=True,
        database_url=f"sqlite:///{tmp_path}/multiuser.db",
    )
    app = create_app(settings)
    owner, alice = TestClient(app), TestClient(app)
    owner_login = owner.post("/api/auth/login", json={"password": settings.auth_password})
    owner.headers["X-CSRF-Token"] = owner_login.json()["csrf_token"]
    owner_task = owner.post("/api/work/tasks", json={"title": "Owner-only task"})
    assert owner_task.status_code == 200

    registered = alice.post(
        "/api/auth/register",
        json={"username": "alice", "password": "a-different-strong-password"},
    )
    assert registered.status_code == 200
    assert registered.json()["user"]["id"] == "user:alice"
    assert registered.json()["user"]["id"] != owner_login.json()["user"]["id"]
    alice.headers["X-CSRF-Token"] = registered.json()["csrf_token"]

    assert alice.get("/api/work/tasks").json()["items"] == []
    assert alice.get(f"/api/work/tasks/{owner_task.json()['id']}").status_code == 404
    assert alice.post("/api/work/tasks", json={"title": "Alice-only task"}).status_code == 200
    assert [item["title"] for item in owner.get("/api/work/tasks").json()["items"]] == ["Owner-only task"]
    assert alice.get("/api/events").status_code == 403
    assert alice.get("/api/integrations").status_code == 403
    assert alice.get("/api/ingestion").status_code == 403

    duplicate = TestClient(app).post(
        "/api/auth/register",
        json={"username": "alice", "password": "another-strong-password"},
    )
    assert duplicate.status_code == 409
    relogin = TestClient(app).post(
        "/api/auth/login",
        json={"username": "alice", "password": "a-different-strong-password"},
    )
    assert relogin.status_code == 200


def test_registration_is_disabled_unless_explicitly_enabled(tmp_path):
    settings = Settings(
        mode="live",
        auth_password="a-strong-test-password-only",
        encryption_key=Fernet.generate_key().decode(),
        database_url=f"sqlite:///{tmp_path}/registration-disabled.db",
    )
    with TestClient(create_app(settings)) as client:
        assert client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "a-different-strong-password"},
        ).status_code == 404


def test_existing_secondary_session_stays_blocked_after_registration_is_disabled(tmp_path):
    settings = Settings(
        mode="live",
        auth_password="a-strong-test-password-only",
        encryption_key=Fernet.generate_key().decode(),
        openai_api_key="configured-for-owner",
        user_registration=True,
        database_url=f"sqlite:///{tmp_path}/registration-toggle.db",
    )
    client = TestClient(create_app(settings))
    registered = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "a-different-strong-password"},
    )
    assert registered.status_code == 200

    settings.user_registration = False

    assert client.get("/api/session").json()["voice_available"] is False
    assert client.get("/api/integrations").status_code == 403
    assert client.get("/api/ingestion").status_code == 403


def test_public_demo_requires_password_login_and_secure_configuration(tmp_path):
    with pytest.raises(ValueError):
        Settings(mode="demo", environment="production", public_demo=True, auth_password="too-short")
    with pytest.raises(ValueError):
        Settings(
            mode="demo",
            environment="production",
            public_demo=True,
            auth_password="a-strong-demo-password",
            allowed_origins=["http://demo.example.test"],
        )

    settings = Settings(
        mode="demo",
        environment="production",
        public_demo=True,
        auth_password="a-strong-demo-password",
        allowed_origins=["https://demo.example.test"],
        database_url=f"sqlite:///{tmp_path}/public-demo.db",
    )
    with TestClient(create_app(settings), base_url="https://demo.example.test") as c:
        assert c.get("/api/session").status_code == 401
        assert c.post("/api/auth/login", json={"password": "incorrect"}).status_code == 401
        login = c.post("/api/auth/login", json={"password": settings.auth_password})
        assert login.status_code == 200
        cookie = login.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "secure" in cookie
        c.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        assert c.post("/api/demo/run", json={"scenario": "flight"}).status_code == 200


def test_parser_generalizes_times():
    for text, expected in [
        ("Flight on 2026-09-15 moved to 8:15 PM", "20:15"),
        ("Meeting tomorrow at 12 AM", "00:00"),
        ("Meeting tomorrow at 12 PM", "12:00"),
        ("Flight tomorrow at 22:30", "22:30"),
    ]:
        event = extract(text, "Asia/Kolkata")
        assert event["new_time"] == expected
    assert extract("Flight tomorrow at 29:90", "Asia/Kolkata")["event_type"] == "unknown"


def test_restart_reconciles_inflight_without_replay(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path}/restart.db")
    app = create_app(settings)
    with TestClient(app) as c:
        session = c.get("/api/session").json()
        c.headers["X-CSRF-Token"] = session["csrf_token"]
        event = plan(c)
        owner = session["user"]["id"]
        event["actions"][0]["status"] = "executing"
        app.state.engine.save(owner, event)
        cookies = dict(c.cookies)
    with TestClient(create_app(settings)) as c:
        c.cookies.update(cookies)
        c.headers["X-CSRF-Token"] = session["csrf_token"]
        restored = c.get(f"/api/events/{event['id']}").json()
        assert restored["actions"][0]["status"] == "uncertain"
        assert c.post(f"/api/events/{event['id']}/retry").status_code == 409


def test_audit_tampering_detected(client):
    plan(client)
    owner = client.get("/api/session").json()["user"]["id"]
    db = client.app.state.db
    entry = db.list(owner, "audit")[0]
    entry["message"] = "altered history"
    db.put(owner, "audit", entry["id"], entry)
    assert client.get("/api/audit/verify").json()["valid"] is False


def test_migration_idempotent(tmp_path):
    from sqlalchemy import text
    from lifeos.store import Database

    db = Database(f"sqlite:///{tmp_path}/nested/migrate.db")
    db.migrate()
    with db.engine.connect() as connection:
        assert connection.execute(text("SELECT version FROM schema_revision")).scalar() == 2


def test_individual_approval_executes_only_selected(client):
    event = plan(client)
    selected = next(a for a in event["actions"] if a["application"] == "calendar")
    response = client.post(
        f"/api/events/{event['id']}/approve", json={"version": event["version"], "action_ids": [selected["id"]]}
    )
    assert response.status_code == 200
    event = client.post(f"/api/events/{event['id']}/execute").json()
    assert event["status"] == "awaiting_approval"
    assert next(a for a in event["actions"] if a["application"] == "calendar")["status"] == "verified"
    assert next(a for a in event["actions"] if a["application"] == "gmail")["status"] == "awaiting_approval"
    assert approve(client, event).status_code == 200
    assert client.post(f"/api/events/{event['id']}/execute").json()["status"] == "resolved"


def test_logout_revokes_session(client):
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/events").status_code == 401


@pytest.mark.asyncio
async def test_cancellation_survives_inflight_provider_save(tmp_path):
    import asyncio
    import httpx

    settings = Settings(database_url=f"sqlite:///{tmp_path}/cancel.db")
    app = create_app(settings)
    reached = asyncio.Event()
    release = asyncio.Event()

    class Provider:
        async def preflight(self, owner, actions):
            return None

        async def execute(self, owner, action, key):
            reached.set()
            await release.wait()
            return {"id": "fixture"}

        async def verify(self, owner, action, result):
            return {"verified": True, "detail": "Test fixture read-back"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
        session = (await c.get("/api/session")).json()
        from lifeos.security import COOKIE

        token = c.cookies.get(COOKIE)
        stored_session = app.state.db.get("system", "session", app.state.security.token_hash(token))
        stored_session["owner"] = "owner"
        app.state.db.put("system", "session", app.state.security.token_hash(token), stored_session)
        c.headers["X-CSRF-Token"] = session["csrf_token"]
        event = (await c.post("/api/demo/run", json={"scenario": "flight"})).json()
        await c.post(
            f"/api/events/{event['id']}/approve",
            json={
                "version": event["version"],
                "action_ids": [a["id"] for a in event["actions"] if a["requires_approval"]],
            },
        )
        app.state.engine.providers = Provider()
        settings.mode = "live"
        running = asyncio.create_task(c.post(f"/api/events/{event['id']}/execute"))
        await asyncio.wait_for(reached.wait(), 5)
        assert (await c.post(f"/api/events/{event['id']}/cancel")).status_code == 200
        release.set()
        result = (await running).json()
        assert result["status"] == "cancelled"
        assert sum(a.get("attempts", 0) for a in result["actions"]) == 1
        assert (await c.get("/api/audit/verify")).json()["valid"]


def test_calendar_edit_updates_dependent_draft_times(client):
    event = plan(client, "meeting")
    calendar = next(a for a in event["actions"] if a["application"] == "calendar")
    args = calendar["arguments"].copy()
    args["start"] = args["start"].replace("T14:00:00", "T15:30:00")
    args["end"] = args["end"].replace("T15:00:00", "T16:30:00")
    changed = client.patch(
        f"/api/events/{event['id']}/actions/{calendar['id']}", json={"arguments": args}
    ).json()
    gmail = next(a for a in changed["actions"] if a["application"] == "gmail")
    assert "15:30" in gmail["arguments"]["body"]
    assert "14:00" not in gmail["arguments"]["body"]
    assert (
        gmail["arguments_hash"]
        != next(a for a in event["actions"] if a["application"] == "gmail")["arguments_hash"]
    )


def test_execution_summary_reports_outcome(client):
    event = plan(client)
    assert "AI-742" in event["title"]
    approve(client, event)
    event = client.post(f"/api/events/{event['id']}/execute").json()
    assert "4 actions verified" in event["summary"]
    undone = client.post(f"/api/events/{event['id']}/undo").json()
    assert "Sent messages remain delivered" in undone["summary"]
