from __future__ import annotations

import base64
import math
import os
import subprocess
import time
import wave
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import Page, Route, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "balanced_submission_demo"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS = Path.home() / "Downloads"
DOWNLOADS.mkdir(parents=True, exist_ok=True)
BASE_URL = os.environ.get("LIFEOS_CAPTURE_URL", "http://127.0.0.1:5175")
FINAL_MP4 = DOWNLOADS / "LIFEOS_BALANCED_2M30_HACKATHON_DEMO_FINAL.mp4"
FINAL_SRT = DOWNLOADS / "LIFEOS_BALANCED_2M30_HACKATHON_DEMO.srt"
FINAL_SCRIPT = DOWNLOADS / "LIFEOS_BALANCED_2M30_HACKATHON_DEMO_SCRIPT.md"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
WIDTH = 1920
HEIGHT = 1080
SCENE_SECONDS = 15.0

SCENES = [
    (
        "01 Overview: the problem",
        "A schedule change should not become a manual coordination mess. LIFEOS starts with the real problem: one change creates consequences across Calendar, email, team chat, and personal messages. Research into workflow automation and human-in-the-loop systems led to one design rule: make every consequence visible before anything acts.",
        "One change should not create ten manual handoffs.",
    ),
    (
        "02 Connected provider screens",
        "Here are the application surfaces LIFEOS coordinates: Gmail and Calendar for source context, Discord and WhatsApp for communication, and Drive for supporting information. These provider screens are rendered through the isolated demo boundary, so the recording shows the real product interface without touching a personal account.",
        "Gmail  |  Calendar  |  Discord  |  WhatsApp  |  Drive",
    ),
    (
        "03 Workflow plan",
        "The solution is an executable consequence graph. LIFEOS gathers context, creates typed dependencies, and makes the order of work understandable. The graph is more than a chatbot response: it is a plan that can be reviewed, approved, executed, and verified.",
        "Intent -> context -> dependencies -> execution",
    ),
    (
        "04 Action review",
        "Before a high-impact action can run, the user sees the exact target, arguments, risk, reversibility, and approval binding. This is where the research becomes product behavior: autonomy is useful only when the human can understand and control the next move.",
        "Exact arguments. Explicit approval. No hidden mutation.",
    ),
    (
        "05 Execution and verification",
        "After approval, the workflow runs through bounded provider operations. Each node changes state, dependencies are respected, and the result is read back independently. The final state is resolved only when the evidence supports it, not merely because a write request returned successfully.",
        "Approved -> executing -> read-back verified -> resolved",
    ),
    (
        "06 Application records",
        "The application record view preserves the provider context behind the plan. Gmail messages, Calendar events, Discord threads, WhatsApp conversations, and Drive files remain inspectable in one place, while demo mode keeps every record isolated from personal accounts.",
        "The context behind the plan stays inspectable.",
    ),
    (
        "07 My Work and Calendar",
        "LIFEOS also handles the daily work around the automation: tasks, projects, goals, habits, notes, reminders, and dates. This matters because productivity is not only sending an action; it is keeping the resulting work visible after the workflow finishes.",
        "Automation connects to the work that follows.",
    ),
    (
        "08 Integrations",
        "The integrations page makes boundaries explicit. It distinguishes local demo records from connected services, reports availability, and keeps monitoring and provider permissions visible. Unavailable services are shown as unavailable rather than being presented as completed work.",
        "Clear boundaries. Honest connection states.",
    ),
    (
        "09 Audit Trail",
        "Every decision has a durable trail: approvals, attempts, receipts, verification, uncertainty, and recovery. This gives judges and users a way to inspect what happened after the animation ends, which is the reliability layer most automation demos leave out.",
        "A finished workflow should leave evidence, not mystery.",
    ),
    (
        "10 Settings and final proof",
        "Finally, the workspace exposes retention, export, connection, and deletion controls. The result is a consequence-aware operating system: it turns a change into a controlled workflow, keeps the human in charge, and makes the final outcome understandable across every connected surface.",
        "LIFEOS: plan, approve, execute, verify, move forward.",
    ),
]


def run(command: list[str], **kwargs) -> None:
    subprocess.run(command, check=True, **kwargs)


