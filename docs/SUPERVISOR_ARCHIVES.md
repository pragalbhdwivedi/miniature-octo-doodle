# Verified supervisor task archives

2 October 2026. Implemented operator library, inspection CLI, opt-in operator RPC and bounded
HTTP history routing. Live activation remains a separate operator step. No live ledger
was compacted by this implementation. No model calls, database credential changes,
new packages, or runtime downloads are required.

## Storage contract

`scripts/supervisor_archive.py` moves old merged/closed task bodies and their
unshared evidence out of the hot supervisor ledger. Keep at least the newest 20
closed tasks hot, ordered by GitHub closure/update time, with saved task update
time as a compatibility fallback. Drafts and merely completed work do not qualify.
A closure must have a matching saved PR URL, repository, number and valid head;
the GitHub observation must be no more than 15 minutes old. An active worker or
question lease holds the entire archive pass. Pending corrections, questions,
Telegram replies and uncertain/pending task messages hold their tasks. A retained
job's prerequisite also stays hot.

Each archive contains the **entire pre-compaction state**, the selected task IDs,
source state SHA-256, board revision and selection policy. Files use their SHA-256
as the filename. On Linux the file is created privately, flushed with `fsync`,
atomically published without overwriting an existing archive, and the directory
entry is flushed. A fresh read verifies file hash, canonical bytes and the nested
source-state hash before a compacted state can be returned. Corruption, missing
archives, stale observations, changed source state and insufficient space savings
all reject compaction. The input object is never modified.

Keep the archive directory on the **control VM**, outside Git, web assets, synced
folders and coder mounts. The operator account owns mode 0700 directories and 0600
files. An operator-configured absolute directory is required; requests must never
choose filesystem paths. Windows tests cover logic and file readback, but do not
establish Linux directory durability or Windows ACL protection. Deploy the archive
writer on the existing Linux control VM.

The hot ledger retains:

- `next_id` and every `by_key` mapping, preventing SUP ID reuse;
- compact `archived_tasks` summaries and an `archive_index` of verified receipts;
- every audit event and idempotency request receipt;
- all questions, correction records and intake history;
- evidence still referenced by a hot task or retained correction.

A new `archive_verified` event records the archive digest and task count. No audit
sequence is reset. The immutable file retains the full task history, original
models, confidence, tests, review, PR and previous attempts.

## Required integration

Use `archive_state(state, configured_directory)` inside the existing
`pilot_server.Store.mutate` operation. Commit only its returned candidate through
the existing PostgreSQL CAS. A losing CAS or interrupted process may leave an
unused verified archive; that file is harmless and must not be silently deleted.
The next pass prepares from freshly read state. The source hash prevents applying
a prepared archive to newer state. Do not compact using a receipt alone without
calling `compact`, which reopens and verifies its file.

Before enabling scheduling, integrate these guards:

1. `ongoing_sync` and the observer filter archived task keys out of the incoming
   catalog and never resurrect them. Preserve a compact task-key/scope identity
   ledger for deduplication. Archived summaries include source SHA, recipe ID and
   `task_scope_digest` over the immutable catalog scope; reject a reused key with
   a different scope digest. Do not treat absence from hot jobs as permission to
   repeat a completed recipe.
2. Existing hot task scope comparisons remain strict. Catalog pruning must only
   remove verified archived keys, never active, draft, blocked or retained work.
3. New dependencies must resolve both hot and archived task records. Never use
   an archived dependency to bypass an independently required acceptance gate.
4. Board snapshots and generated completed-task documents combine hot tasks with
   `history_index(state, offset=0, limit=100)` summaries. Paginate and report counts;
   do not label archived tasks as missing catalog entries.
5. The existing same-origin internal control surface can expose **read-only
   summary pagination**. Full state files are privileged backups, not public
   download responses. `ArchiveStore.task` returns full task evidence for operator
   inspection only; a web detail route must explicitly project/redact allowed
   task fields before returning them. Never expose unrelated snapshot state.
6. Questions about old tasks need a bounded archive evidence reader. Corrections
   to a merged/closed task become a new linked development task; immutable archived
   evidence is never edited or silently rerun.
7. Back up the VM archive directory together with the PostgreSQL ledger and
   verify both on restore. A copied database without its referenced archives is
   an incomplete recovery. No archive retention/deletion policy is enabled.

