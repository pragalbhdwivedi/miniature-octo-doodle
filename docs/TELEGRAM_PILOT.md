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
evidence. Its answer is advisory. Explicit questions now show fixed-answer buttons
and **Custom**. A fixed tap saves that answer; Custom captures the next text
message for the exact question, with a Cancel option. Both receive a durable
acknowledgement. Signed callbacks bind the batch, question, options and context;
changed or answered questions reject stale buttons. `/answer` displays pending
buttons and never becomes a Qwen question. The older `/answer ID text` syntax
remains supported for pending questions. Replies are saved for operator review
and cannot expand scope or retry an uncertain stage automatically. Publication
retains its separate exact-artifact approval. Brief Decisions lists only pending
questions; detailed history remains available. A detail-preference question can
save Brief, Detailed or Comprehensive as the default for `/menu`.

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
completion and final publication were pending at initial deployment; the completed
recovery acceptance below supersedes that status.


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


## Saved-proposal recovery and completed acceptance, 2 October 2026

The third task retained complete Gemini and Codex proposals after local advisory
review stopped. The original stop reason was not durably retained; an observed
HTTP success alone does not establish a successful advisory review. The owner
authorized a 15-minute recovery, at most two fresh GPT reviews and no new coder
runs. Operator-only recovery verifies source freshness, original submissions,
candidate hashes, patches and CLI completion before exposing the saved proposals
as requiring human review. It is not exposed as a model or MCP operation. Local
advisory remains explicitly unavailable; no review success is manufactured.

The timer tested the saved third-task proposals, independently reviewed the
selected result, then tested and independently reviewed the combined file. All
22 normal tests passed. Each of the three fixed normalization mutations failed
only its intended added test. Selected candidates were Gemini, Codex, Codex;
baseline-modifying alternatives were rejected. Exactly two additional GPT calls
were reserved and no coder was rerun. The owner approved the exact combined
artifact using Telegram; the timer published one test-only commit to Dev and
read back the remote branch. Main was unchanged. The bounded batch is completed;
this does not authorize further tasks or establish reboot/laptop-off operation.
Private IDs, source revisions and runtime evidence remain outside this repository.

Fixed-answer and Custom controls are deployed to the VM service. Sixty pilot
tests passed, including recovery integrity/budgets, stale/replayed callbacks,
custom capture, immediate acknowledgement and the bare-command regression.
Telegram accepted delivery of a real detail-preference question. A live user
answer is recorded separately from unit-test evidence.
