# LIFE-OS Submission Risks

## High priority

### Historical credential exposure

A pre-scrub public commit (`972f027`) placed a credential-like value in the README URL. The public `main` history has now been rewritten and force-updated so that value is no longer reachable from the submission branch. A replacement credential has been submitted to Railway and kept only in the ignored local `.private` directory; the active deployment still needs to restart and be tested with it. Do not publish replacement credentials in README, judge guides, issues, or video descriptions.

### Hosted revision drift

The public Railway service and the current GitHub source are separate release artifacts. A successful local build does not prove the hosted service is running that commit. Check `/health`, `/ready`, authenticated UI behavior, and the deployment identifier before claiming parity.

### WhatsApp desktop dependency

WhatsApp reads and approved sends depend on the signed-in Windows companion. The hosted web service alone cannot establish a fresh WhatsApp delivery. The demo identifies this boundary rather than hiding it.

### Primary-owner deployment boundary

The live provider deployment is designed for one owner and one backend process. It is not a horizontally scaled multi-tenant SaaS. Work-record account isolation must not be described as provider-account isolation.

## Medium priority

### ScreenOps privacy comparison

ScreenOps demonstrates browser-local screen/audio inference and a JSON-only backend boundary. LIFE-OS currently performs bounded server-side extraction and does not claim equivalent local sensing. See [PRIVACY_BOUNDARY.md](PRIVACY_BOUNDARY.md).

### External demo hosting

The authenticated demo is stored in the repository. A submission platform may require a streaming URL. Upload the verified artifact only if the rules require it; never invent a video URL.

### GitHub Actions scope

The local CI workflow was validated but could not be published with the current OAuth token because GitHub requires the `workflow` scope for workflow-file updates. The public repository does not claim that workflow is active.

## Low priority

- The Windows companion installer is unsigned.
- The product supports a narrow family of schedule-change consequences rather than arbitrary office automation.
- Hosted backup scheduling and distributed worker coordination are not claimed.
