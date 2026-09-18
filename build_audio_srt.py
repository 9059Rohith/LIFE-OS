import os
import sys
import time
import math
from pathlib import Path
from gtts import gTTS
from moviepy import AudioFileClip, concatenate_audioclips
from moviepy.video.tools.subtitles import SubtitlesClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Ensure Downloads folder exists
DOWNLOADS = Path("C:/Users/AJEYA/Downloads")
DOWNLOADS.mkdir(parents=True, exist_ok=True)
VIDEO_OUT = DOWNLOADS / "complete_application_demo.mp4"
SRT_OUT = DOWNLOADS / "complete_application_demo.srt"
TEMP_DIR = Path("artifacts/demo_temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# 1. Define Narration Script & Subtitles
SCENES = [
    {
        "id": "scene1",
        "text": "Welcome to LIFE OS, an intelligent Life Operating System built to handle complex personal and professional change. When a flight time shifts or a meeting conflicts, LIFE OS automatically analyzes the consequence graph, proposes exact application actions, enforces human authorization, and verifies execution with read-back proof.",
        "duration": 22.0
    },
    {
        "id": "scene2",
        "text": "Here on the main dashboard, the user has a unified view of their productivity workspace. The top navigation bar provides instant access to My Work, Connected Apps, Events, Integrations, and System Settings, while the dark header displays real-time connection status across all integration boundaries.",
        "duration": 22.0
    },
    {
        "id": "scene3",
        "text": "In the My Work module, users manage projects, goals, tasks, habits, and notes with immediate local persistence. Adding a new task, updating habit check-in streaks, or creating notes updates linked project progress instantly. All records survive page reloads and application restarts.",
        "duration": 22.0
    },
    {
        "id": "scene4",
        "text": "Now let's examine the Event Consequence Intelligence engine. On the Connected Apps screen, users can choose any timed Google Calendar event, select a new start and end time, and check optional notification targets for Discord or WhatsApp. LIFE OS reads live availability, evaluates risk policy, and prepares a version-locked proposal for user review.",
        "duration": 25.0
    },
    {
        "id": "scene5",
        "text": "Next, observe the Ripple Effect visualization. As event plans are created and actions transition through execution and verification, the animated progress bar updates dynamically. Each action card displays live application status badges, smooth hover feedback, and direct navigation focus links.",
        "duration": 24.0
    },
    {
        "id": "scene6",
        "text": "LIFE OS integrates directly with Google Workspace, Discord, and WhatsApp. Gmail inboxes, Calendar events, and Drive files stream read-only data securely, while Discord channel history displays live text messages. The Windows desktop companion hosts signed-in WhatsApp Web views for authorized messaging.",
        "duration": 23.0
    },
    {
        "id": "scene7",
        "text": "The user interface is fully responsive across desktop, laptop, tablet, and mobile viewports. Layout grids adjust dynamically to prevent horizontal scrolling, text clipping, or broken touch targets on mobile devices.",
        "duration": 18.0
    },
    {
        "id": "scene8",
        "text": "Here we demonstrate the end-to-end workflow: an event is submitted, analyzed, reviewed in the proposal modal, authorized by the primary owner, executed, and confirmed through provider read-back verification.",
        "duration": 20.0
    },
    {
        "id": "scene9",
        "text": "In conclusion, LIFE OS has passed all 137 backend tests, 7 desktop bridge tests, static type audits, and security checks. It is fully deployed on Render and ready for hackathon submission.",
        "duration": 16.0
    }
]

def format_srt_time(seconds):
    millis = int((seconds - int(seconds)) * 1000)
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def generate_audio_and_srt():
    print("--- Generating Audio Narration & Subtitles ---")
    audio_clips = []
    srt_entries = []
    current_time = 0.0

    for idx, scene in enumerate(SCENES, start=1):
        text = scene["text"]
        mp3_path = TEMP_DIR / f"{scene['id']}.mp3"
        
        # Generate TTS audio
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(str(mp3_path))
        
        # Load audio clip and get actual duration
        audio_clip = AudioFileClip(str(mp3_path))
        actual_duration = audio_clip.duration
        scene["actual_duration"] = actual_duration
        audio_clips.append(audio_clip)

        # SRT entry
        start_srt = format_srt_time(current_time)
        end_srt = format_srt_time(current_time + actual_duration)
        srt_entries.append(f"{idx}\n{start_srt} --> {end_srt}\n{text}\n")

        current_time += actual_duration

    # Write SRT file
    SRT_OUT.write_text("\n".join(srt_entries), encoding="utf-8")
    print(f"SRT file created at: {SRT_OUT} (Total Duration: {current_time:.2f}s)")
    return audio_clips, current_time

if __name__ == "__main__":
    generate_audio_and_srt()
