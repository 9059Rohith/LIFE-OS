from lifeos.planning import make_plan, extract
from lifeos.policy import classify, approval_valid
import pytest


def context():
    return [
        {
            "application": "calendar",
            "records": [
                {
                    "id": "meeting-real",
                    "title": "Client meeting",
                    "participants": ["client@example.com"],
                    "start": {"dateTime": "2026-09-15T09:00:00+05:30"},
                    "end": {"dateTime": "2026-09-15T10:00:00+05:30"},
                    "etag": "v1",
                },
                {
                    "id": "flight-real",
                    "title": "AI-742 to Delhi",
                    "start": {"dateTime": "2026-09-15T11:30:00+05:30"},
                    "end": {"dateTime": "2026-09-15T15:45:00+05:30"},
                    "etag": "flight-v1",
                },
            ],
        },
        {"application": "gmail", "records": [{"id": "mail-real", "recipient": "client@example.com"}]},
        {
            "application": "drive",
            "records": [
                {"id": "doc-real", "title": "Final document", "configured": True, "content_sha256": "a" * 64}
            ],
        },
    ]


def test_live_flight_omits_unverified_travel_time():
    entities = extract("Flight AI-742 on 2026-09-15 moved to 6:40 AM", "Asia/Kolkata")
    event = make_plan("Flight AI-742", "gmail", False, entities, context(), "Asia/Kolkata", "live")
    assert event["status"] == "awaiting_approval"
    assert event["entities"]["departure_time"] is None
    assert event["limitations"]
    assert all(action["application"] != "maps" for action in event["actions"])
    assert event["entities"]["arrival_time"] == "2026-09-15T10:55:00+05:30"
    assert (
        next(a for a in event["actions"] if a["application"] == "calendar")["arguments"]["start"]
        == "2026-09-15T12:00:00+05:30"
    )
    assert (
        next(a for a in event["actions"] if a["application"] == "gmail")["arguments"]["recipient"]
        == "client@example.com"
    )


def test_live_flight_only_offers_whatsapp_for_a_verified_configured_chat():
    source_text = "Flight AI-742 on 2026-09-15 moved to 6:40 AM. Send WhatsApp to +999999999."
    entities = extract(source_text, "Asia/Kolkata")
    unverified = context() + [
        {"application": "whatsapp", "records": [{"contact": "Family"}]}
    ]
    assert not any(
        action["application"] == "whatsapp"
        for action in make_plan("Flight AI-742", "gmail", False, entities, unverified, "Asia/Kolkata", "live")["actions"]
    )
    verified = context() + [
        {"application": "whatsapp", "records": [{"contact": "Family", "verified": True}]}
    ]
    event = make_plan(source_text, "gmail", False, entities, verified, "Asia/Kolkata", "live")
    action = next(action for action in event["actions"] if action["application"] == "whatsapp")
    assert action["requires_approval"] and action["status"] == "awaiting_approval"
    assert action["arguments"]["contact"] == "Family"
    assert "+999999999" not in action["arguments"]["body"]
    assert "AI-742" in action["arguments"]["body"]
    assert "06:40" in action["arguments"]["body"]
    assert "pickup time" not in action["arguments"]["body"].lower()
    assert action["dependencies"] == [
        next(item["id"] for item in event["actions"] if item["application"] == "calendar")
    ]


def test_live_meeting_binds_configured_proposal_hash():
    entities = extract("Meeting on 2026-09-15 moved to 5 PM", "Asia/Kolkata")
    event = make_plan("Meeting moved", "text", False, entities, context(), "Asia/Kolkata", "live")
    gmail = next(a for a in event["actions"] if a["application"] == "gmail")
    assert gmail["arguments"]["attachment_id"] == "doc-real"
    assert gmail["arguments"]["attachment_sha256"] == "a" * 64


def test_live_missing_flight_or_ambiguous_recipient_fails_closed():
    entities = extract("Flight AI-999 on 2026-09-15 moved to 6:40 AM", "Asia/Kolkata")
    event = make_plan("Flight AI-999", "gmail", False, entities, context(), "Asia/Kolkata", "live")
    assert event["status"] == "clarification_required" and not event["actions"]
    records = context()
    records[1]["records"][0]["recipient"] = "attacker@example.com"
    entities = extract("Meeting on 2026-09-15 moved to 2 PM", "Asia/Kolkata")
    event = make_plan("Meeting", "text", False, entities, records, "Asia/Kolkata", "live")
    assert event["status"] == "clarification_required" and not event["actions"]


def test_typed_policy_denies_unknown_and_expiration():
    with pytest.raises(ValueError):
        classify("gmail", "delete_all")
    assert classify("gmail", "send").requires_approval
    with pytest.raises(ValueError):
        classify("maps", "route")
    assert not approval_valid({"version": 1, "hash": "x", "expires": float("nan")}, 1, "x", 0)
    assert not approval_valid({"version": 1, "hash": "x", "expires": 10.0}, 2, "x", 0)
