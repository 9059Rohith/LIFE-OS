# Verification and acceptance status

Current release evidence, provider restrictions and hosting outcome: [RELEASE_STATUS.md](RELEASE_STATUS.md). The results below describe the original build and are retained as history.

Initial build verified locally on 13 September 2026. **The runnable local application and container deployment are tested. The original brief's complete live-account acceptance gate is not yet satisfied.** Credentials were subsequently supplied: actual OpenAI speech/transcription/extraction now pass; Google consent, Discord installation and WhatsApp login are still outstanding. See [follow-up live checks](LIVE_CHECKS.md). The initial build results below remain a record of the earlier demo verification. No external messages were sent.

## Executed quality gates

| Check | Result |
| --- | --- |
| Full Python suite after dependency remediation | **51 passed**, two third-party deprecation warnings |
| Strict Python typecheck | Passed for configuration, request schemas and deterministic policy (3 modules) |
| Ruff, backend/tests/scripts | Passed |
| TypeScript strict build/typecheck | Passed |
| Frontend ESLint | Passed |
| Vite production build | Passed |
| Frontend advisory audit | Zero known vulnerabilities |
| Python advisory audit | Zero known vulnerabilities after upgrades; local unpublished LIFEOS package has no PyPI advisory entry |
| Credential-pattern source scan | Passed |
| Chromium UI suite against development API | **7 passed** |
| Chromium UI suite against packaged PostgreSQL application at port 18090 | **7 passed**, 22.4 seconds; served production assets, no Vite server |
| Docker/PostgreSQL | Build, health, readiness, workflow, non-root runtime and restart persistence passed; see [deployment evidence](DEPLOYMENT_VERIFICATION.md) |

The backend suite includes real local persistence, approval/version/expiry, typed policy, owner isolation, CSRF, injection blocking, partial approval, action edits, dependency propagation, conditional preflight, uncertain delivery, crash reconciliation, cancellation, compensation and audit integrity. Two complete live-mode engine workflows use real adapters with HTTP fixtures, which verify protocol handling without contacting the real providers. Two WhatsApp locator tests run actual Chromium against an explicitly local DOM fixture.

## Browser workflows

1. Approve one action; execute only permitted changes; edit and reject a remaining email; finish and compensate the reversible calendar change.
2. Capture audio with Chromium's synthetic microphone, upload it to a speech fixture, plan using the actual backend, request approval by voice, confirm against the captured plan, execute by voice, request a speech-output fixture and interrupt playback.
3. Reject a bare “yes” as ambiguous rather than granting approval.
4. Flight hero: inspect exact action, approve, execute six local actions, read back all six, inspect application records and audit.
5. Meeting scenario plus what-if simulation and explicit conversion to an approval-required plan.
6. Injection rejection and 390-pixel mobile navigation without horizontal page overflow.
7. Delayed workspace responses cannot overwrite a newer navigation state.

Speech fixtures return known transcription strings and a silent WAV. **They do not test speech-recognition accuracy, natural voice quality, a physical microphone or a live OpenAI request.** Provider HTTP tests separately validate the OpenAI request formats, response parsing and failures.

## Visual inspection

The generated [design concept](design/concept.png) and current [desktop](screenshots/overview.png), [resolved](screenshots/resolved.png), and [mobile](screenshots/mobile.png) screenshots were opened and inspected. No built-in Browser/IAB tool was available; verification used Playwright Chromium with retained traces on failures.

Checked at 1512 × 1050 desktop and 390 × 844 mobile viewports: forest-green navigation, serif primary heading, off-white workspace, event/graph/activity hierarchy, approval controls, readable action/evidence states, microphone controls and mobile overflow. The main heading matches the design's “Something changed. You’re in control.” Actual event content, dependency arrows and activity records replace illustrative concept data. The result follows the concept's visual direction, but is not a pixel-identical reproduction: the application adds local-app inspection, real dependency edges, scenario/reset controls, context details and longer evidence-driven states.

## Honest acceptance boundaries

| Area | Implemented and locally verified | Still required for the full original brief |
| --- | --- | --- |
| End-to-end local product | Flight and meeting scenarios, graph, preview, approval, execution, read-back and persistent audit | Genuine cross-app hero with authorized accounts |
| Google | OAuth PKCE/refresh/encrypted token storage; Gmail, Calendar, Drive protocol fixtures | Consent setup, allowed test users, actual send/attachment/calendar read-back |
| Discord and Maps | Bot/channel constraints, request/read-back fixtures, actual route-duration parsing | Bot installation/permissions, Routes billing/key, live results |
| WhatsApp | Explicit profile/contact allowlist, draft preservation and browser locator fixtures | Legitimate logged-in test account and live DOM acceptance; browser runtime installed separately |
| Voice | Recorded audio upload, shared workflow, contextual voice approval, speech playback/interruption fixtures | Live STT/TTS, physical capture, quality and latency measurements |
| Ingestion | Direct text, text files, voice, demo Gmail/Discord event source | No always-on inbox/channel watcher or webhook ingestion service |
| Realtime | Execution progress is polled; bounded chained voice | No streaming Realtime audio, partial transcription or automatic VAD |
| Execution | Single-process locks, durable intent, safe retries, preflight, read-back | Distributed queue/leases and multi-replica operation |
| Database | Versioned SQLAlchemy schema and PostgreSQL deployment verified | Document storage is used instead of the brief's individual conceptual tables; whole backend is not strictly statically typed |
| Deployment | Local Docker/Compose deployment and CI configuration | Public HTTPS deployment, real credentials, backup restore, load testing and independent security review |
| Observability | Real tool/planning durations, action attempts, traceable audit | Live token/cost/audio-duration accounting and controlled load benchmarks |

This is a single-owner application design. The documented limits must be addressed before presenting it as the fully validated public production system described in the original brief.
