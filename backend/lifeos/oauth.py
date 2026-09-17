"""Google OAuth helpers. The API layer owns expiring, single-use owner-bound state."""

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx

SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.readonly",
)


def create_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def authorization_url(settings, state: str, challenge: str) -> str:
    if not settings.google_client_id or not settings.google_redirect_uri:
        raise ValueError("Google OAuth client and redirect URI are not configured")
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "include_granted_scopes": "true",
        }
    )


async def _token_request(settings, fields: dict) -> dict:
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                **fields,
            },
        )
    if response.status_code != 200:
        raise ValueError("Google authentication failed; reconnect the account")
    token = response.json()
    if not token.get("access_token"):
        raise ValueError("Google returned no access token")
    token["expires_at"] = time.time() + int(token.get("expires_in", 3600))
    return token


async def exchange_code(settings, code: str, verifier: str) -> dict:
    return await _token_request(
        settings,
        {
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        },
    )


async def refresh_token(settings, token: dict) -> dict:
    if not token.get("refresh_token"):
        raise ValueError("Google session expired; reconnect the account")
    refreshed = await _token_request(
        settings, {"refresh_token": token["refresh_token"], "grant_type": "refresh_token"}
    )
    return {**token, **refreshed}
