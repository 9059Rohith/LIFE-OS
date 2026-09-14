# Live Calendar update undo

After a verified Calendar update, **Undo reversible changes** restores only the prior fields changed by that action. The server records a minimal before/after journal, requires the exact post-update etag and field values, sends a conditional `If-Match` restoration, and reads the result back. Unrelated edits block undo. Calendar may notify attendees, just as it does during the approved update.

Undo intent is persisted before the request. A lost response, interrupted process or unverified read-back is marked uncertain and cannot be retried automatically. The original action evidence remains; restoration has separate evidence and errors visible in the action dialog. Retention and data deletion preserve unresolved evidence.

This restores verified Calendar **updates** only. It does not recall messages or reverse arbitrary creates/deletions. No live account was mutated during implementation: conditional restore, stale versions, uncertain outcomes and startup recovery were exercised through local HTTP fixtures.
