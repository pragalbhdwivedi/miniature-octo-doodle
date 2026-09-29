# Build Status

Status values: COMPLETE, PARTIAL, NOT STARTED, BLOCKED, DEFERRED.

| Subsystem | Status | Evidence |
|---|---|---|
| Repository bootstrap | COMPLETE | Initial source-of-truth files committed |
| Preflight tooling | COMPLETE | Target-machine checks passed 2026-09-29; details below |
| Docker Compose core | COMPLETE | Three services healthy; internal, Windows, live provider and Edge browser tests pass |
| PostgreSQL | COMPLETE | 16.15 Alpine healthy; SQL query confirms LiteLLM schema; state survives restart/recreation |
| LiteLLM core | COMPLETE | 1.103.0 healthy; DB/auth/key controls, live inference and policy callback execution pass |
| Open WebUI | COMPLETE | 0.11.4 slim healthy; login, model selection and rendered responses from both providers pass in Edge |
| Host HTTP access | COMPLETE | WSL NAT restored both 127.0.0.1 and localhost on 3000/4000; full smoke test passed |
| Browser acceptance | COMPLETE | Edge sign-in and temporary chat responses passed 2026-09-29; no alternate browser method needed |
| OpenAI provider | COMPLETE | gpt-5.4-mini via openai-chat: live gateway HTTP 200/exact OK and browser response passed |
| Gemini provider | COMPLETE | gemini-3.1-flash-lite via gemini-chat: live gateway HTTP 200/exact OK and browser response passed |
| Deterministic policy layer | COMPLETE | Local text-only scope; declared classification, provider restrictions, tools/approval denies tested before upstream execution |
| TypeSafe Jev decision layer | DEFERRED | Explicitly disabled per user instruction/ADR 0008; offline contracts and activation rejection tested; live integration/calibration unvalidated |
| Routing / fallback | COMPLETE | Eight cloud aliases; one approved fallback; native 503/429 tests and live capability/browser validation |
| Budget controls | COMPLETE | US$100/month UTC conservative admission ledger; atomic race, zero/exhausted budget, concurrency, rollover and restart persistence tested |
| Backup / restore | COMPLETE | Same-host cold backup and isolated restore tested 2026-09-29; off-machine/cutover limits below |
| Clean container rebuild | COMPLETE | Fresh archived-source directory, three new volumes and three new containers validated; existing pinned images reused |
| Kubernetes developer validation (Phase 4) | COMPLETE | Revised PR #11 scope: dedicated k3d core, pod/PVC persistence, API/browser, isolation and synthetic policy pass; no live migration claim |
| Kubernetes Ingress | COMPLETE | Local zero-spend scope: HTTP/auth, Edge sign-in, eight aliases, model selection and rendered budget denial passed; no live provider/cutover claim |
| Linux control-plane VM (Phase 5) | PARTIAL | User-selected Ubuntu template cloned; guest/reboot/SSH checks pass through temporary isolated path; durable routed SSH and Docker/application deployment pending |
| Ollama | NOT STARTED | Optional |
| Local model | NOT STARTED | Optional |
| OmniRoute | NOT STARTED | Optional |
| OpenViking | NOT STARTED | Optional |
| Graphify | NOT STARTED | Optional |
| Isolated coding worker | NOT STARTED | Phase 6, before context/local models |
| Agent Controller | NOT STARTED | Phase 7; independent of AADI production |
| Telegram approvals | NOT STARTED | Phase 8; WhatsApp excluded |

A documented architecture is not implementation evidence.

## User-selected Proxmox VM creation - 2026-09-29

The user explicitly requested a VM from template 9001. Refreshed GitHub main is
still `3cf3b6d`; implementation continues on draft PR #12, based on PR #10 and
including PR #11's roadmap. Live template inspection identified Ubuntu 24.04,
so [ADR 0012](adr/0012-template-9001-ubuntu-target.md) records the explicit change
from the earlier Debian-only target. Private addressing, keys and raw operator
evidence remain outside this public repository.

- **CREATED:** independent full QCOW2 clone, 4 vCPU / 8192 MiB / 60 GiB, on the
  selected cluster node and existing shared storage. No backing file; new MAC,
  SMBIOS UUID and generation identity. Existing VNet/firewall flag preserved;
  no extra guest VLAN tag. Automatic host-boot startup enabled.
- **PASS:** guest Ubuntu 24.04.5, expected hostname/address, 4 visible CPUs,
  7.755 GiB RAM, expanded root filesystem and 55.20 GiB free after installation.
  DNS and outbound HTTPS worked. No Docker/Compose or application service exists.
- **PASS:** existing Windows and WSL RSA public keys authenticate as the template
  administrator, including `sudo -n true`. Existing template authorized keys were
  retained. No password was reset and no private SSH key was copied.
