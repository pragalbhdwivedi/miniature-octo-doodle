# Continuous future development queue

The supervisor distinguishes **paused** (scheduling disabled) from **idle**
(enabled, no eligible task). Finishing a finite recipe list previously left an
empty future view even though the worker remained enabled.

The repository seed is `config/supervisor/future_tasks.json`; its rationale is
in [the development backlog](FUTURE_DEVELOPMENT_BACKLOG.md). FUT identifiers are
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
limit. No history is silently removed. Unconfigured areas remain visible as
`needs_scope`; proposed paths do not create execution authority. Destructive or
production work remains a separate owner decision. Fixed scope manifests and
protected offline acceptance tests remain authoritative at coding admission.

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
  Planning outputs are proposals, independently matched to an existing scope.
- Automatic generation requests another batch of up to ten when the eligible
  future pool falls below ten, at most once per hour. Malformed or ambiguous
  inference retains evidence for recovery instead of repeatedly spending tokens.

Planning reserves one stage against the same daily cloud-work cap. Exhausted
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
