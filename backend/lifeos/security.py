import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque
from sqlalchemy.exc import IntegrityError
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

    @staticmethod
    def user_id(username):
        return "user:" + username

    @staticmethod
    def password_hash(password, salt=None):
        salt = salt or secrets.token_bytes(16)
        encoded = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=64)
        return "scrypt$16384$8$1$" + salt.hex() + "$" + encoded.hex()

    @staticmethod
    def password_matches(password, encoded):
        try:
            algorithm, n, r, p, salt, expected = encoded.split("$")
            if algorithm != "scrypt" or (n, r, p) != ("16384", "8", "1"):
                return False
            actual = hashlib.scrypt(
                password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=64
            )
            return hmac.compare_digest(actual, bytes.fromhex(expected))
        except (AttributeError, TypeError, ValueError):
            return False

    def register(self, username, password):
        if not self.settings.user_registration:
            raise HTTPException(404, "User registration is disabled")
        username = username.lower()
        if username == "owner":
            raise HTTPException(409, "Username is unavailable")
        account = {
            "username": username,
            "owner": self.user_id(username),
            "password_hash": self.password_hash(password),
            "created_at": time.time(),
        }
        try:
            from .store import Document

            with self.db.sessions.begin() as session:
                session.add(
                    Document(
                        id=self.user_id(username),
                        owner="system",
                        kind="user",
                        data=json.dumps(account),
                    )
                )
        except IntegrityError:
            raise HTTPException(409, "Username is unavailable") from None
        return account

    def authenticate(self, username, password):
        if username in (None, "owner"):
            return "owner" if hmac.compare_digest(password, self.settings.auth_password) else None
        account = self.db.get("system", "user", self.user_id(username))
        if not account or not self.password_matches(password, account.get("password_hash")):
            return None
        return account["owner"]

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

    def require_primary_owner(self, request, mutation=False):
        owner = self.require(request, mutation)
        if owner != "owner":
            raise HTTPException(403, "AUTHORIZATION_ERROR: primary owner required")
        return owner
