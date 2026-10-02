# Admitted development tasks

`development_change` allows real application source changes and regression tests.
It is distinct from the older `test_addition` operation, whose AST preservation
contract remains unchanged. Each task names immutable source SHA, exact context,
writable and staged files, and an operator-owned `development_profile` key.
The source adapter must explicitly admit any new file; an empty baseline is not
permission for a coder to invent additional paths.

Profiles contain only `image`, `commands`, `acceptance_tests`, `timeout_seconds`
and `minimum_tests`. `image` is an already-installed immutable Docker SHA ID.
One to four fixed Python unittest commands run for baseline and candidate.
The existing acceptance files are read-only to the coder; separate writable
regression files can be added or changed. Source/test manifests contain at most
eight exact public text paths. Replacement files are at most 32 KiB each and
64 KiB total. A task must actually change application source.

Example operator profile (replace the illustrative digest):

```json
{
  "image": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "commands": [["python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]],
  "acceptance_tests": ["tests/test_existing.py"],
  "timeout_seconds": 90,
  "minimum_tests": 1
}
```

Each suite uses a disposable non-root container with no network, no capabilities,
read-only root and source, a bounded temporary filesystem, process/memory/CPU
limits and bounded output. No host home, credentials or Docker socket are mounted.
The worker forcibly removes the named container in a `finally` block, including
when the Docker client times out. Images and dependencies are never downloaded.
Commands are operator configuration, not coder output. The Windows worker
retains broker authority; generated Python is never imported or executed by it.

Both baseline and candidate must pass, without skipped tests or reduced test
count. Evidence records source, source snapshot, profile, output and candidate
digests. Independent review receives the exact source diff plus both test
receipts and must assess behavior, compatibility, meaningful regression coverage
and security. Tests and review must bind the same candidate before publication;
changing the acceptance profile invalidates old receipts. Test diagnostics are
not a proof of production service acceptance or adversarial code correctness.

The local lane supports the explicitly configured installed coding models
`devstral-small-2:24b` and `qwen3:4b-instruct`. The separate thinking model remains
the planner. No model is downloaded or selected as an automatic retry after an
uncertain inference. Responses must identify the exact configured model.

Local development prompts contain the complete writable files and complete task
requirements. Read-only file contents are explicitly omitted; their paths, byte
counts and SHA-256 hashes remain, together with the complete snapshot digest.
The broker retains all original files for tests, and independent review still
receives the full bounded candidate diff and test evidence. If omitted context
is needed, the coder must explain the missing context and return unchanged
writable files, which cannot pass development acceptance. There is no silent
truncation. Complete local prompts must fit 24,000 bytes, with 8192 context and a
3072 output-token ceiling. Incomplete output remains held for reconciliation.

On 2 October 2026, a Devstral run with roughly 7000 prompt tokens timed out at
600 seconds on predominantly CPU execution; measured generation was about 1.2
tokens/second. That run was cancelled and its evidence retained. The installed
4B instruct model is an operator-selectable lower-cost CPU coder for compact
tasks; successful inference and acceptance must still be verified separately.
Configured `local_fallback` preserves immutable task ownership while reporting
the actual local model. Tests and independent review remain required.

Verified 2 October 2026: offline contract/worker tests and actual existing Docker
image execution. A source change with a new regression test passed (baseline one
test, candidate two); an incorrect replacement failed the regression. No new
image/model was installed. These checks do not establish deployment of these
modules, actual model generation, service integration or a production release.

## Owner intake and scheduling

`development_enabled` matches owner requests to configured `development_scopes`.
Qwen selects only a scope identifier. Paths, test commands, repository, coder
and complexity remain operator-owned. Uncertain classifications do not repeat.
Requests outside the configured scopes become `needs_scope` with an explanation.
The existing SUP identifier is retained upon admission.

Roadmap recipes are finite and consumed once. Add a new recipe ID when review
produces a new requirement; completing a task does not authorize unrelated work.
A clean source is refreshed only while no task on that project is executing.
An admission whose acknowledgement was lost replays its immutable saved catalog
entry. At most three tasks are active. The owner authorized 80 cloud stages/day.

`openai_api_review` configures the Windows broker with `enabled`, `ssh_host`,
`remote_script` and `remote_config`. Linux holds the review-only gateway key and
atomic API-token ledger. Responses bind a canonical request ID and candidate
hash; model provenance, usage and unverified free billing stay in the audit.
An uncertain API result is held rather than retried or replaced by another call.
The adapter allowance is separate from provider subscription quotas.

Verification: all three isolated source profiles passed their baselines (5 ERP,
20 feed and 17 gateway tests). A mapping module import smoke check also passed.
These are module-level checks; project integration CI and PR review remain
required. No new images or model weights were downloaded.
