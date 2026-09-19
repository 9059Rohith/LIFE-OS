# LIFE-OS Integration Matrix

This matrix describes the actual integration boundary in the current release. `Read` means context can be gathered. `Write` means an approved provider operation exists. `Verify` means the system reads provider state back before resolving the action.

| Integration | Read | Approved write | Read-back verification | Hosted/demo boundary |
| --- | --- | --- | --- | --- |
| Google Calendar | Yes | Supported event update/reschedule actions | Yes | Requires configured OAuth and an owner account. |
| Gmail | Yes | Supported notification/draft action families | Provider-specific | Requires configured OAuth; scope is intentionally bounded. |
| Google Drive | Yes | No general Drive write | Context evidence | Context surface is read-only in the current product. |
| Discord | Yes | Allowlisted channel notifications | Yes | Requires configured bot/destination permissions. |
| WhatsApp | Desktop bridge | Approved bridge send job | Exact-body read-back | Requires the signed-in Windows Electron companion. |
| Work records | Yes | Explicit owner-scoped record operations | Stored record state | Available in the workspace database. |

## Safety rule

Provider content is context, not authority. The server constructs the supported action, checks the provider boundary, applies the approval policy, and records the result or an explicit uncertain state.

## Submission note

An unavailable provider is shown as unavailable. The product does not present a disconnected integration as a completed live action.
