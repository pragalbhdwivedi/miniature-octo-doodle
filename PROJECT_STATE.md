# Project State

## Project
`pragalbhdwivedi/miniature-octo-doodle`

## Purpose
Modular local/cloud AI coding platform with a single AI gateway, browser UI, optional agent memory/code graph, and future multi-agent orchestration.

## Current phase
**Phases 1-2: COMPLETE and merged, with Jev disabled. Phase 3: local backup,
restore and clean container rebuild COMPLETE for the tested same-host scope.
Phase 4: COMPLETE for local developer Kubernetes validation.
Phase 5: PARTIAL. Live Windows data/credentials/ledger migrated to the Linux VM;
API/provider/browser acceptance passed. Encrypted off-VM copy and authenticated
readback passed. Separate clean-host recovery and reverse cutover remain pending.
Phase 6: COMPLETE for the bounded operator-run worker scope. Offline isolation,
gateway coding, per-run budgets and live reviewed draft-PR publishing passed.
Fine-grained token repository restriction remains an operator provisioning
responsibility; API success does not independently prove absence of broader scope.
Phase 7: STARTED / PARTIAL. Read-only repository planner implemented and tested;
unprivileged planning remains read-only. Dedicated PostgreSQL claims/audit and
operator-only exact-request dispatch are deployed and live-tested. The committed
zero-spend task passed; simulated completion-write outage retained the claim and
reconciliation recovered the result without re-execution.
Independent fresh-context review, one bounded repair and operator-gated draft
publication are deployed and live-tested: stricter tests/reviewer rejected the
synthetic defect, one repair passed new tests/review, and exact-artifact approval
created draft PR #23. Aggregate conservative debit $0.869440 under $1; duplicate
publication denied. Phase7 remains PARTIAL for end-to-end AADI acceptance.**

