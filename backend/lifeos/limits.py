"""Single-worker ingress and paid voice-operation budgets."""

import asyncio
import time
from collections import deque
from contextlib import asynccontextmanager

from fastapi import HTTPException
from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    """Bound actual bytes before framework JSON/multipart parsing, including chunked requests."""

    def __init__(self, app, maximum=12_000_000, timeout=30, concurrency=4):
        self.app, self.maximum, self.timeout = app, maximum, timeout
        self.concurrency, self.active = concurrency, 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        # HTTP requests without body framing cannot carry a body. Keep ordinary
        # health/static GETs available while uploads occupy the admission slots.
        bodyless_read = (
            scope.get("method") in {"GET", "HEAD", "OPTIONS"}
            and headers.get(b"content-length", b"0") == b"0"
            and b"transfer-encoding" not in headers
        )
        if bodyless_read:
            return await self.app(scope, receive, send)
        # No await between checking and reserving: atomic on the API event loop.
        if self.active >= self.concurrency:
            return await JSONResponse(
                {"detail": "RATE_LIMIT_ERROR: upload capacity reached; try again shortly"}, 429
            )(scope, receive, send)
        self.active += 1
        try:
            await self._bounded_request(scope, receive, send)
        finally:
            self.active -= 1

    async def _bounded_request(self, scope, receive, send):
        body = bytearray()

        async def collect():
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return False
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > self.maximum:
                    raise HTTPException(413, "VALIDATION_ERROR: request too large")
                body.extend(chunk)
                if not message.get("more_body", False):
                    return True

        try:
            if not await asyncio.wait_for(collect(), self.timeout):
                return
        except HTTPException as exc:
            return await JSONResponse({"detail": exc.detail}, exc.status_code)(scope, receive, send)
        except TimeoutError:
            return await JSONResponse({"detail": "VALIDATION_ERROR: request body timed out"}, 408)(
                scope, receive, send
            )
        delivered = False

        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            data = bytes(body)
            body.clear()
            return {"type": "http.request", "body": data, "more_body": False}

        await self.app(scope, replay, send)


class VoiceBudget:
    def __init__(self, concurrency=2, per_minute=12):
        self.concurrency, self.per_minute = concurrency, per_minute
        self.active = 0
        self.requests = {}

    @asynccontextmanager
    async def acquire(self, owner):
        # No await between admission check and reservation: atomic on the API event loop.
        now = time.monotonic()
        self.requests = {
            key: deque(t for t in times if t > now - 60)
            for key, times in self.requests.items()
            if times and times[-1] > now - 60
        }
        queue = self.requests.setdefault(owner, deque())
        if self.active >= self.concurrency or len(queue) >= self.per_minute:
            raise HTTPException(429, "RATE_LIMIT_ERROR: voice budget reached; try again shortly")
        queue.append(now)
        self.active += 1
        try:
            yield
        finally:
            self.active -= 1
