# LIFE-OS Evaluation Suite

The evaluation suite is a small, deterministic regression harness for the part of LIFE-OS where AI-assisted interpretation enters the workflow.

It checks that supported scheduling changes are extracted, ambiguous requests fail closed, and instruction-like provider content cannot become tool authority.

Run it from the repository root:

```powershell
python scripts/run_lifeos_evals.py
```

The suite does not call external providers or model APIs. It is safe to run offline and is intended to complement the backend, provider, security, and browser tests.
