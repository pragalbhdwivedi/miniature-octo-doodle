# Operations

## Current management entry point
`scripts/manage.ps1`

Supported core commands:
- `status`
- `init` (generate local secrets once; never overwrite)
- `components`
- `disk`
- `preflight`
- `configure` (render config only; does not reload services)
- `start`
- `start -Stage gateway` (PostgreSQL/LiteLLM only)
- `test` (container and host checks; no provider inference)
- `test -ContainerOnly` (internal diagnosis; no browser readiness claim)
- `stop`

`stop` preserves containers and volumes. `start` waits for health and performs
disk checks before pulling only the pinned core images. Preserve the database
password, LiteLLM salt and WebUI secret across restarts.

`scripts/test-config.ps1` runs isolated configuration/storage regressions.
`scripts/policy-status.ps1` reports the UTC allowance/debit and secret-free attempt
counts. `python -m unittest discover -s tests -v` tests policy/Jev contracts and
atomic budget races. `scripts/test-policy-runtime.ps1` tests the pinned gateway
against synthetic loopback providers, including outage/quota, streaming and
concurrency. It never calls a live provider. See [policy operations](PHASE2_POLICY.md).
Use `-Matrix` to test both-provider, each single-provider and no-provider synthetic
configurations independently of installed credentials. `policy-status.ps1` must
report deterministic mode and Jev disabled. Jev activation is deliberately rejected.
`python scripts/validate-repository.py` uses `requirements-ci.txt` to validate
YAML and the core security contract. CI also validates Compose syntax; CI does
not establish Windows deployment or cloud provider readiness.

The WebUI admin password is local in `.env`. Startup does not reset existing
accounts. If the password is changed in the application, the sign-in smoke test
needs matching local credentials.

This project deploys no Kubernetes resources. Do not disrupt unrelated host
workloads to repair this stack without assessing their impact.

Install/uninstall operations are intentionally deferred until dependency and disk-safety checks are implemented.

## Operational rules
- check disk before optional installs
- keep secrets local
- record real failures in TROUBLESHOOTING
- update BUILD_STATUS after tested milestones
- do not run Docker and Kubernetes copies of the full stack simultaneously unless explicitly required
