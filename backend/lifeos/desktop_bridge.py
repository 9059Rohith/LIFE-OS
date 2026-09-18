"""Short-lived, owner-scoped jobs for the signed-in desktop provider view.

Jobs live only in this single backend process. A restart during a send leaves the
engine's durable intent uncertain, so it can never trigger an automatic replay.
"""

import asyncio
import secrets
import time

from .providers import ProviderError


class DesktopBridge:
    def __init__(self):
        self._jobs = asyncio.Queue(maxsize=4)
        self._waiting = {}
        self._delivery_lock = asyncio.Lock()
        self._active_id = None
        self._active_done = asyncio.Event()
        self._active_done.set()
        self._uncertain_send_id = None
        self._last_poll = 0.0
        self._closed = False

    @property
    def connected(self):
        return not self._closed and self._uncertain_send_id is None and time.monotonic() - self._last_poll < 15

    def _finish_active(self, job_id):
        if self._active_id == job_id:
            self._active_id = None
            self._active_done.set()

    async def next_job(self, timeout=10):
        if self._closed:
            return None
        self._last_poll = time.monotonic()

        async def take_job():
            async with self._delivery_lock:
                while not self._closed:
                    if self._active_id is not None:
                        await self._active_done.wait()
                        continue
                    job = await self._jobs.get()
                    if job["id"] not in self._waiting:
                        continue
                    self._active_id = job["id"]
                    self._active_done.clear()
                    return job
                return None

        try:
            job = await asyncio.wait_for(take_job(), timeout)
        except TimeoutError:
            return None
        self._last_poll = time.monotonic()
        return job

    async def request(self, operation, payload, timeout=24):
        if not self.connected:
            raise ProviderError("Open the LIFEOS desktop app before using WhatsApp", "BROWSER_UNAVAILABLE")
        if self._closed or self._jobs.full():
            raise ProviderError("Desktop WhatsApp bridge is busy", "BROWSER_UNAVAILABLE")
        job_id = secrets.token_urlsafe(24)
        future = asyncio.get_running_loop().create_future()
        self._waiting[job_id] = future
        job = {"id": job_id, "operation": operation, "payload": payload}
        try:
            self._jobs.put_nowait(job)
            answer = await asyncio.wait_for(future, timeout)
        except TimeoutError as exc:
            raise ProviderError("Desktop WhatsApp operation timed out", "BROWSER_AUTOMATION_ERROR", operation == "send") from exc
        finally:
            self._waiting.pop(job_id, None)
            if self._active_id == job_id:
                if operation == "send" and future.cancelled() and not self._closed:
                    # The desktop may still be sending. Wait for its late result
                    # before allowing another job to touch the same provider view.
                    self._uncertain_send_id = job_id
                else:
                    self._finish_active(job_id)
        if not answer.get("ok"):
            code = answer.get("error_code")
            if code not in {"AUTHENTICATION_ERROR", "AUTHORIZATION_ERROR", "CONFLICT_DETECTED", "BROWSER_AUTOMATION_ERROR", "VERIFICATION_ERROR"}:
                code = "BROWSER_AUTOMATION_ERROR"
            raise ProviderError("Desktop WhatsApp operation failed", code, operation == "send" and answer.get("attempted", False))
        return answer.get("result") or {}

    def complete(self, job_id, answer):
        if self._active_id != job_id:
            return False
        future = self._waiting.get(job_id)
        if not future or future.cancelled():
            if self._uncertain_send_id == job_id or (future and future.cancelled()):
                self._uncertain_send_id = None
                self._finish_active(job_id)
                self._last_poll = time.monotonic()
            return False
        if future.done():
            return False
        self._last_poll = time.monotonic()
        future.set_result(answer)
        return True

    def close(self):
        self._closed = True
        self._active_done.set()
        for future in self._waiting.values():
            if not future.done():
                future.set_exception(ProviderError("Desktop disconnected", "BROWSER_UNAVAILABLE", True))
        self._waiting.clear()
