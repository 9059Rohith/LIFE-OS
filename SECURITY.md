# Security Policy

Security documentation for LIFEOS lives in [docs/SECURITY.md](docs/SECURITY.md). This top-level file exists so GitHub and reviewers can find the security model quickly.

## Supported Versions

The `main` branch is the supported development line. Release-specific caveats are documented in [docs/RELEASE_STATUS.md](docs/RELEASE_STATUS.md).

## Reporting Vulnerabilities

Do not open public issues with secrets, tokens, private account data, OAuth grants, database files or browser profiles. Report privately to the repository owner with:

- affected commit or deployment,
- reproduction steps,
- expected impact,
- whether any third-party account was touched.

## Secret Handling

Never commit `.env`, database backups, OAuth tokens, browser profiles, exported provider data or desktop bridge session files. Run:

```powershell
python scripts/scan_secrets.py
```

before publishing changes.

## Boundaries

LIFEOS enforces session authentication, CSRF, origin checks, approval-bound execution, provider read-back, encrypted provider tokens when configured, and a tamper-evident audit chain. It is not a penetration-tested multi-tenant SaaS and should run as a single-worker primary-owner deployment until distributed execution is implemented and verified.

