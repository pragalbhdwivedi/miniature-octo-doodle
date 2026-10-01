# Telegram coordination pilot

The operator-owned VM controller is the authority for one bounded batch. Its
PostgreSQL state reserves each stage before the laptop worker invokes a model or
changes Git. The existing Antigravity scheduler delivers an exact admitted child
task to Gemini Pro. Independent signed-in Codex proposes another candidate, and
local Qwen compares them. The laptop then runs isolated tests and a fresh Codex
review. This uses saved subscription authentication; no paid API fallback exists.

## Owner controls

Send `/menu` to the existing private Telegram bot. Buttons show Status, Inputs,
Outputs, Decisions, Controls, Usage, and Ask / follow-up. Choose Brief, Detailed,
or Comprehensive; the report button downloads the admitted evidence as Markdown.
Each callback is acknowledged before database or model work, followed by a
durable result message. Duplicate taps cannot reserve a second coding stage.
Expired buttons explain how to open current controls. Delivery uncertainty is
recorded rather than silently resending an action.

Questions are acknowledged and queued for local Qwen to answer from saved
evidence. Its answer is advisory. Replies to explicit decisions use
`/answer QUESTION_ID instruction`; they are saved for operator reconciliation
and cannot expand scope or retry an uncertain stage automatically.

Decisions presents the exact three-task charter before starting. The batch tests
case-sensitive source-system names, internal spaces in external IDs, and
case-sensitive IDs using synthetic identity fixtures. Only the identity test file
may change. Limits are three tasks, sixty minutes after scope approval, ten GPT
call reservations, and at most one repair per task. Idle polling makes no model
calls. These are call/time limits, not an exact token or monetary ceiling.

Each candidate must preserve the baseline AST and add one test. Its normal suite
must pass, and a fixed defect mutation must be caught. Independent GPT verification
cannot override failed deterministic tests. Selected additions are combined,
tested, and reviewed again. A second signed Telegram decision binds publication
to the full immutable result digest; source and bytes are rechecked before a
normal fast-forward push to AADI Dev. Main and production are outside this pilot.

## Runtime and recovery

`pilot_server.py` runs as a protected systemd operator service. Bot credentials
stay in the pre-existing root-owned Telegram configuration on the VM. The additive
`004-pilot.sql` schema uses compare-and-swap revisions; existing controller runs,
approvals, and pipelines are preserved. A shared Telegram consumer lock excludes
the legacy manual poll command. Publication tools remain separate.

`pilot_worker.py` is a fixed operator adapter on the laptop. Its SSH RPC, source
paths, existing test image, and output directory are configured by the operator,
never by model output. Models receive no SSH, Telegram, database, or Docker-host
credentials. Test containers have no network, privileges, host socket or writable
source mount. They use the already-installed pinned image with `--pull=never`.

Timestamped task/prompt/result/ack files remain in private LocalAppData. VM state
binds each parent task to its exact local child ID. A process lock excludes two
laptop workers; retained reservations prevent replay after crashes or ambiguous
transport failures. Recovery requires inspecting the saved stage and evidence.

The laptop, Docker Desktop, Antigravity, its selected conversation, signed-in
Codex, and local Qwen must remain available. The VM can answer menu requests while
the laptop is unavailable, but coding and Qwen answers wait. VM service restart is
automatic; unattended laptop boot/sleep/session recovery is not established.

## Deployment evidence

The existing controller database was backed up before migration. A restored
disposable database passed initial/read/compare-and-swap/replay checks. The
additive migration preserved all five pre-existing controller runs. No new model,
dependency, or container image was downloaded. Live service/button/worker and
three-task completion evidence is recorded separately as it becomes available;
unit tests alone do not establish those outcomes.


The systemd service is enabled and active. Telegram accepted both the welcome and
scope messages; the owner confirmed click acknowledgement and started the batch.
Antigravity hot-loaded the new one-minute worker sidecar with existing user
settings preserved. Its automatic idle tick completed without model calls, then
its next timer reserved planning after the owner approval. The original
five-minute exact-child delivery sidecar remains active. Forty-eight pilot tests
and twenty-seven existing coordination/scheduler/Telegram tests passed. Three-task
completion and final publication remain pending; this record does not assert them.


Live pilot handoff boundary: planning and parent-to-local task admission passed,
but the first Antigravity message delivery was recorded as uncertain before a
coder claimed it. Its reservation is retained; the native timer correctly refused
to resend. Windows UI input returned `GetCursorPos: Access is denied`. An actionable
recovery instruction was delivered through Telegram. The worker now surfaces this
condition once per task automatically and resumes observation of the same child;
full unattended coder delivery/completion is not claimed for this pilot run.


## Orphan timer repair

Investigation found a one-minute native scheduler from a previous Antigravity
instance still running after its parent had exited. It raced the current
five-minute scheduler and reserved new tasks through its disconnected delivery
context. The confirmed orphan was stopped without restarting Antigravity or
clearing task claims. The scheduler now checks the live Windows process ancestry
and creation times before any reservation. Missing, unreadable, unrelated or
reused parents are rejected without overwriting the current timer heartbeat.
Four lifecycle regressions and nine existing scheduler tests pass; live delivery
through the surviving managed timer passed at 20:01 UTC. Agentapi wrote one
successful delivery event and Gemini claimed the exact third task without UI input. No Windows security
setting, authentication, app permission or UI-click workaround is changed.
