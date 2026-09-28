# Build Status

Status values: COMPLETE, PARTIAL, NOT STARTED, BLOCKED.

| Subsystem | Status | Evidence |
|---|---|---|
| Repository bootstrap | COMPLETE | Initial source-of-truth files committed |
| Preflight tooling | COMPLETE | Target-machine checks passed 2026-09-29; details below |
| Docker Compose core | PARTIAL | Three services healthy; internal tests pass; Windows/browser access blocked |
| PostgreSQL | COMPLETE | 16.15 Alpine healthy; SQL query confirms LiteLLM schema; state survives restart/recreation |
| LiteLLM | PARTIAL | 1.103.0 healthy; DB/auth/key controls pass internally; host endpoint blocked |
| Open WebUI | PARTIAL | 0.11.4 slim healthy; internal login and gateway discovery pass; browser blocked |
| Host/browser access | BLOCKED | HTTP and Edge timeout on 127.0.0.1:3000/4000 before/after authorized Desktop restart |
| OpenAI provider | PARTIAL | Configurable template/render tests pass; no key or inference test by instruction |
| Gemini provider | PARTIAL | Configurable template/render tests pass; no key or inference test by instruction |
| Routing / fallback | NOT STARTED | |
| Budget controls | NOT STARTED | |
| Backup / restore | NOT STARTED | |
| Kubernetes base | NOT STARTED | |
| Kubernetes Ingress | NOT STARTED | |
| Ollama | NOT STARTED | Optional |
| Local model | NOT STARTED | Optional |
| OmniRoute | NOT STARTED | Optional |
| OpenViking | NOT STARTED | Optional |
| Graphify | NOT STARTED | Optional |
| Coding agent | NOT STARTED | Optional |
| Agent Controller | NOT STARTED | Planned |

A documented architecture is not implementation evidence.

## Milestone 0 - 2026-09-29 (Asia/Calcutta)

- Refreshed `main`: `ba7a6bb`; reviewed instructions, docs, issues #1-#5; no PRs returned.
- Windows 11 Enterprise 10.0.26200; Ryzen 7 4800H; 63.37 GiB RAM.
- Docker Desktop engine 29.8.0, Compose 5.5.1, local `desktop-linux` context.
- WSL 2.7.14.0; Ubuntu and docker-desktop running in version 2; kernel 6.18.33.2.
- GTX 1650 Ti, 4096 MiB, driver 581.57: Windows, Ubuntu and Docker probes passed.
  Docker probe used an existing image with `--pull never --network none --gpus all`.
- Initial C: free 60.53 GiB; immediately before pulls 60.57 GiB. No images/models pulled in preflight.
- Docker baseline: 15 images / 3.982 GB, 28 running containers, 4 volumes / 143.8 MB, no build cache.
- Docker VHDX: `%LOCALAPPDATA%/Docker/wsl/disk/docker_data.vhdx`, 13.02 GiB file length;
  main VHDX 0.09 GiB. WSL2 backend confirmed in Desktop settings. Storage not relocated.
- Registry manifests verified: PostgreSQL 16.15 Alpine, LiteLLM database 1.103.0,
  Open WebUI 0.11.4 slim. Total compressed layers approximately 0.636 GiB;
  conservative install reserve 12 GiB, projected remaining 48.57 GiB.
- Failure found: bootstrap preflight did not propagate daemon failures or enforce projected reserve;
  replaced with fail-closed checks. Candidate LiteLLM `-stable` version tag did not exist;
  resolved the published `v1.103.0` database image and pinned its digest.
- Validation: revised preflight, empty-provider config generation, Compose config check passed.
- Next: start and test PostgreSQL/LiteLLM, then Open WebUI. Cloud calls remain pending by instruction.

## Milestone 1 - PostgreSQL and LiteLLM (2026-09-29)

- Implemented digest-pinned Compose, isolated DB network, persistent gateway state,
  localhost port 4000, health dependencies, and generated secrets kept outside Git.
