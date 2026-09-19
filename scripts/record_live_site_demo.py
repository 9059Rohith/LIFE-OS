from __future__ import annotations

import base64
import math
import os
import subprocess
import time
import wave
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "live_site_demo"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS = Path.home() / "Downloads"
DOWNLOADS.mkdir(parents=True, exist_ok=True)

LIVE_URL = "https://lifeos-live-production.up.railway.app"
FINAL_MP4 = DOWNLOADS / "LIFEOS_AUTHENTICATED_LIGHTMODE_DEMO_FINAL.mp4"
FINAL_SRT = DOWNLOADS / "LIFEOS_AUTHENTICATED_LIGHTMODE_DEMO.srt"
FINAL_SCRIPT = DOWNLOADS / "LIFEOS_AUTHENTICATED_LIGHTMODE_DEMO_SCRIPT.md"
FINAL_ASS = OUT_DIR / "authenticated-demo.ass"
RAW_VIDEO_DIR = OUT_DIR / "recordings"
FULL_AUDIO = OUT_DIR / "live_narration.wav"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

WIDTH = 1920
HEIGHT = 1080

SCENES = [
    {
        "duration": 24.0,
        "subtitle": "We sign in to the real LIFEOS workspace, switch to light mode, and begin with the user's intent.",
        "narration": (
            "This is the authenticated LIFEOS workspace in light mode. The problem is simple but costly: one change in a schedule "
            "creates a chain of manual updates across email, Calendar, team chat, and personal messages. LIFEOS turns that intent "
            "into a visible, approval-bound workflow."
        ),
    },
    {
        "duration": 24.0,
        "subtitle": "Real authenticated provider surfaces: Gmail, Calendar, Discord, WhatsApp, and Drive.",
        "narration": (
            "Here are the real connected application surfaces behind the workflow: Gmail for source context, Google Calendar for time, "
            "Discord and WhatsApp for communication, and Drive for supporting files. This is the authenticated product interface; "
            "sensitive account content is redacted in the recording, and no message or calendar change is sent during capture."
        ),
    },
    {
        "duration": 24.0,
        "subtitle": "The overview turns one change into a consequence graph with dependencies.",
        "narration": (
            "The research direction was human-in-the-loop orchestration: make consequences understandable before autonomy is allowed. "
            "The overview gathers context, lays out dependent actions, and shows what is waiting for approval, what is running, and "
            "what has already been verified."
        ),
    },
    {
        "duration": 24.0,
        "subtitle": "Action review exposes the exact target, risk, arguments, and reversibility.",
        "narration": (
            "Before a high-impact action runs, the user can inspect the exact target, arguments, risk, and reversibility. "
            "This is the core safety decision: AI can help interpret and plan, but the server constructs the action and the person "
            "approves the exact content."
        ),
    },
    {
        "duration": 24.0,
        "subtitle": "Execution moves through approved, executing, verified, and resolved states.",
        "narration": (
            "Once approved, the workflow is bounded by provider allowlists, idempotency, retries, and read-back verification. "
            "A successful request is not treated as proof. Each node changes state, and the final result is resolved only when the "
            "evidence supports it."
        ),
    },
    {
        "duration": 24.0,
        "subtitle": "The connected application record keeps the context behind every action inspectable.",
        "narration": (
            "The connected application view keeps the source context visible after planning: mail, messages, events, and files are "
            "organized around the same consequence flow. That makes the product more than a chatbot; it is a workspace for reliable "
            "coordination."
        ),
    },
    {
        "duration": 24.0,
        "subtitle": "My Work and Calendar connect automation to the work that follows.",
        "narration": (
            "The productivity layer continues after execution. My Work brings together tasks, projects, goals, habits, notes, and "
            "Calendar context, so the outcome does not disappear when the automation finishes. The work remains visible and actionable."
        ),
    },
    {
        "duration": 24.0,
        "subtitle": "Integrations make provider permissions and connection boundaries explicit.",
        "narration": (
            "The integrations page makes the boundary honest. It distinguishes configured access from verified access, reports provider "
            "health, and keeps writes approval protected. This reflects the engineering research behind LIFEOS: permissions, failures, "
            "and uncertainty must be visible instead of hidden behind a success animation."
        ),
    },
    {
        "duration": 24.0,
        "subtitle": "Audit Trail preserves approvals, attempts, receipts, and verification evidence.",
        "narration": (
            "Every decision leaves an audit trail. Approvals, execution attempts, provider receipts, verification, and recovery states "
            "remain inspectable. This is the reliability layer that turns an impressive workflow animation into an accountable system."
        ),
    },
    {
        "duration": 24.0,
        "subtitle": "Settings and the final overview show a complete, controlled productivity operating system.",
        "narration": (
            "Finally, Settings exposes retention, export, connection, and deletion controls before we return to the complete overview. "
            "The result is a consequence-aware operating system: understand the change, plan the ripple, approve the next move, execute "
            "within bounds, and verify what actually happened."
        ),
    },
]


