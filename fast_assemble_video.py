import os
import sys
import glob
import subprocess
from pathlib import Path

DOWNLOADS = Path("C:/Users/AJEYA/Downloads")
DOWNLOADS.mkdir(parents=True, exist_ok=True)
FINAL_MP4 = DOWNLOADS / "complete_application_demo.mp4"
SRT_FILE = DOWNLOADS / "complete_application_demo.srt"
TEMP_DIR = Path("artifacts/demo_temp")
CLIPS_DIR = Path("artifacts/video_clips")
AUDIO_LIST = TEMP_DIR / "audio_list.txt"
FULL_AUDIO = TEMP_DIR / "full_narration.mp3"

def build_fast_video():
    print("--- Fast FFmpeg Video Assembly ---")
    
    # 1. Create list of audio files for FFmpeg concat
    audio_files = [TEMP_DIR / f"scene{i}.mp3" for i in range(1, 10) if (TEMP_DIR / f"scene{i}.mp3").exists()]
    if not audio_files:
        raise RuntimeError("No scene audio files found!")
        
    with open(AUDIO_LIST, "w", encoding="utf-8") as f:
        for a in audio_files:
            # Escape backslashes for FFmpeg concat list
            path_str = str(a.resolve()).replace("\\", "/")
            f.write(f"file '{path_str}'\n")
            
    # Concatenate audio tracks into full_narration.mp3
    print("Concatenating narration audio tracks...")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(AUDIO_LIST.resolve()),
        "-c", "copy", str(FULL_AUDIO.resolve())
    ], check=True)
    
    # Get total audio duration using ffprobe
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(FULL_AUDIO.resolve())
    ], capture_output=True, text=True, check=True)
    duration = float(probe.stdout.strip())
    print(f"Total Audio Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    
    # Find raw Playwright video clips
    raw_videos = sorted(glob.glob(str(CLIPS_DIR / "*.webm")) + glob.glob(str(CLIPS_DIR / "*.mp4")))
    if not raw_videos:
        raise RuntimeError("No Playwright video clips found!")
    raw_video = raw_videos[0]
    print(f"Using raw video clip: {raw_video}")
    
    # Prepare SRT path formatted for FFmpeg filter (escape colon and backslash)
    srt_path_str = str(SRT_FILE.resolve()).replace("\\", "/").replace(":", "\\:")
    
    # Single fast FFmpeg command: loop video to audio length, merge audio, overlay subtitles, encode h264
    print("Rendering final MP4 with audio and subtitles via FFmpeg...")
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", raw_video,
        "-i", str(FULL_AUDIO.resolve()),
        "-t", str(duration),
        "-vf", f"scale=1280:720,subtitles='{srt_path_str}':force_style='FontSize=18,PrimaryColour=&H00F0F5F1,BackColour=&H99121B14,BorderStyle=3,Outline=1,Shadow=0,MarginV=25'",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(FINAL_MP4.resolve())
    ]
    
    subprocess.run(cmd, check=True)
    print(f"--- Fast FFmpeg Assembly Completed Successfully! ---")
    print(f"Output File: {FINAL_MP4} (Size: {FINAL_MP4.stat().st_size / (1024*1024):.2f} MB)")

if __name__ == "__main__":
    build_fast_video()
