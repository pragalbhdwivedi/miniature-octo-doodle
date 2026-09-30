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

## VM documentation
User instruction, 29 September 2026: whenever creating a VM, create or update
`VM_NOTES/<vmid>-<name>.md` in the owning project folder before handing it over.
Include creation/verification date, project/purpose, VMID/name, cluster name,
hypervisor host/node and address, source template/OS, CPU model/sockets/vCPU,
RAM/ballooning, every disk's capacity/format and storage backend/server/share/
volume/path, NIC/MAC/bridge/VLAN/firewall/IP/prefix/gateway/DNS, startup/boot order,
guest agent, tags/pool, backup/HA/replication state, username, authentication
method and tested access/status limits. Mark unavailable facts as unverified.
Also write the same operational inventory to the Proxmox VM Notes (description)
section, preserving pre-existing notes. Read it back to verify it saved. Keep the
project record and Proxmox notes consistent after changes; never include a
password, private key or token in Proxmox Notes.
State explicitly whether SSH password login is disabled, enabled or unverified;
do not equate key authentication working with password login being disabled.

Keep host-specific notes local and Git-excluded. Never put actual passwords or
private keys in project Markdown, even ignored files in a synced folder. If a
password is provisioned, place it in a protected local credential file outside
Git/sync and record only its location in the VM note. For SSH-only access, say
so and record which existing public keys were installed; never copy private keys.
This recording rule also applies to AADI and future project folders.

## Production safety
Coding agents must not receive unrestricted production credentials, Docker host socket access, or arbitrary host shell execution by default.
