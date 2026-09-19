from __future__ import annotations

import base64
import json
import math
import subprocess
import time
import wave
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "top1_demo"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS = Path.home() / "Downloads"
DOWNLOADS.mkdir(parents=True, exist_ok=True)

FINAL_MP4 = DOWNLOADS / "LIFEOS_top1_hackathon_demo.mp4"
FINAL_SRT = DOWNLOADS / "LIFEOS_top1_hackathon_demo.srt"
FINAL_SCRIPT = DOWNLOADS / "LIFEOS_top1_hackathon_demo_script.md"
HTML_FILE = OUT_DIR / "storyboard.html"
FULL_AUDIO = OUT_DIR / "narration.wav"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

WIDTH = 1920
HEIGHT = 1080


SCENES = [
    {
        "key": "problem",
        "duration": 18.0,
        "title": "One change. Dozens of consequences.",
        "caption": "A schedule change should not become a manual coordination mess.",
        "narration": (
            "A single changed meeting can ripple through a whole workday. Calendar needs to move, teammates need updates, "
            "a client needs a clear message, and every action needs proof."
        ),
    },
    {
        "key": "product",
        "duration": 22.0,
        "title": "LIFEOS turns change into an executable workflow.",
        "caption": "Intent becomes context, approval, execution, read-back, and audit evidence.",
        "narration": (
            "LIFEOS is a workflow automation workspace for consequence management. It turns an event into a reviewed plan, "
            "executes only approved actions, and verifies outcomes with provider read-back."
        ),
    },
    {
        "key": "graph",
        "duration": 28.0,
        "title": "Animated workflow graph",
        "caption": "Source -> planner -> policy -> Calendar -> Discord -> WhatsApp -> audit.",
        "narration": (
            "This demo visualization shows the core workflow as a node graph. The planner reads context, policy gates risky "
            "actions, and downstream notifications wait until Calendar is verified."
        ),
    },
    {
        "key": "approval",
        "duration": 28.0,
        "title": "Human approval before real-world action",
        "caption": "Every mutation is previewed, hashed, version-bound, and explicitly approved.",
        "narration": (
            "High impact actions are never automatic. LIFEOS shows the exact arguments, binds approval to the plan version, "
            "and blocks execution if the event changes before delivery."
        ),
    },
    {
        "key": "execution",
        "duration": 34.0,
        "title": "Ripple execution, n8n-style",
        "caption": "Each node pulses through pending, executing, verified, or manual review.",
        "narration": (
            "During execution the ripple moves across the graph. Calendar verifies first, then Discord and WhatsApp deliver "
            "messages, and the system records read-back evidence instead of trusting a write response alone."
        ),
    },
    {
        "key": "apps",
        "duration": 24.0,
        "title": "Connected apps, real boundaries",
        "caption": "Google Workspace, Discord, WhatsApp, audit, privacy, and recovery live behind explicit controls.",
        "narration": (
            "The product connects to Google Workspace, Discord, and WhatsApp through narrow adapters. Provider content is "
            "treated as untrusted input, and every tool call has validation, limits, and recovery behavior."
        ),
    },
    {
        "key": "workhub",
        "duration": 20.0,
        "title": "A full productivity workspace",
        "caption": "Projects, goals, tasks, habits, notes, events, integrations, and audit history in one place.",
        "narration": (
            "Beyond the hero workflow, LIFEOS includes a productivity workspace with projects, goals, tasks, notes, "
            "integration health, event history, and privacy controls."
        ),
    },
    {
        "key": "mobile",
        "duration": 20.0,
        "title": "Responsive and presentation-ready",
        "caption": "Desktop density, tablet readability, and mobile-safe layouts.",
        "narration": (
            "The interface is designed for repeat use, not just screenshots. It keeps clear hierarchy on desktop and remains "
            "usable on smaller mobile viewports without broken controls."
        ),
    },
    {
        "key": "proof",
        "duration": 24.0,
        "title": "Verified release evidence",
        "caption": "Tests, deployment, live acceptance, screenshots, subtitles, poster, and documentation are included.",
        "narration": (
            "The release includes tests, security checks, deployment verification, screenshots, diagrams, subtitles, and a "
            "documented live Calendar to Discord to WhatsApp acceptance run with undo and cleanup."
        ),
    },
]


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
    wav = OUT_DIR / f"voice_{scene_index:02d}.wav"
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    ps = f"""
$bytes = [Convert]::FromBase64String('{encoded}')
$text = [Text.Encoding]::UTF8.GetString($bytes)
$voice = New-Object -ComObject SAPI.SpVoice
$format = New-Object -ComObject SAPI.SpAudioFormat
$format.Type = 39
$stream = New-Object -ComObject SAPI.SpFileStream
$stream.Format = $format
$stream.Open('{str(wav)}', 3, $false)
$voice.AudioOutputStream = $stream
$voice.Rate = 0
$voice.Volume = 100
[void]$voice.Speak($text)
$stream.Close()
"""
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], capture_output=True)
    return wav


