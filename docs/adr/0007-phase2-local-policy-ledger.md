# ADR 0007: Deterministic policy and durable conservative admission budget

## Status

Implemented for local validation; see BUILD_STATUS for tested/deployed results.

## Decision

Use LiteLLM CustomLogger request/deployment hooks for the deterministic authority
layer. Keep the same three core services/images. Add a small SQLite ledger in a
dedicated persistent volume for transactional monthly admission debits and
concurrency leases. The ledger is independent of optional LiteLLM spend logging;
no prompts are retained to enforce policy.

Reserve conservative cost for primary and permitted fallback before any attempt.
Never refund ambiguous failures. Do not enable Jev at runtime before a labelled
live evaluation and calibration; user explicitly left that evaluation pending.
`local-private` fails closed until a local provider is separately approved.

## Consequences

This offers enforceable local admission limits without another image, service,
Redis dependency or detailed request logs. Usable allowance is intentionally lower
than invoice-based accounting. It is not a provider-account billing cap. The new
volume must be included in Phase 3 recovery work. SQLite is scoped to a single
host; distributed gateway operation is outside this validation.

PR #6 was reviewed and merged to main at `301e3a13a021fedfaa8418759661736fe784fb33`.
This implementation incorporates the design commit from PR #7 and addresses the
deterministic portion of issue #3. The user subsequently accepted Phase 2 with
Jev disabled in [ADR 0008](0008-phase2-acceptance-jev-disabled.md); live Jev evidence
remains a deferred activation gate. See [policy operations](../PHASE2_POLICY.md).
