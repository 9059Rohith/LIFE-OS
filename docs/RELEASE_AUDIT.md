# Release audit — 13 September 2026

This is a source and requirements review, not a percentage-complete estimate or a live-account acceptance certificate. Scope: `docs/REQUIREMENTS.md`, `docs/VERIFICATION.md`, backend authentication, execution, limits, planning, persistence, and deployment configuration. No secrets were read and no account mutations were performed for this audit. Line references identify the reviewed code and may shift during follow-up edits.

## Release conclusion

**Follow-up:** This audit is a historical review. Its scheduling, request-budget, monitoring, live-update-undo, data-control and measured-usage findings were subsequently addressed. Current evidence and outstanding provider/hosting acceptance are recorded in [RELEASE_STATUS.md](RELEASE_STATUS.md).

The repository has a tested local product and production-shaped deployment. It does **not** yet meet the original brief's full live-account definition of done. Local protocol fixtures and demo records cannot establish successful real Gmail/Calendar/Discord/WhatsApp execution. Live acceptance and target-host operational verification must remain explicit gates.

## Concrete issues found and remediation

| Priority | Finding and evidence | Required outcome |
| --- | --- | --- |
| P1, fixed in this review | `main.py` originally checked only the Content-Length header. Chunked/missing-length multipart could spool oversized content before the route's audio length check. | Added `limits.py:BodyLimitMiddleware`, enforcing actual 12 MB bytes before framework parsing, with a 30-second upload deadline. Keep ingress connection/body limits as well; application buffering is not a substitute for host resource controls. |
| P1, fixed in this review | Original `/api/voice/speak` and `/api/voice/transcribe` each opened paid provider calls without a concurrency budget; the general 120/minute owner request allowance applied. | Added one shared voice budget: two concurrent calls and twelve admissions per owner per minute. Saturation returns 429 immediately; failure/cancellation releases the slot. This is intentionally single-process. |
| P1, outstanding at review time | `planning.py:286–296` checks the original client meeting against the flight window, then derives a new meeting start. It does not check the proposed interval against other calendar events. | Reject or choose a conflict-free proposed interval; verify a busy unrelated calendar entry blocks an overlapping move. Revalidate edited times and execution preconditions where necessary. |
| P2, outstanding | `providers.py:322–332` accepts event text but fetches Gmail `newer_than:30d` rather than a relevant query. `gmail_search:179` caps this at five messages, and `calendar_list:192` uses only the first thirty events within thirty days. `planning.py:185–197` then requires exactly one broadly named meeting in the entire result. | Search/filter against the actual event date/entities, handle bounded pagination or disclose incomplete search, and ask for a specific target when ambiguity remains. Ordinary busy accounts must not depend on a specially sparse calendar/mailbox. |
| P2, outstanding | `engine.py:77` invokes event retention only during creation of the next plan; `store.py:63` removes only event documents. Expired sessions, audit documents, tokens and other kinds are not governed by that setting. | Give the retention UI a precise scope and implement scheduled deletion/expiry where required. Define a separate audit retention policy that preserves chain verification; do not silently delete chain links. |
| P2, deployment boundary | `engine.py:16`, `security.py:16`, `store.py:115` use process-local locks/rate state, and `main.py` startup reconciliation marks all executing records uncertain. A second API worker could race execution/reconciliation and audit writes. | Enforce documented one-worker/one-replica operation. Multi-replica support requires database leases/atomic state transitions, shared limits, and coordinated reconciliation; PostgreSQL alone does not supply these guarantees. |
| P2, scaling concern | `store.py:_append_audit` loads every existing audit entry for each append; list APIs also load whole document collections. | Use indexed head/pagination queries before claiming sustained-load readiness. Benchmark using a realistic retained audit history. |

The new limits have five focused regression tests in `tests/backend/test_request_limits.py`. Their initial red run failed because the module was not yet implemented. Final command `python -m pytest tests/backend/test_request_limits.py tests/backend/test_security.py tests/providers/test_ai_browser.py -q` passed **25 tests**, with two existing third-party deprecation warnings, in 7.99 seconds. Ruff passed for the changed backend/test files. This is targeted evidence, not a rerun of every gate.

## Original specification versus current support

