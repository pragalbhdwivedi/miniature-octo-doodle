# ChatGPT Work, Gemini and the local supervisor

Requested 1 October 2026. This is an operator-mediated desktop handoff, separate
from the VM controller. The existing controller, LiteLLM policy, review pipeline
and Telegram publication approval remain authoritative for their own operations.

## Working arrangement

The owner assigns a bounded task. ChatGPT Work or Gemini Pro proposes code for
explicit files at a current public Git SHA. The installed Qwen3 thinking model
critiques the candidate locally. An operator checks the diff and runs appropriate
tests in an isolated workspace before routing it through existing review gates.
Neither a desktop response nor a Qwen verdict can authorize publication or merge.

Use one owner per task. Give the other coder a distinct task or independent review.
Use separate worktrees for actual edits. This helper does not acquire controller
claims or prevent another application from editing files: ownership coordination
is manual. It does not click either desktop app or run an unattended agent loop.

## Shared context and memory

`AGENTS.md` and the current repository documents apply to both coders. `GEMINI.md`
is a Gemini CLI entry point; Desktop must receive an attached/pasted packet.
Imported memory contains stable preferences and dated context, never credentials,
private operational inventories, raw HR/student records or whole local transcripts.
Refresh GitHub before accepting remembered implementation status.

Google supports [memory import](https://support.google.com/gemini/answer/16868299?hl=en)
for eligible personal accounts: Settings & help -> Import memory to Gemini ->
paste the prepared summary -> Add memory. Verify the resulting thread. This is
a one-time transfer, not a live sync with ChatGPT or OpenViking. Whole-chat export
is a separate account operation and is not performed by this setup.

[Gemini Desktop for Windows](https://support.google.com/gemini/answer/18263854?hl=en)
offers coding assistance; local repository execution must be verified separately.
[Gemini CLI](https://geminicli.com/docs/get-started/authentication/) supports Google
AI Pro account sign-in. The subscription path and the paid API/LiteLLM path have
separate authentication and usage controls. Never reuse subscription OAuth tokens
as gateway API keys. On 1 October 2026, after the storage warning, the owner
explicitly requested CLI installation. Gemini CLI 0.62.0 was installed as a
CLI-only exception under the user's `.local/share/gemini-cli` directory, added
to the user PATH and verified with `gemini --version` and `gemini --help`.
The installed native credential-storage module also loads. Google sign-in and
authenticated coding remain pending. Start a new PowerShell window, run `gemini`
from the intended project worktree, and select Sign in with Google using the
subscription account. Further optional downloads remain stopped below the
15-GiB project floor. Do not change Spark privacy/access settings on the owner's behalf.

## Prepare and review a desktop proposal

Run the helper from the implementation checkout, naming a separate clean checkout
whose HEAD equals current public main. It accepts only this public repository,
one to eight named tracked text files, and at most 64 KiB total source. AADI's
private-source adapter remains disabled; do not use this helper on private code.

```powershell
python scripts/desktop_review.py prepare --repo C:\path\to\clean-public-main `
  --owner gemini-pro --task "Explain the selected function and propose one focused fix" `
  --file scripts/local_agent.py
```

Use `--owner chatgpt-work` for the other coder. The resulting LocalAppData directory
contains `prompt.txt` and `packet.json`. Send only `prompt.txt` to the selected
coding app. Copy the contents of its JSON code block into `candidate.json` in that
directory, excluding the fences. Ordinary rendered Markdown can corrupt code
escaping and identifiers; a malformed response must be repaired by its author.
The packet records the exact source and owner; keep it operator-owned. Its digest
is provenance, not a signature or protection against a malicious local operator.

```powershell
python scripts/desktop_review.py review --packet C:\path\to\packet.json `
  --candidate C:\path\to\candidate.json
```

The existing local-agent validator checks the candidate paths/size, verifies the
patch with `git apply --check`, asks local Qwen for a separate critique, and checks
current source again. Output JSON and optional patch remain outside Git/sync in
LocalAppData. It executes no candidate code/tests, edits no source and calls no
cloud model. Review is advice, never an acceptance or deployment result.

## Acceptance boundary

Record unit checks, local-model acceptance and actual desktop import separately
in BUILD_STATUS. A synthetic proposal does not prove Gemini generated code, memory
was imported, dual-agent orchestration works, or an AADI task is ready. Automated
desktop/CLI dispatch, task claiming, cancellation, independent sandbox testing
and controller ingestion still require implementation and end-to-end validation.

## Antigravity local supervisor connection

`scripts/supervisor_mcp.py` is a dependency-free stdio MCP server. It reuses the
existing source, candidate and patch guards and the loopback-only local Qwen
adapter. This adds direct tool-based review transport, not autonomous control of
either coding application. It accepts no caller-supplied repository, endpoint,
model, executable or output path. The operator configures the fixed source root.

Tools:
- `supervisor_status`: describes the boundary; it does not claim model health.
- `prepare_review(task, paths)`: checks clean current public GatewayAI main,
  reads one to eight named tracked files and returns source plus a session task ID.
- `review_proposal(task_id, candidate)`: validates the same source and candidate,
  checks patch applicability, calls `qwen3:4b-thinking`, rechecks source, saves
  local evidence, then returns findings and an audit ID. Candidate fields are
  `summary`, `proposal`, and `changes` (complete replacement contents).

Only public/synthetic content may be submitted. Although Qwen runs locally,
its findings return to the cloud coding client. This bridge is not a route for
private AADI code or institutional records. Model output can be wrong; a `review`
verdict still means `human_review_required`, never acceptance or permission.

The stdio process opens no listening port, exposes no source writes or command
execution tool, and receives no new production credentials. It makes fixed Git
validation calls and loopback inference requests. It uses the existing desktop
evaluation exception, separate from the VM's LiteLLM execution/approval pipeline.
The bridge does not sandbox Antigravity's own built-in tools. Existing app
security settings remain operator-controlled.

Configure a custom server using Google's documented
[MCP configuration](https://antigravity.google/docs/mcp). The global file is
`~/.gemini/config/mcp_config.json`; preserve existing entries and back it up first:

```json
{
  "mcpServers": {
    "gatewayai-local-supervisor": {
      "command": "C:/Python314/python.exe",
      "args": ["-u", "C:/path/to/runtime/supervisor_mcp.py",
               "--repo", "C:/path/to/clean-public-main",
               "--output-root", "C:/Users/USER/AppData/Local/GatewayAI/supervisor-reviews"],
      "env": {"PYTHONUTF8": "1"}
    }
  }
}
```

Use the actual installed Python and keep `supervisor_mcp.py`, `desktop_review.py`
and `local_agent.py` together. Local runtime copies live outside Git/sync under
`~/.local/share/gatewayai-supervisor`. Evidence must resolve beneath LocalAppData;
an explicit matching LOCALAPPDATA environment override handles app virtualization.
There are no additional Python packages. Refresh MCP servers in Antigravity
Settings > Customizations, then use a new conversation if discovery is stale.
App permissions, if requested, must be handled by the user.

A local `~/.gemini/config/rules/gatewayai-supervisor.md` rule with
`trigger: model_decision` describes when to use the tools. Project `GEMINI.md`
also documents the workflow. These instructions encourage tool use; they are
not a mandatory enforcement hook on every app action.

For app acceptance, use a new conversation with no private project: ask Gemini
to call `supervisor_status`, prepare a task explaining validation in
`scripts/controller-init.py`, author an accurate no-change candidate, then call
`review_proposal`. Require actual findings and audit ID in the final response.
Do not run the provisioning script. Match the returned ID to local evidence
before claiming success. A scripted MCP call is not proof of Antigravity use.

The first app acceptance passed on 1 October 2026: Gemini 3.1 Pro invoked all
three tools and displayed a review linked to a verified local audit record.
The owner handled tool permissions in the app. No private project was attached.
Qwen's returned critique contained an incorrect wording objection; treat findings
as untrusted advice to check against source. See BUILD_STATUS for exact limits.

Each process retains at most 16 task packets. Restarting discards task IDs; prepare
a fresh task afterward. Calls are serial and local inference has a 600-second
upper timeout; stopping the client/server interrupts the connection. The source
must remain clean at current public main. If main advances, update the dedicated
source checkout deliberately and prepare a new task. Never point at a dirty
coding branch to bypass the check.

Rollback: remove only the `gatewayai-local-supervisor` entry and refresh MCP.
Retain other entries and local review evidence. The original configuration is
backed up next to the config file. No merge or deployment is part of this setup.
