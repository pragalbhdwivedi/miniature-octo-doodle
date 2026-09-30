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
| Linux control-plane VM (Phase 5) | PARTIAL | Live data/ledger migration, provider/browser and encrypted off-VM readback restore pass; clean-host recovery/reverse cutover pending |
| Internal SSH bastion | COMPLETE | Internal scope: both laptop clients, GatewayAI ProxyJump, denied operations and guest reboot passed 2026-09-30; outside-VPN validation pending |
| Ollama | NOT STARTED | Optional |
| Local model | NOT STARTED | Optional |
| OmniRoute | NOT STARTED | Optional |
| OpenViking | NOT STARTED | Optional |
| Graphify | NOT STARTED | Optional |
| Isolated coding worker | COMPLETE | Bounded operator scope: isolation, gateway coding/budgets and live draft PR #16 passed; token provisioning scope remains operator-owned |
| Agent Controller | PARTIAL | Planner, durable dispatch, independent review, one repair and gated draft publication live-tested; AADI acceptance pending |
| Telegram approvals | NOT STARTED | Phase 8; WhatsApp excluded |

## Phase 7 live review/repair/publication acceptance - 30 September 2026

- PR #22 merged after CI passed at `dca030b99cc090e1c2fd1473cce6e55f9e4b5c45`.
  VM9125 deployed 22 verified source/config/test files; no new image, service,
  package, VM, credentials or agent privilege. PostgreSQL schema 2 retained prior
  run/event history; protected pre-migration backup remains same-host evidence.
- Root run `4dfa7612da644d3fb07d024482a8da8b` created the committed synthetic
  candidate in 12.78s with zero provider calls. Initial independent test child
  `70ec516e8d8f518e88d4ccdecb5eef97` failed the required invalid-bounds case.
  Fresh-context reviewer returned revise, identifying the missing ValueError.
- Exactly one repair ran. Fresh test child `d513c35c299a5b04abe6bdb7fcc10806`
  passed lower/upper/interior/equal/inverted-bound cases in 14.41s; second fresh
  review approved with no findings. All three sandbox containers were removed.
- Permanent pipeline reservations: first review $0.266500, repair $0.324640,
  final review $0.278300 = **$0.869440 of $1**. Three live gateway attempts;
  conservative admission debits are not provider invoice costs. Context/role
  independence does not establish different provider/model independence.
