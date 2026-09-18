from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
import hashlib
from .store import uid, digest
from .policy import classify

APPS = {
    "gmail": "Gmail",
    "calendar": "Google Calendar",
    "whatsapp": "WhatsApp",
    "discord": "Discord",
    "drive": "Google Drive",
}
SCENARIOS = {
    "flight": "Your flight AI-742 tomorrow has been rescheduled from 11:30 AM to 6:40 AM.",
    "meeting": "Client moved tomorrow's meeting to 2 PM. Please send the updated proposal.",
}


def now_iso():
    return datetime.now().astimezone().isoformat()


def seed(db, owner):
    date = (datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=1)).date().isoformat()
    records = {
        "gmail": [
            {
                "id": "flight-notice",
                "subject": "Schedule change · AI-742",
                "from": "updates@airline.example",
                "body": SCENARIOS["flight"],
            },
            {
                "id": "client-thread",
                "subject": "Acme proposal review",
                "recipient": "alex@acme.example",
                "body": "Looking forward to our 9 AM proposal review tomorrow.",
            },
        ],
        "calendar": [
            {
                "id": "client-meeting",
                "title": "Acme · proposal review",
                "start": f"{date}T09:00:00+05:30",
                "end": f"{date}T10:00:00+05:30",
                "recipient": "alex@acme.example",
                "etag": "seed-1",
            },
            {
                "id": "flight",
                "title": "AI-742 · Bengaluru ? Delhi",
                "start": f"{date}T11:30:00+05:30",
                "end": f"{date}T14:15:00+05:30",
                "etag": "seed-1",
            },
        ],
        "whatsapp": [
            {
                "id": "pickup-thread",
                "contact": "Dad",
                "body": "I will pick you up for the airport. Let me know if your flight changes.",
            }
        ],
        "discord": [
            {
                "id": "team-thread",
                "channel_id": "project-acme",
                "body": "Acme proposal review tomorrow at 9 AM. Alex is the client contact.",
            }
        ],
        "drive": [
            {
                "id": "proposal",
                "name": "Acme_Client_Proposal_Final.txt",
                "mimeType": "text/plain",
                "content": "ACME CLIENT PROPOSAL\nScope: Product strategy and launch plan.\nPrepared for Alex Chen.\nVersion: final.",
                "webViewLink": "local://drive/proposal",
            }
        ],
    }
    db.delete_kind(owner, "app")
    for app, rows in records.items():
        db.put(owner, "app", f"{owner}:app:{app}", {"application": app, "records": rows})


