# ADR 0017: PostgreSQL claims and controlled operator dispatch

Date: 30 September 2026. Status: implemented; acceptance tracked in BUILD_STATUS.

Keep the unprivileged repository planner read-only. Introduce a separate Linux
administrator CLI that prepares an exact review request, then requires its SHA-256
before one synchronous worker invocation. It refreshes Git/GitHub again, compares
the selected task/source/job, and pins the worker fetch to that source before any
model call or sandbox startup. Approval includes the immutable image and budget.

Use a dedicated database in the existing PostgreSQL instance. A NOLOGIN role owns
the schema; the runtime role has SELECT and only two narrowly defined mutation
functions. Atomic claim/event insertion precedes dispatch. Unique constraints
prevent run/request replay, repeated task/source attempts, multiple active host
runs and new attempts at a task awaiting review. Terminal states cannot restart.
Functions use a fixed search path; requests are encoded, never interpolated SQL.

The operator reaches the existing psql through local Docker exec and the dedicated
role. This does not grant Docker/database authority to the planner or sandbox.
It needs no provider/master database password, new client package, image, network
listener or agent service. The existing PostgreSQL local-socket authentication is
unchanged; the passwordless runtime role cannot authenticate over password-based
TCP. A host/database administrator remains trusted and can override these controls.

No distributed transaction spans GitHub, PostgreSQL and Docker. Promise at-most-one
automatic attempt, not exactly-once external execution. Lost responses or killed
operators remain dispatching/uncertain; no lease expiry, automatic retry or refund.
Reconciliation only checks the bound private result/artifact and cannot invoke a
worker. Missing evidence stays uncertain and blocks subsequent dispatch.

This adds persistence and bounded dispatch, not an autonomous scheduler, independent
reviewer, repair loop, publication orchestration or Telegram approval service.
AADI remains disabled. Zero-spend offline tasks are now valid planner jobs; coding
requires explicit 0 < budget <= 1 USD and the existing durable run/monthly limits.

PostgreSQL guarantees used: [unique partial indexes](https://www.postgresql.org/docs/16/sql-createindex.html)
and [transaction/row locking](https://www.postgresql.org/docs/16/explicit-locking.html).
