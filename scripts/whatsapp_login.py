"""Operator-run manual WhatsApp QR login into a dedicated browser profile."""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright
from lifeos.profile_lock import ProfileLease


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=".private/whatsapp")
    args = parser.parse_args()
    profile = Path(args.profile).resolve()
    if profile == Path.cwd().resolve() or profile == Path.home().resolve():
        parser.error("Select a dedicated profile subdirectory")
    profile.mkdir(parents=True, exist_ok=True)
    lease = ProfileLease(profile)
    lease.acquire()
    try:
        with sync_playwright() as browser:
            context = browser.chromium.launch_persistent_context(
                str(profile), headless=False, accept_downloads=False
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto("https://web.whatsapp.com/", wait_until="domcontentloaded")
                print(f"Dedicated profile: {profile}")
                input(
                    "Sign in manually using WhatsApp's QR flow, then press Enter here to close and save the profile: "
                )
            finally:
                context.close()
    finally:
        lease.release()


if __name__ == "__main__":
    main()
