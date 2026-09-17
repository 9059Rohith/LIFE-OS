# LIFEOS Real Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking. The user asked for research and planning first; this document authorizes no feature implementation by itself.

**Goal:** Ship a Windows LIFEOS application that shows the user's actual signed-in Discord and WhatsApp pages, executes one real approved cross-app ripple, proves each action with provider read-back, and has a verifiable production release.

**Architecture:** Keep one authoritative FastAPI/PostgreSQL backend for planning, approvals, Gmail, Calendar, Discord and durable evidence. Electron `BaseWindow` hosts a trusted LIFEOS shell plus isolated `WebContentsView` instances for the actual Discord and WhatsApp sites. A narrow Windows action worker uses the **same visible WhatsApp `WebContentsView` session** and receives only approved, typed work through an authenticated outbound connection to the hosted backend. The existing Playwright worker remains a development migration reference until this path passes real acceptance; the public demo never counts as live acceptance.

**Tech Stack:** Python/FastAPI/SQLAlchemy/PostgreSQL, React/TypeScript/Vite, Electron `WebContentsView` and `safeStorage`, the existing Playwright WhatsApp worker as a migration reference, Google APIs, Discord bot API, OpenAI API where configured.

**Spec:** [Competitor research](../../COMPETITOR_RESEARCH_2026-09-17.md), [requirements](../../REQUIREMENTS.md), [exact app window plan](../../EXACT_APP_WINDOW_PLAN.md).

## Global Constraints

- No mock provider, canned message history, simulated action, fallback artifact or synthetic score may appear as a live production result. Deterministic fixtures are allowed inside automated tests only.
- A visible Discord/WhatsApp page must be the provider's actual signed-in HTTPS site in the LIFEOS Windows window. A LIFEOS-rendered summary is labeled as such and does not satisfy this requirement.
- Google Maps Routes API is removed from runtime, configuration, UI and deployed release. Historical tests/docs may mention its removal.
- No remote provider content gets Node integration, privileged preload APIs, LIFEOS session cookies, or access to another provider's persistent session.
- One owner and one backend process remain the supported v1 deployment model until concurrency is intentionally redesigned. Preserve the existing plan version, approval, allowlist, journal and uncertain-state semantics.
- Never mark a send/update successful from intent or API response alone. Independent provider read-back or reconciliation is required; an ambiguous send remains uncertain and cannot auto-resend.
- A manual action inside an embedded provider page is a manual action, not a LIFEOS-verified automation.
- Do not publish screenshots, recordings, tokens, or logs containing private account content. Use dedicated test accounts and redact shareable proof.
- Preserve the existing uncommitted work. At execution time, inspect `git status`, make an isolated worktree if needed, and commit only the files for the task being completed.

## File ownership and interfaces

| Unit | Files | Contract |
| --- | --- | --- |
| Desktop shell | `desktop/main.cjs`, `desktop/preload.cjs`, `desktop/package.json`, `frontend/desktop.html`, new `frontend/src/desktop.tsx`, new `frontend/src/desktop.css`, `frontend/vite.config.ts` | Trusted shell IPC selects an allowlisted provider, positions the viewport, reports load/error state; provider pages receive no preload. Development loads loopback; release loads only the pinned LIFEOS HTTPS origin. |
| Live planning | `backend/lifeos/planning.py`, `backend/lifeos/providers.py`, `backend/lifeos/whatsapp.py`, `backend/lifeos/policy.py` | `make_plan(...)` creates typed dependency-ordered actions only for known, validated targets; `execute` and `verify` preserve immutable arguments and provider evidence. |
| Event provenance/stream | `backend/lifeos/engine.py`, `backend/lifeos/store.py`, new `backend/lifeos/event_stream.py`, `backend/lifeos/main.py`, `frontend/src/api.ts`, `frontend/src/types.ts` | Durable event is the source of truth; a stream only announces that a saved event changed, and reconnect fetches the latest saved state. |
| Ripple UI | `frontend/src/App.tsx`, `frontend/src/components/Graph.tsx`, `frontend/src/components/ConnectedApps.tsx`, new `frontend/src/components/RippleDock.tsx`, `frontend/src/styles.css` | Source -> context -> proposed consequence -> approval -> attempt -> read-back statuses derive from one saved event. Click action focuses its real provider view on desktop. |
| WhatsApp device bridge | New `backend/lifeos/device_bridge.py`, new `backend/lifeos/device_protocol.py`, new `desktop/whatsapp-worker.cjs`, `backend/lifeos/providers.py`, `desktop/main.cjs` | The cloud backend is the action authority; the Windows worker uses the already-visible WhatsApp view for approved actions to the configured contact and returns a durable attempt/read-back result. |
| Release and evidence | `.github/workflows/ci.yml`, `Dockerfile`, `desktop/package.json`, `docs/DEPLOYMENT.md`, `docs/RELEASE_STATUS.md`, new `docs/LIVE_ACCEPTANCE_2026-09-17.md` | Exact source/installer/image revisions, CI result, real account acceptance, backup restore, rollback and deployment endpoints are recorded. |

