# LIFE-OS vs ScreenOps Evidence Scorecard

This is an evidence review, not a claim that one product is universally better. ScreenOps is the benchmark repository at [9059Rohith/screenops-codex](https://github.com/9059Rohith/screenops-codex); LIFE-OS is this repository.

## Baseline comparison

| Category | LIFE-OS evidence | ScreenOps evidence | Current advantage |
| --- | --- | --- | --- |
| Problem and product clarity | Consequence graph for schedule changes across connected applications. | Browser-local commitment capture and verified Google actions. | Tie |
| AI depth | Strict event extraction, confidence, prompt-injection rejection, server-owned action construction. | Browser-local SmolVLM, Whisper, OCR, structured intent JSON, LangGraph planning. | ScreenOps |
| Privacy | Bounded server extraction, provider boundary, encrypted credentials, no arbitrary tools. | Raw screen/audio stay in browser; only structured intent JSON crosses the boundary. | ScreenOps |
| Security | Auth, CSRF, origin checks, rate/body limits, approval hashes, owner guards, audit chain. | Risk-gated approval, browser privacy boundary, excluded secrets, Google OAuth. | LIFE-OS |
| Workflow orchestration | Dependent Calendar, Gmail, Discord, WhatsApp and work-record actions. | LangGraph route, enrich, plan, classify, approve, execute, verify flow. | LIFE-OS breadth; ScreenOps architecture clarity |
| Reliability | Idempotency, retries, compensation, uncertain states, provider read-back. | Poll-back verification for Gmail, Calendar and Sheets. | LIFE-OS |
| Integrations | Google, Discord, WhatsApp desktop bridge, Drive and work records. | Gmail, Calendar and Sheets. | LIFE-OS |
| Evaluation evidence | 141 backend tests, frontend quality gates, provider/security/recovery suites, plus offline extraction evals. | 16/16 extraction evals and 15/15 planning evals. | Comparable; different coverage |
| Reproducibility | Docker, SQLite/PostgreSQL support, Railway configuration, local acceptance documentation. | Local setup, Render deployment notes, model download and Google OAuth setup. | LIFE-OS breadth; ScreenOps simpler setup |
| Demo/storytelling | Authenticated live-site demo, provider UI tour, subtitles, screenshots and poster. | Strong privacy proof showing browser capture and network behavior. | Different strengths |

## Decision

On the current evidence, **LIFE-OS is the stronger end-to-end consequence-execution product**, while **ScreenOps is the stronger privacy-first local-sensing demonstration**. LIFE-OS should not claim to win the local-inference category until it implements and verifies an equivalent boundary.

## Required next improvements

1. Keep the offline extraction evals and add planning fixtures with expected action graphs.
2. Publish the privacy boundary and explicitly distinguish server extraction from browser-local inference.
3. Add a network-boundary acceptance test for every optional browser or desktop capture path.
4. Keep the current approval, idempotency, read-back, uncertain-state and audit controls visible in the demo.
5. Remove stale README and release-report claims whenever evidence changes.

## Evidence policy

Scores must be updated only after a command, test, hosted check, screenshot, or recording proves the claim. A future feature is not an implemented feature, and a fixture test is not proof of a live provider action.
