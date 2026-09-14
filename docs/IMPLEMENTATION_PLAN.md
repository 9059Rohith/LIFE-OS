# LIFEOS implementation plan

**Goal:** Deliver a runnable event → consequence → approval → execution → verification product, with an honest local demo and separately configured live providers.
**Architecture:** React/TypeScript/Vite frontend, FastAPI/Pydantic backend, SQLAlchemy persistence (SQLite locally, PostgreSQL in deployment), explicit provider boundary and durable state machine. Server-side policy owns mutations; models only propose typed event data.
**Spec:** [Original requirements](REQUIREMENTS.md).

## Decisions
- Empty workspace: create a new repository without replacing existing code.
- User explicitly requested autonomous execution without questions; design and implementation choices proceed under that authorization.
- Demo uses clearly labeled, persistent local application records, not fake provider success. Live operations require configured credentials and application approval.
- Single backend process initially, durable database state, bounded execution and restart reconciliation. Production must not advertise untested provider access.
- Use direct Responses structured output for narrow extraction; explicit orchestration is simpler to audit than autonomous mutation tools. Chained voice shares the same approval path. Realtime conversational mode is optional, not an approval bypass.

## Work packages
- [x] Backend: strict schemas, migrations, session authentication, CSRF/origin protections, rate limits, owner-scoped storage, graph planning, deterministic risk and approval hashes, execution idempotency, read-back verification, partial failure, cancellation, retry, simulation, compensation, audit chain, metrics. Tests cover hero, meeting, injection, stale approval, duplicate execution and ownership.
- [x] Providers: real Google OAuth and Gmail/Calendar/Drive clients, Discord, Maps, controlled WhatsApp browser worker, configurable OpenAI extraction/STT/TTS. Contract tests use HTTP fixtures; live status remains unverified until credentials are supplied.
- [x] Frontend: premium command center, event feed, graph, editable approval center, activity/evidence, local application viewer, integrations and settings, text/upload/voice inputs, accessible responsive states.
- [x] Deployment: pinned dependencies, Docker/Compose PostgreSQL, health/readiness, CI lint/typecheck/test/security/build/E2E gates, environment template, scripts, documentation and deployment checklist.
- [x] Verification: execute real local hero and meeting pipelines in browser, inspect responsive rendering, adversarial tests, collect actual performance, document credential-dependent gaps.

## Shared API contract
All routes `/api`. Cookies for session; GET `/session` creates demo user or returns 401 in live mode; response `{user:{id,name},csrf_token,mode,voice_available}`. Mutation header `X-CSRF-Token`. POST `/auth/login` `{password}` for configured single-owner live login.
GET `/events` returns array; POST `/events` `{text,simulation:false,source:"text"}` returns event detail. POST `/demo/run` `{scenario:"flight"|"meeting"}` resets owner demo records and returns new planned event. POST `/demo/reset` resets.
Event detail: `{id,title,event_type,source,status,created_at,version,summary,simulation,entities,actions,context,timeline}`.
Action: `{id,application,type,title,reason,target,arguments,risk,status,requires_approval,reversible,dependencies,evidence,error,arguments_hash}`.
Timeline: `{id,timestamp,stage,message,application,latency_ms}`. Context: array `{application,title,detail}`.
GET `/events/{id}`; POST `/events/{id}/approve` `{action_ids,version}`; POST `/events/{id}/execute`; POST `/events/{id}/cancel`; POST `/events/{id}/retry`; POST `/events/{id}/apply`; POST `/events/{id}/undo`; PATCH `/events/{id}/actions/{action_id}` `{arguments}`; POST `/events/{id}/actions/{action_id}/reject`.
GET `/integrations` array `{id,name,status,mode,description}`. GET `/demo/apps` array `{application,records}`. GET `/audit` array. GET `/metrics` object. GET/PATCH `/settings` `{name,timezone,retention_days}`. POST `/voice/transcribe` multipart `audio` → `{text}`; POST `/voice/speak` `{text}` → audio/mpeg. GET `/integrations/google/connect` → `{url}`; GET callback redirects.
Backend may add fields, but coordinate contract changes before frontend integration.

## Provider module contract
`backend/lifeos/providers.py`: `LiveProviders(settings, token_loader, token_saver)` where loader/saver callable awaitable (user_id, provider[, token_dict]); async `context(user_id,text)->list[dict]`; async `execute(user_id,action:dict,idempotency_key:str)->dict`; async `verify(user_id,action:dict,result:dict)->dict` returns `{verified:bool,detail:str,...}`; async `close()`.
`backend/lifeos/ai.py`: `extract_event(text, api_key, model, timezone)->dict`, `transcribe(data:bytes,filename:str,api_key:str)->str`, `speak(text,api_key)->bytes`.
`backend/lifeos/oauth.py`: standalone PKCE helpers and OAuth exchange/refresh utilities. Backend mounts endpoints and persists encrypted credentials.
Settings attributes: `openai_api_key`, `openai_model`, `google_client_id`, `google_client_secret`, `google_redirect_uri`, `discord_bot_token`, `discord_channel_id`, `google_maps_api_key`, `whatsapp_enabled`, `whatsapp_profile_dir`, `whatsapp_contact`, `mode`.

## Evidence policy
Never mark live third-party or hardware microphone checks passed using local fixture tests. Final status distinguishes implemented, locally verified, and externally unverified.

## Acceptance outcome
Local implementation and verification work packages completed. Full live-account acceptance remains unverified; see [VERIFICATION.md](VERIFICATION.md) for implemented scope, measured checks and remaining original-brief gaps.
