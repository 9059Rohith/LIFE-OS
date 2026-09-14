# Local deployment evidence

Measured on 2026-09-13 using Windows host Python, Docker Desktop's Linux engine 28.5.1, Python 3.12 container runtime, PostgreSQL 17 and Node 22 build stage. These are local checks, not an external production deployment.

Final running image: `sha256:5ec9346c213ef1cc448cf8ce7d5d6c808712d21db3261f816551a58947aa997a`. The served frontend references `index-C7TTenX7.js` and `index-1YhYsP8W.css`. Local handoff URL: `http://127.0.0.1:18090` (Compose project `lifeos-verify`).

## Executed checks

| Check | Observed result |
|---|---|
| `docker compose config --quiet` | Exit 0 |
| `docker build -t lifeos:local-verified .` | Exit 0; frontend and Python application packaged |
| Isolated Compose project `lifeos-verify`, port 18090 | PostgreSQL and application both healthy |
| `/health` | HTTP 200, mode `demo` |
| `/ready` | HTTP 200, database `connected` |
| Frontend `/` | HTTP 200 |
| Runtime identity | `uid=10001(lifeos) gid=10001(lifeos)` |
| PostgreSQL schema revision | Version 1 |
| Five full PostgreSQL hero workflows | Every action reached `verified`; raw timings in `benchmark-postgres.json` |
| Restart application and database | Readiness restored; record counts preserved |
| Source scripts | Ruff passed; known-credential-pattern scan passed |
| Python dependency audit after remediation | Exit 0, zero known findings across 73 installed dependency entries; local unpublished `lifeos` package skipped by advisory service |
| Installed dependency consistency | `python -m pip check`: no broken requirements |

Before and after restarting both containers, PostgreSQL retained 6 application records, 85 audit records, 5 events and 1 session. These counts describe the isolated verification database only. Restart persistence does not establish backup restoration or cross-host disaster recovery.

After the final dependency and frontend rebuild, application-container recreation preserved all 10 benchmark events, 12 application records, 170 audit records and 2 sessions accumulated by the two PostgreSQL runs. Later interactive/browser tests may add their own isolated session records.

Dependency remediation pinned cryptography 50.0.1, pydantic-settings 2.14.2, python-multipart 0.0.32 and pytest 9.0.3, and upgraded pip to 26.2.1 in the development environment, CI setup and Dockerfile. [Raw Python advisory report](pip-audit.json) retains the local-package skip reason. The unpublished application's security is assessed through its source and tests, not a PyPI advisory lookup. This audit covers known Python advisories at execution time, not operating-system image vulnerabilities.

The final Linux runtime was independently enumerated in [runtime-dependencies.json](runtime-dependencies.json). [runtime-requirements.txt](runtime-requirements.txt) records every installed external package, including Linux-only uvloop and pip. [Runtime advisory audit](runtime-pip-audit.json) returned zero known findings. That audit disables re-resolution because it uses the complete installed Linux inventory from the container while the auditing client runs on Windows. It omits only the unpublished application itself, whose source is tested separately. This is an observed dependency snapshot, not a hash-locked cross-platform installation file.

## Measurements

| Local setup | Runs | Median planning | Median approval request | Median execute + read-back | Median total |
|---|---:|---:|---:|---:|---:|
| Windows API + SQLite | 5 | 266.7 ms | 49.2 ms | 500.1 ms | 1109.6 ms |
| Linux container API + PostgreSQL | 5 | 368.4 ms | 70.1 ms | 690.3 ms | 1002.1 ms |

Raw request measurements: [SQLite](benchmark.json), [PostgreSQL](benchmark-postgres.json). Medians of stages do not necessarily sum to the median total. Each test used local deterministic demo records, a sequential HTTP client and no human approval delay; the two clients ran concurrently against their separate servers. Other applications and browser tests were active on the host. This is a functional latency sample, not a controlled database comparison or load benchmark. No live provider, model, voice or network latency is represented.

## Remaining deployment acceptance

Target-host HTTPS/ingress, secure production session behavior, live credential consent/refresh, remote writes/read-back, hardware microphone capture, dedicated WhatsApp login, backup restoration, load testing and independent security review remain environment-specific. No image was published, no external service was deployed, and no live account message was sent during these checks.
