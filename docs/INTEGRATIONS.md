# Live integrations

LIFEOS keeps local demo records separate from real provider adapters. Set `LIFEOS_MODE=live` only after configuring the owner password, encryption key, allowed origins and provider credentials. Missing configuration fails explicitly. A configured integration is **not** proof that account access or delivery has been tested.

## Google

1. Create a Google Cloud project and enable Gmail API, Calendar API and Drive API.
2. Configure OAuth consent, add your test account, and create a Web application OAuth client.
3. Set `LIFEOS_GOOGLE_CLIENT_ID`, `LIFEOS_GOOGLE_CLIENT_SECRET`, and `LIFEOS_GOOGLE_REDIRECT_URI`. The redirect must exactly match the registered URI (the local `.env.example` uses `http://localhost:8010/api/integrations/google/callback`; match your actual API port).
4. Start LIFEOS, sign in, and choose Connect Google in Integrations.

The server uses authorization code exchange, S256 PKCE, offline access, and refresh-token preservation. The API layer must bind a short-lived single-use state to the authenticated session; provider helpers do not implement session storage. The backend persists tokens encrypted, never in browser local storage.

Scopes: `gmail.readonly`, `gmail.compose`, `calendar.events`, and `drive.readonly`. Public distribution may require Google verification and additional requirements for restricted Gmail scopes. Request the scopes appropriate to the deployment. [Google OAuth guidance](https://developers.google.com/identity/protocols/oauth2/web-server), [security guidance](https://developers.google.com/identity/protocols/oauth2/resources/best-practices).

Gmail searches recent mail and reads message content, creates RFC MIME messages/drafts, sends mail, and fetches provider state afterward. Recipient identity comes from server-validated context; editable action arguments cannot grant recipient authority. Read-back compares Message-ID, recipient, subject, body, attachment content hash and sent status. Text/Google Docs proposal attachments are exported as `.txt`; native PDF/DOCX rendering is not implemented. A deterministic Message-ID aids manual reconciliation but is **not** a Gmail idempotency guarantee. Timeouts and malformed successful send responses require manual review; do not blindly retry. [Gmail send format](https://developers.google.com/workspace/gmail/api/guides/sending).

Calendar lists the next 30 days, creates events with deterministic IDs, patches existing events with `If-Match`, and cancels events conditionally. The patch allowlist includes title, time, description and location. It does not replace attendees, recurrence or conference data. Read-back checks changed fields plus preserved identity/conference/recurrence. A stale etag invalidates execution and requires planning and approval again. Updating an expanded recurring instance preserves its series reference. Calendar mutations request attendee notifications with `sendUpdates=all`. [Conditional resource versions](https://developers.google.com/calendar/api/guides/version-resources), [event patch](https://developers.google.com/workspace/calendar/api/v3/reference/events/patch).

Drive searches file metadata and reads permitted plain-text files or exports Google Docs to text, respecting `canDownload`. Configure `LIFEOS_DRIVE_PROPOSAL_FILE_ID` with the exact intended proposal ID, or provide exactly one readable file matching “proposal” in Drive search. Planning records a SHA-256 content hash; preflight and send each require that content to remain unchanged. Text documents are bounded to 50 KB and oversized files fail explicitly rather than being silently truncated. Other binary documents fail with an explicit unsupported-format error. The adapter does not change Drive files or permissions. [Drive downloads and exports](https://developers.google.com/workspace/drive/api/guides/manage-downloads).

## Discord

Create a bot, install it in the intended server, and grant View Channel, Read Message History and Send Messages in one selected channel. Configure `LIFEOS_DISCORD_BOT_TOKEN` and `LIFEOS_DISCORD_CHANNEL_ID`. Reading message content may require the Message Content privileged intent in the developer portal.

The adapter reads recent channel messages, sends only to the configured channel, suppresses all mentions with `allowed_mentions`, and verifies message content through GET. Sends use a deterministic nonce and `enforce_nonce`; Discord's bounded nonce window does not replace the durable application execution ledger. [Discord message API](https://docs.discord.com/developers/resources/message).

## Maps

Maps is optional. With no key/route context, live flight plans can still propose independently supported calendar and notification changes. They explicitly omit route calculations and pickup-time messages, expose no calculated home departure time, and show a limitation banner. Conflict checks then cover the known flight and the two-hour airport check-in window only; the user must assess travel time separately. Meeting workflows do not require Maps.

Enable Routes API and billing, restrict the server API key appropriately, and set `LIFEOS_GOOGLE_MAPS_API_KEY`, `LIFEOS_MAPS_ORIGIN` (your actual departure address), and `LIFEOS_MAPS_DESTINATION` (your actual airport). Route requests use `computeRoutes`, DRIVE, TRAFFIC_AWARE, and a field mask for duration and distance. Context records the real returned travel duration rounded upward to minutes. Execution recalculates the route; if traffic exceeds the approved travel budget, verification fails and dependent notifications stop pending a fresh plan. Missing addresses or credentials fail. Returned route data is evidence of a read-only computation, not a booking or provider mutation. [Routes request reference](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes).

For a live flight scenario, the connected primary calendar must contain exactly one matching flight number with explicit start/end times, plus one identifiable affected client meeting with an attendee whose email matches a recent Gmail sender. Flight duration comes from the existing flight calendar record; LIFEOS does not fabricate flight schedules or fetch airline operations data. It assumes the original scheduled flight duration remains applicable after the reported departure change and exposes the proposed arrival for approval. The two-hour airport buffer is a planning policy, not a provider observation. Missing/ambiguous travel or client records require clarification. For a meeting scenario requesting a proposal, configure the exact approved proposal file as above.

## WhatsApp browser worker

For the enrolled local Windows session, set `LIFEOS_WHATSAPP_HEADLESS=false` and use the desktop runtime documented in [LOCAL_LIVE.md](LOCAL_LIVE.md). The saved login was verified in that browser; headless Chromium was rejected by WhatsApp. No user-agent spoofing or browser-detection bypass is used. The worker accepts both the older and current English search labels and still requires an exact, unique contact match.

This opt-in worker requires a dedicated local Chromium profile and one operator-configured conversation. Set `LIFEOS_WHATSAPP_ENABLED=true`, `LIFEOS_WHATSAPP_PROFILE_DIR=.private/whatsapp`, and `LIFEOS_WHATSAPP_CONTACT` to its exact display name. Install Chromium with `python -m playwright install chromium`. Use `python scripts/whatsapp_login.py` to sign in manually to the dedicated profile, then close the enrollment browser before running the worker. The operator must choose the intended conversation and avoid duplicate contact names.

The worker supports the English WhatsApp Web UI. It uses accessible search/composer/send locators, verifies the exact conversation header, refuses to overwrite existing drafts, tracks new outgoing message IDs, and checks sent indicators afterward. Limited structural selectors identify conversation containers and message records; UI changes fail closed. The profile is a credential and must remain private, excluded from version control, and used by a single worker. This implementation is a single-owner, single-process deployment; do not share a profile between tenants or concurrent server instances.

No QR solving, login bypass, stealth browser behavior, cookie export or unsolicited login automation is included. Failed identity checks stop before sending. Errors after a send click are uncertain and must be reconciled before another send. Live WhatsApp browser behavior and service suitability must be tested using the operator's authorized account. Browser fixtures do not prove that the current WhatsApp Web DOM matches these locators.

## OpenAI extraction and voice

Set `LIFEOS_OPENAI_API_KEY`; `LIFEOS_OPENAI_MODEL` defaults to `gpt-4.1-mini` and can be changed to an accessible Responses model supporting structured outputs. Server HTTP requests use strict JSON-schema output, `store=false`, bounded input/output, and Pydantic validation. Extraction has no mutation tools. Untrusted text cannot grant authority, and incomplete/refused output fails explicitly.

Voice uses `gpt-4o-mini-transcribe` followed by the same event/approval pipeline and `gpt-4o-mini-tts` with the `coral` voice. STT accepts bounded audio uploads; TTS returns MP3. Generated speech must be identified as AI-generated in the UI. This is chained voice, not a Realtime session. Microphone capture, actual transcription quality, paid model access and speaker playback require live-device/account checks. [Structured outputs](https://platform.openai.com/docs/guides/structured-outputs), [speech to text](https://platform.openai.com/docs/guides/speech-to-text), [text to speech](https://platform.openai.com/docs/guides/text-to-speech).

## Provider boundary and tests

`LiveProviders.execute()` is internal to the engine. Every call requires engine-injected `_authorized=True`; Gmail additionally requires `_validated_recipients` derived from original server context. These fields must never be accepted from client JSON. The engine calls read-only `preflight()` to check all selected Calendar etags and proposal content hashes before any mutation; each Calendar patch also retains its atomic `If-Match` check. The engine owns approval hashes, version validation, ownership, dependencies, the durable execution ledger and restart reconciliation. Provider results do not grant authorization.

Read requests have bounded retries; mutation requests have a single attempt. `ProviderError.uncertain` flags ambiguous side effects. A failed verification must never be reported as successful completion. Live adapters refuse to execute in demo mode.

Run `python -m playwright install chromium` followed by `python -m pytest tests/providers -q`. The suite includes two actual Chromium tests against a local DOM fixture for WhatsApp outgoing-message identity/read-back and existing-draft preservation. HTTP fixtures exercise request formats, authorization, stale etags, preflight checks, real route duration normalization, changed route budgets, attachment hash mismatch, OAuth refresh, OpenAI output/refusal, and uncertain sends without contacting external providers. These tests verify local adapter behavior only. Real OAuth consent, Gmail delivery, Calendar invitations, Discord bot permissions, Routes billing, WhatsApp browser sessions and OpenAI speech remain externally unverified until exercised with configured accounts.