## Release proof before “100% completed and deployed”

All of the following must be true on the same release revision:

1. `npm run build`, frontend lint, Python tests/lint, browser tests, container build, and desktop package complete with no skipped required gate.
2. The signed-in **actual** Discord and WhatsApp pages render inside the packaged Windows window; their sessions survive app restart. Provider switch, back/forward, resize, offline/reconnect, focus, keyboard access and reduced motion are checked.
3. A real source message in a dedicated account produces a plan with actual source ID, target IDs and visible consequences. The operator approves exact actions. At least Calendar plus two of Gmail/Discord/WhatsApp change through their live adapters, with separate read-back receipts and no duplicate send.
4. A rejection, changed calendar ETag, revoked provider access, prompt injection, wrong recipient, interrupted process and uncertain delivery all stop or show a truthful recoverable state. They never become a green ripple.
5. The production installer and HTTPS live backend are released, reachable and versioned; the enrolled Windows worker connects outbound and never exposes a remote browser-control port. It uses the same WhatsApp session shown in the window. Persistent storage survives restart; an encrypted backup restores into an isolated environment. The public demo is clearly labeled and is not presented as the live service.
6. The shipped source, image and UI contain no working Maps integration and no Maps API key. A fresh-account onboarding path and a private, redacted proof recording exist.

The target is a measurable product bar; “top 1%” is an aspiration, not a test result or guaranteed contest ranking.

---

### Task 1: Restore the build and prove exact provider-window feasibility

**Files:** Create `frontend/src/desktop.tsx`, `frontend/src/desktop.css`, `frontend/e2e/desktop-shell.spec.ts`, `docs/LIVE_ACCEPTANCE_2026-09-17.md`; modify `desktop/main.cjs`, `desktop/preload.cjs`, `frontend/vite.config.ts` only as needed.

**Interfaces:** Consumes the existing `window.lifeosDesktop` preload API and `desktop.html`. Produces `{ select(name), setViewport(bounds), reload(name), onStatus(handler) }` with `name` restricted to `lifeos | discord | whatsapp`; the main process alone creates or navigates provider views. The release shell URL must match one configured HTTPS origin; loopback is allowed in development only.

- [ ] **Step 1: Freeze the baseline.** Record `git status --short`, `git rev-parse HEAD`, and the observed `npm run build` failure (`/src/desktop.tsx` missing). Do not reset unrelated changes.
- [ ] **Step 2: Add a local desktop shell entry.** Render a provider switcher, actual viewport rectangle, loading/error indicator, and a compact LIFEOS dock. All provider selections go through the preload's bounded IPC API; remote provider DOM is never copied into React. The viewport uses `ResizeObserver` and reports integer bounds after layout changes.

```ts
type DesktopProvider = "lifeos" | "discord" | "whatsapp";
type Bounds = { x: number; y: number; width: number; height: number };
window.lifeosDesktop.select("discord");
window.lifeosDesktop.setViewport(bounds);
```

