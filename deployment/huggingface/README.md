# Free hosting profile

Current interactive demo: https://ajeya95-llmfleet-sre.hf.space/lifeos/.
The original live workspace remains at https://lifeos-live-production.up.railway.app/.

The active free deployment shares one CPU slot with Skylark to meet the account's
three-active-slot limit. Its separate Python environment, proxy and captured
application source are inspectable at
https://huggingface.co/spaces/Ajeya95/llmfleet-sre/tree/main/lifeos_release.
The frontend supports a deployment base path through LIFEOS_BASE_PATH. Its API,
server-sent events and voice requests use that same base path.

The Dockerfile and launcher here describe the optional standalone demo profile.
All credentials must be configured as hosting secrets. The demo has no personal
provider credentials and resets sample sessions on a host restart or idle sleep.