- **Access limit:** direct routed SSH times out from the current laptop network
  and Proxmox management network. Same-VNet ping/SSH works. A temporary isolated
  network namespace on the target node supplied the SSH verification path. Its
  address was checked against guest configurations and failed ARP resolution before
  use. Target MAC matched Proxmox configuration; observed host key was pinned and
  subsequently confirmed through the guest agent. The namespace/veth were removed
  and absence checked. No router ACL, host routing or firewall policy was changed.
  This does **not** establish durable administrator access.
- **Fixed on this clone only:** template did not contain `qemu-guest-agent`.
  Installed the Ubuntu package and `liburing2` (413 kB downloaded, approximately
  1.3 MB package footprint). Guest-agent ping/exec now pass. Template unchanged.
- **PASS:** controlled guest reboot changed boot ID; cloud-init completed, guest
  agent activated automatically, disk/resources persisted, and both Windows/WSL
  SSH and sudo passed again. This is guest reboot evidence, not Proxmox host reboot,
  power-loss, application persistence or recovery evidence.
- **PASS:** all 26 pre-existing guests retained their configuration hashes,
  node identity and running/stopped status. No existing VM/volume was replaced.
- **PASS:** 35 Windows unit tests, including native Ubuntu admission and WSL/
  container rejection; all ten preflight tests also passed under WSL. Repository
  YAML/security checks passed. Real VM preflight passes OS, VM, CPU/RAM, runtime
  disk reserve and free application ports. Overall BLOCKED is expected because
  Docker/Compose and their storage/service checks remain unavailable.
- **Storage:** full clone reserved 60 GiB virtual capacity; final shared-storage
  allocation reports 974,664,192 bytes root disk plus 30,208 bytes cloud-init.
  Shared storage has 4,256,244,957,184 bytes available. These sparse/storage reports
  are not backup capacity guarantees. Local C: sample 41.25 GiB free. No AI images,
  model weights, provider credentials or live application data were transferred.
- **Failures/limits:** clone progress reached 100% before its final task exit;
  configuration lookup before completion correctly failed without mutation.
  The local helper then rejected mixed progress/JSON output; independent task
  status proved `OK`, and cloning was not retried. Configuration readback normalized
  Proxmox's string-valued memory field before proceeding. Initial cloud-init
  reported a deprecated `user` field with no errors; after reboot status was done.
- **Next:** establish durable administrator SSH access, install the core Linux
  Docker prerequisites, then implement and validate the zero-spend application
  deployment. Phase 5 application/browser/backup/clean-host recovery remain pending.


## Updated roadmap, Phase 4 closeout and Phase 5 preparation - 2026-09-29

Refreshed main: `3cf3b6db7b1005c1be4eb541151d0e6fc1d5cdc9`.
Phase 4 open PR #10: `1130fcf23223b3a7a85049be0ea345e1c91b60ee`.
User roadmap open PR #11: `223bb00a9b57efed54a90bee9cffa9012cf03364`.
Both histories are integrated for review on `feat/phase5-debian-foundation`;
main and the existing PR branches are unchanged.

- **Scope reconciliation:** PR #11 explicitly makes Phase 4 local developer
  validation only. Existing browser/PVC evidence plus the fresh runtime suite
  satisfy that scope, so Phase 4 is COMPLETE. This supersedes the older PARTIAL
  wording below; live migration was not performed or silently marked tested.
- **PASS, current runtime:** `scripts/kubernetes.ps1 test` passed internal admin
  login, restricted-key administration denial, eight aliases and zero-budget
  rejection; HTTP Ingress/auth/model discovery through both localhost names;
  gateway-to-DB allowance, UI-to-DB and external TCP denial; native synthetic
  primary/503/429 fallback, provider/private/tool/override policy, streaming,
  concurrency and exhausted budget. No provider request or deployment change.
- **Prior measured evidence retained:** the browser screenshot and all-three-pod
  recreation with Compose stopped were not repeated; their configuration has not
  changed. Those results remain recorded in the entries below.
- **Implemented:** read-only `scripts/debian-preflight.py` and
  [Debian acceptance plan](DEBIAN_CONTROL_PLANE.md). No installer, Linux secret
  generator, startup wrapper, controller runtime or Linux backup implementation
  is claimed. Main continues to contain only the merged Phase 1-3 implementation.
- **PASS:** 34 Python unit tests on Windows, including nine Debian preflight
  guard tests; those nine also passed under WSL Ubuntu. Repository safety/YAML
  checks and configuration/storage regressions passed. Native Windows and WSL
  Ubuntu 24.04 preflight runs both
  exited 1 with BLOCKED as intended, before any Docker request. Fixture acceptance
  is not Debian-machine evidence.
