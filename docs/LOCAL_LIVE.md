# Local live instance

## Current desktop WhatsApp runtime

After WhatsApp QR enrollment, its saved Windows Chromium profile reopened successfully in a visible browser. Headless Chromium received WhatsApp's unsupported-browser screen. The current API therefore runs natively on Windows at the same `http://localhost:8010`, with `LIFEOS_WHATSAPP_HEADLESS=false`. The prior live API container is stopped. The existing live PostgreSQL volume is retained, with its database port exposed only on `127.0.0.1:55439` through `.private/compose-native.yml`. The demo container remains separate.

The local launcher `.private/run_native_live.py` loads private credentials, points to that same database, and enables the enrolled profile. Restart it from the project directory with `.venv/Scripts/python .private/run_native_live.py`, only after the existing native process has stopped. The current PID is recorded in `.private/native-live.pid`; verify its identity before stopping it. Do not start the old live API container simultaneously. This desktop process requires the Windows session and does not automatically restart after reboot. Browser enrollment and the app must never open the profile concurrently.

The account session and the exact configured chat `Rohith CSE A` were verified in a visible browser without sending. The selected header and composer matched that chat. Actual delivery remains unverified and sending still requires application approval.

## Earlier container-only deployment

The local live instance uses `http://localhost:8010`, matching the configured Google OAuth callback. The existing demo remains at `http://127.0.0.1:18090`. These instances have separate PostgreSQL volumes and application state.

Verified locally on 2026-09-13: both live containers healthy, database ready, unauthenticated sessions rejected, configured owner login and CSRF logout accepted. The Connect Google endpoint generated an HTTPS Google consent URL with the exact localhost:8010 callback and PKCE. The URL was not followed and no OAuth grant or external account mutation was performed. Live image: `sha256:162de8e1b06c5650742d8406de371f43cba4eaeb0fe2671286d17e3d17fd1adb`.

The populated `.env` stays private. The local override `.private/compose-live.yml` selects live mode, local-development cookie behavior and the exact localhost callback. This loopback-only configuration is for local use; public deployment requires the HTTPS production configuration described in [DEPLOYMENT.md](DEPLOYMENT.md).

After configuration validation and building the current source:

```powershell
docker build -t lifeos:live-local .
$env:LIFEOS_PORT='8010'
docker compose -p lifeos-live -f docker-compose.yml -f .private/compose-live.yml up --no-build -d --wait
```

Open `http://localhost:8010`, sign in with the password configured in `.env`, then select **Connect Google** in Integrations. Complete Google's consent flow yourself. Use `localhost` consistently for this flow because the registered callback uses that hostname. API keys and OAuth client credentials do not themselves grant access to your Google account; successful consent is still required.

The initial readiness/login check does not send messages, modify calendar events or grant OAuth access. Review and approve any later proposed application actions in the interface. Live WhatsApp additionally requires its dedicated manually enrolled browser profile and a browser-enabled runtime; the default application image does not contain Chromium.

Maps may remain unconfigured. The planner omits route and pickup-time actions and displays that limitation; it does not invent a travel duration. Google consent is still required for Gmail/Calendar/Drive, and Discord requires access to the configured channel.

Check service state without printing secret configuration:

```powershell
$env:LIFEOS_PORT='8010'
docker compose -p lifeos-live -f docker-compose.yml -f .private/compose-live.yml ps
```

Stop only this instance with the same Compose files and project name followed by `down`. Preserve its named volumes unless you intend to delete the live instance's stored records.