- [ ] **Step 3: Test and fix the production build.** Run `npm run build` and `npm run lint` in `frontend`; both must pass, and `frontend/dist/desktop.html` must reference emitted assets. Add a browser test for shell controls and viewport sizing, without claiming it proves real provider sign-in.
- [ ] **Step 4: Run the signed-in feasibility gate on Windows.** Start the backend in live mode and the Electron shell, manually sign in to Discord and WhatsApp in their isolated partitions, then verify actual content, navigation, restart persistence, narrow/wide resize and network recovery. Record Electron version, provider behavior and private screenshots. Verify that the visible WhatsApp view exposes the selected chat and message read-back state needed by the narrow action worker. If either provider refuses the runtime, stop that claim and investigate supported alternate desktop presentation; do not replace the site with a clone or screenshot.
- [ ] **Step 5: Review remote-content isolation.** Use Electron's [WebContentsView API](https://www.electronjs.org/docs/latest/api/web-contents-view) and [security checklist](https://www.electronjs.org/docs/latest/tutorial/security): no Node integration, context isolation and sandboxing on all views, exact HTTPS navigation allowlists, denied popups by default, bounded permissions and validated IPC sender/frame. Verify the local shell cannot be redirected to a remote origin.

**Acceptance:** build and lint pass; both real sites are visible inside the shipped composition in the same application window; blocked navigation and session isolation are observed, not assumed.

### Task 2: Make a real, narrow hero ripple across providers

**Files:** Modify `backend/lifeos/planning.py`, `backend/lifeos/providers.py`, `backend/lifeos/policy.py`, `backend/lifeos/whatsapp.py`, `backend/lifeos/config.py`; add focused cases to `tests/backend/test_planning.py` and `tests/providers/test_live_workflow.py`.

**Interfaces:** `make_plan(text, source, simulation, entities, context, timezone, mode)` produces an ordered event. A WhatsApp send action uses the existing `LiveProviders.execute(user_id, action, idempotency_key)` and `verify(user_id, action, result)` boundaries. The allowed WhatsApp contact comes only from owner configuration and a successfully checked session, never from untrusted message text.

- [ ] **Step 1: Pin one acceptance story.** A dedicated test account receives a genuine Gmail or Discord schedule-change message with an explicit date/time. Its known Calendar event and known recipient thread are real. The plan proposes Calendar update, Gmail/Discord notification and, only when the owner has explicitly enabled a known WhatsApp contact for this event type, a WhatsApp notification. Record the real source message ID and Calendar event/ETag; do not seed product data.
- [ ] **Step 2: Add a failing policy test.** Verify that an external message saying “send WhatsApp to +new-number” cannot override the configured contact, that ambiguous meetings/participants produce `clarification_required`, and that a missing WhatsApp session omits or blocks its action with a reason. Verify the proposed message text, recipient, dependencies and risk are visible before approval.

```python
assert all(a["arguments"].get("contact") != "+new-number" for a in event["actions"])
assert event["status"] == "clarification_required"  # ambiguous target
```

- [ ] **Step 3: Implement only the validated path.** Add the WhatsApp action when the scenario gives a real reason to notify the configured contact. Set its dependency on the calendar action when present. Preserve the existing action hash, plan version, expiration, allowlist and preflight. Keep flight and meeting paths honest when a provider is absent.
- [ ] **Step 4: Check real execution.** Run focused tests, then execute the approved actions with dedicated accounts on the local live backend. Inspect Calendar by event ID/ETag, Gmail by message ID, Discord by channel/message ID, and WhatsApp in the selected chat. Do not resend automatically after an uncertain result.

**Acceptance:** one genuine source event yields a useful, legible plan and at least three live provider effects; every target is owner-known and approved. If an actual provider cannot be used, the action is absent or blocked with a truthful reason.

### Task 3: Persist source-to-receipt provenance and stream truthful state

**Files:** Create `backend/lifeos/event_stream.py`; modify `backend/lifeos/engine.py`, `backend/lifeos/main.py`, `backend/lifeos/store.py`, `frontend/src/api.ts`, `frontend/src/types.ts`; add `tests/backend/test_event_stream.py`.

