"""Bounded provider read checks. Never return credentials or provider payloads."""

import asyncio

from .planning import APPS
from .providers import DISCORD, GMAIL, GOOGLE, ProviderError, segment


async def connection_checks(settings, providers, owner):
    def result(key, status, description):
        return {
            "id": key,
            "name": APPS[key],
            "status": status,
            "mode": settings.mode,
            "description": description,
        }

    if settings.mode == "demo":
        return [
            result(key, "local_demo", "Isolated demo data; no external account was checked.") for key in APPS
        ]

    async def check(key):
        if key == "whatsapp":
            if not settings.whatsapp_enabled:
                return result(key, "not_connected", "Link the dedicated browser with WhatsApp's QR flow, then enable the worker.")
            try:
                await asyncio.wait_for(providers.check_whatsapp(), timeout=90)
                return result(key, "read_access_verified", "Signed-in browser, exact chat and composer verified. A message is sent only through an approved action.")
            except ProviderError as exc:
                if exc.code == "BROWSER_PROFILE_IN_USE":
                    return result(key, "needs_attention", "Another LIFEOS process is using the dedicated WhatsApp browser profile. Close that process and check again.")
                return result(key, "needs_attention", "The dedicated WhatsApp browser or exact configured chat could not be verified. Check the browser session and chat name.")
            except Exception:
                return result(key, "needs_attention", "The dedicated WhatsApp browser or exact configured chat could not be verified. Check the browser session and chat name.")
        if key == "discord" and not (settings.discord_bot_token and settings.discord_channel_id):
            return result(
                key, "not_connected", "Configure a bot and channel, then invite the bot to that server."
            )
        try:
            if key == "gmail":
                call = providers._google(owner, "GET", GMAIL + "/profile")
            elif key == "calendar":
                call = providers._google(
                    owner, "GET", GOOGLE + "/calendar/v3/calendars/primary/events", params={"maxResults": 1}
                )
            elif key == "drive":
                call = providers._google(
                    owner, "GET", GOOGLE + "/drive/v3/files", params={"pageSize": 1, "fields": "files(id)"}
                )
            elif key == "discord":
                call = providers._request(
                    "GET",
                    DISCORD + "/channels/" + segment(settings.discord_channel_id) + "/messages",
                    headers=providers._discord_headers(),
                    params={"limit": 1},
                )
            else:
                raise ValueError(f"Unsupported integration: {key}")
            await asyncio.wait_for(call, timeout=25)
            return result(
                key,
                "read_access_verified",
                "Read access was verified at the last check. No messages or calendar changes were made; write permissions and delivery still require verification.",
            )
        except ProviderError as exc:
            if exc.code == "AUTHENTICATION_ERROR":
                return result(
                    key,
                    "not_connected",
                    "Complete Connect Google or reconnect the expired account."
                    if key in {"gmail", "calendar", "drive"}
                    else "Check the configured credential; the provider rejected authentication.",
                )
            if exc.code == "AUTHORIZATION_ERROR":
                detail = {
                    "discord": "Channel access denied. Invite the bot and grant View Channel and Read Message History; sending also needs Send Messages.",
                }.get(
                    key,
                    "Access denied. Reconnect Google with the required permission and enable this API in Google Cloud.",
                )
                return result(key, "needs_attention", detail)
            return result(
                key,
                "needs_attention",
                "The provider check failed. Check API availability, quota and configuration, then retry.",
            )
        except Exception:
            return result(
                key,
                "needs_attention",
                "The connection check could not finish. Retry after checking network and provider availability.",
            )

    return list(await asyncio.gather(*(check(key) for key in APPS)))
