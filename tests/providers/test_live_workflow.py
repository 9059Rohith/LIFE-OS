"""Full live adapter/engine contracts, backed by HTTP fixtures rather than accounts."""

import base64
import json
from email import message_from_bytes, policy
from types import SimpleNamespace

import httpx
import pytest

from lifeos.engine import Engine
from lifeos.providers import LiveProviders
from lifeos.store import Database


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["meeting", "flight"])
async def test_live_engine_approval_execution_readback_and_replay(tmp_path, scenario):
    calendar = {
        "id": "meeting",
        "summary": "Client meeting",
        "etag": "v1",
        "start": {"dateTime": "2026-09-15T09:00:00+05:30"},
        "end": {"dateTime": "2026-09-15T10:00:00+05:30"},
        "attendees": [{"email": "client@example.com"}],
        "conferenceData": {"conferenceId": "existing-meet"},
    }
    flight = {
        "id": "flight",
        "summary": "AI-742 to Delhi",
        "etag": "f1",
        "start": {"dateTime": "2026-09-15T11:30:00+05:30"},
        "end": {"dateTime": "2026-09-15T15:45:00+05:30"},
    }
    sent = {}
    writes = []

    def handler(request):
        path = request.url.path
        if request.method in {"POST", "PATCH"}:
            writes.append((request.method, path))
        if path.endswith("/calendars/primary/events"):
            return httpx.Response(200, json={"items": [calendar, flight]})
        if path.endswith("/events/meeting"):
            if request.method == "PATCH":
                assert request.headers["if-match"] == "v1"
                calendar.update(json.loads(request.content))
                calendar["etag"] = "v2"
            return httpx.Response(200, json=calendar)
        if path.endswith("/files/proposal/export"):
            return httpx.Response(200, text="Approved client proposal")
        if path.endswith("/files/proposal"):
            return httpx.Response(
                200,
                json={
                    "id": "proposal",
                    "name": "Final document",
                    "mimeType": "application/vnd.google-apps.document",
                    "capabilities": {"canDownload": True},
                },
            )
        if path.endswith("/messages"):
            return httpx.Response(200, json={"messages": [{"id": "incoming"}]})
        if path.endswith("/messages/incoming"):
            return httpx.Response(
                200,
                json={
                    "id": "incoming",
                    "snippet": "Please update our meeting",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Client <client@example.com>"},
                            {"name": "Subject", "value": "Client meeting"},
                        ]
                    },
                },
            )
        if path.endswith("/messages/send"):
            message = message_from_bytes(
                base64.urlsafe_b64decode(json.loads(request.content)["raw"]), policy=policy.default
            )

            def part(item):
                if item.is_multipart():
                    return {
                        "mimeType": item.get_content_type(),
                        "parts": [part(p) for p in item.iter_parts()],
                    }
                return {
                    "mimeType": item.get_content_type(),
                    "filename": item.get_filename() or "",
                    "body": {"data": base64.urlsafe_b64encode(item.get_payload(decode=True)).decode()},
                }

            payload = part(message)
            payload["headers"] = [{"name": key, "value": str(value)} for key, value in message.items()]
            sent.update({"id": "sent", "labelIds": ["SENT"], "payload": payload})
            return httpx.Response(200, json={"id": "sent"})
        if path.endswith("/messages/sent"):
            return httpx.Response(200, json=sent)
        pytest.fail(f"Unexpected provider request: {request.method} {path}")

    settings = SimpleNamespace(
        mode="live",
        approval_seconds=600,
        openai_api_key="",
        discord_bot_token="",
        whatsapp_enabled=False,
        drive_proposal_file_id="proposal",
    )

    async def load(*args):
        return {"access_token": "fixture"}

    async def save(*args):
        pass

    providers = LiveProviders(settings, load, save)
    await providers.http.aclose()
    providers.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    db = Database(f"sqlite:///{tmp_path}/workflow.db")
    engine = Engine(db, settings, providers)
    text = (
        "Meeting on 2026-09-15 moved to 5 PM. Send the updated proposal."
        if scenario == "meeting"
        else "Flight AI-742 on 2026-09-15 moved to 6:40 AM."
    )
    event = await engine.plan("owner", text, "text", False)
    assert event["status"] == "awaiting_approval"
    assert writes == []
    event = engine.approve(
        "owner", event, [a["id"] for a in event["actions"] if a["requires_approval"]], event["version"]
    )
    event = await engine.execute("owner", event)
    assert event["status"] == "resolved", event["actions"]
    assert all(a["evidence"]["verified"] for a in event["actions"])
    assert len(writes) == 2
    assert calendar["conferenceData"]["conferenceId"] == "existing-meet"
    if scenario == "meeting":
        assert any(p.get("filename") for p in sent["payload"]["parts"])
    else:
        assert event["entities"]["arrival_time"] == "2026-09-15T10:55:00+05:30"
    await engine.execute("owner", event)
    assert len(writes) == 2
    await providers.close()
    db.engine.dispose()