- **Storage:** C: 41.33 GiB before work, 41.30 GiB after tests (concurrent host
  activity included). Docker inventory: 40 images / 18.5 GB,
  67 containers / 34 running, 21 volumes / 4.287 GB and 10.11 GB build cache.
  Only small source/documentation files added; no image/model install, runtime
  volumes, destructive cleanup, target connection or live-data migration.
- **Pending:** VM identity/SSH access, actual Debian preflight, Linux deployment
  and secret permissions, browser/provider acceptance, reboot and recovery.
  Off-machine backups/new-machine recovery retain their explicit unvalidated
  status and the user's prior pause. No new remote web address/login exists.
- **Next:** identify the dedicated VM, run read-only target admission and implement
  the Linux fresh zero-spend deployment path before any approved live cutover.

The later order is isolated worker, controller, Telegram-only approvals, then
context and advanced orchestration. Optional models remain uninstalled; Jev stays
disabled. See [ADR 0011](adr/0011-debian-controller-progression.md).

## Phase 4 browser acceptance follow-up - 2026-09-29

Runtime/source baseline: `17b96db28ba3d88c501ec2fac5a518a1dc405d1e`, open PR #10.
Documentation/evidence follow-up only; no deployment configuration changed.

- **PASS**: Edge opened `http://localhost:3080`, displayed the sign-in page and
  signed in with the existing test administrator. The password stayed out of
  screenshots, Git and chat. Release notes were dismissed; no settings changed.
- **PASS**: picker displayed all eight aliases: `openai-chat`, `gemini-chat`,
  `coding-fast`, `coding-standard`, `coding-hard`, `architecture`, `review`,
  `documentation`. No `local-private` or optional provider appeared.
- **PASS**: temporary chat selected `coding-standard`; the synthetic message
  "Synthetic Phase 4 browser acceptance check. Reply OK." rendered the expected
  `policy: monthly_budget_exhausted` result. This is correct for budget zero.
- **PASS**: post-browser gateway inspection confirmed zero admission debit, zero
  provider attempts, zero active requests, empty OpenAI/Gemini credentials and
  explicitly disabled Jev. All three Kubernetes Deployments remained 1/1 ready.
- Saved [browser screenshot](evidence/phase4-browser-budget-denial.png), 31,694 bytes,
  SHA-256 `2e58090090df8361cf6883693d7b4ac969a8bde6b0c9becf949758abf9c75503`.
  Only synthetic test text and the denial are visible. The temporary chat was not saved.
- The earlier browser blocker did not recur using the connected Edge browser this
  session. No security bypass, alternate headless browser, network change, image
  pull, service restart or live provider request was needed. Root cause remains unknown.
- Free C: 41.37 GiB, above warning/critical thresholds. No runtime installation;
  only small documentation and screenshot artifacts were added. Host free-space
  changes since the prior sample include concurrent activity.
- Local zero-spend browser acceptance and Ingress are COMPLETE. Phase 4 remains
  PARTIAL for live provider/data migration; this is not provider response validation,
  production cutover, Kubernetes backup or separate-machine recovery evidence.
- Next: choose the intended target and migration scope; preserve/reconcile existing
  data and monthly budget history before any live activation. Off-machine and
  new-machine recovery remain pending under the prior pause.

## Phase 3 closeout and Phase 4 start - 2026-09-29

