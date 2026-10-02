# Future development backlog

Batch: `FUT-BATCH-20261002-01`. Evidence audited at **2026-10-02T13:41:33+00:00**.

110 individually specified future tasks: AADI 52, GatewayAI 58. Machine-readable authority: `config/supervisor/future_tasks.json`. This Markdown is a review index, not a second editable queue.

## Evidence and completed-work audit

- AADI `origin/Dev`: `a21afcd8b169f8192ddeeeb040593e2af9f8b517`; files read from the Git tree rather than the older pinned physical checkout.
- GatewayAI `main` baseline: `226ddb0f70c97d044e53802c849de1bab2236b31`; validation also checked the shared integration tree at `17215c8eab9ffafc1f41ad5db015e5dd4fdeea24`.
- Read repository governance, current source, roadmaps, M1 contracts, fit-gap plan and supervisor operations. Queried current GitHub open issues/PRs for both repositories. Open issues are requirements pointers, not proof work remains: some completed work still has open issues.
- Excluded merged AADI reconciliation ordering, receipt-clock warnings, denied-identity preservation, ERP runtime/foundation preservation, ERP structural validation and independent mapping freshness (PRs 27, 29, 31, 32, 33, 35, 38, 39). Excluded Gateway boolean confidence, invalid-threshold and provider-allowlist repairs and blocker recovery. Existing archives, scheduling, task-bound Telegram conversation, confidence display, two-suite acceptance and full-source review are explicitly extended, not reimplemented.
- Relevant AADI unfinished issue lanes: #3 inventory, #4 sandbox migration evidence, #6 identity reconciliation, #7 permissions, #8 source coverage, #9 ERP fit-gap, #10 HR authority/payroll, #15 OS, #17 orchestration, #19 sandbox. Gateway lanes include #5 context/controller, #4 optional Kubernetes, #28 approval evidence and #38 distinct-coder work. Source and measured evidence override stale issue wording.
- Existing AADI PRs #21/#22/#23 and Gateway PR #36 are broader ongoing work. The private-memory task here is a planned proof harness, not a claim that PR #36 is merged or safe for derived memory. No task authorizes releasing those PRs or activating deferred provider/infrastructure changes.

## Admission and execution

FUT-000001 through FUT-000014 use the four configured scopes. Every one requires a source modification and regression coverage in its admitted two-file boundary. The first task in each scope can run independently; later same-file tasks depend on predecessors to prevent stale parallel edits. These are concrete proposed extensions, not a claim that all are observed production defects.

The other 96 tasks have empty scope IDs and remain planned until deterministic writable-file scopes, protected acceptance commands and immutable source revisions are admitted. `routine` does not confer host shell, live database, messaging or deployment authority. Four `needs_owner` tasks require actual external authorization/acceptance. An empty scope and an owner gate are distinct holds.

Priority 1: narrow correctness/authority; 2: next hardening; 3: roadmap capability; 4: owner evidence; 5: deferred optional. Priority cannot override dependencies, scope, budget or owner gates. Some dependencies intentionally reference later IDs because IDs are audit identities, not execution order; the graph is acyclic.

Prompts are at most 1,000 characters including inline checks, matching ongoing intake. The acceptance array repeats the same measurable checks for structured review. First-fourteen writable sets:

- `aadi-erp-validation`: `tools/check_erp_candidate.py`, `tests/test_development_erp.py`.
- `aadi-mapping-freshness`: `src/aadi_console/live_source.py`, `tests/test_development_mapping.py`.
- `gateway-choice-validation`: `gateway/jev.py`, `tests/test_development_choice.py`.
- `gateway-provider-restrictions`: `gateway/policy.py`, `tests/test_development_providers.py`.

No queue, deployment, credentials, model configuration or live state was modified by authoring this catalogue. Do not infer unlimited operation from 110 planned tasks: finite budgets, archive capacity, worker availability, review and scope gates still apply.

## Audit and future maintenance

- Never reuse or renumber a FUT ID. On dispatch record its immutable batch/prompt/evidence baseline and resulting SUP ID, timestamps, host/model, worktree/source, artifact/test/reviewer and PR receipts.
- At PR review, record the actual outcome in runtime state. Append new numbered follow-ups for new work; corrections link original FUT/SUP/PR/head. Retain failed attempts and completed history.
- Refresh GitHub/source before admission. If another PR implemented the exact outcome, mark superseded with evidence instead of creating duplicate code. Preserve original proposals when requirements change.
- Repository-relative evidence points to the project named on each task. No private data, credentials, production records or model responses belong in this public catalogue.

