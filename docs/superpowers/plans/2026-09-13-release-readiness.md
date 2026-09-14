# LIFEOS release readiness implementation plan

> **For agentic workers:** Use parallel, bounded implementation and review tasks, preserving the running local instance and private credentials.

**Goal:** Verify the supplied providers, fix concrete release defects, make connection failures actionable in the product, and publish a full application when an available hosting entitlement supports it.

**Architecture:** Preserve the single-owner FastAPI/React application and approval-based execution. Provider checks are read-only, authenticated and bounded. Cloud hosting must run both API and frontend with durable storage; the enrolled desktop WhatsApp profile remains local.

**Tech stack:** FastAPI, SQLAlchemy, React/TypeScript, Playwright, Docker/PostgreSQL.

**Spec:** `docs/REQUIREMENTS.md`; live evidence in `docs/PROVIDER_RELEASE_CHECK.md`.

## Constraints

- No fabricated provider success or completion percentages.
- Do not send messages or edit calendars during connection tests.
- Preserve existing database volumes, credentials and WhatsApp enrollment.
- Do not activate a paid hosting subscription or attach billing without authorization.
- External provider access and live hero acceptance remain release gates.

## Tasks and verification

- [x] Check the actual Maps key, native database Google grant and Discord channel. Record only status and allowlisted error reasons. Command: `.venv/Scripts/python scripts/check_release_integrations.py`.
- [x] Enforce actual request byte limits before multipart parsing, including chunked uploads and aggregate admission; bound paid voice calls. Regression tests passed.
- [x] Filter live calendar context using explicit event identifiers and dates; preserve clarification for ambiguous identities and calendar collisions.
- [x] Add authenticated in-app diagnostics with safe provider results and independent bounded admission.
- [x] Assess authenticated hosting and attempt free provisioning. Railway refused new resources; no public URL or paid upgrade. Record requirements in PRODUCTION_HOSTING.md.
- [x] Add opt-in bounded Gmail/Discord ingestion, safe live Calendar update compensation, local data controls, protected reconciliation evidence and actual usage aggregates.
- [x] Run backend tests (96 passed), typecheck/lint/build, packaged browser workflows (8 passed), PostgreSQL restore and local benchmark. Restart local API preserving its database/profile.
- [x] Record exact account-side and scope limitations in RELEASE_STATUS.md. Full live cross-app acceptance remains blocked.

## Evidence so far

Maps: key is supplied but Routes returns `API_KEY_SERVICE_BLOCKED`; route addresses are absent. Google: no owner OAuth grant in the actual live PostgreSQL database. Discord: bot authentication succeeds but configured channel returns 403. WhatsApp: saved visible-browser login verified; exact configured recipient has no match. OpenAI extraction/STT/TTS passed in the prior live check. These are account/configuration blockers, not passing acceptance tests.
