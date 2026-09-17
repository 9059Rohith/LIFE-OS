"""Bounded real provider adapters; no automatic retry of uncertain mutations."""

import asyncio
import base64
import copy
import hashlib
import re
import time
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from .oauth import refresh_token
from .planning import extract, meeting_candidates

GOOGLE = "https://www.googleapis.com"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
DISCORD = "https://discord.com/api/v10"


class ProviderError(RuntimeError):
    def __init__(self, message: str, code: str = "TOOL_ERROR", uncertain: bool = False):
        super().__init__(message)
        self.code = code
        self.uncertain = uncertain


def segment(value) -> str:
    if not value or len(str(value)) > 512:
        raise ProviderError("Missing or invalid provider resource ID", "VALIDATION_ERROR")
    return quote(str(value), safe="")


def calendar_matches(current, expected):
    for field, value in expected.items():
        actual = current.get(field)
        if field in {"start", "end"} and isinstance(value, dict) and "dateTime" in value:
            try:
                if datetime.fromisoformat(actual["dateTime"]) != datetime.fromisoformat(value["dateTime"]):
                    return False
            except (KeyError, TypeError, ValueError):
                return False
        elif actual != value:
            return False
    return True


def message_parts(payload):
    yield payload
    for part in payload.get("parts", []):
        yield from message_parts(part)