def build_audio() -> tuple[float, list[dict[str, object]]]:
    prepared: list[dict[str, object]] = []
    for index, scene in enumerate(SCENES, start=1):
        voice = make_voice(index, scene["narration"])
        voice_duration = wav_duration(voice)
        duration = max(float(scene["duration"]), voice_duration + 1.4)
        silence = max(0.05, duration - voice_duration)
        padded = OUT_DIR / f"padded_{index:02d}.wav"
        run(
            [
                FFMPEG,
                "-y",
                "-i",
                str(voice),
                "-f",
                "lavfi",
                "-t",
                f"{silence:.3f}",
                "-i",
                "anullsrc=r=44100:cl=mono",
                "-filter_complex",
                "[0:a][1:a]concat=n=2:v=0:a=1[a]",
                "-map",
                "[a]",
                str(padded),
            ],
            capture_output=True,
        )
        prepared.append({**scene, "voice": voice, "padded": padded, "duration": duration})

    concat_list = OUT_DIR / "audio_concat.txt"
    concat_list.write_text(
        "".join(f"file '{str(item['padded']).replace(chr(92), '/')}'\n" for item in prepared),
        encoding="utf-8",
    )
    run(
        [
            FFMPEG,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c",
            "copy",
            str(FULL_AUDIO),
        ],
        capture_output=True,
    )
    return sum(float(item["duration"]) for item in prepared), prepared


def write_srt_and_script(prepared: list[dict[str, object]]) -> None:
    current = 0.0
    srt = []
    script = [
        "# LIFEOS Top 1% Hackathon Demo Script",
        "",
        "This video is a polished submission demo visualization. It uses the shipped LIFEOS product surface, repository evidence, and mock animated workflow states to present the full complex workflow without touching live accounts again.",
        "",
    ]
    for index, scene in enumerate(prepared, start=1):
        duration = float(scene["duration"])
        start = current
        end = current + duration
        srt.append(
            f"{index}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{scene['narration']}\n"
        )
        script.extend(
            [
                f"## Scene {index}: {scene['title']}",
                "",
                f"Time: {format_srt_time(start)} to {format_srt_time(end)}",
                "",
                f"Narration: {scene['narration']}",
                "",
                f"On screen: {scene['caption']}",
                "",
            ]
        )
        current = end
    FINAL_SRT.write_text("\n".join(srt), encoding="utf-8")
    FINAL_SCRIPT.write_text("\n".join(script), encoding="utf-8")


def image_uri(relative: str) -> str:
    path = ROOT / relative
    return path.resolve().as_uri() if path.exists() else ""