## Counts

| Scope | Tasks |
|---|---:|
| `aadi-erp-validation` | 3 |
| `aadi-mapping-freshness` | 3 |
| `gateway-choice-validation` | 3 |
| `gateway-provider-restrictions` | 5 |
| `planned (no scope)` | 96 |

Risk counts: routine 106; needs_owner 4.

## Review index

| ID | Project | Priority | Admission | Task | Dependencies |
|---|---|---:|---|---|---|
| FUT-000001 | AADI | 1 | aadi-erp-validation | Validate every ERP requirement clause before comparison | - |
| FUT-000002 | AADI | 2 | aadi-erp-validation | Bound ERP version and requirement parsing | FUT-000001 |
| FUT-000003 | AADI | 2 | aadi-erp-validation | Canonicalize ERP preflight result ordering | FUT-000002 |
| FUT-000004 | AADI | 2 | aadi-mapping-freshness | Expose mapping-specific diagnostic reasons | - |
| FUT-000005 | AADI | 2 | aadi-mapping-freshness | Fingerprint validated aggregate snapshots | FUT-000004 |
| FUT-000006 | AADI | 2 | aadi-mapping-freshness | Validate the snapshot evaluation clock explicitly | FUT-000005 |
| FUT-000007 | GatewayAI | 1 | gateway-choice-validation | Validate the allowed route catalogue before selection | - |
| FUT-000008 | GatewayAI | 1 | gateway-choice-validation | Require explicit boolean routing trust flags | FUT-000007 |
| FUT-000009 | GatewayAI | 3 | gateway-choice-validation | Add a redacted deterministic decision explanation helper | FUT-000008 |
| FUT-000010 | GatewayAI | 1 | gateway-provider-restrictions | Reject non-object policy metadata consistently | - |
| FUT-000011 | GatewayAI | 1 | gateway-provider-restrictions | Validate route candidate shapes before provider filtering | FUT-000010 |
| FUT-000012 | GatewayAI | 1 | gateway-provider-restrictions | Validate model price units before budget arithmetic | FUT-000011 |
| FUT-000013 | GatewayAI | 2 | gateway-provider-restrictions | Validate ledger concurrency and lease settings | FUT-000012 |
| FUT-000014 | GatewayAI | 2 | gateway-provider-restrictions | Reject malformed direct reservation debits | FUT-000013 |
| FUT-000015 | AADI | 3 | planned | Add a staff OIDC account-link verification adapter | - |
| FUT-000016 | AADI | 3 | planned | Implement activation invitation state transitions | FUT-000015 |
| FUT-000017 | AADI | 3 | planned | Add owner-scoped MFA recovery requests | - |
| FUT-000018 | AADI | 3 | planned | Add grant-change proposals with separate approval | - |
| FUT-000019 | AADI | 3 | planned | Reauthorize identity exports at delivery time | FUT-000018 |
| FUT-000020 | AADI | 3 | planned | Separate restricted identity field projections | - |
| FUT-000021 | AADI | 3 | planned | Implement two-scope transfer proposals | FUT-000018 |
| FUT-000022 | AADI | 3 | planned | Implement immutable maker-checker identity comparison | - |
| FUT-000023 | AADI | 3 | planned | Implement immediate local offboarding denial | - |
| FUT-000024 | AADI | 3 | planned | Add replay-safe provider lifecycle outbox | - |
| FUT-000025 | AADI | 3 | planned | Require owned-block evidence for reenabling accounts | FUT-000023, FUT-000024 |
| FUT-000026 | AADI | 3 | planned | Build alias collision classification | - |
| FUT-000027 | AADI | 3 | planned | Add directory reconciliation proposal export | FUT-000026 |
| FUT-000028 | AADI | 3 | planned | Implement day-90 retention review scheduling | - |
| FUT-000029 | AADI | 3 | planned | Implement former-mailbox access requests | FUT-000022 |
| FUT-000030 | AADI | 3 | planned | Add controlled file-release manifests | FUT-000022 |
| FUT-000031 | AADI | 3 | planned | Add emergency custody audit workflow | FUT-000022 |
| FUT-000032 | AADI | 3 | planned | Implement admission denies for deferred student identities | - |
| FUT-000033 | AADI | 3 | planned | Build admission lifecycle fit-gap runner | - |
| FUT-000034 | AADI | 3 | planned | Build student rollover and transfer fit-gap runner | FUT-000033 |
| FUT-000035 | AADI | 3 | planned | Build decimal fee receipt and reversal scenarios | - |
| FUT-000036 | AADI | 3 | planned | Build HR contract and restricted-field fit-gap cases | - |
| FUT-000037 | AADI | 3 | planned | Implement payroll golden-case comparison engine | - |
| FUT-000038 | AADI | 3 | planned | Build exam moderation and publication fit-gap runner | - |
| FUT-000039 | AADI | 3 | planned | Add report-catalogue acceptance runner | - |
| FUT-000040 | AADI | 3 | planned | Build shared-site student isolation adversarial runner | - |
| FUT-000041 | AADI | 3 | planned | Build separate-site tenancy comparison adapter | FUT-000040 |
| FUT-000042 | AADI | 3 | planned | Add ERP rejected-row reconciliation queue | - |
| FUT-000043 | AADI | 3 | planned | Add extension upgrade-compatibility harness | FUT-000033, FUT-000034, FUT-000035, FUT-000036, FUT-000038 |
| FUT-000044 | AADI | 3 | planned | Add ERP restore acceptance receipt validator | - |
| FUT-000045 | AADI | 3 | planned | Implement device coverage reconciliation contract | - |
| FUT-000046 | AADI | 3 | planned | Implement approved reader-rule revisions | - |
| FUT-000047 | AADI | 3 | planned | Add attendance absence eligibility explanation | FUT-000045, FUT-000046, FUT-000048 |
| FUT-000048 | AADI | 3 | planned | Add source-clock offset evidence projection | - |
| FUT-000049 | AADI | 3 | planned | Add capture-to-display provenance receipts | FUT-000005 |
| FUT-000050 | AADI | 3 | planned | Implement recovery-safe attendance notification proposals | FUT-000047 |
| FUT-000051 | AADI | 3 | planned | Add Identity reconciliation evidence packages | - |
| FUT-000052 | AADI | 3 | planned | Add import conflict resolution proposals | FUT-000051 |
| FUT-000053 | AADI | 3 | planned | Add restore reconciliation verification | FUT-000051 |
| FUT-000054 | AADI | 3 | planned | Implement M1 gate evidence freshness tracking | - |
| FUT-000055 | AADI | 3 | planned | Add AADI OS signed release manifest verification | - |
| FUT-000056 | AADI | 3 | planned | Implement node enrollment proposal records | FUT-000055 |
| FUT-000057 | AADI | 3 | planned | Add node update rollback eligibility evaluator | FUT-000055 |
| FUT-000058 | AADI | 3 | planned | Implement sandbox network readiness evidence parser | - |
| FUT-000059 | AADI | 4 | owner evidence | Record signed ERP foundation selection evidence | FUT-000033, FUT-000034, FUT-000035, FUT-000036, FUT-000037, FUT-000038, FUT-000039, FUT-000040, FUT-000041, FUT-000042, FUT-000043, FUT-000044 |
| FUT-000060 | AADI | 4 | owner evidence | Record two accepted payroll shadow cycles | FUT-000037 |
| FUT-000061 | GatewayAI | 3 | planned | Implement verified global audit-segment archival | - |
| FUT-000062 | GatewayAI | 3 | planned | Implement idempotency receipt archival lookup | FUT-000061 |
| FUT-000063 | GatewayAI | 3 | planned | Add complete ledger-and-archive backup manifests | FUT-000061, FUT-000062 |
| FUT-000064 | GatewayAI | 3 | planned | Add paginated archived task detail projection | - |
| FUT-000065 | GatewayAI | 3 | planned | Add archived-task correction linkage | FUT-000064 |
| FUT-000066 | GatewayAI | 3 | planned | Add supervisor retention capacity forecasting | FUT-000061, FUT-000062 |
| FUT-000067 | GatewayAI | 3 | planned | Add workflow dependency graph projection | - |
| FUT-000068 | GatewayAI | 3 | planned | Add PR review evidence comparison view | FUT-000087 |
| FUT-000069 | GatewayAI | 3 | planned | Add task attempt timeline view | FUT-000064 |
| FUT-000070 | GatewayAI | 3 | planned | Add workflow filters with stable pagination | FUT-000064 |
| FUT-000071 | GatewayAI | 3 | planned | Bind confidence observations to artifact revisions | - |
| FUT-000072 | GatewayAI | 3 | planned | Add safe machine-readable task evidence exports | FUT-000064 |
| FUT-000073 | GatewayAI | 3 | planned | Persist Telegram reply-message task bindings | - |
| FUT-000074 | GatewayAI | 3 | planned | Add delayed-action acknowledgement receipts | FUT-000073 |
| FUT-000075 | GatewayAI | 3 | planned | Add user-controlled digest quiet windows | - |
| FUT-000076 | GatewayAI | 3 | planned | Add dependent multi-question clarification flows | FUT-000073 |
| FUT-000077 | GatewayAI | 3 | planned | Add conversational correction confirmation | FUT-000073 |
| FUT-000078 | GatewayAI | 3 | planned | Add task-specific notification deep links and next actor | FUT-000068 |
| FUT-000079 | GatewayAI | 3 | planned | Persist quota observations with provenance and expiry | - |
| FUT-000080 | GatewayAI | 3 | planned | Add capability-compatible quota fallback plans | FUT-000079, FUT-000107 |
| FUT-000081 | GatewayAI | 3 | planned | Add work-preserving coder handoff receipts | FUT-000080 |
| FUT-000082 | GatewayAI | 3 | planned | Add local-model acceptance profiling | - |
| FUT-000083 | GatewayAI | 3 | planned | Add empirical model selection reports | FUT-000082 |
| FUT-000084 | GatewayAI | 3 | planned | Add executor heartbeat grace diagnostics | - |
| FUT-000085 | GatewayAI | 3 | planned | Add reviewer finding evidence anchors | - |
| FUT-000086 | GatewayAI | 3 | planned | Classify baseline and candidate command failures | - |
| FUT-000087 | GatewayAI | 3 | planned | Add per-file review-context completeness manifests | - |
| FUT-000088 | GatewayAI | 3 | planned | Add bounded independent-review disagreement workflow | FUT-000085, FUT-000086, FUT-000087 |
| FUT-000089 | GatewayAI | 3 | planned | Add per-file protected-test attestation manifests | - |
| FUT-000090 | GatewayAI | 3 | planned | Add dependency-aware publication stale checks | FUT-000068 |
| FUT-000091 | GatewayAI | 3 | planned | Add incremental code-graph reindex planning | - |
| FUT-000092 | GatewayAI | 3 | planned | Implement graph parser coverage reporting | - |
| FUT-000093 | GatewayAI | 3 | planned | Add retrieval quality evaluation corpus | FUT-000092 |
| FUT-000094 | GatewayAI | 3 | planned | Add context deduplication with source citations | FUT-000093 |
| FUT-000095 | GatewayAI | 3 | planned | Add public-memory deletion reconciliation | - |
| FUT-000096 | GatewayAI | 3 | planned | Add private-memory export and deletion proof harness | - |
| FUT-000097 | GatewayAI | 3 | planned | Add recovery evidence bundle validator | FUT-000063 |
| FUT-000098 | GatewayAI | 3 | planned | Add recovery send-disable configuration checks | FUT-000097 |
| FUT-000099 | GatewayAI | 3 | planned | Add reverse-cutover preflight evidence checks | FUT-000097 |
| FUT-000100 | GatewayAI | 3 | planned | Add backup retention integrity inventory | FUT-000063 |
| FUT-000101 | GatewayAI | 3 | planned | Implement isolated Kubernetes worker Job renderer | - |
| FUT-000102 | GatewayAI | 3 | planned | Add worker network-policy fixture verification | FUT-000101 |
| FUT-000103 | GatewayAI | 3 | planned | Implement component installation plan preflight | - |
| FUT-000104 | GatewayAI | 3 | planned | Implement component removal impact analysis | FUT-000103 |
| FUT-000105 | GatewayAI | 3 | planned | Add component configuration drift reports | FUT-000103 |
| FUT-000106 | GatewayAI | 3 | planned | Add storage growth guard projections | - |
| FUT-000107 | GatewayAI | 3 | planned | Add provider capability catalogue validation | - |
| FUT-000108 | GatewayAI | 3 | planned | Add conservative price-review expiry policy | FUT-000012 |
| FUT-000109 | GatewayAI | 4 | owner evidence | Record separate-host recovery acceptance | FUT-000097, FUT-000098, FUT-000100 |
| FUT-000110 | GatewayAI | 4 | owner evidence | Record remote-client internal TLS acceptance | - |

## Validation boundary

Catalogue checks passed: 110 unique sequential IDs and distinct titles; every evidence path exists at its recorded Git baseline; every dependency resolves and the graph has no cycles; 14 source-changing tasks have configured scopes; exact schema and prompt bounds checked (maximum 490 characters). The actual future-state seed validator accepted all 110 entries, exact reimport added none and next ID remained 111. This validates planning data, not implementation or production acceptance. No model calls or live integration were needed.
