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
| #13 isolated coding worker | Reviewed/reconciled; draft retained | 73 existing WSL tests pass, refreshed main includes dashboard/storage fix. Live publisher acceptance blocked by missing scoped credential. |

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
- PR13 reconciled head `52fb798` preserves both worker and dashboard evidence.
  It is not merged and Phase6 completion is not claimed.

Reviewed boundaries include selected-project Docker operations, private secret
storage, preserved volumes/ledger, zero-spend recovery copies, pinned images,
default-deny Kubernetes networks, offline worker execution, exact artifact review
and create-only publishing. Source review/unit/CI evidence does not close the
separate live publisher, clean-host restore, reverse cutover or client gates.

Phase7 starts on a draft branch stacked on PR13. It introduces only a read-only
planner; durable PostgreSQL run state and execution orchestration remain pending.