def load_auth_password() -> str:
    if os.environ.get("LIFEOS_AUTH_PASSWORD"):
        return os.environ["LIFEOS_AUTH_PASSWORD"]
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("LIFEOS_AUTH_PASSWORD="):
                return line.split("=", 1)[1].strip().strip("\"'")
    raise RuntimeError("Set LIFEOS_AUTH_PASSWORD in the environment or local .env file before recording.")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, **kwargs)


def format_srt_time(seconds: float) -> str:
    millis = int(round((seconds - math.floor(seconds)) * 1000))
    whole = int(math.floor(seconds))
    mins, secs = divmod(whole, 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def format_ass_time(seconds: float) -> str:
    whole = int(seconds)
    centis = int(round((seconds - whole) * 100))
    if centis == 100:
        whole += 1
        centis = 0
    mins, secs = divmod(whole, 60)
    hours, mins = divmod(mins, 60)
    return f"{hours}:{mins:02d}:{secs:02d}.{centis:02d}"


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / float(audio.getframerate())


def make_voice(scene_index: int, text: str) -> Path:
    wav = OUT_DIR / f"live_voice_{scene_index:02d}.wav"
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    ps = f"""
$bytes = [Convert]::FromBase64String('{encoded}')
$text = [Text.Encoding]::UTF8.GetString($bytes)
$voice = New-Object -ComObject SAPI.SpVoice
$format = New-Object -ComObject SAPI.SpAudioFormat
$format.Type = 39
$stream = New-Object -ComObject SAPI.SpFileStream
$stream.Format = $format
$stream.Open('{str(wav).replace("'", "''")}', 3, $false)
$voice.AudioOutputStream = $stream
$voice.Rate = -1
$voice.Volume = 100
[void]$voice.Speak($text)
$stream.Close()
"""
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps])
    return wav


