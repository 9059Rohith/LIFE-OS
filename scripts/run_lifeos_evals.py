"""Run deterministic, offline LIFE-OS extraction regression cases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from lifeos.planning import extract  # noqa: E402


def matches(actual: dict, expected: dict) -> list[str]:
    failures = []
    for key, value in expected.items():
        if key == "date_required":
            if bool(actual.get(key)) is not value:
                failures.append(f"{key}: expected {value!r}, got {actual.get(key)!r}")
        elif actual.get(key) != value:
            failures.append(f"{key}: expected {value!r}, got {actual.get(key)!r}")
    return failures


def main() -> int:
    cases = json.loads((ROOT / "evals" / "extraction_cases.json").read_text(encoding="utf-8"))
    passed = 0
    for case in cases:
        actual = extract(case["input"], "Asia/Kolkata")
        failures = matches(actual, case["expected"])
        if failures:
            print(f"FAIL {case['name']}: {'; '.join(failures)}")
        else:
            passed += 1
            print(f"PASS {case['name']}")
    print(f"\nLIFE-OS extraction evals: {passed}/{len(cases)} passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
