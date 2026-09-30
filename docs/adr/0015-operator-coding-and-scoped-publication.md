# ADR 0015: Separate coding, execution and publication authority

Date: 30 September 2026. Status: coding/budgets live-tested; publication
implemented with live credential acceptance pending.

The user requested gateway-backed coding, per-run budgets and scoped PR publishing.
Extend the Phase 6 broker rather than installing a general-purpose CLI with host
shell or credential access. The first executor is one model turn returning JSON
file edits; the operator supplies scope and sandbox tests. This is intentionally
bounded and does not implement Phase 7 autonomous task selection or repair loops.

The operator adapter calls only loopback LiteLLM with a dedicated inference key.
It permanently reserves both approved attempts' conservative cost in a durable
per-run SQLite ledger before HTTP. Zero is the default; the first implementation
caps a run at one USD and one client call. The gateway retains the independent
100 USD UTC-month authority. Policy price/attempt drift fails closed. The observed
live Gemini failure/OpenAI fallback fit the same reserved ceiling.

Model output cannot select commands, network destinations or credentials. The
offline non-root sandbox applies validated edits, runs explicit tests and exports
changes against the immutable public source. Host credentials never enter it.

Publication is a separate operator action bound to the exact artifact digest,
run, project and unchanged source revision. A repository-scoped credential stays
outside the sandbox. GitHub object APIs create a new run-specific branch and a
draft PR; there is no existing-ref update, force push, delete or merge operation.
A durable attempt journal blocks automatic retries on ambiguous partial results.
Actual token scope must be checked by the operator; application-level repository
checks alone cannot establish the credential's server-side permissions.

Consequences: small changes must fit the existing text/token ceilings. Larger
contexts, iterative repair, private repositories, automatic publishing/merging,
remote approval channels and new providers require later explicit work. Live
publication remains an acceptance gate until a scoped credential is configured.
Existing Phase 5 recovery limits remain unchanged. See [worker operations](../WORKER.md).
