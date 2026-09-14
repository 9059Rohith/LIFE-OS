# LIFEOS release status — updated 14 September 2026

A password-protected [public demo](PUBLIC_DEMO_RELEASE.md) is now running at https://lifeos-public-production.up.railway.app. The earlier live-account application was run locally at http://localhost:8010 and a Docker image exists as `lifeos:release`. This is **not a 100% accepted live production release**: the public service uses demo providers, while live cross-app acceptance and the original full brief still have outstanding capabilities documented below. Earlier percentage estimates were informal and must not be treated as measured completion.

## Changes verified in this release

- Actual upload byte enforcement, including chunked multipart, with a 30-second deadline and four concurrent body-bearing requests.
- Two concurrent paid voice calls maximum and a separate per-owner voice rate budget.
- Conservative calendar/date/title/flight matching. Busy calendar context is retained; conflicting proposed meeting slots require clarification.
- Missing dates are not silently interpreted as today. Truncated calendar context and ambiguous identities fail closed.
- Gmail thread identity is preserved separately from message identity. Update emails are new messages; original-thread replies are not implemented.
- The Integrations screen now checks actual API read access, presents safe corrective guidance, and avoids blocking the execution lock.
- Opt-in Gmail/Discord monitoring now creates approval-required plans with durable deduplication and bounded polling; it remains disabled on the live account.
- Verified Calendar updates now support conditional, journaled undo with separate read-back evidence and restart-safe uncertain-state handling.
- Settings now includes credential-free export, Google disconnection and explicitly confirmed owner-scoped local-data deletion. Uncertain action evidence survives retention/deletion attempts. Aggregate OpenAI usage records only actual returned usage and measured timing/bytes.
- 101 backend/provider tests passed; whole-backend mypy passed for 20 modules (not strict annotation coverage); strict checks for config/schemas/policy passed. Ruff, frontend lint and production build passed.
- An earlier release-check image passed 8 Chromium browser tests (24 seconds), including hero execution, voice fixtures, monitoring controls, export controls, approval safety and mobile layout. The refreshed `lifeos:release` image built successfully with the unified connected workspace and passed a module-import smoke check; its image ID is `sha256:55a471488ebfebd2e37c0d580c80dbeae66b7a125583ce5200c075c7cd8b0330`.
- Python dependency audit found no known vulnerabilities (the local unpublished package cannot be looked up); frontend production dependency audit found none. Source credential-pattern scan passed.
- Current live browser login and connection diagnostics passed. The later explicitly authorized Discord and WhatsApp test messages are documented below; no calendar mutation was sent.
- Local PostgreSQL dump/restore into a fresh isolated database passed with document count and schema revision preserved; only the temporary test database was removed afterward.
- Three warm local hero runs on the packaged image measured a median 172 ms planning and 315 ms execution/read-back (552 ms total). These exclude external providers, voice and human approval time.

## Account and hosting blockers

| Area | Actual result | Required action |
| --- | --- | --- |
| Google Maps | Enabled Routes API in project lifeos-508512, but real Routes request still returns HTTP 403 `API_KEY_SERVICE_BLOCKED`; no route origin/destination configured | Allow Routes API in key restrictions, enable billing as required, configure actual route addresses |
| Gmail, Calendar, Drive | Owner grant saved; enabled all three APIs and verified real read access on 13 September | Read access verified; write/delivery acceptance remains separate |
| Discord | Bot in one server; configured channel permissions verified, test message sent and read back | Live send/read-back verified for the configured channel |
| WhatsApp | Saved Windows visible-browser login, exact `Rohith CSE A` chat and composer verified; one test message appeared once with a Read receipt | Live outgoing and Read receipt verified on this desktop; the enrolled session is local |
| Railway | $0 Free plan activated; new project creation rejected, but a separate LIFEOS service and volume were added inside the existing project without replacing its other service | Protected demo deployed; a separate project and live-account host remain unavailable without more capacity |
| Google Cloud | Relevant project billing disabled; hosting APIs disabled | Operator-controlled billing/hosting setup required |

