"""Refresh vendored font assets and licenses; no runtime font service dependency."""

from pathlib import Path
import re
import httpx

root = Path(__file__).resolve().parents[1] / "frontend" / "public" / "fonts"
root.mkdir(parents=True, exist_ok=True)
with httpx.Client(timeout=30, follow_redirects=True) as client:
    for family in ["DM Sans", "Manrope"]:
        response = client.get(
            "https://fonts.googleapis.com/css2",
            params={"family": family + ":wght@400;500;600;700", "display": "swap"},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        urls = list(dict.fromkeys(re.findall(r"url\((https://[^)]+)\)", response.text)))
        css = response.text
        for number, url in enumerate(urls):
            data = client.get(url)
            data.raise_for_status()
            name = family.lower().replace(" ", "-") + f"-{number}.woff2"
            (root / name).write_bytes(data.content)
            css = css.replace(url, "/fonts/" + name)
        (root / (family.lower().replace(" ", "-") + ".css")).write_text(css, encoding="utf-8")
        slug = family.lower().replace(" ", "")
        license_response = client.get(
            f"https://raw.githubusercontent.com/google/fonts/main/ofl/{slug}/OFL.txt"
        )
        license_response.raise_for_status()
        (root / (family.replace(" ", "-") + "-OFL.txt")).write_text(license_response.text, encoding="utf-8")
