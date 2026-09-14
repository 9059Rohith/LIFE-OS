# Public demo release — 14 September 2026

- **URL:** https://lifeos-public-production.up.railway.app
- **Railway deployment:** `0f9152ca-fd95-4a59-881b-ce676d6c1452` (`SUCCESS`)
- **Service:** `lifeos-public`, one US West replica, separate 500 MB volume at `/app/data`

This is a password-protected **demo-provider** installation. It does not contain the local Google, Discord or WhatsApp credentials or browser profile. The owner can read the generated workspace password from `.private/public-demo-password.txt` on the deployment machine and share it separately with reviewers. The password and Fernet key are Railway service variables, not source files. The server-side OpenAI key enables actual speech input/output; its value is not exposed to the browser or this report.

## Acceptance observed

- HTTPS `/`, `/health` and `/ready` returned HTTP 200. Anonymous `/api/session` returned HTTP 401.
- An authenticated Chromium browser opened the password form, signed in, ran the flight hero demo, approved the plan and observed the resolved read-back state: **1/1 public browser check passed**.
- The public API executed flight and meeting demo workflows with **6/6** and **4/4** actions verified, respectively. `/api/audit/verify` reported a valid chain.
- A previously resolved event remained available after restarting only the LIFEOS Railway service. The volume was mounted during the new deployment.
- The deployed API synthesized a short sample with OpenAI and transcribed that returned audio; the speech round trip passed. This verifies provider-backed API voice, not a physical microphone or speaker.
- The local release checks before deployment passed: **102 Python tests**, Ruff, strict mypy on the three enforced modules, frontend lint/typecheck/build, Docker Compose config and shell syntax. The source credential-pattern scan passed. The earlier isolated demo Chromium suite passed **8/8**.

Reproduce the public API workflow with `python scripts/check_public_demo.py --url https://lifeos-public-production.up.railway.app --password-file <private-password-file> --scenario flight --voice`. Omit `--voice` to avoid metered OpenAI requests. The public browser check uses `frontend/e2e/public-demo.spec.ts` with `E2E_BASE_URL` and `PUBLIC_DEMO_PASSWORD_FILE` set locally.

## Remaining acceptance boundaries

This URL is a working end-to-end **demo**, not a fully accepted live-account production installation. It does not perform live Gmail/Calendar/Discord/WhatsApp mutations, and the container intentionally lacks the headed Chromium runtime needed for WhatsApp. The Google Maps Routes key still returns a 403 restriction error, and the Google Cloud project has billing disabled. A real approved multi-provider hero workflow, hardware microphone/speaker use, broader event classes, and target-host backup/restore and independent security review remain open. The app is intentionally single-owner and single-worker. Railway's Free-plan sleeping and credit limits also mean this is a review/demo host rather than an uptime commitment.
