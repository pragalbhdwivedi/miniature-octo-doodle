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
- Current acceptance: complete the deterministic scope with Jev disabled, per
  the user's decision in `docs/adr/0008-phase2-acceptance-jev-disabled.md`.
  Live Jev integration/evaluation/calibration is a deferred activation gate.
- deterministic request/data policy layer
- TypeSafe Jev structured decision/routing evaluation using synthetic labelled cases
- routing, fallbacks, budgets
- local-private route with no cloud fallback
- low-confidence/Jev-outage deterministic fallback
- provider outage/quota tests
- prove fallback cannot broaden data exposure

### Milestone 5
- Docker backup/rebuild validation

### Milestone 6
- lightweight local Kubernetes using k3d unless current validation shows a better fit
- base deployment only
- Ingress
- do not duplicate local model storage

### Later milestones
Follow the updated [roadmap](docs/ROADMAP.md); the milestone numbers above are
historical implementation steps, not additional roadmap phases.

- Phase 5: dedicated Linux control-plane VM, protected configuration and recovery.
  The user-selected template 9001 is Ubuntu 24.04; ADR 0012 supersedes Debian-only
  target selection while retaining Debian compatibility.
  Start with [target admission](docs/DEBIAN_CONTROL_PLANE.md). Local k3d is developer
  validation only; it is not the AADI production architecture.
- Phase 6: isolated coding worker with bounded shell/tests and no production authority.
- Phase 7: repository-driven Agent Controller; Git alone must suffice initially.
- Phase 8: Telegram-only approvals and exact-run pause/resume; no WhatsApp integration.
- Phase 9: OpenViking/Graphify context, after the controller works without them.
- Phases 10-12: multi-agent roles, separately approved advanced routing/Jev, then
  full Kubernetes deployment when operational evidence justifies it.

Ollama/llama.cpp, local models, OmniRoute, extra observability and third-party
skills remain optional lanes requiring the existing installation checks. They
are not prerequisites for the worker/controller. AADI governs its own requirements
and production deployment; this platform is not an AADI runtime dependency.

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

## Decision separation
Never merge permission and model selection into one probabilistic prompt.

- deterministic policy decides what is allowed
- Jev may help decide among already-permitted routes
- LiteLLM executes the selected approved provider/model route
- human approval remains mandatory where configured

## Security
- `.env` is local only.
- commit only `.env.example`.
- no API keys in repository, logs, screenshots, issues, or documentation.
- no unrestricted Docker socket.
- no arbitrary host shell from web UI.
- no production credentials.
- no cloud fallback from a local-only route.
- third-party skills/plugins require review before activation.

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
- `docs/MODELS_AND_SKILLS.md` as the non-approved research catalogue

At the end of every milestone record:
- what changed
- what was tested
- what failed
- disk consumed
- remaining disk
- next step

Do not continue automatically into optional heavyweight modules.
