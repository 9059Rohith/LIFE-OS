<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:1f8f61,100:3967a5&height=180&section=header&text=LIFE-OS&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Consequence-Aware%20Automation%20for%20Your%20Digital%20Life&descAlignY=58&descSize=16" width="100%" />

</div>

---

## Project Name

**LIFE-OS** — A consequence-aware operating system for your digital life.

---

## One-Line Description

LIFE-OS detects a real-world change, maps its downstream consequences across Calendar, Gmail, Discord, and WhatsApp, builds a typed action plan, waits for human approval, executes with idempotency guarantees, and verifies each result by independently reading every provider back.

---

## The Problem

Every day, one event changes and silently invalidates a dozen others. A meeting moves. That single fact needs to reach the calendar entry, every invitee's inbox, the coordination chat channel, and the team messaging thread. Doing this manually is slow, error-prone, and precisely the kind of invisible coordination work that gets dropped under pressure.

Existing tools force a bad choice:

- **Rule-based automation** only handles workflows that were pre-configured. It cannot reason about a change it was never taught, and it has no model of downstream consequences.
- **Autonomous AI agents** can reason about anything but handing an open-ended agent write access to your calendar, email, and messaging accounts is a trust problem. You cannot easily see what it did, verify whether it worked, or confirm who authorized it.

---

## The Solution

LIFE-OS takes a **third path**:

```
Real-world change described
          |
          v
AI extracts a structured event  (bounded, server re-validated)
          |
          v
Server builds a typed consequence graph  (deterministic, typed actions)
          |
          v
Human reviews the exact arguments  (approval bound to content hash)
          |
          v
Bounded provider execution  (idempotency keys, owner locks, retries)
          |
          v
Independent provider read-back  ("verified" != "API returned 200")
          |
          v
Tamper-evident audit entry
```

AI handles **understanding**. The server handles **planning and execution**. Humans handle **approval**. The system handles **verification**.

---

## Key Innovation

**The consequence graph and the verification model are the core innovation.**

Most systems treat "the API returned 200" as success. LIFE-OS does not. After every execution, it independently reads provider state back and compares it to what was planned. If the state does not match, the action becomes an explicit `uncertain` state routed to manual review — never optimistically reported as done.

This makes LIFE-OS the only system in this space with a formal distinction between **executed** and **verified**.

---

## What Is Built

| Component | Description |
|---|---|
| **React command center** | Web UI for event intake, consequence graph, action review, audit trail, workspace pages, and mobile layout |
| **FastAPI API** | Authenticated routes, CSRF protection, origin validation, rate limits, health endpoints |
| **Workflow engine** | Typed extraction, consequence planning, approval state machine, idempotent execution, compensation |
| **Provider adapters** | Owner-scoped, allowlisted adapters for Google Calendar, Gmail, Drive, Discord, and WhatsApp |
| **Verification layer** | Independent provider read-back before any action is marked verified |
| **Audit chain** | Tamper-evident history with inspectable evidence for every step |
| **Electron desktop app** | Windows companion with isolated Discord and WhatsApp web views and a signed-in bridge queue |

---

## Live Demo

| Resource | Link |
|---|---|
| 🌐 Live workspace | [lifeos-live-production.up.railway.app](https://lifeos-live-production.up.railway.app) |
| 🎬 Authenticated demo video (4:00) | [YouTube](https://www.youtube.com/watch?v=efi747ciy18) |
| 🖼️ Product poster | [docs/poster/lifeos-poster.png](docs/poster/lifeos-poster.png) |
| 📸 Full product tour (11 screenshots) | [docs/screenshots/](docs/screenshots/) |

The live workspace has an isolated **interactive demo mode** — click **Try interactive demo** to run a full consequence workflow on sample data without credentials.

---

## Proof of Quality

| Signal | Evidence |
|---|---|
| Backend tests | **141 passed** (`python -m pytest -q`) |
| Playwright end-to-end tests | **15 passed, 1 skipped** |
| Desktop tests | **8 passed** (`npm test` in `desktop/`) |
| Offline extraction evals | **6/6 passed** |
| Type checking | `mypy --strict` — passing on core modules |
| Linting | `ruff check` — passing |
| Frontend build | `npm run build` — passing |
| Secret scan | `scan_secrets.py` — no known credential patterns |
| Dependency audit | `pip-audit` + `npm audit` — no critical vulnerabilities |
| Security documentation | Full threat model, mitigations, honest scope in [SECURITY.md](SECURITY.md) |
| License | MIT — [LICENSE](LICENSE) |

---

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React 18, TypeScript, Vite, Playwright |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic |
| AI | OpenAI-compatible structured extraction (optional), deterministic parsing first |
| Database | SQLAlchemy, SQLite (default), PostgreSQL (Docker Compose) |
| Desktop | Electron with isolated provider web views |
| Deployment | Docker, Railway (live), same-origin static serving |
| Quality | pytest, Playwright, ruff, mypy, ESLint, pip-audit, npm audit |

---

## Integrations

Google Calendar · Google Gmail · Google Drive · Discord · WhatsApp · Owner-scoped work records

All integrations use owner-scoped OAuth or bot tokens, are bounded to allowlisted operations, require human approval for high-impact writes, and are independently verified via provider read-back.

---

## Why This Is Defensible

1. **Architecture depth** — consequence graph + approval hashing + read-back verification is a production-grade pattern, not a demo trick
2. **Honest engineering** — `uncertain` state, explicit failure handling, tamper-evident audit trail
3. **Breadth of integrations** — five bounded provider surfaces, with live read evidence and provider-specific write boundaries documented
4. **Test evidence** — 141 backend tests, 15 browser passes, 8 desktop tests, and 6/6 offline extraction evaluations
5. **Security discipline** — CSRF, origin validation, approval hashes, idempotency keys, credential encryption
6. **Full delivery** — web app, desktop companion, hosted workspace, demo video, poster, screenshots, and evidence-led documentation

---

## Documentation

Full documentation is in [README.md](README.md) (964 lines, 20+ sections) and the [docs/](docs/) folder (47 files).

Quick-access guide for judges: [JUDGES.md](JUDGES.md)

---

<div align="center">

*🧠 Consequence-aware. 🔏 Approval-bound. ✅ Verified.*

**[@9059Rohith](https://github.com/9059Rohith) · [github.com/9059Rohith/LIFE-OS](https://github.com/9059Rohith/LIFE-OS)**

</div>
