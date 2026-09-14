"""Small credential-pattern gate; emits locations only, never matched secrets."""

from pathlib import Path
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".venv", "node_modules", "dist", "data", "__pycache__", ".browser-profile", ".private"}
PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def main() -> int:
    findings = []
    for directory, directories, filenames in os.walk(ROOT):
        directories[:] = [name for name in directories if name not in EXCLUDED]
        for filename in filenames:
            path = Path(directory) / filename
            relative = path.relative_to(ROOT)
            if path.is_symlink() or (filename.startswith(".env") and filename != ".env.example"):
                continue  # Local secret configuration is intentionally outside source scanning.
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                lines = path.read_text(encoding="utf-8").splitlines()
            except (UnicodeError, OSError):
                continue
            for number, line in enumerate(lines, 1):
                if any(pattern.search(line) for pattern in PATTERNS):
                    findings.append(f"{relative}:{number}: possible credential")
    print("\n".join(findings) if findings else "No known credential patterns found in source files.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
