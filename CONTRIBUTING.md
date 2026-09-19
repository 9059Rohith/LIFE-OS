# Contributing to LIFEOS

LIFEOS is a safety-sensitive automation project. Changes should preserve the approval boundary, provider read-back evidence and honest release-status documentation.

## Local Checks

Run the focused checks that match your change. Before a release candidate, run:

```powershell
python -m ruff check backend tests scripts
python -m mypy --strict backend/lifeos/policy.py backend/lifeos/schemas.py backend/lifeos/config.py
python -m pytest -q
python scripts/scan_secrets.py
cd frontend
npm run lint
npm run typecheck
npm run build
```

## Engineering Rules

- Do not let model output invoke arbitrary tools.
- Do not bypass approval hashes or version checks.
- Do not retry uncertain external sends automatically.
- Do not expose provider exception bodies to users.
- Do not claim live provider success from fixture tests.
- Keep `.env`, private browser profiles, token exports and database backups out of Git.

## Documentation

When behavior changes, update the README and the relevant file in `docs/`. Claims must describe verified behavior, not intended behavior.

