# LIFEOS competitor research — 17 September 2026

## Scope and evidence standard

This review covers the three medal winners of the Pune Codex Community Hackathon, using the [organizer's results](https://www.loops.house/blog/codex-community-hackathon-pune-case-study), each submitted project page, and the public repository where available. The source review is static: no winner's code was executed, no deployment was authenticated, and a repository's current default branch may have changed since judging on 14 June 2026. The seven other Top 10 projects are listed by the organizer, but their code is outside this medalist code review.

| Project | Public code reviewed | Evidence ceiling |
| --- | --- | --- |
| Air Secure | No. Its [submitted repository URL](https://github.com/Jayesh1512/Air-Secure) returned GitHub 404 on 17 September 2026. | [Submitted description](https://www.loops.house/explore-projects/air-secure-01c40) and [organizer result](https://www.loops.house/blog/codex-community-hackathon-pune-case-study). Its submitted [Loom demo](https://www.loom.com/share/b0dfe65892e144fca0692565c52969a4) was linked but not independently inspected. |
| FORGE | Yes. [VanshMomaya7/Forge](https://github.com/VanshMomaya7/Forge), current HEAD `77417639b9bd7a8d4d96cfdd5d540b52a6cfbc88` (13 August 2026). | Code structure and behavior at that commit; no real Codex run or deploy was performed. |
| RedShield_Agent | Yes. [ritisha12345/RedShield_Agent](https://github.com/ritisha12345/RedShield_Agent), current HEAD `a6939d5ededb31620f3fbc75448f0d92c96dcf48` (24 June 2026). | Code structure and behavior at that commit; no live target scan was performed. |

The missing Air Secure repo is a hard evidence limit. A different repo called `DroneHunter` under the same GitHub account is about sales prospecting and is **not** evidence of Air Secure's implementation.

## 1. Air Secure — narrow job, visible proof

The [submission](https://www.loops.house/explore-projects/air-secure-01c40) describes a pipeline: motion detection selects footage, a local vision-language model describes activity, deterministic rules identify events such as after-hours entry and loitering, and a dashboard stores searchable incidents. Urgent Telegram alerts include annotated images. The organizer confirms first place and describes the same footage-to-event-to-evidence loop. It is a clear product promise for a specific operator: show what happened at a site and provide proof quickly.

**Verified:** the project was awarded first place, the submitted description and links exist, and the submitted GitHub URL is currently unavailable. **Not verified:** model choice, code quality, rule implementation, alert latency, Telegram delivery, test coverage, and production readiness. No ranking against LIFEOS code quality can be inferred from the unavailable repository.

**Lesson for LIFEOS:** the first live journey must be equally legible. One real incoming schedule change should become a concise consequence graph, approved actions, and independent evidence in each affected service. The screen should expose the source message and action receipts, not merely a polished diagram.

## 2. FORGE — strong orchestration idea with important demo defaults

The [repository](https://github.com/VanshMomaya7/Forge) is a TypeScript monorepo. Its [shared task contract](https://github.com/VanshMomaya7/Forge/blob/77417639b9bd7a8d4d96cfdd5d540b52a6cfbc88/shared/task.ts) gives the UI, engine, evals and deployment one task state. [Component building](https://github.com/VanshMomaya7/Forge/blob/77417639b9bd7a8d4d96cfdd5d540b52a6cfbc88/packages/core/src/build-components.ts) creates detached Git worktrees and runs candidates concurrently. [Codex execution](https://github.com/VanshMomaya7/Forge/blob/77417639b9bd7a8d4d96cfdd5d540b52a6cfbc88/packages/core/src/codex-exec.ts) can invoke `codex exec --json`. Candidates are scored and selected, assembled, and subjected to a [site gate](https://github.com/VanshMomaya7/Forge/blob/77417639b9bd7a8d4d96cfdd5d540b52a6cfbc88/packages/core/src/site/gate.ts) that checks structure and parses TSX with esbuild when available. A [deployer](https://github.com/VanshMomaya7/Forge/blob/77417639b9bd7a8d4d96cfdd5d540b52a6cfbc88/packages/core/src/site/deploy.ts) can call a Codex agent for publication. The [Express/WebSocket server](https://github.com/VanshMomaya7/Forge/blob/77417639b9bd7a8d4d96cfdd5d540b52a6cfbc88/packages/surfaces/src/server/index.ts) streams state to the cockpit and can re-enter orchestration from a CI or telemetry event.

The actual defaults matter. Its [router](https://github.com/VanshMomaya7/Forge/blob/77417639b9bd7a8d4d96cfdd5d540b52a6cfbc88/packages/core/src/router.ts) routes the site path to simulation when the Codex CLI is unavailable or real mode is disabled, and also falls back after a real-path error. The [simulation](https://github.com/VanshMomaya7/Forge/blob/77417639b9bd7a8d4d96cfdd5d540b52a6cfbc88/packages/core/src/site/simulate.ts) emits staged progress, fixed candidate scores and a preview URL, then marks the task `shipped`. [Candidate building](https://github.com/VanshMomaya7/Forge/blob/77417639b9bd7a8d4d96cfdd5d540b52a6cfbc88/packages/core/src/build-components.ts) can write fallback artifacts when agents do not produce files. `FORGE_DEPLOY` is opt-in, and the server's task map is in memory. These are code observations, not a claim about what happened in the judged demo.

**Lesson for LIFEOS:** use one durable event/action contract, make every transition observable, and gate release on actual execution. For LIFEOS, a synthetic run must never be labeled as a completed live ripple; missing provider output must block the action rather than generating a convincing substitute.

## 3. RedShield_Agent — closed-loop verification and explicit uncertainty

The [repository](https://github.com/ritisha12345/RedShield_Agent) implements `ATTACK -> JUDGE -> ANALYZE -> PATCH -> VERIFY -> REPORT`. [Attack generation](https://github.com/ritisha12345/RedShield_Agent/blob/a6939d5ededb31620f3fbc75448f0d92c96dcf48/agent/attacker.py) creates category-tagged probes. The [target adapter](https://github.com/ritisha12345/RedShield_Agent/blob/a6939d5ededb31620f3fbc75448f0d92c96dcf48/target/adapter.py) supports Python imports and HTTP endpoints, including patched-prompt retests. The [judge](https://github.com/ritisha12345/RedShield_Agent/blob/a6939d5ededb31620f3fbc75448f0d92c96dcf48/agent/judge.py) returns typed safe, violation, inconclusive or error outcomes. The [verifier](https://github.com/ritisha12345/RedShield_Agent/blob/a6939d5ededb31620f3fbc75448f0d92c96dcf48/agent/verifier.py) reruns the same successful attacks with a proposed patch; the [reporter](https://github.com/ritisha12345/RedShield_Agent/blob/a6939d5ededb31620f3fbc75448f0d92c96dcf48/agent/reporter.py) exposes before/after outcomes and remaining risks. FastAPI exposes scan status and server-sent events; thread or Celery execution and Firestore persistence are configurable.

Its [README](https://github.com/ritisha12345/RedShield_Agent/blob/a6939d5ededb31620f3fbc75448f0d92c96dcf48/README.md) and [scan runner](https://github.com/ritisha12345/RedShield_Agent/blob/a6939d5ededb31620f3fbc75448f0d92c96dcf48/tasks/runner.py) explicitly allow mock target mode and fall back to a generic mock when no target is configured. The production result therefore depends on configuration and actual target access. A model-based judge is evidence from a second model, not an independent proof of safety; manual review remains necessary for serious claims.

**Lesson for LIFEOS:** show a proposed action and its executed read-back side by side. Classify outcomes as verified, failed, inconclusive/uncertain, or blocked, and retain the source and receipt needed to audit each claim. Retest the exact failure after a fix; do not replace the test with a different example.

## Competitive positioning for a real LIFEOS release

| Dimension | Winner pattern | LIFEOS current state | Release bar |
| --- | --- | --- | --- |
| Single vivid job | Air Secure: footage to incident to Telegram proof | LIFEOS supports flight/meeting plans; hero run is not yet accepted across providers | One real event drives at least two real service changes and a visible evidence trail. |
| Live state | FORGE cockpit streams candidate and gate events | LIFEOS has a ripple panel over its own provider summaries | Every displayed transition comes from a persisted LIFEOS event/action state and links to a provider receipt. |
| Verified loop | RedShield retests the same failed attack | LIFEOS has approvals and some read-back code; full live cross-app run remains unverified | Every action must have its own independent read-back or remain uncertain. |
| Honest operation | Strong demos can still contain simulated paths | Public Railway service uses demo providers; live accounts are local | Production mode cannot silently seed or substitute data; demo mode is separate and visibly labeled. |
| Exact app UI | None of these winners establishes this requirement for LIFEOS | Current Discord/WhatsApp panels are LIFEOS-rendered summaries | Actual signed-in provider pages must load in the shipped Windows window and survive restart. |

This is a plan for meeting a top-tier product bar, **not a defensible numerical “top 1%” ranking**. Quality will be judged by a real end-to-end acceptance recording, reliability, security, usability, and release evidence.

## LIFEOS baseline checked for this review

- The current frontend build fails: `npm run build` reports `Failed to resolve /src/desktop.tsx` from `frontend/desktop.html`. The untracked Electron scaffold is incomplete.
- [`docs/RELEASE_STATUS.md`](RELEASE_STATUS.md) records a password-protected Railway **demo** using demo providers, local live account reads, isolated Discord/WhatsApp sends with read-back, and no accepted full cross-provider workflow. Its older Maps/connected-screen paragraphs are stale after the 17 September source removal and must be reconciled during release work.
- [`backend/lifeos/engine.py`](../backend/lifeos/engine.py) has plan-version approvals, a durable execution journal, and uncertain-state protection after interruption. [`backend/lifeos/planning.py`](../backend/lifeos/planning.py) still seeds synthetic records in demo mode. [`backend/lifeos/app_screens.py`](../backend/lifeos/app_screens.py) fetches real bounded records in live mode, but [`frontend/src/components/ConnectedApps.tsx`](../frontend/src/components/ConnectedApps.tsx) renders LIFEOS's own views, not the provider websites.
- [`docs/EXACT_APP_WINDOW_PLAN.md`](EXACT_APP_WINDOW_PLAN.md) already proposes Electron `WebContentsView`. Electron [documents the view](https://www.electronjs.org/docs/latest/api/web-contents-view) and [requires strict remote-content isolation](https://www.electronjs.org/docs/latest/tutorial/security). The actual Discord/WhatsApp compatibility and sign-in behavior remain untested.
- Source searches found Maps references only in a historical test, but deployment is older than the removal. Verify the released image and UI separately; source removal alone is not production removal.

The implementation sequence, file ownership and proof gates are in [the real-product implementation plan](superpowers/plans/2026-09-17-lifeos-real-product.md).
