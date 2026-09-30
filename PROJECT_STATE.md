# Project State

## Project
`pragalbhdwivedi/miniature-octo-doodle`

## Purpose
Modular local/cloud AI coding platform with a single AI gateway, browser UI, optional agent memory/code graph, and future multi-agent orchestration.

## Current phase
**Phases 1-2: COMPLETE and merged, with Jev disabled. Phase 3: local backup,
restore and clean container rebuild COMPLETE for the tested same-host scope.
Phase 4: COMPLETE for local developer Kubernetes validation.
Phase 5: PARTIAL, Docker and fresh zero-spend VM core deployed; direct laptop SSH,
API/browser acceptance and same-VM backup/restore passed. Live migration and
off-machine/clean-host recovery remain outstanding.**

PR [#6](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/6) was reviewed
and merged at `301e3a13a021fedfaa8418759661736fe784fb33`.
Phase 2 [PR #8](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/8)
merged at `c76406927ae1110e6023f4195c7d4b81c360cd55`, incorporating PR #7's design.
Phase 3 [PR #9](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/9)
merged at `3cf3b6db7b1005c1be4eb541151d0e6fc1d5cdc9`.
Phase 4 implementation: [PR #10](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/10),
branch `feat/phase4-kubernetes`, based on that main commit; not yet merged.
See `docs/BUILD_STATUS.md` for measured results, including live provider and Edge browser tests.

The updated roadmap from open PR #11 (`223bb00`) makes the dedicated Debian VM
Phase 5, followed by isolated worker, controller and Telegram approvals. It is
integrated with PR #10 on `feat/phase5-debian-foundation` for review; neither PR
has been merged to main. Local model installation is an optional lane, not next.

## Hardware baseline
- Windows 11
- AMD Ryzen 7 4800H
- 64 GB RAM
- NVIDIA GTX 1650 Ti, 4 GB VRAM
- 256 GB NVMe
- approximately 50 GB free at project start
- Docker Desktop + WSL2 expected

## Canonical architecture
Open WebUI / coding agent -> Agent Controller -> OpenViking + Graphify + Git/GitHub -> deterministic policy -> TypeSafe Jev decision layer -> LiteLLM -> OpenAI / Gemini / Claude / OmniRoute / optional Ollama/llama.cpp.

## Installed
Preflight validated Windows 11, Docker Desktop 29.8.0 / Compose 5.5.1,
WSL2 2.7.14.0, and NVIDIA visibility in Windows, Ubuntu, and a disposable
container using an already-installed image.

Deployed and healthy: PostgreSQL 16.15 Alpine, LiteLLM database 1.103.0,
Open WebUI 0.11.4 slim. Internal database, authentication, WebUI login and
gateway model discovery tests passed, including after an authorized Docker
Desktop restart. Existing unrelated workloads and volumes were preserved.

Windows HTTP access was restored on 2026-09-29 by switching the host's WSL
networking from mirrored to NAT and restarting WSL/Docker. Mirrored mode still
failed after a full WSL restart. Full core tests now pass via 127.0.0.1 and
localhost, including admin login and UI-to-gateway discovery. The exact upstream
defect is unresolved. The backed-up change and rollback procedure are recorded
in `docs/TROUBLESHOOTING.md`; no firewall or Compose exposure changes were needed.

On 2026-09-29, after the user configured provider keys locally and requested the
next action, OpenAI and Gemini each passed a bounded live completion through
the scoped LiteLLM key. Edge became available: existing administrator sign-in,
model selection and rendered responses from both providers passed in a temporary
WebUI chat. No alternate headless browser method was needed.

## Implemented and validated within Phase 1
- Pinned core Compose, persistent volumes, health checks, local-only publication.
- Guarded preflight/startup, random local secrets, restricted WebUI inference key.
- OpenAI/Gemini configuration with independently configurable model IDs/aliases.
- Empty-provider startup and both configured providers tested; live browser chat passed.
- Repeatable opt-in live probe: `scripts/test-providers.ps1 -RunLive`.
- Latest storage sample: 59.19 GiB free on C:; core image sizes sum to 2.68 GiB.

## Next bounded action
On 2026-09-30 the user resumed deployment. Both direct Windows/WSL SSH and the
bastion path now pass. The direct Omada rule is restricted to the laptop's current
address and the target's SSH port; the bastion handles changing laptop networks.
Outside-VPN acceptance remains pending by user choice. See [SSH access](docs/SSH_BASTION.md).

The selected Ubuntu VM now runs Docker Engine 29.8.1, Compose 5.5.1 and the three
pinned core services. Linux startup/private secrets and same-VM backup/restore
are implemented and tested. The VM WebUI is accessible through the SSH tunnel at
`http://localhost:3180`; it has fresh credentials/data, blank provider keys and a
zero allowance. The original Windows instance remains the live provider deployment.
Next: plan approved existing-data/ledger cutover and off-machine/clean-host recovery,
preserving the user's separate recovery pause until a target is identified.
See [Linux operations](docs/LINUX_CORE.md) and [Phase 5 gates](docs/DEBIAN_CONTROL_PLANE.md).

Preserve existing chats, credentials and monthly budget history during any later
explicitly approved migration. Zero-spend Kubernetes browser acceptance has passed.
The local k3d deployment is an isolated validation instance: no provider keys,
zero spending, fresh data, Jev disabled. It does not replace the Compose gateway.
Off-machine backup and new-machine recovery remain unvalidated; the user's pause
until their Kubernetes setup is running is preserved. A same-host k3d cluster
does not establish recovery on a separate machine or authorize a remote target.

Live Jev integration/evaluation/calibration remains deferred under ADR 0008.
No optional modules or model weights were installed. See [Kubernetes operations](docs/KUBERNETES.md).

## Phase 5 runtime checkpoint
- Direct Windows/WSL SSH, fresh-target admission, three-service health, admin login,
  scoped-key restrictions, eight aliases, zero-budget denial, synthetic routing,
  fallback/concurrency and database/external TCP isolation pass on the selected VM.
- Browser login/model selection/rendered budget denial passed through the SSH
  tunnel. Docker internal-only networks suppressed host bindings; unprivileged
  systemd socket proxies now provide loopback-only HTTP without container egress.
- Independent restore from a protected cold backup passed exact file-content,
  PostgreSQL dump, SQLite integrity and restored login/key checks. Recovery
  containers are stopped; artifacts and volumes are retained. No live data migrated.
- Runtime credentials remain outside Git in a 0700 directory with 0600 files.
  Jev/provider activation is rejected by the fresh-runtime tool. No optional
  module, agent/controller, model or provider credentials installed on the VM.
- Gateway recreation and planned VM reboot passed: credentials persisted, services
  and loopback access returned automatically, and full runtime tests passed after
  health readiness. Ledger debit/provider attempts remain zero; VM free 51.78 GiB.

## Phase 5 initial preparation checkpoint (2026-09-29)
- Complete private VM handover record is in local `VM_NOTES/9125-gatewayai-control.md`
  and the VM's Proxmox Notes. Both were verified on 2026-09-29; operational details
  remain Git-excluded. AGENTS.md requires this for every future VM.
- Implemented read-only Debian 12/13 and Ubuntu 24.04 VM preflight: local Engine/Compose, systemd,
  CPU/RAM, both runtime and Docker storage reserves, fresh-target and loopback-port checks.
- Guard tests cover unsupported hosts, remote Docker endpoints, occupied targets
  and disk thresholds. Real Windows and WSL Ubuntu runs correctly reject the host.
- Independent full clone: 4 vCPU, 8 GiB RAM, 60 GiB disk; auto-start enabled.
  Verified guest identity, disk expansion, DNS/HTTPS, administrator SSH keys/sudo
  and QEMU guest agent. Target preflight passes OS/VM/resources/runtime disk/ports;
  overall BLOCKED as expected because Docker/Compose are not installed.
- At this initial checkpoint, Linux startup/recovery/browser work had not begun.
  The 2026-09-30 runtime checkpoint above supersedes that status. Off-machine
  restore and live migration remain unvalidated. See BUILD_STATUS for limits.

## Phase 4 local checkpoint
- Dedicated k3d 5.9.0 / k3s 1.35.5 cluster; existing Docker Desktop context preserved.
- PostgreSQL, LiteLLM and WebUI ready, three bound PVCs, UI Ingress on loopback 3080.
- HTTP through both localhost names, admin login, scoped key, eight aliases and
  zero-budget rejection passed. Synthetic routing/fallback/concurrency tests passed.
- NetworkPolicy permits gateway-to-database and UI-to-gateway only (plus DNS and
  Ingress); UI-to-database and external TCP egress denial passed.
- Edge browser acceptance passed at `http://localhost:3080`: existing admin sign-in,
  eight-alias picker, `coding-standard` selection and rendered zero-budget denial in
  a temporary chat. The prior browser automation blocker did not recur this session.
- Post-browser ledger: zero debit, zero provider attempts, zero active requests;
  provider keys remain empty and Jev disabled. Screenshot is in `docs/evidence/`.
- All three deployments remain ready; 41.37 GiB free, no image pull/runtime change.
- Kubernetes provider inference, Compose-data migration, off-machine recovery and
  Kubernetes backups remain unvalidated. No production/cutover readiness claim.

## Phase 3 local recovery checkpoint
- Consistent cold backup of PostgreSQL, WebUI and policy volumes, existing secrets,
  rendered configuration and Git source; SHA-256 manifest and archive safety checks.
- Private physical AppData storage with current-user/SYSTEM ACLs; no Git/OneDrive
  backup, external upload, image pull or optional component installation.
- Final backup: `backup-20260929T132209Z`, 71,571,646 bytes; core interruption 48.80 s.
- Fresh source directory, three new volumes and three rebuilt containers passed
  exact file comparisons, PostgreSQL full dump read, SQLite integrity, restored
  admin/key access, eight-alias discovery and synthetic routing/fallback tests.
- Final restore/validation: 78.46 s. Recovery networks internal, no host ports,
  cloud keys omitted, budget zero, Jev disabled. Recovery containers stopped;
  failed/successful test volumes retained. No production cutover performed.
- Original $100 allowance / 2.875240 USD conservative debit unchanged, zero active
  requests; full original core host/auth tests pass and all 31 original container
  identities still run. Latest free C: 45.47 GiB; no automatic data cleanup.
- Off-machine encrypted retention, new-machine provisioning/image retrieval,
  restored-browser cutover and reboot/power-loss recovery remain unvalidated.

## Phase 2 design checkpoint
- TypeSafe Jev is the selected structured decision-layer evaluation target.
- Deterministic policy remains authoritative for data classes, provider allowlists, tools, spend limits and human approval.
- LiteLLM remains the mandatory execution gateway.
- Jev Choice parsing and authority/failure contracts are tested with synthetic fixtures.
  Live Jev integration, accuracy, domain evaluation and calibration are **deferred** by
  user instruction; a blank local key field exists but is not passed to containers.
- Deterministic mode and `jev_enabled: false` are explicit. Renderer and gateway
  startup reject activation, even if a key is present. This is a tested disabled
  boundary, not a claim that live Jev integration is ready.
- Six capability aliases plus the two legacy aliases are deployed. Native HTTP
  outage/quota fallback, provider restrictions, private/local-only denial, streaming,
  atomic budgets and concurrency tests pass. No local provider is installed.
- The local allowance is US$100 per UTC calendar month, using conservative
  admission debits rather than billed spend. Fresh installs default to zero.
- Policy ledger survives gateway recreation. WebUI's default avoids automatic
  native builtin-tool injection; actual tool definitions remain denied.
- Core host/auth/model-discovery checks and a live capability browser response pass.
- See `docs/PHASE2_POLICY.md` for the declarative classification boundary, supported
  text-only requests, cost ceilings and remaining validation limits.
- The discussion catalogue is in `docs/MODELS_AND_SKILLS.md`.

## Later phases / optional
- Anthropic / Claude
- OmniRoute
- Ollama
- local LLM
- OpenViking
- Graphify
- isolated coding worker (Phase 6)
- Agent Controller (Phase 7)
- Telegram approvals (Phase 8; WhatsApp excluded)
- Kubernetes live provider/data cutover
- extended observability

## Storage policy
- warning threshold: <25 GB free
- critical threshold: <15 GB free
- initial target: keep new core footprint around 10-12 GB where practical
- do not download local models automatically
- do not duplicate local models between Docker and Kubernetes

## Completion rule
Do not mark a subsystem COMPLETE until it has been run and tested on the target machine. Architecture documents are not implementation evidence.
