# LIFEOS exact app window plan — 17 September 2026

## Current truth

LIFEOS has a deployed, password-protected demo at `https://lifeos-public-production.up.railway.app`. That service runs demo providers. The live account workspace is local. Its Discord and WhatsApp panels display real authorized data through LIFEOS components, but they are not the actual signed-in Discord or WhatsApp interfaces. The local source now removes Google Maps and the Routes API. These changes are not yet deployed.

## Product decision

Make the **actual signed-in Discord and WhatsApp sites** the center of a Windows desktop application window. Keep LIFEOS as a narrow native shell around them: connected-app switcher on the left, the real site in the center, and a collapsible consequence/approval dock on the right. The site gets most of the window. Gmail, Calendar and Drive can continue using the existing API-backed panels until their own exact-window experience is validated.

A normal hosted web page cannot promise to frame another provider's signed-in site. The desktop shell should use Electron `WebContentsView` to render each approved HTTPS origin as its own top-level web content inside one `BaseWindow`, rather than an HTML iframe. Electron documents this composition at <https://www.electronjs.org/docs/latest/api/web-contents-view>. The project must not weaken provider framing headers or scrape browser credentials.

## Implementation sequence

1. **Feasibility gate.** Build a small Windows shell with separate persistent, local sessions for `discord.com` and `web.whatsapp.com`. Sign in manually and verify that both sites load, navigate, reconnect and display the user's actual content inside the LIFEOS window. Verify behavior after restart, screen resize and network loss. If either provider refuses this runtime, record the failure before promising exact embedded UI.
2. **Application layout.** Replace the small cloned Discord/WhatsApp cards in the desktop view with a single full-size provider viewport. Keep a clear provider switcher, connection state, loading/error state and a compact LIFEOS dock. Opening a provider must show its actual page, not a screenshot. On the hosted demo, retain the current API-backed views and label them as LIFEOS views.
3. **Ripple interaction.** An event enters as a message, voice command or instruction. LIFEOS builds the consequence graph and previews each affected app. The dock shows the selected event's actions in order: planned, awaiting approval, executing, verifying, verified or blocked. An action highlights its provider; clicking it focuses that actual provider view. Show motion for real state changes and an animated path between steps. Respect reduced-motion settings. The current web workspace already polls event state every five seconds, animates changed action cards and lets a click focus its provider panel; desktop work will use the same event model.
4. **Approval and verification.** Keep the existing server-side allowlists, per-action approval, execution journal and read-back evidence. A manual click inside Discord or WhatsApp is a user action and must never be recorded as a LIFEOS-verified automation. After an approved LIFEOS send, refresh the provider view and reconcile the result before displaying success. An uncertain result stays uncertain; no automatic resend.
5. **Security and packaging.** Give remote provider pages no Node.js access, no privileged preload API and no LIFEOS session token. Use separate provider session partitions, context isolation, sandboxing, HTTPS-only allowlists, bounded permissions and blocked untrusted navigation/popups. Package and sign a Windows installer. Electron's remote-content checklist is the minimum baseline: <https://www.electronjs.org/docs/latest/tutorial/security>.
6. **Deployment and acceptance.** Deploy the changed server/web source separately from the Windows client. Test the exact production build with signed-in Discord and WhatsApp accounts, a real approved multi-app event, independent read-back, restart persistence, keyboard and screen-reader access, reduced motion, narrow and wide windows, and a recovery path when a provider changes its UI. Record screenshots privately because they contain personal messages. Publish only after these checks pass.

## Quality bar

- Actual provider site visible in the center, with no fake chat history or provider controls.
- App switching and LIFEOS dock remain responsive while a provider page loads; a failure in one view does not blank the others.
- Every ripple animation is tied to a real event or action status. No decorative activity suggests work is happening when it is not.
- Clear distinction between a proposed action, a human-approved action, an API/browser attempt and verified provider evidence.
- Strong typography, consistent spacing, accessible contrast, visible keyboard focus and no horizontal overflow at supported window sizes.
- Measured desktop startup, app switching, memory use and CPU use on the target Windows machine; optimize regressions before release.

## Release definition

“100% completed and deployed” requires both the live backend and the Windows client to be released, the real provider pages to pass the feasibility and account tests above, and a genuine approved multi-provider workflow to complete with read-back on the release build. The current public demo does not meet that definition.
