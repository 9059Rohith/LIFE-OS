"""Small live OpenAI smoke test using synthetic content, never account data.

Makes three metered API requests: speech, transcription, structured extraction.
Writes only a status report; no keys, provider responses or speech files are logged.
"""

import asyncio
import json
from pathlib import Path

from dotenv import dotenv_values
from lifeos.ai import extract_event, speak, transcribe


async def main():
    values = dotenv_values(".env")
    key = values.get("LIFEOS_OPENAI_API_KEY", "")
    report = {}
    try:
        audio = await speak("My flight AI-742 on September fifteenth moved to six forty in the morning.", key)
        report["tts"] = {"status": "passed", "bytes": len(audio)}
    except Exception as exc:
        report["tts"] = {"status": "failed", "code": getattr(exc, "code", "NETWORK_ERROR")}
        audio = None
    if audio:
        try:
            transcript = await transcribe(audio, "synthetic.mp3", key)
            report["stt"] = {"status": "passed" if transcript.strip() else "failed"}
        except Exception as exc:
            report["stt"] = {"status": "failed", "code": getattr(exc, "code", "NETWORK_ERROR")}
    try:
        result = await extract_event(
            "My flight AI-742 on 2026-09-15 moved to 6:40 AM.",
            key,
            values.get("LIFEOS_OPENAI_MODEL") or "gpt-4.1-mini",
            "Asia/Kolkata",
        )
        correct = result.get("event_type") == "flight_change" and result.get("new_time") == "06:40"
        report["extraction"] = {"status": "passed" if correct else "unexpected_extraction"}
    except Exception as exc:
        report["extraction"] = {"status": "failed", "code": getattr(exc, "code", "NETWORK_ERROR")}
    Path(".private").mkdir(exist_ok=True)
    Path(".private/voice-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    asyncio.run(main())
