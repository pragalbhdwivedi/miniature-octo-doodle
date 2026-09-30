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

## Recovery data

Cold backups contain secrets and potentially retained chats. Keep them in the
ACL-restricted physical recovery directory outside Git/OneDrive; never attach
archives or resolved Compose to PRs. SHA-256 checks detect corruption, not a
malicious replacement. Restore only trusted bundles. Local ACLs are not encryption
or protection from administrators; off-machine copies need protected storage.
Recovery drills omit cloud keys, use internal networks, zero allowance and no
automatic restart. Reconcile post-backup monthly debits before any real cutover;
restoring an old ledger must not reset spend capacity.

## Kubernetes validation boundary

The local k3d instance uses fresh per-service secrets, a separate private kubeconfig,
K3s secrets encryption, loopback publication, no pod API token and default-deny
networking. Only DNS, Ingress-to-UI, UI-to-gateway and gateway-to-database are allowed.
Cloud keys are blank and the allowance is zero. No live Compose credentials or
records are copied. A local/cluster administrator can still access secrets.

k3d's infrastructure node requires Docker privilege; core application pods have no
privileged mode, host path or Docker socket. This does not grant an installed coding
agent host access: no agent is installed. Kubeconfig and credentials stay outside
Git/OneDrive. Never publish raw k3d node labels (which include its cluster token),
Secret manifests, credentials.json or cluster logs without redaction.
Do not activate live spending against a fresh ledger without preserving and
reconciling existing monthly admission debits. See [Kubernetes operations](KUBERNETES.md).

## Internal HTTPS ingress

The explicitly requested NPM proxy exposes only WebUI at `ai.aadi.dgoi.local` to
internal networks and the existing VPN. The router rule targets web ports only;
no WAN forwarding was configured. NPM port 81 remains loopback-only. NPM has no
Docker socket, provider credentials or database network; its shared WebUI network
is internal. Existing WebUI authentication and signup-disabled settings remain.
The wildcard certificate covers `*.aadi.dgoi.local`. The constrained private CA
signing key stays on the laptop, outside Git/sync; only its public certificate is
distributed. NPM leaf keys, admin credentials and database are protected runtime
files and encrypted backup contents. They must never enter this public repository.
See [ingress](INGRESS.md) for trust distribution, manual renewal and acceptance limits.
