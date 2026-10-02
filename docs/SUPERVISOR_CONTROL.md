# Continuous supervision and task control

Owner decisions, 2 October 2026: supervise AADI and GatewayAI, derive bounded
subtasks from approved roadmaps, send immediate completion/blocker/question
updates plus hourly active-work digests, and provide full task controls on a
separate internal hostname without a login screen.

## Task records and authority

The existing durable controller ledger owns task claims, timestamps and audit.
GitHub owns code and PR state. Stable incrementing `SUP-000001` identifiers map
to existing task keys; reruns preserve that identity and increment the attempt.
No historical result is rewritten as if the correction were the first attempt.

The protected supervision directory contains five generated Markdown views:

- `future_supervisor_tasks.md`: queued and planned work.
- `active_supervisor_tasks.md`: coding, tests, review and holds.
- `completed_supervisor_tasks.md`: completed coding and its distinct PR state.
- `rerun_supervision_tasks.md`: requested corrections and their disposition.
- `supervisor_audit.md`: timestamped actors, transitions and decisions.

A sixth file, `supervisor_inbox.md`, accepts fenced JSON `add_task`,
`request_changes` and `ask` requests. The observer never overwrites this input
file. Repeated identical input blocks are acknowledged once. Generated views
are not independently editable queues: use the inbox, Telegram or control page
to enter work. Live records stay outside Git and synchronized folders.

Example inbox entry:

```json
{"action":"request_changes","task_id":"SUP-000001","text":"Add the missing edge assertion identified in our PR review."}
```

The PR observer checks exact resources every five minutes without inference.
Owner-account change requests enter the correction queue; foreign comments
remain evidence, not instructions. Old-head reviews, truncated instructions,
changed scopes, uncertain claims and changed PR heads require reconciliation.
A current matching draft may receive a new bounded attempt with fresh tests and
independent review; the publisher updates its existing task branch/PR. Review,
merge and deployment remain separate states. Nothing auto-merges or deploys.

## Roadmap and model boundaries

The operator manifest admits a finite set of roadmap recipes, including issue,
project, pinned source, goal, read/write paths and test files. Local Qwen derives
a focused title/prompt within one recipe. It cannot select executable scope or
grant itself new credentials. The observer admits at most one new subtask per
planning cycle, with at most three unfinished jobs and existing daily budgets.
Completed topic/source pairs are not regenerated just to keep models busy.

The executable contract supports bounded source development and regression
tests. Both projects use separate clean sources, evidence and publication ledgers
(AADI/Dev and GatewayAI/main). Free-text intake is automatically matched to
configured development scopes; unmatched requests stay visible as needs_scope.
This grants no arbitrary shell or production authority. New scope definitions
remain operator configuration. See [development contract](DEVELOPMENT_TASK_CONTRACT.md).
When we review PRs, we can add the next approved recipes and corrections; the
observer refreshes generated future-work records from the same ledger.

Qwen coordinates; existing cloud and local coder routes handle separate
subtasks. Observed account quota groups, existing cloud-stage budgets and bounded
repair remain effective. Idle checks and GitHub reconciliation make no model
calls. Persisted inference intent prevents replay of uncertain planning calls.

Coder confidence and independent-reviewer confidence are separate values out
of ten with recorded reasons. Missing historical scores stay unassessed.
These are model self-assessments, not calibrated probabilities or merge gates.

## Control page and conversation

The dedicated task-control hostname is linked from the existing service
directory. The page shows assignments, queue, blockers, PRs, review state,
confidence, audit history and downloadable task records. It supports global or
task pause/resume, priority, new planned intake, questions, review notes and
correction requests. Every action shows an immediate acknowledgement followed
by its saved result or error. Polling preserves input and failed requests retain
their idempotency identifier. Priorities run from 1 (lowest) to 5 (highest).

No additional login is requested by design. Any client reaching the permitted
internal/VPN network can operate these task controls; the audit therefore says
`Internal network operator`, not a verified individual name. Exact Host/Origin,
same-origin JSON, signed SameSite cookies, CSRF tokens, input bounds and optimistic
revisions protect against foreign-site actions and stale/repeated clicks. This
does not authenticate one LAN user against another. The backend binds loopback;
only the existing internal ingress bridge socket exposes it to the proxy. No
WAN web forward, arbitrary shell, credential editor or production control exists.

Telegram identifies the deterministic observer, actual recorded coder model,
execution host role, reviewer and PR. Task buttons acknowledge immediately.
Replies to tracked task messages, explicit SUP IDs, Explain and Custom stay
attached to that task. Qwen answers from bounded saved evidence; it cannot turn
conversation into unreviewed execution authority. Hourly digests occur only
while enabled work remains active; completions and blockers are immediate.

## Operation and recovery

`scripts/deploy-supervisor-control.py` deploys into the existing controller and
NPM without downloading an image. It backs up scripts/assets/route/units, preserves
other dashboard cards, enables the loopback service and adds only the dedicated
route. Deployment requires a protected `--networks` JSON list containing explicit
management, development and VPN CIDRs; broad private-address ranges are rejected.
DNS and client certificate trust are separate acceptance checks.

The VM owns the board and Telegram independently of an RDP session. Actual local
and native CLI coding still requires the Windows worker and its scheduler. A
working web page does not prove laptop logout/reboot continuity.

The state storage ceiling remains 1.9 MB. Audit evidence is never silently
evicted; reaching the ceiling rejects further mutations until explicit archival.
Rollback restores the protected pre-deployment scripts/config/assets and disables
only the new control service/socket/route. Preserve existing tasks and databases.

See [ongoing coordination](ONGOING_COORDINATION.md),
[dashboard](DASHBOARD.md), and [build evidence](BUILD_STATUS.md).

## Deployed access and audit evidence, 2 October 2026

Open [Task control](https://control.aadi.dgoi.local/) directly or use the Task
control card on [dash](http://dash.aadi.dgoi.local/). The private hostname is
served by existing ingress with the existing trusted certificate. Omada contains
an explicit host record; Windows uses a suffix-specific private DNS rule while
public DNS remains unchanged. No guest-WiFi or WAN access is admitted by the
control route. No VPN settings were changed. Phone access still needs a live
client check.

The live control checks covered pause/resume, idempotent duplicate acknowledgement,
foreign-Origin denial, question receipt and recorded answers. The original
mixed-pilot answer was retained as historical advice; exact-task questions now
exclude the old pilot evidence. Model replies remain advisory.

SUP-000005 completed a new GatewayAI draft PR (#40), 17 isolated tests and an
independent review. SUP-000006 completed local AADI coding and four tests; cloud
review waits at the daily budget cap. Protected task files are updated by the
observer and after stage completion. Live configuration, network inventory and
rollback backups remain outside the public repository.


## Blocker recovery, 2 October 2026

Blocked/owner-held jobs retain their evidence and claims but do not consume all
roadmap admission capacity. New independent work may be planned; recipes sharing
a held coder or writable path in the same repository wait for reconciliation.
The native CLI accepts one successful structured result from one invocation with
one or two native turns, the exact selected model/agent and strict permissions;
unexpected tools/delegation, duplicate results and incomplete output stay held.
Turn count is checked after completion, not a provider billing ceiling. Exit
status is saved beside the original event stream. This is not an inference
retry. Local development explanations are bounded so code has output space;
truncation still fails closed. Reviewer suggestions remain advisory and cannot
silently replace task requirements or protected compatibility expectations.

Operator corrections use a new numbered attempt, preserve previous artifacts,
identify operator authorship, and repeat isolated tests and independent review
before draft publication. These controls do not make arbitrary future work
admissible or authorize a release deployment.
