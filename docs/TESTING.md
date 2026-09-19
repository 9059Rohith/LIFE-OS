# LIFE-OS Testing Record

## Current local results

These results were run from the current checkout on 20 September 2026.

| Check | Result |
| --- | --- |
| `python -m pytest -q` | 141 passed, 1 warning |
| `python scripts/run_lifeos_evals.py` | 6/6 passed |
| `python -m ruff check backend tests scripts` | Passed |
| `python scripts/scan_secrets.py` | No known credential patterns found |
| `npm run typecheck` in `frontend` | Passed |
| `npm run lint` in `frontend` | Passed |
| `npm run build` in `frontend` | Passed |
| `E2E_PORT=5174 npm run test:e2e -- --project=chromium` | 15 passed, 1 skipped |
| `npm test` in `desktop` | 8 passed |

The skipped browser test requires private public-demo credentials. It is not counted as a pass.

## Coverage shape

- Backend unit and integration tests cover planning, security, limits, recovery, providers, event streams, work records, and desktop bridge behavior.
- Browser tests cover approval invalidation, connected application states, privacy controls, voice approval, work persistence, responsive layout, injection blocking, and navigation.
- Desktop tests cover trusted navigation, provider isolation, WhatsApp selection, and exact outgoing-message verification.
- Offline evals cover flight extraction, meeting extraction, relative dates, clarification, unrelated input, and instruction-like prompt injection.

## Live evidence boundary

Fixtures and local tests do not prove a third-party account is reachable. Hosted health, login, read-access, and the recorded authenticated demo are tracked separately in [RELEASE_STATUS.md](RELEASE_STATUS.md) and [FINAL_RELEASE_REPORT.md](FINAL_RELEASE_REPORT.md).
