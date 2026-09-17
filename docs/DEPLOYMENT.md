# Deployment

The provided image compiles React and runs FastAPI as a non-root user. Compose adds PostgreSQL with a named data volume and a readiness dependency. The application binds to host loopback by default. A production release still requires an operator-controlled HTTPS ingress, secrets, backups and live acceptance tests.

## Windows desktop companion

The current Windows installer is built with `cd desktop; npm ci; npm run dist:win` and written to `artifacts/windows/`. It opens the trusted hosted HTTPS workspace by default and shows the actual Discord and WhatsApp websites in separate sandboxed views. Sign in with the live workspace password. The local offline screen retries the configured workspace connection and contains no sample account data. For local development, set `LIFEOS_DESKTOP_URL=http://127.0.0.1:8010/desktop.html` and start the local backend first. The installer contains the Electron shell only; it does not bundle the backend or a WhatsApp sending worker. It is unsigned and remains an online desktop companion, not an independently hosted backend.

The live `My work` module requires database schema revision 2. Startup applies its owner/kind/time index without deleting existing records. Back up the live database before upgrading, as with any release. `GET /api/work/dashboard` returns one owner-scoped snapshot for the UI; projects, goals, tasks, habits, notes, local calendar entries, activity and reminders come from saved records.

## Local container demonstration

Install Docker Engine/Desktop and Docker Compose. Copy `.env.example` to `.env`, then set `POSTGRES_PASSWORD` to a random hexadecimal value, `LIFEOS_AUTH_PASSWORD` to a unique password of at least 16 characters, and `LIFEOS_ENCRYPTION_KEY` to a generated Fernet key. The example now defaults to live mode and starts with an empty workspace. Hex avoids URL escaping ambiguity in the Compose database URL.

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
.venv\Scripts\python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

Open `http://localhost:8000`. If that port is occupied, set `LIFEOS_PORT` in `.env` and add the resulting browser origin to `LIFEOS_ALLOWED_ORIGINS`. For Google OAuth, also change `LIFEOS_GOOGLE_REDIRECT_URI` to that host port; the template uses development port 8010. Compose overrides the SQLite URL with PostgreSQL. Startup runs `python -m lifeos.migrate` before Uvicorn. Probe `http://localhost:8000/health` and `/ready` (adjust the port if changed). Logs: `docker compose logs --tail 100 lifeos`. Stop without deleting records: `docker compose down`. Named volumes survive that command.

Do not use `docker compose down -v` unless you intend to delete stored data. The application image omits browser automation binaries; ordinary API integrations and local demo mode do not require them.

## Railway hosted live workspace

The current source is deployed separately at `https://lifeos-live-production.up.railway.app` as the `lifeos-live` service in EU West. It uses one replica and its own volume mounted at `/app/data`; its database URL is `sqlite:////app/data/lifeos.db`. The service has `LIFEOS_MODE=live`, `LIFEOS_ENVIRONMENT=production`, a password, encryption key, HTTPS allowed origin, Google client settings, Discord bot settings and server-side OpenAI settings. The exact credentials are stored in Railway variables, not in this repository. Browser login, a work-record write and read-back across a service restart, deletion, empty state and Discord read access passed on 18 September 2026.

The hosted owner now holds the existing owner's Google grant, re-encrypted under the hosted key after a volume backup. Hosted Gmail, Calendar and Drive passed live read checks on 18 September 2026. For future reconnects, add `https://lifeos-live-production.up.railway.app/api/integrations/google/callback` to the OAuth web client's authorized redirect URIs; a new authorization attempt still receives `redirect_uri_mismatch`. Do not copy the local `.env` or database into the public service. WhatsApp sending remains disabled because this image has no browser worker. The older `lifeos-public` service remains an isolated demo.

## Railway public demo (single service)

Create one Railway service from this repository using its Dockerfile. Add one persistent volume mounted at `/app/data`, set the service to one replica, and configure `/ready` as the health check. The startup command is already in the image: it repairs ownership of the mounted `/app/data` directory, drops to UID 10001, migrates the SQLite database, and starts one Uvicorn worker. Railway supplies `PORT`; the image uses it automatically.

Set these Railway variables in the service's secret-variable UI. Replace `https://your-public-domain` with the generated Railway HTTPS domain before the first deploy. Do not copy `.env` or any local database/profile to Railway.

```text
LIFEOS_MODE=demo
LIFEOS_ENVIRONMENT=production
LIFEOS_PUBLIC_DEMO=true
LIFEOS_DATABASE_URL=sqlite:////app/data/lifeos.db
LIFEOS_AUTH_PASSWORD=<unique password of at least 16 characters>
LIFEOS_ALLOWED_ORIGINS=["https://your-public-domain"]
LIFEOS_WHATSAPP_ENABLED=false
```

