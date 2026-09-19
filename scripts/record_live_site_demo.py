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
FINAL_MP4 = DOWNLOADS / "LIFEOS_original_live_site_demo.mp4"
FINAL_SRT = DOWNLOADS / "LIFEOS_original_live_site_demo.srt"
FINAL_SCRIPT = DOWNLOADS / "LIFEOS_original_live_site_demo_script.md"
RAW_VIDEO_DIR = OUT_DIR / "recordings"
FULL_AUDIO = OUT_DIR / "live_narration.wav"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

WIDTH = 1920
HEIGHT = 1080

SCENES = [
    {
        "duration": 18.0,
        "subtitle": "We open the real hosted LIFEOS workspace and sign in to the live production site.",
        "narration": (
            "This is the real hosted LIFEOS workspace, opened from the production Railway URL. "
            "I am signing in to the private live workspace, not showing a mock storyboard."
        ),
    },
    {
        "duration": 26.0,
        "subtitle": "The command center shows a verified cross-app workflow and the dependency graph.",
        "narration": (
            "The overview starts with an actual completed workflow. A Calendar change was planned, approved, executed, "
            "read back from providers, and then compensated where the Calendar mutation was reversible."
        ),
    },
    {
        "duration": 30.0,
        "subtitle": "The graph connects Calendar, Discord, WhatsApp and verification evidence.",
        "narration": (
            "The consequence graph is the core product surface. It does not just chat about a change. It organizes "
            "the work into dependent actions, shows prerequisites, and keeps each action tied to evidence."
        ),
    },
    {
        "duration": 30.0,
        "subtitle": "The activity timeline proves the workflow moved from detection to verification.",
        "narration": (
            "The timeline shows the live lifecycle: detected, context loaded, planned, approved, executing, verified, "
            "resolved, and compensated. This is the audit path a reviewer can inspect."
        ),
    },
    {
        "duration": 26.0,
        "subtitle": "Audit trail entries expose provider receipts and evidence inspection.",
        "narration": (
            "The audit trail records decisions and provider receipts. LIFEOS keeps action history separate from the UI, "
            "so an evaluator can review what happened after the workflow is finished."
        ),
    },
    {
        "duration": 24.0,
        "subtitle": "Integrations show live boundaries, read checks and approval-protected writes.",
        "narration": (
            "The integrations page shows the safety boundary. Read checks can be refreshed without changing external "
            "accounts, while Calendar writes and messages remain approval protected."
        ),
    },
    {
        "duration": 22.0,
        "subtitle": "The work hub proves LIFEOS is a usable productivity workspace, not only a demo screen.",
        "narration": (
            "The My Work area adds the everyday productivity layer: tasks, projects, goals, habits, notes, and saved "
            "activity that persists in the live workspace."
        ),
    },
    {
        "duration": 24.0,
        "subtitle": "Settings document data control, retention and account boundaries.",
        "narration": (
            "Settings make the operating model explicit. The user controls preferences, retention, exports, Google "
            "disconnection, and workspace deletion without exposing provider secrets."
        ),
    },
    {
        "duration": 18.0,
        "subtitle": "Final view: a live, evidence-driven automation workspace for real consequences.",
        "narration": (
            "The result is a live automation product: human approval before mutation, provider read-back after execution, "
            "and an interface that makes the ripple of work understandable."
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
        .demo-live-redaction {
          filter: blur(5px);
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
        hold_until(scene_started, SCENES[0]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Overview", 1200)
        page.mouse.move(980, 424)
        page.wait_for_timeout(3500)
        scroll_to(page, 240, 1800)
        page.wait_for_timeout(2500)
        scroll_to(page, 0, 1500)
        hold_until(scene_started, SCENES[1]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Graph", 900)
        page.mouse.move(1165, 485)
        page.wait_for_timeout(4200)
        safe_click(page, "List", 1500)
        safe_click(page, "Graph", 1500)
        page.mouse.move(1275, 520)
        hold_until(scene_started, SCENES[2]["duration"])

        scene_started = time.monotonic()
        scroll_to(page, 520, 1800)
        page.mouse.move(1515, 616)
        page.wait_for_timeout(5500)
        scroll_to(page, 920, 1800)
        page.wait_for_timeout(5500)
        scroll_to(page, 1210, 1800)
        hold_until(scene_started, SCENES[3]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Audit trail", 1800)
        page.mouse.move(1540, 330)
        page.wait_for_timeout(5000)
        first_evidence = page.locator("button:has-text('Inspect evidence')").first
        if first_evidence.is_visible(timeout=3000):
            first_evidence.click()
            page.wait_for_timeout(5000)
            close = page.locator("button:has-text('Close'), button[aria-label*='close' i]").first
            if close.is_visible(timeout=1500):
                close.click()
                page.wait_for_timeout(1200)
            else:
                page.keyboard.press("Escape")
                page.wait_for_timeout(1200)
        hold_until(scene_started, SCENES[4]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Integrations", 1800)
        page.mouse.move(545, 430)
        page.wait_for_timeout(4500)
        check = page.locator("button:has-text('Check API access')").first
        if check.is_visible(timeout=3000):
            check.click()
            page.wait_for_timeout(5000)
        scroll_to(page, 520, 1500)
        hold_until(scene_started, SCENES[5]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "My work", 1600)
        page.mouse.move(1030, 460)
        page.wait_for_timeout(3500)
        for tab in ["Projects", "Goals", "Habits", "Notes", "Calendar", "Tasks"]:
            safe_click(page, tab, 950)
        hold_until(scene_started, SCENES[6]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Settings", 1600)
        page.mouse.move(918, 505)
        page.wait_for_timeout(3500)
        scroll_to(page, 560, 1500)
        page.wait_for_timeout(3500)
        scroll_to(page, 0, 1200)
        hold_until(scene_started, SCENES[7]["duration"])

        scene_started = time.monotonic()
        safe_click(page, "Overview", 1400)
        scroll_to(page, 0, 1200)
        page.mouse.move(1120, 430)
        page.wait_for_timeout(4000)
        hold_until(scene_started, SCENES[8]["duration"])

        context.close()
        browser.close()

    recordings = sorted(RAW_VIDEO_DIR.glob("*.webm"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not recordings:
        raise RuntimeError("No live site recording was created.")
    return recordings[0]


def mux_final(raw_video: Path) -> None:
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
