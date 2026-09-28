# ChatGPT Work Implementation Brief

Use this file as the primary execution brief for ChatGPT Work.

## Objective
Build a complete, documented, rebuildable AI development platform in this repository.

The first working milestone is intentionally small:

```text
Browser
  -> Open WebUI
  -> LiteLLM
      -> OpenAI
      -> Gemini

plus PostgreSQL
```

Do not install heavyweight optional components until the core passes tests.

## Hard machine constraints
- Windows 11 host
- Ryzen 7 4800H
- 64 GB RAM
- GTX 1650 Ti 4 GB VRAM
- 256 GB NVMe
- about 50 GB free at project start
- Docker Desktop / WSL2

Storage conservation is a hard requirement.

## Required implementation sequence

### Milestone 0
- system discovery
- preflight report
- verify Docker / Compose / WSL2
- verify available disk
- verify NVIDIA GPU visibility
- update BUILD_STATUS

### Milestone 1
- LiteLLM
- PostgreSQL
- health checks
- local-only exposure by default

### Milestone 2
- Open WebUI
- connect Open WebUI only through LiteLLM
- confirm browser access

### Milestone 3
- OpenAI provider template
- Gemini provider template
- no secrets in Git
- configurable model aliases

### Milestone 4
- routing, fallbacks, budgets
- local-private route with no cloud fallback

### Milestone 5
- Docker backup/rebuild validation

### Milestone 6
- lightweight local Kubernetes using k3d unless current validation shows a better fit
- base deployment only
- Ingress
- do not duplicate local model storage

### Later milestones
- Ollama
- one small local coding model
- OmniRoute
- OpenViking
- Graphify
- coding agent
- Agent Controller
- expanded observability

## Before pulling large images
Report:
- host free disk
- Docker usage
- WSL2 status
- GPU status
- estimated additional footprint

Do not proceed if the critical free-space threshold would be crossed.

## Provider abstraction
Clients should call LiteLLM rather than provider APIs directly wherever practical.

Capability aliases should be configurable, for example:
- coding-fast
- coding-standard
- coding-hard
- architecture
- review
- documentation
- local-private

Do not permanently hard-code provider model names. Verify currently supported provider/model identifiers at implementation time.

## Security
- `.env` is local only.
- commit only `.env.example`.
- no API keys in repository, logs, screenshots, issues, or documentation.
- no unrestricted Docker socket.
- no arbitrary host shell from web UI.
- no production credentials.

## Required deliverables
Maintain:
- `README.md`
- `PROJECT_STATE.md`
- `docs/BUILD_STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/STORAGE.md`
- `docs/SECURITY.md`
- `docs/ROADMAP.md`
- ADRs for material architecture decisions

At the end of every milestone record:
- what changed
- what was tested
- what failed
- disk consumed
- remaining disk
- next step

Do not continue automatically into optional heavyweight modules.
