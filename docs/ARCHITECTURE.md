# Architecture

## Canonical target

```text
                              YOU
                               │
                     Coding UI / Agent
                               │
                    ┌──────────▼──────────┐
                    │   Agent Controller  │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
     OpenViking             Graphify           Git / GitHub
       Memory              Code Graph          Source Truth
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Deterministic Policy│
                    │ auth/data/approval  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ TypeSafe Jev       │
                    │ choice/score/prob. │
                    └──────────┬──────────┘
                               │
                        ┌──────▼──────┐
                        │ AI GATEWAY  │
                        │  LiteLLM    │
                        └──────┬──────┘
                               │
      ┌──────────────┬─────────┼──────────┬──────────────┐
      │              │         │          │              │
      ▼              ▼         ▼          ▼              ▼
   OpenAI          Gemini    Claude    OmniRoute        Local
      API             API       API     optional       Ollama /
                                                llama.cpp
                                                        │
                                                 GTX 1650 Ti
                                                   + 64 GB RAM
```

## Architectural roles

### Git/GitHub
Canonical source code and project history.

### Graphify
Structural representation of repositories and relationships in code. It augments Git; it does not replace it.

### OpenViking
Persistent contextual memory for agents, decisions, resources, and prior work. It augments Git; it does not replace it.

### Agent Controller
Future orchestration layer for architect, implementer, tester, reviewer, security, and documentation agents.

### Deterministic policy layer
Hard rules decide whether a task is permitted, which data classification applies, whether cloud execution is allowed, which tools are available, whether a human approval is mandatory, and which spend/concurrency limits apply. A probabilistic model cannot override these rules.

### TypeSafe Jev
Disabled for Phase 2 by user decision, with offline Choice/authority contracts
prepared. Live integration/evaluation and activation remain deferred under ADR 0008.
Where subsequently validated, Jev may return typed choices, scores, or probabilities
for task classification, complexity, routing, risk, or escalation. Jev is decision
intelligence, not authority and not a generative coding model.

If Jev is unavailable, outside the evaluated task domain, malformed, or below the configured confidence/calibration threshold, the controller must use a deterministic fallback, fixed compliant route, or human review.

### LiteLLM
Mandatory central OpenAI-compatible gateway. Provider keys live behind the gateway whenever practical. LiteLLM performs the final provider/model routing only after deterministic policy and, where enabled, Jev decisioning.

### Open WebUI
Initial human-facing browser interface.

### Ollama / llama.cpp
Optional local inference. No model is downloaded by default.

## Routing trust rule

Fallback must never broaden data exposure.

Examples:
- `local-private` has no cloud fallback.
- a private route may fall back only to providers explicitly approved for the same data class.
- a free/experimental OmniRoute provider cannot become an implicit fallback for private work.
- a Jev recommendation cannot grant a provider, tool, data, or production permission that policy denied.

## Initial deployed architecture

```text
Browser
  -> Open WebUI
  -> LiteLLM
      -> OpenAI
      -> Gemini
LiteLLM -> PostgreSQL for gateway state
Open WebUI -> its persistent SQLite volume for UI state
```

The Phase 1 runtime is validated and PR #6 is merged. Phase 2 adds deterministic
policy as LiteLLM callbacks, plus a persistent `policy-data` SQLite admission ledger.
It requires no additional service/image. Jev live execution remains disabled;
only its offline decision contract is tested. See [ADR 0007](adr/0007-phase2-local-policy-ledger.md).

## Core principle
Document the full architecture now, install components only when they are needed and disk capacity allows it.

## Phase 1 implementation boundary

Compose defines only PostgreSQL, LiteLLM and Open WebUI. Cloud routes are included
only when their keys exist in local `.env`. WebUI receives a restricted gateway
inference key; provider keys and the master key remain in LiteLLM. The database
network is internal and PostgreSQL has no host port. UI/gateway ports bind to
127.0.0.1. See [ADR 0005](adr/0005-lean-authenticated-core.md).

The full Agent Controller, live Jev and optional local/provider-aggregation layers
remain targets. The current policy only admits public/synthetic text to the two
configured cloud providers; private/local-only inputs fail closed.

## Phase 4 validation deployment

