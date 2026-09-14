"""Explicit local-data controls. Never exports credentials or browser profiles."""

import json
from typing import Literal

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select

from .security import COOKIE
from .store import Document


class DeletionConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirmation: Literal["DELETE MY DATA"]


def register_privacy(app, db, security, engine, pause_ingestion=None):
    @app.get("/api/privacy/export")
    async def export(request: Request):
        owner = security.require(request)
        async with engine.lock(owner):
            # Explicit allowlist excludes OAuth grants, pending OAuth state and sessions.
            return {kind: db.list(owner, kind) for kind in ("event", "audit", "settings", "usage")}

    @app.post("/api/privacy/disconnect/google")
    async def disconnect(request: Request):
        owner = security.require(request, True)
        if pause_ingestion:
            await pause_ingestion(owner)
        async with engine.lock(owner):
            db.delete(owner, "token", owner + ":token:google")
            db.delete_kind(owner, "oauth")
            db.delete(owner, "integration_check", owner + ":integration_check")
            db.audit(owner, "disconnected", "Google credentials removed from LIFEOS")
        return {
            "status": "disconnected",
            "detail": "Stored Google credentials removed. Manage the provider's separate account permissions in Google.",
        }

    @app.post("/api/privacy/delete")
    async def remove(body: DeletionConfirmation, request: Request, response: Response):
        owner = security.require(request, True)
        if engine.lock(owner).locked():
            raise HTTPException(409, "Wait for the current operation to finish before deleting data")
        if pause_ingestion:
            await pause_ingestion(owner)
        async with engine.lock(owner):
            if any(
                event.get("status") in {"executing", "verifying", "running"}
                or any(
                    action.get("status") in {"executing", "uncertain"}
                    or action.get("compensation_status") in {"executing", "uncertain"}
                    for action in event.get("actions", [])
                )
                for event in db.list(owner, "event")
            ):
                raise HTTPException(
                    409, "Reconcile active or uncertain actions before deleting their evidence"
                )
            with db.sessions.begin() as session:
                sessions = session.scalars(
                    select(Document).where(Document.owner == "system", Document.kind == "session")
                )
                for entry in sessions:
                    if json.loads(entry.data).get("owner") == owner:
                        session.delete(entry)
                session.execute(delete(Document).where(Document.owner == owner))
        response.delete_cookie(COOKIE, path="/")
        return {
            "status": "deleted",
            "detail": "Local workspace records and sessions deleted. External messages, environment credentials and the dedicated WhatsApp profile were not removed.",
        }