Source: main `3cf3b6db7b1005c1be4eb541151d0e6fc1d5cdc9` (merged PR #9);
implementation branch `feat/phase4-kubernetes`.

### Phase 3 closeout

- Accepted same-host backup/restore/rebuild scope is complete and merged.
- Reverified `backup-20260929T134402Z`: SHA-256 inventory and archive safety pass.
  An initial verify command using only its directory name was rejected before
  mutation; rerunning with the documented full protected path passed.
- Existing restore evidence below remains the accepted drill. No off-machine copy,
  new-machine restore, reboot or cutover occurred. The user's new-machine pause
  remains; a local k3d instance does not validate a separate recovery host.

### Implemented and deployed

- Checksum-verified Windows k3d 5.9.0, dedicated `gatewayai` cluster with one
  k3s 1.35.5 server, 6 GiB memory limit, secrets encryption enabled; metrics-server
  disabled. k3s index digest `2074403abe1bded11ef3dde09d457e13be8e0b64c218b1c4f8269b4565cfbc65`.
- Three existing digest-pinned core images deployed into fresh PVCs; all three
  Deployments ready, all PVCs bound. Generated ConfigMaps use tracked code/policy;
  random test secrets and separate kubeconfig stay in ACL-protected physical AppData.
- WebUI Ingress on 127.0.0.1:3080; API on 127.0.0.1:6550. Port bindings checked.
  Existing `docker-desktop` context preserved. Only ClusterIP application services.
- Blank provider keys, budget zero, Jev disabled; no optional module/model downloaded.
  Core pods have no service-account token, host path, Docker socket or privilege escalation.
  The k3d infrastructure node itself requires Docker privilege; no agent receives it.

### Tested results

- Server dry-run succeeded before application deployment.
- Internal admin login, scoped-key use and key-administration denial, eight aliases,
  zero-budget inference rejection: PASS.
- Ingress health, admin sign-in and model discovery using both `127.0.0.1` and
  `localhost`: PASS. No cloud completion requested.
- Gateway-to-PostgreSQL TCP allowed, WebUI-to-PostgreSQL blocked; gateway and WebUI
  external TCP connection to 1.1.1.1:443 blocked: PASS.
- Native synthetic primary execution, 503/429 fallback, provider restriction,
  local/private denial, override/tool denial, streaming, four concurrent admissions
  and fifth denial, exhausted budget: PASS inside Kubernetes with a temporary ledger.
- Stopped only the three Compose core containers; recreated all three Kubernetes
  pods; repeated the full tests with Compose still stopped: PASS. All PVC UIDs
  unchanged; admin account and scoped key remained usable. Compose resumed healthy.
- 25 Python unit tests, configuration/storage guard regressions, repository safety
  and full original Compose HTTP/auth smoke tests: PASS.
- All 31 original running container identities preserved; three k3d containers
  added. Original admission debit unchanged at 2.875240 USD, allowance 100 USD/month,
  zero active requests. Unrelated apps were not functionally retested.

### Failures and limits

- First k3d creation used `--no-image-volume` and failed before any node started
  with `failed to ensure tools node ... No nodes found`. Only the two confirmed
  never-started nodes and their empty network were removed. Standard image-volume
  retry succeeded. No existing persistent data or unrelated resource was deleted.
  Successful retry used the version tag whose local image matches the above digest;
  the committed bootstrap pins that digest. Fresh bootstrap was not repeated after
  that pin, to preserve the validated cluster and avoid another image copy.
- Browser connector reported `ERR_BLOCKED_BY_CLIENT`. Native Computer Use stopped
  because it could not determine the current browser URL for policy checks. No
  further browser automation was attempted. Browser rendering/chat remain unvalidated.
- No live Kubernetes provider inference, Compose-data migration, Kubernetes PVC
  backup, whole-cluster reboot, off-machine recovery, LAN/TLS exposure or cutover.

### Storage and next action

- Before: 45.39 GiB free; after: 41.30 GiB (4.09 GiB host delta, includes concurrent
  activity). Above 25 GiB warning / 15 GiB critical. Eight GiB reserved before cluster
  images; no model weights. Core image copies inside k3s containerd are expected.
- Global Docker: images 37 / 18.02 GB -> 40 / 18.50 GB; volumes 16 / 425.7 MB ->
  21 / about 4.28 GB; containers 64 / 31 running -> 67 / 34 running. Build cache
  unchanged at 10.11 GB. No prune or compaction. Cluster and fresh PVCs retained.
- Next: complete browser acceptance, select intended target and migration scope,
  then plan secure data/ledger migration and bounded live provider validation.
  Separate-machine recovery still needs an identified/authorized target.

## PR #9 review follow-up - 2026-09-29

- Confirmed the automated P2 finding: edited `.env`/rendered configuration could
  be combined with databases from differently configured running containers.
- Added exact effective environment and mount checks, conservative bound-file
  freshness checks, PostgreSQL TCP password verification and source fingerprint
  checks before/during capture. Configuration drift fails without exposing secrets.
- All 22 offline tests passed, including changed/removed environment settings,
  post-start configuration edits and a wrong bind source. Read-only validation of
  the actual three-service deployment passed against the new guard.
- Updated backup path PASSED on the target machine: `backup-20260929T134402Z`,
  71,645,374 bytes, source `e8be7cc`; running-config/TCP-password checks, archive
  verification and restart health passed, with 49.21 s core interruption. No new
  restore namespace or volume was needed for this backup-only review change.
  Free C: 45.42 GiB; no images pulled. Initial retry caught a Windows fingerprint
  key separator mismatch before stopping services; normalized portable keys and
  added a regression test. That incomplete bundle has no completion manifest.
- New-machine validation was requested and then explicitly paused by the user
  until their Kubernetes setup is running. Off-machine backup and new-machine
  recovery remain unvalidated; no VM, Kubernetes runtime or remote transfer was
  started. The following same-host evidence does not satisfy those gates.

## Milestone 5 - Phase 3 local recovery, 2026-09-29, 19:00 IST

Implemented on `feat/phase3-recovery`, based on main `c764069` (merged PR #8).
Local acceptance is COMPLETE; repository delivery is
[PR #9](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/9), pending review/merge.
[ADR 0009](adr/0009-cold-backup-isolated-recovery.md) and the
[runbook](BACKUP_RESTORE.md) define the same-host rehearsal boundary.

- Added cold backup, integrity verification and isolated restore commands. Three
  stopped volumes are archived together with local secrets/configuration, exact
  tracked source and SHA-256 manifest. No credentials or runtime data enter Git.
- Final accepted backup `backup-20260929T132209Z`, source commit `31bfacf`, contains
  71,571,646 bytes (68.26 MiB). Measured source volumes: 70,524,928 bytes. Source
  services resumed healthy after 48.80 s interruption. An earlier backup caused
  50.01 s interruption; both resumes passed. The first mixed-path backup is failed
  evidence, not the accepted deliverable.
- Final restore project `gatewayai-recovery-20260929132739` passed in 78.46 s
  from validation/extraction through startup and probes (65.47 s startup/probes).
  All files, modes and owners in all three new volumes matched the accepted backup
  before startup. New containers mounted archived source, not the live checkout.
- PostgreSQL full dump read to `/dev/null` PASSED; WebUI and policy SQLite
  `integrity_check` PASSED. Existing administrator sign-in, restricted inference
  key, denied key administration and all eight aliases PASSED inside the recovery
  network. Zero-budget inference was denied before upstream execution.
- The rebuilt gateway's synthetic HTTP suite PASSED: every advertised alias,
  deterministic provenance, 503/429 bounded fallback, provider restriction,
  private/local/tool/override denial, concurrency, streaming and exhausted budgets.
  The recovered policy ledger remained byte-for-byte unchanged after these tests.
- Recovery has internal networks, no published ports, no provider keys, zero
  allowance and disabled Jev. All nine rehearsal containers (three attempts) are
  stopped; nine recovery volumes retained. No original volume was overwritten.
- Final original-deployment smoke checks PASSED: health, auth/admin login, eight
  aliases, 127.0.0.1 and localhost. All 31 original running container IDs/names
  preserved, including 28 unrelated workloads. Unrelated application functionality
  was not tested. Original budget remains 100 USD/month, debit 2.875240 USD,
  active requests zero; no new live provider request was made in Phase 3.
- All 19 offline tests PASSED, including archive traversal/link/device/duplicate
  rejection, corruption rejected before Docker mutation, private/internal recovery
  configuration, source-name protection and disk reserve. Configuration/storage
  regressions PASSED. Actual rerun against an existing recovery target was rejected
  with no volume changes; final backup re-verification PASSED.
- Failures corrected: repeat `Set-Acl` requested SACL privilege; DACL-only write
  succeeds. Packaged AppData redirected Windows files away from Docker mounts;
  physical-path resolution and mounted-file checks fix this. Internal-only networks
  suppress host forwarding on this Docker host; the final drill intentionally uses
  internal HTTP tests with no host publication. Details in TROUBLESHOOTING.
- Storage: C: 46.30 GiB before, 45.47 GiB after. Accepted/private physical recovery
  tree contains 215,149,154 bytes, plus retained initial nominal-path failure
  artifacts. Global Docker: 37 images / 18.02 GB unchanged, 16 volumes / 425.7 MB
  (initial seven / 214.6 MB), 64 containers / 31 running (initial 55 / 31), writable
  layers 394.9 MB (initial 117.4 MB). No image/model/package pull, prune, global
  Docker/WSL restart, network-mode change or data deletion. Host deltas can include
  unrelated activity; retained failed drills are included, not hidden.
- Backup files' ACLs were read back as current user/SYSTEM only. They contain
  secrets and are not tool-encrypted. No scheduled backup, off-machine retention,
  new-machine OS/image download, reboot/power-loss test, restored-browser/live
  provider cutover or guaranteed RPO/RTO is claimed. Next: review/merge this work
  and choose protected off-machine retention before laptop-loss recovery.

## Milestone 4 completion - 2026-09-29, 15:32 IST

**Phase 2 is COMPLETE for the accepted deterministic scope with Jev disabled.**
[ADR 0008](adr/0008-phase2-acceptance-jev-disabled.md) records the user's revised
acceptance scope. Delivery: [PR #8](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/8);
GitHub records its merge status. Historical partial entries below are superseded.

- Fixed the PR review finding: runtime probes now derive provider expectations
  and support both providers, OpenAI only, Gemini only and neither provider.
  The full four-mode pinned-image HTTP matrix PASSED, including every advertised
  alias and deterministic provenance headers. Single-provider outages fail within
  their allowed attempts; no-provider startup remains healthy with inference denied.
- All 14 offline tests PASSED. Renderer/storage regressions, repository security
  checks and Compose syntax PASSED. Explicit deterministic/disabled configuration
  is enforced at render and startup; providing a Jev key cannot activate calls.
- HTTP matrix PASSED: 503/429 fallback bounds, privacy/local isolation, tool and
  approval denial, provider restrictions, forged ownership, concurrent admission,
  budget exhaustion, streaming and slot release. All upstreams were synthetic.
- Streaming now records `stream_completed` or `stream_incomplete` for the final
  attempt without overwriting an earlier failed attempt. Offline tests and the
  HTTP matrix validate this; live browser streams for both providers recorded
  `stream_completed`. Historical `pending` rows are preserved.
- Recreated only LiteLLM using existing images (`--pull never`). All three core
  services and full Windows/internal authentication/discovery checks PASSED,
  including `localhost` and `127.0.0.1`. An initial smoke invocation ran before
  readiness and failed its health assertion; the completed Compose health wait
  and subsequent full smoke run passed. No global Docker/WSL restart was needed.
- Bounded live probes (64-token output cap) PASSED HTTP 200/exact `OK`:
  `coding-standard` 2.27 s, 14/4 prompt/completion tokens; `coding-fast` 3.39 s,
  9/1 tokens; `gemini-chat` 2.91 s, 9/1 tokens. A three-alias probe invocation was
  rejected by the script's two-alias limit before inference, then run in two batches.
- Edge temporary chat rendered `PHASE2_READY` from `coding-fast` and
  `STANDARD_READY` from `coding-standard`. Local ignored proof:
  `tmp/phase2-complete-browser.png`. Browser follow-up generation is additional
  traffic and is not included in the scripted token counts.
- Budget remains US$100 per UTC calendar month. Existing conservative debit
  1.437320 USD survived gateway recreation unchanged; after live/browser checks
  debit was 2.875240 USD, zero active requests, ledger 28,672 bytes. These are
  conservative admission debits, not billing totals. Fresh installs default to zero.
- C: free 59.90 GiB (preflight 59.81 GiB); core images remain 2.68 GiB. Global
  Docker sample: 23 images / 7.646 GB, seven volumes / 214 MB, 31 running of 55
  containers. No image/model/package was installed for this completion; global
  changes include unrelated concurrent activity. Only the gateway was recreated.
- Live Jev integration, labelled evaluation, calibration and activation remain
  DEFERRED, not tested or enabled. Optional components remain uninstalled. Next:
  Phase 3 backup/restore and clean rebuild, including the policy ledger. Recovery,
  reboot/crash behavior and distributed/load acceptance are not claimed here.

## Milestone 4 - 2026-09-29, 13:15 IST

Implementation review: [PR #8](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/8).
The target machine runs this implementation; main contains merged Phase 1 only.

- Refreshed GitHub, reviewed PR #6 and its checks/diff against the repository
  instructions, reran core/configuration validation and found no blocking review
  issue. Marked ready and merged with the reviewed head pinned; main merge commit
  `301e3a13a021fedfaa8418759661736fe784fb33`.
- Started `feat/phase2-policy` from that main commit. Incorporated the updated
  design in PR #7 (`8e3f324`) with a history-preserving merge; PR #7 itself remains
  open. No optional research-catalogue component was installed.
- Implemented the LiteLLM deterministic callbacks, six capability aliases,
  ordered single fallback, text/tool/provider/data-class/approval restrictions,
  durable SQLite admission debits, concurrency leases and secret-free provenance.
  See [policy operations](PHASE2_POLICY.md) and [ADR 0007](adr/0007-phase2-local-policy-ledger.md).
- User supplied amount **US$100**; implemented/stated a UTC calendar-month period.
  Local configuration uses 100; committed template uses zero. Conservative
  debits reserve both permitted attempts and are never refunded. They are not
  invoice totals or an account-wide provider cap.
- PASSED 12 offline policy tests with labelled policy/Jev subcases: deny precedence,
  key policy floors, restricted providers, unapproved fields/tools/models, request
  limits, ordered attempts, concurrent budget race, UTC rollover, restart/lease
  semantics, live lease renewal, zero budget and secret-free ledger content. A 40-request concurrent
  reservation test admitted exactly the ten requests fitting its allowance.
- PASSED pinned-image HTTP fault suite against isolated synthetic OpenAI/Gemini
  protocols: primary success, HTTP 503/429 fallback exactly once, provider restriction
  during failure, local/private isolation with zero upstream calls, empty WebUI tools,
  streaming and slot release, four active requests/fifth denied, forged admission
  token rejection without releasing another slot, and exhausted-budget denial.
  No live provider was used by this suite; it creates no additional container/image.
- PASSED renderer/storage regressions, including absent/one/both providers,
  capability alias collision and unreviewed model pricing rejection. Repository
  security/YAML checks, Compose syntax and diff whitespace checks passed.
- Deployed only the gateway and WebUI configuration updates, preserving accounts,
  provider secrets, inference key, PostgreSQL and existing volumes. Added the
  `policy-data` volume. All three core services healthy; full Windows/internal
  authentication/model discovery and both localhost spellings pass with eight aliases.
- Bounded live scripted probes returned HTTP 200/exact `OK`: `coding-standard`
  2.57 s, 14/4 prompt/completion tokens; `coding-fast` 2.70 s, 14/4 tokens. The latter
  used the approved fallback, so it was not counted as Gemini-primary proof.
  A separate `gemini-chat` probe passed in 3.42 s with 9/1 tokens. Each used a
  64-token output cap. The initial fallback's upstream error category was not
  retained; synthetic 429/503 evidence is separate.
- PASSED Edge temporary chat through the policy: `coding-fast` rendered
  `PHASE2_OK`; `coding-standard` rendered `STANDARD_OK`. Screenshot is local/ignored
  `tmp/phase2-browser-validation.png`. WebUI also generated follow-up suggestions;
  scripted token counts do not include those requests or browser traffic.
- Real failures found and corrected: SQLite context managers did not close Windows
  handles; LiteLLM enriches the shallow request-metadata snapshot; WebUI sends an
  empty tools field and also injects native builtin tools by default. Connections
  now close, policy validates preserved caller metadata, empty tools are stripped,
  actual tool definitions remain denied, and WebUI defaults to legacy mode with
  no tools configured. Fault and browser tests above passed after these corrections.
- Ledger debit survived gateway recreation (0.240400 USD before/after a
  recreation, before browser tests). At 13:15 IST it showed 1.437320 USD conservative
  debit and zero active requests. This is intentionally much higher than expected
  billing. Attempt outcomes `pending` include earlier records and streaming
  attempts lacking a deployment-success callback; they are not a billing result.
- Storage: ledger 28,672 bytes; C: free 59.72 GiB. Global Docker sample: 22 images /
  7.554 GB, seven volumes / 213.6 MB, 31 running of 55 containers. This task pulled
  no images/models; differences in global image/cache counts include unrelated
  concurrent host activity and are not attributed to Phase 2. Only project gateway
  and UI were recreated; unrelated application functionality was not retested.
- **Phase 2 remains PARTIAL.** The user has no Jev key and explicitly left live
  evaluation pending. TypeSafe Choice parsing, malformed/outage/low-confidence and
  authority boundaries have synthetic contract evidence only. Live accuracy,
  calibration, domain thresholds and provider evaluation spend remain pending.
  No runtime Jev call is enabled. Phase 3 backup/restore, reboot/crash recovery,
  distributed/load testing and optional modules are not claimed complete.

## Phase 2 design checkpoint - 2026-09-29

- Added a reviewed target separation: deterministic policy -> TypeSafe Jev structured decision -> LiteLLM provider/model execution.
- Jev may be evaluated for choice/score/probability tasks such as task class, complexity, risk, routing and escalation; it cannot grant permissions or override hard policy.
- Acceptance now requires synthetic labelled cases, calibration/low-confidence behavior, Jev outage handling, provider outage/quota handling, and proof that local-private and other fallbacks do not broaden data exposure.
- No Jev service, API key, container, package, model, third-party skill or optional provider was installed by this documentation change.
- The researched model/tool/skill inventory is recorded in `docs/MODELS_AND_SKILLS.md`; catalogue membership is not installation or approval evidence.

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

## Repository delivery and CI

- Draft PR [#6](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/6)
  contains the implementation; `main` remains at the refreshed baseline.
- Initial Linux CI run `36489059799` passed every regression assertion but failed
  because the deliberate Docker failure mock left a nonzero native exit status.
  The suite now clears that status only after all assertions pass. This was a
  test-runner issue, not a successful host/browser check.
- Corrected code at `2ba5246` passed Linux PR CI
  [run 36489200561](https://github.com/pragalbhdwivedi/miniature-octo-doodle/actions/runs/36489200561):
  YAML/security checks, configuration/storage regressions and Compose syntax.
  All 28 pre-existing workload identities were matched to running containers
  after Desktop restart; original volumes were also verified present.

## Milestone 2 follow-up - localhost forwarding (2026-09-29)

- Refreshed GitHub/main and PR #6 before work; continued `feat/phase1-core`.
- Desktop 4.92.0 / Engine 29.8.0, Windows 26200.9550, WSL 2.7.14.0 /
  kernel 6.18.33.2. Existing `.wslconfig` selected mirrored networking.
- Corrected earlier diagnosis: WSL's shared network namespace had listening
  sockets, although Windows did not list listeners. Ubuntu connections also
  timed out. Header-only inspection saw correct-port SYNs reach `loopback0`
  without replies. No demonstrated checksum or reverse-path-drop cause.
- Failed remedies: previous Desktop restart/recreation, temporary checksum
  offload change (restored), and a complete WSL restart with mirrored mode.
- At approximately 03:48 IST, backed up `.wslconfig` outside Git, changed only
  `networkingMode` to `nat`, stopped Docker, shut down WSL and started Docker.
  `wslinfo --networking-mode` confirmed `nat`. Waited for application health;
  early empty HTTP replies during startup were not counted as passing tests.
- PASSED full `manage.ps1 test`: Windows gateway health 200, unauthenticated
  listing denied, master/inference-key listing accepted, inference-key
  administration denied, WebUI health/HTML 200, existing admin sign-in and
  gateway model discovery. Both model lists empty as expected; no inference.
  Added and passed explicit `localhost` hostname checks alongside 127.0.0.1.
- Windows listeners now show only 127.0.0.1:3000/4000. PostgreSQL remains
  unpublished. Container safety, secret scoping and internal checks all pass.
- All 31 pre-change running workloads (including 28 unrelated workloads,
  matching Kubernetes names without restart counters) returned; all six volumes
  remain. Ubuntu DNS resolution passed. Unrelated application functionality,
  remote LAN access, host reboot and rollback remain untested.
- No images/models/dependencies installed for recovery. Global Docker usage
  unchanged at 19 images / 7.464 GB and six volumes / 214.2 MB, 31 running of 55
  total containers. Free C: 59.11 GiB; small host fluctuations are not an
  attributable recovery footprint. Backup is a tiny local configuration file.
- Browser acceptance is NOT claimed: Edge is unavailable through this session's
  browser tool; both visible and background in-app tabs timed out attaching the
  webview before navigation. Permission requested for alternate installed Edge
  validation. This is a browser-tool blocker, distinct from the repaired HTTP path.
- Static repository YAML/security validation and `git diff --check` passed.
- Next: complete browser acceptance. Phase 1 remains PARTIAL; provider inference
  remains pending by instruction. No optional component installed. See
  [the recovery/rollback procedure](TROUBLESHOOTING.md) for the global NAT scope.

## Milestone 3 completion and browser acceptance - 2026-09-29, 09:30 IST

- User entered OpenAI/Gemini keys in the ignored local `.env` and requested the
  next action, authorizing provider activation and minimal live validation.
  Existing secrets and gateway inference key were preserved.
- Guarded `manage.ps1 start` rendered two routes and recreated the gateway.
  All three services are healthy. Full internal and Windows smoke tests pass,
  including localhost, authentication, secret scoping and model discovery.
  Gateway and WebUI both list `openai-chat` and `gemini-chat`.
- New opt-in `test-providers.ps1 -RunLive` passed using WebUI's existing scoped
  gateway key. Each request used synthetic text, no tools, non-streaming output,
  and `max_completion_tokens=64`; the client performed no retries.

| Gateway alias | Configured model | Result | Prompt / completion tokens | Seconds |
|---|---|---|---|---|
| openai-chat | openai/gpt-5.4-mini | HTTP 200; exactly OK | 14 / 4 | 3.66 |
| gemini-chat | gemini/gemini-3.1-flash-lite | HTTP 200; exactly OK | 9 / 1 | 1.28 |

- Edge's browser extension became available. Using the existing local admin
  credentials, verified sign-in, rendered chat UI, model selection and a
  temporary conversation. OpenAI rendered `OK`; Gemini rendered `GEMINI_OK`.
  Both completed through WebUI -> LiteLLM -> provider. The UI also generated
  follow-up suggestions; the token counts above cover only the scripted probes,
  not the browser requests or their background tasks. No total billing claim.
- Local browser screenshot: ignored `tmp/phase1-browser-validation.png`.
  The earlier browser-tool blocker is resolved; no headless workaround was used.
- Validation: configuration/storage regression suite, repository security/YAML
  contract and diff checks passed. Core images remain 2.68 GiB; no optional
  component or model was installed. Host free 59.19 GiB; global Docker 19 images /
  7.464 GB, six volumes / 214.4 MB, 31 running of 55 total containers. Volume
  growth since the previous sample was approximately 0.2 MB, not exclusively
  attributable to this test. Credentials and runtime state remain outside Git.
- Phase 1 is COMPLETE on the target machine. Main is unchanged; PR #6 still
  requires review/merge. Next: Phase 2 routing, fallbacks, budgets, logging policy
  and local-private isolation. Restore, clean rebuild, reboot recovery, load
  testing and optional modules remain unvalidated/later work.
