# Ongoing assigned-task coordination

The owner delegates routine reversible decisions and issue/draft-PR publication.
Each subtask has one coder; unrelated work gets its own issue and draft PR. The
controller preserves the completed pilot and adds an `ongoing` state record.
See [decision and boundaries](adr/0020-assigned-subtasks-and-delegated-drafts.md).

## Work flow

1. Read the operator-owned catalog pinned to current AADI Dev. Qwen orders its
   existing tasks once; malformed local planning falls back to catalog order.
2. Admit up to three independent owners with disjoint writable files. Shared
   immutable read context is permitted. Reserve claims before inference.
3. Run ready Antigravity, Codex and local Devstral lanes concurrently. Only one
   task can occupy the local hardware lane; Qwen remains the coordinator.
4. Preserve baseline tests, run the isolated synthetic suite, and bind the result
   to the candidate hash. A fresh compact reviewer sees the added tests and scope.
5. Automatically return a failed candidate for one repair. Keep further failures
   for review while other independent work continues.
6. Create/update the task issue and draft PR using deterministic markers and
   ordinary pushes to its own branch. Exact source/bytes and confirmed draft
   receipts are required. No integration, merge or deployment follows.

GitHub write intents and readback prevent duplicate issues/PRs after uncertain
responses. Unobserved ambiguous writes stop for reconciliation. Runtime evidence,
credential-helper material, catalog and account metadata remain outside Git/sync.
Models never receive the operator's GitHub, SSH, database or Docker credentials.

## Model and usage policy

Focused Codex tasks use the installed Luna route; harder tasks use Sol and
explicit demanding work uses Astra. One repair may escalate one tier. The runtime
validates model/effort against installed metadata before inference. Reported
tokens are actual observed CLI usage; missing usage is unknown, not zero or a bill.

Antigravity's official CLI provides explicit model selection and native account
authentication. Shared Gemini and Claude/GPT quota groups must be considered
across both five-hour and weekly windows. Select an eligible suitable model before
starting; never retry an ambiguous completed generation under a different model.
No paid API or alternate-account fallback is configured.

Routine native tasks prefer Flash Low, then Medium if Low is unavailable.
Complex tasks prefer Pro; the other subscription group offers Sonnet, GPT-OSS
and, for demanding tasks, Opus when present in the native inventory. Both weekly
and five-hour windows must have capacity. If all suitable native groups are
exhausted before inference, preserve the queued claim and wait until the observed
reset, then recheck live quota. This path consumes no inference reservation.
An explicit Codex quota denial before generated output may use an eligible
native model; generic failures or partial generations never trigger fallback.

The installed `devstral-small-2:24b` is an additional local coder, not a replacement
for Qwen coordination. Its loopback-only Ollama request has no tools, 10 KB maximum
prompt, 4096-token context, 512-token output ceiling and a ten-minute deadline.
It returns only one new test method; the operator inserts it without changing
existing AST nodes. It receives compact synthetic test additions and the same independent cloud
review as other coders. Local generation does not consume cloud quota; the
review does. Cloud budget exhaustion does not prevent eligible local generation.
Truncated, failed or ambiguous local generations retain their claims.

Idle checks call no models. Twelve cloud-stage reservations per UTC day and one
repair per task are the initial conservative limits; they are not a dollar or
exact-token ceiling. There is no endless task generation to consume remaining
quota. The admitted backlog waits when empty, while Telegram remains available.

## Telegram and operation

Status/Outputs include the ongoing task summary and draft links. Ongoing work,
Pause ongoing and Resume ongoing buttons acknowledge the click and return the
new state. Pause stops new stages; an already reserved stage may finish and save
its evidence. Original fixed-answer/Custom reply controls remain available.

Technical holds explicitly say that no owner answer is requested. Decisions lists
those holds and available drafts rather than implying an approval is pending.
Usage and the comprehensive report include actual model routes and observed
input/output tokens for new tasks; lease tokens and local credential paths are
excluded. Operator recovery does not grant destructive authority.

The existing one-minute native timer invokes the ongoing worker after the pilot
is idle. Protected configuration explicitly enables it. Each stage uses a
durable VM lease plus a local process lock. Disabling `ongoing_enabled` in the
operator config stops new ongoing ticks without deleting claims or evidence.

The first catalog contains synthetic receiver-warning, missing-history ordering
and denied-access input-preservation regressions, plus a compact ERP manifest
preservation task for the local coder. Expanding beyond this admitted
test scope needs a corresponding validator/test contract; a generic issue title
does not grant arbitrary shell or production access.