- Tested `manage.ps1 start -Stage gateway`: both containers healthy. SQL query
  confirms LiteLLM public tables. Internal liveness returns 200, unauthenticated
  model listing 401, authenticated listing 200 with zero configured models.
- Gateway image 1,663,638,401 bytes; PostgreSQL image 419,072,015 bytes.
  Docker image total after this milestone 6.066 GB (baseline 3.982 GB);
  volumes 196.4 MB (baseline 143.8 MB). Host free sample 58.55 GiB; background
  activity means host delta is not exclusively attributable to this deployment.
- Failed: Windows localhost port 4000 timed out although container checks passed.
  Continue only internal core validation; keep host-access status blocked.

## Milestone 2 - Open WebUI (2026-09-29)

- Deployed slim image, persistent SQLite UI volume, local admin bootstrap and
  a separate gateway key restricted to model listing/chat completion endpoints.
  Provider, database and master secrets are absent from the UI environment.
- All three containers healthy. Internal tests passed: WebUI health 200, admin
  sign-in 200, gateway model listing 200, UI model discovery 200, gateway key
  administration denied 403. Both model lists correctly empty with no provider keys.
- Validated all published bindings are 127.0.0.1, PostgreSQL has no host binding,
  no privileged container/socket/host-root mount, and optional integrations disabled.
- Found and fixed: explicit unavailable aliases appeared in virtual-key model
  discovery, and WebUI's default arena entry advertised an extra model. The
  inference key now follows registered proxy models and arena is disabled.
- WebUI image 799,737,171 bytes. Three core image sizes sum to 2,882,447,587 bytes
  (2.68 GiB; shared layers/physical allocation may differ). Pre-restart Docker
  totals: 18 images / 6.870 GB, 6 volumes / 214.2 MB, 31 running containers.
  Free C: sample 59.49 GiB. No models or optional service images pulled by this project.
- Browser/host tests FAILED on both core ports. Edge reported
  `net::ERR_CONNECTION_TIMED_OUT`; curl returned 000/timeouts. Docker reported
  the forwards but Windows listener checks found no listener on 3000/4000.
- User subsequently authorized Docker Desktop restart; performed at approximately
  03:17 IST. Three core services and 28 existing workloads returned. All original
  volumes remained. Kubernetes-managed containers naturally received new IDs.
  No full functional claim is made for unrelated applications.
- Restart did NOT repair HTTP/browser access. Docker logs also show its existing
  Kubernetes localhost API timing out. WSL mirrored mode observed; cause unresolved.
  No firewall weakening, network-mode change, Windows reboot or volume deletion.
- Repeated guarded startup with forced gateway recreation succeeded and preserved
  the WebUI key, admin login and database. Internal smoke tests passed again.
  This is restart persistence evidence, not backup/restore or clean rebuild proof.
- Post-restart host sample: 59.21 GiB free; Docker 19 images / 7.464 GB,
  55 total containers / 31 running, 6 volumes / 214.2 MB. Existing Kubernetes
  restart activity changed global totals; do not attribute the extra image/stopped
  containers to the three-image core. VHDX file lengths remained 13.02/0.09 GiB.
- Next: resolve host forwarding and repeat browser validation before marking COMPLETE.

## Milestone 3 - provider templates (2026-09-29)

- OpenAI/Gemini identifiers checked against official docs; variables and aliases
  editable in local `.env`. Renderer omits absent providers and never copies key
  values into generated config. Core starts with neither credential.
- Offline fixture tests passed for none/OpenAI/Gemini/both providers, overwrite
  refusal, forbidden cloud `local-private`, duplicate aliases, wildcard models,
  projected/critical disk rejection, native failure propagation and env restoration.
- Static YAML/security contract and Compose syntax passed locally. Live provider
  requests intentionally NOT RUN at the user's direction; no billing/access claim.
- Provider-test disk consumption: no provider requests, downloads or runtime data.
  Local Python/PyYAML validation environment is ignored; reflected in host samples.
- Phase 2 budgets/routing/fallbacks, Phase 3 recovery, Kubernetes and optional modules
  remain NOT STARTED for this project.
