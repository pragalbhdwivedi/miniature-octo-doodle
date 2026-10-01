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
as gateway API keys. CLI installation is blocked while disk is below the 15-GiB
project floor. Do not change Spark privacy/access settings on the owner's behalf.

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
