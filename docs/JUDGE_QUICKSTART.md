# LIFE-OS Judge Quickstart

## 30-second explanation

LIFE-OS turns one real-world schedule change into a reviewed consequence graph. It gathers authorized context, proposes dependent actions across connected applications, waits for approval, executes bounded operations, reads providers back, and preserves the evidence.

## 60-second hosted path

1. Open the [live workspace](https://lifeos-live-production.up.railway.app).
2. Choose **Try interactive demo** for isolated data, or use the protected owner workspace when live provider surfaces are required.
3. Open **Overview** and inspect the consequence graph.
4. Select an action in the approval center and open its details.
5. Inspect target, arguments, risk, dependency, and verification state.

## Three-minute product path

1. Start with a supported change such as: `Flight AI-742 tomorrow moved from 11:30 AM to 6:40 AM.`
2. Let LIFE-OS gather Calendar, Gmail, Discord, WhatsApp, Drive, and work context where the provider is configured.
3. Review the generated consequence graph.
4. Open the approval dialog and confirm the exact arguments. Editing the action invalidates the approval.
5. Approve only the intended actions.
6. Watch the lifecycle move through execution and verification.
7. Open the connected application records and confirm the evidence.
8. Open **Audit Trail** to inspect approvals, attempts, receipts, and read-back results.

## What to look for

- AI interprets a supported event; it does not receive mutation tools.
- The server owns action construction and permission checks.
- High-impact actions require explicit approval.
- Idempotency and bounded retries prevent duplicate work.
- A successful request is not enough; provider read-back is required.
- Ambiguous outcomes become `uncertain` and require review.

## Offline fallback

Use the repository's authenticated demo artifact when provider credentials are unavailable: [live-site demo](demo/lifeos-authenticated-lightmode-demo-final.mp4). Its provider content is redacted and its capture is read-only.
