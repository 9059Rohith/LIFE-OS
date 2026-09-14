import json
import base64
from email import message_from_bytes
from types import SimpleNamespace

import httpx
import pytest

from lifeos.providers import LiveProviders, ProviderError
from lifeos.oauth import create_pkce, authorization_url, exchange_code, refresh_token


def client(handler, **config):
    settings = SimpleNamespace(mode="live", discord_channel_id="123", discord_bot_token="bot", **config)

    async def load(*args):
        return {"access_token": "token"}

    async def save(*args):
        pass

    provider = LiveProviders(settings, load, save)
    provider.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return provider


@pytest.mark.asyncio
async def test_unapproved_send_never_reaches_provider():
    provider = client(lambda r: pytest.fail("network forbidden"))
    with pytest.raises(ProviderError, match="approval"):
        await provider.execute("u", {"application": "gmail", "type": "send", "arguments": {}}, "k")
    await provider.close()


@pytest.mark.asyncio
async def test_calendar_patch_is_conditional_and_preserves_identity():
    original = {
        "id": "event",
        "etag": "v1",
        "recurrence": ["RRULE:FREQ=WEEKLY"],
        "conferenceData": {"conferenceId": "meet"},
        "start": {"dateTime": "2026-09-13T10:00:00+05:30"},
        "end": {"dateTime": "2026-09-13T11:00:00+05:30"},
    }
    updated = dict(original)
    calls = []

    def handler(request):
        calls.append(request.method)
        if request.method == "PATCH":
            assert request.headers["if-match"] == "v1"
            payload = json.loads(request.content)
            assert "recurrence" not in payload and "conferenceData" not in payload and "id" not in payload
            updated.update(payload)
        return httpx.Response(200, json=updated)

    provider = client(handler)
    action = {
        "_authorized": True,
        "application": "calendar",
        "type": "update",
        "arguments": {
            "event_id": "event",
            "etag": "v1",
            "start": {"dateTime": "2026-09-14T10:00:00+05:30"},
            "end": {"dateTime": "2026-09-14T11:00:00+05:30"},
        },
    }
    result = await provider.execute("u", action, "k")
    assert (await provider.verify("u", action, result))["verified"]
    assert calls == ["GET", "PATCH", "GET"]
    await provider.close()


@pytest.mark.asyncio
async def test_stale_calendar_approval_blocks_write():
    provider = client(lambda r: httpx.Response(200, json={"id": "e", "etag": "new"}))
    with pytest.raises(ProviderError, match="STALE_APPROVAL"):
        await provider.execute(
            "u",
            {
                "_authorized": True,
                "application": "calendar",
                "type": "cancel",
                "arguments": {"event_id": "e", "etag": "old"},
            },
            "k",
        )
    await provider.close()


@pytest.mark.asyncio
async def test_uncertain_discord_send_is_not_retried():
    calls = []

    def handler(request):
        calls.append(request.method)
        raise httpx.ReadTimeout("timeout", request=request)

    provider = client(handler)
    with pytest.raises(ProviderError, match="UNCERTAIN"):
        await provider.execute(
            "u",
            {
                "_authorized": True,
                "application": "discord",
                "type": "send",
                "arguments": {"channel_id": "123", "body": "Update"},
            },
            "k",
        )
    assert calls == ["POST"]
    await provider.close()


@pytest.mark.asyncio
async def test_unvalidated_recipient_is_blocked():
    provider = client(lambda r: pytest.fail("network forbidden"))
    with pytest.raises(ProviderError, match="recipient"):
        await provider.execute(
            "u",
            {
                "_authorized": True,
                "application": "gmail",
                "type": "send",
                "arguments": {"recipient": "attacker@example.com", "body": "secret"},
            },
            "k",
        )
    await provider.close()


def test_pkce_and_authorization_url():
    verifier, challenge = create_pkce()
    assert 43 <= len(verifier) <= 128 and len(challenge) == 43
    url = authorization_url(
        SimpleNamespace(
            google_client_id="id",
            google_redirect_uri="http://localhost:8000/api/integrations/google/callback",
        ),
        "state",
        challenge,
    )
    assert "code_challenge_method=S256" in url and "state=state" in url


