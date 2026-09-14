# Connected app screens

This initial tabbed layout was replaced by the single-page design in [Unified connected workspace](UNIFIED_CONNECTED_WORKSPACE.md). The security and data-scope decisions below still apply.

LIFEOS will show provider-backed screens inside its existing Applications page in live mode. Gmail and Discord are the first-class message views. Calendar, Drive, the configured WhatsApp chat, and Maps status share the same navigation so the user can inspect their connected world without switching sites.

Each screen loads a bounded, read-only slice through authenticated LIFEOS endpoints. The server scopes Google requests to the signed-in owner's grant, Discord to the configured channel, and WhatsApp to the exact configured chat. It returns normalized plain text and metadata only; no raw HTML, tokens, or browser profiles are exposed. A provider failure stays visible in that screen. Sending and calendar mutations remain in the existing plan/approval/execution flow.

The UI uses the existing layout, typography, and panel system. The Applications navigation label becomes Connected apps in live mode and stays Demo applications in demo mode. A provider switcher controls one active screen at a time; content is fetched only for the active screen. It has loading, empty, error, and mobile states.

Verification: isolated provider-response tests for data shaping and owner/target scoping, frontend build/lint, and an authenticated browser pass against the live local app. Real account content must not appear in logs or screenshots shared outside the private workspace.
