"""Opt-in, bounded source polling. External records can create plans, never authority."""

import asyncio
import contextlib
import json
import re
import time
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from .planning import extract
from .providers import DISCORD, decode_body, message_parts, segment
from .store import Document, digest


class IngestionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = False
    sources: list[Literal["gmail", "discord"]] = Field(
        default=["gmail"], min_length=1, max_length=2
    )
    interval_seconds: int = Field(default=300, ge=60, le=86400)


class Ingestion:
    def __init__(self, db, settings, engine, providers):
        self.db, self.settings, self.engine, self.providers = db, settings, engine, providers
        self.task = None
        self.owners = set()
        self.locks = {}
        self.active = {}
        self.closed = False

    def status(self, owner):
        state = self.db.get(owner, "ingestion", owner + ":ingestion") or {
            **IngestionSettings().model_dump(),
            "last_checked": None,
            "results": [],
            "error": None,
        }
        return {**state, "running": bool(self.task and not self.task.done() and state["enabled"])}

    def configure(self, owner, body):
        if self.settings.mode == "live" and owner != "owner":
            raise HTTPException(403, "Source polling is restricted to the installation owner")
        state = {**self.status(owner), **body.model_dump()}
        state.pop("running", None)
        self.db.put(owner, "ingestion", owner + ":ingestion", state)
        self.owners.add(owner)
        return self.status(owner)

    async def records(self, owner, source):
        if self.settings.mode == "demo":
            app = self.db.get(owner, "app", owner + ":app:" + source) or {}
            return [
                (str(row["id"]), (row.get("subject", "") + "\n" + row.get("body", ""))[:10000])
                for row in app.get("records", [])[:20]
                if row.get("id")
            ]
        if not self.providers:
            raise RuntimeError("Providers unavailable")
        if source == "gmail":
            rows = await self.providers.gmail_search(
                owner, "newer_than:2d {rescheduled delayed moved changed} {flight meeting}"
            )
            result = []
            for row in rows[:5]:
                payload = row.get("payload", {})
                subject = next(
                    (
                        h.get("value", "")
                        for h in payload.get("headers", [])
                        if h.get("name", "").lower() == "subject"
                    ),
                    "",
                )
                bodies = []
                for part in message_parts(payload):
                    data = part.get("body", {}).get("data", "")
                    if part.get("mimeType") == "text/plain" and data:
                        bodies.append(decode_body(data[:20000]).decode("utf-8", errors="replace"))
                content = subject + "\n" + ("\n".join(bodies) or row.get("snippet", ""))
                if row.get("id"):
                    result.append((str(row["id"]), content[:10000]))
            return result
        rows = await self.providers._request(
            "GET",
            DISCORD + "/channels/" + segment(self.settings.discord_channel_id) + "/messages",
            headers=self.providers._discord_headers(),
            params={"limit": 20},
        )
        return [
            (str(row["id"]), str(row.get("content", ""))[:10000])
            for row in rows[:20]
            if row.get("id") and not row.get("author", {}).get("bot")
        ]

    def reserve(self, owner, source, record_id):
        key = digest([owner, "ingestion", source, record_id])
        try:
            with self.db.sessions.begin() as session:
                session.add(
                    Document(
                        id=key,
                        owner=owner,
                        kind="ingestion_record",
                        data=json.dumps(
                            {
                                "source": source,
                                "record_id": record_id,
                                "status": "reserved",
                                "checked_at": time.time(),
                            }
                        ),
                    )
                )
        except IntegrityError:
            return None
        return key

    async def scan(self, owner):
        task = asyncio.current_task()
        self.active.setdefault(owner, set()).add(task)
        try:
            return await self._scan(owner)
        finally:
            self.active[owner].discard(task)

    async def _scan(self, owner):
        lock = self.locks.setdefault(owner, asyncio.Lock())
        if lock.locked():
            raise HTTPException(429, "A source scan is already running")
        async with lock:
            if self.closed or not self.status(owner)["enabled"]:
                raise HTTPException(409, "Enable source polling before scanning")
            if self.settings.mode == "live" and owner != "owner":
                raise HTTPException(403, "Owner required")
            state = self.status(owner)
            results, errors = [], []
            for source in dict.fromkeys(state["sources"]):
                try:
                    records = await asyncio.wait_for(self.records(owner, source), 45)
                except Exception:
                    errors.append(source + ": read failed; check the connection")
                    continue
                for record_id, content in records:
                    if len(results) >= 3 or not self.status(owner)["enabled"]:
                        break
                    key = self.reserve(owner, source, record_id)
                    if not key:
                        continue
                    outcome = {"source": source, "record_id": record_id, "status": "skipped"}
                    entities = extract(content, self.engine.settings_for(owner)["timezone"])
                    meaningful = (
                        entities.get("event_type") in {"flight_change", "meeting_change"}
                        and entities.get("date")
                        and entities.get("new_time")
                        and re.search(r"\b(rescheduled|delayed|moved|changed)\b", content, re.I)
                    )
                    # Relative dates in old account messages cannot safely mean the scan date.
                    if self.settings.mode == "live" and not re.search(r"\b20\d{2}-\d{2}-\d{2}\b", content):
                        meaningful = False
                    if meaningful:
                        try:
                            async with self.engine.lock(owner):
                                if not self.status(owner)["enabled"]:
                                    break
                                event = await self.engine.plan(
                                    owner, content, source, False, source_record_id=record_id
                                )
                            outcome.update(status="planned", event_id=event["id"])
                        except asyncio.CancelledError:
                            # Durable reservation deliberately survives cancellation: no uncertain retry.
                            raise
                        except Exception:
                            outcome["status"] = "manual_review_required"
                            errors.append(
                                source + ": planning interrupted; this record will not retry automatically"
                            )
                        results.append(outcome)
                    self.db.put(owner, "ingestion_record", key, {**outcome, "checked_at": time.time()})
            latest = self.status(owner)
            latest.pop("running", None)
            latest.update(last_checked=time.time(), results=results, error="; ".join(errors) or None)
            self.db.put(owner, "ingestion", owner + ":ingestion", latest)
            return self.status(owner)

    async def start(self):
        if self.task and not self.task.done():
            return
        self.closed = False
        if self.settings.mode == "live":
            self.owners.add("owner")
        self.task = asyncio.create_task(self._run())

    async def _run(self):
        while True:
            for owner in tuple(self.owners):
                state = self.status(owner)
                if (
                    state["enabled"]
                    and time.time() - (state["last_checked"] or 0) >= state["interval_seconds"]
                ):
                    pending = asyncio.create_task(self.scan(owner))
                    try:
                        await pending
                    except asyncio.CancelledError:
                        if self.closed:
                            raise
                    except Exception:
                        # A single failed scan must not terminate the background service.
                        pass
            await asyncio.sleep(5)

    async def pause(self, owner):
        state = self.status(owner)
        self.configure(
            owner,
            IngestionSettings(
                enabled=False, sources=state["sources"], interval_seconds=state["interval_seconds"]
            ),
        )
        pending = tuple(self.active.get(owner, ()))
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def close(self):
        self.closed = True
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        pending = [task for tasks in self.active.values() for task in tuple(tasks)]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def register(self, app, security):
        @app.get("/api/ingestion")
        async def status(request: Request):
            return self.status(security.require(request))

        @app.post("/api/ingestion")
        async def configure(body: IngestionSettings, request: Request):
            owner = security.require(request, True)
            if not body.enabled:
                await self.pause(owner)
            return self.configure(owner, body)

        @app.post("/api/ingestion/scan")
        async def scan(request: Request):
            owner = security.require(request, True)
            security.rate("ingestion-scan:" + owner, 1)
            return await self.scan(owner)
