import asyncio
import copy
import hashlib
import time
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from .store import uid, digest
from .planning import APPS, calendar_time, extract, make_plan, make_reschedule_plan, now_iso, seed
from .policy import approval_valid, classify


GOOGLE = "https://www.googleapis.com"


class Engine:
    def __init__(self, db, settings, providers=None):
        self.db, self.settings, self.providers = db, settings, providers
        self.locks = {}

    def lock(self, owner):
        return self.locks.setdefault(owner, asyncio.Lock())

    def event(self, owner, id):
        event = self.db.get(owner, "event", id)
        if not event:
            raise HTTPException(404, "Event not found")
        return event

    def save(self, owner, event):
        latest = self.db.get(owner, "event", event["id"])
        if latest and latest.get("cancel_requested"):
            event["cancel_requested"] = True
            event["status"] = "cancelled"
        self.db.put(owner, "event", event["id"], event)
        return event

    def log(self, owner, event, stage, message, application=None, latency_ms=None):
        event["timeline"].append(
            {
                "id": uid(),
                "timestamp": now_iso(),
                "stage": stage,
                "message": message,
                "application": application,
                "latency_ms": latency_ms,
            }
        )
        self.db.audit(
            owner,
            stage,
            message,
            event["id"],
            {
                "plan_version": event["version"],
                "actions": [
                    {
                        "id": a["id"],
                        "application": a["application"],
                        "type": a["type"],
                        "arguments_hash": a["arguments_hash"],
                        "risk": a["risk"],
                        "status": a["status"],
                        "approval": a.get("approval"),
                        "evidence_hash": digest(a["evidence"]) if a.get("evidence") else None,
                    }
                    for a in event["actions"]
                ],
            },
        )

    def settings_for(self, owner):
        return self.db.get(owner, "settings", owner + ":settings") or {
            "name": "Your workspace",
            "timezone": "Asia/Kolkata",
            "retention_days": 30,
        }

    async def plan(self, owner, text, source, simulation, source_record_id=None):
        started = time.perf_counter()
        preferences = self.settings_for(owner)
        self.db.prune_events(owner, preferences["retention_days"])
        entities = extract(text, preferences["timezone"])
        if self.settings.mode == "demo":
            if not self.db.list(owner, "app"):
                seed(self.db, owner)
            context = [
                dict(
                    a, title=APPS[a["application"]], detail=f"{len(a['records'])} owner-scoped local records"
                )
                for a in self.db.list(owner, "app") if a["application"] in APPS
            ]
        else:
            if (
                entities["event_type"] == "unknown"
                and not entities.get("date_required")
                and self.settings.openai_api_key
            ):
                from .ai import extract_event
                from .telemetry import scope

                try:
                    with scope(self.db, owner):
                        extracted = await extract_event(
                            text,
                            self.settings.openai_api_key,
                            self.settings.openai_model,
                            preferences["timezone"],
                        )
                    if (
                        extracted.get("event_type") in ["flight_change", "meeting_change"]
                        and extracted.get("new_time")
                        and extracted.get("date")
                    ):
                        entities = extract(
                            f"{extracted['event_type']} {extracted.get('flight') or ''} {extracted['date']} moved to {extracted['new_time']}",
                            preferences["timezone"],
                        )
                except Exception:
                    pass
            try:
                context = await asyncio.wait_for(
                    self.providers.context(owner, text, entities=entities, timezone=preferences["timezone"]),
                    55,
                )
            except Exception:
                raise HTTPException(
                    502, "TOOL_ERROR: context retrieval failed; check connected providers"
                ) from None
        event = make_plan(
            text, source, simulation, entities, context, preferences["timezone"], self.settings.mode
        )
        if source_record_id is not None:
            event["source_ref"] = {"application": source, "record_id": source_record_id}
        self.log(
            owner,
            event,
            "detected",
            "Event received from " + source
            + (" · source ID " + source_record_id if source_record_id is not None else ""),
        )
        for item in context:
            self.log(owner, event, "context", item.get("detail", "Context retrieved"), item["application"])
        self.log(
            owner,
            event,
            "planned",
            event["summary"],
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return self.save(owner, event)

    @staticmethod
    def _reschedule_time(value, timezone):
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("New Calendar times must be ISO-8601 values with a timezone offset")
        try:
            return value.astimezone(ZoneInfo(timezone))
        except Exception as exc:
            raise ValueError("Calendar timezone is invalid") from exc

    @staticmethod
    def _busy_overlap(record, start, end, timezone):
        if record.get("status") == "cancelled" or record.get("transparency") == "transparent":
            return False
        try:
            busy_start, busy_end = calendar_time(record, "start"), calendar_time(record, "end")
        except (KeyError, TypeError, ValueError):
            # All-day events reserve time as well. Incomplete events fail closed.
            try:
                zone = ZoneInfo(timezone)
                busy_start = datetime.fromisoformat(record["start"]["date"]).replace(tzinfo=zone)
                busy_end = datetime.fromisoformat(record["end"]["date"]).replace(tzinfo=zone)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Calendar availability cannot be verified from an incomplete event") from exc
        if busy_end <= busy_start:
            raise ValueError("Calendar availability cannot be verified from an invalid event")
        return start < busy_end and end > busy_start

    async def plan_reschedule(
        self,
        owner,
        event_id,
        new_start,
        new_end,
        timezone,
        notify_discord=False,
        notify_whatsapp=False,
        expected_etag=None,
    ):
        """Create an approval-only plan for one exact, owner-readable Calendar event.

        This method issues bounded GET requests only. Provider mutations remain in
        ``execute`` after the usual approval and Calendar preflight checks.
        """
        if self.settings.mode != "live" or self.providers is None:
            raise ValueError("Calendar reschedule planning requires a connected live provider")
        if not isinstance(owner, str) or not owner:
            raise ValueError("Authenticated owner is required")
        if not isinstance(event_id, str) or not event_id or len(event_id) > 512:
            raise ValueError("A valid Calendar event ID is required")
        if expected_etag is not None and (not isinstance(expected_etag, str) or not expected_etag):
            raise ValueError("Expected Calendar etag must be a non-empty string")
        start = self._reschedule_time(new_start, timezone)
        end = self._reschedule_time(new_end, timezone)
        if end <= start:
            raise ValueError("New Calendar end must be after start")
        encoded_id = quote(event_id, safe="")
        base = GOOGLE + "/calendar/v3/calendars/primary/events"
        current = await self.providers._google(owner, "GET", base + "/" + encoded_id)
        if current.get("id") != event_id:
            raise ValueError("Calendar returned an unexpected event")
        if expected_etag is not None and current.get("etag") != expected_etag:
            raise ValueError("Calendar event etag changed; fetch it again before planning")
        # Restrict the availability read to exactly the requested interval.
        busy = await self.providers._google(
            owner,
            "GET",
            base,
            params={
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 2500,
            },
        )
        if busy.get("nextPageToken"):
            raise ValueError("Calendar availability exceeds the safe retrieval limit")
        for record in busy.get("items", []):
            if record.get("id") != event_id and self._busy_overlap(record, start, end, timezone):
                raise ValueError("Requested Calendar time overlaps another busy event")
        event = make_reschedule_plan(
            current,
            start,
            end,
            timezone,
            self.settings,
            notify_discord=bool(notify_discord),
            notify_whatsapp=bool(notify_whatsapp),
        )
        self.log(owner, event, "detected", "Explicit Calendar reschedule request received", "calendar")
        self.log(owner, event, "context", "Exact owner Calendar event and requested availability were read", "calendar")
        self.log(owner, event, "planned", event["summary"], latency_ms=None)
        return self.save(owner, event)

    def approve(self, owner, event, ids, version):
        if (
            event["version"] != version
            or event["status"] in ["cancelled", "blocked", "clarification_required", "resolved"]
            or event["simulation"]
        ):
            raise HTTPException(409, "STALE_APPROVAL_ERROR: plan is not eligible for approval")
        if not set(ids).issubset({a["id"] for a in event["actions"]}):
            raise HTTPException(422, "Unknown action")
        for action in event["actions"]:
            if action["id"] in ids and action["status"] in ["awaiting_approval", "approved", "failed"]:
                action["approval"] = {
                    "hash": digest(action["arguments"]),
                    "version": version,
                    "expires": time.time() + self.settings.approval_seconds,
                }
                action["status"] = "approved"
        event["status"] = (
            "approved"
            if all(
                not a["requires_approval"] or a["status"] in ["approved", "verified", "rejected"]
                for a in event["actions"]
            )
            else "awaiting_approval"
        )
        self.log(owner, event, "approved", f"{len(ids)} actions approved for plan version {version}")
        return self.save(owner, event)

    def invalidate(self, event):
        event["version"] += 1
        event["status"] = "awaiting_approval"
        for a in event["actions"]:
            a.pop("approval", None)
            if a["status"] not in ["verified", "rejected", "compensated", "uncertain"]:
                a["status"] = "awaiting_approval" if a["requires_approval"] else "pending"

    def validate_approval(self, event, a):
        try:
            policy = classify(a["application"], a["type"])
        except ValueError:
            raise HTTPException(409, "This plan uses a removed integration. Create a new plan.") from None
        if policy.requires_approval != a["requires_approval"] or policy.risk != a["risk"]:
            raise HTTPException(403, "AUTHORIZATION_ERROR: action policy changed")
        if not a["requires_approval"]:
            return
        approval = a.get("approval", {})
        if (
            policy.requires_approval != a["requires_approval"]
            or policy.risk != a["risk"]
            or not approval_valid(approval, event["version"], digest(a["arguments"]), time.time())
        ):
            raise HTTPException(409, "STALE_APPROVAL_ERROR: review and approve the current plan")

    @staticmethod
    def provider_result(action, result):
        """Keep only the fields needed for a later read-only provider check."""
        fields = {
            "calendar": ("id", "calendar_id", "cancelled", "expected", "preserved"),
            "gmail": ("id", "kind", "message_id", "attachment_sha256"),
            "discord": ("id", "channel_id"),
            "whatsapp": ("id", "contact", "body", "idempotency_key"),
        }.get(action["application"], ())
        if not isinstance(result, dict) or not isinstance(result.get("id"), str):
            return None
        return {key: copy.deepcopy(result[key]) for key in fields if key in result}

    @staticmethod
    def summarize(event):
        if event["status"] != "cancelled":
            event["status"] = (
                "resolved"
                if all(a["status"] in ["verified", "rejected"] for a in event["actions"])
                else "partial_failure"
                if any(a["status"] in ["failed", "uncertain", "blocked_dependency"] for a in event["actions"])
                else "awaiting_approval"
            )
        verified = sum(a["status"] == "verified" for a in event["actions"])
        rejected = sum(a["status"] == "rejected" for a in event["actions"])
        failed = sum(a["status"] in ["failed", "blocked_dependency"] for a in event["actions"])
        uncertain = sum(a["status"] == "uncertain" for a in event["actions"])
        waiting = sum(a["status"] in ["pending", "awaiting_approval", "approved"] for a in event["actions"])
        event["summary"] = (
            f"{verified} actions verified, {rejected} rejected, {failed} failed or blocked, {uncertain} uncertain, {waiting} awaiting execution or approval."
        )
        if uncertain:
            event["summary"] += " Uncertain deliveries require manual provider review before any retry."
        if event["status"] == "cancelled":
            event["summary"] = (
                "Execution cancelled. " + event["summary"] + " Completed deliveries remain delivered."
            )

    async def reconcile(self, owner, event, action_id):
        """Read the provider again using a saved result; never repeat the write."""
        action = next((item for item in event["actions"] if item["id"] == action_id), None)
        if action is None:
            raise HTTPException(404, "Action not found")
        result = action.get("provider_result")
        if (
            self.settings.mode != "live"
            or event.get("simulation")
            or action["status"] != "uncertain"
            or not isinstance(result, dict)
            or not result.get("id")
        ):
            raise HTTPException(409, "No provider result is available for read-only reconciliation")
        try:
            evidence = await asyncio.wait_for(self.providers.verify(owner, action, copy.deepcopy(result)), 15)
        except Exception:
            self.log(owner, event, "verification_failed", "Provider read-back unavailable; manual review required", action["application"])
            return self.save(owner, event)
        action["evidence"] = evidence
        if evidence.get("verified") is True and evidence.get("provider_id") == result["id"]:
            action["status"] = "verified"
            action["error"] = None
            self.summarize(event)
            self.log(owner, event, "verified", "Previously uncertain action confirmed by provider read-back", action["application"])
        else:
            self.log(owner, event, "verification_failed", "Provider still does not confirm the action; manual review required", action["application"])
        return self.save(owner, event)

    async def execute(self, owner, event, retry=False):
        if event["simulation"] or event["status"] in [
            "blocked",
            "clarification_required",
            "cancelled",
            "compensated",
        ]:
            raise HTTPException(409, "This plan cannot execute")
        if any(a["status"] == "uncertain" for a in event["actions"]):
            raise HTTPException(
                409, "MANUAL_REVIEW_REQUIRED: an earlier delivery is uncertain; automatic retry is blocked"
            )
        pending = [a for a in event["actions"] if a["status"] not in ["verified", "rejected", "compensated"]]
        selected = [a for a in pending if not a["requires_approval"] or a.get("approval")]
        if any(a["requires_approval"] for a in pending) and not any(a["requires_approval"] for a in selected):
            raise HTTPException(409, "STALE_APPROVAL_ERROR: approve at least one action before execution")
        for a in selected:
            self.validate_approval(event, a)
        # Validate all local optimistic preconditions before any mutation.
        if self.settings.mode == "demo":
            for a in selected:
                if a["application"] == "calendar":
                    record = self.local_record(owner, "calendar", a["arguments"]["event_id"])
                    if not record or record.get("etag") != a["arguments"].get("etag"):
                        raise HTTPException(409, "CONFLICT_DETECTED: calendar changed; create a fresh plan")
                if a["arguments"].get("attachment_id"):
                    record = self.local_record(owner, "drive", a["arguments"]["attachment_id"])
                    if not record or hashlib.sha256(record.get("content", "").encode()).hexdigest() != a[
                        "arguments"
                    ].get("attachment_sha256"):
                        raise HTTPException(
                            409, "CONFLICT_DETECTED: proposal content changed; create a fresh plan"
                        )
        if not pending:
            return event
        if self.settings.mode == "live":
            try:
                await asyncio.wait_for(self.providers.preflight(owner, selected), 50)
            except Exception as exc:
                if getattr(exc, "code", "") == "STALE_APPROVAL_ERROR":
                    raise HTTPException(
                        409, "STALE_APPROVAL_ERROR: provider record changed; re-plan and approve"
                    ) from None
                raise HTTPException(
                    502, "TOOL_ERROR: execution preconditions could not be verified"
                ) from None
        event["status"] = "executing"
        self.log(owner, event, "executing", "Approved plan execution started")
        self.save(owner, event)
        deadline = time.monotonic() + 90
        for a in event["actions"]:
            # Cancel requests use the same process but deliberately do not acquire execution lock.
            if self.event(owner, event["id"]).get("cancel_requested"):
                event["status"] = "cancelled"
                break
            if a["status"] in ["verified", "rejected", "compensated"]:
                continue
            if a not in selected:
                continue
            statuses = {x["id"]: x["status"] for x in event["actions"]}
            if any(statuses.get(d) != "verified" for d in a["dependencies"]):
                if any(
                    statuses.get(d) in ["rejected", "failed", "uncertain", "blocked_dependency"]
                    for d in a["dependencies"]
                ):
                    a["status"] = "blocked_dependency"
                    a["error"] = "A prerequisite did not verify."
                continue
            if time.monotonic() > deadline:
                a["status"] = "failed"
                a["error"] = "TIMEOUT_ERROR: execution budget exhausted"
                break
            a["status"] = "executing"
            a["attempts"] = a.get("attempts", 0) + 1
            key = digest([owner, event["id"], a["id"], event["version"], a["arguments_hash"]])
            a["idempotency_key"] = key
            # Durable intent prevents sending again after process failure.
            self.save(owner, event)
            started = time.perf_counter()
            try:
                if a["attempts"] > 3:
                    raise HTTPException(409, "Maximum attempts reached")
                if self.settings.mode == "demo":
                    result = self.execute_local(owner, a, key)
                    evidence = self.verify_local(owner, a, result)
                else:
                    recipients = [
                        r["recipient"]
                        for c in event["context"]
                        if c["application"] == "gmail"
                        for r in c.get("records", [])
                        if r.get("recipient")
                    ]
                    result = await asyncio.wait_for(
                        self.providers.execute(
                            owner, dict(a, _authorized=True, _validated_recipients=recipients), key
                        ),
                        30,
                    )
                    if result.get("compensation_journal"):
                        a["compensation_journal"] = result["compensation_journal"]
                        self.save(owner, event)
                    receipt = self.provider_result(a, result)
                    if receipt:
                        a["provider_result"] = receipt
                        self.save(owner, event)
                    evidence = await asyncio.wait_for(self.providers.verify(owner, a, result), 15)
                a["evidence"] = evidence
                a["status"] = "verified" if evidence.get("verified") else "uncertain"
                a["error"] = (
                    None
                    if evidence.get("verified")
                    else "VERIFICATION_ERROR: manual read-back required before retry"
                )
                self.log(
                    owner,
                    event,
                    "verified" if evidence.get("verified") else "verification_failed",
                    evidence.get("detail", "Read-back completed"),
                    a["application"],
                    round((time.perf_counter() - started) * 1000, 2),
                )
            except Exception as exc:
                # No provider exception body is exposed: it may contain tokens or private payloads.
                uncertain = (
                    a["type"] == "send"
                    or bool(getattr(exc, "uncertain", False))
                    or (isinstance(exc, TimeoutError) and a["type"] not in ["read", "route"])
                )
                a["status"] = "uncertain" if uncertain else "failed"
                code = getattr(exc, "code", "TOOL_ERROR")
                a["error"] = f"{code}: " + (
                    "delivery is uncertain; review provider before retry"
                    if uncertain
                    else "action failed; check integration and retry"
                )
                self.log(
                    owner,
                    event,
                    "failed",
                    a["error"],
                    a["application"],
                    round((time.perf_counter() - started) * 1000, 2),
                )
            self.save(owner, event)
            await asyncio.sleep(0)
        self.summarize(event)
        self.log(
            owner,
            event,
            event["status"],
            "Every selected action has read-back evidence."
            if event["status"] == "resolved"
            else "Execution stopped with incomplete actions. Inspect individual results.",
        )
        return self.save(owner, event)

    def local_record(self, owner, app, id):
        data = self.db.get(owner, "app", owner + ":app:" + app)
        return next((r for r in data["records"] if r["id"] == id), None) if data else None

    def execute_local(self, owner, a, key):
        app = a["application"]
        args = a["arguments"]
        data = self.db.get(owner, "app", owner + ":app:" + app)
        existing = next((r for r in data["records"] if r.get("idempotency_key") == key), None)
        if existing:
            return {"id": existing["id"]}
        if a["type"] == "read":
            record = self.local_record(owner, app, args.get("file_id", ""))
            if not record:
                raise ValueError("Record missing")
            if (
                args.get("expected_sha256")
                and hashlib.sha256(record.get("content", "").encode()).hexdigest() != args["expected_sha256"]
            ):
                raise ValueError("Proposal content changed")
            return {"id": record["id"], "record": record}
        if app == "calendar":
            record = next(r for r in data["records"] if r["id"] == args["event_id"])
            a["before"] = copy.deepcopy(record)
            record.update(start=args["start"], end=args["end"], etag=uid(), idempotency_key=key)
        else:
            record = {"id": uid(), "idempotency_key": key, "created_at": now_iso(), "status": "sent", **args}
            if args.get("attachment_id"):
                attachment = self.local_record(owner, "drive", args["attachment_id"])
                record["attachment"] = {
                    "name": attachment["name"],
                    "content": attachment["content"],
                    "sha256": hashlib.sha256(attachment["content"].encode()).hexdigest(),
                }
            data["records"].append(record)
        self.db.put(owner, "app", owner + ":app:" + app, data)
        return {"id": record["id"]}

    def verify_local(self, owner, a, result):
        record = self.local_record(owner, a["application"], result["id"])
        args = a["arguments"]
        verified = bool(record)
        if a["type"] == "send":
            verified = (
                verified
                and record.get("body") == args["body"]
                and record.get("idempotency_key") == a["idempotency_key"]
            )
        elif a["type"] == "update":
            verified = verified and record["start"] == args["start"] and record["end"] == args["end"]
        return {
            "verified": bool(verified),
            "detail": "Read back from persistent local " + APPS[a["application"]] + " records.",
            "mode": "demo",
            "record_id": result["id"],
            "observed": record,
            "verified_at": now_iso(),
        }

    async def undo(self, owner, event):
        if self.settings.mode != "demo":
            return await self.undo_live(owner, event)
        count = 0
        for a in reversed(event["actions"]):
            if a["reversible"] and a["status"] == "verified" and a.get("before"):
                app = self.db.get(owner, "app", owner + ":app:" + a["application"])
                current = next(r for r in app["records"] if r["id"] == a["before"]["id"])
                if current.get("idempotency_key") != a.get("idempotency_key"):
                    raise HTTPException(409, "CONFLICT_DETECTED: record changed since execution")
                app["records"] = [a["before"] if r["id"] == a["before"]["id"] else r for r in app["records"]]
                self.db.put(owner, "app", owner + ":app:" + a["application"], app)
                a["status"] = "compensated"
                a["compensation_evidence"] = {
                    "verified": self.local_record(owner, a["application"], a["before"]["id"]) == a["before"]
                }
                count += 1
        event["status"] = "compensated"
        event["summary"] = (
            f"{count} reversible changes restored and verified. Sent messages remain delivered and cannot be recalled."
        )
        self.log(
            owner,
            event,
            "compensated",
            f"{count} reversible changes restored. Sent messages remain delivered.",
        )
        return self.save(owner, event)

    async def undo_live(self, owner, event):
        if any(a.get("compensation_status") in {"executing", "uncertain"} for a in event["actions"]):
            raise HTTPException(
                409, "Compensation is uncertain; manually review Calendar before further changes"
            )
        eligible = [
            a
            for a in reversed(event["actions"])
            if a["status"] == "verified"
            and a.get("reversible")
            and a["application"] == "calendar"
            and a["type"] == "update"
            and a.get("compensation_journal")
        ]
        if not eligible:
            raise HTTPException(
                409, "No verified Calendar updates are available to restore. Sent messages remain delivered."
            )
        for a in eligible:
            a["compensation_status"] = "executing"
            self.log(
                owner,
                event,
                "compensation_started",
                "User requested restoration of recorded Calendar fields",
                "calendar",
            )
            self.save(owner, event)
            try:
                evidence = await asyncio.wait_for(
                    self.providers.compensate_calendar(owner, dict(a, _authorized=True)), 45
                )
                a["compensation_evidence"] = dict(evidence, verified_at=now_iso())
                a["compensation_status"] = "verified" if evidence.get("verified") else "uncertain"
                if evidence.get("verified"):
                    a["status"] = "compensated"
            except Exception as exc:
                uncertain = isinstance(exc, TimeoutError) or bool(getattr(exc, "uncertain", False))
                a["compensation_status"] = "uncertain" if uncertain else "failed"
                a["compensation_error"] = (
                    getattr(exc, "code", "TOOL_ERROR")
                    + ": "
                    + (
                        "Restoration may have occurred; manually review Calendar"
                        if uncertain
                        else "Restoration blocked; verify Calendar state and integration"
                    )
                )
            self.log(
                owner,
                event,
                "compensation_" + a["compensation_status"],
                "Calendar restoration "
                + a["compensation_status"]
                + "; evidence "
                + digest(a.get("compensation_evidence", {})),
                "calendar",
            )
            self.save(owner, event)
            if a["compensation_status"] != "verified":
                break
        count = sum(a["status"] == "compensated" for a in event["actions"])
        incomplete = any(
            a.get("compensation_status") in {"failed", "uncertain", "executing"} for a in event["actions"]
        )
        event["status"] = "partial_failure" if incomplete else "compensated"
        event["summary"] = (
            f"{count} reversible Calendar changes restored and verified. Sent messages remain delivered and cannot be recalled."
        )
        if incomplete:
            event["summary"] += (
                " Restoration stopped; inspect compensation evidence and manually review Calendar."
            )
        return self.save(owner, event)