def write_html(prepared: list[dict[str, object]]) -> None:
    scenes_json = json.dumps(
        [
            {
                "key": item["key"],
                "duration": item["duration"],
                "title": item["title"],
                "caption": item["caption"],
                "narration": item["narration"],
            }
            for item in prepared
        ]
    )
    assets = json.dumps(
        {
            "dashboard": image_uri("docs/screenshots/01-dashboard.png"),
            "plan": image_uri("docs/screenshots/02-workflow-plan.png"),
            "result": image_uri("docs/screenshots/03-verified-result.png"),
            "apps": image_uri("docs/screenshots/04-demo-applications.png"),
            "audit": image_uri("docs/screenshots/05-audit-trail.png"),
            "mobile": image_uri("docs/screenshots/06-mobile-overview.png"),
        }
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>LIFEOS Top 1% Demo</title>
<style>
:root {{
  --bg: #08110e;
  --panel: rgba(246, 248, 242, .94);
  --ink: #0e1814;
  --muted: #688076;
  --line: #d8e3d8;
  --green: #34d399;
  --lime: #b7f264;
  --gold: #f4c95d;
  --blue: #82b1ff;
  --rose: #ff8aa1;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; width: {WIDTH}px; height: {HEIGHT}px; overflow: hidden;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Arial, sans-serif;
  color: #f6faf7; background: radial-gradient(circle at 18% 15%, #1e4f3e 0, transparent 24%),
    radial-gradient(circle at 80% 12%, #233c5f 0, transparent 24%),
    linear-gradient(140deg, #07100d 0%, #101a17 48%, #16231d 100%);
}}
.grid {{
  position: fixed; inset: 0; opacity: .24;
  background-image: linear-gradient(rgba(255,255,255,.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.08) 1px, transparent 1px);
  background-size: 54px 54px;
}}
.noise {{
  position: fixed; inset: 0; opacity: .1; pointer-events: none;
  background-image: repeating-radial-gradient(circle at 0 0, rgba(255,255,255,.4) 0 1px, transparent 1px 5px);
}}
.frame {{ position: relative; width: 100%; height: 100%; padding: 54px 70px 120px; }}
.topbar {{ display:flex; align-items:center; justify-content:space-between; height:62px; }}
.brand {{ display:flex; align-items:center; gap:16px; font-weight:800; letter-spacing:0; font-size:26px; }}
.logo {{ width:44px; height:44px; border-radius:12px; background: conic-gradient(from 120deg, var(--green), var(--blue), var(--gold), var(--green)); box-shadow: 0 0 38px rgba(52,211,153,.55); position:relative; }}
.logo::after {{ content:""; position:absolute; inset:12px; border-radius:8px; background:#09120f; }}
.pillrow {{ display:flex; gap:10px; }}
.pill {{ border:1px solid rgba(255,255,255,.18); color:#d9f4e6; padding:10px 14px; border-radius:999px; background:rgba(255,255,255,.07); font-size:14px; }}
.main {{ display:grid; grid-template-columns: 1.02fr 1.08fr; gap:34px; height:780px; margin-top:38px; }}
.hero {{ padding:24px 0 0; }}
.eyebrow {{ color:var(--lime); font-weight:800; font-size:17px; margin-bottom:16px; }}
h1 {{ font-size:72px; line-height:.98; margin:0 0 22px; letter-spacing:0; max-width:760px; }}
.subtitle {{ color:#d3e0d8; font-size:24px; line-height:1.42; max-width:780px; }}
.proofs {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:14px; margin-top:32px; max-width:790px; }}
.proof {{ padding:18px; border:1px solid rgba(255,255,255,.14); background:rgba(255,255,255,.07); border-radius:16px; min-height:112px; }}
.proof strong {{ display:block; color:#fff; font-size:28px; margin-bottom:8px; }}
.proof span {{ color:#bad0c5; font-size:14px; line-height:1.35; }}
.stage {{ position:relative; border:1px solid rgba(255,255,255,.16); border-radius:28px; background:rgba(246,248,242,.08); overflow:hidden; box-shadow: 0 30px 120px rgba(0,0,0,.36); }}
.stage::before {{ content:""; position:absolute; inset:-40%; background: radial-gradient(circle, rgba(52,211,153,.12), transparent 45%); animation: drift 16s linear infinite; }}
@keyframes drift {{ from {{ transform: translate(-4%, -2%) rotate(0deg); }} to {{ transform: translate(4%, 2%) rotate(360deg); }} }}
.canvas {{ position:absolute; inset:0; padding:32px; }}
.appshot {{ position:absolute; border-radius:22px; overflow:hidden; border:1px solid rgba(255,255,255,.18); box-shadow:0 24px 70px rgba(0,0,0,.34); background:#f7faf7; }}
.appshot img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.shot-main {{ left:38px; top:40px; width:820px; height:506px; transform: rotate(-1.4deg); }}
.shot-side {{ right:42px; bottom:62px; width:420px; height:522px; transform: rotate(2.2deg); }}
.workflow {{ position:absolute; inset:42px 28px 42px 28px; }}
.node {{ position:absolute; width:182px; min-height:112px; padding:16px; border-radius:18px; color:var(--ink); background:var(--panel); border:1px solid rgba(255,255,255,.5); box-shadow:0 18px 60px rgba(0,0,0,.28); }}
.node small {{ color:#557067; font-weight:800; font-size:12px; text-transform:uppercase; }}
.node b {{ display:block; font-size:20px; margin:8px 0 7px; }}
.node span {{ color:#5a7169; font-size:13px; line-height:1.28; }}
.node .dot {{ position:absolute; right:18px; top:18px; width:13px; height:13px; border-radius:50%; background:var(--green); box-shadow:0 0 0 0 rgba(52,211,153,.7); animation:pulse 1.4s infinite; }}
@keyframes pulse {{ 70% {{ box-shadow:0 0 0 18px rgba(52,211,153,0); }} 100% {{ box-shadow:0 0 0 0 rgba(52,211,153,0); }} }}
.n-source {{ left:16px; top:54px; }}
.n-plan {{ left:260px; top:42px; }}
.n-policy {{ left:504px; top:54px; }}
.n-calendar {{ left:86px; top:300px; }}
.n-discord {{ left:330px; top:318px; }}
.n-whatsapp {{ left:574px; top:300px; }}
.n-audit {{ left:330px; top:420px; }}
svg.links {{ position:absolute; inset:0; overflow:visible; }}
.links path {{ fill:none; stroke:rgba(183,242,100,.48); stroke-width:4; stroke-linecap:round; stroke-dasharray:10 15; animation: dash 1.8s linear infinite; filter: drop-shadow(0 0 8px rgba(52,211,153,.48)); }}
@keyframes dash {{ to {{ stroke-dashoffset:-50; }} }}
.statusRail {{ position:absolute; left:38px; right:38px; bottom:36px; display:grid; grid-template-columns: repeat(4,1fr); gap:14px; }}
.status {{ background:rgba(246,248,242,.95); color:var(--ink); border-radius:16px; padding:16px; border:1px solid #dce8de; }}
.status b {{ display:block; font-size:18px; margin-bottom:8px; }}
.status span {{ color:#5d736b; font-size:13px; }}
.bar {{ height:8px; border-radius:999px; background:#dce8de; margin-top:12px; overflow:hidden; }}
.bar i {{ display:block; height:100%; width:0; background:linear-gradient(90deg,var(--green),var(--lime)); animation: fill 7s ease-in-out infinite; }}
@keyframes fill {{ 0% {{ width:12%; }} 45% {{ width:72%; }} 80%,100% {{ width:100%; }} }}
.phone {{ position:absolute; right:76px; top:78px; width:292px; height:600px; border-radius:34px; border:12px solid #101917; background:#f8faf7; overflow:hidden; box-shadow:0 30px 70px rgba(0,0,0,.42); }}
.phone img {{ width:100%; height:100%; object-fit:cover; }}
.architecture {{ position:absolute; inset:48px; display:grid; grid-template-columns: repeat(3, 1fr); gap:18px; }}
.archCard {{ border-radius:18px; background:rgba(246,248,242,.95); color:var(--ink); padding:22px; box-shadow:0 20px 60px rgba(0,0,0,.24); }}
.archCard h3 {{ margin:0 0 10px; font-size:26px; }}
.archCard p {{ margin:0; color:#5b7169; font-size:16px; line-height:1.38; }}
.captionBox {{ position:absolute; left:70px; right:70px; bottom:36px; border:1px solid rgba(255,255,255,.2); background:rgba(5,10,8,.78); backdrop-filter: blur(14px); border-radius:18px; min-height:64px; padding:16px 22px; display:flex; align-items:center; justify-content:space-between; gap:24px; }}
.captionText {{ font-size:22px; line-height:1.25; color:#effaf4; max-width:1460px; }}
.sceneCount {{ color:#b7f264; font-weight:800; min-width:110px; text-align:right; }}
.progress {{ position:absolute; left:70px; right:70px; bottom:20px; height:4px; border-radius:999px; background:rgba(255,255,255,.14); overflow:hidden; }}
.progress i {{ display:block; height:100%; width:0; background:linear-gradient(90deg,var(--green),var(--lime),var(--gold)); }}
.hidden {{ display:none; }}
.fade {{ animation: sceneIn .8s ease both; }}
@keyframes sceneIn {{ from {{ opacity:0; transform:translateY(18px) scale(.985); }} to {{ opacity:1; transform:translateY(0) scale(1); }} }}
</style>
</head>
<body>
<div class="grid"></div><div class="noise"></div>
<main class="frame">
  <div class="topbar">
    <div class="brand"><div class="logo"></div><div>LIFEOS</div></div>
    <div class="pillrow"><div class="pill">Next-Gen Productivity</div><div class="pill">AI Workflow Automation</div><div class="pill">Verified Execution</div></div>
  </div>
  <section class="main">
    <div class="hero fade">
      <div class="eyebrow" id="eyebrow">Hackathon demo visualization</div>
      <h1 id="title">One change. Dozens of consequences.</h1>
      <p class="subtitle" id="subtitle">A schedule change should not become a manual coordination mess.</p>
      <div class="proofs">
        <div class="proof"><strong>140</strong><span>backend tests passed during final verification</span></div>
        <div class="proof"><strong>Live</strong><span>Calendar to Discord to WhatsApp acceptance verified</span></div>
        <div class="proof"><strong>Safe</strong><span>approval gates, read-back, audit trail, undo path</span></div>
      </div>
    </div>
    <div class="stage fade" id="stage"></div>
  </section>
</main>
<div class="captionBox"><div class="captionText" id="caption">Loading demo...</div><div class="sceneCount" id="sceneCount">01 / 09</div></div>
<div class="progress"><i id="progress"></i></div>
<script>
const scenes = {scenes_json};
const assets = {assets};
const stage = document.getElementById('stage');
const title = document.getElementById('title');
const subtitle = document.getElementById('subtitle');
const caption = document.getElementById('caption');
const count = document.getElementById('sceneCount');
const progress = document.getElementById('progress');
const total = scenes.reduce((sum, scene) => sum + scene.duration, 0);
let started = performance.now();
function img(src) {{ return src ? `<img src="${{src}}" alt="" />` : ''; }}
function graph() {{
  return `<div class="workflow">
    <svg class="links" viewBox="0 0 800 720">
      <path d="M198 112 C226 84 242 94 260 104" />
      <path d="M442 104 C470 84 488 94 504 112" />
      <path d="M594 170 C530 244 452 288 421 318" />
      <path d="M108 170 C110 236 132 270 178 300" />
      <path d="M352 160 C354 226 374 278 421 318" />
      <path d="M666 170 C646 238 646 270 665 300" />
      <path d="M178 412 C254 438 326 414 408 420" />
      <path d="M421 430 C420 424 420 422 421 420" />
      <path d="M665 412 C570 438 496 414 436 420" />
    </svg>
    <div class="node n-source"><i class="dot"></i><small>Source</small><b>Changed event</b><span>Flight or meeting update enters LIFEOS.</span></div>
    <div class="node n-plan"><i class="dot"></i><small>Planner</small><b>AI extraction</b><span>Structured intent and affected records.</span></div>
    <div class="node n-policy"><i class="dot"></i><small>Policy</small><b>Approval gate</b><span>Risk, version, hashes, permissions.</span></div>
    <div class="node n-calendar"><i class="dot"></i><small>Action</small><b>Calendar</b><span>Update event after approval.</span></div>
    <div class="node n-discord"><i class="dot"></i><small>Notify</small><b>Discord</b><span>Send team update after Calendar verifies.</span></div>
    <div class="node n-whatsapp"><i class="dot"></i><small>Notify</small><b>WhatsApp</b><span>Send configured chat message.</span></div>
    <div class="node n-audit"><i class="dot"></i><small>Evidence</small><b>Read-back</b><span>Provider proof, audit, undo path.</span></div>
  </div>`;
}}
function statusRail() {{
  return `<div class="statusRail">
    <div class="status"><b>Calendar</b><span>verified read-back</span><div class="bar"><i></i></div></div>
    <div class="status"><b>Discord</b><span>message ID confirmed</span><div class="bar"><i></i></div></div>
    <div class="status"><b>WhatsApp</b><span>exact outgoing body found</span><div class="bar"><i></i></div></div>
    <div class="status"><b>Audit</b><span>immutable evidence trail</span><div class="bar"><i></i></div></div>
  </div>`;
}}
function arch() {{
  return `<div class="architecture">
    <div class="archCard"><h3>AI plans</h3><p>Structured extraction turns messy text into bounded workflow intent.</p></div>
    <div class="archCard"><h3>Server controls</h3><p>Validation, approvals, dependency rules, rate limits and safe failure states.</p></div>
    <div class="archCard"><h3>Read-back proof</h3><p>Calendar, Discord and WhatsApp are verified after execution.</p></div>
    <div class="archCard"><h3>Privacy</h3><p>Owner-scoped records, CSRF, export, deletion and no credential logs.</p></div>
    <div class="archCard"><h3>Desktop bridge</h3><p>WhatsApp actions run through the signed-in local app window.</p></div>
    <div class="archCard"><h3>Release evidence</h3><p>Tests, build, public URL, screenshots, subtitles and final report.</p></div>
  </div>`;
}}
function render(scene, index) {{
  title.textContent = scene.title;
  subtitle.textContent = scene.caption;
  caption.textContent = scene.narration;
  count.textContent = String(index + 1).padStart(2, '0') + ' / ' + String(scenes.length).padStart(2, '0');
  stage.classList.remove('fade'); void stage.offsetWidth; stage.classList.add('fade');
  if (scene.key === 'problem' || scene.key === 'product') {{
    stage.innerHTML = `<div class="canvas"><div class="appshot shot-main">${{img(assets.dashboard)}}</div><div class="appshot shot-side">${{img(assets.plan)}}</div></div>${{statusRail()}}`;
  }} else if (scene.key === 'graph' || scene.key === 'execution') {{
    stage.innerHTML = graph() + statusRail();
  }} else if (scene.key === 'approval') {{
    stage.innerHTML = `<div class="canvas"><div class="appshot shot-main">${{img(assets.plan)}}</div><div class="appshot shot-side">${{img(assets.result)}}</div></div>${{statusRail()}}`;
  }} else if (scene.key === 'apps') {{
    stage.innerHTML = `<div class="canvas"><div class="appshot shot-main">${{img(assets.apps)}}</div><div class="appshot shot-side">${{img(assets.audit)}}</div></div>${{statusRail()}}`;
  }} else if (scene.key === 'workhub') {{
    stage.innerHTML = `<div class="canvas"><div class="appshot shot-main">${{img(assets.dashboard)}}</div><div class="appshot shot-side">${{img(assets.result)}}</div></div>${{statusRail()}}`;
  }} else if (scene.key === 'mobile') {{
    stage.innerHTML = `<div class="canvas"><div class="appshot shot-main">${{img(assets.dashboard)}}</div><div class="phone">${{img(assets.mobile)}}</div></div>`;
  }} else {{
    stage.innerHTML = arch();
  }}
}}
let active = -1;
function tick() {{
  const elapsed = (performance.now() - started) / 1000;
  let cursor = 0;
  let index = scenes.length - 1;
  for (let i = 0; i < scenes.length; i++) {{
    if (elapsed < cursor + scenes[i].duration) {{ index = i; break; }}
    cursor += scenes[i].duration;
  }}
  if (index !== active) {{ active = index; render(scenes[index], index); }}
  progress.style.width = Math.min(100, elapsed / total * 100) + '%';
  requestAnimationFrame(tick);
}}
window.__startDemo = () => {{ started = performance.now(); active = -1; tick(); }};
window.__startDemo();
</script>
</body>
</html>"""
    HTML_FILE.write_text(html, encoding="utf-8")


def record_video(duration: float) -> Path:
    video_dir = OUT_DIR / "recordings"
    if video_dir.exists():
        for item in video_dir.glob("*"):
            item.unlink()
    video_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            record_video_dir=str(video_dir),
            record_video_size={"width": WIDTH, "height": HEIGHT},
        )
        page = context.new_page()
        page.goto(HTML_FILE.resolve().as_uri(), wait_until="load")
        page.evaluate("window.__startDemo()")
        page.wait_for_timeout(int((duration + 0.5) * 1000))
        video = page.video
        context.close()
        browser.close()
        if not video:
            raise RuntimeError("Playwright did not produce a video")
        return Path(video.path())


def mux_video(raw_video: Path, duration: float) -> None:
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(raw_video),
            "-i",
            str(FULL_AUDIO),
            "-t",
            f"{duration:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
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
    start = time.time()
    print("Generating narration audio...")
    duration, prepared = build_audio()
    print(f"Audio duration: {duration:.2f}s")
    print("Writing script, subtitles and storyboard...")
    write_srt_and_script(prepared)
    write_html(prepared)
    print("Recording HD storyboard...")
    raw_video = record_video(duration)
    print(f"Raw video: {raw_video}")
    print("Muxing final MP4...")
    mux_video(raw_video, duration)
    print(f"Video: {FINAL_MP4}")
    print(f"Subtitles: {FINAL_SRT}")
    print(f"Script: {FINAL_SCRIPT}")
    print(f"Completed in {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
