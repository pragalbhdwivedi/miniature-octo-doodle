# Independent review, bounded repair and publication

The operator-only `controller_pipeline.py` extends a durable `review_required`
run. It never gives the planner, reviewer or worker host/database/publisher keys.
There is no daemon, automatic merge or deployment. AADI remains disabled.

## Review authority and independence

The controller re-fetches full governance and current task/issue/PR ownership.
It rejects any change to the original selected plan/source before starting or
publishing. Each review uses a **fresh advisory context**, with no implementer
conversation, edit tools or command authority. It sees the requirements, original
and complete candidate files, full PROJECT.md/AGENTS.md, explicitly selected context
and the independent test outcome. Full historical state/README/logs are not silently
truncated into this prompt: the controller validates their exact governance hashes;
the bounded adviser intentionally receives only the declared review context.
Missing selected files or more than 16 KiB of prompt data causes rejection.

The existing `review` capability alias may resolve to the same provider/model as
implementation. Independence means separate role/context and operator-owned tests,
not a guarantee of model/provider diversity or proof of code correctness. JSON
verdict/findings have no publication authority. Failed tests veto an approving
model; malformed, contradictory or incomplete output stops the pipeline.

Tests run in a fresh offline worker with the candidate applied against the original
source. Their command arrays are part of the operator-approved specification;
the model cannot rewrite them. Successful exports must exactly match the candidate,
so test-side edits cannot obtain review approval. Each sandbox retains the existing
CPU/RAM/PID/deadline/filesystem limits and must be removed before proceeding.

One rejected candidate may receive **one repair call**, using `coding-fast` and
the current candidate/findings. The response is full-file JSON restricted to the
original approved write paths, validated against the immutable original source.
Another fresh sandbox and fresh reviewer must both pass. Second rejection stops;
no unbounded repair loop, prompt-driven tool invocation or automatic retry exists.

## Persistent budget and state

Apply `controller-migrate.py --container SELECTED_POSTGRES --admin-role ADMIN`
after taking a protected controller DB backup. The additive transactional schema-2
migration preserves existing runs/events and refuses any version other than 1.
Fresh installations run controller-init.py, then this migration. No new database
image, driver, service, listener or provider is installed.

The PostgreSQL pipeline ceiling is **at most $1 total**, including the original
coding debit, first review, repair and second review. Stage reservations cover both
possible gateway attempts at the existing conservative price ceilings. A unique
stage debit commits before HTTP and is never refunded or replayed. The existing
$100 UTC-month gateway ceiling applies independently. Large contexts can exhaust
the remaining ceiling and stop; a requested repair is not a spending guarantee.

States: reviewing -> repairing -> re_reviewing -> approved/rejected; first-pass
approval can skip repair. Exact final operator approval permits approved ->
publishing -> published. Ambiguous HTTP/DB/worker/publication failures retain an
active/uncertain state and block re-entry. There is no retry/reset/resume command.
Inspect durable audit and publication journal; never substitute a new identity to
retry an ambiguous side effect. Database role privileges remain function-only for
writes. All CLIs share the operator lock and DB admission serialization.

## Operator workflow

Copy the structure in `config/controller/review-acceptance.json` to root-owned
0600 protected storage. Its zero IDs are placeholders. Set the exact durable run,
source SHA, artifact SHA, requirements, context, independent tests, aggregate
budget and max repairs (0 or 1). Review this scope before approving its canonical
SHA-256 (`controller_dispatch.digest(spec)`: sorted compact JSON, allow_nan=False).

```sh
sudo python3 scripts/controller_pipeline.py review --config /etc/gatewayai-controller/dispatch.json \
  --run-id RUN_ID --spec /private/review.json --approve-sha256 REVIEWED_SPEC_DIGEST
sudo python3 scripts/controller_pipeline.py status --config /etc/gatewayai-controller/dispatch.json --run-id RUN_ID
```

If approved, inspect the final candidate's private `review.patch`, artifact and
review evidence. Status emits a new **publication approval digest**, binding the
final candidate/source/artifact/review and original pipeline approval. Approval of
the earlier candidate/spec cannot authorize publication of changed repaired bytes.

```sh
sudo python3 scripts/controller_pipeline.py publish --config /etc/gatewayai-controller/dispatch.json \
  --run-id RUN_ID --approve-sha256 FINAL_PUBLICATION_DIGEST \
  --publisher-config /etc/gatewayai-worker/publisher.json
```

The existing journaled scoped publisher creates only a new worker branch and draft
PR, now identifying the tracked issue. It checks the exact unchanged source again.
No force/update/delete/merge API is available. If GitHub succeeds but result storage
fails, inspect the journal/branch/PR manually; never automatically repeat publish.
Operator provisioning still owns token scope; API success cannot prove the token
has no broader permissions. Keep all secrets, requests, model findings, artifacts,
debits and journals outside Git/sync and preserve them together during recovery.

Live GatewayAI synthetic acceptance passed on 30 September 2026: stricter tests
and first review rejected the defect, one repair passed fresh tests/review, then
exact final approval created draft PR #23. The three stages reserved $0.869440
within $1; duplicate publication was denied. See BUILD_STATUS for exact identities
and limitations. This does not establish AADI or separate-machine recovery.
