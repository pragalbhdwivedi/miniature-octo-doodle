# Unattended delivery of admitted coder tasks

2 October 2026. The owner requested unattended scheduling for the existing
[local two-coder lane](CODER_COORDINATION.md). This adds a queue-aware Antigravity
sidecar, not a second controller or automatic task admission.

## Behavior and limits

Every five minutes, Antigravity's documented `schedule` builtin runs
`scripts/coder_schedule.py`. The helper reads the existing local queue. An empty
queue or a claimed/running/completed task causes no conversation or model call.
For one queued task it verifies exact clean current Dev, durably reserves one
notification, then uses the supported `agentapi send-message` command to notify
the operator-selected AADI conversation. Gemini's existing tools obtain the
independent Codex candidate and local Qwen comparison.

MCP `claim_next_task` now requires `expected_task_id`, checked inside the same
SQLite transaction that claims the task. A delayed notification cannot claim
a replacement task. Existing clients must refresh the MCP server/tool schema.

Before reserving delivery on Windows, the helper verifies a live process chain:
Python -> native schedule process -> Antigravity host -> Antigravity desktop.
Windows creation times reject reused parent IDs. If any ancestor has exited or
cannot be checked, the helper stops without reserving work or overwriting the
current heartbeat. This guards against native timers left behind by an app restart.
A direct shell invocation is not a valid delivery context; use the managed sidecar.
Deploy `sidecar_runtime.py` alongside the helper.

Reservations survive app restarts. A timeout, crash, ambiguous send or source
failure never automatically retries; the operator must inspect the ledger and
reconcile it. `schedule-status.json` holds the latest heartbeat and preserves
the persisted delivery state. A `notified` result proves only that agentapi
returned success. Actual task progress and the persisted candidate hashes are
the completion evidence. App permissions can still block a model turn.

The operator still admits each task and its reviewed source. No arbitrary
backlog ingestion, tool-permission grant, source application, generated-code
execution, Git publication, merge or deployment is added. Qwen remains advisory.
Subscription limits apply, with no paid API fallback. The helper has no model
credentials and invokes only a fixed CLI verb with separate argument strings.

This schedule requires Antigravity to be running in the signed-in Windows
session, the laptop to be awake, and the existing network/CLI/local-model
dependencies to be available. It does not wake the laptop or create an OS
service. Power-off, logout and reboot recovery must not be inferred from an app
restart test. Missed ticks do not authorize duplicate delivery.

## Configuration

Deploy the reviewed helper beside `coder_coordination.py` and its existing
dependencies. Keep the scheduler configuration outside Git and sync:

```json
{
  "coordination_config": "ABSOLUTE_EXISTING_COORDINATION_CONFIG",
  "conversation_id": "OPERATOR_SELECTED_EXISTING_CONVERSATION_UUID"
}
```

Use a dedicated AADI conversation with the intended Gemini Pro model selected.
The sidecar does not override model selection or change app permissions. Verify
the selected model in the app and record the model actually used in acceptance.

Create `~/.gemini/config/sidecars/aadi-coder-coordination/sidecar.json`:

```json
{
  "display_name": "AADI queued coder coordination",
  "builtin": "schedule",
  "args": [
    "*/5 * * * *", "ABSOLUTE_EXISTING_PYTHON_EXECUTABLE",
    "ABSOLUTE_CODER_SCHEDULE_SCRIPT", "--config", "ABSOLUTE_SCHEDULE_CONFIG"
  ],
  "restart_policy": "on-failure"
}
```

Back up and merge the following into `~/.gemini/config/config.json`; retain every
other setting and sidecar. Do not change the app's permission configuration:

```json
{
  "sidecars": {
    "aadi-coder-coordination": {
      "enabled": true,
      "projectId": "EXISTING_AADI_PROJECT_ID"
    }
  }
}
```

Use physical, externally visible paths from packaged ChatGPT Work. Antigravity
supplies `agentapi` in the sidecar PATH. Do not find private editor services or
repurpose app authentication. Logs/events use Antigravity's documented
`~/.gemini/antigravity/sidecar_data/aadi-coder-coordination/` directory. The helper
does not print candidate contents or claim tokens. Heartbeats are replaced
atomically rather than accumulating per-tick files; Antigravity owns its logs.

## Acceptance and operation

1. Validate an empty scheduled tick: fresh heartbeat, zero model calls.
2. Admit one reviewed synthetic no-change task at exact Dev; wait for a timer
   tick rather than manually sending the model prompt.
3. Verify Gemini claim/submission, independent Codex and Qwen artifacts, source
   SHA and result hashes. If a permission prompt appears, the user handles it.
4. Wait for another tick and verify no additional delivery or model invocation.
5. Restart Antigravity and verify the heartbeat resumes without replaying work.
6. Restore the five-minute cadence after any shorter acceptance interval.

Fixtures cover concurrent ticks, durable restart/crash exclusion, ambiguous
delivery, dirty source, exact-task replacement races, held work, closed-task
readmission, UUID validation, heartbeat persistence and bounded shell-free CLI
transport. Provider acceptance is recorded separately in
[BUILD_STATUS](BUILD_STATUS.md).

Pause/rollback: set only this sidecar's `enabled` to `false`. Keep the queue,
`scheduled_dispatches` table and artifacts for reconciliation. Do not delete
reservation rows or clear running claims to make a retry happen. The ordinary
operator `close` flow can retire a investigated task; a new admission needs a
new ID and current reviewed source. Disabling the timer does not cancel an
already-running Gemini/Codex/Qwen turn.

Official references checked 2 October 2026:
[Antigravity sidecars and agentapi](https://www.antigravity.google/docs/sidecars/),
[Codex noninteractive execution](https://learn.chatgpt.com/docs/non-interactive-mode).


Repair acceptance, 2 October 2026: the orphan from the previous host was stopped;
one current managed scheduler remained. The normal five-minute tick passed the
new lifecycle guard, recorded a successful agentapi event and moved the third
pilot task from queued to gemini_claimed without UI input. Four lifecycle tests
and nine existing scheduler regressions pass. This establishes delivery and claim,
not full batch acceptance or publication. Old uncertain reservations remain in
the ledger as history; none were deleted or replayed to obtain this result.
