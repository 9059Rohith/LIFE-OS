import pytest

from lifeos.event_stream import EventNotice, EventStream


@pytest.mark.asyncio
async def test_event_stream_delivers_owner_scoped_notice():
    stream = EventStream()
    queue = stream.subscribe("owner", "event-1")
    other_event = stream.subscribe("owner", "event-2")
    other_owner = stream.subscribe("user:team", "event-1")

    notice = EventNotice(
        owner="owner",
        event_id="event-1",
        version=3,
        updated_at="2026-09-19T10:00:00+05:30",
    )

    stream.publish(notice)

    assert await queue.get() == notice
    assert other_event.empty()
    assert other_owner.empty()

    stream.unsubscribe("owner", "event-1", queue)
    stream.publish(EventNotice("owner", "event-1", 4, "2026-09-19T10:01:00+05:30"))
    assert queue.empty()


def test_event_stream_tolerates_full_subscriber_queue():
    stream = EventStream()
    queue = stream.subscribe("owner", "event-1")

    for version in range(20):
        stream.publish(EventNotice("owner", "event-1", version, "2026-09-19T10:00:00+05:30"))

    assert queue.qsize() == 16
