# ADR 0011: Debian control plane after local Kubernetes validation

Date: 2026-09-29
Status: Proposed implementation of the user-authored roadmap in PR #11; not merged.

## Context

PR #11 at `223bb00` defines k3d/K3s as developer validation only and prioritizes a
dedicated Debian VM, isolated worker, controller and Telegram approvals. Existing
Phase 4 API, browser, policy/isolation and pod/PVC recreation evidence meets that
local scope. Older status text made live data/provider migration a Phase 4 gate.

## Decision

Close Phase 4 only for its revised developer scope. Preserve every unvalidated
live migration, off-machine recovery and production limitation. Prepare Phase 5
using the existing three-service Compose and deterministic policy contracts.
Require an identified dedicated target before remote inspection or deployment.

Recommend Debian 13, 4 vCPU, 8 GiB RAM and at least 60 GiB disk for initial VM
planning, with no GPU. Debian 12 remains a supported preflight candidate. These
are initial sizing recommendations, not measured Debian capacity guarantees.
Keep the 12 GiB core reserve and 15/25 GiB critical/warning storage thresholds.

Start with fresh test state, blank provider credentials, zero spending and Jev
disabled. Later migration must preserve data and monthly admission history and
must be explicitly approved. Do not infer recovery acceptance from a preflight.

Build the worker/controller before adding optional context and local inference.
Telegram is the sole planned approval channel. AADI retains its own architecture,
branch rules, deployment decisions and independent production operation.

## Consequences

The Windows deployment remains live. The new read-only preflight does not install
Docker, prepare secrets, pull images, create a VM or start services. Linux startup,
protected secrets, controller foundation and Linux recovery are still outstanding.
Full Kubernetes service migration belongs to Phase 12, not local Phase 4 acceptance.
