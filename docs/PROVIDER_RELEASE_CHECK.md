# Live provider verification

Checked 2026-09-13 against the native live runner and its PostgreSQL database using
`scripts/check_release_integrations.py`. The private machine-readable report is
`.private/release-integration-check.json`. No credentials, account content, or
encrypted token values are included in either report.

| Integration | Observed result | Remaining external requirement |
| --- | --- | --- |
| Google OAuth | Client ID/secret are present, but the actual live PostgreSQL owner grant is absent. | Complete **Connect Google** in the live app, then rerun verification. Gmail, Calendar, and Drive access cannot be verified before consent. |
| Google Maps Routes | Key is present. A real route calculation returned HTTP 403 with provider reason `API_KEY_SERVICE_BLOCKED`. | Allow the Routes API in this key's API restrictions in its Google Cloud project; rerun to identify any further provider requirements. |
| Configured travel route | Both origin and destination are absent. | Supply the actual origin and destination. The validation request used India Gate to Indira Gandhi International Airport only as synthetic public landmarks; it is not the user's itinerary. |
| Discord | Bot identity authenticated. Reading configured channel metadata returned HTTP 403. | Give this bot access to the intended channel or configure a channel it can access. Send/history permissions remain unverified because the metadata request was denied. |

The checker does not launch browsers, inspect browser profiles, send messages,
refresh OAuth tokens, or mutate provider/database records. It loads the native
runner under a non-main run name, which configures only the checker process and
does not launch the app. It reads the current dotenv file and does not edit it.

Run from the repository root:

```powershell
.venv/Scripts/python.exe scripts/check_release_integrations.py
```

Success on a read-only check does not prove mutation permissions or production
deployment readiness. The script reports only bounded read access and route
calculation; it never sends a test message.

## Local workflow regression evidence

The live context/planner now retrieves the requested calendar date in the owner's
timezone, matches explicit meeting names and flight numbers, and searches Gmail
for known calendar attendees. Missing dates and ambiguous targets still require
clarification. Complete busy-calendar context is retained so proposed meeting
times that overlap other appointments are rejected; truncated calendars and
proposed slots extending beyond the checked date also require clarification.

Gmail message IDs and thread IDs are preserved separately. The planner omits a
thread ID when the provider did not return one. Sending continues to create the
existing update message; this change does not claim that updates are replies in
the original Gmail thread.

Nine focused regressions cover unrelated meetings and dates, missing dates,
flight-number prefixes, named-meeting ambiguity, busy-slot collisions, targeted
Gmail retrieval, and message/thread identity. The initial relevance test run
failed five cases before the implementation; the thread-identity regression also
failed before its fix. The existing proposal-content fixture was moved to 17:00
because its previous 14:00 request overlapped the stored flight appointment.
No live provider requests were made during this implementation or its tests.
