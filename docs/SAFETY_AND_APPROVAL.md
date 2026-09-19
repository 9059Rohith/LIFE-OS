# LIFE-OS Safety and Approval

LIFE-OS follows a server-decides, human-approves model.

## Boundary

```text
Untrusted user/provider content
          |
          v
Strict extraction and validation
          |
          v
Server-owned consequence plan
          |
          v
Risk policy and allowlisted arguments
          |
          v
Human approval for consequential writes
          |
          v
Bounded execution and provider read-back
          |
          v
Evidence, audit, or explicit uncertainty
```

## Approval rules

- Read and context actions may run without mutation approval.
- Calendar changes, notifications, and bridge sends are approval-bound.
- Approval includes the action identity, event version, exact argument digest, and expiry.
- Editing action arguments invalidates an existing approval.
- A stale, missing, expired, or mismatched approval is rejected.
- A failed or uncertain delivery is not silently retried as a new success.

## Failure behavior

Provider failures return controlled errors and retain technical details in server-side diagnostics rather than exposing provider response bodies. Crashes during execution reconcile to an explicit uncertain state. The user can inspect the provider and decide whether to create a new reviewed plan.

## Least privilege

Provider operations are allowlisted by application and operation. Recipients, channels, Calendar events, and desktop bridge jobs are checked against configured owner-scoped context. Provider content cannot grant itself new tools or permissions.
