import os
import sys
import glob
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy import (
    VideoFileClip, AudioFileClip, CompositeVideoClip, CompositeAudioClip,
    concatenate_videoclips, concatenate_audioclips, ImageClip
)

DOWNLOADS = Path("C:/Users/AJEYA/Downloads")
DOWNLOADS.mkdir(parents=True, exist_ok=True)
FINAL_MP4 = DOWNLOADS / "complete_application_demo.mp4"
TEMP_DIR = Path("artifacts/demo_temp")
CLIPS_DIR = Path("artifacts/video_clips")

# Narration scenes matching build_audio_srt.py
SCENES_TEXT = [
    ("Welcome to LIFE OS, an intelligent Life Operating System built to handle complex personal and professional change.", 22.0),
    ("Here on the main dashboard, the user has a unified view of their productivity workspace.", 22.0),
    ("In the My Work module, users manage projects, goals, tasks, habits, and notes with immediate local persistence.", 22.0),
    ("Now let's examine the Event Consequence Intelligence engine. On Connected Apps, users can plan calendar changes.", 25.0),
    ("Next, observe the Ripple Effect visualization as action cards transition through execution and verification.", 24.0),
    ("LIFE OS integrates directly with Google Workspace, Discord, and WhatsApp Web views for authorized messaging.", 23.0),
    ("The user interface is fully responsive across desktop, laptop, tablet, and mobile viewports.", 18.0),
    ("Here we demonstrate the end-to-end workflow: event input, analysis, proposal approval, and read-back verification.", 20.0),
    ("In conclusion, LIFE OS has passed all 137 tests, static type audits, and is live on Render ready for submission.", 16.0)
]

def make_subtitle_frame(txt, width=1280, height=720):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Subtitle box styling
    margin = 40
    box_height = 70
    box_y = height - margin - box_height
    box_rect = [(margin, box_y), (width - margin, box_y + box_height)]
    
    # Semi-transparent dark background box
    draw.rectangle(box_rect, fill=(15, 23, 18, 220), outline=(45, 94, 62, 255), width=2)
    
    # Font
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
        
    # Draw centered text
    bbox = draw.textbbox((0, 0), txt, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    text_x = (width - text_w) // 2
    text_y = box_y + (box_height - text_h) // 2 - 2
    
    draw.text((text_x, text_y), txt, font=font, fill=(240, 245, 241, 255))
    return np.array(img)

def assemble_video():
    print("--- Assembling Final Demo Video ---")
    
    # Find recorded WebM/MP4 video files from Playwright
    raw_videos = sorted(glob.glob(str(CLIPS_DIR / "*.webm")) + glob.glob(str(CLIPS_DIR / "*.mp4")))
    if not raw_videos:
        raise RuntimeError("No Playwright video clips found in artifacts/video_clips")
        
    print(f"Found {len(raw_videos)} raw video clips: {raw_videos}")
    
    # Load primary recorded raw video clip
    main_web_clip = VideoFileClip(raw_videos[0]).without_audio()
    if len(raw_videos) > 1:
        mobile_clip = VideoFileClip(raw_videos[1]).without_audio()
    else:
        mobile_clip = main_web_clip
        
    final_video_parts = []
    final_audio_parts = []
    
    total_audio_duration = 0.0
    
    for i in range(1, 10):
        scene_mp3 = TEMP_DIR / f"scene{i}.mp3"
        if not scene_mp3.exists():
            print(f"Warning: {scene_mp3} does not exist, skipping")
            continue
            
        audio_clip = AudioFileClip(str(scene_mp3))
        scene_dur = audio_clip.duration
        total_audio_duration += scene_dur
        
        # Pick appropriate video segment
        if i == 7 and len(raw_videos) > 1: # Mobile viewport scene
            base_v = mobile_clip
        else:
            base_v = main_web_clip
            
        # Loop or subclip video to match audio duration
        v_dur = base_v.duration
        if scene_dur <= v_dur:
            start_t = ((i - 1) * 12.0) % max(1.0, (v_dur - scene_dur))
            v_sub = base_v.subclipped(start_t, start_t + scene_dur)
        else:
            n_loops = math.ceil(scene_dur / v_dur)
            v_sub = concatenate_videoclips([base_v] * n_loops).subclipped(0, scene_dur)
            
        # Resize to standard 1280x720
        v_sub = v_sub.resized((1280, 720))
        
        # Create burned-in subtitle overlay
        sub_text, _ = SCENES_TEXT[i - 1]
        sub_img_np = make_subtitle_frame(sub_text, 1280, 720)
        sub_clip = ImageClip(sub_img_np).with_duration(scene_dur)
        
        # Composite video subclip + subtitle
        comp_v = CompositeVideoClip([v_sub, sub_clip]).with_duration(scene_dur)
        
        final_video_parts.append(comp_v)
        final_audio_parts.append(audio_clip)
        
    print(f"Total Combined Video Duration: {total_audio_duration:.2f} seconds ({total_audio_duration/60:.2f} minutes)")
    
    final_v = concatenate_videoclips(final_video_parts, method="compose")
    final_a = concatenate_audioclips(final_audio_parts)
    
    final_video = final_v.with_audio(final_a)
    
    print(f"Writing final MP4 to: {FINAL_MP4}")
    final_video.write_videofile(
        str(FINAL_MP4),
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        logger="bar"
    )
    print("--- Final Video Assembly Completed Successfully ---")

if __name__ == "__main__":
    assemble_video()