def srt_time(seconds: float) -> str:
    millis = int(round((seconds - math.floor(seconds)) * 1000))
    whole = int(math.floor(seconds))
    minutes, secs = divmod(whole, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / float(handle.getframerate())


def voice(index: int, text: str) -> Path:
    output = OUT_DIR / f"voice-{index:02d}.wav"
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    escaped = str(output).replace("'", "''")
    command = f"""
$bytes = [Convert]::FromBase64String('{encoded}')
$text = [Text.Encoding]::UTF8.GetString($bytes)
$speaker = New-Object -ComObject SAPI.SpVoice
$format = New-Object -ComObject SAPI.SpAudioFormat
$format.Type = 39
$stream = New-Object -ComObject SAPI.SpFileStream
$stream.Format = $format
$stream.Open('{escaped}', 3, $false)
$speaker.AudioOutputStream = $stream
$speaker.Rate = -1
$speaker.Volume = 100
[void]$speaker.Speak($text)
$stream.Close()
"""
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], capture_output=True)
    return output


def build_audio() -> None:
    parts: list[Path] = []
    subtitles: list[str] = []
    script: list[str] = [
        "# LIFEOS Balanced Hackathon Demo",
        "",
        "Duration: exactly 2 minutes 30 seconds.",
        "",
        "The provider-screen chapter uses the shipped Connected Apps interface with isolated demo records. It does not claim to send personal messages or change a personal calendar.",
        "",
    ]
    cursor = 0.0
    for index, (title, narration, caption) in enumerate(SCENES, start=1):
        raw = voice(index, narration)
        padded = OUT_DIR / f"scene-{index:02d}.wav"
        run(
            [
                FFMPEG,
                "-y",
                "-i",
                str(raw),
                "-af",
                "apad",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-t",
                f"{SCENE_SECONDS:.3f}",
                str(padded),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        parts.append(padded)
        subtitles.append(
            f"{index}\n{srt_time(cursor)} --> {srt_time(cursor + SCENE_SECONDS)}\n{narration}\n"
        )
        script.extend(
            [
                f"## {title}",
                "",
                f"Time: {srt_time(cursor)} - {srt_time(cursor + SCENE_SECONDS)}",
                "",
                f"Narration: {narration}",
                "",
                f"On screen: {caption}",
                "",
            ]
        )
        cursor += SCENE_SECONDS

    concat = OUT_DIR / "voice-concat.txt"
    concat.write_text("".join(f"file '{part.as_posix()}'\n" for part in parts), encoding="utf-8")
    voice_track = OUT_DIR / "voice-track.wav"
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(voice_track)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mixed = OUT_DIR / "narration-with-bed.wav"
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(voice_track),
            "-f",
            "lavfi",
            "-t",
            "150",
            "-i",
            "sine=frequency=196:sample_rate=48000",
            "-filter_complex",
            "[1:a]volume=0.018[bed];[0:a][bed]amix=inputs=2:duration=first:normalize=0[a]",
            "-map",
            "[a]",
            str(mixed),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    full_audio = OUT_DIR / "full-audio.wav"
    run([FFMPEG, "-y", "-i", str(mixed), "-ar", "48000", "-ac", "2", str(full_audio)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    FINAL_SRT.write_text("\n".join(subtitles), encoding="utf-8")
    FINAL_SCRIPT.write_text("\n".join(script), encoding="utf-8")


def move(page: Page, x: float, y: float) -> None:
    page.mouse.move(x, y, steps=12)


def click(page: Page, text: str, wait: int = 450) -> bool:
    target = page.get_by_role("button", name=text, exact=True).first
    if not target.is_visible(timeout=2500):
        target = page.get_by_text(text, exact=True).first
    if not target.is_visible(timeout=2500):
        return False
    target.click()
    page.wait_for_timeout(wait)
    return True


def hold(start: float) -> None:
    remaining = SCENE_SECONDS - (time.monotonic() - start)
    if remaining > 0:
        time.sleep(remaining)


def provider_event() -> dict[str, object]:
    return {
        "id": "provider-demo-event",
        "title": "Flight AI-742 moved to 06:40",
        "event_type": "flight_change",
        "source": "gmail",
        "status": "awaiting_approval",
        "created_at": "2026-09-20T10:00:00Z",
        "version": 1,
        "summary": "A flight change needs coordinated updates.",
        "simulation": False,
        "entities": {},
        "context": [],
        "timeline": [],
        "actions": [
            {"id": "calendar-action", "application": "calendar", "type": "update", "title": "Move the calendar event", "reason": "The flight time changed.", "target": "trip-calendar", "arguments": {}, "risk": "medium", "status": "verified", "requires_approval": True, "reversible": True, "dependencies": [], "evidence": {}, "error": None, "arguments_hash": "demo-calendar"},
            {"id": "discord-action", "application": "discord", "type": "send", "title": "Notify the project channel", "reason": "The team needs the updated schedule.", "target": "#travel", "arguments": {}, "risk": "medium", "status": "verified", "requires_approval": True, "reversible": False, "dependencies": ["calendar-action"], "evidence": {}, "error": None, "arguments_hash": "demo-discord"},
            {"id": "whatsapp-action", "application": "whatsapp", "type": "send", "title": "Send a personal update", "reason": "The traveler needs the new time.", "target": "trip-thread", "arguments": {}, "risk": "medium", "status": "verified", "requires_approval": True, "reversible": False, "dependencies": ["calendar-action"], "evidence": {}, "error": None, "arguments_hash": "demo-whatsapp"},
        ],
    }


def install_provider_mock(page: Page) -> list[str]:
    patterns = ["**/api/session", "**/api/events", "**/api/integrations", "**/api/apps/**"]
    event = provider_event()
    integrations = [
        {"id": name, "name": label, "status": "read_access_verified", "mode": "demo", "description": "Isolated provider-screen record for this recording."}
        for name, label in [("gmail", "Gmail"), ("calendar", "Google Calendar"), ("discord", "Discord"), ("whatsapp", "WhatsApp"), ("drive", "Google Drive")]
    ]
    screens = {
        "gmail": {"application": "gmail", "title": "Inbox", "items": [{"id": "mail-1", "from": "travel@example.com", "subject": "Flight AI-742 schedule update", "preview": "Departure moved to 06:40.", "date": "2026-09-20T08:40:00Z", "unread": True}]},
        "calendar": {"application": "calendar", "title": "Trip calendar", "items": [{"id": "cal-1", "title": "Flight AI-742", "start": "2026-09-20T06:40:00+05:30", "end": "2026-09-20T08:40:00+05:30", "etag": "demo", "location": "Bengaluru to Delhi"}]},
        "discord": {"application": "discord", "title": "#travel", "items": [{"id": "discord-1", "author": "Travel Ops", "content": "Flight AI-742 moved to 06:40.", "date": "2026-09-20T08:42:00Z"}]},
        "whatsapp": {"application": "whatsapp", "title": "Trip thread", "items": [{"id": "wa-1", "content": "AI-742 is now at 06:40. I will update the plan.", "date": "2026-09-20T08:43:00Z", "outgoing": True, "status": "verified"}]},
        "drive": {"application": "drive", "title": "Recent files", "items": [{"id": "drive-1", "name": "AI-742 itinerary.pdf", "modified": "2026-09-20T08:20:00Z"}]},
    }

    def handler(route: Route) -> None:
        url = route.request.url
        if url.endswith("/api/session"):
            route.fulfill(json={"user": {"id": "owner", "name": "Demo owner"}, "csrf_token": "provider-demo", "mode": "live", "voice_available": False})
        elif url.endswith("/api/events"):
            route.fulfill(json=[event])
        elif url.endswith("/api/integrations"):
            route.fulfill(json=integrations)
        elif "/api/apps/gmail/mail-1" in url:
            route.fulfill(json={"id": "mail-1", "subject": "Flight AI-742 schedule update", "from": "travel@example.com", "date": "2026-09-20T08:40:00Z", "body": "The departure is now 06:40. Please update the connected plan."})
        else:
            name = url.rstrip("/").split("/")[-1]
            route.fulfill(json=screens.get(name, {"application": name, "title": name, "items": []}))

    for pattern in patterns:
        page.route(pattern, handler)
    return patterns


def record_video() -> Path:
    video_dir = OUT_DIR / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    for old in video_dir.glob("*.webm"):
        old.unlink()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": WIDTH, "height": HEIGHT}, record_video_dir=str(video_dir), record_video_size={"width": WIDTH, "height": HEIGHT})
        page = context.new_page()
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.get_by_role("heading", name="Something changed. You’re in control.").wait_for(timeout=30000)

        started = time.monotonic()
        move(page, 940, 340)
        page.wait_for_timeout(900)
        move(page, 1325, 65)
        page.wait_for_timeout(700)
        click(page, "Run hero demo", 1200)
        move(page, 980, 440)
        hold(started)

        started = time.monotonic()
        patterns = install_provider_mock(page)
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.get_by_role("button", name="Connected apps", exact=True).wait_for(timeout=30000)
        click(page, "Connected apps", 1000)
        page.get_by_label("Gmail screen").wait_for(timeout=15000)
        for y in (350, 820, 1220):
            page.evaluate("(target) => window.scrollTo({top: target, behavior: 'smooth'})", y)
            move(page, 1380, min(930, 350 + y / 2))
            page.wait_for_timeout(1100)
        hold(started)
        for pattern in patterns:
            page.unroute(pattern)

        started = time.monotonic()
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.get_by_role("heading", name="Something changed. You’re in control.").wait_for(timeout=30000)
        move(page, 1020, 360)
        page.wait_for_timeout(700)
        click(page, "Overview", 500)
        click(page, "Graph", 500)
        move(page, 820, 470)
        click(page, "List", 600)
        click(page, "Graph", 600)
        hold(started)

        started = time.monotonic()
        click(page, "Review", 600)
        page.get_by_role("dialog").wait_for(timeout=10000)
        move(page, 1120, 690)
        page.wait_for_timeout(900)
        page.keyboard.press("Escape")
        move(page, 940, 720)
        hold(started)

        started = time.monotonic()
        click(page, "Approve all (3)", 800)
        click(page, "Execute approved", 900)
        page.get_by_role("heading", name="Every action accounted for.").wait_for(timeout=20000)
        move(page, 1120, 830)
        page.wait_for_timeout(900)
        hold(started)

        started = time.monotonic()
        click(page, "Demo applications", 600)
        page.get_by_role("heading", name="Inside the demo applications.").wait_for(timeout=10000)
        page.locator(".app-records .panel").first.wait_for(timeout=10000)
        for summary in ("Schedule change - AI-742", "Acme proposal review", "pickup-thread"):
            item = page.get_by_text(summary, exact=True).first
            if item.is_visible(timeout=1200):
                item.click()
                page.wait_for_timeout(500)
        move(page, 1100, 520)
        hold(started)

        started = time.monotonic()
        click(page, "My work", 600)
        page.get_by_role("heading", name="Your work, connected.").wait_for(timeout=10000)
        for tab in ("Projects", "Goals", "Tasks", "Calendar"):
            target = page.get_by_role("tab", name=tab, exact=True)
            if target.is_visible(timeout=1500):
                target.click()
                page.wait_for_timeout(650)
        move(page, 1150, 520)
        hold(started)

        started = time.monotonic()
        click(page, "Integrations", 600)
        page.get_by_role("heading", name="Your connected world.").wait_for(timeout=10000)
        page.locator(".integration-list .integration-row").first.wait_for(timeout=10000)
        page.evaluate("window.scrollTo({top: 440, behavior: 'smooth'})")
        move(page, 1040, 640)
        page.wait_for_timeout(1000)
        hold(started)

        started = time.monotonic()
        click(page, "Audit trail", 600)
        page.get_by_role("heading", name="A record of every decision.").wait_for(timeout=10000)
        page.locator(".audit-table").wait_for(timeout=10000)
        move(page, 1180, 410)
        page.wait_for_timeout(900)
        hold(started)

        started = time.monotonic()
        click(page, "Settings", 600)
        page.get_by_label("Display name").wait_for(timeout=10000)
        page.evaluate("window.scrollTo({top: 470, behavior: 'smooth'})")
        move(page, 780, 690)
        page.wait_for_timeout(1000)
        page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        click(page, "Overview", 700)
        move(page, 1120, 430)
        hold(started)

        context.close()
        browser.close()
    recordings = sorted(video_dir.glob("*.webm"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not recordings:
        raise RuntimeError("Playwright did not create a recording.")
    return recordings[0]


def mux(raw: Path) -> None:
    audio = OUT_DIR / "full-audio.wav"
    run(
        [
            FFMPEG,
            "-y",
            "-ss",
            "8",
            "-i",
            str(raw),
            "-i",
            str(audio),
            "-f",
            "srt",
            "-i",
            str(FINAL_SRT),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-map",
            "2:0",
            "-t",
            "150",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "tpad=stop_mode=clone:stop_duration=1",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=eng",
            "-metadata:s:s:0",
            "title=English subtitles",
            "-movflags",
            "+faststart",
            str(FINAL_MP4),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    print("Building narration, subtitles, and script...")
    build_audio()
    print("Recording balanced UI walkthrough...")
    raw = record_video()
    print(f"Raw recording: {raw}")
    print("Muxing HD MP4 with embedded subtitles...")
    mux(raw)
    print(f"Video: {FINAL_MP4}")
    print(f"Subtitles: {FINAL_SRT}")
    print(f"Script: {FINAL_SCRIPT}")


if __name__ == "__main__":
    main()
