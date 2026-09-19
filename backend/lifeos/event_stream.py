from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class EventNotice:
    owner: str
    event_id: str
    version: int
    updated_at: str


class EventStream:
    """In-process change notices. Durable event bodies stay in the database."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[EventNotice]]] = {}

    def _key(self, owner: str, event_id: str) -> str:
        return f"{owner}:{event_id}"

    def subscribe(self, owner: str, event_id: str) -> asyncio.Queue[EventNotice]:
        queue: asyncio.Queue[EventNotice] = asyncio.Queue(maxsize=16)
        self._subscribers.setdefault(self._key(owner, event_id), []).append(queue)
        return queue

    def unsubscribe(self, owner: str, event_id: str, queue: asyncio.Queue[EventNotice]) -> None:
        key = self._key(owner, event_id)
        listeners = self._subscribers.get(key, [])
        if queue in listeners:
            listeners.remove(queue)
        if not listeners:
            self._subscribers.pop(key, None)

    def publish(self, notice: EventNotice) -> None:
        for queue in list(self._subscribers.get(self._key(notice.owner, notice.event_id), [])):
            try:
                queue.put_nowait(notice)
            except asyncio.QueueFull:
                continue
