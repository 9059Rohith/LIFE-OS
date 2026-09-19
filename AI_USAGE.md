# LIFEOS AI Usage

LIFEOS uses AI as a constrained planning input, not as an autonomous permission system.

## Where AI Is Used

- `backend/lifeos/ai.py` calls OpenAI-compatible APIs for structured event extraction when live deterministic parsing cannot confidently identify the change.
- Voice transcription and speech synthesis are available when `LIFEOS_OPENAI_API_KEY` is configured.
- The workflow engine uses AI output only to recover a supported event type, date and new time. It then re-enters deterministic parsing and policy.

## Models

`LIFEOS_OPENAI_MODEL` defaults to `gpt-4.1-mini` in `.env.example`. Operators may choose another Responses model that supports structured JSON output. Voice endpoints use the configured OpenAI key for transcription and speech synthesis.

## Agent Boundary

LIFEOS does not expose a general tool-using agent that can invent actions. The backend constructs supported actions from validated context:

- Calendar updates.
- Gmail notifications.
- Discord notifications.
- WhatsApp notifications through the connected desktop bridge.
- Work-record operations through explicit API routes.

The server decides which actions exist, which arguments may change, which targets are authorized, and which actions require approval.

## Validation and Oversight

- Pydantic schemas reject unexpected request fields.
- Provider context is treated as untrusted input.
- Approval binds the action argument hash and plan version.
- Edited actions invalidate previous approvals.
- Provider preflight checks run before live writes.
- Provider writes receive idempotency keys.
- Read-back verification is required before an action is considered verified.
- Uncertain deliveries block automatic retry until a human reviews provider state.

## Failure Handling

Malformed AI output, provider errors, timeouts and unavailable voice services return controlled API errors. The UI shows human-readable messages. Provider exception bodies are not exposed because they may contain private data.

## Limitations

LIFEOS is currently optimized for a narrow class of schedule-change and consequence workflows. It should not be presented as a general autonomous office agent or a broad no-code automation builder. The current release status remains the source of truth for live provider acceptance.

