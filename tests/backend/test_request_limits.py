import asyncio

import pytest
from fastapi import HTTPException

from lifeos.limits import BodyLimitMiddleware, VoiceBudget


def test_application_rejects_chunked_oversize_multipart(client):
    response = client.post(
        "/api/voice/transcribe",
        content=iter([b"a" * 6_000_001, b"b" * 6_000_000]),
        headers={"content-type": "multipart/form-data; boundary=x"},
    )
    assert response.status_code == 413


def test_speech_endpoint_enforces_separate_budget(monkeypatch):
    from fastapi.testclient import TestClient
    from lifeos.config import Settings
    from lifeos.main import create_app
    from lifeos import ai

    calls = []

    async def speak(text, key):
        calls.append(text)
        return b"audio"

    monkeypatch.setattr(ai, "speak", speak)
    with TestClient(create_app(Settings(database_url="sqlite:///:memory:", openai_api_key="test"))) as c:
        c.headers["X-CSRF-Token"] = c.get("/api/session").json()["csrf_token"]
        for _ in range(12):
            assert c.post("/api/voice/speak", json={"text": "hello"}).status_code == 200
        assert c.post("/api/voice/speak", json={"text": "hello"}).status_code == 429
        assert len(calls) == 12
        assert c.get("/api/events").status_code == 200


def test_chunked_body_rejected_before_application_parses_multipart():
    async def run():
        called = False
        sent = []
        chunks = iter([
            {"type": "http.request", "body": b"123456", "more_body": True},
            {"type": "http.request", "body": b"78901", "more_body": False},
        ])

        async def receive():
            return next(chunks)

        async def send(message):
            sent.append(message)

        async def app(scope, receive, send):
            nonlocal called
            called = True

        await BodyLimitMiddleware(app, maximum=10)(
            {"type": "http", "headers": [(b"content-type", b"multipart/form-data; boundary=x")]},
            receive, send,
        )
        assert not called
        assert sent[0]["status"] == 413

    asyncio.run(run())


def test_body_at_limit_replayed_exactly():
    async def run():
        chunks = iter([
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"45", "more_body": False},
        ])

        async def receive():
            return next(chunks)

        async def app(scope, receive, send):
            message = await receive()
            assert message["body"] == b"12345"
            assert not message["more_body"]

        await BodyLimitMiddleware(app, maximum=5)({"type": "http", "headers": []}, receive, None)

    asyncio.run(run())


def test_upload_admission_rejects_before_receive_and_releases_after_cancellation():
    async def run():
        entered = asyncio.Event()
        stay_open = asyncio.Event()

        async def app(scope, receive, send):
            message = await receive()
            assert message["body"] == b"12345"
            entered.set()
            await stay_open.wait()

        middleware = BodyLimitMiddleware(app, maximum=5, concurrency=1)

        async def receive():
            return {"type": "http.request", "body": b"12345", "more_body": False}

        async def send(message):
            pass

        scope = {"type": "http", "method": "POST", "headers": []}
        active = asyncio.create_task(middleware(scope, receive, send))
        await entered.wait()
        rejected = []

        async def must_not_receive():
            raise AssertionError("Saturated uploads must be rejected before reading")

        async def reject_send(message):
            rejected.append(message)

        await middleware(scope, must_not_receive, reject_send)
        assert rejected[0]["status"] == 429
        rejected.clear()
        await middleware(
            {"type": "http", "method": "GET", "headers": [(b"transfer-encoding", b"chunked")]},
            must_not_receive,
            reject_send,
        )
        assert rejected[0]["status"] == 429
        active.cancel()
        with pytest.raises(asyncio.CancelledError):
            await active
        stay_open.set()
        await middleware(scope, receive, send)

    asyncio.run(run())


def test_bodyless_health_request_does_not_consume_upload_slot():
    async def run():
        entered = asyncio.Event()
        stay_open = asyncio.Event()
        observed = []

        async def app(scope, receive, send):
            observed.append(scope["method"])
            if scope["method"] == "POST":
                entered.set()
                await stay_open.wait()

        middleware = BodyLimitMiddleware(app, concurrency=1)

        async def receive():
            return {"type": "http.request", "body": b"x", "more_body": False}

        active = asyncio.create_task(middleware(
            {"type": "http", "method": "POST", "headers": []}, receive, None
        ))
        await entered.wait()
        await middleware({"type": "http", "method": "GET", "headers": []}, receive, None)
        assert observed == ["POST", "GET"]
        stay_open.set()
        await active

    asyncio.run(run())


def test_voice_concurrency_and_rate_are_independent_and_release_on_failure():
    async def run():
        budget = VoiceBudget(concurrency=1, per_minute=2)
        with pytest.raises(RuntimeError):
            async with budget.acquire("owner"):
                with pytest.raises(HTTPException) as busy:
                    async with budget.acquire("other"):
                        pass
                assert busy.value.status_code == 429
                raise RuntimeError("provider failed")
        async with budget.acquire("owner"):
            pass
        with pytest.raises(HTTPException) as limited:
            async with budget.acquire("owner"):
                pass
        assert limited.value.status_code == 429
        async with budget.acquire("other"):
            pass

    asyncio.run(run())
