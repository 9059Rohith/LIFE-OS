# LIFE-OS Submission Risks

## High priority

### Historical credential exposure (resolved)

A pre-scrub public commit (`972f027`) placed a credential-like value in the README URL. The public `main` history has been rewritten and force-updated so that value is no longer reachable from the submission branch. Railway deployment `5378760c-07f4-4d71-b337-4d5b4bfb746b` was restarted with a replacement credential: the replacement login and authenticated session returned 200, while the historical credential returned 401. The replacement remains only in the ignored local `.private` directory. Do not publish it in README, judge guides, issues, or video descriptions.

### Hosted revision drift (verified for current release)

The public Railway service and the current GitHub source are separate release artifacts. For the current release, checkout commit `81ec67f` was uploaded to Railway and deployment `5378760c-07f4-4d71-b337-4d5b4bfb746b` passed `/health`, `/ready`, homepage, login, and authenticated session checks. Re-run those checks after any future deployment.

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