**Phase 8: STARTED / PARTIAL. Schema-3 exact-action Telegram approval state,
signed callback validation and one-shot manual poll/request CLIs are implemented.
Windows/WSL fixture tests and real PostgreSQL test-copy transitions passed.
PR #25 merged; VM9125 controller source now matches main and production schema 3
was applied after a verified protected backup. Prior run history, gateway ledger
and core health passed readback. On 2026-10-01, the owner-provided bot token and
private `/start` update identified one approved numeric user/chat. A root-only
configuration was copied to VM9125 and a one-time Telegram `sendMessage` from the
VM received API acknowledgment for that chat, and the owner confirmed phone
receipt. On 2026-10-01, production dispatch activated the protected Telegram gate.
A real private callback passed identity/MAC checks and was recorded, but the first
approval expired before publication. No PR was created from it. A fresh synthetic
run then passed offline execution and independent review. After the GitHub quota
reset, the owner approved its private-chat button and the exact decision was
consumed to create [draft PR #32](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/32).
The bounded Telegram-gated draft-publication path is live validated. Broader
Phase 8 notifications and choose/pause/resume actions remain unimplemented.**

**Phase 9: STARTED / PARTIAL.** Graphify `graphifyy==0.9.72` runs as an
unprivileged, code-only index of this public repository on VM9125. At main SHA
`8c57104bcf7d1386bf5f0075a0febaff9e526a22`, the latest rebuild yielded
580 nodes and 1,191 edges after adding the optional SQL parser. A same-run
extract/provenance gate, bounded query and read-only exact-plan graph preview
passed. The graph has no dispatch or publication authority. OpenViking v0.4.22
is installed separately on VM9125 with a VM-local embedding model, laptop-hosted
text VLM and loopback-only API. Its authenticated public-document vector ingest
and search passed in both `vectors_only` and `semantic_and_vectors` modes.
Private-source permissions, automatic controller consumption, compaction quality
and clean-host memory recovery were pending at installation. On 1 October a
15-minute VM timer was enabled to refresh only three public documents at the
exact current GitHub main SHA. Live sync and three bounded content hits passed.
The operator controller's optional advisory lookup returned three live hits and
denied a mismatched SHA; fixture tests cover prompt inclusion and Git-only
fallback. A paid reviewer run with retrieved context, private memory permissions,
WebUI chat capture and clean-host memory recovery remain pending. See
[Graphify](docs/GRAPHIFY.md), [OpenViking](docs/OPENVIKING.md) and
[build evidence](docs/BUILD_STATUS.md).

**Optional laptop local-model lane: PARTIAL.** Native Windows Ollama 0.35.0
retains Qwen3 4B instruct and now the owner-authorized 15 GB Devstral Small 2
coding model plus Qwen3 4B thinking supervisor. Cloud use is disabled and the
laptop listener remains loopback-only. A scheduled outbound SSH reverse tunnel
and gateway-only VM bridge let the existing LiteLLM/Open WebUI app advertise
`local-coding` and `local-supervisor`. Both passed synthetic WebUI chat requests,
and the owner confirmed both models worked from the phone;
an outage produced only an Ollama failure, no cloud fallback or USD debit.
An authenticated long local-coding stream later completed with a final SSE
marker and an Ollama `stream_completed` ledger outcome.
C: had 17.76 GiB free after download, but later measurements were 7.37 and
12.93 GiB,
**below the critical 15-GiB floor**; optional laptop installs/downloads are
stopped pending recovery of free space. The
bounded PC proposal agent completed one clean public-source test with a
Git-checkable patch and advisory Qwen review, without edits or publication.
Production coding quality and next-logon/reboot recovery remain open. Windows trusted roots contain the internal CA;
Edge opens the HTTPS sign-in page without a warning, while authenticated HTTPS
model selection in Edge is still pending. See [local model](docs/LOCAL_MODEL.md).

AADI Phase 7 gate: refreshed private `pragalbhdwivedi/aadi` `Dev` at
`cf5de5a465a71e83998488b9c59c1951241fdac8`; controller integration PR #23
is open. The existing public-only worker and cloud public/synthetic-text policy
cannot ingest private AADI source. Its adapter remains disabled pending a scoped
private-source/data-path design and an approved bounded AADI task.

PR [#6](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/6) was reviewed
and merged at `301e3a13a021fedfaa8418759661736fe784fb33`.
Phase 2 [PR #8](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/8)
merged at `c76406927ae1110e6023f4195c7d4b81c360cd55`, incorporating PR #7's design.
Phase 3 [PR #9](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/9)
merged at `3cf3b6db7b1005c1be4eb541151d0e6fc1d5cdc9`.
Phase 4 PR #10, Phase 5 PR #12 (including roadmap PR #11), and dashboard PR #14
are merged. Historical design PR #7 was closed as superseded. Phase 6 PR #13
is merged after live publishing acceptance in draft test PR #16. Phase 7's read-only
planner was merged in PR #15, durable dispatch in PR #18 and review/repair/draft
publication in PR #22. See [dispatch operations](docs/CONTROLLER_DISPATCH.md)
and [review operations](docs/CONTROLLER_REVIEW.md).
See `docs/BUILD_STATUS.md` for measured results and remaining Phase 5 gates.

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
Outside OpenVPN/phone RDP were subsequently owner-confirmed in PR #14;
phone browser trust and complete client/reboot acceptance remain pending. See [SSH access](docs/SSH_BASTION.md).

The selected Ubuntu VM now owns the live Compose gateway. Existing account/chat
volumes, scoped/provider credentials and the US$100 UTC-month allowance were
retained. Windows is frozen, restart disabled, with a local start guard; do not
restart its stale ledger. The earlier fresh zero-spend VM project is retained
stopped. WebUI is `http://localhost:3180` through the SSH tunnel, using the existing
Windows administrator credentials. Protected login location is in local VM notes.

Recovery still requires a separate approved clean machine, and reverse cutover
using current data/ledger rather than the old Windows snapshot. An encrypted copy
has been placed in protected laptop storage and read back with authentication;
this does not prove recovery after loss of the VM/host. No separate recovery target
has been named, so the earlier clean-machine pause remains respected.
See [Linux operations](docs/LINUX_CORE.md) and [Phase 5 gates](docs/DEBIAN_CONTROL_PLANE.md).

On 2026-09-30 the user authorized the next phase. The first Phase 6 milestone
adds an operator-only broker, allowlisted public repository refresh, offline
non-root disposable worker, bounded shell/tests and reviewable artifacts.
The worker and controller foundation are merged on main.
Gateway-backed one-turn coding and per-run cost reservations now pass live
acceptance. The external publisher created draft PR #16 from a fresh main snapshot;
exact file/parent and unchanged main were verified with no provider calls. See [worker operations](docs/WORKER.md).

The local k3d deployment remains isolated developer validation: no provider keys,
zero spending, fresh data and Jev disabled. It does not replace the Compose gateway.

Live Jev integration/evaluation/calibration remains deferred under ADR 0008.
Only the explicitly requested NPM and Phase 6 worker image have been added;
no local model weights or optional context modules. See [Kubernetes operations](docs/KUBERNETES.md).

## Phase 5 runtime checkpoint (2026-09-30)
- Direct Windows/WSL and bastion SSH, target admission, Docker/core health,
  authentication, scoped-key restrictions and eight aliases passed.
- Fresh zero-spend startup, recreation/reboot and same-VM restore passed first.
  Unprivileged systemd proxies supply loopback HTTP without a Docker socket.
- Windows cold snapshots restored into independent Linux volumes, matching every
  file's bytes/mode/owner. PostgreSQL/SQLite integrity, restored account/key,
  synthetic routing/fallback/concurrency and unchanged budget ledger passed.
- Frozen-source handoff and pre-activation rollback were tested. Final cutover
  retained the existing US$2.875240 debit; live probes and browser checks advanced
  conservative admission debits to US$3.569700, with 21 attempts and zero active
  requests. The US$100 UTC-month limit is unchanged; these are not vendor charges.
- Both cloud providers passed HTTP 200/exact-response tests and Edge rendered
  their responses in a temporary chat. UI/database networks remain internal;
  only LiteLLM has provider egress, with no published container ports.
- Private credentials/data remain root-owned outside Git/sync. Jev, optional
  components, workers/controller and model downloads remain disabled/uninstalled.
- Live VM cold backup/resume passed in 88.53 seconds. An authenticated encrypted
  95,887,460-byte copy is retained on the laptop; ciphertext hash and decrypted
  internal manifest passed after readback. An isolated restore from the returned
  copy passed all volume, database, login/key and synthetic checks in 143.84s.
  Clean-host recovery remains unvalidated.
- Live reboot initially exposed changed Docker IPs and stale loopback proxies.
  Added a selected-project boot refresh after all three services are healthy.
  Repeat reboot passed after refresh completion: HTTP/auth/model discovery,
  Windows/WSL SSH and tunnel restored automatically; ledger unchanged, 50.514 GiB free.
- All 49 unit tests pass on VM and WSL. Windows passes 44 with five dependency/POSIX
  skips. Repository YAML/security and diff checks pass.

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
  The 2026-09-30 runtime checkpoint above supersedes that status. Later migration/retention results are recorded above. See BUILD_STATUS for limits.

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
- Ollama/local LLM (Windows laptop evaluation installed; gateway integration pending)
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

## Requested internal ingress (30 September 2026)
Nginx Proxy Manager 2.16.0 is deployed on the existing VM by explicit request.
All services use `*.aadi.dgoi.local`; GatewayAI uses `https://ai.aadi.dgoi.local`.
Omada requires an explicit DNS record per service. DNS and a stable LAN TCP
80/443 destination rule are saved; NPM admin port 81 stays loopback-only.
Private wildcard TLS, strict HTTPS sign-in, eight aliases, a streamed response
and blocked LAN administration/backend ports passed. WSL trusts the private CA;
Windows browser trust remains blocked on local confirmation/elevated import. The existing ledger is
retained: $3.612410 conservative September debit, 22 attempts, zero active after
the synthetic ingress probe; $100 UTC-month ceiling unchanged. An encrypted NPM
backup and isolated restore passed; the restored copy is stopped. Reboot passed
with four healthy live containers, working HTTPS and unchanged ledger. Browser
and all-VLAN/external-VPN acceptance remain open. See docs/INGRESS.md.

## Service directory and remote access - 30 September 2026

DEPLOYED: password-free `dash.aadi.dgoi.local` directory and separate HRMS/console
HTTPS hostnames reuse existing ingress. Preserved-account login, protected reads,
logout and origin/anonymous denial passed. No image pull, migration or password
reset. User confirmed external OpenVPN and phone RDP login. WireGuard server routes
corrected; client setup/handshake pending. Phone CA/DNS and tunnel reboot/logon
acceptance remain open. See [dashboard operation](docs/DASHBOARD.md) and
[remote-access evidence](docs/REMOTE_ACCESS_CHECK.md).

## Phase 7 first milestone - 30 September 2026

Read-only CLI refreshes the approved public gateway repository, records exact SHA,
recent commits, issue/PR inventory and governance hashes, and checks a committed
task manifest against issue ownership, explicit ready label and dependencies.
It emits a zero-budget worker plan for operator review; it cannot execute jobs,
publish, merge or call a model. AADI remains disabled. Live unprivileged VM run
fetched main and correctly recorded `no_committed_task_manifest`; synthetic tests
cover selection/denial paths. PostgreSQL persistence, dispatch, independent review,
repair and exact-run approval integration are not implemented. See controller docs.
