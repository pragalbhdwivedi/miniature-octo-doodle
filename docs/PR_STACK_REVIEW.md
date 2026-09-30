# PR stack review - 30 September 2026

GitHub heads, CI, review comments, changed source, runtime evidence and repository
governance were refreshed before the authorized reconciliation. Existing local
dashboard files were left untouched; review used an isolated Git worktree.

| PR | Disposition | Evidence / remaining scope |
|---|---|---|
| #7 historical Jev design | Closed as superseded | PR8 implements deterministic routing; Jev remains disabled. No old branch was merged over current state. |
| #10 developer Kubernetes | Reviewed, fixed and merged | Open P1 storage finding corrected in `30f2333`; separate Docker-drive reserve tests pass. Exact successful CI runs are listed below. |
| #11 roadmap | Merged through PR12 ancestry | Existing roadmap commits retained; no duplicate implementation. |
| #12 Linux control plane | Reviewed, reconciled and merged | 49 WSL tests and fresh CI passed. Operational Phase5 remains partial for the documented recovery/client gates. |
| #14 service dashboard | Reviewed, reconciled and merged | URL rendering uses text nodes/protocol checks; application login/CSRF boundaries retained; fresh CI green. Existing live acceptance retained; no repeat deployment. |
| #13 isolated coding worker | Reviewed and merged | Live draft PR #16 verified exact artifact/source and unchanged main; fresh CI passed. |
| #15 read-only controller | Reviewed and reconciled onto main | Read-only scope; 84-test suite. Execution orchestration remains pending. |
| #16 publication acceptance | Draft retained | Synthetic single-file live publishing proof; no application feature to merge. |

The P1 finding was substantive: Kubernetes cluster/deploy checked only C: while
Docker Desktop could use another drive. Preflight now applies the 8/4GiB reserves
to every discovered repository/Docker drive, using unrounded free space. Tests
with C:50GiB and D:18GiB reject both pulls and permit zero-reserve inspection.

Exact merge/check evidence:

- PR10 merge `6316b3527bf7b27c379cf4d93c459520c7261753`; head
  `30f2333851e3d8e106979bef794e6b567fb1dad7`; CI36699758184/36699751206 success.
- PR12 merge `c38d357a7aca22c6c9a3adac71455560c9db630b`; reconciled head
  `b5c676afebe03c089c079519e5a256eda24f6a0a`; CI36700039221/36700034415 success.
- PR14 merge `b5843bbe091ccab9a12d95dd812dc167dc88db16`; reconciled head
  `44568e93c4e06fff532066fdbcf0736773b6f9ef`; CI36700234967/36700228151 success.
- PR13 merge `5c9684b129849edad7758093a095d422dbe1e5b7`; head
  `f0c13148bbdc31762de84176a5b05a72e77f7ce0`; CI36741350063/36741342519 success.

Reviewed boundaries include selected-project Docker operations, private secret
storage, preserved volumes/ledger, zero-spend recovery copies, pinned images,
default-deny Kubernetes networks, offline worker execution, exact artifact review
and create-only publishing. Source review/unit/CI evidence does not close the
separate clean-host restore, reverse cutover or client gates. Live publisher
acceptance is now recorded in BUILD_STATUS; broader token scope is not API-proven.

Phase7 PR15 is reconciled onto main after PR13 merged. It introduces only a read-only
planner; durable PostgreSQL run state and execution orchestration remain pending.

## Durable dispatch increment

PR #18 added PostgreSQL claims and controlled dispatch after CI passed. PR #19
fixed the pre-existing smoke JSON escaping exposed by live execution, retaining
the failed run. Positive zero-spend dispatch and completion-failure reconciliation
then passed. The implementation and correction are merged; exact tested results
and remaining Phase7 scope are in BUILD_STATUS.

## Review, repair and publication increment

PR #22 passed push/PR CI (36749975334 / 36750047606), had no open review comments,
and merged with exact head `c5b90e1b4eba98bd027a7581d418cdd868153628` pinned.
Merge: `dca030b99cc090e1c2fd1473cce6e55f9e4b5c45`. Live review, one repair,
re-review and gated publication passed afterward. Draft PR #23 is the synthetic
single-file result and stays unmerged, like PR #16. Issue #21 is closed; no wider
Phase 7 or Phase 5 gate is inferred from these bounded results.
