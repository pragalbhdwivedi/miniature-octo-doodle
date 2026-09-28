# Security

This repository is public.

## Never commit
- API keys
- credentials
- passwords
- tokens
- private keys
- production kubeconfigs
- institutional/student/employee records
- raw database exports
- model weights
- runtime backups

## Trust boundaries
- Browser UI must not receive arbitrary host shell access.
- Web UI must not mount `/var/run/docker.sock` by default.
- Coding agents must use isolated workspaces.
- Production credentials must not be exposed to autonomous agents.
- Optional free-provider routes must not be used automatically for sensitive workloads.

## Provider classifications
At minimum support:
- public/synthetic
- private
- local-only

The `local-private` model route must have no cloud fallback.

## Secrets
Use local `.env`, Docker secrets, or Kubernetes Secrets generated outside Git. Commit only templates/placeholders.