def decode_body(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class LiveProviders:
    def __init__(self, settings, token_loader, token_saver, whatsapp_bridge=None):
        self.settings = settings
        self.token_loader = token_loader
        self.token_saver = token_saver
        self.http = httpx.AsyncClient(timeout=20, follow_redirects=False)
        self._google_lock = asyncio.Lock()
        self._limit = asyncio.Semaphore(4)
        self._whatsapp = None
        self.whatsapp_bridge = whatsapp_bridge

    async def close(self):
        await self.http.aclose()
        if self._whatsapp:
            await self._whatsapp.close()

    async def check_whatsapp(self):
        from .whatsapp import WhatsAppWorker

        if not (getattr(self.settings, "whatsapp_enabled", False) or self.whatsapp_bridge) or not getattr(
            self.settings, "whatsapp_contact", ""
        ):
            raise ProviderError("WhatsApp chat is not configured", "AUTHORIZATION_ERROR")
        if self.whatsapp_bridge:
            result = await self.whatsapp_bridge.request("check", {"contact": self.settings.whatsapp_contact}, 45)
            if result.get("verified") is not True:
                raise ProviderError("Desktop WhatsApp chat could not be verified", "AUTHORIZATION_ERROR")
            return True
        if not self._whatsapp:
            self._whatsapp = WhatsAppWorker(self.settings)
        return await self._whatsapp.check(self.settings.whatsapp_contact)

    async def read_whatsapp_messages(self):
        from .whatsapp import WhatsAppWorker

        if not (getattr(self.settings, "whatsapp_enabled", False) or self.whatsapp_bridge) or not getattr(
            self.settings, "whatsapp_contact", ""
        ):
            raise ProviderError("WhatsApp chat is not configured", "AUTHORIZATION_ERROR")
        if self.whatsapp_bridge:
            result = await self.whatsapp_bridge.request("read", {"contact": self.settings.whatsapp_contact}, 24)
            if result.get("application") != "whatsapp" or result.get("title") != self.settings.whatsapp_contact or not isinstance(result.get("items"), list):
                raise ProviderError("Desktop WhatsApp read-back was invalid", "VERIFICATION_ERROR")
            return result
        if not self._whatsapp:
            self._whatsapp = WhatsAppWorker(self.settings)
        return await self._whatsapp.read_recent(self.settings.whatsapp_contact)

    async def _google_headers(self, user_id):
        async with self._google_lock:
            token = await self.token_loader(user_id, "google")
            if not token or not token.get("access_token"):
                raise ProviderError("Connect Google before using this integration", "AUTHENTICATION_ERROR")
            if token.get("expires_at", time.time() + 3600) < time.time() + 60:
                try:
                    token = await refresh_token(self.settings, token)
                except ValueError as exc:
                    raise ProviderError(str(exc), "AUTHENTICATION_ERROR") from exc
                await self.token_saver(user_id, "google", token)
            return {"Authorization": "Bearer " + token["access_token"]}

    def _discord_headers(self):
        if not getattr(self.settings, "discord_bot_token", ""):
            raise ProviderError("Configure a Discord bot token", "AUTHENTICATION_ERROR")
        return {"Authorization": "Bot " + self.settings.discord_bot_token}

    async def _request(self, method, url, **kwargs):
        mutation = method not in {"GET", "HEAD"}
        async with self._limit:
            for attempt in range(3 if not mutation else 1):
                try:
                    response = await self.http.request(method, url, **kwargs)
                except httpx.RequestError as exc:
                    if mutation:
                        raise ProviderError(
                            "UNCERTAIN: provider may have accepted the action; verify before retry",
                            "NETWORK_ERROR",
                            True,
                        ) from exc
                    if attempt == 2:
                        raise ProviderError(
                            "Provider connection failed after bounded retries", "NETWORK_ERROR"
                        ) from exc
                    await asyncio.sleep(0.2 * (2**attempt))
                    continue
                if response.status_code in {429, 500, 502, 503, 504} and not mutation and attempt < 2:
                    await asyncio.sleep(
                        min(
                            float(response.headers.get("Retry-After", "1"))
                            if response.headers.get("Retry-After", "1").isdigit()
                            else 1,
                            2,
                        )
                    )
                    continue
                if response.status_code == 412:
                    raise ProviderError(
                        "STALE_APPROVAL: provider resource changed; re-plan and approve",
                        "STALE_APPROVAL_ERROR",
                    )
                if response.status_code >= 400:
                    code = (
                        "AUTHENTICATION_ERROR"
                        if response.status_code == 401
                        else "AUTHORIZATION_ERROR"
                        if response.status_code == 403
                        else "RATE_LIMIT_ERROR"
                        if response.status_code == 429
                        else "TOOL_ERROR"
                    )
                    uncertain = mutation and response.status_code >= 500
                    raise ProviderError(
                        ("UNCERTAIN: " if uncertain else "")
                        + f"Provider rejected request (HTTP {response.status_code})",
                        code,
                        uncertain,
                    )
                if not response.content:
                    return {}
                if "json" in response.headers.get("content-type", ""):
                    try:
                        data = response.json()
                    except ValueError as exc:
                        raise ProviderError(
                            ("UNCERTAIN: " if mutation else "") + "Provider returned malformed data",
                            "TOOL_ERROR",
                            mutation,
                        ) from exc
                    if (
                        mutation
                        and method in {"POST", "PATCH"}
                        and (not isinstance(data, dict) or not data.get("id"))
                    ):
                        raise ProviderError(
                            "UNCERTAIN: provider response did not include a resource identity",
                            "TOOL_ERROR",
                            True,
                        )
                    return data
                if mutation and method in {"POST", "PATCH"}:
                    raise ProviderError(
                        "UNCERTAIN: provider returned an unexpected response format", "TOOL_ERROR", True
                    )
                if len(response.content) > 50000:
                    raise ProviderError("Provider text exceeds the 50 KB document limit", "VALIDATION_ERROR")
                return {"text": response.text}
        raise ProviderError("Provider retry budget exhausted")

    async def _google(self, user_id, method, url, **kwargs):
        headers = {**await self._google_headers(user_id), **kwargs.pop("headers", {})}
        return await self._request(method, url, headers=headers, **kwargs)

    async def gmail_search(self, user_id, query):
        result = await self._google(
            user_id, "GET", GMAIL + "/messages", params={"q": query[:500], "maxResults": 5}
        )
        return await asyncio.gather(
            *(
                self._google(
                    user_id, "GET", GMAIL + "/messages/" + segment(item["id"]), params={"format": "full"}
                )
                for item in result.get("messages", [])
            )
        )

    async def calendar_list(self, user_id, entities=None, timezone="UTC"):
        now = datetime.now(UTC)
        start = (
            datetime.fromisoformat(entities["date"]).replace(tzinfo=ZoneInfo(timezone))
            if entities and entities.get("date")
            else now
        )
        end = start + timedelta(days=1 if entities and entities.get("date") else 30)
        result = await self._google(
            user_id,
            "GET",
            GOOGLE + "/calendar/v3/calendars/primary/events",
            params={
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 2500,
            },
        )
        if result.get("nextPageToken"):
            raise ProviderError(
                "Calendar context exceeds the safe retrieval limit; narrow the date.",
                "CLARIFICATION_REQUIRED",
            )
        return result.get("items", [])

    async def drive_search(self, user_id, query):
        escaped = query[:100].replace("\\", "\\\\").replace("'", "\\'")
        result = await self._google(
            user_id,
            "GET",
            GOOGLE + "/drive/v3/files",
            params={
                "q": f"trashed = false and fullText contains '{escaped}'",
                "pageSize": 5,
                "fields": "files(id,name,mimeType,modifiedTime,description,webViewLink,capabilities/canDownload)",
            },
        )
        return result.get("files", [])

    async def drive_read(self, user_id, file_id):
        url = GOOGLE + "/drive/v3/files/" + segment(file_id)
        metadata = await self._google(
            user_id, "GET", url, params={"fields": "id,name,mimeType,size,capabilities/canDownload"}
        )
        if int(metadata.get("size", 0)) > 50000:
            raise ProviderError("Drive text exceeds the 50 KB document limit", "VALIDATION_ERROR")
        if not metadata.get("capabilities", {}).get("canDownload", False):
            raise ProviderError("Drive file does not permit content download", "AUTHORIZATION_ERROR")
        mime = metadata.get("mimeType", "")
        if mime == "application/vnd.google-apps.document":
            content = await self._google(user_id, "GET", url + "/export", params={"mimeType": "text/plain"})
        elif mime.startswith("text/"):
            content = await self._google(user_id, "GET", url, params={"alt": "media"})
        else:
            raise ProviderError(
                "Only text files and Google Docs can be read by this adapter", "VALIDATION_ERROR"
            )
        return {
            **metadata,
            **content,
            "content_sha256": hashlib.sha256(content.get("text", "").encode()).hexdigest(),
        }

    async def _drive_context(self, user_id):
        file_id = getattr(self.settings, "drive_proposal_file_id", "")
        if file_id:
            return [await self.drive_read(user_id, file_id)]
        candidates = await self.drive_search(user_id, "proposal")
        if len(candidates) == 1:
            return [await self.drive_read(user_id, candidates[0]["id"])]
        return candidates

    async def preflight(self, user_id, actions):
        """Read all preconditions before the engine starts its first mutation."""
        for action in actions:
            args = action.get("arguments", {})
            if action["application"] == "calendar" and action["type"] in {"update", "cancel"}:
                url = (
                    GOOGLE
                    + "/calendar/v3/calendars/"
                    + segment(args.get("calendar_id", "primary"))
                    + "/events/"
                    + segment(args.get("event_id"))
                )
                current = await self._google(user_id, "GET", url)
                if not args.get("etag") or current.get("etag") != args["etag"]:
                    raise ProviderError(
                        "STALE_APPROVAL: Calendar changed before execution", "STALE_APPROVAL_ERROR"
                    )
                if action["type"] == "update":
                    action["before"] = {
                        k: copy.deepcopy(current.get(k))
                        for k in ("summary", "start", "end", "description", "location")
                        if k in args
                    }
            if action["application"] == "gmail" and args.get("attachment_id"):
                attachment = await self.drive_read(user_id, args["attachment_id"])
                if (
                    not args.get("attachment_sha256")
                    or attachment["content_sha256"] != args["attachment_sha256"]
                ):
                    raise ProviderError(
                        "STALE_APPROVAL: proposal changed before execution", "STALE_APPROVAL_ERROR"
                    )
            if action["application"] == "whatsapp" and action["type"] == "send":
                if args.get("contact") != getattr(self.settings, "whatsapp_contact", ""):
                    raise ProviderError("WhatsApp contact is not allowlisted", "AUTHORIZATION_ERROR")
                await self.check_whatsapp()

    async def context(self, user_id, text, entities=None, timezone="UTC"):
        tasks = []
        names = []
        entities = entities or extract(text, timezone)
        if await self.token_loader(user_id, "google"):

            async def relevant_google():
                calendar = await self.calendar_list(user_id, entities, timezone)
                candidates = meeting_candidates(
                    [dict(r, title=r.get("summary", "")) for r in calendar],
                    entities,
                    timezone,
                    filter_flight_overlap=False,
                )
                # Read known attendees only; the planner retains all ambiguous candidates.
                addresses = sorted(
                    {
                        a["email"]
                        for r in candidates
                        for a in r.get("attendees", [])
                        if a.get("email") and not a.get("self") and not a.get("resource")
                    }
                )
                if len(addresses) > 10 or any(
                    not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+", a) for a in addresses
                ):
                    addresses = []
                mail = await asyncio.gather(
                    *(self.gmail_search(user_id, "from:" + address) for address in addresses)
                )
                return calendar, [r for group in mail for r in group]

            try:
                calendar_records, mail_records = await relevant_google()
            except Exception as exc:
                calendar_records, mail_records = exc, exc

            async def existing(value):
                if isinstance(value, Exception):
                    raise value
                return value

            tasks += [
                existing(mail_records),
                existing(calendar_records),
                self._drive_context(user_id),
            ]
            names += ["gmail", "calendar", "drive"]
        if getattr(self.settings, "discord_bot_token", "") and getattr(
            self.settings, "discord_channel_id", ""
        ):
            tasks.append(
                self._request(
                    "GET",
                    DISCORD + "/channels/" + segment(self.settings.discord_channel_id) + "/messages",
                    headers=self._discord_headers(),
                    params={"limit": 20},
                )
            )
            names.append("discord")
        if (getattr(self.settings, "whatsapp_enabled", False) or self.whatsapp_bridge) and getattr(
            self.settings, "whatsapp_contact", ""
        ):
            tasks.append(asyncio.wait_for(self.check_whatsapp(), 48))
            names.append("whatsapp")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        context = []
        for application, records in zip(names, results, strict=True):
            if isinstance(records, Exception):
                context.append(
                    {
                        "application": application,
                        "title": "Context unavailable",
                        "detail": str(records),
                        "error": True,
                    }
                )
                continue
            if application == "whatsapp":
                if records is True:
                    context.append(
                        {
                            "application": "whatsapp",
                            "id": self.settings.whatsapp_contact,
                            "title": "Verified WhatsApp conversation",
                            "detail": "The configured chat and composer were verified in a signed-in browser session.",
                            "contact": self.settings.whatsapp_contact,
                            "verified": True,
                        }
                    )
                continue
            for record in records:
                headers = {
                    h["name"].lower(): h["value"] for h in record.get("payload", {}).get("headers", [])
                }
                normalized = {
                    "application": application,
                    "id": record.get("id"),
                    "title": record.get("summary")
                    or record.get("name")
                    or headers.get("subject")
                    or "Recent message",
                    "detail": record.get("snippet")
                    or record.get("description")
                    or record.get("content")
                    or "",
                    "record": record,
                }
                if application == "calendar":
                    normalized.update(
                        {
                            "calendar_id": "primary",
                            "event_id": record["id"],
                            "etag": record.get("etag"),
                            "start": record.get("start"),
                            "end": record.get("end"),
                            "participants": [
                                a["email"] for a in record.get("attendees", []) if a.get("email")
                            ],
                        }
                    )
                if application == "gmail":
                    normalized["recipient"] = parseaddr(headers.get("from", ""))[1]
                    normalized["thread_id"] = record.get("threadId")
                if application == "discord":
                    normalized["channel_id"] = self.settings.discord_channel_id
                if application == "drive":
                    normalized.update(
                        {
                            "name": record.get("name"),
                            "content_sha256": record.get("content_sha256"),
                            "configured": record.get("id")
                            == getattr(self.settings, "drive_proposal_file_id", ""),
                        }
                    )
                context.append(normalized)
        grouped = []
        for application in dict.fromkeys(row["application"] for row in context):
            rows = [r for r in context if r["application"] == application]
            grouped.append(
                {
                    "application": application,
                    "title": application.title() + " context",
                    "detail": f"Retrieved {sum(not r.get('error') for r in rows)} records",
                    "records": [r for r in rows if not r.get("error")],
                    "errors": [r["detail"] for r in rows if r.get("error")],
                }
            )
        return grouped

    async def execute(self, user_id, action: dict, idempotency_key: str):
        if getattr(self.settings, "mode", "demo") != "live":
            raise ProviderError("Live adapters cannot execute in demo mode", "AUTHORIZATION_ERROR")
        application, kind, args = action["application"].lower(), action["type"], action.get("arguments", {})
        if action.get("_authorized") is not True:
            raise ProviderError("Engine approval authorization is required", "AUTHORIZATION_ERROR")
        if application == "calendar":
            return await self._calendar_execute(user_id, kind, args, idempotency_key)
        if application == "gmail" and kind in {"send", "draft"}:
            recipient = args.get("recipient", "")
            allowed = action.get("_validated_recipients", [])
            if not re.fullmatch(
                r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+", recipient
            ) or recipient.lower() not in {r.lower() for r in allowed}:
                raise ProviderError(
                    "Email recipient must match server-validated context", "AUTHORIZATION_ERROR"
                )
            message = EmailMessage()
            message["To"] = recipient
            message["Subject"] = args.get("subject", "LIFEOS update")
            message_id = "<" + hashlib.sha256(idempotency_key.encode()).hexdigest() + "@lifeos.local>"
            message["Message-ID"] = message_id
            message.set_content(args.get("body", ""))
            if args.get("attachment_id"):
                attachment = await self.drive_read(user_id, args["attachment_id"])
                if (
                    not args.get("attachment_sha256")
                    or attachment["content_sha256"] != args["attachment_sha256"]
                ):
                    raise ProviderError(
                        "STALE_APPROVAL: proposal changed before send", "STALE_APPROVAL_ERROR"
                    )
                message.add_attachment(
                    attachment.get("text", "").encode(),
                    maintype="text",
                    subtype="plain",
                    filename=attachment.get("name", "proposal") + ".txt",
                )
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            body: dict = {"raw": raw} if kind == "send" else {"message": {"raw": raw}}
            url = GMAIL + ("/messages/send" if kind == "send" else "/drafts")
            result = await self._google(user_id, "POST", url, json=body)
            return {
                **result,
                "message_id": message_id,
                "kind": kind,
                "attachment_sha256": args.get("attachment_sha256"),
            }
        if application == "discord" and kind == "send":
            channel = str(args.get("channel_id", ""))
            if not channel or channel != str(getattr(self.settings, "discord_channel_id", "")):
                raise ProviderError("Discord channel is not allowlisted", "AUTHORIZATION_ERROR")
            body = args.get("body", "")
            if not body or len(body) > 2000:
                raise ProviderError("Discord message must contain 1–2000 characters", "VALIDATION_ERROR")
            result = await self._request(
                "POST",
                DISCORD + "/channels/" + segment(channel) + "/messages",
                headers=self._discord_headers(),
                json={
                    "content": body,
                    "allowed_mentions": {"parse": []},
                    "nonce": hashlib.sha256(idempotency_key.encode()).hexdigest()[:24],
                    "enforce_nonce": True,
                },
            )
            return {**result, "channel_id": channel}
        if application == "drive" and kind == "read":
            return await self.drive_read(user_id, args.get("file_id"))
        if application == "whatsapp" and kind == "send":
            if self.whatsapp_bridge:
                if args.get("contact") != self.settings.whatsapp_contact or not args.get("body") or len(args["body"]) > 4000:
                    raise ProviderError("WhatsApp target or message is invalid", "AUTHORIZATION_ERROR")
                result = await self.whatsapp_bridge.request("send", {
                    "contact": self.settings.whatsapp_contact,
                    "body": args["body"], "idempotency_key": idempotency_key,
                }, 27)
                if (not result.get("id") or result.get("contact") != self.settings.whatsapp_contact
                        or result.get("body") != args["body"] or result.get("idempotency_key") != idempotency_key):
                    raise ProviderError("Desktop WhatsApp send result was invalid", "VERIFICATION_ERROR", True)
                return result
            from .whatsapp import WhatsAppWorker

            if not self._whatsapp:
                self._whatsapp = WhatsAppWorker(self.settings)
            return await self._whatsapp.send(args.get("contact", ""), args.get("body", ""), idempotency_key)
        raise ProviderError("Unsupported provider action", "VALIDATION_ERROR")

    async def _calendar_execute(self, user_id, kind, args, key):
        args = dict(args)
        for field in ("start", "end"):
            if isinstance(args.get(field), str):
                args[field] = {"dateTime": args[field]}
        base = GOOGLE + "/calendar/v3/calendars/" + segment(args.get("calendar_id", "primary")) + "/events"
        if kind == "create":
            event_id = hashlib.sha256(key.encode()).hexdigest()
            body = {k: args[k] for k in ("summary", "start", "end", "description", "location") if k in args}
            if not all(k in body for k in ("summary", "start", "end")):
                raise ProviderError("Calendar creation requires title, start and end", "VALIDATION_ERROR")
            result = await self._google(user_id, "POST", base, json={**body, "id": event_id})
            return {**result, "calendar_id": args.get("calendar_id", "primary"), "expected": body}
        if kind not in {"update", "cancel"} or not args.get("etag"):
            raise ProviderError("Calendar mutation requires an approved etag", "VALIDATION_ERROR")
        url = base + "/" + segment(args.get("event_id"))
        original = await self._google(user_id, "GET", url)
        if original.get("etag") != args["etag"]:
            raise ProviderError("STALE_APPROVAL: Calendar changed after planning", "STALE_APPROVAL_ERROR")
        if kind == "cancel":
            await self._google(
                user_id, "DELETE", url, headers={"If-Match": args["etag"]}, params={"sendUpdates": "all"}
            )
            return {
                "id": args["event_id"],
                "calendar_id": args.get("calendar_id", "primary"),
                "cancelled": True,
            }
        patch = {k: args[k] for k in ("summary", "start", "end", "description", "location") if k in args}
        if not patch:
            raise ProviderError("No permitted Calendar changes supplied", "VALIDATION_ERROR")
        result = await self._google(
            user_id,
            "PATCH",
            url,
            headers={"If-Match": args["etag"]},
            params={"conferenceDataVersion": 1, "sendUpdates": "all"},
            json=patch,
        )
        return {
            **result,
            "calendar_id": args.get("calendar_id", "primary"),
            "expected": patch,
            "compensation_journal": {
                "id": args["event_id"],
                "calendar_id": args.get("calendar_id", "primary"),
                "etag": result.get("etag"),
                "before": {k: copy.deepcopy(original.get(k)) for k in patch},
                "after": {k: copy.deepcopy(result.get(k)) for k in patch},
            },
            "preserved": {
                k: original[k]
                for k in ("id", "iCalUID", "recurrence", "recurringEventId", "conferenceData")
                if k in original
            },
        }

    async def compensate_calendar(self, user_id, action):
        """Restore only recorded update fields, using an exact conditional write."""
        journal = action.get("compensation_journal", {})
        args = action.get("arguments", {})
        fields = set(journal.get("before", {}))
        if (
            self.settings.mode != "live"
            or action.get("_authorized") is not True
            or action.get("status") != "verified"
            or not action.get("reversible")
            or action.get("application") != "calendar"
            or action.get("type") != "update"
            or not action.get("evidence", {}).get("verified")
            or not journal.get("etag")
            or journal.get("id") != args.get("event_id")
            or journal.get("calendar_id") != args.get("calendar_id", "primary")
            or not fields
            or not fields <= {"summary", "start", "end", "description", "location"}
            or fields != set(journal.get("after", {}))
            or fields != {k for k in ("summary", "start", "end", "description", "location") if k in args}
            or journal["before"] != action.get("before")
        ):
            raise ProviderError("A verified Calendar update journal is required", "AUTHORIZATION_ERROR")
        url = (
            GOOGLE
            + "/calendar/v3/calendars/"
            + segment(journal["calendar_id"])
            + "/events/"
            + segment(journal["id"])
        )
        current = await self._google(user_id, "GET", url)
        if current.get("etag") != journal["etag"] or any(
            current.get(k) != journal["after"][k] for k in fields
        ):
            raise ProviderError("Calendar changed since execution", "STALE_APPROVAL_ERROR")
        await self._google(
            user_id,
            "PATCH",
            url,
            headers={"If-Match": journal["etag"]},
            params={"conferenceDataVersion": 1, "sendUpdates": "all"},
            json=journal["before"],
        )
        try:
            restored = await self._google(user_id, "GET", url)
        except Exception as exc:
            raise ProviderError("Restoration requires manual read-back", "VERIFICATION_ERROR", True) from exc
        verified = restored.get("id") == journal["id"] and calendar_matches(restored, journal["before"])
        return {
            "verified": verified,
            "provider_id": journal["id"],
            "etag": restored.get("etag"),
            "observed": {k: restored.get(k) for k in fields},
            "detail": "Calendar prior fields restored and read-back verified"
            if verified
            else "Restoration read-back differs; manual review required",
        }

    async def verify(self, user_id, action, result):
        application, args = action["application"].lower(), action.get("arguments", {})
        if application == "calendar":
            url = (
                GOOGLE
                + "/calendar/v3/calendars/"
                + segment(result.get("calendar_id", "primary"))
                + "/events/"
                + segment(result.get("id"))
            )
            try:
                current = await self._google(user_id, "GET", url)
            except ProviderError as exc:
                if result.get("cancelled") and ("HTTP 404" in str(exc) or "HTTP 410" in str(exc)):
                    return {
                        "verified": True,
                        "detail": "Calendar event deletion confirmed by read-back",
                        "provider_id": result["id"],
                    }
                raise
            expected = result.get("expected", {})
            matches = (
                current.get("status") == "cancelled"
                if result.get("cancelled")
                else calendar_matches(current, {**expected, **result.get("preserved", {})})
            )
        elif application == "gmail":
            draft = result.get("kind") == "draft"
            current = await self._google(
                user_id,
                "GET",
                GMAIL + ("/drafts/" if draft else "/messages/") + segment(result.get("id")),
                params={"format": "full"},
            )
            msg = current.get("message", current)
            headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            parts = list(message_parts(msg.get("payload", {})))
            content = "\n".join(
                decode_body(p.get("body", {}).get("data", "")).decode("utf-8", errors="replace")
                for p in parts
                if p.get("mimeType") == "text/plain" and not p.get("filename")
            )
            matches = (
                headers.get("message-id") == result.get("message_id")
                and parseaddr(headers.get("to", ""))[1].lower() == args.get("recipient", "").lower()
                and headers.get("subject") == args.get("subject", "LIFEOS update")
                and content.strip() == args.get("body", "").strip()
                and (draft or "SENT" in msg.get("labelIds", []))
            )
            if args.get("attachment_id"):
                attachments = [p for p in parts if p.get("filename")]
                attachment_matches = False
                if len(attachments) == 1 and result.get("attachment_sha256"):
                    body = attachments[0].get("body", {})
                    if body.get("attachmentId"):
                        body = await self._google(
                            user_id,
                            "GET",
                            GMAIL
                            + "/messages/"
                            + segment(msg.get("id"))
                            + "/attachments/"
                            + segment(body["attachmentId"]),
                        )
                    attachment_matches = (
                        hashlib.sha256(decode_body(body.get("data", ""))).hexdigest()
                        == result["attachment_sha256"]
                    )
                matches = matches and attachment_matches
        elif application == "discord":
            current = await self._request(
                "GET",
                DISCORD
                + "/channels/"
                + segment(result.get("channel_id"))
                + "/messages/"
                + segment(result.get("id")),
                headers=self._discord_headers(),
            )
            matches = current.get("content") == args.get("body") and str(current.get("channel_id")) == str(
                args.get("channel_id")
            )
        elif application == "whatsapp":
            if self.whatsapp_bridge:
                answer = await self.whatsapp_bridge.request("verify", {
                    "contact": self.settings.whatsapp_contact,
                    "id": result["id"], "body": result["body"],
                }, 12)
                return {
                    "verified": answer.get("verified") is True and answer.get("provider_id") == result["id"],
                    "detail": "WhatsApp outgoing message and sent indicator read from the conversation"
                    if answer.get("verified") is True else "WhatsApp send not confirmed; manual review required",
                    "provider_id": result["id"],
                }
            return await self._whatsapp.verify(result)
        elif application == "drive":
            current = await self.drive_read(user_id, args.get("file_id"))
            matches = current.get("id") == result.get("id") and current.get("text") == result.get("text")
        else:
            matches = False
        return {
            "verified": matches,
            "detail": f"{application.title()} {'read-back matched expected state' if matches else 'verification did not match; manual review required'}",
            "provider_id": result.get("id"),
        }
