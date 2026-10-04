# CI and source delivery

The `validate` GitHub Actions workflow runs on pull requests and pushes. Its
`repository-safety` job checks tracked-secret exclusions, YAML, the core safety
contract, Python regressions, PowerShell configuration checks and Compose syntax.
The job has read-only repository permission and no production credentials.

On a push to `main`, a successful validation job unlocks `source-bundle`. It
packages that exact commit with `git archive`, checks the resulting SHA-256 and
publishes the archive and checksum as a GitHub Actions artifact for 30 days. A
failed or cancelled validation cannot publish a bundle. Pull requests and other
branches cannot publish one. The archive contains committed source only; local
runtime files, credentials, backups and ignored files stay out of it.

This is continuous delivery of a reviewable source candidate, not an automatic
production deployment. No runner receives SSH access, a Docker socket, provider
keys or deployment credentials. GitHub Actions does not modify the live Compose
VM, its data volumes, current allowance ledger or the separate Kubernetes test
environment. Merging, promotion and live acceptance remain operator actions.

For an operator promotion, identify the successful `validate` run for the desired
`main` commit, download its `gatewayai-source-<full-commit-SHA>` artifact, and
verify the archive before staging it:

```sh
sha256sum --check gatewayai-source-<full-commit-SHA>.tar.gz.sha256
tar -tzf gatewayai-source-<full-commit-SHA>.tar.gz
```

Confirm the full commit SHA against the intended merged commit. Stage only in a
new, private directory; do not unpack over `/opt/gatewayai/source` or any live
runtime directory. Review the change, take and verify the appropriate current
live backup, then follow the [Linux core operations](LINUX_CORE.md) and relevant
component runbook for a controlled update and post-update health checks. The
migrated live runtime has retained source and ledger coupling, so this artifact
alone does not authorize a generic `docker compose up` or a blind source swap.
The checksum detects an altered or incomplete download; identify the trusted
Actions run and commit separately.
Record the promoted commit, backup, checks and rollback path in the operational
log. If those steps cannot be established for a change, leave the artifact
unpromoted.

GitHub branch protection and deployment environment approval settings are
repository administration controls; this workflow does not configure or claim
them. Require the `repository-safety` check in branch protection before treating
CI as a merge gate. A successful Actions run proves the named checks on a clean
runner, not provider behavior, browser acceptance or production recovery.
