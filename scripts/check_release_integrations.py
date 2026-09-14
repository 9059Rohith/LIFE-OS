"""Secret-safe read-only checks against the native live runtime configuration.

Does not start the runtime, refresh tokens, send messages, or change provider data.
The optional synthetic Maps route checks API access only, never the user's commute.
"""

import asyncio
import json
import runpy
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from lifeos.config import Settings  # noqa: E402
from lifeos.providers import LiveProviders, ProviderError  # noqa: E402


def read_grant(settings):
    engine = create_engine(
        settings.database_url, echo=False, hide_parameters=True, connect_args={"connect_timeout": 5}
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            row = connection.execute(
                text("SELECT data FROM documents WHERE owner=:owner AND kind=:kind AND id=:id"),
                {"owner": "owner", "kind": "token", "id": "owner:token:google"},
            ).first()
        if not row:
            return None
        document = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        return json.loads(Fernet(settings.encryption_key.encode()).decrypt(document["encrypted"].encode()))
    finally:
        engine.dispose()


async def check_discord(provider, settings):
    if not settings.discord_bot_token:
        return {"status": "token_missing"}
    headers = provider._discord_headers()

    async def get(path):
        return await provider._request("GET", "https://discord.com/api/v10" + path, headers=headers)

    identity = await get("/users/@me")
    result = {"authenticated_bot": identity.get("bot") is True}
    if not settings.discord_channel_id:
        return {**result, "status": "channel_missing"}
    try:
        channel = await get("/channels/" + settings.discord_channel_id)
    except ProviderError as error:
        return {**result, "status": error.code, "failed_stage": "channel_metadata", "message_sent": False}
    result["channel_metadata_readable"] = True
    guild_id = channel.get("guild_id")
    if not guild_id:
        return {**result, "status": "non_guild_channel_permissions_unchecked"}
    member, roles = await asyncio.gather(
        get(f"/guilds/{guild_id}/members/{identity['id']}"), get(f"/guilds/{guild_id}/roles")
    )
    role_ids = set(member.get("roles", [])) | {guild_id}
    permissions = 0
    for role in roles:
        if role["id"] in role_ids:
            permissions |= int(role["permissions"])
    administrator = bool(permissions & 8)
    if not administrator:
        overwrites = channel.get("permission_overwrites", [])
        for overwrite in overwrites:
            if overwrite["id"] == guild_id:
                permissions = (permissions & ~int(overwrite["deny"])) | int(overwrite["allow"])
        deny = allow = 0
        for overwrite in overwrites:
            if overwrite["type"] == 0 and overwrite["id"] in role_ids - {guild_id}:
                deny |= int(overwrite["deny"])
                allow |= int(overwrite["allow"])
        permissions = (permissions & ~deny) | allow
        for overwrite in overwrites:
            if overwrite["type"] == 1 and overwrite["id"] == identity["id"]:
                permissions = (permissions & ~int(overwrite["deny"])) | int(overwrite["allow"])
    for label, bit in {"view_channel": 1024, "send_messages": 2048, "read_message_history": 65536}.items():
        result[label] = administrator or bool(permissions & bit)
    result["communication_timeout_present"] = bool(member.get("communication_disabled_until"))
    result["status"] = "permissions_read_only_verified"
    result["message_sent"] = False
    return result


async def main():
    env = dotenv_values(ROOT / ".env")
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "read_only": True,
        "configuration": "native live runner / PostgreSQL",
        "dotenv": {
            "maps_key_present": bool(env.get("LIFEOS_GOOGLE_MAPS_API_KEY")),
            "origin_present": bool(env.get("LIFEOS_MAPS_ORIGIN")),
            "destination_present": bool(env.get("LIFEOS_MAPS_DESTINATION")),
            "google_client_pair_present": bool(
                env.get("LIFEOS_GOOGLE_CLIENT_ID") and env.get("LIFEOS_GOOGLE_CLIENT_SECRET")
            ),
        },
    }
    # The runner sets this process's settings only; __main__ is deliberately not executed.
    runpy.run_path(str(ROOT / ".private/run_native_live.py"), run_name="release_check_config")
    settings = Settings()

    async def no_token(*args):
        raise RuntimeError("Token refresh and save are disabled in this checker")

    provider = LiveProviders(settings, no_token, no_token)
    try:
        try:
            token = read_grant(settings)
            if not token or not token.get("access_token"):
                report["google"] = {
                    "status": "oauth_grant_missing",
                    "client_credentials_are_not_consent": True,
                }
            elif token.get("expires_at", 0) <= time.time():
                report["google"] = {
                    "status": "access_token_expired",
                    "refresh_available": bool(token.get("refresh_token")),
                    "refresh_attempted": False,
                }
            else:
                report["google"] = {"status": "grant_present", "read_access": {}}
                endpoints = {
                    "gmail": ("https://gmail.googleapis.com/gmail/v1/users/me/messages", {"maxResults": 1}),
                    "calendar": (
                        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                        {"maxResults": 1},
                    ),
                    "drive": (
                        "https://www.googleapis.com/drive/v3/files",
                        {"pageSize": 1, "fields": "files(id)"},
                    ),
                }
                for name, (url, params) in endpoints.items():
                    try:
                        await provider._request(
                            "GET",
                            url,
                            params=params,
                            headers={"Authorization": "Bearer " + token["access_token"]},
                        )
                        report["google"]["read_access"][name] = "verified"
                    except ProviderError as error:
                        report["google"]["read_access"][name] = error.code
        except Exception:
            report["google"] = {"status": "database_or_grant_unavailable", "details_suppressed": True}
        synthetic = not (settings.maps_origin and settings.maps_destination)
        report["maps"] = {
            "route_source": "synthetic public landmarks for API validation only"
            if synthetic
            else "configured route",
            "user_route_configured": not synthetic,
        }
        try:
            routes = await provider.route(
                "India Gate, New Delhi, India" if synthetic else settings.maps_origin,
                "Indira Gandhi International Airport, New Delhi, India"
                if synthetic
                else settings.maps_destination,
            )
            report["maps"]["status"] = "live_route_verified" if routes.get("routes") else "no_routes"
        except ProviderError as error:
            report["maps"]["status"] = error.code
            # Only allowlisted provider codes are retained; never record raw error messages.
            response = await provider.http.post(
                "https://routes.googleapis.com/directions/v2:computeRoutes",
                headers={
                    "X-Goog-Api-Key": settings.google_maps_api_key,
                    "X-Goog-FieldMask": "routes.duration,routes.distanceMeters",
                },
                json={
                    "origin": {
                        "address": "India Gate, New Delhi, India" if synthetic else settings.maps_origin
                    },
                    "destination": {
                        "address": "Indira Gandhi International Airport, New Delhi, India"
                        if synthetic
                        else settings.maps_destination
                    },
                    "travelMode": "DRIVE",
                    "routingPreference": "TRAFFIC_AWARE",
                },
            )
            report["maps"]["http_status"] = response.status_code
            details = response.json().get("error", {}).get("details", [])
            allowed = {
                "SERVICE_DISABLED",
                "BILLING_DISABLED",
                "API_KEY_INVALID",
                "API_KEY_SERVICE_BLOCKED",
                "API_KEY_HTTP_REFERRER_BLOCKED",
                "API_KEY_IP_ADDRESS_BLOCKED",
                "CONSUMER_INVALID",
            }
            report["maps"]["provider_reasons"] = [d["reason"] for d in details if d.get("reason") in allowed]
        try:
            report["discord"] = await check_discord(provider, settings)
        except ProviderError as error:
            report["discord"] = {"status": error.code, "message_sent": False}
    finally:
        await provider.close()
    (ROOT / ".private/release-integration-check.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        print('{"status": "check_failed", "details_suppressed": true}')
        raise SystemExit(1) from None