**Interfaces:** Introduce `EventNotice(owner: str, event_id: str, version: int, updated_at: str)` and `publish_notice(notice) -> None`. `GET /api/events/{id}/stream` requires the owner session and sends only a change notice, never private message text. `GET /api/events/{id}` remains the durable authoritative snapshot. The persisted event includes source provider ID and each action's attempt/read-back references, subject to existing retention and credential-free audit rules.

- [ ] **Step 1: Write tests for stream ownership and restart.** A second owner cannot subscribe to an event; disconnect/reconnect fetches the current event; a process restart retains final action statuses because the database, not the stream, owns state. No event body or token appears in stream frames.
- [ ] **Step 2: Persist provenance at ingest and execution.** Store source application and provider record ID at detection. For each action, record proposed argument hash, approval version, attempt timestamp, provider result ID, read-back timestamp and final status. Keep a bounded redacted excerpt only where useful; never put secrets in audit records.

```python
@dataclass(frozen=True)
class EventNotice:
    owner: str
    event_id: str
    version: int
    updated_at: str
```

- [ ] **Step 3: Publish only after successful persistence.** Notify subscribers from `Engine.save(...)` after the transaction is durable. On the frontend, receive notices and refetch the event; if streaming fails, fall back to bounded polling and show connection state. Avoid duplicate rendering by event ID and version.
- [ ] **Step 4: Verify event ordering.** Run `python -m pytest tests/backend/test_event_stream.py -q` and a browser test where plan, approval, attempt and read-back statuses appear in order. A transient notification loss must not lose the durable final state.

**Acceptance:** a user can trace each consequence to a real source and each green result to a real provider receipt, including after refresh or restart.

### Task 4: Build the LIFEOS ripple dock around the real app window

**Files:** Create `frontend/src/components/RippleDock.tsx`; modify `frontend/src/desktop.tsx`, `frontend/src/desktop.css`, `frontend/src/App.tsx`, `frontend/src/components/Graph.tsx`, `frontend/src/components/ConnectedApps.tsx`, `frontend/src/styles.css`; add `frontend/e2e/ripple-dock.spec.ts`.

**Interfaces:** `RippleDock` consumes one typed persisted `Event` and `onFocusProvider(provider: DesktopProvider)`; it does not create actions or infer success. The desktop switcher opens the actual provider view while the dock remains local and visible.

- [ ] **Step 1: Define the compact state model.** Each node shows one of detected, context found, proposed, awaiting approval, approved, attempting, verifying, verified, failed, uncertain or blocked. The app name and source/receipt link are visible. No continuously moving line is allowed when no state changes.
- [ ] **Step 2: Implement the dock.** Give the provider website the majority of the window. Show current event title, source, affected apps, exact approval prompt, action sequence, and receipt/failure details in a collapsible pane. Clicking an action focuses the corresponding real provider view. A provider load failure does not erase the dock or other views.

```tsx
<RippleDock event={event} onFocusProvider={(provider) => window.lifeosDesktop.select(provider)} />
```

- [ ] **Step 3: Make motion explain causality.** Animate only saved status transitions, respecting `prefers-reduced-motion`. Use a stable node layout so new receipts do not jump the page. Preserve visible keyboard focus, readable contrast, accessible status text and screen-reader updates for completed/failed steps.
- [ ] **Step 4: Verify interaction.** Browser tests assert selected provider, approval wording, pending vs verified distinction, no green state on uncertain delivery, reduced motion, and 1060 px minimum window layout. Inspect the packaged Windows UI with real provider content at wide and minimum sizes.

**Acceptance:** a first-time user can answer what triggered the event, what LIFEOS proposes, what they approved, what changed and what is still uncertain without opening a technical log.

### Task 5: Adversarial and failure verification against the same real workflow

**Files:** Extend `tests/backend/test_security.py`, `tests/providers/test_live_workflow.py`, `tests/providers/test_whatsapp_browser.py`, `frontend/e2e/approval.spec.ts`; update `backend/lifeos/engine.py`, `backend/lifeos/providers.py`, `backend/lifeos/whatsapp.py` only for observed defects. Record results in `docs/LIVE_ACCEPTANCE_2026-09-17.md`.

