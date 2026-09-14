# Public hosting assessment

No public production deployment was created during the 2026-09-13 hosting assessment. The existing native Windows application and PostgreSQL container were left running. Local success does not establish availability from the public internet.

## Available accounts and actual blockers

| Target | Read-only evidence | Deployment implication |
| --- | --- | --- |
| Vercel | A connected team is available. | The current application depends on one long-lived backend process, in-memory locks and a persistent Chromium profile. Ordinary Vercel Functions do not preserve that architecture. |
| Railway | The $0 Free subscription was activated successfully; the account reports `FREE`, `ACTIVE`, and $1 remaining usage credit. Creation of a new `lifeos-public` project was rejected: `Free plan resource provision limit exceeded. Please upgrade to provision more resources!` | Public deployment is blocked by the account's free provisioning quota. No LIFEOS resources or deployment were created. Existing unrelated resources were preserved. |
| Google Cloud | Existing project `lifeos-508512` has billing disabled. Compute Engine and Cloud Run APIs are disabled. | There is no usable deployment target established in this project. Enabling services or billing and provisioning compute was not attempted. |

The assessment activated only Railway's $0 Free subscription after checking the official pricing and confirming no payment method was present. It did not purchase a plan, create resources, copy secrets to a provider, expose browser debugging ports or publish a frontend-only substitute.

## Prepared public-instance option

A separate public instance can serve both the real FastAPI backend and React frontend from the existing Docker image. Use one worker and one replica with a persistent 0.5 GB volume at `/app/data` and `LIFEOS_DATABASE_URL=sqlite:////app/data/lifeos.db`. This starts with its own database; it does not require copying the local PostgreSQL state. Keep `LIFEOS_WHATSAPP_ENABLED=false` and show WhatsApp as disconnected until a cloud browser is enrolled. The local native instance can continue using its own database and signed-in profile.

Set `PORT=8000`, use `/ready` for the health check, configure the generated HTTPS origin and exact Google callback, and provide selected credentials via `railway variable set KEY --stdin --skip-deploys`. Supply values from a protected process without printing them or placing them in command-line arguments. Never upload the local `.env` or profile. Google requires consent on the public instance.

Railway volumes are root-owned initially, while this image runs as UID 10001. Before deployment, provide a startup initializer that owns only the mounted application-data directory and then drops back to UID 10001. Boot migrations must run after the volume is mounted. Verify persistence across a restart and the full authentication flow from HTTPS before reporting a working public URL.

Railway's Free plan permits one replica, 0.5 GB RAM and 0.5 GB volume storage and includes $1 of usage each month. This is a limited free instance rather than an unlimited uptime commitment. The existing account's provisioning quota currently prevents even creating the separate project; do not delete or repurpose unrelated projects to bypass it.

## Compatible deployment for the complete application

Use a persistent host with PostgreSQL, durable application storage, a single backend process and an HTTPS ingress. For the current headed WhatsApp integration, the host must also provide an operator-accessible desktop session for Chromium and manual QR enrollment. A dedicated Windows host most closely matches the locally validated runtime. A Linux host would require installation and validation of browser dependencies, a display session and a newly enrolled dedicated profile.

Keep the React build and API on the same public origin. Preserve the single Uvicorn worker and single replica: the engine and provider locks are currently process-local. A rolling deployment must stop the old process before the new process can execute actions; two replicas must not access one Chromium profile concurrently.

The existing Dockerfile is appropriate for an API service with ordinary integrations, but it does not install Playwright or Chromium. Deploying it unchanged cannot establish a fully working WhatsApp integration. A Railway service with a persistent volume is a possible API hosting option after an explicit resource budget is established and browser hosting is resolved.

## Target-host release procedure

1. Establish the host, its access credentials, a stable public hostname and any resource budget. Configure HTTPS ingress and keep PostgreSQL and the backend's direct port private.
2. Build the frontend and install the pinned backend dependencies on the target. For WhatsApp, install the pinned development Playwright dependency and Chromium, then manually enroll a dedicated profile on that host. Never publish or commit the local `.env` or `.private` directory.
3. Provision PostgreSQL and migrate data using an encrypted backup and restore procedure. Preserve the existing token encryption key when restoring encrypted provider tokens; replacing it would require provider reconnection. Verify the restored data before cutting over.
4. Supply production secrets through protected host configuration. Set `LIFEOS_MODE=live`, `LIFEOS_ENVIRONMENT=production`, the real HTTPS `LIFEOS_ALLOWED_ORIGINS`, the same-origin Google callback URI, PostgreSQL URL, owner password and encryption key. Configure the dedicated browser profile path, allowed contact and headed mode if WhatsApp is enabled.
5. Register the exact HTTPS Google redirect URI with the existing OAuth client. Complete consent again on the target when required. The local development callback is not the public callback.
6. Stop the old execution process at cutover, run `python -m lifeos.migrate`, and start one Uvicorn worker under a service supervisor. Allow forwarded headers only from the actual trusted ingress. Configure automatic restart, persistent database backups and encryption-key recovery.
7. Verify `/health` and `/ready` from the public HTTPS URL; check authentication, Secure cookies, origin checks and sign-out. Verify each configured integration on the target, including Google refresh, approved writes and independent read-back, voice round trip and dedicated WhatsApp conversation behavior. Keep evidence without recording tokens or personal message bodies.
8. Record the public URL, deployed commit/image, target configuration and acceptance results. Report a production link only after this target-host verification passes.

See [DEPLOYMENT.md](DEPLOYMENT.md) for configuration and backup details. The host and budget are still required inputs; a temporary tunnel would remain dependent on the local desktop and is not a production deployment.

## Platform references

- [Vercel Functions limitations](https://vercel.com/docs/functions/limitations): function execution constraints; the incompatibility conclusion above also follows from this application's process-local locks and browser profile design.
- [Railway Docker Compose deployment](https://docs.railway.com/guides/docker-compose): mapping services, networking and volumes to hosted resources.
- [Railway persistent volumes](https://docs.railway.com/volumes): runtime storage that survives restarts and deployments.
- [Railway pricing](https://docs.railway.com/pricing/plans): Free subscription price and resource limits.
- [Railway variable CLI](https://docs.railway.com/cli/variable): setting a secret value through standard input.
