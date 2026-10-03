# Continuous future development queue

The supervisor distinguishes **paused** (scheduling disabled) from **idle**
(enabled, no eligible task). Finishing a finite recipe list previously left an
empty future view even though the worker remained enabled.

The repository seed is `config/supervisor/future_tasks.json`; its current retained identities are
in [the development backlog](FUTURE_DEVELOPMENT_BACKLOG.md). The original broad catalogue was superseded on 4 October 2026; the live ledger retains its cancelled proposals and audit trail. FUT identifiers are
monotonic planning identities. An admitted task also receives a SUP identity,
retaining the FUT link, timestamped events and its eventual PR evidence.

Every five minutes the existing Windows observer reconciles task/PR results and
refills up to ten outstanding future candidates. Priority, earliest start time,
dependencies and registered development scope determine eligibility. Coding
remains limited to three active tasks with disjoint ownership/files; ten queued
candidates do not mean ten concurrent model calls. Dependencies require merged
PR evidence. Ready-for-review results release the planning window for independent
work without satisfying merge dependencies.

The backlog is bounded at 500 retained entries and the existing 1.9 MB ledger
limit. Verified merged tasks can be archived automatically when the retained queue reaches 450 entries. The operator writes and reads back an immutable full snapshot before compacting completed task text, terminal generation receipts and audit events; dependency and deduplication identities remain indexed. No history is silently removed. Unconfigured areas remain visible as
`needs_scope`; proposed paths do not create execution authority. Destructive or
production work remains a separate owner decision. Fixed scope manifests and
protected offline acceptance tests remain authoritative at coding admission.
The work board shows awaiting-scope proposals separately from blocked execution
and cancelled work. An empty scope hint on a seeded task means it is retained as
a roadmap proposal, not registered as executable coding work. Registering a
bounded scope requires repository paths, an isolated test profile and independent
admission; generating another task does not grant that authority.

## Controls

- **Override start** acknowledges immediately and resumes global scheduling on
  the next worker check. It releases the next batch cadence once. It does not
  override task-specific earliest start times, task pauses, failed/ambiguous
  claims, dependencies, quotas, protected tests or production decisions.
- **Generate future tasks** records a durable request and acknowledges it before
  invoking a model. The next available locked observer step supplies bounded
  current repository code, admitted scope descriptions, source SHA receipts and
  existing task titles to a higher-capability subscription model. Model choice
  uses the native installed inventory and both weekly/five-hour shared quotas.
  A different higher-capability model checks the concrete code gaps and rejects already-implemented or unsupported proposals before intake. Accepted outputs are then independently matched to an existing scope.
- Automatic generation requests another batch of up to ten when the eligible
  future pool falls below ten, at most once per hour. Malformed or ambiguous
  inference retains evidence for recovery instead of repeatedly spending tokens.

Planning conservatively reserves two stages (proposal and independent review) against the same daily cloud-work cap. Exhausted
subscription quotas wait for their observed reset; they do not silently consume
OpenAI API capacity for planning. Coding retains the existing configured local
fallback. Daily reservations are conservative capacity accounting, not invoices.

The future section is separate from the bounded, independently scrollable work
board. Search and state filters limit rendering to 100 results at a time and
report additional matches. The generated future Markdown includes the backlog.
HTTP controls retain revision checks, request deduplication, CSRF and internal
network restrictions. No individual login or arbitrary host command is added.

## Operation and recovery

Enable `future_enabled` in the protected worker configuration only after both
controller and Windows modules are installed. Seed through the operator-only
`ongoing_future_seed` RPC (idempotent exact IDs); the web endpoint cannot seed,
claim inference or admit scopes. `ongoing_future_prepare` takes only registered
scope IDs from that configuration. Existing intake admission fixes paths,
commands and immutable source before coding. Durable generation running state
and native inference intent prevent concurrent/repeated calls after a lost reply.

Do not label a queued proposal as implemented, reviewed, merged or deployed.
Confidence remains an uncalibrated model report, recorded when coding/review
actually returns evidence. A planning task has no fabricated confidence score.

A blocked task retains its evidence, dependency identity and exact writable-path
claim, but releases its coder slot so unrelated queued tasks continue, including
tasks for the same coder in another repository.
A source check that fails before assigned inference now holds the coordinator
packet as blocked rather than leaving it queued with a coder claim. An operator
can requeue a failed admission only when the controller has no child or model
result, the exact source SHA still matches, and the coordinator confirms no child
packet exists. The old blocked task and its evidence remain on the board.
Admission retries use a new receipt directory so a retained failed directory
cannot overwrite evidence or stop the retry. Saved candidates may normalize
oversized summary/proposal text within bounded limits; their code and original
provider receipts remain unchanged and still require isolated acceptance.

Complete
assigned output that failed only an envelope limit is normalized deterministically
and returned to isolated testing without another model call; the original provider
receipt remains unchanged. Reproducible test or review failures use the permitted
single repair attempt and prefer Claude through the native subscription pool.
Ambiguous provider completion remains held to prevent duplicate generation.
