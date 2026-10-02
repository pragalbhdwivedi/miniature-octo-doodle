# ADR 0021: Durable multi-project task control

Date: 2026-10-02. Status: accepted by owner for bounded implementation.

Use the existing PostgreSQL controller ledger as the single operational task
record and GitHub as code/PR truth. Human-readable task files are generated views;
a preserved inbox and task-bound Telegram/web actions provide input. Stable SUP
IDs and retained attempts connect roadmap work, PR review and correction.

The owner selected both AADI and GatewayAI, roadmap-derived subtasks, immediate
events plus hourly active-work digests, and a separate control hostname without
login. Network reachability supplies task-control authority. Therefore record
network operators honestly and enforce private ingress, exact origins, CSRF,
optimistic revisions, idempotency and bounded command schemas. No generic shell
or production credential reaches the page or coder.

Keep one coder per subtask, independent acceptance, observed quota routing and
bounded repairs. Local Qwen may derive text only within an operator-admitted
recipe. New code scopes require a matching validator/test contract. Automated
work produces draft PRs; integration and deployment remain separate decisions.

Consequences: no extra account for internal task controls; no individual user
attribution on the web page; private/VPN users with access share its authority.
Existing code cannot be silently widened through free-text task requests. Audit
growth eventually requires explicit archival. VM availability is independent
from the Windows coder scheduler's session/power limitations.

Implementation and verification are recorded separately in
[supervisor operations](../SUPERVISOR_CONTROL.md) and [build status](../BUILD_STATUS.md).
