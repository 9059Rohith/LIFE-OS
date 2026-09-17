"""Local live-instance UI smoke check; does not navigate to or mutate provider accounts."""

import json
from pathlib import Path

from dotenv import dotenv_values
from playwright.sync_api import sync_playwright, expect


def main():
    password = dotenv_values(".env").get("LIFEOS_AUTH_PASSWORD", "")
    result = {"login": "unverified", "work": "unverified", "integrations": "unverified"}
    try:
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1512, "height": 1050})
            page.goto("http://localhost:8010/", wait_until="domcontentloaded")
            page.get_by_label("Workspace password").fill(password)
            page.get_by_role("button", name="Open workspace").click()
            expect(page.get_by_role("heading", name="Something changed. You’re in control.")).to_be_visible()
            result["login"] = "passed"
            page.get_by_role("button", name="My work", exact=True).click()
            expect(page.get_by_role("heading", name="Make progress visible.")).to_be_visible()
            result["work"] = "passed"
            page.get_by_role("button", name="Integrations", exact=True).click()
            expect(page.get_by_role("heading", name="Your connected world.")).to_be_visible()
            result["integrations"] = "passed"
            browser.close()
    except Exception:
        # Playwright diagnostics can include filled form values: never print them.
        result["error"] = "Local UI check failed; inspect application health and login configuration."
    Path(".private").mkdir(exist_ok=True)
    Path(".private/live-ui-check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
