"""Measure real local demo API requests. Refuses live mode and does not invent results."""

import argparse
import json
from pathlib import Path
import statistics
import time

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output", default="docs/benchmark.json")
    args = parser.parse_args()
    if not 1 <= args.runs <= 20:
        parser.error("--runs must be between 1 and 20")
    rows = []
    with httpx.Client(base_url=args.url, timeout=60) as client:
        response = client.get("/api/session")
        response.raise_for_status()
        session = response.json()
        if session["mode"] != "demo":
            raise SystemExit("Benchmark only runs against an explicitly labeled demo server.")
        client.headers.update({"X-CSRF-Token": session["csrf_token"], "Origin": args.url})
        for _ in range(args.runs):
            start = time.perf_counter()
            response = client.post("/api/demo/run", json={"scenario": "flight"})
            response.raise_for_status()
            event = response.json()
            planned = time.perf_counter()
            response = client.post(
                f"/api/events/{event['id']}/approve",
                json={
                    "action_ids": [action["id"] for action in event["actions"]],
                    "version": event["version"],
                },
            )
            response.raise_for_status()
            approved = time.perf_counter()
            response = client.post(f"/api/events/{event['id']}/execute")
            response.raise_for_status()
            final = response.json()
            done = time.perf_counter()
            if not final.get("actions") or any(a["status"] != "verified" for a in final["actions"]):
                raise RuntimeError(f"Execution was not fully verified: {final.get('status')}")
            rows.append(
                {
                    "plan_ms": (planned - start) * 1000,
                    "approve_ms": (approved - planned) * 1000,
                    "execute_verify_ms": (done - approved) * 1000,
                    "total_ms": (done - start) * 1000,
                }
            )
    report = {
        "mode": "local demo, persistent local records only",
        "url": args.url,
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runs": rows,
        "median_ms": {key: statistics.median(r[key] for r in rows) for key in rows[0]},
        "limitations": "Sequential warm local HTTP measurements; excludes human approval time, external providers and voice.",
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
