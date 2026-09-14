# Source monitoring

Monitoring is disabled by default. The installation owner can opt in using
`POST /api/ingestion` with `enabled`, `sources` (`gmail`, `discord`), and
`interval_seconds` (60–86400; default 300). `GET /api/ingestion` reports settings,
last check, recent results, a safe error summary, and background worker status.
All writes require the authenticated session and CSRF token. `POST
/api/ingestion/scan` checks immediately when enabled, at most once per minute;
overlapping scans return 429. Disabling monitoring cancels and awaits an active
scan. Shutdown also cancels outstanding scans before provider clients close.

Live mode reads only the installation owner's connected Gmail and configured
Discord bot channel. Each scan reads at most five recent Gmail messages matching
flight/meeting change terms from the last two days, and twenty latest Discord
messages, excluding bots. It creates at most three new plans. This is a bounded
recent-message window, not complete historical ingestion: high-volume sources
can move messages out of the window before they are seen.

Live notices must contain a supported flight or meeting change, a new time, and
an explicit `YYYY-MM-DD` date. Relative dates in account messages are skipped
because “tomorrow” could refer to an older message date. Demo mode reads only
owner-scoped local application records and permits the seeded relative dates;
it makes no account requests. The background worker resumes a saved live-owner
opt-in on restart. Demo owners must opt in during the current process.

External text passes through the ordinary engine's extraction, injection checks,
planning, and approval requirements. Monitoring never approves or executes an
action. Provider message IDs are durably reserved before planning and retained
as deduplication checkpoints across restarts. Skipped messages are also recorded.
An interruption after reservation can leave a record marked `reserved`, or
`manual_review_required` after a caught planning error. It is never automatically
retried because a plan may already have been saved. Inspect existing plans and
the exported ingestion records before manually creating a replacement. Source
text and provider tokens are omitted from monitoring error summaries.
