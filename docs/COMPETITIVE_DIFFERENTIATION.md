# Competitive Differentiation

This is a factual comparison with [ScreenOps-Codex](https://github.com/9059Rohith/screenops-codex), not an attempt to force a predetermined winner.

| Dimension | LIFE-OS | ScreenOps-Codex |
| --- | --- | --- |
| Core problem | Consequences of a real-world schedule change across applications. | Commitments detected from live browser screen/audio context. |
| Input | Text, upload, voice, and connected application context. | Browser screen capture, microphone/tab audio, local OCR and model inference. |
| AI boundary | Structured extraction; server constructs and validates actions. | Browser-local models emit structured intent JSON to a backend agent. |
| Agent architecture | Durable deterministic workflow, risk policy, allowlisted provider operations. | LangGraph route/enrich/plan/risk/approve/execute/verify flow with MCP tools. |
| Automation breadth | Calendar, Gmail, Discord, WhatsApp bridge, Drive context, and work records. | Gmail draft, Calendar reminder, and Sheets commitment log. |
| Approval | Exact action arguments and plan version are hashed and expiry-bound. | Risk-based approval, with Gmail draft approval in the documented flow. |
| Verification | Independent provider read-back, uncertain state, compensation path, audit evidence. | Poll-back verification for the documented Google actions and SQLite audit log. |
| Privacy | Bounded server extraction; no arbitrary model tools; provider secrets encrypted when configured. | Stronger browser-local raw screen/audio boundary. |
| Evidence | 141 backend tests, 15 browser passes, 8 desktop passes, 6/6 offline extraction evals, live demo. | 16/16 extraction evals, 15/15 planning evals, local-model and network-boundary demo. |

## LIFE-OS's defensible position

LIFE-OS is strongest when the problem is not merely noticing one commitment, but safely coordinating the consequences of a change across multiple systems and proving what happened afterward. Its differentiator is consequence-aware, approval-bound, read-back-verified execution.

## ScreenOps's defensible position

ScreenOps is strongest when privacy-preserving browser-local multimodal sensing is the central requirement. LIFE-OS does not claim to replace that architecture today.

## Submission framing

Present LIFE-OS as a consequence-execution system, not as a generic chatbot and not as a browser-local inference clone. Judges should see the graph, approval boundary, cross-provider execution, read-back proof, and audit trail in that order.
