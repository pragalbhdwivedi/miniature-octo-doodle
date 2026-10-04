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
