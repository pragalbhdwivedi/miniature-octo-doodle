# Project State

## Project
`pragalbhdwivedi/miniature-octo-doodle`

## Purpose
Modular local/cloud AI coding platform with a single AI gateway, browser UI, optional agent memory/code graph, and future multi-agent orchestration.

## Current phase
**Phases 1-2: COMPLETE and merged, with Jev disabled. Phase 3: local backup,
restore and clean container rebuild COMPLETE on the implementation branch.**

PR [#6](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/6) was reviewed
and merged at `301e3a13a021fedfaa8418759661736fe784fb33`.
Phase 2 [PR #8](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/8)
merged at `c76406927ae1110e6023f4195c7d4b81c360cd55`, incorporating PR #7's design.
Phase 3 implementation branch: `feat/phase3-recovery`, based on that main commit.
Phase 3 is tested locally; it is not yet merged to main.
See `docs/BUILD_STATUS.md` for measured results, including live provider and Edge browser tests.

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
Review the Phase 3 recovery implementation. Its same-host cold backup and isolated
restore/rebuild passed; see `docs/BACKUP_RESTORE.md` and the measured build record.
Choose protected off-machine backup storage before claiming laptop-loss recovery.
Phase 2 remains accepted with Jev disabled under ADR 0008.
Live Jev integration/evaluation/calibration is deferred to a separately reviewed
and authorized change with a key and evaluation allowance. Local validation is
not production or new-machine recovery certification. Kubernetes and optional
modules remain later phases. NAT applies to all WSL2
distributions; direct WSL LAN access and
Linux-to-Windows localhost semantics change. All 31 running workload identities
and six volumes were preserved; unrelated applications were not functionally tested.
No reboot, firewall changes or data deletion was performed.

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

## Deferred / optional
- Anthropic / Claude
- OmniRoute
- Ollama
- local LLM
- OpenViking
- Graphify
- coding agent
- Agent Controller
- Kubernetes runtime
- extended observability

## Storage policy
- warning threshold: <25 GB free
- critical threshold: <15 GB free
- initial target: keep new core footprint around 10-12 GB where practical
- do not download local models automatically
- do not duplicate local models between Docker and Kubernetes

## Completion rule
Do not mark a subsystem COMPLETE until it has been run and tested on the target machine. Architecture documents are not implementation evidence.