This deployment uses demo application records. It does not include Playwright or Chromium and does not support a live WhatsApp session. Keep Gmail, Calendar, Discord and WhatsApp credentials off this service. An optional server-side OpenAI key enables real speech input/output; distribute the workspace password narrowly because voice requests incur provider usage. After Railway assigns its HTTPS domain, update `LIFEOS_ALLOWED_ORIGINS`, redeploy, then verify `/health`, `/ready`, sign-in, a demo workflow, and persistence after a restart. Download or back up `/app/data/lifeos.db` before deleting the volume; the volume provides persistence but is not a backup.

## Production configuration

1. Configure a private PostgreSQL service and a distinct database for each environment. Use TLS for remote database connections.
2. Generate a long owner password and a Fernet key:

   ```powershell
   .venv\Scripts\python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

3. Set `LIFEOS_MODE=live`, `LIFEOS_ENVIRONMENT=production`, `LIFEOS_AUTH_PASSWORD`, `LIFEOS_ENCRYPTION_KEY`, and `LIFEOS_ALLOWED_ORIGINS=["https://your-host.example"]` using your host's secret manager. Do not use the example hostname literally.
4. Set provider credentials only for the integrations you will use. Register the exact HTTPS Google callback. Complete consent and test-user requirements.
5. Put the application behind an HTTPS reverse proxy/load balancer. Preserve Host/Origin and configure trusted proxy headers explicitly for your ingress. Do not blindly trust forwarded headers from the public network. Restrict the backend port to the proxy.
6. Run migrations as a release step, then start **one** Uvicorn worker. The image also runs migrations at boot for a single-replica deployment. Do not race migrations across replicas.
7. Configure `/health` liveness and `/ready` readiness probes, restart policy, resource limits and database/application monitoring.
8. Run live acceptance checks in dedicated test accounts. Confirm consent, each provider write and independent read-back, expired token recovery, stale approval rejection, failed request handling and sign-out/session behavior.

The cookie and OAuth flow expects the frontend and API on one origin. A separate frontend host requires deliberate routing and cookie/CORS design; it is not covered by the default Compose file. Hosting on a platform is possible with the Dockerfile, but no provider-specific publication is automated here.

## WhatsApp browser worker

Browser automation is opt-in and account-sensitive. Install the Python Playwright extra tooling from the development dependencies and its browser (`python -m playwright install chromium`; Linux also needs system browser dependencies). Provision a dedicated persistent profile with an interactive QR login, set `LIFEOS_WHATSAPP_PROFILE_DIR`, explicitly set the allowed contact, then enable `LIFEOS_WHATSAPP_ENABLED`.

Enroll a dedicated profile locally (this intentionally opens a visible browser for your manual QR login):

```powershell
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python scripts/whatsapp_login.py --profile .private/whatsapp
```

Close that browser before starting backend automation; Chromium cannot share an active profile. Set `LIFEOS_WHATSAPP_PROFILE_DIR` to the same directory. The current adapter runs within the backend process; a separately isolated browser-worker service is future work. Do not mount a personal Chrome profile. Do not expose Playwright/CDP ports. Keep this feature disabled until the dedicated account's selectors, send confirmation and read-back have been manually validated. The default image does not include this runtime.

## Backups and rollback

Use your database platform's encrypted automated backups and point-in-time recovery. Store the token encryption key in a separate recoverable secret store. Validate restoration to an isolated database before launch. Backups contain personal event data and must follow retention rules. Named Docker volumes are persistence, not backups.

Before migration, snapshot the database and retain the prior image. Restore a backup to a new database if a schema change is incompatible; never assume an application-image rollback also reverses its data migration. Test compatibility and restoration for the exact release. Graceful shutdown receives 30 seconds in Compose; inspect interrupted actions before retrying remote effects.

## CI and release gate

`.github/workflows/ci.yml` installs pinned direct Python dependencies and the npm lockfile, runs lint, backend tests, source credential scanning, dependency audits, frontend typechecking/build, Playwright and a container build. An unsuccessful gate blocks the job. No deployment credentials or external publication step is enabled.

Before an operator publishes an image, require the successful CI run for that exact commit, review advisory findings, confirm a restore test, configure environment protection/approval, and record the resulting image digest. Base images are pinned to reviewed digests; update them deliberately when security fixes are released. Python direct dependencies are pinned, but transitive resolution is not a complete hash-locked supply chain.

## Acceptance evidence still required

- Actual Docker build/run and PostgreSQL readiness/migrations on the target host.
- HTTPS cookie and origin enforcement through the real ingress.
- Google OAuth consent/refresh and provider writes/read-back with test accounts.
- Discord bot permissions and target-channel behavior.
- WhatsApp dedicated profile, current DOM selectors and account restrictions.
- OpenAI quota/model access, live transcription/speech, hardware microphone permission.
- Load/resource limits, restart recovery, backup restore and independent security review.

Record dates, versions and evidence for each. Local deterministic tests do not prove these external checks.
