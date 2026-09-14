from lifeos.planning import extract, make_plan


def test_live_flight_without_maps_keeps_independent_actions_and_omits_pickup():
    context = [
        {
            "application": "calendar",
            "records": [
                {
                    "id": "meeting",
                    "title": "Client meeting",
                    "participants": ["client@example.com"],
                    "start": "2026-09-15T09:00:00+05:30",
                    "end": "2026-09-15T10:00:00+05:30",
                    "etag": "v1",
                },
                {
                    "id": "flight",
                    "title": "Flight AI-742",
                    "start": "2026-09-15T11:30:00+05:30",
                    "end": "2026-09-15T14:15:00+05:30",
                },
            ],
        },
        {"application": "gmail", "records": [{"id": "thread", "recipient": "client@example.com"}]},
        {"application": "discord", "records": [{"id": "channel", "channel_id": "channel"}]},
        {"application": "whatsapp", "records": [{"id": "pickup", "contact": "Pickup"}]},
    ]
    text = "Flight AI-742 on 2026-09-15 moved to 6:40 AM"
    result = make_plan(text, "text", False, extract(text, "Asia/Kolkata"), context, "Asia/Kolkata", "live")
    assert result["status"] == "awaiting_approval"
    assert {a["application"] for a in result["actions"]} == {"calendar", "gmail", "discord"}
    assert result["entities"]["departure_time"] is None
    assert result["limitations"]
    assert "pickup" in result["summary"].lower()
    assert all(a["requires_approval"] for a in result["actions"])
