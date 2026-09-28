# Project State

## Project
`pragalbhdwivedi/miniature-octo-doodle`

## Purpose
Modular local/cloud AI coding platform with a single AI gateway, browser UI, optional agent memory/code graph, and future multi-agent orchestration.

## Current phase
**Phase 1: PARTIAL; localhost fixed and tested, browser validation pending**

Implementation branch: `feat/phase1-core`, based on refreshed `main` at `ba7a6bb`.
Review: draft PR [#6](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/6).
See `docs/BUILD_STATUS.md` for measured results; provider requests are pending by user instruction.

## Hardware baseline
- Windows 11
- AMD Ryzen 7 4800H
- 64 GB RAM
- NVIDIA GTX 1650 Ti, 4 GB VRAM
- 256 GB NVMe
- approximately 50 GB free at project start
- Docker Desktop + WSL2 expected

## Canonical architecture
Open WebUI / coding agent -> Agent Controller -> OpenViking + Graphify + Git/GitHub -> LiteLLM -> OpenAI / Gemini / Claude / OmniRoute / optional Ollama.

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

Browser validation is pending: this session's browser tool reports Edge
unavailable, and its in-app browser fails to attach. HTTP tests do not establish
browser rendering. Phase 1 stays PARTIAL until browser acceptance passes.

## Implemented, not fully validated
- Pinned core Compose, persistent volumes, health checks, local-only publication.
- Guarded preflight/startup, random local secrets, restricted WebUI inference key.
- OpenAI/Gemini configuration with independently configurable model IDs/aliases.
- Empty-provider startup tested; cloud inference intentionally pending by user instruction.
- Latest storage sample: 59.11 GiB free on C:; core image sizes sum to 2.68 GiB.

## Next bounded action
Complete actual browser validation using an available browser tool or the
requested alternate headless Edge method. Then configure and validate providers
only when requested. Budgets, recovery, Kubernetes and optional modules remain
later phases. NAT applies to all WSL2 distributions; direct WSL LAN access and
Linux-to-Windows localhost semantics change. All 31 running workload identities
and six volumes were preserved; unrelated applications were not functionally tested.
No reboot, firewall changes or data deletion was performed.

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