@pytest.mark.asyncio
async def test_gmail_real_mime_send_and_content_readback():
    captured = {}

    def handler(request):
        if request.method == "POST":
            message = message_from_bytes(base64.urlsafe_b64decode(json.loads(request.content)["raw"]))
            captured.update(
                {"to": message["To"], "subject": message["Subject"], "message-id": message["Message-ID"]}
            )
            assert message.get_payload(decode=True).decode().strip() == "Updated meeting"
            return httpx.Response(200, json={"id": "sent-1"})
        return httpx.Response(
            200,
            json={
                "id": "sent-1",
                "labelIds": ["SENT"],
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [{"name": k, "value": v} for k, v in captured.items()],
                    "body": {"data": base64.urlsafe_b64encode(b"WRONG BODY").decode()},
                },
            },
        )

    provider = client(handler)
    action = {
        "_authorized": True,
        "_validated_recipients": ["alex@example.com"],
        "application": "gmail",
        "type": "send",
        "arguments": {"recipient": "alex@example.com", "subject": "Schedule", "body": "Updated meeting"},
    }
    result = await provider.execute("u", action, "stable-key")
    assert not (await provider.verify("u", action, result))["verified"]
    await provider.close()


@pytest.mark.asyncio
async def test_calendar_verification_accepts_equivalent_timezone_representation():
    provider = client(
        lambda r: httpx.Response(
            200, json={"id": "e", "start": {"dateTime": "2026-09-14T04:30:00Z", "timeZone": "Asia/Kolkata"}}
        )
    )
    result = {"id": "e", "expected": {"start": {"dateTime": "2026-09-14T10:00:00+05:30"}}}
    assert (await provider.verify("u", {"application": "calendar"}, result))["verified"]
    await provider.close()


@pytest.mark.asyncio
async def test_discord_blocks_mentions_and_verifies_content():
    posted = {}

    def handler(request):
        if request.method == "POST":
            posted.update(json.loads(request.content))
            assert posted["allowed_mentions"] == {"parse": []}
            assert posted["enforce_nonce"] is True
        return httpx.Response(200, json={"id": "m", "channel_id": "123", "content": posted["content"]})

    provider = client(handler)
    action = {
        "_authorized": True,
        "application": "discord",
        "type": "send",
        "arguments": {"channel_id": "123", "body": "@everyone schedule updated"},
    }
    result = await provider.execute("u", action, "k")
    assert (await provider.verify("u", action, result))["verified"]
    await provider.close()


@pytest.mark.asyncio
async def test_drive_export_and_maps_use_real_api_contracts():
    def handler(request):
        if "computeRoutes" in str(request.url):
            assert request.headers["x-goog-fieldmask"] == "routes.duration,routes.distanceMeters"
            assert json.loads(request.content)["origin"] == {"address": "Home"}
            return httpx.Response(200, json={"routes": [{"duration": "3600s", "distanceMeters": 40000}]})
        if request.url.path.endswith("/export"):
            return httpx.Response(200, text="Proposal document")
        return httpx.Response(
            200,
            json={
                "id": "doc",
                "name": "Proposal",
                "mimeType": "application/vnd.google-apps.document",
                "capabilities": {"canDownload": True},
            },
        )

    provider = client(handler, google_maps_api_key="key")
    doc = await provider.drive_read("u", "doc")
    assert doc["text"] == "Proposal document"
    action = {
        "_authorized": True,
        "application": "maps",
        "type": "route",
        "arguments": {"origin": "Home", "destination": "Airport"},
    }
    result = await provider.execute("u", action, "k")
    assert (await provider.verify("u", action, result))["verified"]
    await provider.close()


@pytest.mark.asyncio
async def test_calendar_cancel_reads_back_deleted_resource():
    def handler(request):
        if request.method == "DELETE":
            assert request.headers["if-match"] == "v1"
            return httpx.Response(204)
        return httpx.Response(200, json={"id": "e", "etag": "v1"})

    provider = client(handler)
    action = {
        "_authorized": True,
        "application": "calendar",
        "type": "cancel",
        "arguments": {"event_id": "e", "etag": "v1"},
    }
    result = await provider.execute("u", action, "k")
    await provider.http.aclose()
    provider.http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(410)))
    assert (await provider.verify("u", action, result))["verified"]
    await provider.close()


