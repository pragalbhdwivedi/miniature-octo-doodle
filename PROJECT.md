# miniature-octo-doodle project synchronization contract

This file is the mandatory synchronization entry point for every ChatGPT Work session, coding agent, reviewer, and automation working on this repository.

Repository: `pragalbhdwivedi/miniature-octo-doodle`  
Canonical baseline: the repository default branch, currently `main`, unless an active task explicitly names another branch or pull request.

## Mandatory refresh before work
For every substantive project prompt:
1. Fetch the current repository/default branch.
2. Resolve current HEAD.
3. Read this file.
4. Read `PROJECT_STATE.md`, `AGENTS.md`, `WORK_INSTRUCTIONS.md`, and `docs/BUILD_STATUS.md`.
5. Inspect recent commits.
6. Inspect open/recent pull requests and issues relevant to the task.
7. Read the latest relevant architecture, ADR, deployment, security, storage, and troubleshooting documents.
8. Reconcile the requested work against repository state before acting.

## Source-of-truth rule
Fresh GitHub state outranks remembered chat context for current implementation status.

Distinguish:
- merged on main
- open PR
- issue/planned work
- documented architecture
- actually installed/tested state

Never silently promote planned or documented work to implemented.

## Change discipline
- preserve files and history
- prefer additive/narrow changes
- use reviewable branches for substantial implementation
- inspect diffs before merge
- keep secrets/runtime data out of Git
- update state/build evidence when implementation status changes

## Completion discipline
Before reporting completion:
1. refresh repository state if concurrent changes are plausible
2. inspect final diff
3. run relevant tests/checks
4. update `docs/BUILD_STATUS.md`
5. record what changed and what remains
6. separate repository changes from machine-local deployment state

A conversation is not the database. GitHub is.
