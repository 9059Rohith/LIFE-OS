# LIFE-OS Privacy Boundary

LIFE-OS does not treat AI output or provider content as permission to act.

## Data flow

```text
User input or authorized provider context
                |
                v
      bounded extraction boundary
                |
                v
     typed event and confidence value
                |
                v
      server-owned planner and policy
                |
                v
       approval-bound provider action
                |
                v
        independent read-back evidence
```

The current web workflow sends bounded natural-language extraction requests to the configured OpenAI-compatible provider only when deterministic parsing cannot confidently identify a supported schedule change. The model receives no provider mutation tools. The server validates the returned schema, constructs the action arguments, applies the permission policy, and requires approval for consequential writes.

Provider records are context, not authority. A message, document, calendar description, or browser record cannot grant a recipient, tool, or permission that the server did not already allow.

## What is not claimed

- LIFE-OS does not currently claim ScreenOps-style browser-local screen inference.
- LIFE-OS does not claim that raw provider content never leaves the deployment boundary.
- LIFE-OS does not claim multi-tenant isolation for live provider accounts.
- LIFE-OS does not expose arbitrary model-generated tools.

The desktop companion isolates Discord and WhatsApp web sessions. The service remains primary-owner and single-worker focused until distributed ownership, shared rate limits, and provider-session isolation are implemented and verified.

## Controls

- Strict Pydantic schemas reject unexpected fields.
- Prompt-injection-like instruction text is rejected before planning.
- Provider operations are allowlisted by application and operation.
- Exact action arguments and plan versions are approval-bound.
- Provider writes use idempotency keys and bounded retries.
- A result is not resolved until independent provider read-back supports it.
- Uncertain delivery becomes a review state, not an optimistic success.
- Privacy export and deletion controls do not export provider secrets.
