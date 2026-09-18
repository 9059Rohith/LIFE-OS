import asyncio
import json
import secrets
import time
from datetime import UTC, datetime
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .config import Settings
from .store import Database, digest, requires_reconciliation
from .security import Security
from .limits import BodyLimitMiddleware, VoiceBudget
from .engine import Engine
from .telemetry import scope as usage_scope, snapshot as usage_snapshot
from .privacy import register_privacy
from .ingestion import Ingestion
from .app_screens import register_app_screens
from .work import register_work
from .planning import APPS, SCENARIOS, seed
from .schemas import EventInput, DemoInput, ApprovalInput, EditInput, LoginInput, RegistrationInput, DesktopBridgeResult, Preferences, SpeakInput


def create_app(settings=None):
    settings = settings or Settings()
    db = Database(settings.database_url)
    security = Security(db, settings)
    voice_budget = VoiceBudget()
    diagnostic_lock = asyncio.Lock()
    providers = None
    desktop_bridge = None
    cipher = None
    if settings.encryption_key:
        from cryptography.fernet import Fernet

        cipher = Fernet(settings.encryption_key.encode())

    async def token_loader(owner, provider):
        token = db.get(owner, "token", owner + ":token:" + provider)
        return json.loads(cipher.decrypt(token["encrypted"].encode())) if token and cipher else None

    async def token_saver(owner, provider, token):
        if not cipher:
            raise HTTPException(503, "Encryption is not configured")
        db.put(
            owner,
            "token",
            owner + ":token:" + provider,
            {"encrypted": cipher.encrypt(json.dumps(token).encode()).decode()},
        )

    if settings.mode == "live":
        from .providers import LiveProviders

        if settings.whatsapp_bridge_enabled:
            from .desktop_bridge import DesktopBridge

            desktop_bridge = DesktopBridge()
        providers = LiveProviders(settings, token_loader, token_saver, desktop_bridge)
    engine = Engine(db, settings, providers)
    ingestion = Ingestion(db, settings, engine, providers)

    @asynccontextmanager
    async def lifespan(app):
        # A process may have stopped between delivery and read-back. Never send it again automatically.
        from .store import Document
        from sqlalchemy import select

        with db.sessions() as session:
            rows = session.scalars(select(Document).where(Document.kind == "event")).all()
            for row in rows:
                event = json.loads(row.data)
                changed = False
                for action in event["actions"]:
                    if action.get("compensation_status") == "executing":
                        action["compensation_status"] = "uncertain"
                        action["compensation_error"] = (
                            "MANUAL_REVIEW_REQUIRED: process interrupted during Calendar restoration"
                        )
                        changed = True
                    if action["status"] == "executing":
                        action["status"] = "uncertain"
                        action["error"] = (
                            "MANUAL_REVIEW_REQUIRED: process interrupted after durable execution intent"
                        )
                        changed = True
                if changed:
                    event["status"] = "partial_failure"
                    row.data = json.dumps(event)
            session.commit()
        await ingestion.start()
        try:
            yield
        finally:
            await ingestion.close()
            try:
                if providers:
                    await providers.close()
            finally:
                if desktop_bridge:
                    desktop_bridge.close()
                db.engine.dispose()

    app = FastAPI(title="LIFEOS", version="0.1.0", lifespan=lifespan)
    app.state.db = db
    app.state.engine = engine
    app.state.security = security
    app.state.ingestion = ingestion
    app.state.desktop_bridge = desktop_bridge
    register_app_screens(app, settings, security, providers)
    register_work(app, db, security, engine)
    ingestion.register(app, security)
    register_privacy(app, db, security, engine, pause_ingestion=ingestion.pause)
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def headers(request, call_next):
        try:
            if int(request.headers.get("content-length", "0")) > 12_000_000:
                return JSONResponse({"detail": "VALIDATION_ERROR: request too large"}, 413)
        except ValueError:
            return JSONResponse({"detail": "VALIDATION_ERROR: invalid content length"}, 400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'"
        )
        return response

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": settings.mode}

    @app.get("/ready")
    def ready():
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}

    @app.post("/api/desktop/bridge/next")
    async def desktop_bridge_next(request: Request):
        security.require_primary_owner(request, True)
        if not desktop_bridge:
            raise HTTPException(404, "Desktop bridge is unavailable")
        job = await desktop_bridge.next_job()
        return {"job": job}

    @app.post("/api/desktop/bridge/result")
    async def desktop_bridge_result(body: DesktopBridgeResult, request: Request):
        security.require_primary_owner(request, True)
        if not desktop_bridge:
            raise HTTPException(404, "Desktop bridge is unavailable")
        if len(json.dumps(body.result or {})) > 64000:
            raise HTTPException(413, "Desktop bridge result is too large")
        if not desktop_bridge.complete(body.id, body.model_dump(exclude={"id"})):
            raise HTTPException(409, "Desktop job expired")
        return {"status": "accepted"}

    def session_payload(session):
        preferences = engine.settings_for(session["owner"])
        return {
            "user": {"id": session["owner"], "name": preferences["name"]},
            "csrf_token": session["csrf"],
            "mode": settings.mode,
            "voice_available": bool(settings.openai_api_key) and session["owner"] == "owner",
        }

    def require_live_primary_owner(request, mutation=False):
        owner = security.require(request, mutation)
        if settings.mode == "live" and owner != "owner":
            raise HTTPException(403, "AUTHORIZATION_ERROR: primary owner required")
        return owner

    @app.get("/api/session")
    def session(request: Request, response: Response):
        security.rate("session:" + (request.client.host if request.client else "unknown"), 30)
        current = security.session(request)
        if not current:
            if settings.mode != "demo" or settings.public_demo:
                raise HTTPException(401, "AUTHENTICATION_ERROR: sign in required")
            current = security.create(response)
            seed(db, current["owner"])
        return session_payload(current)

    @app.post("/api/auth/login")
    def login(body: LoginInput, request: Request, response: Response):
        security.rate("login:" + (request.client.host if request.client else "unknown"), 5)
        origin = request.headers.get("origin")
        if origin and origin not in settings.allowed_origins:
            raise HTTPException(403, "Origin rejected")
        if settings.mode != "live" and not settings.public_demo:
            raise HTTPException(401, "AUTHENTICATION_ERROR: invalid credentials")
        owner = security.authenticate(body.username, body.password)
        if not owner:
            raise HTTPException(401, "AUTHENTICATION_ERROR: invalid credentials")
        return session_payload(security.create(response, owner))

    @app.post("/api/auth/register")
    def register(body: RegistrationInput, request: Request, response: Response):
        security.rate("register:" + (request.client.host if request.client else "unknown"), 3)
        origin = request.headers.get("origin")
        if origin and origin not in settings.allowed_origins:
            raise HTTPException(403, "Origin rejected")
        account = security.register(body.username, body.password)
        return session_payload(security.create(response, account["owner"]))

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response):
        security.require(request, True)
        from .security import COOKIE

        db.delete("system", "session", security.token_hash(request.cookies.get(COOKIE, "")))
        response.delete_cookie(COOKIE, path="/")
        return {"status": "signed_out"}

    @app.get("/api/events")
    def events(request: Request):
        owner = require_live_primary_owner(request)
        retention = engine.settings_for(owner)["retention_days"] * 86400
        return list(
            reversed(
                [
                    e
                    for e in db.list(owner, "event")
                    if time.time()
                    - __import__("datetime").datetime.fromisoformat(e["created_at"]).timestamp()
                    < retention
                    or requires_reconciliation(e)
                ]
            )
        )

    @app.post("/api/events")
    async def new_event(body: EventInput, request: Request):
        owner = require_live_primary_owner(request, True)
        async with engine.lock(owner):
            return await engine.plan(owner, body.text, body.source, body.simulation)

    @app.get("/api/events/{id}")
    def event(id: str, request: Request):
        return engine.event(require_live_primary_owner(request), id)

    @app.post("/api/demo/reset")
    async def reset(request: Request):
        owner = security.require(request, True)
        if settings.mode != "demo":
            raise HTTPException(403, "Demo is disabled in live mode")
        async with engine.lock(owner):
            seed(db, owner)
            db.delete_kind(owner, "event")
            db.audit(owner, "reset", "Local demo applications reset")
        return {"status": "reset"}

    @app.post("/api/demo/run")
    async def run_demo(body: DemoInput, request: Request):
        owner = security.require(request, True)
        if settings.mode != "demo":
            raise HTTPException(403, "Demo is disabled in live mode")
        async with engine.lock(owner):
            seed(db, owner)
            for event in db.list(owner, "event"):
                if event["status"] not in ["resolved", "compensated"]:
                    event["status"] = "cancelled"
                    engine.save(owner, event)
            return await engine.plan(
                owner, SCENARIOS[body.scenario], "gmail" if body.scenario == "flight" else "discord", False
            )

    @app.post("/api/events/{id}/approve")
    async def approve(id: str, body: ApprovalInput, request: Request):
        owner = require_live_primary_owner(request, True)
        async with engine.lock(owner):
            return engine.approve(owner, engine.event(owner, id), body.action_ids, body.version)

    @app.patch("/api/events/{id}/actions/{action_id}")
    async def edit(id: str, action_id: str, body: EditInput, request: Request):
        owner = require_live_primary_owner(request, True)
        async with engine.lock(owner):
            event = engine.event(owner, id)
            action = next((a for a in event["actions"] if a["id"] == action_id), None)
            if not action:
                raise HTTPException(404, "Action not found")
            if event["status"] in ["resolved", "cancelled", "compensated"] or action["status"] in [
                "verified",
                "uncertain",
                "executing",
            ]:
                raise HTTPException(409, "Executed actions cannot be edited")
            allowed = (
                {"body", "subject"}
                if action["type"] == "send"
                else {"start", "end", "summary"}
                if action["application"] == "calendar"
                else set()
            )
            if set(body.arguments) != set(action["arguments"]) or any(
                body.arguments[k] != action["arguments"][k] for k in action["arguments"] if k not in allowed
            ):
                raise HTTPException(
                    422, "Only message content or calendar time can be edited; targets are policy bound"
                )
            if any(
                not isinstance(body.arguments[k], str) or len(body.arguments[k]) > 8000
                for k in allowed
                if k in body.arguments
            ):
                raise HTTPException(422, "Invalid action content")
            if action["application"] == "calendar":
                from datetime import datetime

                try:
                    start, end = (
                        datetime.fromisoformat(body.arguments["start"]),
                        datetime.fromisoformat(body.arguments["end"]),
                    )
                    if not start.tzinfo or not end.tzinfo or end <= start:
                        raise ValueError()
                except ValueError:
                    raise HTTPException(
                        422, "Calendar times require timezone and positive duration"
                    ) from None
                from zoneinfo import ZoneInfo

                timezone = ZoneInfo(engine.settings_for(owner)["timezone"])
                old_start = datetime.fromisoformat(action["arguments"]["start"]).astimezone(timezone)
                display_start = start.astimezone(timezone)
                action["title"] = f"Move client meeting to {display_start:%H:%M}"
                for dependent in event["actions"]:
                    if (
                        action["id"] in dependent["dependencies"]
                        and dependent["type"] == "send"
                        and dependent["status"] not in ["verified", "uncertain"]
                    ):
                        message = dependent["arguments"]["body"]
                        for fmt in ["%d %b at %H:%M %Z", "%d %b, %H:%M %Z"]:
                            message = message.replace(old_start.strftime(fmt), display_start.strftime(fmt))
                        dependent["arguments"]["body"] = message
                        dependent["arguments_hash"] = digest(dependent["arguments"])
            action["arguments"] = body.arguments
            action["arguments_hash"] = digest(body.arguments)
            engine.invalidate(event)
            engine.log(owner, event, "edited", "Plan edited; all earlier approvals invalidated")
            return engine.save(owner, event)

    @app.post("/api/events/{id}/actions/{action_id}/reject")
    async def reject(id: str, action_id: str, request: Request):
        owner = require_live_primary_owner(request, True)
        async with engine.lock(owner):
            event = engine.event(owner, id)
            action = next((a for a in event["actions"] if a["id"] == action_id), None)
            if not action:
                raise HTTPException(404, "Action not found")
            if action["status"] in ["verified", "uncertain", "executing"]:
                raise HTTPException(409, "Action already executed")
            action["status"] = "rejected"
            engine.invalidate(event)
            engine.log(owner, event, "rejected", "Action rejected; dependent actions will not execute")
            return engine.save(owner, event)

    @app.post("/api/events/{id}/execute")
    @app.post("/api/events/{id}/retry")
    async def execute(id: str, request: Request):
        owner = require_live_primary_owner(request, True)
        async with engine.lock(owner):
            return await engine.execute(owner, engine.event(owner, id), request.url.path.endswith("retry"))

    @app.post("/api/events/{id}/actions/{action_id}/reconcile")
    async def reconcile_action(id: str, action_id: str, request: Request):
        owner = require_live_primary_owner(request, True)
        async with engine.lock(owner):
            return await engine.reconcile(owner, engine.event(owner, id), action_id)

    @app.post("/api/events/{id}/cancel")
    async def cancel(id: str, request: Request):
        owner = require_live_primary_owner(request, True)
        event = engine.event(owner, id)
        event["cancel_requested"] = True
        event["status"] = "cancelled"
        engine.log(
            owner, event, "cancelled", "Cancellation requested; an in-flight provider action may finish"
        )
        return engine.save(owner, event)

    @app.post("/api/events/{id}/apply")
    async def apply(id: str, request: Request):
        owner = require_live_primary_owner(request, True)
        async with engine.lock(owner):
            event = engine.event(owner, id)
            if not event["simulation"]:
                raise HTTPException(409, "Plan is already active")
            event["simulation"] = False
            engine.invalidate(event)
            engine.log(
                owner, event, "applied", "Simulation converted to an active plan; approval is still required"
            )
            return engine.save(owner, event)

    @app.post("/api/events/{id}/undo")
    async def undo(id: str, request: Request):
        owner = require_live_primary_owner(request, True)
        async with engine.lock(owner):
            return await engine.undo(owner, engine.event(owner, id))

    @app.get("/api/demo/apps")
    def apps(request: Request):
        owner = security.require(request)
        if settings.mode != "demo":
            return []
        return [item for item in db.list(owner, "app") if item["application"] in APPS]

    @app.get("/api/settings")
    def preferences(request: Request):
        return engine.settings_for(security.require(request))

    @app.patch("/api/settings")
    def save_preferences(body: Preferences, request: Request):
        owner = security.require(request, True)
        db.put(owner, "settings", owner + ":settings", body.model_dump())
        return body

    @app.get("/api/audit")
    def audit(request: Request):
        return list(reversed(db.list(security.require(request), "audit")))

    @app.get("/api/audit/verify")
    def audit_verify(request: Request):
        entries = db.list(security.require(request), "audit")
        previous = "0" * 64
        for entry in entries:
            if entry["previous_hash"] != previous or entry["hash"] != digest(
                {k: v for k, v in entry.items() if k != "hash"}
            ):
                return {"valid": False, "entries": len(entries)}
            previous = entry["hash"]
        return {"valid": True, "entries": len(entries), "head": previous}

    @app.get("/api/metrics")
    def metrics(request: Request):
        owner = security.require(request)
        events = db.list(owner, "event")
        timings = sorted(
            t["latency_ms"] for e in events for t in e["timeline"] if t.get("latency_ms") is not None
        )
        actions = [a for e in events for a in e["actions"]]
        return {
            "events": len(events),
            "resolved_events": sum(e["status"] == "resolved" for e in events),
            "verified_actions": sum(a["status"] == "verified" for a in actions),
            "failed_actions": sum(a["status"] in ["failed", "uncertain"] for a in actions),
            "tool_calls": sum(a.get("attempts", 0) for a in actions),
            "latency_ms": {
                p: timings[min(len(timings) - 1, int(len(timings) * n))] if timings else None
                for p, n in [("p50", 0.5), ("p95", 0.95), ("p99", 0.99)]
            },
            "samples": len(timings),
            "mode": settings.mode,
            "model_token_usage": usage_snapshot(db, owner),
        }

    @app.get("/api/integrations")
    async def integrations(request: Request):
        owner = require_live_primary_owner(request)
        google = bool(await token_loader(owner, "google"))
        snapshot = db.get(owner, "integration_check", owner + ":integration_check")
        fresh = bool(snapshot and 0 <= time.time() - snapshot.get("checked_at", 0) < 86400)
        checked = {item["id"]: item for item in snapshot.get("results", [])} if fresh else {}
        configured = {
            "gmail": google,
            "calendar": google,
            "drive": google,
            "discord": bool(settings.discord_bot_token and settings.discord_channel_id),
            "whatsapp": settings.whatsapp_enabled or bool(desktop_bridge),
        }
        return [
            {
                "id": key,
                "name": name,
                "status": "local_demo"
                if settings.mode == "demo"
                else "needs_attention"
                if key == "whatsapp" and desktop_bridge and not desktop_bridge.connected
                else checked[key]["status"]
                if configured[key] and key in checked
                else "configured_unverified"
                if configured[key]
                else "not_connected",
                "mode": settings.mode,
                "description": "Persistent local application records; no third-party account accessed."
                if settings.mode == "demo"
                else "Open the signed-in LIFEOS desktop app to connect WhatsApp actions."
                if key == "whatsapp" and desktop_bridge and not desktop_bridge.connected
                else "Last checked "
                + datetime.fromtimestamp(snapshot["checked_at"], UTC).strftime("%Y-%m-%d %H:%M UTC")
                + ". "
                + checked[key]["description"]
                if configured[key] and key in checked
                else "Credentials present; live access requires provider verification."
                if configured[key]
                else "Connect an authorized account to use this integration.",
            }
            for key, name in APPS.items()
        ]

    @app.post("/api/integrations/check")
    async def check_integrations(request: Request):
        from .diagnostics import connection_checks

        owner = require_live_primary_owner(request, True)
        security.rate("provider-check:" + owner, 3)
        if diagnostic_lock.locked():
            raise HTTPException(429, "A connection check is already running; wait for its result")
        async with diagnostic_lock:
            results = await connection_checks(settings, providers, owner)
            if settings.mode == "live":
                db.put(
                    owner,
                    "integration_check",
                    owner + ":integration_check",
                    {"checked_at": time.time(), "results": results},
                )
            return results

    @app.get("/api/integrations/google/connect")
    async def connect(request: Request):
        owner = require_live_primary_owner(request)
        if settings.mode != "live" or not settings.google_client_id:
            raise HTTPException(409, "Google OAuth requires live mode and configured credentials")
        security.rate("oauth-connect:" + owner, 5)
        from .oauth import create_pkce, authorization_url

        verifier, challenge = create_pkce()
        state = secrets.token_urlsafe(32)
        db.put("system", "oauth_state", digest(state), {
            "owner": owner, "verifier": verifier, "expires": time.time() + 600,
        })
        return {"url": authorization_url(settings, state, challenge)}

    @app.get("/api/integrations/google/callback")
    async def callback(request: Request, code: str = "", state: str = ""):
        security.rate("oauth-callback:" + (request.client.host if request.client else "unknown"), 15)
        if not code or not state or len(state) > 256:
            raise HTTPException(403, "OAuth state invalid or expired")
        pending = db.consume("system", "oauth_state", digest(state))
        if not pending or pending["expires"] < time.time():
            raise HTTPException(403, "OAuth state invalid or expired")
        owner = pending["owner"]
        from .oauth import exchange_code

        try:
            token = await exchange_code(settings, code, pending["verifier"])
            await token_saver(owner, "google", token)
            db.delete(owner, "integration_check", owner + ":integration_check")
        except Exception:
            raise HTTPException(502, "AUTHENTICATION_ERROR: Google authorization failed") from None
        callback_session = security.session(request)
        if callback_session and callback_session["owner"] == owner:
            return RedirectResponse("/?integration=google")
        return HTMLResponse(
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<title>Google connected to LIFEOS</title>"
            "<body><h1>Google connected to LIFEOS</h1>"
            "<p>You can return to the LIFEOS desktop window.</p></body></html>"
        )

    @app.post("/api/voice/transcribe")
    async def transcribe(request: Request, audio: UploadFile = File(...)):
        owner = require_live_primary_owner(request, True)
        if not settings.openai_api_key:
            raise HTTPException(503, "TRANSCRIPTION_ERROR: configure OpenAI voice access")
        data = await audio.read(12_000_001)
        if len(data) > 12_000_000 or len(data) < 16:
            raise HTTPException(422, "Audio must be between 16 bytes and 12 MB")
        from .ai import transcribe

        try:
            async with voice_budget.acquire(owner):
                with usage_scope(db, owner):
                    result = await asyncio.wait_for(
                        transcribe(data, audio.filename or "audio.webm", settings.openai_api_key), 45
                    )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502, "TRANSCRIPTION_ERROR: provider could not transcribe audio") from None
        return {"text": result}

    @app.post("/api/voice/speak")
    async def speak(body: SpeakInput, request: Request):
        owner = require_live_primary_owner(request, True)
        if not settings.openai_api_key:
            raise HTTPException(503, "TTS_ERROR: configure OpenAI voice access")
        from .ai import speak

        try:
            async with voice_budget.acquire(owner):
                with usage_scope(db, owner):
                    data = await asyncio.wait_for(speak(body.text, settings.openai_api_key), 45)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502, "TTS_ERROR: provider could not synthesize speech") from None
        return Response(data, media_type="audio/mpeg", headers={"X-AI-Generated": "true"})

    @app.get("/{path:path}")
    def frontend(path: str):
        root = Path(settings.static_dir).resolve()
        candidate = (root / path).resolve()
        if path.startswith("api/") or not candidate.is_relative_to(root):
            raise HTTPException(404, "Not found")
        if candidate.is_file():
            return FileResponse(candidate)
        if (root / "index.html").exists():
            return FileResponse(root / "index.html")
        return {"service": "LIFEOS API", "frontend": "Run npm dev server or build frontend/dist"}

    return app


app = create_app()
