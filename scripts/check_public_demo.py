"""Exercise a password-protected public demo without printing credentials or content."""

import argparse
import json
from pathlib import Path

import httpx


def check(
    url: str, password_file: Path, scenario: str, expect_event: str | None = None, voice: bool = False
) -> dict[str, object]:
    password = password_file.read_text(encoding="utf-8").strip()
    if not password:
        raise ValueError("Password file is empty")
    with httpx.Client(base_url=url.rstrip("/"), timeout=60, follow_redirects=False) as client:
        for path in ("/health", "/ready"):
            response = client.get(path)
            response.raise_for_status()
        if client.get("/api/session").status_code != 401:
            raise RuntimeError("Public demo accepted an anonymous session")

        response = client.post("/api/auth/login", json={"password": password})
        response.raise_for_status()
        cookie = response.headers.get("set-cookie", "").lower()
        if "secure" not in cookie or "httponly" not in cookie:
            raise RuntimeError("Session cookie lacks Secure or HttpOnly")
        session = response.json()
        if session.get("mode") != "demo":
            raise RuntimeError("Target is not a demo workspace")
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        if expect_event:
            response = client.get(f"/api/events/{expect_event}")
            response.raise_for_status()
            if response.json().get("status") != "resolved":
                raise RuntimeError("Earlier resolved event did not survive restart")

        response = client.post("/api/demo/run", json={"scenario": scenario})
        response.raise_for_status()
        event = response.json()
        actions = event.get("actions", [])
        if not actions:
            raise RuntimeError("Demo produced no actions")
        response = client.post(
            f"/api/events/{event['id']}/approve",
            json={
                "version": event["version"],
                "action_ids": [action["id"] for action in actions if action["requires_approval"]],
            },
        )
        response.raise_for_status()
        response = client.post(f"/api/events/{event['id']}/execute")
        response.raise_for_status()
        executed = response.json()
        if executed.get("status") != "resolved" or not all(
            action.get("evidence", {}).get("verified") for action in executed.get("actions", [])
        ):
            raise RuntimeError("Demo did not resolve with verified evidence")
        response = client.get(f"/api/events/{event['id']}")
        response.raise_for_status()
        if response.json().get("status") != "resolved":
            raise RuntimeError("Resolved event did not persist")
        response = client.get("/api/audit/verify")
        response.raise_for_status()
        if not response.json().get("valid"):
            raise RuntimeError("Audit chain verification failed")
        if voice:
            if not session.get("voice_available"):
                raise RuntimeError("Voice is not enabled on the target")
            response = client.post("/api/voice/speak", json={"text": "LIFEOS voice verification."})
            response.raise_for_status()
            if not response.content or "audio" not in response.headers.get("content-type", ""):
                raise RuntimeError("Speech synthesis returned no audio")
            response = client.post(
                "/api/voice/transcribe",
                files={"audio": ("voice-check.mp3", response.content, "audio/mpeg")},
            )
            response.raise_for_status()
            if "voice" not in response.json().get("text", "").lower():
                raise RuntimeError("Speech transcription did not recognize the generated sample")
        return {
            "status": "passed",
            "scenario": scenario,
            "event_id": event["id"],
            "actions_verified": len(executed["actions"]),
            "voice_verified": voice,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--password-file", required=True, type=Path)
    parser.add_argument("--scenario", choices=("flight", "meeting"), default="flight")
    parser.add_argument("--expect-event", help="Previously resolved event ID that must survive a restart")
    parser.add_argument("--voice", action="store_true", help="Make one metered TTS and STT round trip")
    args = parser.parse_args()
    print(json.dumps(check(args.url, args.password_file, args.scenario, args.expect_event, args.voice)))


if __name__ == "__main__":
    main()
