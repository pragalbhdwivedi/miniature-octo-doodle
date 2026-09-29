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
- Agent Controller
- Extended observability

No optional component may be downloaded merely because it appears in the architecture.

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

Phase 1 core implementation is on `feat/phase1-core`: pinned Compose images,
guarded Windows startup, health checks and provider templates. See
[Quick Start](docs/QUICK_START.md), [PROJECT_STATE.md](PROJECT_STATE.md) and
[tested build evidence](docs/BUILD_STATUS.md). Both providers and Edge browser
chat are validated on the target machine; PR review/merge remains pending.
No optional component is installed by this project.
