# Local AADI coder coordination

1 October 2026. This optional subscription handoff extends the desktop lane.
It does not replace LiteLLM, the VM controller's PostgreSQL claims, its isolated
test worker, or Telegram publication approval. The VM AADI adapter stays disabled.
Never dispatch the same private task through both lanes; a future controller
integration must unify ownership before enabling the VM adapter.

## Working boundary

The operator refreshes AADI GitHub, reads current governance/issues/PRs, reviews
the selected files for secrets/real records, and admits one bounded task against
a clean checkout of exact current `Dev`. Repository membership is not evidence
that content is safe: admission is a deliberate code-only review, not a data
classification scanner. No raw institutional data or credentials are admitted.

Antigravity Gemini claims that packet and submits its own candidate. One
`advance_task` call obtains an independent candidate from the installed signed-in
Codex CLI (`gpt-6-astra`), then asks local `qwen3:4b-thinking` to compare both.
Separate replacement files, patches, hashes, CLI events and findings remain in
non-synced LocalAppData. No candidate code is executed. Source is checked again
before a result is recorded. Findings are advice, including a `review` verdict.

```text
Operator-reviewed task at exact AADI Dev
  -> durable single-owner claim
  -> Gemini candidate in Antigravity
  -> independent Codex candidate (no Gemini answer in its prompt)
  -> local Qwen comparison
  -> persisted human_review_required result
  -> operator review, isolated tests and normal Dev workflow
```

The active Antigravity session drives this loop. App permissions still apply.
This is not an unattended background backlog runner, automatic merge/deployment,
or a full AADI controller acceptance test. Gemini CLI 0.62.0 rejected the tested
individual account with `IneligibleTierError`, directing it to Antigravity.
No credential substitution or API billing fallback was attempted. Optional CLI
installation remains stopped below the laptop's 15-GiB storage floor.

## Operator configuration

`scripts/coder_coordination.py` uses an operator-owned JSON file outside Git:

```json
{
  "repo": "ABSOLUTE_CLEAN_AADI_DEV_CHECKOUT",
  "output_root": "ABSOLUTE_LOCALAPPDATA_PRIVATE_DIRECTORY",
  "codex": "ABSOLUTE_INSTALLED_CODEX_EXECUTABLE"
}
```

Register a separate stdio MCP server named `aadi-coder-coordination`, command
Python, arguments `-u`, the script path, `--config`, configuration path, `serve`.
Keep the public `gatewayai-local-supervisor` server unchanged. These four tools
accept no repository, output path, executable, model or command:

| Tool | Effect |
| --- | --- |
| `coordination_status` | Read states and persisted results, including after a disconnect |
| `claim_next_task` | Atomically claim the pre-admitted task and obtain only its source packet |
| `submit_candidate` | Validate paths/size/schema and persist Gemini's proposal |
| `advance_task` | Commit running ownership, invoke Codex once and Qwen once, save artifacts |

Operator CLI examples, with reviewed absolute configuration and tracked paths:

```powershell
python scripts/coder_coordination.py --config CONFIG admit --task-id UNIQUE-ID --task "BOUNDED TASK" --file TRACKED-SOURCE
python scripts/coder_coordination.py --config CONFIG status
python scripts/coder_coordination.py --config CONFIG close --task-id UNIQUE-ID --reason "Reviewed artifacts and reconciled outcome; retained evidence."
```

Only one unclosed task is admitted. SQLite `BEGIN IMMEDIATE` serializes clients;
ownership is committed before provider invocation. Claims never expire or retry
automatically. Wrong tokens, duplicate submissions, dirty/stale source, unknown
paths, failed models and schema violations stop the run. Completed results are
retrievable without rerunning inference. Operator-only `close` retains history;
it does not approve a candidate. Running tasks require investigation,
not takeover. A crash in `running` deliberately needs manual reconciliation.

Use actual physical LocalAppData paths when registering a server from packaged
ChatGPT Work: its virtualized paths can be invisible to Antigravity. Check the
MCP server initializes from Antigravity before claiming it is connected.

Codex uses strict configuration, read-only sandbox, disabled shell/tool hosts,
apps/plugins/browser/skills discovery, no API-key/provider environment inheritance,
forced ChatGPT authentication, a 180-second execution/drain deadline with bounded cleanup and 1-MiB per-stream log cap.
Unexpected tool/event types invalidate a proposal. This is a restriction on the
child run, not a change to the user's global Codex or Antigravity permissions.
Subscription quotas still apply; there is no paid API fallback or retry loop.
Local Qwen has the existing 600-second ceiling and no cloud fallback.

## Validation and rollback

Eleven integration fixtures use actual temporary Git repositories and SQLite:
two-coder artifacts and hashes, result recovery/close/readmission, concurrent
single-owner claims, duplicate/ownership denial, dirty/stale remote rejection,
path/schema rejection, failure retention and fixed MCP/notification boundaries.
Existing public bridge tests remain separate. Live evidence is recorded in
BUILD_STATUS after execution; fixture results alone do not prove provider access.

Rollback: remove only this additional MCP entry and refresh Antigravity. Preserve
the public bridge and private ledger/artifacts for reconciliation. No source,
runtime, provider key, database, VM, merge or deployment needs rollback.

References: [Codex noninteractive execution](https://learn.chatgpt.com/docs/non-interactive-mode),
[Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference),
[Antigravity MCP](https://antigravity.google/docs/mcp).
