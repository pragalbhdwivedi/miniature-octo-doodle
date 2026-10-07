# Operator resolution of a failed supervisor candidate

SUP-000016's Gemini candidate reached isolated testing and failed source
validation. Its `blocked` job, failed test result, attempt number, evidence
digest and local receipts must remain unchanged. A separate operator change was
reviewed and merged as GatewayAI PR #59. It is not a successful continuation of
the Gemini attempt.

The one-time `scripts/reconcile_sup_000016.py` command verifies the merged PR
and closed issue against GitHub, then checks the exact task, source SHA, final
blocked history digest and retained failure evidence. Its default preview
simulates the state transition on a copy. Applying it requires the freshly
observed board revision. The durable transaction adds an `external_resolution`
record and an audit event; it does not change the worker job, model result,
test result, publication record, source SHA or earlier history/evidence.

The board projects this externally resolved task as `completed` with
`merged_external` review state, a link to PR #59, and the original `blocked`
state and error visible alongside it. The original attempt's test, review and
worker-draft flags remain false. The worker still sees its underlying blocked
job and cannot replay it. A repeat apply fails closed; a later genuine
correction would expose the new job state rather than hide it behind this
external resolution.

An operator runs the script only from the protected control environment:

```text
sudo python3 scripts/reconcile_sup_000016.py --config /protected/pilot.json
sudo python3 scripts/reconcile_sup_000016.py --config /protected/pilot.json --apply --expected-revision REVISION_FROM_PREVIEW
```

Afterward, read back the task, audit event, unchanged failed history/evidence,
and generated supervisor documents. If the preview identity or board revision
differs, stop and inspect the current ledger; do not replay the model or edit
the generated Markdown. This is bookkeeping for reviewed development code,
not a live Jev activation or production deployment.

## Releasing the retained local file claim

External completion can satisfy intake admission without rewriting the failed
worker job. Admission verifies the saved job/SUP identity, source SHA, attempt,
final blocked-history digest and operator merge record. Other blocked or changed
attempts continue to hold overlapping files. The local coordinator independently
checks unclosed claims, so the original local claim must also be reconciled.

`scripts/release_sup_000016_claim.py --config <protected-worker-config>` previews
that one claim. Applying requires `--apply --expected-revision <preview-revision>`.
It takes both worker locks, verifies PR #59 and the original failure receipt,
requires no controller lease, and backs up the local coordination database.
The transaction stores the complete original row and operator resolution in
`external_claim_releases` before changing only the local claim state to `closed`.
Packet, result, error, token and all receipt files remain retained; the server job
remains blocked at attempt 0. No coder, reviewer or publisher runs in this command.
Newly admitted work uses a fresh source snapshot and its own attempt/evidence.

Operator RPC responses use compact UTF-8 JSON with the same one-MiB worker
transport cap, including the terminating newline. If compact JSON exceeds that
cap, a `zlib-json-v1` envelope carries the complete response with its exact
decoded byte count and SHA-256. The client bounds decompression to the declared
size and existing 1.9-MB controller storage ceiling, and rejects truncation,
trailing compressed data, invalid envelopes and hash/size mismatches. No fields,
history or receipts are discarded. Incompressible over-limit responses and
decoded content beyond the storage ceiling still fail explicitly.

On 8 October the release applied at revision 836. The local row's packet, result,
error and token were verified unchanged; only its claim state became closed.
The original server job remains blocked at attempt 0 with four history entries
and receipt hash `d385cf056607575cc552cd85a16b032dbf38655f79f9036705bf2275a763f7eb`.
The board continues to project it as completed/merged_external.

The next routing task, SUP-000023, had never reached a coder during its admission
failures. `scripts/rebind_sup_000023.py` is an operator-only CAS for that exact
task, requiring a fresh revision, no lease/child/model evidence, and an audit
entry containing the complete original failed job. Under Windows worker locks,
the operator verifies child absence and exact equality of all admitted files
across old/new commits, refreshes the clean source, and updates only the pinned
source in its retained local catalog. Its first coder attempt is attempt 1;
ordinary model repairs still require reconciliation of their existing child.
Readback on current source `44cb3f9` showed successful admission, a candidate,
29 passing isolated tests and an independent passing review, followed by draft
PR #69 and draft_ready status. The next worker tick was idle with zero model calls. SUP-000016 was
not replayed or reclassified as a successful worker attempt.

## Executed reconciliation, 4 October 2026

The operator preview at board revision 784 matched the exact source SHA,
blocked-history digest, retained failure receipt SHA-256
`d385cf056607575cc552cd85a16b032dbf38655f79f9036705bf2275a763f7eb`,
and merged PR #59 (`c6a4f24226c49751f8ab12e9f9f7429e5aacb057`). The guarded
apply advanced the board to revision 785 and appended audit event 790. The
operator script read back the unchanged worker job and failed evidence. The
subsequent projection fix in PR #61 left all three original worker-progress
flags false. The latest readback showed `completed` / `merged_external` in the
public board, while the underlying job remained `blocked`, attempt 0, with no
publication. The generated completed-task Markdown linked PR #59 and retained
the original error; the active-task document no longer listed SUP-000016.

PR #60 passed 188 supervisor tests (one skip) and exact-head CI run
`37192424296`; PR #61 passed its 19 focused tests and exact-head CI run
`37192710776`. Both are merged to `main`. Only the supervisor board module
and one-time operator script were installed on the control VM, with the prior
board module retained for rollback. No model call, candidate replay, provider
configuration, Jev activation or live gateway deployment occurred.
