# miniature-octo-doodle

A modular, self-hosted AI development platform, developed on Windows + WSL2 with
a dedicated Linux control-plane VM now hosting the live gateway.

This repository is the permanent source of truth for the platform. It is designed to start lean on a laptop with limited free disk space, while preserving a documented path to a larger multi-agent coding system.

## Canonical target architecture

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
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ TypeSafe Jev       │
                    │ decision layer      │
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
 Sol/Terra/Luna      API       API     Free APIs       Ollama
                                                        │
                                                 GTX 1650 Ti
                                                   + 64 GB RAM
```

## Current hardware constraint

The initial target machine has approximately 50 GB free on a 256 GB NVMe drive. The core installation therefore must remain small.

### Install now
- LiteLLM
- PostgreSQL
- Open WebUI
- OpenAI provider configuration
- Gemini provider configuration

### Document now, install later
- Anthropic / Claude
- OmniRoute
- Ollama
- Local coding model
- OpenViking
- Graphify
- Coding agent
- TypeSafe Jev decision layer (Phase 2 evaluation)
- Agent Controller
- Security-scanned reusable agent skills
- Extended observability

No optional component may be downloaded merely because it appears in the architecture.

The control plane deliberately separates **authority**, **decision intelligence**, and **model execution**: deterministic policy decides what is permitted; Jev may help choose among already-permitted routes; LiteLLM executes the approved provider/model route. A Jev or LLM result cannot grant itself broader access.

## Source-of-truth rule

Repository files and Git history are authoritative for this project. Chat history is not.

Before implementation, read:
1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `WORK_INSTRUCTIONS.md`
4. `docs/ARCHITECTURE.md`
5. `docs/BUILD_STATUS.md`

## Security

This repository is public. Never commit:
- API keys
- credentials
- private keys
- production tokens
- institutional/student/employee data
- raw exports
- local model files
- database contents
- backups

Use `.env` locally. Only `.env.example` belongs in Git.

## Deployment philosophy

Docker Compose is the first operational target. Kubernetes definitions are maintained in parallel for later use, but the project must not require both environments to run simultaneously.

## Status

Phase 1 is validated and merged through PR #6. Phase 2 adds deterministic
policy, capability aliases, bounded fallbacks and a persistent monthly admission
budget, merged through PR #8 and incorporating the design from PR #7. See
[Quick Start](docs/QUICK_START.md), [PROJECT_STATE.md](PROJECT_STATE.md) and
[tested build evidence](docs/BUILD_STATUS.md). Both providers and Edge browser
chat are validated on the target machine. See [policy operations](docs/PHASE2_POLICY.md)
for limits and budget semantics. New installations default to zero spending.
Phase 2 is COMPLETE for the accepted deterministic scope, with Jev explicitly
disabled by user decision. Live Jev integration/evaluation/calibration is deferred;
see [ADR 0008](docs/adr/0008-phase2-acceptance-jev-disabled.md).
The user-requested internal Nginx Proxy Manager and Phase 6 worker are installed; other optional
components remain deferred. See [Models and Skills](docs/MODELS_AND_SKILLS.md).

Phase 3 backup, isolated restore and clean container rebuild are implemented and
tested and merged through [PR #9](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/9). See the
[recovery runbook](docs/BACKUP_RESTORE.md). The drill preserves the live deployment,
blocks recovery-copy cloud access and retains all data. Phase 5 migration/retention evidence and clean-host limits are recorded below.

Phase 4 developer validation is complete: an isolated k3d core with persistent volumes, network policies
and loopback Ingress passes API, synthetic policy and zero-spend browser acceptance
checks. It uses fresh test data, zero budget and no cloud keys; Compose
remains the live provider deployment. See [Kubernetes operations](docs/KUBERNETES.md).

Phase 5 has started with a read-only [Linux target preflight and acceptance plan](docs/DEBIAN_CONTROL_PLANE.md).
The user selected Proxmox template 9001 (Ubuntu 24.04), superseding the original
Debian-only target. See [ADR 0012](docs/adr/0012-template-9001-ubuntu-target.md) and
[current VM evidence](docs/BUILD_STATUS.md). The VM now has direct Windows/WSL SSH,
Docker and the migrated live Compose core. Existing data, credentials and budget
ledger were retained; provider/browser acceptance and encrypted off-VM readback
passed. See [Linux operations](docs/LINUX_CORE.md). Separate clean-host recovery
and reverse cutover remain pending, so Phase 5 is still partial.
Internal HTTPS is deployed at `https://ai.aadi.dgoi.local` within the shared
`*.aadi.dgoi.local` namespace. API/streaming checks passed; private CA browser
trust and broader client acceptance remain pending. See [ingress operations](docs/INGRESS.md).
The updated [roadmap](docs/ROADMAP.md) prioritizes an isolated worker, repository-driven
controller and Telegram approvals before optional memory/code graph or local models.
AADI is the first managed development project and retains its own production authority.

Phase 6 has started with a tested [isolated worker execution boundary](docs/WORKER.md):
fresh approved-repository snapshots, bounded offline commands/tests, local worker
branches/commits and reviewed artifact export. The live gateway is unchanged.
Gateway-backed one-turn coding and per-run budgets passed live acceptance. Scoped
draft-PR publishing passed live acceptance in PR #16, completing the bounded
Phase 6 scope. Token restriction is an operator provisioning responsibility. No sandbox receives credentials.

## Service directory and remote access - 30 September 2026

DEPLOYED: password-free `dash.aadi.dgoi.local` directory and separate HRMS/console
HTTPS hostnames reuse existing ingress. Preserved-account login, protected reads,
logout and origin/anonymous denial passed. No image pull, migration or password
reset. User confirmed external OpenVPN and phone RDP login. WireGuard server routes
corrected; client setup/handshake pending. Phone CA/DNS and tunnel reboot/logon
acceptance remain open. See [dashboard operation](docs/DASHBOARD.md) and
[remote-access evidence](docs/REMOTE_ACCESS_CHECK.md).

Phase 7 has started with a [read-only repository planner](docs/AGENT_CONTROLLER.md).
It checks committed tasks, current issues/PRs, ownership and dependencies, then
emits a zero-budget plan for operator review. It cannot execute, publish or merge.
A separate operator-only dispatcher now adds PostgreSQL claims/audit, exact-request
approval and one bounded worker attempt. The review pipeline adds fresh-context
review, one repair and exact-artifact draft publication gates. See
[dispatch operations](docs/CONTROLLER_DISPATCH.md). The [reviewed PR stack](docs/PR_STACK_REVIEW.md)
records what is merged and what still awaits acceptance.

## Bounded review and publication increment

Independent fresh-context review and operator-owned sandbox tests now gate the
artifact. One repair may run within the aggregate $1 original/review/repair
ceiling, followed by new tests and review. Publication requires a separate exact
final-artifact approval and current source/ownership, then creates only a draft PR.
See [review operations](docs/CONTROLLER_REVIEW.md) and BUILD_STATUS for actual acceptance.
No scheduler, merge/deployment authority, AADI activation or Telegram integration.
