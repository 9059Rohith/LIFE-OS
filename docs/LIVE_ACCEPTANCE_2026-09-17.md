# LIFE-OS live acceptance record

# LIFEOS live acceptance — 17 September 2026

## Current verdict

**Not completed as a live cross-provider product.** A separate password-protected Railway live workspace is now deployed at `https://lifeos-live-production.up.railway.app`. The older `lifeos-public` URL remains a demo. The Windows shell runs locally against the live backend. Its real Discord and WhatsApp sign-in pages were observed on 17 September; the packaged executable visibly rendered signed-in Discord on 18 September, while packaged WhatsApp and restart persistence are still unverified. A complete signed-in, approved, cross-provider ripple has not been accepted on this revision.

## 18 September hosted live deployment

The current source deployed successfully to a new Railway `lifeos-live` service in EU West with a separate persistent `/app/data` volume. Its HTTPS `/health` returned `mode=live`, `/ready` passed, unauthenticated work access returned 401, and its desktop-width browser UI passed login, My work empty state and Integrations navigation. A 390-pixel browser viewport passed the mobile menu, My work, Calendar and no-horizontal-overflow checks. A temporary real task saved through the public API survived a service restart and a new authenticated session; it was then deleted, leaving the hosted workspace empty. This verifies hosted persistence for the work module, not external provider writes.

The hosted integration check returned `read_access_verified` for Discord and `not_connected` for Gmail, Calendar, Drive and WhatsApp. The new Google callback produced `redirect_uri_mismatch`; it must be added to the OAuth client's authorized redirect URI list before the owner can grant the hosted service access. The hosted image does not contain the WhatsApp browser worker, so WhatsApp remains disabled there. The local app's five verified read connections remain separate from this hosted account.

## 18 September connection recheck

The owner has now completed Google consent. A read-only database check found an encrypted Google grant. The first live check returned `read_access_verified` for Gmail, Calendar, Drive and Discord; WhatsApp returned HTTP 502 because an isolated acceptance server also held its Chromium profile. After stopping that competing process and restarting the live server, **all five** integrations returned `read_access_verified`. A new cross-process profile lease blocks concurrent profile opens with a specific error. These checks sent no messages and made no calendar changes. The local `/health` reports `mode: live`; the public Railway `/health` still reports `mode: demo`. Read access does not prove provider writes or an approved ripple.

The current source adds owner-scoped projects, goals, tasks, habits, notes, a real local calendar agenda, saved activity and due reminders. A fresh live test account began with zero work records, saved linked records, checked in a habit, refreshed the data from a second session, verified owner isolation and exported the data. Browser tests created all five record types through the UI and checked linked progress, persistence and mobile layout. The account system still supports one configured owner, so this is not a public multi-user release.

The desktop Google connection flow now opens Google authorization in the system browser and consumes a one-use owner-bound callback state; focused tests cover valid, invalid and replayed callbacks. A Windows companion installer builds locally but depends on the local backend and remains unsigned. A Railway upload of the new source was rejected during the free-tier regional peak-hours window, so no updated public deployment occurred.

After restarting the final local backend, an authenticated live connection check returned HTTP 200 with `read_access_verified` for Gmail, Calendar, Drive, Discord and WhatsApp. This was a read check only. The packaged desktop executable stayed running and its archive contains the offline recovery screen. Signed-in Discord was visible inside the packaged window. Packaged WhatsApp content and approved write/read-back remain unverified.

The pinned-base release-candidate image passed an isolated live SQLite smoke test. A separate PostgreSQL 17 run saved a task, restarted the application container, read the same task back and confirmed schema revision 2. No operator database or unrelated container was changed by these tests.

## Verified on this revision

- The frontend production build contains `desktop.html`, and frontend lint passes.
- The local live FastAPI server returns HTTP 200 for `/health` and `/desktop.html`.
- A fresh isolated SQLite workspace required authentication, showed zero events, rejected a bad password, accepted the configured live password, persisted a clarification event submitted through the UI, and restored its consequence graph and four timeline steps after a page refresh. No records were seeded for that live account.
- The Electron `BaseWindow` opened `https://discord.com/login` and `https://web.whatsapp.com/` in separate `WebContentsView` partitions inside the LIFEOS window. The captured views showed each provider's actual sign-in screen. Their observed `nodeIntegration` setting was false. The WhatsApp view required removing Electron's extra product tokens from the user agent while retaining its actual Chromium version; then the real QR sign-in screen loaded.
- The backend planner offers WhatsApp flight notification only when the exact configured chat and composer pass a real check. Preflight checks the contact and chat again. An unverified chat produces no action. Calendar dependencies and source provider IDs are persisted in the plan. API clients cannot label a manually submitted event as Gmail or Discord provenance.
- The historical 17 September read-only check returned Discord `read_access_verified`; Gmail, Calendar and Drive `not_connected`; and WhatsApp `needs_attention`. The later 18 September check above supersedes those connection states. No provider mutation was sent during either check.
- Backend tests: 106 passed. Ruff and mypy passed. Desktop navigation tests: 2 passed. Playwright: 12 passed; the optional external public-demo check was skipped because its release credentials were not supplied. Browser tests now start an isolated test backend instead of hitting the operator's live port. The new browser regression verifies that disconnecting Gmail clears earlier private inbox content and shows setup guidance. Frontend build and lint, production npm dependency audits, and the source credential-pattern scan passed.
- A Linux container image built locally as `lifeos:local-20260917` (final manifest digest `sha256:5c17e5f1207db2b727b01c8c8779e19e985e305fe69135be5fa52f0dd11618f3`). A temporary live-mode container on the preceding image returned ready and served `desktop.html`; unauthenticated session access returned 401, login succeeded, and the new workspace had zero events. The temporary container was stopped. The final rebuild changes only the frontend disconnect state and documentation. This is local image proof, not a deployed live service.
- A scan of the built image's runtime Python and browser assets found zero Google Maps/Routes API references. The public Railway health endpoint still returned `{"status":"ok","mode":"demo"}` at the time of this check.
- The preceding image also ran against a fresh isolated PostgreSQL 17 container. A real API request created one `clarification_required` event in an initially empty workspace. After restarting the LIFEOS container, a new login retrieved the same event and its persisted timeline. The isolated test containers and volume were then removed. This proves database persistence on that backend revision, not external provider execution.

## Still required for live acceptance

- Verify signed-in WhatsApp content in the packaged desktop window and confirm both provider sessions persist after restart. Signed-in Discord content was observed in the packaged executable; earlier WhatsApp QR/login screens prove the exact site renders, but do not prove current signed-in content or restart persistence.
- Google and WhatsApp read access are now verified. Their current-revision write operations and independent read-back still require acceptance.
- The visible Electron WhatsApp session is separate from the older dedicated Playwright worker profile. Approved WhatsApp sends currently use that older worker, so an action through the **same visible view** has not been implemented or verified.
- A genuine source message, Calendar update, two real notifications, independent provider read-backs, stale-plan recovery and a no-duplicate-send interruption test have not passed together on this revision.
- There is an unsigned local Windows companion installer but no signed, self-contained client. A separate HTTPS live-account backend is now deployed and persists work data. The original `lifeos-public` service is still demo mode; the new `lifeos-live` service contains the Maps removal but lacks hosted Google consent and WhatsApp automation.

Private screenshots of provider sign-in and the live fresh-account browser pass remain under `.private/`; QR codes and account content must not be published.