**Interfaces:** Keep `Engine.validate_approval(...)`, `LiveProviders.preflight(...)`, `LiveProviders.verify(...)` and WhatsApp `verify(result)` as the security boundary. A failed or inconclusive verification returns a distinct status and reason; it never becomes `verified`.

- [ ] **Step 1: Reproduce the same workflow under faults.** Inject malicious instructions into the source message; change Calendar ETag after planning; change configured recipient; expire approval; revoke Google/Discord access; interrupt after remote send but before read-back; break the WhatsApp selector. Automated fixtures cover deterministic branches; dedicated accounts cover at least one real stale-plan and one real provider-recovery case.
- [ ] **Step 2: Verify safe outcomes.** Assert no send for injected/new recipients, no update after stale approval/ETag, no duplicate send after uncertain response, and an audit entry for each block. Reconcile uncertain messages by provider ID or exact bounded chat search before any operator retry.

```python
assert action["status"] in {"blocked", "failed", "uncertain"}
assert action["status"] != "verified"
```

- [ ] **Step 3: Fix and retest the same case.** For each observed defect, add a focused regression test using the same source/target shape, fix the smallest boundary, and rerun that exact case. Keep the failed baseline and passing retest in the acceptance record.
- [ ] **Step 4: Measure responsiveness.** Record cold startup, provider switch latency, planning time, approval-to-attempt time, read-back time, CPU and memory on the target Windows machine. Include provider/network time separately; do not present local-only milliseconds as end-to-end live latency.

**Acceptance:** failures are visible, bounded and recoverable; the same known-bad inputs no longer produce an unauthorized or falsely verified effect.

### Task 6: Connect the local WhatsApp worker to the hosted authority

**Files:** Create `backend/lifeos/device_protocol.py`, `backend/lifeos/device_bridge.py`, `desktop/whatsapp-worker.cjs`, `tests/providers/test_device_bridge.py`, `desktop/test/whatsapp-worker.test.cjs`; modify `backend/lifeos/main.py`, `backend/lifeos/providers.py`, `desktop/main.cjs`, `desktop/package.json`.

**Interfaces:** Define a versioned `WhatsAppCommand(command_id, event_id, action_id, arguments_hash, contact, body, expires_at)` and `WhatsAppReceipt(command_id, outcome, provider_message_id, readback_at, evidence_hash, error)`. The backend enqueues a command only after current approval and preflight. The enrolled Windows client opens an authenticated outbound WSS connection and executes only `whatsapp.send` for its configured contact through the existing WhatsApp `WebContentsView`. The backend owns final status and rejects duplicate/out-of-order receipts. The pairing token stays in Electron `safeStorage`; the provider page has no bridge access.

- [ ] **Step 1: Write protocol and replay tests.** A command with stale approval, wrong contact, changed body hash, expired deadline or second delivery is rejected. A disconnect after attempted send creates `uncertain`; reconnect reconciles by provider evidence before any retry. A revoked device cannot reconnect.

```python
assert receipt.command_id == command.command_id
assert receipt.outcome in {"verified", "failed", "uncertain"}
assert command.arguments_hash == approved_action["arguments_hash"]
```

- [ ] **Step 2: Pair one desktop device.** Require owner authentication to issue a short-lived, single-use pairing code. Store the resulting device token using Electron `safeStorage`, bind it to one owner/device ID, provide revoke/re-pair controls, and record only a token hash server-side. Do not put a device token in the provider `WebContentsView` or in a URL.
- [ ] **Step 3: Add a durable bounded queue and exact-view worker.** Persist commands and receipts in the existing database with monotonic sequence numbers and a unique command ID; allow only one active worker for this v1 owner. Use heartbeat/expiry to show offline status. In `desktop/whatsapp-worker.cjs`, locate the configured chat, check the actual composer, perform one send and read back its message/status through the existing WhatsApp view. Keep a local attempted-command journal before clicking send; after a crash or network loss, reconcile before any retry. Port selector knowledge from `backend/lifeos/whatsapp.py`, but never share or copy its Chromium profile.
- [ ] **Step 4: Connect and verify on dedicated accounts.** Pair the actual Windows worker with a staging HTTPS backend, approve one WhatsApp action, watch the one real message appear in the visible configured chat and confirm server-side read-back. Then restart the client and backend, pull the network mid-send, revoke the device and replay the old command; record each outcome and provider evidence. No remote Playwright/CDP port is exposed.

