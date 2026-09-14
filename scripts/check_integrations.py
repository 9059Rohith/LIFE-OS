"""Read-only integration checks. Prints statuses, never credentials or response bodies.

Run from the repository root with the project virtual environment. This script
does not change mode, refresh OAuth grants, send messages, or launch browsers.
"""

import asyncio
import json
import os
import re
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from cryptography.fernet import Fernet
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def status(value, detail):
    return {"status": value, "detail": detail}


def read_google_grant(database_url, cipher):
    """Read the single live owner's token without initializing or migrating DB."""
    try:
        url = make_url(database_url)
        if url.get_backend_name() == "sqlite":
            filename = Path(url.database or "")
            if not filename.is_absolute():
                filename = ROOT / filename
            if not filename.is_file():
                return status(
                    "oauth_grant_missing", "No existing database grant; Connect Google after live login."
                )
            connection = sqlite3.connect(filename.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                row = connection.execute(
                    "SELECT data FROM documents WHERE owner=? AND kind=? AND id=?",
                    ("owner", "token", "owner:token:google"),
                ).fetchone()
            finally:
                connection.close()
        elif url.get_backend_name() == "postgresql":
            engine = create_engine(url, echo=False, hide_parameters=True, connect_args={"connect_timeout": 5})
            try:
                with engine.connect() as connection:
                    row = connection.execute(
                        text("SELECT data FROM documents WHERE owner=:owner AND kind=:kind AND id=:id"),
                        {"owner": "owner", "kind": "token", "id": "owner:token:google"},
                    ).first()
            finally:
                engine.dispose()
        else:
            return status("unchecked", "Database type is unsupported by this read-only checker.")
        if not row:
            return status(
                "oauth_grant_missing",
                "OAuth client credentials exist separately from user consent; Connect Google after live login.",
            )
        if cipher is None:
            return status(
                "encryption_required", "A stored grant cannot be checked without a valid encryption key."
            )
        try:
            token = json.loads(cipher.decrypt(json.loads(row[0])["encrypted"].encode()))
        except Exception:
            return status(
                "grant_unreadable",
                "Stored OAuth grant could not be decrypted; reconnect with the configured encryption key.",
            )
        if not token.get("access_token"):
            return status("oauth_grant_missing", "Stored grant has no access token; reconnect Google.")
        if token.get("expires_at", 0) <= time.time():
            return status(
                "refresh_available" if token.get("refresh_token") else "grant_expired",
                "Stored access token has expired; refresh was not attempted by this read-only check.",
            )
        return status(
            "grant_present_unverified",
            "Encrypted owner grant is present; Google account access was not requested.",
        )
    except Exception:
        return status(
            "database_unavailable",
            "Could not inspect the existing database safely; no database changes were made.",
        )


async def get_status(client, url, headers):
    try:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            try:
                return "ok", response.json()
            except Exception:
                return "invalid_response", None
        return {
            401: "authentication_rejected",
            403: "permission_denied",
            404: "not_found",
            429: "rate_limited",
        }.get(response.status_code, "provider_unavailable"), None
    except Exception:
        return "connection_failed", None


async def check_openai(client, values):
    key = values.get("LIFEOS_OPENAI_API_KEY", "")
    if not key:
        return status("missing", "Set LIFEOS_OPENAI_API_KEY.")
    result, data = await get_status(
        client, "https://api.openai.com/v1/models", {"Authorization": "Bearer " + key}
    )
    if result != "ok":
        return status(
            result, "OpenAI read-only model access could not be confirmed; no generation was requested."
        )
    identifiers = (
        {item.get("id") for item in data.get("data", []) if isinstance(item, dict)}
        if isinstance(data, dict)
        else set()
    )
    expected = values.get("LIFEOS_OPENAI_MODEL", "gpt-4.1-mini")
    return {
        **status(
            "authenticated",
            "Read-only model listing succeeded; billing, generation and voice remain untested.",
        ),
        "configured_model": "listed" if expected in identifiers else "not_listed",
        "transcription_model": "listed" if "gpt-4o-mini-transcribe" in identifiers else "not_listed",
        "speech_model": "listed" if "gpt-4o-mini-tts" in identifiers else "not_listed",
    }


async def check_discord(client, values):
    token = values.get("LIFEOS_DISCORD_BOT_TOKEN", "")
    if not token:
        return status("missing", "Set LIFEOS_DISCORD_BOT_TOKEN.")
    headers = {"Authorization": "Bot " + token}
    result, identity = await get_status(client, "https://discord.com/api/v10/users/@me", headers)
    if result != "ok":
        return status(result, "Discord bot authentication could not be confirmed.")
    if not isinstance(identity, dict) or identity.get("bot") is not True:
        return status("bot_not_confirmed", "The authenticated identity was not confirmed as a bot.")
    channel = values.get("LIFEOS_DISCORD_CHANNEL_ID", "")
    if not re.fullmatch(r"\d{15,22}", channel):
        return status(
            "channel_missing_or_invalid", "Bot authenticated; configure the numeric Discord channel ID."
        )
    result, _ = await get_status(client, "https://discord.com/api/v10/channels/" + channel, headers)
    return status(
        "channel_access_confirmed" if result == "ok" else "channel_" + result,
        "Bot authenticated; channel metadata readable. Sending and message history were not tested."
        if result == "ok"
        else "Bot authenticated, but the configured channel could not be read.",
    )


async def check():
    loaded = dotenv_values(ROOT / ".env")
    values = {key: value or "" for key, value in loaded.items()}
    values.update({key: value for key, value in os.environ.items() if key.startswith("LIFEOS_")})
    cipher = None
    try:
        if values.get("LIFEOS_ENCRYPTION_KEY"):
            cipher = Fernet(values["LIFEOS_ENCRYPTION_KEY"].encode())
    except Exception:
        pass
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "checks_are_read_only": True,
        "application_mode": status(
            "live" if values.get("LIFEOS_MODE") == "live" else "demo",
            "Current configuration only; this check does not switch app mode.",
        ),
        "auth_password": status(
            "ready" if len(values.get("LIFEOS_AUTH_PASSWORD", "")) >= 16 else "missing_or_short",
            "Live owner password must contain at least 16 characters.",
        ),
        "encryption": status(
            "ready" if cipher else "missing_or_invalid",
            "Fernet key format checked locally; key material is not included.",
        ),
    }
    client_id, secret = (
        values.get("LIFEOS_GOOGLE_CLIENT_ID", ""),
        values.get("LIFEOS_GOOGLE_CLIENT_SECRET", ""),
    )
    plausible = (
        bool(re.fullmatch(r"[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com", client_id))
        and len(secret) >= 12
        and not any(c.isspace() for c in secret)
    )
    report["google_client"] = status(
        "format_valid_unverified" if plausible else "missing_or_invalid_format",
        "Client ID/secret format only; valid client credentials do not constitute an OAuth grant.",
    )
    report["google_grant"] = read_google_grant(
        values.get("LIFEOS_DATABASE_URL", "sqlite:///./lifeos.db"), cipher
    )
    try:
        redirect = urlsplit(values.get("LIFEOS_GOOGLE_REDIRECT_URI", ""))
        local = redirect.hostname in {"localhost", "127.0.0.1"}
        valid = (
            redirect.path == "/api/integrations/google/callback"
            and (redirect.scheme == "https" or local and redirect.scheme == "http")
            and not redirect.query
            and not redirect.fragment
            and not redirect.username
        )
        expected_port = int(values.get("LIFEOS_PORT", "8010"))
        report["google_callback"] = status(
            "port_mismatch"
            if valid and local and (redirect.port or 80) != expected_port
            else "format_valid"
            if valid
            else "invalid",
            "Callback must exactly match the running API origin and Google Cloud registration; registration cannot be checked locally.",
        )
    except Exception:
        report["google_callback"] = status("invalid", "OAuth callback URI could not be validated.")
    profile = Path(values.get("LIFEOS_WHATSAPP_PROFILE_DIR", ".private/whatsapp"))
    if not profile.is_absolute():
        profile = ROOT / profile
    enabled = values.get("LIFEOS_WHATSAPP_ENABLED", "false").lower() in {"true", "1", "yes"}
    report["whatsapp"] = {
        **status(
            "enabled" if enabled else "disabled",
            "Browser was not launched; signed-in session and contact identity remain unverified.",
        ),
        "profile": "present" if profile.is_dir() else "missing",
        "contact": "configured" if values.get("LIFEOS_WHATSAPP_CONTACT") else "missing",
    }
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        report["openai"], report["discord"] = await asyncio.gather(
            check_openai(client, values), check_discord(client, values)
        )
    return report


def main():
    try:
        report = asyncio.run(check())
        output = ROOT / ".private" / "integration-check.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    except Exception:
        print(
            json.dumps(
                {
                    "status": "check_failed",
                    "detail": "Validation could not complete. Exception details are suppressed to protect credentials.",
                }
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
