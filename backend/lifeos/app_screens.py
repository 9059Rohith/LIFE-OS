"""Owner-scoped, read-only snapshots for LIFEOS's connected application screens."""

import asyncio
import re
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request

from .providers import DISCORD, GMAIL, GOOGLE, ProviderError, decode_body, message_parts, segment


def short(value, limit=4000):
    return str(value or "")[:limit]


def headers_for(message):
    return {
        str(header.get("name", "")).lower(): short(header.get("value"), 300)
        for header in message.get("payload", {}).get("headers", [])
        if isinstance(header, dict)
    }


def plain_body(message):
    for part in message_parts(message.get("payload", {})):
        if part.get("mimeType") != "text/plain" or not part.get("body", {}).get("data"):
            continue
        try:
            return decode_body(part["body"]["data"]).decode("utf-8", errors="replace")[:20000]
        except (ValueError, TypeError):
            break
    return short(message.get("snippet"), 20000)


def discord_avatar(author):
    user_id = str(author.get("id", ""))
    avatar = str(author.get("avatar", ""))
    if not re.fullmatch(r"[0-9]{1,24}", user_id) or not re.fullmatch(r"[A-Za-z0-9_]{1,80}", avatar):
        return ""
    return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png?size=64"


def register_app_screens(app, settings, security, providers):
    def owner_for(request):
        owner = security.require(request)
        if settings.mode != "live" or not providers:
            raise HTTPException(409, "Connected application screens require live mode")
        return owner

    async def checked(action):
        try:
            return await asyncio.wait_for(action, timeout=30)
        except ProviderError as exc:
            raise HTTPException(502, f"Connected app access failed ({exc.code}). Check Integrations.") from None
        except TimeoutError:
            raise HTTPException(504, "Connected app did not respond in time. Retry shortly.") from None

    @app.get("/api/apps/gmail")
    async def gmail(request: Request):
        owner = owner_for(request)

        async def load():
            listed = await providers._google(
                owner, "GET", GMAIL + "/messages", params={"labelIds": "INBOX", "maxResults": 12}
            )
            ids = [item.get("id") for item in listed.get("messages", [])[:12] if item.get("id")]
            messages = await asyncio.gather(*(
                providers._google(
                    owner, "GET", GMAIL + "/messages/" + segment(mid),
                    params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                ) for mid in ids
            ), return_exceptions=True)
            items = []
            for message in messages:
                if not isinstance(message, dict):
                    continue
                headers = headers_for(message)
                items.append({
                    "id": short(message.get("id"), 128),
                    "from": headers.get("from", "Unknown sender"),
                    "subject": headers.get("subject", "(No subject)"),
                    "preview": short(message.get("snippet"), 500),
                    "date": headers.get("date", ""),
                    "unread": "UNREAD" in message.get("labelIds", []),
                })
            return {"application": "gmail", "title": "Inbox", "items": items}

        return await checked(load())

    @app.get("/api/apps/gmail/{message_id}")
    async def gmail_message(message_id: str, request: Request):
        owner = owner_for(request)

        async def load():
            message = await providers._google(
                owner, "GET", GMAIL + "/messages/" + segment(message_id), params={"format": "full"}
            )
            headers = headers_for(message)
            return {
                "id": short(message.get("id"), 128),
                "from": headers.get("from", "Unknown sender"),
                "to": headers.get("to", ""),
                "subject": headers.get("subject", "(No subject)"),
                "date": headers.get("date", ""),
                "body": plain_body(message),
            }

        return await checked(load())

    @app.get("/api/apps/discord")
    async def discord(request: Request):
        owner_for(request)
        if not settings.discord_bot_token or not settings.discord_channel_id:
            raise HTTPException(409, "Discord channel is not configured")
        channel_id = segment(settings.discord_channel_id)

        async def load():
            channel, messages = await asyncio.gather(
                providers._request("GET", DISCORD + "/channels/" + channel_id, headers=providers._discord_headers()),
                providers._request("GET", DISCORD + "/channels/" + channel_id + "/messages", headers=providers._discord_headers(), params={"limit": 25}),
            )
            items = [{
                "id": short(message.get("id"), 128),
                "author": short(message.get("author", {}).get("global_name") or message.get("author", {}).get("username"), 100),
                "avatar_url": discord_avatar(message.get("author", {})),
                "content": short(message.get("content"), 4000),
                "date": short(message.get("timestamp"), 64),
                "attachments": min(len(message.get("attachments", [])), 20),
            } for message in reversed(messages[:25]) if isinstance(message, dict)]
            return {"application": "discord", "title": "#" + short(channel.get("name"), 100), "items": items}

        return await checked(load())

    @app.get("/api/apps/calendar")
    async def calendar(request: Request):
        owner = owner_for(request)

        async def load():
            start = datetime.now(UTC)
            events = await providers._google(owner, "GET", GOOGLE + "/calendar/v3/calendars/primary/events", params={
                "timeMin": start.isoformat(), "timeMax": (start + timedelta(days=14)).isoformat(),
                "singleEvents": "true", "orderBy": "startTime", "maxResults": 30,
            })
            items = [{
                "id": short(event.get("id"), 128),
                "title": short(event.get("summary") or "Untitled event", 300),
                "start": short(event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"), 64),
                "end": short(event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"), 64),
                "location": short(event.get("location"), 300),
            } for event in events.get("items", [])[:30] if isinstance(event, dict)]
            return {"application": "calendar", "title": "Next 14 days", "items": items}

        return await checked(load())

    @app.get("/api/apps/drive")
    async def drive(request: Request):
        owner = owner_for(request)

        async def load():
            files = await providers._google(owner, "GET", GOOGLE + "/drive/v3/files", params={
                "pageSize": 30, "q": "trashed = false", "orderBy": "modifiedTime desc",
                "fields": "files(id,name,mimeType,modifiedTime),nextPageToken",
            })
            items = [{
                "id": short(file.get("id"), 128),
                "name": short(file.get("name") or "Untitled file", 300),
                "type": short(file.get("mimeType"), 120),
                "modified": short(file.get("modifiedTime"), 64),
            } for file in files.get("files", [])[:30] if isinstance(file, dict)]
            return {"application": "drive", "title": "Recent files", "items": items}

        return await checked(load())

    @app.get("/api/apps/whatsapp")
    async def whatsapp(request: Request):
        owner_for(request)
        if not settings.whatsapp_enabled or not settings.whatsapp_contact:
            raise HTTPException(409, "WhatsApp chat is not configured")
        try:
            return await asyncio.wait_for(providers.read_whatsapp_messages(), timeout=90)
        except ProviderError as exc:
            raise HTTPException(502, f"WhatsApp chat unavailable ({exc.code}). Check Integrations.") from None
        except TimeoutError:
            raise HTTPException(504, "WhatsApp chat did not respond in time.") from None

    @app.get("/api/apps/maps")
    async def maps(request: Request):
        owner_for(request)
        return {
            "application": "maps", "title": "Travel route", "items": [],
            "status": "needs_attention" if not (settings.maps_origin and settings.maps_destination) else "configured",
            "message": "Set your actual origin and destination in LIFEOS configuration. The Routes API key must also be permitted for Routes requests."
            if not (settings.maps_origin and settings.maps_destination)
            else "Route configured. Use a planning event to calculate travel time.",
        }
