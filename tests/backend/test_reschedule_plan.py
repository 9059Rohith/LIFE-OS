from datetime import datetime
from types import SimpleNamespace

import pytest

from lifeos.engine import Engine


class MemoryDB:
    def __init__(self):
        self.values = {}
        self.audits = []

    def get(self, owner, kind, key):
        return self.values.get((owner, kind, key))

    def put(self, owner, kind, key, value):
        self.values[(owner, kind, key)] = value

    def audit(self, owner, stage, message, *args):
        self.audits.append((owner, stage, message))

    def prune_events(self, owner, days):
        return None


class CalendarReader:
    def __init__(self, event, busy=None):
        self.event = event
        self.busy = busy or []
        self.calls = []

    async def _google(self, owner, method, url, **kwargs):
        self.calls.append((owner, method, url, kwargs))
        assert owner == "owner-1"
        assert method == "GET"
        if url.endswith("/events/event-1"):
            return self.event
        return {"items": self.busy}


def settings(**values):
    defaults = {
        "mode": "live",
        "discord_bot_token": "discord-token",
        "discord_channel_id": "channel-1",
        "whatsapp_enabled": True,
        "whatsapp_bridge_enabled": False,
        "whatsapp_contact": "Family",
    }
    return SimpleNamespace(**(defaults | values))


@pytest.mark.asyncio
async def test_reschedule_plan_fetches_exact_owner_event_and_gates_notifications_on_calendar():
    event = {
        "id": "event-1",
        "etag": "etag-1",
        "status": "confirmed",
        "summary": "Design review",
        "start": {"dateTime": "2030-01-15T09:00:00+05:30"},
        "end": {"dateTime": "2030-01-15T10:00:00+05:30"},
    }
    providers = CalendarReader(event)
    engine = Engine(MemoryDB(), settings(), providers)

    plan = await engine.plan_reschedule(
        "owner-1",
        "event-1",
        datetime.fromisoformat("2030-01-15T14:00:00+05:30"),
        datetime.fromisoformat("2030-01-15T15:00:00+05:30"),
        "Asia/Kolkata",
        notify_discord=True,
        notify_whatsapp=True,
    )

    calendar = next(action for action in plan["actions"] if action["application"] == "calendar")
    assert calendar["requires_approval"]
    assert calendar["arguments"]["etag"] == "etag-1"
    assert calendar["arguments"]["start"] == "2030-01-15T14:00:00+05:30"
    assert {action["application"] for action in plan["actions"]} == {"calendar", "discord", "whatsapp"}
    assert all(
        calendar["id"] in action["dependencies"]
        for action in plan["actions"]
        if action["application"] in {"discord", "whatsapp"}
    )
    assert providers.calls[0][2].endswith("/events/event-1")
    assert all(method == "GET" for _, method, _, _ in providers.calls)


@pytest.mark.asyncio
async def test_reschedule_plan_rejects_busy_slot_without_creating_a_plan():
    target = {
        "id": "event-1", "etag": "etag-1", "status": "confirmed", "summary": "Design review",
        "start": {"dateTime": "2030-01-15T09:00:00+05:30"},
        "end": {"dateTime": "2030-01-15T10:00:00+05:30"},
    }
    busy = [{
        "id": "busy-1", "status": "confirmed", "summary": "Busy",
        "start": {"dateTime": "2030-01-15T14:30:00+05:30"},
        "end": {"dateTime": "2030-01-15T15:30:00+05:30"},
    }]
    engine = Engine(MemoryDB(), settings(), CalendarReader(target, busy))

    with pytest.raises(ValueError, match="overlaps"):
        await engine.plan_reschedule(
            "owner-1", "event-1", "2030-01-15T14:00:00+05:30", "2030-01-15T15:00:00+05:30", "Asia/Kolkata"
        )


@pytest.mark.asyncio
async def test_reschedule_plan_requires_same_duration_and_present_etag():
    target = {
        "id": "event-1", "status": "confirmed", "summary": "Design review",
        "start": {"dateTime": "2030-01-15T09:00:00+05:30"},
        "end": {"dateTime": "2030-01-15T10:00:00+05:30"},
    }
    engine = Engine(MemoryDB(), settings(discord_bot_token="", whatsapp_enabled=False), CalendarReader(target))

    with pytest.raises(ValueError, match="etag"):
        await engine.plan_reschedule(
            "owner-1", "event-1", "2030-01-15T14:00:00+05:30", "2030-01-15T16:00:00+05:30", "Asia/Kolkata"
        )