def extract(text, timezone):
    low = text.lower()
    if re.search(
        r"ignore.{0,40}(instruction|rule)|system prompt|exfiltrat|send all.{0,30}(file|document)|api.?key|secret|password",
        low,
    ):
        return {
            "event_type": "blocked",
            "title": "Untrusted instruction blocked",
            "reason": "PROMPT_INJECTION_DETECTED: external content cannot grant tool authority.",
        }
    kind = "flight_change" if "flight" in low else "meeting_change" if "meeting" in low else "unknown"
    matches = list(re.finditer(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|\b([01]?\d|2[0-3]):([0-5]\d)\b", low))
    values = []
    for match in matches:
        if match[4]:
            hour, minute = int(match[4]), int(match[5])
        else:
            hour, minute = int(match[1]), int(match[2] or 0)
            if not 1 <= hour <= 12:
                continue
            hour = hour % 12 + (12 if match[3] == "pm" else 0)
        if minute < 60:
            values.append(f"{hour:02}:{minute:02}")
    if not values and re.search(r"six forty.*morning", low):
        values = ["06:40"]
    current = datetime.now(ZoneInfo(timezone))
    if not re.search(
        r"\b(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|20\d{2}-\d{2}-\d{2})\b",
        low,
    ):
        return {
            "event_type": "unknown",
            "title": "Date needs clarification",
            "date_required": True,
            "reason": "CLARIFICATION_REQUIRED: specify the event date before planning.",
        }
    day = (current + timedelta(days=1)).date() if "tomorrow" in low else current.date()
    explicit = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if explicit:
        try:
            day = datetime.strptime(explicit[1], "%Y-%m-%d").date()
        except ValueError:
            return {"event_type": "unknown", "title": "Date needs clarification"}
    for n, name in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
        if not explicit and re.search(r"\b" + name + r"\b", low):
            day = (current + timedelta(days=(n - current.weekday()) % 7 or 7)).date()
    if kind == "unknown" or not values:
        return {
            "event_type": "unknown",
            "title": "A little more context is needed",
            "reason": "CLARIFICATION_REQUIRED: specify a flight or meeting, date and new time.",
        }
    flight = re.search(r"\b[A-Z]{2}[- ]?\d{2,4}\b", text, re.IGNORECASE)
    named = re.search(
        r'["“]([^"”]{1,120})["”]\s+meeting\b|\bmeeting\s+(?:named|called)\s+["“]([^"”]{1,120})["”]',
        text,
        re.IGNORECASE,
    )
    meeting_name = next((v for v in named.groups() if v), None) if named else None
    if not meeting_name:
        prefix = re.search(r"\b([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,2})\s+meeting\b", text)
        if prefix and prefix[1].lower() not in {"client", "the", "my", "our", "a", "your"}:
            meeting_name = prefix[1]
    return {
        "event_type": kind,
        "new_time": values[-1],
        "old_time": values[0] if len(values) > 1 else None,
        "date": day.isoformat(),
        "flight": flight[0] if flight else None,
        "meeting_name": meeting_name,
        "confidence": 0.93,
        "title": f"Flight {flight[0] + ' ' if flight else ''}moved to {values[-1]}"
        if kind == "flight_change"
        else f"Client meeting moved to {values[-1]}",
    }


def calendar_time(record, field):
    value = record[field]
    parsed = datetime.fromisoformat(value if isinstance(value, str) else value["dateTime"])
    if not parsed.tzinfo:
        raise ValueError("Calendar timezone missing")
    return parsed


def flight_matches(record, number, date, timezone):
    normalized = re.sub(r"[- ]", "", (number or "").upper())
    numbers = re.findall(r"(?<![A-Z0-9])[A-Z]{2}[- ]?\d{2,4}(?![A-Z0-9])", record.get("title", "").upper())
    try:
        return (
            bool(normalized)
            and normalized in {re.sub(r"[- ]", "", n) for n in numbers}
            and calendar_time(record, "start").astimezone(ZoneInfo(timezone)).date().isoformat() == date
        )
    except (KeyError, TypeError, ValueError):
        return False


def meeting_candidates(records, entities, timezone, travel_minutes=0, filter_flight_overlap=True):
    candidates = []
    name = entities.get("meeting_name")
    for record in records:
        title = record.get("title", "")
        if name:
            if not re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", title, re.IGNORECASE):
                continue
        elif not any(word in title.lower() for word in ("proposal", "client", "meeting")):
            continue
        try:
            if calendar_time(record, "start").astimezone(
                ZoneInfo(timezone)
            ).date().isoformat() != entities.get("date"):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        candidates.append(record)
    if entities.get("event_type") == "flight_change" and filter_flight_overlap:
        flights = [
            r for r in records if flight_matches(r, entities.get("flight"), entities.get("date"), timezone)
        ]
        if len(flights) != 1:
            return []
        try:
            duration = calendar_time(flights[0], "end") - calendar_time(flights[0], "start")
            changed = datetime.fromisoformat(entities["date"] + "T" + entities["new_time"]).replace(
                tzinfo=ZoneInfo(timezone)
            )
            if not timedelta(0) < duration <= timedelta(days=1):
                return []
            candidates = [
                r
                for r in candidates
                if calendar_time(r, "start") < changed + duration + timedelta(hours=1)
                and calendar_time(r, "end") > changed - timedelta(minutes=120 + travel_minutes)
            ]
        except (KeyError, TypeError, ValueError):
            return []
    return candidates


def make_plan(text, source, simulation, entities, context, timezone, mode):
    event = {
        "id": uid(),
        "title": entities.get("title", "Schedule changed"),
        "event_type": entities["event_type"],
        "source": source,
        "status": "awaiting_approval",
        "created_at": now_iso(),
        "version": 1,
        "summary": "",
        "simulation": simulation or text.lower().startswith("what if"),
        "entities": entities,
        "actions": [],
        "context": context,
        "timeline": [],
        "input": text,
    }
    if entities["event_type"] in ["unknown", "blocked"]:
        event["status"] = "blocked" if entities["event_type"] == "blocked" else "clarification_required"
        event["summary"] = entities.get("reason", "Clarify the new date and time before planning.")
        return event
    flat = [dict(r, application=c["application"]) for c in context for r in c.get("records", [])]

    def find(app, predicate=lambda r: True):
        return next((r for r in flat if r["application"] == app and predicate(r)), None)

    meeting = find("calendar", lambda r: "proposal" in str(r).lower() or "client" in str(r).lower())
    thread = find("gmail", lambda r: bool(r.get("recipient")))
    proposal = find("drive")
    if mode == "live":
        candidates = meeting_candidates(
            [r for r in flat if r["application"] == "calendar"],
            entities,
            timezone,
            0,
        )
        if len(candidates) != 1:
            event["status"] = "clarification_required"
            event["summary"] = (
                "The calendar target is missing or ambiguous. Identify exactly one client meeting before planning."
            )
            return event
        meeting = candidates[0]
        participants = meeting.get("participants", [])
        matches = [r for r in flat if r["application"] == "gmail" and r.get("recipient") in participants]
        recipients = set(r["recipient"] for r in matches)
        thread = matches[0] if len(recipients) == 1 else None
        proposals = [
            r
            for r in flat
            if r["application"] == "drive"
            and (r.get("configured") or "proposal" in r.get("title", "").lower())
        ]
        proposal = proposals[0] if len(proposals) == 1 else None
    if not meeting or not thread:
        event["status"] = "clarification_required"
        event["summary"] = (
            "Connect calendar and a known client email thread so targets can be validated. No recipient is inferred from incoming instructions."
        )
        return event
    try:
        for key in ["start", "end"]:
            value = meeting[key]
            parsed = datetime.fromisoformat(value if isinstance(value, str) else value["dateTime"])
            if not parsed.tzinfo:
                raise ValueError("Timezone missing")
    except (KeyError, TypeError, ValueError):
        event["status"] = "clarification_required"
        event["summary"] = (
            "The selected meeting needs an exact start, end and timezone. All-day or incomplete calendar records cannot be moved automatically."
        )
        return event
    zone = ZoneInfo(timezone)
    changed = datetime.fromisoformat(entities["date"] + "T" + entities["new_time"]).replace(tzinfo=zone)
    flight = entities["event_type"] == "flight_change"
    flight_duration = timedelta(hours=2, minutes=45)
    flight_record = None
    if flight and mode == "live":
        matching_flights = [
            r
            for r in flat
            if r["application"] == "calendar"
            and flight_matches(r, entities.get("flight"), entities.get("date"), timezone)
        ]
        if len(matching_flights) == 1:
            flight_record = matching_flights[0]
            try:
                fs = flight_record["start"]
                fe = flight_record["end"]
                flight_start = datetime.fromisoformat(fs if isinstance(fs, str) else fs["dateTime"])
                flight_end = datetime.fromisoformat(fe if isinstance(fe, str) else fe["dateTime"])
                flight_duration = flight_end - flight_start
                if (
                    not flight_start.tzinfo
                    or not flight_end.tzinfo
                    or not timedelta(0) < flight_duration <= timedelta(days=1)
                ):
                    flight_record = None
            except (KeyError, TypeError, ValueError):
                flight_record = None
    if flight and mode == "live" and not flight_record:
        event["status"] = "clarification_required"
        event["summary"] = (
            "Live flight planning needs an exact flight-number calendar match with known duration. Connect this travel context before proposing changes."
        )
        return event
    departure = None
    airport_window_start = changed - timedelta(minutes=120)
    if flight:
        event["limitations"] = [
            "Travel time is not calculated. Check your airport departure time yourself; pickup-time actions are omitted. Calendar checks cover the airport check-in and flight window only."
        ]
    landing = changed + flight_duration
    meeting_start = (
        datetime.fromisoformat(meeting["start"])
        if isinstance(meeting["start"], str)
        else datetime.fromisoformat(meeting["start"]["dateTime"])
    )
    meeting_end = (
        datetime.fromisoformat(meeting["end"])
        if isinstance(meeting["end"], str)
        else datetime.fromisoformat(meeting["end"]["dateTime"])
    )
    conflict = (
        flight
        and meeting_start < landing + timedelta(minutes=60)
        and meeting_end > (departure or airport_window_start)
    )
    proposed = (landing + timedelta(minutes=90)).replace(minute=0, second=0) if flight else changed
    if flight and proposed < landing + timedelta(minutes=60):
        proposed += timedelta(hours=1)
    if flight and not conflict:
        proposed = meeting_start
    if mode == "live" and (not flight or conflict):
        if (
            proposed.astimezone(zone).date().isoformat() != entities["date"]
            or (proposed + (meeting_end - meeting_start)).astimezone(zone).date().isoformat()
            != entities["date"]
        ):
            event["status"] = "clarification_required"
            event["summary"] = (
                "The proposed meeting extends beyond the checked calendar date. Verify availability on that date."
            )
            return event
        for record in flat:
            if record["application"] != "calendar" or record["id"] == meeting["id"]:
                continue
            if flight_record and record["id"] == flight_record["id"]:
                continue
            if (
                record.get("record", {}).get("transparency") == "transparent"
                or record.get("record", {}).get("status") == "cancelled"
            ):
                continue
            try:
                busy_start, busy_end = calendar_time(record, "start"), calendar_time(record, "end")
            except (KeyError, TypeError, ValueError):
                # All-day entries remain relevant busy context.
                try:
                    busy_start = datetime.fromisoformat(record["start"]["date"]).replace(tzinfo=zone)
                    busy_end = datetime.fromisoformat(record["end"]["date"]).replace(tzinfo=zone)
                except (KeyError, TypeError, ValueError):
                    event["status"] = "clarification_required"
                    event["summary"] = "Calendar availability cannot be verified from incomplete records."
                    return event
            if proposed < busy_end and proposed + (meeting_end - meeting_start) > busy_start:
                event["status"] = "clarification_required"
                event["summary"] = (
                    "The proposed meeting time overlaps another calendar appointment. Choose an available time."
                )
                return event

    def add(app, type, title, reason, args, deps=None, reversible=False):
        policy = classify(app, type)
        action = {
            "id": uid(),
            "application": app,
            "type": type,
            "title": title,
            "reason": reason,
            "target": args.get("recipient")
            or args.get("contact")
            or args.get("event_id")
            or args.get("file_id")
            or args.get("channel_id")
            or args.get("destination", ""),
            "arguments": args,
            "risk": policy.risk.value,
            "status": "pending" if type == "read" else "awaiting_approval",
            "requires_approval": policy.requires_approval,
            "reversible": reversible,
            "dependencies": deps or [],
            "evidence": None,
            "error": None,
        }
        action["arguments_hash"] = digest(args)
        event["actions"].append(action)
        return action["id"]

    if flight:
        event["entities"].update(
            {
                "departure_time": departure.isoformat() if departure else None,
                "arrival_time": landing.isoformat(),
                "calendar_conflict": conflict,
            }
        )
    calendar_id = None
    if not flight or conflict:
        calendar_id = add(
            "calendar",
            "update",
            f"Move client meeting to {proposed:%H:%M}",
            "The new schedule affects the existing client commitment."
            if flight
            else "The client requested a new meeting time.",
            {
                "calendar_id": meeting.get("calendar_id", "primary"),
                "event_id": meeting["id"],
                "etag": meeting.get("etag", ""),
                "start": proposed.isoformat(),
                "end": (proposed + (meeting_end - meeting_start)).isoformat(),
                "summary": meeting.get("title", meeting.get("summary", "Client meeting")),
            },
            [],
            mode == "demo",
        )
    doc_id = None
    if proposal:
        doc_id = add(
            "drive",
            "read",
            "Retrieve the current client proposal",
            "Use the existing proposal; external input cannot select unrelated files.",
            {
                "file_id": proposal["id"],
                "expected_sha256": proposal.get("content_sha256")
                or hashlib.sha256(proposal.get("content", "").encode()).hexdigest(),
            },
        )
    dependencies = [i for i in [calendar_id, doc_id] if i]
    meeting_title = meeting.get("title", "Client meeting")
    greeting = "Hi Alex" if mode == "demo" else "Hello"
    body = f"{greeting}, {'my flight schedule changed' if flight else 'confirming the updated meeting time'}. {meeting_title} is {'now ' if calendar_id else 'still '}scheduled for {proposed:%d %b at %H:%M %Z}."
    email_args = {
        "recipient": thread["recipient"],
        "validated_recipients": [thread["recipient"]],
        "subject": "Updated schedule · " + meeting_title,
        "body": body,
    }
    if thread.get("thread_id"):
        email_args["thread_id"] = thread["thread_id"]
    if proposal and not flight:
        email_args["attachment_id"] = proposal["id"]
        email_args["attachment_sha256"] = (
            proposal.get("content_sha256") or hashlib.sha256(proposal.get("content", "").encode()).hexdigest()
        )
    add(
        "gmail",
        "send",
        "Send the client an updated schedule",
        "Keep the known client informed after the calendar change.",
        email_args,
        dependencies,
    )
    discord = find("discord")
    if discord:
        add(
            "discord",
            "send",
            "Notify the project team",
            "The team uses the existing project channel for schedule changes.",
            {
                "channel_id": discord.get("channel_id", discord["id"]),
                "body": f"{meeting_title}: {proposed:%d %b, %H:%M %Z}. "
                + (
                    "Flight change affects travel arrangements."
                    if flight
                    else "Updated proposal is ready for review."
                ),
            },
            [calendar_id] if calendar_id else [],
        )
    whatsapp = find("whatsapp", lambda r: r.get("verified") is True and bool(r.get("contact")))
    if flight and whatsapp:
        number = entities.get("flight") or "my flight"
        add(
            "whatsapp",
            "send",
            "Share the flight change in WhatsApp",
            "The configured conversation was verified in a signed-in browser session. No pickup or airport departure time is inferred.",
            {
                "contact": whatsapp["contact"],
                "body": (
                    f"My flight {number} on {entities['date']} has moved to {changed:%H:%M %Z}. "
                    "Please check your travel plans with me. I have not calculated an airport departure time."
                ),
            },
            [calendar_id] if calendar_id else [],
        )
    event["summary"] = (
        f"Found {len(event['actions'])} actions across {len(set(a['application'] for a in event['actions']))} applications. "
        + ("Airport departure and the client meeting overlap. " if conflict else "")
        + "Review exact changes before anything is sent."
        + (" " + " ".join(event["limitations"]) if event.get("limitations") else "")
    )
    return event


def make_reschedule_plan(
    calendar_event,
    new_start,
    new_end,
    timezone,
    settings,
    notify_discord=False,
    notify_whatsapp=False,
):
    """Build an approval-only plan from one provider-read Calendar event.

    This deliberately accepts the target event itself, rather than selecting one
    from free-form context. The caller owns fetching it with the authenticated
    owner's Google grant and checking availability before invoking this helper.
    """
    zone = ZoneInfo(timezone)
    try:
        current_start = calendar_time(calendar_event, "start")
        current_end = calendar_time(calendar_event, "end")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Calendar event must have timezone-aware start and end times") from exc
    if not calendar_event.get("id") or not calendar_event.get("etag"):
        raise ValueError("Calendar event ID and etag are required")
    if calendar_event.get("status") == "cancelled":
        raise ValueError("Cancelled Calendar events cannot be rescheduled")
    duration = current_end - current_start
    if not timedelta(0) < duration <= timedelta(days=1):
        raise ValueError("Calendar event duration must be between zero and 24 hours")
    if not new_start.tzinfo or not new_end.tzinfo:
        raise ValueError("New Calendar times must include a timezone offset")
    if new_start.astimezone(zone).utcoffset() is None or new_end.astimezone(zone).utcoffset() is None:
        raise ValueError("New Calendar times must be valid in the selected timezone")
    if new_end - new_start != duration:
        raise ValueError("Rescheduling must preserve the existing Calendar event duration")

    title = calendar_event.get("summary") or "Calendar event"
    event = {
        "id": uid(),
        "title": f"Reschedule {title}",
        "event_type": "calendar_reschedule",
        "source": "calendar",
        "status": "awaiting_approval",
        "created_at": now_iso(),
        "version": 1,
        "summary": "",
        "simulation": False,
        "entities": {
            "calendar_event_id": calendar_event["id"],
            "calendar_etag": calendar_event["etag"],
            "timezone": timezone,
            "previous_start": current_start.isoformat(),
            "previous_end": current_end.isoformat(),
        },
        "actions": [],
        "context": [
            {
                "application": "calendar",
                "detail": "Exact owner Calendar event read before planning.",
                "records": [{"id": calendar_event["id"], "etag": calendar_event["etag"]}],
            }
        ],
        "timeline": [],
        "input": "Explicit Calendar reschedule request",
    }

    def add(application, action_type, action_title, reason, arguments, dependencies=None):
        policy = classify(application, action_type)
        action = {
            "id": uid(),
            "application": application,
            "type": action_type,
            "title": action_title,
            "reason": reason,
            "target": arguments.get("event_id") or arguments.get("channel_id") or arguments.get("contact", ""),
            "arguments": arguments,
            "risk": policy.risk.value,
            "status": "awaiting_approval",
            "requires_approval": policy.requires_approval,
            "reversible": application == "calendar",
            "dependencies": dependencies or [],
            "evidence": None,
            "error": None,
        }
        action["arguments_hash"] = digest(arguments)
        event["actions"].append(action)
        return action["id"]

    calendar_action_id = add(
        "calendar",
        "update",
        f"Move {title}",
        "The requested time and the current provider event were checked before creating this plan.",
        {
            "calendar_id": "primary",
            "event_id": calendar_event["id"],
            "etag": calendar_event["etag"],
            "start": new_start.isoformat(),
            "end": new_end.isoformat(),
            "summary": title,
        },
    )
    message = f"{title} is planned for {new_start.astimezone(zone):%d %b, %H:%M %Z}."
    if notify_discord and not (getattr(settings, "discord_bot_token", "") and getattr(settings, "discord_channel_id", "")):
        raise ValueError("Discord notification is not configured")
    if notify_discord:
        add(
            "discord",
            "send",
            "Notify the configured Discord channel",
            "The configured channel will be notified only after Calendar read-back verifies the update.",
            {"channel_id": settings.discord_channel_id, "body": message},
            [calendar_action_id],
        )
    whatsapp_ready = (
        (getattr(settings, "whatsapp_enabled", False) or getattr(settings, "whatsapp_bridge_enabled", False))
        and bool(getattr(settings, "whatsapp_contact", ""))
    )
    if notify_whatsapp and not whatsapp_ready:
        raise ValueError("WhatsApp notification is not configured")
    if notify_whatsapp:
        add(
            "whatsapp",
            "send",
            "Notify the configured WhatsApp contact",
            "The configured contact will be notified only after Calendar read-back verifies the update.",
            {"contact": settings.whatsapp_contact, "body": message},
            [calendar_action_id],
        )
    event["summary"] = (
        f"Prepared {len(event['actions'])} approval-required action(s) for the exact Calendar event. "
        "Calendar verification is required before configured notifications can send."
    )
    return event
