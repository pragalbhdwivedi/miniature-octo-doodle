# Agent Controller

Phase 7 is STARTED / PARTIAL. The read-only repository planning CLI is implemented
and deployed for an unprivileged VM acceptance run. A separate operator dispatcher
now adds PostgreSQL claims/audit and one controlled worker attempt. Independent
review, repair and publishing orchestration remain pending. Follow
the [roadmap](ROADMAP.md) and [AADI integration contract](AADI_DEVELOPMENT_INTEGRATION.md).

## Intended roles
- Architect
- Planner
- Implementer
- Tester
- Reviewer
- Security reviewer
- Documentation agent

## Integration
The controller will:
- read source from Git/GitHub
- work correctly from refreshed Git alone before adding Graphify/OpenViking
- optionally use Graphify for code relationships and OpenViking for context in Phase 9
- enforce deterministic policy before model/tool selection
- keep Jev disabled until separately approved live evaluation in Phase 11
- call LiteLLM for approved model access
- work in isolated repositories/workspaces
- record runs and exact action-bound approvals, with Telegram as the sole human
  control channel (Phase 8); WhatsApp is excluded
- create reviewable branches and draft PRs; human approval is required for merge
  and production deployment

AADI is the first managed development project. Its repository remains authoritative
for its own requirements, branch rules and production architecture. This controller
does not become an AADI production runtime dependency.

## Decision boundary
The controller must treat three things separately:

1. **authority/policy**: deterministic rules, permissions, data classes, approval requirements
2. **decision intelligence**: Jev choice/score/probability where evaluated
3. **generative execution**: local/cloud models accessed through LiteLLM

A model or Jev result cannot self-authorize production access, dangerous tools, private-data egress, or a broader provider fallback.

## Skills
Third-party skills/plugins are untrusted code/instructions until reviewed. The planned skills workflow should include provenance, licence review, least privilege, and security scanning (for example NVIDIA SkillSpector where technically appropriate) before activation.

## Safety
It must not receive unrestricted production credentials, Docker host socket access, or arbitrary host-level access.

## Implemented first milestone

`scripts/controller.py` reads only approved public GitHub repositories. It fetches
five recent commits into a fresh private temporary Git database with credentials,
hooks and redirects disabled; validates a bounded source archive; reads complete
bounded issue/open-PR inventories; and checks that the branch SHA did not advance.
The refresh has a 180-second deadline and preserves a 15GiB disk floor plus 1GiB
reserve. AADI's registry entry is disabled and cannot be selected.

Required governance: PROJECT.md, AGENTS.md, WORK_INSTRUCTIONS.md, PROJECT_STATE.md,
README.md, ARCHITECTURE, BUILD_STATUS and ROADMAP. Missing files block selection.
Tasks must be committed in `config/controller/tasks.json`. The manifest contains
one completed zero-spend synthetic dispatch acceptance task; it grants no
scheduling or production authority.
Each task has `id`, `issue`, `state` (ready/paused/done), `priority` (1..100),
`depends_on` (task IDs), and a worker `job` matching `config/worker/coding-job.json`.
The job must use this project's approved ref, explicit context/write paths,
operator-supplied sandbox commands, a reviewed capability alias and zero budget.

A ready task also requires an open issue labelled `gatewayai:ready`, no existing
assignee, no open PR mentioning that issue, and dependencies marked done with
closed GitHub issues. Duplicate ownership, cycles, unknown dependencies,
incomplete pagination, stale revisions and inconsistent project mappings fail
closed. Selection is deterministic by priority then task ID. GitHub metadata and
model text cannot add execution or publishing authority.

```sh
python3 scripts/controller.py --project gatewayai \
  --output-directory /private/operator-owned-controller-plans
```

The output directory must be outside the checkout, owner-only0700. Each new0600
JSON plan records source/governance/task/inventory hashes, recent commits, reasons
and a unique run ID. A plan is a review artifact, not a durable execution-state
backend or an approval. The separate dispatcher stores durable claims and audit
events in PostgreSQL; see [dispatch operations](CONTROLLER_DISPATCH.md).
`awaiting_operator_review` means eligible planning only. Revalidate repository
ownership/source and explicitly set a budget before any separate worker operation.
There is no automatic handoff or scheduler. The separate operator dispatcher
acquires durable claims only after exact-request approval.

VM acceptance used Linux UID65534 with no sudo/Docker/provider/GitHub credentials.
It fetched current main and correctly blocked because main had no committed task
manifest at that checkpoint. This is real refresh/deny evidence; positive task
selection is tested with synthetic issue/PR fixtures. No provider spend or GitHub
mutation occurred. Larger/private repositories require separate activation.

## Remaining Phase 7 acceptance

PostgreSQL run/event persistence, atomic claims and controlled operator dispatch
passed the subsequent live milestone. Remaining work: independent review; bounded repair;
source/ownership revalidation before publication; and end-to-end AADI acceptance.
Telegram action-bound pause/resume remains Phase 8. No service/daemon or new
container image was installed for this first planning milestone.

## Bounded review and publication increment

Independent fresh-context review and operator-owned sandbox tests now gate the
artifact. One repair may run within the aggregate $1 original/review/repair
ceiling, followed by new tests and review. Publication requires a separate exact
final-artifact approval and current source/ownership, then creates only a draft PR.
See [review operations](CONTROLLER_REVIEW.md) and BUILD_STATUS for actual acceptance.
No scheduler, merge/deployment authority, AADI activation or Telegram integration.
