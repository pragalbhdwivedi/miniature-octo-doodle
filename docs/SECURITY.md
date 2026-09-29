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
- Third-party agent skills/plugins are untrusted until provenance, permissions, dependencies and instructions are reviewed.

## Provider classifications
At minimum support:
- public/synthetic
- private
- local-only

The `local-private` model route must have no cloud fallback.

## Decision-plane rule

Deterministic security policy is authoritative.

TypeSafe Jev may be evaluated for structured classification/routing/risk decisions, but:
- Jev cannot grant access, tools, secrets, data, or production permission.
- Jev cannot override a hard deny or mandatory human approval.
- low-confidence, malformed, unavailable, or out-of-scope decisions must fail to a deterministic safe route or human review.
- provider fallback must remain inside the same or a stricter data/trust class.
- a cheaper/free provider is never automatically a safer fallback.

## Secrets
Use local `.env`, Docker secrets, or Kubernetes Secrets generated outside Git. Commit only templates/placeholders.

## Phase 1 controls

- `manage.ps1 init` generates distinct random secrets and refuses to overwrite them.
- WebUI receives only its own secret/admin login and a route-scoped gateway key.
  The key is allowed model listing and chat completions; key administration is denied.
- Provider credentials are injected only into LiteLLM; generated config uses environment references.
- Loopback port publication, internal database network, no PostgreSQL host port,
  no privileged containers, no Docker socket or host root mounts.
- Signup, Ollama, direct connections/integrations, code execution/interpreter,
  evaluation arena and community sharing are disabled by default.
- WebUI uses offline/no-model-update settings with the slim image; no local model
  download occurs. No unrestricted host shell/terminal integration is configured.
- Gateway message logging and detailed spend logs are disabled; container logs rotate.
  WebUI still persists user chats in its local volume. This is not a no-retention system.
- Never publish `.env`, raw `docker inspect`, resolved Compose configuration or
  unredacted logs. Test tools report statuses without printing credentials.

Phase 2 deterministic policy enforces a persistent conservative admission budget,
four-request concurrency limit, approved provider/model attempts and one bounded
fallback. Private and local-only labels deny before execution; `local-private`
is not advertised. Actual tool definitions and client routing overrides are denied.
Empty WebUI tool lists are stripped; they grant no tool permission.
WebUI defaults to legacy function-calling mode with no configured tools, avoiding
automatic native builtin-tool injection in ordinary chats.

Classification is declared, not DLP: unlabelled WebUI text is treated as public.
Do not send sensitive material through cloud chats. Administrator key metadata
can enforce stricter classification, providers and mandatory approval. Jev has no
runtime authority or credentials. See [policy boundaries](PHASE2_POLICY.md).
