import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from fastapi import HTTPException

COOKIE = "lifeos_session"


class Security:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings
        self.requests = defaultdict(deque)

    def rate(self, key, limit=None):
        queue = self.requests[key]
        now = time.monotonic()
        while queue and queue[0] < now - 60:
            queue.popleft()
        if len(queue) >= (limit or self.settings.rate_limit):
            raise HTTPException(429, "RATE_LIMIT_ERROR: wait before trying again")
        queue.append(now)

    def token_hash(self, token):
        return hashlib.sha256(token.encode()).hexdigest()

    def session(self, request):
        token = request.cookies.get(COOKIE, "")
        session = self.db.get("system", "session", self.token_hash(token)) if token else None
        if not session or session["expires"] < time.time():
            return None
        return session

    def create(self, response, owner=None):
        self.db.prune_sessions()
        token = secrets.token_urlsafe(32)
        session = {
            "owner": owner or secrets.token_hex(16),
            "csrf": secrets.token_urlsafe(32),
            "expires": time.time() + self.settings.session_seconds,
        }
        self.db.put("system", "session", self.token_hash(token), session)
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            secure=self.settings.environment == "production",
            samesite="lax",
            max_age=self.settings.session_seconds,
            path="/",
        )
        return session

    def require(self, request, mutation=False):
        session = self.session(request)
        if not session:
            raise HTTPException(401, "AUTHENTICATION_ERROR: sign in required")
        self.rate(session["owner"])
        if mutation:
            origin = request.headers.get("origin")
            if origin and origin not in self.settings.allowed_origins:
                raise HTTPException(403, "AUTHORIZATION_ERROR: origin rejected")
            if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), session["csrf"]):
                raise HTTPException(403, "AUTHORIZATION_ERROR: CSRF token required")
        return session["owner"]