def build_audio_and_srt() -> None:
    parts: list[Path] = []
    srt_entries: list[str] = []
    script_lines = [
        "# LIFEOS Original Live Site Demo Script",
        "",
        f"Recorded URL: {LIVE_URL}",
        "",
    ]
    cursor = 0.0
    for index, scene in enumerate(SCENES, start=1):
        voice = make_voice(index, scene["narration"])
        voice_duration = wav_duration(voice)
        duration = scene["duration"]
        padded = OUT_DIR / f"live_scene_{index:02d}.wav"
        if voice_duration < duration:
            silence = OUT_DIR / f"live_silence_{index:02d}.wav"
            run(
                [
                    FFMPEG,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-t",
                    f"{duration - voice_duration:.3f}",
                    str(silence),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            concat = OUT_DIR / f"live_audio_list_{index:02d}.txt"
            concat.write_text(
                f"file '{voice.as_posix()}'\nfile '{silence.as_posix()}'\n",
                encoding="utf-8",
            )
            run(
                [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(padded)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            run(
                [FFMPEG, "-y", "-i", str(voice), "-t", f"{duration:.3f}", str(padded)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        parts.append(padded)
        start = cursor
        end = cursor + duration
        srt_entries.append(
            f"{index}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{scene['subtitle']}\n"
        )
        script_lines.extend(
            [
                f"## Scene {index} ({format_srt_time(start)} - {format_srt_time(end)})",
                "",
                f"Subtitle: {scene['subtitle']}",
                "",
                f"Narration: {scene['narration']}",
                "",
            ]
        )
        cursor = end

    audio_list = OUT_DIR / "live_audio_list.txt"
    audio_list.write_text("".join(f"file '{part.as_posix()}'\n" for part in parts), encoding="utf-8")
    run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(audio_list), "-c", "copy", str(FULL_AUDIO)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    FINAL_SRT.write_text("\n".join(srt_entries), encoding="utf-8")
    FINAL_SCRIPT.write_text("\n".join(script_lines), encoding="utf-8")
    ass_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Subtitle,Arial,28,&H00FFFFFF,&H00FFFFFF,&HAA07140F,&HAA07140F,0,0,0,0,100,100,0,0,1,2,0,2,80,80,42,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    cursor = 0.0
    for scene in SCENES:
        start = format_ass_time(cursor)
        cursor += scene["duration"]
        end = format_ass_time(cursor)
        text = scene["subtitle"].replace("{", "(").replace("}", ")")
        ass_lines.append(f"Dialogue: 0,{start},{end},Subtitle,,0,0,0,,{{\\fad(220,180)}}{text}")
    FINAL_ASS.write_text("\n".join(ass_lines), encoding="utf-8")


def safe_click(page: Page, label: str, wait_ms: int = 1200) -> None:
    loc = page.locator(f"button:has-text('{label}'), a:has-text('{label}')").first
    if loc.is_visible(timeout=3000):
        loc.click()
        page.wait_for_timeout(wait_ms)


def scroll_to(page: Page, y: int, wait_ms: int = 1000) -> None:
    page.evaluate("(targetY) => window.scrollTo({ top: targetY, behavior: 'smooth' })", y)
    page.wait_for_timeout(wait_ms)


def hold_until(start: float, duration: float) -> None:
    remaining = duration - (time.monotonic() - start)
    if remaining > 0:
        time.sleep(remaining)


def prepare_page(page: Page) -> None:
    page.add_style_tag(
        content="""
        * { scroll-behavior: smooth !important; }
        input[type='password'] { font-family: password, sans-serif !important; }
        .unified-discord-message,
        .unified-gmail-row,
        .unified-gmail-detail,
        .unified-whatsapp-bubble,
        .unified-calendar-row,
        .unified-drive-row,
        .unified-provider-heading small,
        .unified-impact-action small {
          filter: blur(7px);
        }
        """
    )


def login(page: Page) -> None:
    page.goto(LIVE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)
    prepare_page(page)
    if page.locator("input[type='password']").first.is_visible(timeout=5000):
        page.locator("input[type='password']").first.fill(load_auth_password())
        page.wait_for_timeout(600)
        page.locator("button:has-text('Open workspace')").first.click()
        page.wait_for_timeout(3500)
    light_mode = page.get_by_role("button", name="Light mode")
    if light_mode.is_visible(timeout=3000):
        light_mode.click()
        page.wait_for_timeout(1800)


def record_live_site() -> Path:
    RAW_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    for old in RAW_VIDEO_DIR.glob("*.webm"):
        old.unlink()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            record_video_dir=str(RAW_VIDEO_DIR),
            record_video_size={"width": WIDTH, "height": HEIGHT},
        )
        page = context.new_page()

        scene_started = time.monotonic()
        login(page)
        safe_click(page, "Overview", 1400)
        prompt = page.locator("textarea").first
        if prompt.is_visible(timeout=3000):
            prompt.fill("A flight moved to 06:40. Coordinate the approved updates across my connected apps.")
        page.mouse.move(1110, 790)
        page.wait_for_timeout(4500)
        hold_until(scene_started, SCENES[0]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Connected apps", 1800)
        page.get_by_label("Gmail screen").wait_for(timeout=15000)
        page.mouse.move(1500, 235)
        scroll_to(page, 430, 1800)
        page.mouse.move(1510, 540)
        scroll_to(page, 870, 1800)
        page.mouse.move(1110, 870)
        scroll_to(page, 0, 1600)
        hold_until(scene_started, SCENES[1]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Overview", 1600)
        safe_click(page, "Graph", 900)
        page.mouse.move(1165, 485)
        page.wait_for_timeout(3800)
        safe_click(page, "List", 1300)
        safe_click(page, "Graph", 1300)
        page.mouse.move(1275, 520)
        scroll_to(page, 360, 1600)
        hold_until(scene_started, SCENES[2]["duration"])

        scene_started = time.monotonic()
        review = page.locator("button:has-text('Review')").first
        if review.is_visible(timeout=3000):
            review.click()
            page.wait_for_timeout(5000)
            page.mouse.move(1130, 575)
            page.wait_for_timeout(4500)
            page.keyboard.press("Escape")
            page.wait_for_timeout(1200)
        else:
            page.mouse.move(1420, 890)
        hold_until(scene_started, SCENES[3]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Overview", 1300)
        scroll_to(page, 520, 1600)
        page.mouse.move(1515, 616)
        page.wait_for_timeout(4000)
        scroll_to(page, 920, 1600)
        page.mouse.move(1290, 830)
        page.wait_for_timeout(4200)
        scroll_to(page, 0, 1500)
        hold_until(scene_started, SCENES[4]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Connected apps", 1500)
        page.mouse.move(1340, 720)
        scroll_to(page, 520, 1700)
        page.mouse.move(720, 700)
        scroll_to(page, 0, 1500)
        page.mouse.move(1640, 246)
        hold_until(scene_started, SCENES[5]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "My work", 1600)
        page.mouse.move(1030, 460)
        page.wait_for_timeout(3200)
        for tab in ["Projects", "Goals", "Habits", "Notes", "Calendar", "Tasks"]:
            safe_click(page, tab, 850)
        page.mouse.move(1120, 700)
        hold_until(scene_started, SCENES[6]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Integrations", 1600)
        page.mouse.move(545, 430)
        page.wait_for_timeout(4200)
        check = page.locator("button:has-text('Check API access')").first
        if check.is_visible(timeout=3000):
            check.click()
            page.wait_for_timeout(5000)
        scroll_to(page, 520, 1500)
        page.mouse.move(1210, 690)
        hold_until(scene_started, SCENES[7]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Audit trail", 1800)
        page.mouse.move(1540, 330)
        page.wait_for_timeout(4500)
        first_evidence = page.locator("button:has-text('Inspect evidence')").first
        if first_evidence.is_visible(timeout=3000):
            first_evidence.click()
            page.wait_for_timeout(4500)
            page.mouse.move(1120, 640)
            page.keyboard.press("Escape")
            page.wait_for_timeout(1200)
        hold_until(scene_started, SCENES[8]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Settings", 1600)
        page.mouse.move(918, 505)
        page.wait_for_timeout(3200)
        scroll_to(page, 560, 1500)
        page.mouse.move(1370, 660)
        page.wait_for_timeout(3500)
        safe_click(page, "Overview", 1400)
        scroll_to(page, 0, 1200)
        page.mouse.move(1120, 430)
        page.wait_for_timeout(3500)
        hold_until(scene_started, SCENES[9]["duration"])

        context.close()
        browser.close()

    recordings = sorted(RAW_VIDEO_DIR.glob("*.webm"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not recordings:
        raise RuntimeError("No live site recording was created.")
    return recordings[0]


def mux_final(raw_video: Path) -> None:
    ass_path = FINAL_ASS.relative_to(ROOT).as_posix()
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(raw_video),
            "-i",
            str(FULL_AUDIO),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-t",
            f"{wav_duration(FULL_AUDIO):.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            f"subtitles=filename='{ass_path}'",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(FINAL_MP4),
        ]
    )


def main() -> None:
    print("Generating narration and SRT...")
    build_audio_and_srt()
    print("Recording original live website...")
    raw_video = record_live_site()
    print(f"Raw live capture: {raw_video}")
    print("Muxing final MP4...")
    mux_final(raw_video)
    print(f"Video: {FINAL_MP4}")
    print(f"Subtitles: {FINAL_SRT}")
    print(f"Script: {FINAL_SCRIPT}")


if __name__ == "__main__":
    main()