| Requirement | Current boundary |
| --- | --- |
| §§1, 64, 73, 74, 78–79: real cross-app hero, independent read-back, text and voice | Demo and provider fixture tests exist. All required real accounts, configured destinations, writes/read-back, physical voice workflow and resulting audit must be exercised before full acceptance. Latest live provider evidence belongs in `LIVE_CHECKS.md`; this audit does not supersede it. |
| §§7–12: integration capabilities | Adapters contain substantial real API/browser code. Adapter availability is distinct from reachable product actions: generated plans specialize in flight/meeting workflows; Calendar create/cancel support in the adapter does not by itself expose a complete create/cancel product flow. Gmail draft preview is not necessarily a saved provider draft. Verify these separately before claiming the whole capability list. |
| §§1, 9, 64: event detection from applications | Explicit input and demo-origin scenarios work; no always-on webhook/inbox/channel ingestion service is present. Labels such as `source=gmail` do not prove ingestion of a real incoming message. |
| §§13–16, 42: voice | Chained recorded STT → shared workflow → TTS and contextual approval/interruption are implemented. Hardware capture, live recognition quality and latency still require acceptance evidence; provider fixtures use synthetic data. |
| §§19–20, 57: consequences/action planning | Specialized deterministic flight/meeting rules and narrow validated AI extraction exist. `ai.py:EventExtraction` supports only flight change, meeting change or unknown. The full brief's broad consequence engine is not established for arbitrary event classes. Specialized responsibilities need not mean multiple model agents. |
| §34: database | PostgreSQL deployment and schema revisioning exist. One generic document table differs from the expressly listed conceptual tables, with ownership and kinds represented as fields. This is a documented architecture deviation, not proof of a database defect by itself. |
| §38, §64: visible application operation | Persistent local app inspection exists. The default container omits a browser runtime and WhatsApp runs within the API process when enabled. A live multi-app visible browser demonstration still needs to be demonstrated. |
| §44: undo/compensation | `engine.py:411` implements demo compensation. Live undo returns an instruction to create a new reviewed plan; there is no generated live compensation workflow. |
| §§46, 50, 55–56: observability and budgets | Measured workflow/tool durations and bounded retries exist. `main.py` metrics explicitly return `model_token_usage: None`; full token, voice-duration, cost and browser-action accounting remain missing. Voice admission limits now bound call rate/concurrency, not cumulative billed cost. No general unbounded model loop exists. |
| §§58–59: memory and control | Events/history/preferences/integration state are scoped; inspect/edit/approve/reject/cancel/retry exists. Retention limitations above remain. Live compensation is incomplete. |
| §§70–71: deployment and CI/CD | Container/PostgreSQL checks and CI verify/build stages exist. `.github/workflows/ci.yml` explicitly has no publication step. Target HTTPS ingress, backups plus restore drill, host load/resource checks and successful protected deployment are separate outstanding evidence. |
| §72: strict typing | CI statically checks only config, schemas and policy; the full backend is not strictly typed. This is disclosed in verification docs. |

## Conditional requirements, not automatic blockers

- Realtime voice is explicitly “where appropriate” (§2 Mode B and §77). Lack of the Realtime API, automatic VAD or partial transcription is not by itself noncompliance if the required chained voice experience passes its quality/latency checks.
- Agents SDK features, handoffs and multiple agents are recommended where useful (§2 and §57), not a demand to replace deterministic policy with model autonomy.
- A separate browser container is conditional on deployment needs (§70). For a public service, isolating browser credentials/processes is advisable, but the brief does not make a separate service an unconditional deliverable.
- Circuit breakers, tracing and streaming have conditional wording. A missing optional mechanism must not be reported as a missing mandatory feature without demonstrating the failure it is meant to address.

## Authentication and security assessment boundaries

The live application is intentionally single-owner: successful password login creates sessions for `owner`. It has hashed session tokens, HttpOnly/SameSite cookies, secure cookies in production, CSRF/origin checks, encrypted OAuth tokens and constrained provider hosts/targets. This supports a private owner-operated deployment; it is not a multi-user SaaS identity system. Do not expose it under a multi-tenant claim without implementing separate identities, authorization and isolated integration/browser state. This review found no reason to bypass existing approval, authentication or provider safeguards to make the demonstration appear complete.
