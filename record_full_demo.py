import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CLIPS_DIR = Path("artifacts/video_clips")
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
AUTH_PASS = "nQeWZnwZlHvSDLwg8ciy0IppnY6xsQOj"

def record_demo():
    print("--- Starting Playwright UI Recording ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Scenario 1: Main Desktop Recording (1280x720)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(CLIPS_DIR),
            record_video_size={"width": 1280, "height": 720}
        )
        page = context.new_page()
        
        # Navigate to local app
        page.goto("http://127.0.0.1:5173", wait_until="networkidle")
        time.sleep(1.5)
        
        # Handle login if login screen is displayed
        pwd_input = page.locator("input[type='password']").first
        if pwd_input.is_visible():
            pwd_input.fill(AUTH_PASS)
            time.sleep(1)
            submit_btn = page.locator("button:has-text('Sign in'), button[type='submit']").first
            if submit_btn.is_visible():
                submit_btn.click()
                time.sleep(2)
        
        # Scene 1 & 2: Header Overview & Navigation
        page.mouse.move(200, 150)
        time.sleep(1.5)
        
        # Click My work
        my_work_tab = page.locator("button:has-text('My work'), a:has-text('My work')").first
        if my_work_tab.is_visible():
            my_work_tab.click()
            time.sleep(2)
        
        # Scene 3: My Work Features (Add Task, Habit Check-in, Notes)
        task_input = page.locator("input[placeholder*='task' i], input[placeholder*='Add' i], input[type='text']").first
        if task_input.is_visible():
            task_input.fill("Complete QA Audit & Final Demo Video")
            time.sleep(1)
            add_btn = page.locator("button:has-text('Add'), button[type='submit']").first
            if add_btn.is_visible():
                add_btn.click()
                time.sleep(1.5)
        
        # Switch tabs in My Work
        for tab_name in ["Goals", "Habits", "Notes", "Agenda", "Projects", "Tasks"]:
            tab_loc = page.locator(f"button:has-text('{tab_name}')").first
            if tab_loc.is_visible():
                tab_loc.click()
                time.sleep(1.2)
        
        # Scene 4 & 5 & 6: Connected Apps & Reschedule Plan & Ripple Effect
        connected_tab = page.locator("button:has-text('Connected apps'), a:has-text('Connected apps')").first
        if connected_tab.is_visible():
            connected_tab.click()
            time.sleep(2.5)
        
        # Click Check connections
        check_btn = page.locator("button:has-text('Check connections')").first
        if check_btn.is_visible():
            check_btn.click()
            time.sleep(2)
            
        # Plan move on calendar if button exists
        plan_move_btn = page.locator("button:has-text('Plan move')").first
        if plan_move_btn.is_visible():
            plan_move_btn.click()
            time.sleep(2)
            
            # Fill datetime fields
            start_in = page.locator("input[type='datetime-local']").first
            if start_in.is_visible():
                start_in.fill("2026-09-20T14:00")
                time.sleep(1)
            
            end_in = page.locator("input[type='datetime-local']").nth(1)
            if end_in.is_visible():
                end_in.fill("2026-09-20T15:00")
                time.sleep(1)
                
            disc_check = page.locator("input[type='checkbox']").first
            if disc_check.is_visible() and not disc_check.is_checked():
                disc_check.check()
                time.sleep(1)
                
            rev_btn = page.locator("button:has-text('Review plan')").first
            if rev_btn.is_visible():
                rev_btn.click()
                time.sleep(3)
        
        # Ripple Effect section focus
        ripple_elem = page.locator("[aria-label*='Ripple' i]").first
        if ripple_elem.is_visible():
            ripple_elem.hover()
            time.sleep(2)
            
        # Hover over individual provider panels
        for app in ["discord", "gmail", "whatsapp", "calendar", "drive"]:
            app_sec = page.locator(f".unified-{app}").first
            if app_sec.is_visible():
                app_sec.hover()
                time.sleep(1.2)

        # Scene 8: Events & Intelligence
        events_tab = page.locator("button:has-text('Events'), a:has-text('Events')").first
        if events_tab.is_visible():
            events_tab.click()
            time.sleep(2)
        
        evt_in = page.locator("textarea, input[placeholder*='event' i]").first
        if evt_in.is_visible():
            evt_in.fill("Flight AI101 delayed by 2 hours. Reschedule team meeting and alert team on Discord.")
            time.sleep(1.5)
            
        # Scene 9: Dashboard Summary
        if my_work_tab.is_visible():
            my_work_tab.click()
            time.sleep(3)
        
        context.close()
        
        # Scenario 2: Responsive Mobile Recording (390x844)
        context_mobile = browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            record_video_dir=str(CLIPS_DIR),
            record_video_size={"width": 390, "height": 844}
        )
        page_m = context_mobile.new_page()
        page_m.goto("http://127.0.0.1:5173", wait_until="networkidle")
        time.sleep(1.5)
        
        # Login on mobile
        pwd_m = page_m.locator("input[type='password']").first
        if pwd_m.is_visible():
            pwd_m.fill(AUTH_PASS)
            time.sleep(1)
            submit_m = page_m.locator("button:has-text('Sign in'), button[type='submit']").first
            if submit_m.is_visible():
                submit_m.click()
                time.sleep(2)
                
        # Scroll and navigate on mobile
        c_tab = page_m.locator("button:has-text('Connected apps'), a:has-text('Connected apps')").first
        if c_tab.is_visible():
            c_tab.click()
            time.sleep(2)
        page_m.evaluate("window.scrollBy(0, 400)")
        time.sleep(2)
        
        m_tab = page_m.locator("button:has-text('My work'), a:has-text('My work')").first
        if m_tab.is_visible():
            m_tab.click()
            time.sleep(2)
            
        context_mobile.close()
        browser.close()
        print("--- Playwright UI Recording Completed ---")

if __name__ == "__main__":
    record_demo()
