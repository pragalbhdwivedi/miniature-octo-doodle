# miniature-octo-doodle

A modular, self-hosted AI development platform for a Windows + WSL2 workstation.

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
No optional component is installed by this project. See [Models and Skills](docs/MODELS_AND_SKILLS.md).

Phase 3 backup, isolated restore and clean container rebuild are implemented and
tested and merged through [PR #9](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/9). See the
[recovery runbook](docs/BACKUP_RESTORE.md). The drill preserves the live deployment,
blocks recovery-copy cloud access and retains all data. Off-machine disaster
recovery and production cutover are separate, unvalidated steps.

Phase 4 has started: an isolated k3d core with persistent volumes, network policies
and loopback Ingress passes API, synthetic policy and zero-spend browser acceptance
checks. It uses fresh test data, zero budget and no cloud keys; Compose
remains the live provider deployment. See [Kubernetes operations](docs/KUBERNETES.md).
