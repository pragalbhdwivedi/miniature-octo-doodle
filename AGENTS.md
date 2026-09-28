# AGENTS.md

These rules apply to ChatGPT Work, Codex, Claude Code, Gemini CLI, GitHub Copilot agents, and any other coding agent working in this repository.

## First action
Before making changes:
1. Read `README.md`.
2. Read `PROJECT_STATE.md`.
3. Read `WORK_INSTRUCTIONS.md`.
4. Read `docs/ARCHITECTURE.md`.
5. Read `docs/BUILD_STATUS.md`.
6. Inspect current Git status, recent commits, open issues, and open pull requests.

## Source of truth
GitHub is the source of truth for current project state. Do not rely on old chat context when repository state disagrees.

## Change discipline
- Prefer small, reviewable changes.
- Preserve history.
- Do not silently replace architecture.
- Update documentation when behavior changes.
- Clearly separate planned, implemented, tested, and deployed states.
- Never claim a component works unless it has been validated.

## Public repository rule
Never commit secrets or private data.

Forbidden:
- provider API keys
- passwords
- tokens
- private keys
- production credentials
- institutional/student/employee records
- database exports
- model weights
- backups
- local runtime volumes

## Storage discipline
The target laptop starts with only about 50 GB free.
- Do not download large models without explicit approval.
- Do not pull optional images during base install.
- Check free disk before any optional installation.
- Stop at the critical threshold defined in `PROJECT_STATE.md`.

## Architecture discipline
The canonical target is modular. LiteLLM is the central AI gateway. Git/GitHub remains source of truth. OpenViking is memory, Graphify is code graph, neither replaces Git.

## Deployment discipline
Docker Compose first. Kubernetes second. Do not require both to be active at once.

## Production safety
Coding agents must not receive unrestricted production credentials, Docker host socket access, or arbitrary host shell execution by default.
