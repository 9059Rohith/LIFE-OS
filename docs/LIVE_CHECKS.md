# Live configuration follow-up

The operator supplied credentials after the initial build. Credentials are kept in the ignored `.env`; status reports in `.private` do not contain keys or account content.

## Verified

- Live application and PostgreSQL are healthy at http://localhost:8010. Browser login and the Integrations screen passed. Cookie/CSRF and Google consent URL, callback and PKCE checks passed; consent itself remains pending.
- OpenAI authentication succeeds and the configured models are listed.
- Actual metered OpenAI speech generation, transcription of synthetic audio, and structured event extraction all passed. This does not verify a physical microphone.
- Fixed an invalid Fernet key after confirming there were zero stored encrypted-token rows; changed only the encryption-key entry.
- Maps is optional. Flight plans omit route/pickup-time actions without route data and display the resulting limitations. Meeting workflows need no Maps key.
- 52 Python tests passed after adding a missing-Maps regression and isolating tests from the operator's real credentials. Ruff, strict policy/schema/config typing, frontend build and lint passed.

## Still requires the operator

1. **Google:** sign into the local live app with the configured workspace password, open Integrations and choose **Connect Google**. Complete Google consent. OAuth client credentials alone do not grant Gmail/Calendar/Drive access. Registered callback: `http://localhost:8010/api/integrations/google/callback`.
2. **Discord:** the bot authenticates but has no server memberships; the configured channel returns 403. Invite it to the intended server and grant View Channel, Read Message History and Send Messages in the configured text channel. Confirm the configured value is the channel ID.
3. **WhatsApp:** QR enrollment and reopening the saved session succeeded in a visible browser. The local desktop API now enables that profile; see [LOCAL_LIVE.md](LOCAL_LIVE.md). The exact configured contact returned no matching search result, so recipient selection and message delivery remain unverified. Configure the exact intended chat display name. No messages were sent. Headless Chromium showed an unsupported-browser screen, so the verified session requires a visible desktop browser.

No live emails, Discord messages, WhatsApp messages or Calendar modifications were sent during these checks. Existing demo data remains in its separate deployment. These outstanding grants prevent an honest claim that every live integration is complete.

Repeat status checks: `python scripts/check_integrations.py`. The optional `python scripts/check_voice.py` performs three small metered OpenAI requests using synthetic content. Both avoid printing secrets.