**Acceptance:** hosted LIFEOS can truthfully execute and verify one approved WhatsApp action through an enrolled desktop worker; offline and ambiguous outcomes block completion instead of faking success.

### Task 7: Package, deploy and prove the release revision

**Files:** Modify `desktop/package.json`, `desktop/main.cjs`, `.github/workflows/ci.yml`, `Dockerfile` and deployment config only as required; update `docs/DEPLOYMENT.md`, `docs/RELEASE_STATUS.md`, `docs/INTEGRATIONS.md`, `docs/LIVE_ACCEPTANCE_2026-09-17.md`.

**Interfaces:** A versioned Windows installer launches the trusted shell and its narrow WhatsApp worker with a documented update and rollback path. A live backend deployment exposes `/health` and `/ready` over HTTPS, owns durable storage and device pairing, and never silently switches to demo mode. The desktop build records the backend/API revision it accepts.

- [ ] **Step 1: Confirm the release topology from Tasks 1 and 6.** The hosted FastAPI/PostgreSQL backend owns events and approvals; the narrow worker uses the visible WhatsApp view only; Discord and WhatsApp pages have isolated Electron sessions. A single WhatsApp linked session is enrolled in the LIFEOS window. The hosted server must never claim to contain that locally enrolled browser.
- [ ] **Step 2: Package and sign the client.** Build a Windows installer from exact locked dependencies and a pinned Electron version, include the narrow worker and shell assets, provide onboarding for Google grant, Discord bot/channel, WhatsApp window sign-in and device pairing, and record installer hash/signing identity. The production startup screen shows live connection checks and actionable errors, not demo records.
- [ ] **Step 3: Run CI and deploy the live backend.** The gate runs Python tests/lint, frontend lint/build, browser tests, secret scan, dependency audit, container build and installer smoke test for the exact commit. Configure HTTPS, secrets, database backup, single-process migration and health probes. Keep demo and live data/credentials in distinct deployments. Verify Maps is absent in the deployed image and UI.
- [ ] **Step 4: Run a private release acceptance.** On the packaged installer plus deployed revision, sign in to both actual app pages, run the genuine approved hero event, inspect every remote effect and read-back, restart both client and backend, and restore a backup to an isolated database. Record commit, image digest, installer hash, timestamps, provider IDs redacted for sharing, CI link, latency and any unresolved issues.
- [ ] **Step 5: Reconcile public status.** Replace stale Maps and screen descriptions in `docs/RELEASE_STATUS.md`. State “completed and deployed” only after all six release proof conditions above pass. If a provider blocks the exact-page runtime or live hosting is unavailable, record the precise blocker and continue improving independent parts without substituting a mock.

**Acceptance:** a reviewer can install, connect dedicated accounts, reproduce the real ripple, inspect receipts and verify that the distributed bits match the documented source. The password-protected Railway demo remains labeled as a demo until a separate live release is proven.

## Execution order and checkpoints

Tasks 1 and 2 unblock the product. Task 3 makes state reliable for Task 4. Task 5 attacks the same live story; Task 6 joins the hosted authority to the enrolled Windows worker; Task 7 packages only a passing revision. After each task, review the diff and run its focused gate before proceeding. Do not attempt visual polish to hide a failed build, missing sign-in, unverified send or inaccessible host.

## Self-review against the spec

- Actual Discord and WhatsApp UI: Task 1 and Task 4, with a signed-in Windows feasibility gate.
- Real event -> consequence -> approval -> execution -> verification: Tasks 2–5, with durable source/receipt linkage.
- Motion and exact app window: Task 4, tied to saved transitions.
- No mocks in the actual product: global constraint, Task 2 live accounts and Task 7 release proof.
- Google Maps API removal: global constraint and Task 7 deployed artifact check.
- Security, access, failure and uncertain sends: Tasks 1, 2 and 5.
- Complete/deployed claim: six release proof conditions and Task 7, with explicit blockers if they cannot pass.
