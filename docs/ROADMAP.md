# Roadmap

## Phase 0 - Repository and architecture
- source-of-truth documentation
- component registry
- security/storage rules

## Phase 1 - Core Docker platform
- preflight
- PostgreSQL
- LiteLLM
- Open WebUI
- OpenAI
- Gemini

## Phase 2 - Gateway intelligence and decision plane
Status: COMPLETE with Jev disabled by user decision ([ADR 0008](adr/0008-phase2-acceptance-jev-disabled.md)).
Deterministic routing, fallbacks and conservative budgets are deployed and tested.
Jev wire/authority contract tests are synthetic; live integration, evaluation and
calibration are deferred until separately authorized. No optional module is installed.

- deterministic policy layer
- model aliases
- TypeSafe Jev synthetic evaluation
- routing
- fallbacks
- budgets
- request/provenance logging policy
- local-private route with no cloud fallback
- provider outage and Jev-outage tests
- prove fallback cannot broaden data exposure

## Phase 3 - Recovery
Status: local backup/restore and clean container rebuild COMPLETE on
main, merged through PR #9 (`3cf3b6d`). Same-host isolated rehearsal passed;
off-machine retention, new-machine recovery and production cutover remain outside
this evidence. See [recovery operations](BACKUP_RESTORE.md).

New-machine recovery validation remains paused pending an approved target.
Phase 5 subsequently validated an encrypted off-VM copy and same-host restore
from its authenticated readback; separate-machine recovery remains unvalidated.

- backup
- restore
- clean rebuild test
- disk reporting

## Phase 4 - Developer Kubernetes validation
Status: COMPLETE for the local developer-validation scope. PR #10 contains the
implementation; browser, policy/isolation and persistence evidence is recorded in
[BUILD_STATUS](BUILD_STATUS.md). This does not claim live migration or production readiness.

This phase validates the existing gateway stack on a disposable/local Kubernetes
environment. k3d/K3s is a **developer-validation mechanism only** for this repository;
it is not the production orchestration target for AADI.

- k3d-based local validation where useful
- base manifests and Ingress
- same core services and policy boundaries
- persistence/recreation checks
- no duplicate large model storage
- no claim that a passing k3d test approves an AADI production cluster

## Phase 5 - Dedicated always-on control-plane VM
Target update: the user selected Proxmox template 9001 (Ubuntu 24.04) on
2026-09-29, superseding the original Debian-only choice below. See
[ADR 0012](adr/0012-template-9001-ubuntu-target.md). Debian remains a supported
candidate; the selected VM uses Ubuntu. Provider/policy contracts are unchanged.

Status: PARTIAL; live Windows data/ledger migration, provider/browser acceptance,
reboot and encrypted off-VM readback/restore passed. Internal HTTPS is deployed;
broader client trust/access, separate clean-host recovery and reverse live cutover
remain outstanding. See the [acceptance plan](DEBIAN_CONTROL_PLANE.md)
and [Linux operations](LINUX_CORE.md).

Move the proven core from the Windows/WSL2 development host to the selected Linux
VM without changing the repository's provider/policy contracts.

- PostgreSQL
- LiteLLM
- Open WebUI
- deterministic policy and budgets
- Agent Controller runtime foundation
- protected secrets outside Git
- backup/restore and clean-host recovery evidence
- no GPU requirement for the control plane
- Windows Docker remains a supported development environment, not the permanent
  always-on controller

Target progression:

```text
Windows + Docker/WSL2 development
        ->
dedicated Linux control-plane VM (selected Ubuntu template 9001)
        ->
full Kubernetes deployment when scale/recovery evidence justifies it
```

## Phase 6 - Isolated coding worker v0.1
Status: COMPLETE for bounded operator scope on 30 September 2026. The zero-spend execution
boundary is deployed/tested: approved public repository refresh, bounded offline
commands/tests, isolated local branch/commit and immutable-source artifact review.
Gateway-backed one-turn coding and per-run budgets are deployed/live-tested.
Scoped draft-PR publication passed live in PR #16; bounded Phase 6 scope is complete.
Token repository restrictions remain the operator provisioning responsibility.
See [worker operations](WORKER.md). Phase 5's open gates remain open.

Build the first execution worker before adding persistent agent memory or a large
multi-agent hierarchy.

- clone/fetch approved repositories
- one isolated workspace or Git worktree per run
- bounded shell and test execution
- Codex/coding-agent executor behind explicit policy
- Git branch/commit/push support
- no direct push to protected/default branches
- no unrestricted Docker socket by default
- no production credentials or production kubeconfig
- disposable worker recovery/rebuild
- iteration, time and cost ceilings

## Phase 7 - Agent Controller v0.1
Status: STARTED / PARTIAL. Read-only repository refresh, task/dependency/ownership
planning and zero-authority review artifacts are implemented and tested. Live
unprivileged refresh/deny passed. PostgreSQL persistence and controlled operator
dispatch are implemented, along with independent review, one repair and gated
draft publication. See BUILD_STATUS for measured acceptance and remaining gates,
[dispatch operations](CONTROLLER_DISPATCH.md) and [controller operations](AGENT_CONTROLLER.md).

Implement the shared controller that turns a repository's own roadmap and issues
into bounded development runs.

