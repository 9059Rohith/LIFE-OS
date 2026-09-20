# LIFE-OS Final Release Checklist

## Product

- [x] Core schedule-change workflow
- [x] Consequence graph
- [x] Approval-bound actions
- [x] Bounded execution
- [x] Provider read-back verification
- [x] Audit evidence
- [ ] Arbitrary event classes beyond the supported schedule-change domain

## UI

- [x] Overview, graph, approval, connected apps, work, calendar, integrations, audit, and settings surfaces
- [x] Loading, empty, error, success, uncertain, and disconnected states
- [x] Responsive browser coverage
- [x] Light and dark modes
- [x] Motion-aware workflow visualization

## Backend and security

- [x] Authentication and sessions
- [x] CSRF and origin checks
- [x] Request/body limits
- [x] Provider allowlists
- [x] Owner-scoped provider actions
- [x] Idempotency and bounded retries
- [x] Secret scanning and credential exclusion
- [ ] Horizontally scaled multi-worker execution

## AI

- [x] Structured extraction boundary
- [x] Strict schema validation
- [x] Prompt-injection rejection tests
- [x] Server-owned action construction
- [ ] ScreenOps-style browser-local screen/audio inference

## Testing

- [x] 141 backend tests
- [x] 6/6 offline extraction evals
- [x] 15 browser E2E passes, 1 skipped private-demo case
- [x] 8 desktop tests
- [x] Frontend typecheck, lint, and build
- [x] Secret scan

## Submission

- [x] README and architecture documentation
- [x] Security and AI usage documentation
- [x] Competitor scorecard
- [x] Judge quickstart
- [x] Screenshots and poster
- [x] Authenticated live demo, narration, and subtitles
- [x] GitHub repository
- [ ] Published GitHub Actions workflow; blocked by OAuth scope
- [x] Verify the replacement credential after the hosted deployment restarts; historical credential rejected
- [x] Purge the historical credential value from public `main` Git history
- [x] Deploy and verify the current checkout on the hosted service