- Separate final artifact review/approval invoked the journaled publisher.
  [Draft PR #23](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/23)
  contains only `docs/examples/controller_acceptance.py`; commit
  `6f286f04523a0f68a04f002fed925f19ca183d4a` has the exact source parent above.
  Artifact SHA-256 `24177e1ee3c4f3ce633c7ce0d01696ad03699edcc1fdf457cc4baa5fdd4f910c`.
  Both durable root/pipeline states are published. Main was unchanged by this
  publication; repeated publication was rejected before any second side effect.
  Issue #21 is complete; this synthetic draft is deliberately not merged.
- Final validation: **33 target controller tests passed**, including both real
  PostgreSQL tests; **104 WSL tests passed / 2 opt-in skips**; **96 Windows tests
  passed / 10 platform/opt-in skips**. Repository security/YAML checks passed.
  A repeated test found a fixed request-hash fixture collision; randomized test
  request hashes corrected it without weakening runtime replay protection.
- GitHub anonymous API quota initially blocked refresh; waited for reset without
  passing publisher credentials to the planner. No run/provider call started
  during that block. Initial candidate failure above was the intended defect.
- Four core/proxy services healthy, gateway token-table access denied to the
  controller role, no active gateway requests. September debit **$5.739970 / 31
  attempts**, monthly ceiling unchanged at $100. Controller DB 8,223,767 bytes;
  free VM disk **48.45 GiB**, about 0.02 GiB below the previous milestone (rounded
  whole-VM measurement, not precise attributable usage). No optional downloads.
  Local VM inventory and Proxmox Notes were updated and read back; existing
  hardware, network and authentication configuration remained unchanged.
- Remaining: enable/reconcile AADI only under its own repository approvals and
  pass end-to-end acceptance. Phase 8 Telegram controls, separate-machine recovery,
  reverse cutover and outstanding client gates remain unvalidated. Phase 7 stays
  PARTIAL; this bounded GatewayAI pipeline milestone is complete.

## Phase 7 review/repair/publication implementation - 30 September 2026

- Implemented fresh-context JSON reviewer and separate sandbox tests; one bounded
  repair with immutable operator test commands; new tests/review required afterward.
  Final operator publication receipt binds the repaired artifact and review.
- Added transactional schema2 with one-shot pipeline/stage reservations, aggregate
  original+review+repair ceiling <=1USD, strict transitions and permanent replay
  denial. Model verdicts cannot authorize publication. Existing monthly limit retained.
- Migrated a test copy first. All32target controller tests passed including real
  PostgreSQL stage replay, aggregate exhaustion, transition and publication-state
  checks. Full WSL103passed/two opt-in DB skips before added HTTP-order regression.
- Private controller-only dump taken (13,344 bytes); production schema2 migration
  preserved existing run/audit records. Four live services healthy, 48.46GiB free;
  admission ledger unchanged4.870530USD/28attempts. No new images/packages/services.
- At implementation time live acceptance awaited the committed task on main;
  the subsequent measured acceptance is recorded above. No Phase7 completion claim.

## Phase 7 durable dispatch acceptance - 30 September 2026

- Implementation PR #18 merged; smoke correction PR #19 merged at
  `989d22edb6d0e526ba20511cb2899e622797de3e` after CI36745273935/36745270726 passed.
  Sixteen deployed source/config/test files verified against that commit.
- Real public GitHub refresh selected the committed ready issue/task. Reviewed
  zero-budget request `e1fa8981d99c4d85a50f38309178e990`, digest
  `ef2ca2d71308c9d22734a539ed0acc2e69ece7be474d2fe5a72fda40e7cc420f`.
  PostgreSQL claim committed before the worker fetched the exact approved source.
- Worker passed synthetic write/content assertion/local commit/export in 9.93s.
  Only `docs/worker-smoke.txt` changed; artifact SHA-256
  `5841516be22bad902af3e586ed8faab835b6fa8f969de50a755c52433dbd602c`.
  Container removed; zero provider calls; one-line patch reviewed separately.
- Injected a completion-write exception after actual worker completion. A new
  operator process read the retained `dispatching` claim. Duplicate dispatch was
  denied before execution. Reconcile verified exact result/source/job/artifact
  and persisted `review_required` without rerunning the worker. Fresh status
  readback and ordered audit events passed. First failed run remains in history.
- Final target suite: 22 tests passed including real PostgreSQL concurrency,
  audit/privilege/replay/ownership checks. Full WSL94passed/one opt-in DB skip;
  Windows86passed/nine platform/opt-in DB skips.
  Repository safety and diff checks pass; no worker containers remain.
- Four core/proxy services healthy; ledger unchanged4.870530USD/28attempts and
  zero active requests; monthly ceiling remains100USD. Controller database
  8,068,119 bytes; VMfree48.47GiB vs48.49GiB preflight. Test DB retained; no new
  images, packages, services, models or VMs. Whole-host delta is not exclusive
  database allocation. Local inventory and Proxmox Notes synchronized/read back.
- The synthetic task is marked done after acceptance; its artifact remains
  private and un-published, with the durable review-required record retained.
  No autonomous review/repair or publication action was introduced. Paid coding
  through this new dispatcher, independent reviewer/repair/publication orchestration,
  AADI activation and separate-machine controller recovery remain unvalidated.
  Existing Phase6 paid coding evidence is distinct. Phase7 remains PARTIAL.

## Phase 7 first live dispatch and fixture correction - 30 September 2026

- PR #18 merged at `d331110fabb5acbf9c323ad457dbb04b62fec3a6` after
  CI36744777902/36744738437 passed. Sixteen deployed files match `e647ff6`.
- Main task/issue eligibility and exact request review passed. Run
  `3b9d24f3dc274d72839cc1a2059abb65` was durably claimed before execution.
  Request digest `912f4407d3c2760afe3c23d9c1946fe4aec76b7abacd42b0679d254b58515828`.
- Live worker FAILED in 8.02s: the pre-existing smoke-job JSON decoded a literal
  newline inside a Python string, causing SyntaxError. Container removal passed;
  zero provider calls. PostgreSQL retained dispatching -> failed audit evidence.
  Duplicate dispatch of the same request was rejected before worker execution.
- Corrected escaping in the smoke fixture and committed controller task, with a
  regression that compiles embedded Python commands. WSL94passed/one opt-in DB skip.
  A new reviewed source/request is required; no failed run is reset or retried.
  Successful committed-task dispatch remains pending this correction reaching main.

## Phase 7 persistent state and controlled dispatch - 30 September 2026

- Implemented separate operator-only prepare/dispatch/status/reconcile CLI, exact
  source/job/image/budget digest approval and fresh eligibility check. Worker source
  pin rejects drift before model calls or container startup; run ID is reserved.
- Provisioned a dedicated PostgreSQL database/schema and restricted runtime role
  in the existing instance. Gateway tables, users, credentials and networks retained;
  no image, driver, service or model installed. VM preflight free48.49GiB.
- Real PostgreSQL test database: concurrent duplicate claims admit one caller;
  new connection sees durable state; single-flight/ambiguous/review ownership,
  permanent task/source replay denial, atomic audit order and terminal transition
  denial pass. Direct table deletion/update and schema creation denied.
- Target controller suite: 21 tests passed, including real PostgreSQL acceptance.
  Full WSL suite: 93 passed, one opt-in DB skip; Windows: 85 passed, nine platform/DB
  skips. Repository safety/diff checks pass. Gateway table access denied to runtime
  role; it has no superuser/create-role/create-database privilege. Controller DB
  7,986,199 bytes before dispatch, VMfree48.47GiB; separate test DB retained.
- Four live services healthy, monthly debit unchanged4.870530USD/28attempts.
  Committed-task live dispatch acceptance pending merge of the reviewed manifest.
- Approval remains operator-only; no daemon, automatic retry, independent reviewer,
  repair loop, publisher invocation or AADI activation. Phase7 remains PARTIAL.

## Live scoped publisher acceptance - 30 September 2026

- Supplied fine-grained token installed root-only outside Git/sandbox. Repository
  API authentication passed; the API response does not prove the token lacks
  broader repository permissions. Scope restriction remains operator-owned.
- Fresh zero-spend run `3c8b04fae1294d85b662abfa3b82f5d2` fetched main
  `b5843bbe091ccab9a12d95dd812dc167dc88db16`, recreated the previously reviewed
  synthetic clamp example, passed lower/upper/interior/equal/inverted-limit tests,
  local commit and export in 20.08s. Container removed; zero provider calls.
- Reviewed exact eight-line patch, sole path `docs/examples/worker_acceptance.py`,
  mode 0644 and artifact digest
  `5c6f2172036378342409f114cef9e83e11f2f624d52f2da252d61bb3d1f8e75d`.
- Live adapter created draft [PR #16](https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/16),
  commit `8ccedb8d461ec66e1cec3c1fb757b07b3c481f04`. GitHub readback confirms exactly
  the reviewed file, draft state, exact source parent and unchanged default branch.
  Private journal retained; no retry, force push, merge or deployment by worker.
- Four core/proxy containers healthy; loopback refresh successful. September debit
  unchanged at 4.870530 USD, 28 attempts. VM free 48.49 GiB; no images/packages/models
  installed. Only small job/artifact/configuration files added (no isolated disk delta).
- PR #13 merged at `5c9684b129849edad7758093a095d422dbe1e5b7` after
  CI36741350063/36741342519 success. Local suite: 66 passed, seven platform skips;
  safety/diff checks passed. Local VM inventory and Proxmox Notes synchronized
  and read back; hardware/auth settings unchanged.
- Phase 6 bounded acceptance complete. Phase 5 recovery/client gates remain open;
  controller orchestration is separate Phase 7 work. Acceptance PR stays draft.

A documented architecture is not implementation evidence.

## Stack review and Phase 7 start - 30 September 2026

- Refreshed all PR heads/CI/issues and reviewed the implementation stack. Fixed
  Phase4 P1 review: reserve checks now cover all discovered Docker storage drives,
  not only C:. Synthetic separate-drive tests pass; fresh CI green before merge.
- Merged PR10, PR12 (including roadmap PR11), and PR14. Closed superseded design
  PR7; preserved history. Reconciled PR13 against current main, preserving both
  worker and dashboard documentation. PR13 remains draft: publisher token is still
  absent, so live scoped publication remains blocked. No broad credential substituted.
- Phase7 read-only planner implemented: bounded public Git/GitHub refresh, exact
  SHA/recent commits, governance/task/inventory hashes, explicit ready-label and
  task ownership/dependency checks, deterministic selection, zero-budget plans.
  Empty task manifest prevents unapproved automatic work. AADI remains disabled.
- Unprivileged VM UID65534 run fetched main `b5843bbe091ccab9a12d95dd812dc167dc88db16`;
  real GitHub issue/PR inventory and governance passed. Correctly blocked with
  `no_committed_task_manifest` (the new manifest is not merged). Plan hash:
  `24e707e8bf003e311568edbc1f3fe475b6acba3199c92bc065d83f6c4daf3db3`.
  Positive task selection is synthetic evidence only; no live task executed.
- 84 WSL tests passed; Windows77passed/7existing platform/dependency skips.
  New controller tests cover ownership, approval label, dependency completion,
  cycles/duplicates, stale scope, zero budget, missing governance and pagination.
  No model calls, publication, new image, package, VM or service. VMfree48.52GiB.
- Current client check: strict WSL HTTPS200; Windows HTTPS still fails TLS
  validation. Owner-confirmed outside OpenVPN/phone RDP evidence from PR14 remains
  distinct from phone browser trust and all-client acceptance. No certificate
  bypass, Windows gateway restart or recovery cutover performed.
- Separate clean recovery host is still unnamed; clean-host and reverse-cutover
  tests remain open. Controller dispatch, PostgreSQL audit state, independent
  reviewer, repair and AADI end-to-end acceptance remain unimplemented.

## Phase 6 coding, run budgets and scoped publisher - 30 September 2026

- Continued PR #13 from `058807a`; refreshed GitHub PRs/issues and repository
  governance. Separate dashboard PR #14/untracked files were preserved.
- Implemented operator-only one-turn LiteLLM coding adapter: allowlisted public
  source/governance context, fixed aliases, JSON file proposals, exact write paths,
  independent sandbox tests and immutable input/artifact hashes. No new image,
  service, CLI package, provider, controller or VM was installed.
- Per-run budget defaults to zero, maximum1USD. Durable SQLite reservation uses
  the gateway's reviewed conservative ceilings for both possible attempts; actual
  mounted policy prices/attempt count are checked. Duplicate/concurrent IDs,
  insufficient budgets, changed ceilings and replay fail closed. Ambiguous failures
  are never refunded; the existing100USD UTC-month ledger remains authoritative.
- Dedicated chat-only key created in protected root0600 configuration outside
  Git/sync. Gateway management endpoint denied. No credential enters the sandbox.
- Live run `3f1942325ad648fb9156281ef28f9daf`: fresh main `3cf3b6d`, model-generated
  clamp function, lower/upper/interior/equal/inverted-limit tests, local commit and
  artifact export passed in18.25s; exact container removed. Reserved0.656860USD
  within the1USD ceiling. Gateway ledger confirms Gemini primary HTTP503 then
  approved OpenAI fallback accepted; two provider attempts, one client call.
- Zero-budget run was denied before HTTP. First acceptance harness expected a zero
  debit field before the ledger existed; added explicit zero counters and reran.
  No provider call occurred for either denied run.
- Reviewed synthetic artifact SHA256
  `5c6f2172036378342409f114cef9e83e11f2f624d52f2da252d61bb3d1f8e75d`;
  publisher's read-only plan passed against its recorded source/job/artifact hashes.
- Implemented separate exact-hash publisher: approved repository/default-base SHA,
  new `worker/<run-id>` branch only, draft PR only, no update/force/delete/merge.
  Stale base, cross-project credentials, default-branch output, changed artifact,
  sensitive paths and incomplete runs fail closed. Private attempt journal blocks
  automatic retries after partial failure. Scoped token provisioning remains open;
  VM publisher configuration has an empty token and is disabled. Live GitHub
  branch/PR publication is NOT validated; no acceptance PR was created.
- Tests:73 WSL passed; Windows venv66passed/7platform/dependency skips;
  24worker tests passed on VM. Initial global Windows Python lacked PyYAML;
  reran with the existing project venv, without installing packages. New Windows
  SQLite cleanup failures were fixed by explicitly closing connections.
  Repository YAML/security checks passed. Final offline source/edit/test/export
  regression passed in8.11s after adapter hardening; container removed, zero calls.
  Updated local VM notes and Proxmox Notes were read back; existing dashboard
  notes and all hardware/authentication settings were preserved.
- Core health after acceptance: four healthy containers, preserved network
  boundaries/loopback, no worker residue,100USD monthly allowance unchanged.
  Admission ledger moved4.213670->4.870530USD,26->28provider attempts,0active;
  delta equals the worker reservation. These are conservative debits, not invoices.
  VM free disk48.52GiB; no new image/storage-volume allocation.
- Phase6 remains PARTIAL until scoped credential and live publishing acceptance.
  Phase5 clean-host recovery/reverse-cutover/client gates are unchanged.

## Phase 6 worker execution boundary - 30 September 2026

- User authorized the next phase. Refreshed GitHub/default main (`3cf3b6d`),
  current Phase 5 branch (`8e0948a`), open PRs/issues and governing documents.
  Work is stacked on Phase 5 in `feat/phase6-isolated-worker`; no main/PR merge.
  Phase 5's remaining recovery and client-trust gates are not marked complete.
- Implemented an operator-only Linux broker and digest-based Python/Git worker
  image. Approved public repository fetch records the resolved SHA, then passes
  an immutable source snapshot/job into an offline non-root container. No host
  write mount, Docker socket, provider/GitHub key or production state is passed.
- Resource readback and in-container probes passed: UID65532, capabilities zero,
  no-new-privileges, seccomp, network denial, read-only input/root, no secret/socket
  mounts, 1 CPU, 768 MiB RAM/no extra swap, 64 PIDs, 256 MiB workspace and 64 MiB
  temporary tmpfs, 16 MiB per-file limit. At most eight commands/120s execution,
  30s per command, 2 MiB output per command and 1 MiB changed artifacts.
- Positive target run fetched current main, wrote/tested a synthetic permitted
  file, made a local worker-branch Git commit and exported the reviewed artifact
  in 10.78s. The broker compares against immutable input, not mutable Git history.
- Negative target runs passed: 10-second execution timeout (13.99s including
  fetch/cleanup), output flood, unauthorized README edit committed into worker
  history, symlink escape and attempted default-branch push all failed closed.
  No output artifact was accepted and each exact container was removed. Nonzero
  model budget was rejected before execution. No provider calls occurred.
- Independent lifetime/resource test passed without broker command scheduling:
  the image deadline exited137 after 151.35s; that container was removed.
- Rebuilt from the same cached source/image inputs, created a fresh workspace and
  fetched again: repeated positive run passed in 10.65s and produced the same
  patch hash. This is disposable-worker recreation, not a clean-host recovery test.
- Reviewed image: `sha256:e4933835442bd06ba855e24a347879da62ee2f6f458a22c344e9bc12c7139672`,
  306,143,291 bytes. Base Python digest pinned; Git installed from signed Debian
  repositories. VM free 48.72 GiB before and 48.53 GiB after build. No model,
  Codex CLI, controller, memory service or extra VM installed. Docker reported a
  legacy-builder deprecation notice; buildx was not installed merely to hide it.
- New worker tests passed on the target. Initial Windows test fixture used platform-dependent
  path separators; corrected to PurePosixPath, then the worker tests passed.
- Ledger immediately after worker negative tests was unchanged at September
  debit3.612410USD,22attempts,0active. Later concurrent gateway traffic advanced it
  to4.213670USD/26attempts/0active; no cause/user is inferred. Workers have no
  network/credentials and made zero provider calls. Final core check passed all
  four healthy live containers, internal network boundaries, loopback and HTTPS;
  gateway allowance remains100USD UTC-month. An old exact-debit health assertion
  failed on this later traffic; replaced in the operator probe by monotonic-ledger
  and unchanged-allowance checks without altering the live ledger.
- The independent lifetime SSH wrapper did not return after its remote result
  had been saved. Read back PASS/151.35s/exit137 and verified no worker containers
  remained, then cancelled that waiting client. No running job was abandoned.
- Final validation: 59 WSL tests passed; Windows52passed/7POSIX/dependency skips;
  all10worker tests passed on the VM. The final hardened broker re-fetched main
  and repeated the positive runtime in9.03s with the same patch hash. Repository
  safety and diff checks passed. Complete local VM/Proxmox Notes were compacted
  to fit the server limit, saved and read back; hardware settings unchanged.
- Remaining Phase 6: a gateway-backed coding-agent adapter with per-run cost
  reservations, scoped branch publication outside the sandbox and live
  coding/publishing acceptance. No autonomous agent or publication path is active.
  See [worker operations](WORKER.md) and [ADR 0014](adr/0014-zero-spend-worker-boundary.md).

## Phase 5 live migration and encrypted retention - 2026-09-30

- Tested frozen-source handoff: consistent snapshot, three Windows containers
  stopped, restart=no and local startup guard. Before any VM activation, verified
  no activation journal existed and restored Windows to healthy operation. This
  proves pre-activation rollback only; stale Windows data is unsafe after live use.
- Final frozen snapshot: 71,827,888 bytes. Independent Linux restore matched all
  three volume trees exactly and passed database integrity, existing admin/scoped
  key, eight aliases, zero-budget deny, synthetic routing/fallback/concurrency and
  unchanged policy ledger in 156.74 seconds through validation; stopped afterward.
- Activated only that verified snapshot. Windows remains stopped/restart disabled;
  the former fresh zero-spend VM core is retained stopped. Existing private
  credentials and data were preserved. Jev remains disabled. No optional install.
- Live core healthy; localhost/127.0.0.1 HTTP, existing administrator, scoped-key
  administration denial and all eight aliases passed. UI/database networks remain
  internal, only LiteLLM is attached to provider egress, and no container publishes
  host ports. Existing loopback socket proxies now target the migrated project.
- Original allowance US$100 per UTC month and US$2.875240 debit retained exactly,
  with 15 attempts/zero active requests before any VM inference. OpenAI probe:
  HTTP200/exact OK, 4.82s, 18 total tokens; Gemini: HTTP200/exact OK, 1.93s, 10 tokens.
  After both probes debit was US$2.971400, 17 attempts/zero active requests.
- Edge PASS through SSH tunnel: preserved account signed in, model selection worked,
  OpenAI rendered `VM migration verified` and Gemini rendered `Gemini VM verified`
  in a temporary chat. Evidence: `docs/evidence/phase5-live-migration.png`.
  Including WebUI follow-up generation, final admission debit US$3.569700,
  21 attempts/zero active requests. These debits are conservative reservations,
  not provider invoices or a claim of actual billed cost.
- Migrated cold backup/resume passed in 88.53s. Authenticated Fernet encryption used
  the already-installed cryptography 41.0.7 library. No dependency install.
  A 95,887,460-byte encrypted file and independent recovery-key file were retained
  in current-user/SYSTEM-only laptop storage outside Git/OneDrive. Ciphertext SHA256
  matched after download; a returned copy authenticated and passed its inner manifest.
- Restored exclusively from that returned/decrypted copy into another isolated
  project: exact three-volume bytes/modes/owners, PostgreSQL full read, both SQLite
  integrity checks, restored login/scoped key/eight aliases, budget rejection,
  synthetic routing/fallback/concurrency and unchanged ledger all passed.
  Restore through validation 143.84s; recovery containers stopped, data retained.
  This validates off-VM copy/readback plus same-VM restore, not a separate clean host.
- Rechecked live backup after adding archived-source equality and measured storage
  reserve guards: PASS, stop/backup/resume 86.87s.
- Planned live VM reboot exposed swapped Docker bridge IPs: services and ledger
  recovered, but stale systemd proxy destinations broke host HTTP. Added an
  administrator-owned boot refresh service for the explicitly selected project.
  It waits for all three owned services to be healthy, then refreshes the two
  unprivileged loopback proxy targets. No worker/application receives host authority.
- Repeated reboot PASS after readiness: boot ID changed, only the migrated three
  containers auto-started healthy, refresh service completed successfully in 59s,
  and its destinations matched current container IPs. An HTTP probe made before
  refresh completion reset; after the unit completed, localhost/127.0.0.1 HTTP,
  existing login/key/eight aliases, network isolation, Windows/WSL SSH and laptop
  tunnel HTTP200 passed. Ledger stayed US$3.569700/21 attempts/zero active requests.
  SSH password/keyboard-interactive remain disabled; VM free disk 50.514 GiB.
- All 49 unit tests pass on Linux VM and WSL, including encryption round-trip/tamper
  rejection and project/readiness guards. Windows 44 pass/5 dependency/POSIX skips.
  Repository YAML/security and diff checks pass.
- Remaining: separate approved clean-host/image retrieval recovery, reverse live
  cutover with current ledger, automated retention/key escrow and host/NAS-loss
  resilience. No recovery target has been supplied; earlier clean-machine pause
  remains respected. Outside-VPN testing remains pending by user choice.

## Phase 5 cross-host data rehearsal - 2026-09-30

- Windows cold backup passed environment/mount/configuration freshness, database
  credentials, clean stop, hashes/archive safety and healthy resumption. Size
  74,831,038 bytes; source interruption 50.62 seconds. Laptop free disk 39.28 GiB.
- Restored that backup on the approved Linux VM in a separate, internal-only
  Compose project: all three volume trees matched bytes, modes and owners before
  startup; PostgreSQL full dump read, both SQLite integrity checks, existing admin,
  scoped key, eight aliases, zero-budget rejection and synthetic routing/fallback/
  concurrency passed. The retained policy ledger was unchanged. Total restore
  through validation 194.85 seconds; containers stopped afterward, data retained.
- Existing Windows live and VM zero-spend deployments were preserved. No provider
  request was made by the restored project. This is cross-host data portability
  evidence using already-installed images, not a clean-machine recovery claim.
- This rehearsal preceded the live cutover measured above. Reverse live rollback
  remains unvalidated. No optional installation.

## Phase 5 Linux core and recovery - 2026-09-30

- User resumed VM deployment. Direct Windows and WSL key SSH passed with
  ProxyJump explicitly disabled after adding a narrow Omada laptop-address to
  target-SSH rule. Existing AADI/bastion rules and VPN configuration remain.
  The direct alias is address-dependent; the existing bastion remains available.
- Installed Docker Engine 29.8.1, containerd 2.3.6 and Compose 5.5.1 from Docker's
  official Ubuntu repository: four packages, 73.0 MB downloaded / 284 MB package
  footprint. No optional Buildx/rootless/model package or extra image installed.
- Fresh VM preflight PASS: native Ubuntu 24.04/KVM, 4 CPUs, 7.755 GiB visible RAM,
  enabled/active Docker, no existing containers, free ports and 54.837 GiB free
  before the three pinned image pulls. No Windows Docker service/data changes.
- Implemented guarded Linux private configuration/start/test/status operations,
  sharing the existing Kubernetes validation renderer. Runtime secrets have
  root ownership, directory 0700/files 0600 and survive repeated startup.
  Provider keys blank, budget zero, Jev disabled; activation is rejected.
- All three services healthy. Host HTTP, admin sign-in, scoped-key administration
  denial, eight-model discovery, zero-budget denial and synthetic HTTP
  primary/fallback/streaming/concurrency tests passed. UI-to-database and external
  TCP egress denial passed; gateway-to-database succeeded.
- **Found/fixed:** Docker internal-only networks accepted Compose's port declarations
  but installed no host bindings. Added unprivileged systemd socket proxies on
  127.0.0.1:3000/4000 using the installed systemd binary, with no socket/secret
  access. Container networks remain internal; PostgreSQL remains unpublished.
- Edge browser PASS through SSH at `http://localhost:3180`: separate administrator
  login, all eight aliases, coding-standard selection and rendered
  `policy: monthly_budget_exhausted` in a temporary chat. Screenshot:
  `docs/evidence/phase5-browser-budget-denial.png`. This is zero-spend acceptance,
  not live provider inference on the VM.
- Cold backup `backup-20260930T050013Z`: 8,261,945 bytes; stop/backup/resume 74.64 s.
  Protected same-VM storage includes source, runtime secrets and three volume
  archives with SHA-256 manifest. Source containers resumed healthy.
- Independent restore `restore-20260930T050129Z`: 76.91 s; exact restored file
  contents, original admin/scoped-key access, eight aliases, budget denial,
  PostgreSQL full dump read and WebUI SQLite integrity passed. Fresh volumes and
  containers use archived source/config, no ports and internal networks. Recovery
  containers stopped; artifacts/volumes retained. No production cutover.
- Repeated startup recreated the gateway container; private credential hash
  remained identical and the full host/API/synthetic/isolation tests passed again.
- Planned VM reboot PASS: boot ID changed, credential hash stayed identical,
  Docker and both socket units activated automatically, and all three containers
  became healthy. After readiness, host/API/synthetic/isolation tests passed again;
  Windows/WSL direct SSH and tunneled HTTP passed. A probe during early startup
  reset its connection and was not counted as acceptance. This is guest reboot
  evidence, not host power-loss or NAS recovery evidence.
- Post-reboot ledger: zero debit and zero provider attempts. VM free disk
  55,597,940,736 bytes (51.78 GiB). Three images total 2.887 GB; six volumes
  including retained recovery total 141.1 MB; six containers, three active,
  230.4 MB writable layers. No build cache or model footprint.
- Local checks: all 42 unit tests pass under WSL; Windows passes 40 with two
  POSIX-only tests skipped. Repository
  YAML/security contract and diff checks passed.
- This earlier fresh-core checkpoint preceded the migration and encrypted
  retention results above. Separate clean-host/reverse cutover gates remain open.
  Outside-network OpenVPN remains pending by user choice. No Phase 6/7 component
  installed. See [operations and remaining gates](LINUX_CORE.md).

## Internal SSH bastion acceptance - 2026-09-30

- Created an independent Ubuntu template clone: 1 vCPU, 1 GiB RAM, 32 GiB thin
  QCOW2 root on existing shared NAS storage. No backing file; measured root
  allocation 837,000,704 bytes. Guest filesystem free 30,139,219,968 bytes;
  Windows C: free 39.39 GiB. No laptop VM disk or optional image/model installed.
- SSH listens on TCP7000 only, with required public-key authentication; password,
  keyboard-interactive and root SSH disabled. Existing Windows/WSL public keys
  installed, no private keys copied. Dedicated forwarding-only user permits
  onward SSH ports 22/7000; separate key-only administrator retained.
- Narrow Omada LAN rules and guest firewall permit the path. Existing AADI rules
  and OpenVPN configuration preserved; no WAN SSH exposure added.
- Windows and WSL administrator login and GatewayAI ProxyJump passed. Onward
  TCP7000 passed. Forwarding-account shell and onward TCP8006 were denied.
  Effective SSH policy and absence of port22 listener verified. Five sampled
  internal SSH banners and inbound target-VLAN access passed; not every host tested.
- First cloud-init bootstrap failed because `/run/sshd` did not exist. Corrected
  both the guest script and vendor snippet, then reran successfully. Planned
  reboot changed boot ID; cloud-init completed, SSH/guest agent were active,
  firewall persisted and both laptop client paths passed again.
- Complete private local VM records in GatewayAI and AADI, with Proxmox Notes
  readback, capture cluster/node, disk paths, networking, accounts and test limits.
  GatewayAI's VM record now documents its working bastion access path.
- Outside-network OpenVPN validation is explicitly pending by user instruction.
  Backup/restore, hypervisor restart and NAS outage recovery remain unvalidated.
  Docker/GatewayAI application deployment stays stopped; Phase 5 is PARTIAL.
- Next: external VPN acceptance when the user is ready, or resume Phase 5 core
  deployment when requested. See [operations](SSH_BASTION.md).

## VM inventory documentation - 2026-09-29

User requested complete per-VM records in the owning project folder and Proxmox
Notes, including cluster/node identity, CPU/RAM, disk backend/volume/path, network,
startup/backup and username/access details. Added this standing rule to project
agent instructions and excluded `VM_NOTES/` from Git.

Created complete local records for GatewayAI's control plane and AADI's existing
ChatGPT Work VM. Current configuration/storage paths and effective SSH policy
were read from Proxmox/guest-agent; both named accounts have public-key access
with SSH password and keyboard-interactive authentication disabled. Passwords
were not read or changed. Actual passwords/private keys are excluded from project
files and Proxmox Notes.

Saved both records to Proxmox Notes, retained existing descriptions and verified
exact readback. Compared before/after configurations excluding description/digest:
no non-note setting changed. Git-ignore checks passed for both local records.
Application readiness and routed-SSH/recovery limitations remain unchanged.

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

## Internal ingress deployment - 30 September 2026

- User requested Nginx Proxy Manager on the existing VM. Prepared opt-in single-
  container Compose with required digest/address/private-state parameters,
  loopback-only administration and a dedicated WebUI ingress network boundary.
- Live read-only preflight: three healthy core containers, 50.51 GiB free,
  80/81/443 unused. Upstream setup/network documentation reviewed.
- User selected all internal VLANs + existing OpenVPN, private certificates, and
  the `*.aadi.dgoi.local` namespace. GatewayAI is `ai.aadi.dgoi.local`.
- NPM 2.16.0 digest-pinned image pulled (1,909,394,336 installed image bytes);
  VM free space changed from 50.51 to 48.73 GiB. No other optional image/model.
- Omada rejected wildcard LAN DNS syntax. Explicit GatewayAI DNS record saved
  for all 13 configured LANs; laptop resolution verified. Stable LAN-to-LAN TCP
  destination rule saved for ingress 80/443 only. No WAN forwarding configured.
- Separate NPM project and internal WebUI network deployed; only WebUI recreated.
  Administration stays loopback-only, with generated credentials in protected
  storage outside Git/sync. Bootstrap API avoids the image's password-logging
  environment bootstrap. Core accounts, keys, data and allowance retained.
- Strict Windows Python certificate verification initially failed due to missing
  leaf Authority Key Identifier. Leaf reissued with AKI/SKI, then strict
  certificate/hostname verification passed. WSL system trust HTTPS HTTP/2 200.
  Windows curl/Schannel revocation-status check failed; no validation bypass used.
- HTTPS existing sign-in, eight aliases, unauthenticated rejection and a synthetic
  OpenAI streamed response passed. Laptop LAN ports 81/3000/4000/5432 unavailable.
  September admission debit 3.569700 -> 3.612410 USD, 21 -> 22 attempts, zero active;
  $100 UTC-month ceiling unchanged. This is reserved admission cost, not an invoice.
- NPM cold backup encrypted with the protected recovery key; 34,788 bytes,
  off-VM copy SHA-256 matched. Authenticated decrypt, SQLite integrity, existing
  admin/route, healthy isolated NPM and nginx configuration checks passed. The
  no-port/no-provider restored copy is stopped with restart=no and retained.
  This checks ingress recovery on the existing host, not clean-host recovery.
- Reboot passed: four healthy live containers, WSL system-trusted HTTPS 200,
  successful loopback refresh and unchanged ledger. Free disk 48.72 GiB.
  The first check incorrectly expected the completed oneshot to remain active;
  service Result=success/ExecMainStatus=0 and both loopback endpoints verified it.
- User requested unattended Windows CA installation. CurrentUser CLI commands
  waited on local confirmation; the user-policy store denied access. Waiting
  commands stopped. This shell is non-admin; Edge authority-invalid remains.
  Prepared fingerprint-checked administrator import helper; elevated execution
  and subsequent browser acceptance are unvalidated. No trust checks bypassed.
- Repository safety/YAML and 49-test Windows suite passed (44 run, five platform
  skips); initial global Python lacked PyYAML, so the existing project venv was
  used with no installation. Local/proxmox inventory updated and read back;
  oversized note attempts were rejected before a compact complete note saved.
- Browser, all-VLAN clients and outside-VPN validation pending. Details:
  [ingress](INGRESS.md). No merge or next-phase readiness claim.
- Public CA handover created locally in Git-excluded LOCAL_CERTIFICATES as DER
  and PEM with installation notes; certificate fingerprint matches the issued CA.
  No private key copied. Phone/other-PC import remains a user/device acceptance step.

## Service directory and remote access - 30 September 2026

DEPLOYED: password-free `dash.aadi.dgoi.local` directory and separate HRMS/console
HTTPS hostnames reuse existing ingress. Preserved-account login, protected reads,
logout and origin/anonymous denial passed. No image pull, migration or password
reset. User confirmed external OpenVPN and phone RDP login. WireGuard server routes
corrected; client setup/handshake pending. Phone CA/DNS and tunnel reboot/logon
acceptance remain open. See [dashboard operation](DASHBOARD.md) and
[remote-access evidence](REMOTE_ACCESS_CHECK.md).

## PR stack review: Phase 4 storage guard - 30 September 2026

Resolved the open P1 review: cluster/deployment reserves now apply to every
discovered Docker/repository storage drive before downloads. Synthetic C:50GiB
and Docker D:18GiB reject both 8GiB and 4GiB reservations; zero-reserve inspection
passes. No image download or running cluster change during this review.
