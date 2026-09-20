<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:1f8f61,100:3967a5&height=160&section=header&text=LIFE-OS%20Judge%20Guide&fontSize=40&fontColor=ffffff&animation=fadeIn&fontAlignY=40" width="100%" alt="LIFE-OS Judge Guide" />

# 🧑‍⚖️ LIFE-OS — Judge Quickstart

**Read this first. Everything you need to evaluate LIFE-OS is here.**

</div>

---

## 🏎️ 30-Second Summary

> LIFE-OS is a **consequence-aware automation system** for your digital life. When a real-world event changes — a meeting moves, a deadline shifts — LIFE-OS maps every downstream consequence across Calendar, Gmail, Discord, and WhatsApp, builds an exact action plan, waits for human approval, executes with idempotency guarantees, and verifies each result by independently reading each provider back. **Nothing is marked done until the source of truth confirms it.**

This is not a chatbot. It is not a rule-based scheduler. It is not an autonomous agent with unconstrained write access.
It is a **third option**: AI interprets → server plans → human approves → system executes and verifies.

---

## ⚡ Evaluation Paths

| Time you have | Do this |
|---|---|
| **30 seconds** | Read the summary above and look at the [product poster](docs/poster/lifeos-poster.png) |
| **3 minutes** | Open **[lifeos-live-production.up.railway.app](https://lifeos-live-production.up.railway.app)** → click **Try interactive demo** → run a consequence workflow end to end |
| **5 minutes** | Watch the **[4:00 authenticated demo video](https://www.youtube.com/watch?v=efi747ciy18)** — narrated, subtitled, light-mode, real Calendar → Discord → WhatsApp lifecycle |
| **10 minutes** | Read **[AI and agent boundary](README.md#-ai-and-agent-boundary)** and **[Reliability and failure handling](README.md#️-reliability-and-failure-handling)** |
| **30 minutes** | Clone the repo, run `python -m pytest -q` (141 passing), run `npm run test:e2e` (15 passing), and explore the code |

---

## 🔑 Key Claims and Where to Verify Them

| Claim | Verification |
|---|---|
| **141 backend tests passing** | `python -m pytest -q` or see [docs/FINAL_RELEASE_REPORT.md](docs/FINAL_RELEASE_REPORT.md) |
| **15 Playwright e2e tests passing** | `npm run test:e2e` from `frontend/` |
| **8 desktop tests passing** | `npm test` from `desktop/` |
| **6/6 offline extraction evals** | `python scripts/run_lifeos_evals.py` |
| **mypy --strict passing** | `python -m mypy --strict backend/lifeos/policy.py backend/lifeos/schemas.py backend/lifeos/config.py` |
| **ruff linting passing** | `python -m ruff check backend tests scripts` |
| **Frontend build passing** | `npm --prefix frontend run build` |
| **Secret scan clean** | `python scripts/scan_secrets.py` |
| **pip-audit clean** | See [docs/pip-audit.json](docs/pip-audit.json) |
| **Live deployment reachable** | [lifeos-live-production.up.railway.app](https://lifeos-live-production.up.railway.app) |
| **Authenticated demo video** | [YouTube](https://www.youtube.com/watch?v=efi747ciy18) · [repo artifact](docs/demo/lifeos-authenticated-lightmode-demo-final.mp4) |
| **MIT licensed** | [LICENSE](LICENSE) |

---

## 🏛️ What Makes This Architecture Different

Most AI hackathon submissions fall into one of two buckets:

1. **Rule-based tools** — fast and safe but blind to anything not pre-configured
2. **Autonomous AI agents** — flexible but opaque, with unconstrained write access

LIFE-OS is a **third architecture**:

```
User describes change
        |
AI extracts structured event  <- bounded, server-validated
        |
Server builds consequence graph  <- deterministic, typed
        |
Human reviews EXACT arguments  <- approval hash bound to content
        |
Bounded provider execution  <- idempotency keys, owner locks, preflight
        |
Independent provider read-back  <- verified != "API returned 200"
        |
Tamper-evident audit entry
```

The key insight: **"verified" is not the same as "API returned 200."** LIFE-OS reads provider state back independently after every execution. If state does not match, the action becomes `uncertain` — surfaced for manual review, never silently marked done.

---

## 📁 Repository Structure

```
LIFE-OS/
├── backend/        FastAPI, workflow engine, provider adapters, security
├── frontend/       React + TypeScript + Vite command center + Playwright tests
├── desktop/        Electron app with isolated Discord & WhatsApp web views
├── tests/          141 backend tests across all domains
├── docs/           47 documentation files: architecture, release report,
│                   screenshots, poster, demo assets, security analysis
├── evals/          Offline extraction evaluation suite (6/6 passing)
├── scripts/        Verification, packaging, deployment helpers
├── Dockerfile      Multi-stage production image
├── docker-compose.yml
├── railway.json    Live Railway deployment config
├── ARCHITECTURE.md Full Mermaid system map
├── AI_USAGE.md     AI boundary, models, failure handling
├── SECURITY.md     Threat model, mitigations
└── README.md       Full 964-line documentation
```

---

## 🧪 Quality Gates — All Passed

| Gate | Tool | Status |
|---|---|---|
| Backend unit + integration tests | pytest | ✅ 141 passed |
| End-to-end tests | Playwright | ✅ 15 passed, 1 skipped |
| Desktop tests | npm test | ✅ 8 passed |
| Extraction evals | custom eval runner | ✅ 6/6 |
| Type checking | mypy --strict | ✅ Passed |
| Linting | ruff | ✅ Passed |
| Frontend lint | ESLint | ✅ Passed |
| Frontend build | Vite | ✅ Passed |
| Dependency audit | pip-audit + npm audit | ✅ No critical vulnerabilities |
| Secret scan | custom scanner | ✅ No known credential patterns |

---

## 🔌 Integrations

| Service | Role | Verification boundary |
|---|---|---|
| **Google Calendar** | Read events, plan reschedules, verify after change | OAuth, owner-scoped, idempotency + read-back |
| **Google Gmail** | Read context, send approved notifications | OAuth, owner-scoped, approval-gated |
| **Google Drive** | Surface supporting document context | OAuth, optional read-only |
| **Discord** | Read channel context, send approved messages | Bot token, configured allowlist |
| **WhatsApp** | Send via signed-in desktop companion bridge | Isolated Electron view, explicit bridge job |
| **Work records** | Persist tasks, goals, reminders, habits | Owner-scoped routes, deletion/export controls |

---

## 📖 Key Documentation

| Doc | Purpose |
|---|---|
| [README.md](README.md) | Full 964-line project documentation |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System map with Mermaid diagrams |
| [AI_USAGE.md](AI_USAGE.md) | AI boundary, models, validation, failure handling |
| [SECURITY.md](SECURITY.md) | Threat model and mitigations |
| [docs/FINAL_RELEASE_REPORT.md](docs/FINAL_RELEASE_REPORT.md) | Evidence-based release checklist |
| [docs/HACKATHON_ALIGNMENT.md](docs/HACKATHON_ALIGNMENT.md) | Track-by-track alignment evidence |
| [docs/VERIFICATION.md](docs/VERIFICATION.md) | Verification system deep dive |
| [docs/SAFETY_AND_APPROVAL.md](docs/SAFETY_AND_APPROVAL.md) | Approval integrity details |
| [docs/JUDGE_QUICKSTART.md](docs/JUDGE_QUICKSTART.md) | One-page judge guide (alternate) |

---

<div align="center">

*🧠 Consequence-aware. 🔏 Approval-bound. ✅ Verified.*

**Built by [@9059Rohith](https://github.com/9059Rohith)**

[⬆️ Back to README](README.md)

</div>
