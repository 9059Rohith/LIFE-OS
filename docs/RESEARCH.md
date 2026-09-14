# Research and architecture decisions

Official sources were retrieved during implementation on 13 September 2026. These references inform the design; they do not demonstrate that live account integration tests passed.

| Area | Source | Decision in LIFEOS |
| --- | --- | --- |
| Model output | [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | Narrow extraction through Responses JSON Schema with strict Pydantic validation; models receive no mutation tools. |
| Orchestration | [Agents SDK agents](https://openai.github.io/openai-agents-python/agents/) and [guardrails](https://openai.github.io/openai-agents-python/guardrails/) | Explicit durable workflow and deterministic policy own approvals and mutations. Direct Responses is sufficient for the bounded extraction step; SDK handoffs would add complexity without changing authorization. |
| Human control | [Agents SDK human-in-the-loop](https://github.com/openai/openai-agents-python/blob/main/docs/human_in_the_loop.md) | Approvals bind current plan version, arguments, action identity and expiry. External app content cannot approve actions. |
| Speech | [OpenAI transcription](https://developers.openai.com/api/docs/guides/speech-to-text), [speech generation](https://developers.openai.com/api/docs/guides/text-to-speech), [voice pipeline](https://openai.github.io/openai-agents-python/voice/pipeline/) | Record bounded browser audio, transcribe server-side, review transcript, run the same workflow, synthesize summary server-side. Explicit interruption stops playback. Voice approval is reviewed against a captured plan version. |
| Realtime | [Agents SDK realtime guide](https://github.com/openai/openai-agents-python/blob/main/docs/realtime/guide.md) | Realtime streaming is a future extension. Current chained speech does not claim streaming audio or VAD. No client gets a long-lived provider key. |
| Browser automation | [Playwright best practices](https://playwright.dev/docs/best-practices), [locators](https://playwright.dev/docs/locators), [authentication](https://playwright.dev/docs/auth) | Role/text locators, bounded waits, isolated contexts, traces on failed E2E tests, protected authenticated WhatsApp profile. No CAPTCHA or authentication bypass. |
| Agency | [OWASP excessive agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) | Provider-specific allowlists, server-bound recipients, preflight conditions, least privilege and explicit approval. Regex injection checks are only an early rejection layer, not the security boundary. |

Google OAuth, conditional Calendar writes, MIME email, Drive exports, Discord nonce/mention control and Maps Routes sources are linked near implementation decisions in [INTEGRATIONS.md](INTEGRATIONS.md).

## Deployment tradeoffs

One application process with a persistent relational store is intentionally the supported deployment. Concurrent API requests can read execution progress, but mutation locks and rate limits are process-local. Scaling replicas requires distributed coordination before production use. PostgreSQL persistence and a versioned schema are exercised in the local Docker deployment; remote hosting, production TLS/OAuth consent and live credentials still need an operator environment.

The database stores owner-scoped typed-input workflow documents rather than one table per conceptual entity from the brief. This preserves complete plan/approval/evidence snapshots but trades normalized analytics and per-field SQL constraints for simpler transactions. The deterministic policy and API schemas have strict type checks; the orchestration/document layer remains dynamically typed Python.