A dedicated local k3d cluster implements the same three core services with separate
PVCs, internal services and WebUI Ingress. ConfigMaps carry tracked gateway policy;
per-service Secrets restrict credential distribution. Default-deny NetworkPolicy,
blank cloud keys and a zero allowance keep this fresh instance unable to spend.
It operates independently of Compose. Existing Compose records and budget history
have not been migrated. See [ADR 0010](adr/0010-isolated-kubernetes-validation.md).

## Operational progression and controller boundary

The revised roadmap accepts Phase 4 as developer validation only. Next is a
dedicated Linux VM running the core with Compose; full Kubernetes services are
Phase 12. The user subsequently selected Ubuntu template 9001, superseding the
Debian-only choice in [ADR 0011](adr/0011-debian-controller-progression.md).
See [ADR 0012](adr/0012-template-9001-ubuntu-target.md). The selected VM now runs
the migrated live Compose core with protected configuration, internal UI/database
networks and gateway-only provider egress. Loopback systemd socket proxies support
SSH-tunneled browser access. The VM owns current data and budget history; Windows
is frozen. See [Linux operations](LINUX_CORE.md). A user-requested internal Nginx
Proxy Manager entry point is deployed: internal DNS/Omada TCP 80/443 -> NPM ->
dedicated internal WebUI network -> existing UI/gateway. It routes
`ai.aadi.dgoi.local` within the `*.aadi.dgoi.local` namespace and does not join the
database network. See tested boundaries and open browser gates in [ingress](INGRESS.md).

Build an isolated worker (Phase 6), then a controller that refreshes each managed
repository and works from Git alone (Phase 7). OpenViking/Graphify are later context
enhancements, and Jev remains disabled until separately approved. Telegram is the
sole planned approval channel; WhatsApp is excluded. Human authority remains
required for merges, production deployments and other consequential actions.
AADI retains its own architecture and acceptance gates and must operate without
this development platform. See [the integration contract](AADI_DEVELOPMENT_INTEGRATION.md).

## Phase 6 worker execution boundary

The approved operator broker fetches an allowlisted public GitHub revision,
records its SHA and starts a disposable offline non-root container. The worker
receives a read-only source/job mount and bounded tmpfs workspace; it has no
gateway/provider/SSH credentials, host write mount or Docker socket. Commands
and local Git commits occur only inside it. Export compares allowlisted file
changes to the immutable input, preserving an audit record outside the worker.
No agent/runtime API can invoke the privileged broker. An operator adapter makes
one budget-reserved LiteLLM call and validates proposed edits before sandbox tests.
A separate publisher binds operator review to artifact hashes and creates only
new run branches/draft PRs; live publication passed in draft PR #16.
Phase 7 has a read-only planner and separate durable operator dispatcher;
independent review, bounded repair and draft publication use the operator pipeline below.
See [WORKER](WORKER.md) and [controller](AGENT_CONTROLLER.md).

## Service directory and remote access - 30 September 2026

DEPLOYED: password-free `dash.aadi.dgoi.local` directory and separate HRMS/console
HTTPS hostnames reuse existing ingress. Preserved-account login, protected reads,
logout and origin/anonymous denial passed. No image pull, migration or password
reset. User confirmed external OpenVPN and phone RDP login. WireGuard server routes
corrected; client setup/handshake pending. Phone CA/DNS and tunnel reboot/logon
acceptance remain open. See [dashboard operation](DASHBOARD.md) and
[remote-access evidence](REMOTE_ACCESS_CHECK.md).

## Durable operator dispatch

The read-only planner stays unprivileged. A separate operator CLI refreshes the
repository, binds approval to exact source/job/image/budget, commits a PostgreSQL
claim and invokes the bounded worker once. Duplicate/ambiguous runs cannot retry.
The dedicated database reuses the existing instance without gateway-table changes.
The separate schema-2 pipeline adds review, repair and publication gates. See
[ADR 0017](adr/0017-durable-operator-dispatch.md).

## Bounded review and publication increment

Independent fresh-context review and operator-owned sandbox tests now gate the
artifact. One repair may run within the aggregate $1 original/review/repair
ceiling, followed by new tests and review. Publication requires a separate exact
final-artifact approval and current source/ownership, then creates only a draft PR.
See [review operations](CONTROLLER_REVIEW.md) and BUILD_STATUS for actual acceptance.
No scheduler, merge/deployment authority, AADI activation or Telegram integration.