@pytest.mark.asyncio
async def test_oauth_exchange_and_refresh_preserve_refresh_token(monkeypatch):
    from urllib.parse import parse_qs

    original = httpx.AsyncClient

    def handler(request):
        body = parse_qs(request.content.decode())
        assert request.url.host == "oauth2.googleapis.com"
        if body["grant_type"] == ["authorization_code"]:
            assert body["code_verifier"] == ["verifier"]
            return httpx.Response(
                200, json={"access_token": "first", "refresh_token": "refresh", "expires_in": 3600}
            )
        assert body["refresh_token"] == ["refresh"]
        return httpx.Response(200, json={"access_token": "second", "expires_in": 3600})

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )
    settings = SimpleNamespace(
        google_client_id="id", google_client_secret="secret", google_redirect_uri="http://localhost/callback"
    )
    token = await exchange_code(settings, "code", "verifier")
    updated = await refresh_token(settings, token)
    assert updated["refresh_token"] == "refresh" and updated["access_token"] == "second"
    assert updated["expires_at"] > 0


@pytest.mark.asyncio
async def test_malformed_successful_send_is_uncertain():
    provider = client(
        lambda r: httpx.Response(200, text="not JSON", headers={"content-type": "application/json"})
    )
    with pytest.raises(ProviderError, match="UNCERTAIN"):
        await provider.execute(
            "u",
            {
                "_authorized": True,
                "application": "discord",
                "type": "send",
                "arguments": {"channel_id": "123", "body": "Update"},
            },
            "k",
        )
    await provider.close()


@pytest.mark.asyncio
async def test_configured_route_context_uses_actual_routes_response():
    def handler(request):
        if request.url.host == "routes.googleapis.com":
            assert json.loads(request.content)["origin"] == {"address": "Configured home"}
            return httpx.Response(200, json={"routes": [{"duration": "3721s", "distanceMeters": 42000}]})
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json=[] if "discord" in request.url.host else {"messages": []})
        return httpx.Response(200, json={"items": [], "files": []})

    provider = client(
        handler,
        google_maps_api_key="key",
        maps_origin="Configured home",
        maps_destination="Configured airport",
    )
    context = await provider.context("u", "Flight AI-742 tomorrow moved to 06:40")
    routes = next(c["records"] for c in context if c["application"] == "maps")
    assert routes[0]["duration_minutes"] == 63
    assert routes[0]["origin"] == "Configured home"
    assert routes[0]["source"] == "Google Routes API"
    await provider.close()


@pytest.mark.asyncio
async def test_preflight_checks_later_calendar_before_any_write():
    calls = []

    def handler(request):
        calls.append(request.method)
        assert request.method == "GET"
        return httpx.Response(200, json={"id": "meeting", "etag": "changed"})

    provider = client(handler)
    actions = [
        {"application": "gmail", "type": "send", "arguments": {}},
        {
            "application": "calendar",
            "type": "update",
            "arguments": {"event_id": "meeting", "etag": "approved"},
        },
    ]
    with pytest.raises(ProviderError, match="STALE_APPROVAL"):
        await provider.preflight("u", actions)
    assert calls == ["GET"]
    await provider.close()


@pytest.mark.asyncio
async def test_gmail_attachment_readback_compares_content_hash():
    import hashlib

    def handler(request):
        if "/attachments/" in request.url.path:
            return httpx.Response(200, json={"data": base64.urlsafe_b64encode(b"WRONG PROPOSAL").decode()})
        return httpx.Response(
            200,
            json={
                "id": "m",
                "labelIds": ["SENT"],
                "payload": {
                    "headers": [
                        {"name": "Message-ID", "value": "<id>"},
                        {"name": "To", "value": "alex@example.com"},
                        {"name": "Subject", "value": "Proposal"},
                    ],
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {"data": base64.urlsafe_b64encode(b"Attached").decode()},
                        },
                        {"mimeType": "text/plain", "filename": "Proposal.txt", "body": {"attachmentId": "a"}},
                    ],
                },
            },
        )

    provider = client(handler)
    action = {
        "application": "gmail",
        "arguments": {
            "recipient": "alex@example.com",
            "subject": "Proposal",
            "body": "Attached",
            "attachment_id": "doc",
        },
    }
    result = {
        "id": "m",
        "message_id": "<id>",
        "attachment_sha256": hashlib.sha256(b"APPROVED PROPOSAL").hexdigest(),
    }
    assert not (await provider.verify("u", action, result))["verified"]
    await provider.close()


@pytest.mark.asyncio
async def test_route_growth_blocks_frozen_departure_plan():
    provider = client(lambda r: pytest.fail("verification uses returned computation"))
    action = {"application": "maps", "arguments": {"duration_minutes": 55}}
    result = {"routes": [{"duration": "4200s", "distanceMeters": 42000}]}
    assert not (await provider.verify("u", action, result))["verified"]
    await provider.close()
