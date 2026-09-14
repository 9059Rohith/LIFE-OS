# Security model

LIFEOS treats imported messages, documents, webpages and model output as untrusted data. They may describe an event; they cannot grant authorization, replace server policy or choose arbitrary executable tools. The backend validates typed inputs and constructs supported operations. Narrow policies reduce injection impact but keyword checks are not a complete semantic injection defense.

## Trust boundaries

- Browser → backend: session authentication, owner-scoped records, CSRF token and origin checks for commands. Demo sessions are convenient local identities, not a public authentication system.
- Backend → model: event content may be sensitive and leaves the host when live AI is enabled. Only the configured server key is used. Review provider data terms for your deployment.
- Backend → providers: explicit configuration and OAuth credentials. API return data remains untrusted. Approval is enforced by the application, not the provider or model.
- Approval → execution: approval records bind action arguments and event version. Changed arguments require reapproval. A write response alone is insufficient; the action must be read back.
- Browser automation → WhatsApp: an authenticated browser profile grants substantial account access. Use a dedicated test account/profile and restrict filesystem access. Never reuse a personal browsing profile or expose a remote debugging port.

## Credentials and sessions

Keep `.env`, database backups, browser profiles and tokens out of Git and images. `LIFEOS_ENCRYPTION_KEY` is a Fernet key used to encrypt provider credentials; store it separately from database backups. Losing it makes encrypted credentials unreadable. Encrypting the database tokens does not encrypt all event data. Use disk encryption and restricted database access as appropriate.

Live mode uses a configured single-owner password. Set a unique random password of at least 16 characters, HTTPS allowed origins, production environment and encryption key. Production cookies require HTTPS. Terminate TLS at a trusted ingress and restrict direct backend access. Never deploy the convenient unauthenticated demo mode to a public network. Browser sessions and CSRF tokens are not API integration keys.

## Execution and recovery

Approval never authorizes arbitrary recipients or future payload changes. Inspect targets and content before approving. Execution state and evidence persist. The application limits retries and tracks idempotency, but third-party APIs differ in their deduplication guarantees. If a provider request times out after a remote write, inspect the remote application before retrying. A crash between a provider write and local persistence remains a distributed-systems hazard.

Run one backend worker until a distributed lease/queue design is implemented and tested. Cancelling prevents subsequent work; it cannot recall a completed request. Compensation is limited to operations for which a safe inverse exists.

## Audit, retention and logs

Audit entries form a tamper-evident chain. A database administrator who rewrites the whole chain can defeat this protection; use external append-only storage or periodic signed anchors for stronger assurance. Logs, evidence, event text and local application records may contain personal data. Define retention, export and deletion requirements before using sensitive real accounts. A retention setting alone is not evidence that a background deletion job is running.

## Release checks

Run tests, lint, frontend typechecking, dependency audits and `python scripts/scan_secrets.py`. The local scanner checks common credential patterns, reports only locations and skips local `.env` files; it is not a full entropy/history scanner. Review tracked files and enable repository secret scanning before publication. Dependency audits require advisory network access and reflect the advisory database at execution time.

Live OAuth consent, actual provider writes/read-backs, production HTTPS cookies, PostgreSQL recovery, WhatsApp account behavior and physical microphone capture require environment-specific checks. Unit fixtures and browser tests of local demo records cannot certify them. No penetration test or production security certification is implied.
