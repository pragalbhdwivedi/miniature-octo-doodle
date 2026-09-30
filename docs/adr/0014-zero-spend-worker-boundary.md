# ADR 0014: Establish the worker execution boundary before agent activation

Date: 30 September 2026. Status: implemented and target-tested for the execution
boundary; overall Phase 6 remains partial.

The user requested the next phase after the dedicated VM/internal HTTPS work.
Phase 6 requires isolated development execution before a repository-driven
controller or optional memory/model components. Outstanding Phase 5 recovery
and client validation gates remain explicitly open.

Use an operator-only broker and disposable non-root, offline Docker containers
on the existing VM for the first bounded milestone. The broker resolves an
allowlisted public repository/ref without credentials. Workers receive only an
immutable snapshot and explicit job, execute in size-limited tmpfs, and return
allowlisted artifacts for review. They never receive host control or credentials.

Enforce CPU/RAM/PID/time/output/storage limits, serialize broker runs, refuse
source links/special files and compare output to immutable input. Use an
independent container deadline so loss of the broker cannot leave an unbounded
job. Preserve the live gateway and budget ledger without adding worker spend.

This milestone deliberately fails closed for model budgets and publication.
The later coding-agent and publishing adapters must bind authority to the exact
run/repository/branch, keep credentials outside the worker and enforce budgets
through LiteLLM. Container isolation shares the host kernel; broader untrusted
execution may require a separately approved worker VM/hardened runtime.
