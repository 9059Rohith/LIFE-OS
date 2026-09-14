import pytest
from lifeos.store import Database
from lifeos.telemetry import record, scope, snapshot


def test_usage_is_measured_owner_scoped_and_does_not_store_content():
    db = Database("sqlite:///:memory:")
    with scope(db, "alice"):
        record("responses", 42, True, {"input_tokens": 10, "output_tokens": 3, "total_tokens": 13})
        record("audio/speech", 20, True, None, output_bytes=900)
    measured = snapshot(db, "alice")
    assert measured["requests"] == 2
    assert measured["input_tokens"] == 10 and measured["output_tokens"] == 3
    assert measured["usage_reported_requests"] == 1 and measured["audio_output_bytes"] == 900
    assert snapshot(db, "bob")["requests"] == 0
    assert "text" not in measured
    db.engine.dispose()


def test_export_excludes_credentials_and_delete_invalidates_session(client):
    owner = client.get("/api/session").json()["user"]["id"]
    db = client.app.state.db
    db.put(owner, "token", owner + ":token:google", {"encrypted": "private-credential"})
    response = client.get("/api/privacy/export")
    assert response.status_code == 200
    assert "private-credential" not in response.text
    assert client.post("/api/privacy/delete", json={"confirmation": "wrong"}).status_code == 422
    assert db.get(owner, "token", owner + ":token:google")
    result = client.post("/api/privacy/delete", json={"confirmation": "DELETE MY DATA"})
    assert result.status_code == 200
    assert db.list(owner, "app") == [] and db.list(owner, "token") == []
    assert client.get("/api/events").status_code == 401


def test_deletion_is_owner_scoped_and_requires_csrf(client):
    db = client.app.state.db
    db.put("other", "event", "other-event", {"id": "other-event"})
    token = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/privacy/delete", json={"confirmation": "DELETE MY DATA"}).status_code == 403
    client.headers["X-CSRF-Token"] = token
    assert client.post("/api/privacy/delete", json={"confirmation": "DELETE MY DATA"}).status_code == 200
    assert db.get("other", "event", "other-event")


def test_retention_preserves_uncertain_execution_evidence():
    import time
    from lifeos.store import Document

    db = Database("sqlite:///:memory:")
    db.put(
        "owner",
        "event",
        "pending",
        {"id": "pending", "status": "partial_failure", "actions": [{"status": "uncertain"}]},
    )
    db.put(
        "owner", "event", "done", {"id": "done", "status": "resolved", "actions": [{"status": "verified"}]}
    )
    with db.sessions.begin() as session:
        session.get(Document, "pending").created = time.time() - 86400 * 10
        session.get(Document, "done").created = time.time() - 86400 * 10
    db.prune_events("owner", 1)
    assert db.get("owner", "event", "pending")
    assert db.get("owner", "event", "done") is None
    db.engine.dispose()


@pytest.mark.asyncio
async def test_transcription_records_actual_provider_usage_without_recording_speech(monkeypatch):
    import httpx
    from lifeos import ai

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "text": "private spoken words",
                "usage": {"input_tokens": 4, "output_tokens": 2, "total_tokens": 6},
            },
        )
    )
    monkeypatch.setattr(ai.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    db = Database("sqlite:///:memory:")
    with scope(db, "owner"):
        assert await ai.transcribe(b"fixture audio", "clip.wav", "test-fixture") == "private spoken words"
    measured = snapshot(db, "owner")
    assert measured["total_tokens"] == 6 and measured["audio_input_bytes"] == 13
    assert "private spoken words" not in str(measured)
    db.engine.dispose()


def test_delete_refuses_uncertain_actions(client):
    owner = client.get("/api/session").json()["user"]["id"]
    client.app.state.db.put(
        owner, "event", "uncertain-event", {"status": "partial_failure", "actions": [{"status": "uncertain"}]}
    )
    assert client.post("/api/privacy/delete", json={"confirmation": "DELETE MY DATA"}).status_code == 409
    assert client.app.state.db.get(owner, "event", "uncertain-event")
