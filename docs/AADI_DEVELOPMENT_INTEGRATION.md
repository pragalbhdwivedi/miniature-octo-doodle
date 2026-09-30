# AADI development integration contract

> Roadmap contract | 29 September 2026  
> Platform repository: `pragalbhdwivedi/miniature-octo-doodle`  
> First managed product repository: `pragalbhdwivedi/aadi`

## Purpose

This repository is the shared AI development/control platform for AADI and
future approved software projects. It provides the model gateway, development
controller, isolated coding workers, run state and human approval interface.

It is **not** the AADI application and must not become a required runtime
dependency for AADI production services.

## Source-of-truth boundary

For AADI work:

1. fresh `pragalbhdwivedi/aadi` GitHub state is authoritative for AADI;
2. AADI's `PROJECT.md`, `AGENTS.md`, project state, active issue/PR, ADRs and
   relevant handovers define the task and its boundaries;
3. this platform may select and execute only work that those records permit;
4. cached context, model output, Jev output or controller state cannot override
   a newer AADI repository decision;
5. if source records conflict or authority is unclear, the run pauses for human
   input rather than inventing a resolution.

## Project adapter

The Agent Controller should model every managed repository as a project adapter.

For AADI the adapter records at minimum:

```yaml
project: aadi
repository: pragalbhdwivedi/aadi
default_branch: main
bootstrap:
  - PROJECT.md
  - PROJECT_STATE.md
  - AGENTS.md
  - START_HERE.md
  - DOCUMENT_CONTROL.md
  - CHANGELOG.md
refresh:
  recent_commits: true
  open_pull_requests: true
  relevant_issues: true
workspace:
  isolated: true
authority:
  merge: human
  production_deploy: human
  consequential_action: human
```

A moving branch/PR must be resolved to the current SHA at run start and recorded
with the run.

## Development run lifecycle

```text
refresh repository
  -> reconcile issue/PR ownership and dependencies
  -> choose one bounded permitted task
  -> build minimum relevant context
  -> deterministic policy checks
  -> choose LiteLLM capability alias
  -> execute in isolated worker
  -> run deterministic tests/checks
  -> independent review
  -> bounded repair loop
  -> push reviewable branch
  -> create/update draft PR
  -> request human action only when needed
```

Initial logical AI roles are **planner, implementer and reviewer**. Deterministic
test runners are preferred over inventing a separate LLM "tester" where ordinary
test execution is sufficient.

## Model routing

The controller asks for capabilities rather than provider model names:

- `coding-fast`
- `coding-standard`
- `coding-hard`
- `architecture`
- `review`
- `documentation`
- `local-private`

LiteLLM and deterministic policy own the provider/model mapping. Jev may later
help choose among already-permitted routes after evaluation, but it never grants
authority or weakens data/provider restrictions.

## Human approval channel

Telegram is the only planned remote approval/input channel.

Use it for:

- requirement/architecture decisions;
- approval-required or policy-blocked runs;
- authentication/manual-input requests;
- budget-limit decisions;
- PR-ready notifications;
- pause/resume/cancel.

**WhatsApp is explicitly out of scope.** Do not implement it as primary,
secondary, emergency or fallback approval transport.

Approvals must be bound to the exact run/action and expire or be invalidated
when the underlying payload/commit changes.

## Authority boundary

The controller may initially:

- refresh repositories;
- create isolated workspaces/worktrees;
- create development branches;
- edit code and documentation;
- run tests and bounded development commands;
- repair ordinary failures within configured limits;
- commit and push its branch;
- create or update draft pull requests;
- report evidence and blockers.

It may not autonomously:

- merge to protected/default branches;
- deploy AADI production;
- execute real-data migrations;
- write fees, payroll, marks or institutional records;
- send real institutional communications;
- use unrestricted production credentials;
- change network/firewall/access-control/electrical systems;
- approve its own consequential action.

## Deployment separation

The platform deployment progression is:

```text
Windows + Docker/WSL2 development
        ->
dedicated Debian always-on control-plane VM
        ->
full Kubernetes deployment when justified
```

k3d/K3s may remain a disposable local validation environment for this repository.
It does not supersede AADI's own Kubernetes architecture decisions.

The control plane and coding worker are distinct trust zones. The always-on
controller/gateway should not expose unrestricted Docker/host control. Coding
workers may receive broader development tooling only inside isolated,
rebuildable environments with project-scoped credentials.

## AADI availability independence

If this platform is unavailable, AADI development may continue manually through
Git/GitHub and AADI's documented contributor workflow. AADI production must keep
operating without the development controller, LiteLLM development gateway,
Telegram bot, OpenViking, Graphify or coding workers.

## First implementation acceptance

The first AADI-controller milestone is accepted only when a synthetic/bounded
AADI task can demonstrate all of the following:

1. fresh AADI repository synchronization;
2. correct identification of an existing issue/PR owner;
3. one isolated development workspace;
4. capability-alias routing through the gateway;
5. bounded implementation and actual tests;
6. independent review;
7. draft PR creation/update;
8. Telegram pause/resume for one human-required decision;
9. no default-branch merge or production access;
10. complete run provenance including repository SHA, task, prompts/versions,
    route, commands/tests, result and human approvals.

This contract defines development tooling. It does not itself approve any AADI
feature, provider, production deployment or data access.