`archive_state` returns `(unchanged_copy, None)` when no work is eligible. The
caller chooses an operator-owned trigger (for example approaching 80 hot tasks),
not a model instruction. The module does not raise the 100-task catalog or
1.9 MB storage ceilings. Compact summaries, global audit/request history and other
retained state still grow. If those alone reach the ceiling, work **stops without
losing evidence**; a separately reviewed global-history archival migration is
required. This is task archival, not an unlimited-history claim.

## Inspect and export

These commands run locally as the VM operator and do not read database credentials:

```text
python scripts/supervisor_archive.py --directory /protected/operator/archive --archive-id <64-character-sha256>
python scripts/supervisor_archive.py --directory /protected/operator/archive --archive-id <64-character-sha256> --export /protected/operator/new-evidence.json
```

The first prints only verified identity, task IDs and state hash. The second
creates a new private file and refuses to overwrite anything. Full exports contain
all pre-compaction private operational state and must remain operator-only. To
retrieve one task in code, use `ArchiveStore(directory).task(state, 'SUP-000001')`;
its archive hash is looked up from the persisted ledger, not supplied by a model.

## Verification

`python -m unittest discover -s tests -p test_supervisor_archive.py -v` passed
20 tests on WSL Ubuntu, including Linux private modes and real file/directory
`fsync`; Windows Python 3.14 passed the same suite with one explicit POSIX-mode
skip. Coverage includes immutable readback, interruption, corruption, stale CAS,
closure freshness/identity, active/draft/pending exclusions, dependency retention,
shared evidence, two successive archives, SUP counter preservation, bounded
history projection, traversal denial and failure when compaction is insufficient.
No live archive, PostgreSQL CAS integration, HTTP route or backup/restore acceptance
is claimed by these unit tests.

## Opt-in integration and worker hookup

The private VM `pilot_server` configuration may contain:

```json
{"supervisor_archive":{"enabled":true,"directory":"/protected/operator/archive"}}
```

The existing operator RPC accepts `ongoing_archive` with the expected board
`revision`, and `ongoing_archive_history` with optional bounded `offset`/`limit`.
It rejects request-supplied paths and archive IDs. Archive writes are disabled
without the explicit private configuration above. The HTTP surface exposes only
`GET /api/archive-history?offset=0&limit=100`; existing network checks apply,
unknown/duplicate parameters are rejected, and no archive POST or full-state
file route exists. `/api/state` includes a bounded `archived` summary page.
The completed-task Markdown view lists that page and reports omitted summaries.

The observer's separate `archive_enabled: true` option requests archival only
when approaching 80 hot tasks or a 1.5 MB board response, after PR reconciliation.
It then refreshes the authoritative board. Regardless of this trigger option,
the observer prunes only verified archived catalog identities before admitting
more work. `ongoing_sync` also filters archived identities before its existing
100-hot-task check. Reused archived IDs with changed scope fail closed. Recipe
IDs and source/goal digests in the archive index prevent roadmap re-admission.
This implementation was not enabled against the live six-task ledger.

The worker applies the verified catalog filter before sync when `archive_enabled`
is true, including when the observer is throttled. It updates only the protected
local catalog after verifying the server's archive identity and scope digest.

`filter_catalog` retains every nonarchived spec unchanged. It verifies persisted
archive receipt identity, SUP-to-key tombstone and immutable scope digest before
removing a local entry. The complete archived job spec remains in the verified
VM file. New dependencies referencing archived keys currently fail the existing
catalog dependency check; no acceptance is fabricated to satisfy them.

Integration validation: the Windows supervisor suite passed 102 tests (one
POSIX-only skip), including 18 observer tests with catalog pruning and
archived-recipe deduplication; 80 ongoing regressions passed. An additional
125-task regression verifies pruning to 20 hot jobs while preserving all 125
identity mappings and the next SUP counter; 103 supervisor tests then passed. Operator RPC tests
cover disabled mode, path injection, revision conflict, bounded history, scope
reuse rejection and a six-task no-op. The final suite count includes those new
observer cases in the subsequent verification record. Real VM CAS, live history
browser interaction and a live 100-task run remain NOT RUN until deployment acceptance.
