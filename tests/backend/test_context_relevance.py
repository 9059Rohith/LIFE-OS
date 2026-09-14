import asyncio
from copy import deepcopy

import httpx

from lifeos.config import Settings
from lifeos.planning import extract, make_plan
from lifeos.providers import LiveProviders


def records():
    return [
        {
            "application": "calendar",
            "records": [
                {
                    "id": "acme",
                    "title": "Acme proposal review",
                    "participants": ["alex@example.com"],
                    "start": "2026-09-15T09:00:00+05:30",
                    "end": "2026-09-15T10:00:00+05:30",
                },
                {
                    "id": "other",
                    "title": "Other client meeting",
                    "participants": ["other@example.com"],
                    "start": "2026-09-15T16:00:00+05:30",
                    "end": "2026-09-15T17:00:00+05:30",
                },
                {
                    "id": "other-date",
                    "title": "Acme proposal review",
                    "participants": ["alex@example.com"],
                    "start": "2026-09-16T09:00:00+05:30",
                    "end": "2026-09-16T10:00:00+05:30",
                },
            ],
        },
        {
            "application": "gmail",
            "records": [
                {"id": "spam", "recipient": "stranger@example.com"},
                {"id": "known", "recipient": "alex@example.com"},
            ],
        },
    ]


def plan(text, context):
    return make_plan(text, "text", False, extract(text, "Asia/Kolkata"), context, "Asia/Kolkata", "live")


def test_named_meeting_and_explicit_date_ignore_unrelated_calendar_entries():
    event = plan('The "Acme proposal review" meeting on 2026-09-15 moved to 2 PM', records())
    assert event["status"] == "awaiting_approval"
    action = next(a for a in event["actions"] if a["application"] == "calendar")
    assert action["arguments"]["event_id"] == "acme"
    email = next(a for a in event["actions"] if a["application"] == "gmail")
    assert email["arguments"]["recipient"] == "alex@example.com"
    assert email["requires_approval"]


def test_ambiguous_named_meeting_still_requires_clarification():
    context = records()
    duplicate = deepcopy(context[0]["records"][0])
    duplicate["id"] = "second-acme"
    context[0]["records"].append(duplicate)
    result = plan('The "Acme proposal review" meeting on 2026-09-15 moved to 2 PM', context)
    assert result["status"] == "clarification_required" and not result["actions"]


def test_missing_date_does_not_invent_today():
    assert extract("Acme meeting moved to 2 PM", "Asia/Kolkata")["event_type"] == "unknown"


def test_flight_number_prefix_is_not_exact_match():
    context = records()
    context[0]["records"] = context[0]["records"][:1] + [
        {
            "id": "different-flight",
            "title": "Flight AI-7420",
            "start": "2026-09-15T11:30:00+05:30",
            "end": "2026-09-15T14:15:00+05:30",
        }
    ]
    result = plan("Flight AI-742 on 2026-09-15 moved to 6:40 AM", context)
    assert result["status"] == "clarification_required" and not result["actions"]


def test_flight_ignores_unrelated_dates_and_nonoverlapping_meetings():
    context = records()
    context[0]["records"].append(
        {
            "id": "flight",
            "title": "Flight AI-742",
            "start": "2026-09-15T11:30:00+05:30",
            "end": "2026-09-15T14:15:00+05:30",
        }
    )
    result = plan("Flight AI-742 on 2026-09-15 moved to 6:40 AM", context)
    assert result["status"] == "awaiting_approval"
    assert (
        next(a for a in result["actions"] if a["application"] == "calendar")["arguments"]["event_id"]
        == "acme"
    )


def test_proposed_flight_reschedule_cannot_overlap_unrelated_busy_appointment():
    context = records()
    context[0]["records"] += [
        {
            "id": "flight",
            "title": "Flight AI-742",
            "start": "2026-09-15T11:30:00+05:30",
            "end": "2026-09-15T14:15:00+05:30",
        },
        {
            "id": "dentist",
            "title": "Dentist",
            "start": "2026-09-15T10:30:00+05:30",
            "end": "2026-09-15T12:00:00+05:30",
        },
    ]
    result = plan("Flight AI-742 on 2026-09-15 moved to 6:40 AM", context)
    assert result["status"] == "clarification_required" and not result["actions"]
    assert "overlaps" in result["summary"]


def test_explicit_meeting_move_cannot_overlap_another_appointment():
    result = plan('The "Acme proposal review" meeting on 2026-09-15 moved to 4 PM', records())
    assert result["status"] == "clarification_required" and not result["actions"]
    assert "overlaps" in result["summary"]


def test_gmail_thread_identity_is_distinct_from_message_identity():
    context = records()
    context[1]["records"][1]["thread_id"] = "actual-thread"
    result = plan('The "Acme proposal review" meeting on 2026-09-15 moved to 2 PM', context)
    email = next(a for a in result["actions"] if a["application"] == "gmail")
    assert email["arguments"]["thread_id"] == "actual-thread"
    del context[1]["records"][1]["thread_id"]
    result = plan('The "Acme proposal review" meeting on 2026-09-15 moved to 2 PM', context)
    email = next(a for a in result["actions"] if a["application"] == "gmail")
    assert not email["arguments"].get("thread_id")


def test_live_context_searches_known_attendee_instead_of_latest_mail():
    calls = []

    def respond(request):
        calls.append(request)
        if "/calendar/v3/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "acme",
                            "summary": "Acme proposal review",
                            "attendees": [{"email": "alex@example.com"}],
                            "start": {"dateTime": "2026-09-15T09:00:00+05:30"},
                            "end": {"dateTime": "2026-09-15T10:00:00+05:30"},
                        }
                    ]
                },
            )
        if request.url.path.endswith("/messages"):
            known = "from:alex@example.com" in request.url.params.get("q", "")
            return httpx.Response(200, json={"messages": [{"id": "known" if known else "spam"}]})
        if "/messages/" in request.url.path:
            known = request.url.path.endswith("known")
            return httpx.Response(
                200,
                json={
                    "id": "known" if known else "spam",
                    "threadId": "actual-thread" if known else "spam-thread",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "alex@example.com" if known else "stranger@example.com"}
                        ]
                    },
                },
            )
        return httpx.Response(200, json={"files": []})

    async def run():
        async def token(*args):
            return {"access_token": "test-token"}

        provider = LiveProviders(Settings(), token, token)
        await provider.http.aclose()
        provider.http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            return await provider.context(
                "owner", 'The "Acme proposal review" meeting on 2026-09-15 moved to 2 PM'
            )
        finally:
            await provider.close()

    context = asyncio.run(run())
    assert (
        next(c for c in context if c["application"] == "gmail")["records"][0]["recipient"]
        == "alex@example.com"
    )
    calendar_request = next(r for r in calls if "/calendar/v3/" in r.url.path)
    assert calendar_request.url.params["timeMin"].startswith("2026-09-15")
    assert (
        next(c for c in context if c["application"] == "gmail")["records"][0]["thread_id"] == "actual-thread"
    )