- project registry/adapters
- mandatory repository refresh before each run
- task/issue/PR ownership reconciliation
- dependency-aware task selection
- prompt construction from current repository evidence
- capability-alias model selection through LiteLLM
- run state and audit records in PostgreSQL
- planner -> implementer -> deterministic tests -> independent reviewer
- automatic repair within configured limits
- push only to reviewable branches
- create/update draft pull requests
- pause instead of inventing requirements when human authority is required

The first managed project is
[`pragalbhdwivedi/aadi`](https://github.com/pragalbhdwivedi/aadi). AADI remains
the source of truth for its own requirements, issue sequence, architecture and
approval gates. This repository supplies development tooling; it does not become
an AADI runtime dependency.

See [AADI development integration](AADI_DEVELOPMENT_INTEGRATION.md).

## Phase 8 - Telegram approval and pause/resume
Status: STARTED / PARTIAL. Exact draft-publication decision state and synthetic
Telegram callback/real PostgreSQL tests pass. No bot token or approved user/chat
is configured, so live delivery and full pause/resume remain unvalidated. See
[Telegram operations](CONTROLLER_TELEGRAM.md) and BUILD_STATUS.

Add a single human control channel for development decisions.

- Telegram bot restricted to approved user/account identity
- PR-ready, blocked, approval-required and budget-limit notifications
- structured approve/reject/choose/pause/resume actions
- resume the exact stored run after a response
- signed/expiring approval records bound to the exact action or payload
- no approval inferred from silence

**WhatsApp is out of scope and must not be added as a fallback or secondary
approval channel.**

Initial autonomous authority is limited to:

```text
select bounded task
-> create isolated branch/workspace
-> implement
-> test
-> bounded repair
-> push agent branch
-> create/update draft PR
```

Human approval remains mandatory for merge, deployment, production changes,
database migrations affecting real data, external communications, credentials,
spending outside approved limits and other consequential actions.

## Phase 9 - Agent context and repository intelligence
Status: STARTED / PARTIAL. The public code-only Graphify index and a read-only,
fresh-Git query gate passed on VM9125. OpenViking public-main sync is timed and
the operator controller's advisory read path is enabled and live smoke-tested;
one paid reviewer call with retrieved public context passed. Private WebUI admin
text chats are now mirrored into isolated raw sessions; encrypted clean-guest
restore passed on VM9127. Memory quality, derived-memory deletion and NAS/site
loss recovery remain open. See
BUILD_STATUS, GRAPHIFY and OPENVIKING for measured scope.

Add context systems only after the controller can work correctly from Git alone.

- OpenViking persistent development context
- Graphify/code graph
- permission-aware context selection
- stale-context detection against fresh Git state
- no context store may override repository source of truth
- context compaction and retrieval evaluation

These components improve efficiency; they are not prerequisites for the first
working AADI development controller.

## Phase 10 - Multi-agent development
Expand logical roles only after the single-controller workflow is reliable.

- architect/planner
- implementer
- tester
- reviewer
- security reviewer
- documentation/release evidence agent
- bounded parallelism only for non-conflicting tasks
- independent review prompts/models where useful
- shared run/audit state rather than chat-memory coordination

Multiple AI agents never substitute for required human approval.

## Phase 11 - Advanced model routing and Jev live evaluation
Keep deterministic authority ahead of probabilistic routing.

- labelled routing/task-complexity evaluation
- TypeSafe Jev shadow/live evaluation only after separate approval
- calibration and low-confidence behaviour
- model performance/cost history
- provider/model selection by capability rather than hard-coded model names
- outage and quota handling
- local/private route evaluation
- provider fallback may not broaden data/trust exposure

Jev remains advisory decision intelligence. It cannot grant repository,
production, tool, secret or approval authority.

## Phase 12 - Full Kubernetes service deployment
Move the proven control-plane services and scalable worker execution to a
supported Kubernetes deployment when operational evidence warrants it.

- controller and gateway services
- worker Jobs with isolated service accounts/workspaces
- persistent state and tested recovery
- NetworkPolicies and scoped secrets
- resource/budget/concurrency controls
- observability and run audit
- no assumption that k3d/K3s development validation is the AADI production target

For AADI specifically, its own repository and ADRs govern the production
Kubernetes architecture. This platform may supply development workers and model
routing without dictating AADI's runtime topology.

## Optional capability lanes
The following do not block the controller roadmap and may be evaluated when
storage, security and current need justify them:

- Ollama / llama.cpp
- one small local coding model
- Anthropic / Claude
- OmniRoute
- additional observability
- security-reviewed reusable engineering skills

The owner activated the Windows laptop Ollama/local-model evaluation lane on
1 October 2026, then requested a 15 GB coding model, a small thinking
supervisor and both models in the existing WebUI. Their two local-only LiteLLM
aliases passed bounded live tests. This lane remains separate from Phase 9's
context work; see [local model operations](LOCAL_MODEL.md) for scope and limits.

Provider/model additions must remain behind LiteLLM capability aliases and the
deterministic policy layer.

## Bounded review and publication increment

Independent fresh-context review and operator-owned sandbox tests now gate the
artifact. One repair may run within the aggregate $1 original/review/repair
ceiling, followed by new tests and review. Publication requires a separate exact
final-artifact approval and current source/ownership, then creates only a draft PR.
See [review operations](CONTROLLER_REVIEW.md) and BUILD_STATUS for actual acceptance.
No scheduler, merge/deployment authority, AADI activation or Telegram integration.