There is no public **live-account** deployment URL. The protected public demo URL and acceptance record are in [PUBLIC_DEMO_RELEASE.md](PUBLIC_DEMO_RELEASE.md). The local `.env`, WhatsApp profile and local databases were not uploaded; the demo service has generated auth/encryption secrets and a server-side OpenAI key in Railway variables. The unrelated Railway service and local database volumes were preserved.

## Original-brief gaps

Public-host load/backup acceptance, device microphone/speaker acceptance and a genuine approved multi-provider hero workflow remain unverified. Source monitoring deliberately covers bounded recent Gmail/Discord messages with explicit dates, not exhaustive historical or all-provider ingestion. Calendar update undo does not recall sent messages or reverse arbitrary actions. Usage metrics do not invent currency charges or token counts when the provider omits them. The application deliberately supports one owner and one backend process. Realtime voice and adopting the Agents SDK are conditional choices in the brief, not prerequisites by themselves. See [monitoring](SOURCE_MONITORING.md), [undo](LIVE_UNDO.md), [data controls and usage](PRIVACY_AND_USAGE.md), and the historical [release audit](RELEASE_AUDIT.md).

## Reproduction

Use the source archive `artifacts/lifeos-source.zip` or this repository. Follow [deployment instructions](DEPLOYMENT.md) for Docker/PostgreSQL and [local desktop instructions](LOCAL_LIVE.md) for the enrolled WhatsApp session. The archive excludes `.env`, private browser profiles, databases and local runtime files. Configure your own credentials before live use.

## Google connection follow-up

The saved Google grant was valid, but Gmail, Calendar and Drive APIs were disabled in project lifeos-508512. Enabled gmail.googleapis.com, calendar-json.googleapis.com and drive.googleapis.com; all three live read checks passed. The live frontend now automatically checks access on opening Integrations and hides the Google connection button once a grant is present. Browser verification confirmed all five non-Maps integrations as read-access-verified and no Google connection buttons. The refreshed Docker image includes this frontend follow-up.

## Live message acceptance follow-up

At 15:20 UTC on 13 September 2026, one clearly labeled test message was sent to the configured Discord channel and read back by message ID. One test message was sent to the configured WhatsApp chat; the first adapter read-back returned uncertain because WhatsApp moved outgoing message records and status labels. A separate read-only reconciliation located exactly one matching outgoing record with a Read receipt. The adapter now supports the current markup, and a new browser fixture covers send and read-back. No duplicate WhatsApp message was sent. The live Integrations diagnostic now verifies the signed-in chat and composer directly without sending. Its first live browser check returned verified for WhatsApp.

## Connected application screens

Live mode now opens one continuous **Connected apps** page by default inside LIFEOS. Discord uses a recognizable channel layout with the configured channel's real messages and author avatars when available. Gmail shows a real inbox and plain-text detail; WhatsApp shows the exact configured chat; Calendar and Drive show bounded real lists. The same page shows connection statuses, an in-place recheck, and the latest real LIFEOS event's action impact. Each panel fetches independently through authenticated owner-scoped endpoints. Message sending and calendar changes still go through the existing plan and approval flow. Maps has an in-app status screen, but no working route until the Routes key restriction and route addresses are fixed. This is a LIFEOS-rendered interface over provider APIs, not an embedded authenticated Discord or Gmail website.

The WhatsApp screen was tested twice against the enrolled browser session. The first read loaded the configured chat; the second read reused the exact selected chat after WhatsApp hid its search field. Both succeeded without sending. Authenticated API checks passed for all six providers (Maps returned `needs_attention`). A browser pass rendered all six panels together, Gmail detail, in-place connection checking, the ripple panel and the mobile layout with no horizontal overflow. The current local UI is at http://localhost:8010. This does not remove the public hosting and Maps blockers above.

## Refresh-safe connection status

The live server now saves the last credential-free integration check for the workspace for up to 24 hours. The Integrations page shows its timestamp and statuses after refresh; it automatically calls providers only when no recent check exists. The cache is invalidated on Google reconnection or disconnection. This prevents repeated refreshes from hitting the three-checks-per-minute limit and falling back to “configured unverified.” Live browser acceptance confirmed five verified integrations after two reloads with only one provider check.
