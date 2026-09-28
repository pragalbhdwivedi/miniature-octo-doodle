# Operations

## Current management entry point
`scripts/manage.ps1`

Supported bootstrap commands:
- `status`
- `components`
- `disk`
- `preflight`
- `start`
- `stop`

Install/uninstall operations are intentionally deferred until dependency and disk-safety checks are implemented.

## Operational rules
- check disk before optional installs
- keep secrets local
- record real failures in TROUBLESHOOTING
- update BUILD_STATUS after tested milestones
- do not run Docker and Kubernetes copies of the full stack simultaneously unless explicitly required
