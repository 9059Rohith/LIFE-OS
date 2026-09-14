"""Owner-scoped aggregate measurements; no prompts, credentials or recordings."""

from contextlib import contextmanager
from contextvars import ContextVar

_scope = ContextVar("lifeos_measurement_scope", default=None)


@contextmanager
def scope(db, owner):
    token = _scope.set((db, owner))
    try:
        yield
    finally:
        _scope.reset(token)


def snapshot(db, owner):
    return db.get(owner, "usage", owner + ":usage") or {
        "requests": 0,
        "failed_requests": 0,
        "usage_reported_requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "latency_ms_total": 0.0,
        "audio_input_bytes": 0,
        "audio_output_bytes": 0,
        "reported_audio_seconds": 0.0,
    }


def record(endpoint, latency_ms, success, usage=None, input_bytes=0, output_bytes=0):
    current = _scope.get()
    if current is None:
        return
    db, owner = current
    measured = snapshot(db, owner)
    measured["requests"] += 1
    measured["failed_requests"] += int(not success)
    measured["latency_ms_total"] += round(latency_ms, 2)
    measured["audio_input_bytes"] += input_bytes
    measured["audio_output_bytes"] += output_bytes
    if isinstance(usage, dict):
        reported = False
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = usage.get(key)
            if type(value) is int and 0 <= value < 1_000_000_000:
                measured[key] += value
                reported = True
        seconds = usage.get("seconds")
        if type(seconds) in (int, float) and 0 <= seconds <= 86400:
            measured["reported_audio_seconds"] += seconds
            reported = True
        measured["usage_reported_requests"] += int(reported)
    db.put(owner, "usage", owner + ":usage", measured)