## Validation boundary

Tests cover separate ownership, stale source, hash binding, baseline preservation,
unsafe test constructs, sandbox restrictions, duplicate publication recovery,
quota groups and bounded escalation. BUILD_STATUS records live CLI, simultaneous
generation, tests, reviews and draft receipts separately as they are observed.

## Native CLI installation and recovery

The operator-authorized Windows installation used the
[official Antigravity CLI installer](https://antigravity.google/docs/cli/install/),
verified its SHA512 and Google LLC Authenticode signature, and installed version
1.2.14 under the user's physical app-data `agy/bin` directory. Windows app virtualization
redirected the install, so both the scheduler and user PATH use its resolved
physical location rather than the logical LocalAppData alias;
new terminals can invoke `agy --version`. Existing native Google sign-in worked.
No model weights or optional images were downloaded. This explicit installation
was authorized despite the existing optional-install storage hold; C: afterward
had 12.22 GiB free, so further optional downloads remain held.

The unattended profile is intentionally proposal-only: strict permissions deny
file, shell, URL and MCP tools; its dedicated `aadi-proposal` agent can return a
structured result through `finish`. Credits are disabled. The adapter verifies
the profile and effective model/agent/permission mode and rejects other actual
tool calls, delegation and multiple-turn results. Native inventory metadata
lists global tools even for this restricted agent; it is not execution evidence.
Authentication files are neither copied nor sent to models. Quota metadata is
queried through native `/usage`; it is not inferred from the screenshot.

Readback uses the exact GitHub resource returned by a create operation because
repository lists can lag a successful write. Uncertain writes reconcile existing
markers without duplicate creation. Recovery also preserved a valid saved Codex
proposal when the initial test validator omitted its existing `codes()` helper;
the corrected isolated run passed without another coding call.

The operator-owned catalog is reloaded each tick. New IDs are validated and
appended idempotently with a receipt timestamp; edits or removals of retained
tasks are rejected. This is a file handoff, not permission for a model to change
the catalog or create arbitrary production work.

## Live evidence, 2 October 2026

Pinned AADI Dev: `f22cc9ce4e3594f1f8c461071e3f6d6ffcacff0d`. Main and Dev
were not changed by this four-task activation. Each candidate passed independent
review and isolated tests, then received its own confirmed draft PR.

| Task | Actual coder | Isolated tests | Draft |
|---|---|---:|---|
| Missing-history ordering | Codex Luna Medium | 29 | [#27](https://github.com/pragalbhdwivedi/aadi/pull/27) |
| Feed warning combination | Gemini Flash Medium | 20 | [#29](https://github.com/pragalbhdwivedi/aadi/pull/29) |
| Denied identity input | Gemini Flash Low | 23 | [#32](https://github.com/pragalbhdwivedi/aadi/pull/32) |
| Rejected ERP manifest preservation | Local Devstral Small 2, with operator correction | 4 | [#33](https://github.com/pragalbhdwivedi/aadi/pull/33) |

The combined overlay of all four accepted candidate hashes passed 76 tests in
an isolated container. No candidate was merged into the source checkout. The
AADI policy/status handover is separately reviewable in
[documentation PR #31](https://github.com/pragalbhdwivedi/aadi/pull/31).

Local acceptance required recovery: a full-file call reached its ten-minute
limit; the compact method call then completed in 169 seconds using 1,136 input
and 185 output tokens. The adapter now normalizes an unambiguous method placed
in the wrong structured field. Independent review required replaying rejection
on the same object; the operator corrected that saved method, preserved earlier
artifacts, reran all four tests and obtained a fresh passing review. No further
coding call was made for these corrections. Routine review stays on Luna Low;
a recovery counter alone no longer escalates its model tier. This demonstrates
a usable local contribution, not yet a clean unattended repetition of the updated
local path. Quota-group switching and observed-reset waiting passed controlled
unit tests; actual account exhaustion was not forced to manufacture evidence.

Telegram delivery receipts confirm the corrected technical-recovery notices and
all four draft notifications. Final queue state is idle with no active lease;
new admitted catalog entries can continue through the existing timer.

### Review-cycle routing

A task's lifetime attempt number remains monotonic for audit. Model escalation
uses the attempt offset within the current correction cycle: a newly requested
correction starts at the normal route, and its one permitted automatic repair
may escalate once. Repeated PR reviews therefore do not exhaust model routing
merely because earlier attempts exist. Invalid cycle counters fail closed.
