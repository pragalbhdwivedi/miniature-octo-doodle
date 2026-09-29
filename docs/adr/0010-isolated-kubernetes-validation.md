# ADR 0010: Isolated local Kubernetes validation before cutover

Status: accepted for Phase 4 implementation, 2026-09-29.

## Context

Phase 3 same-host recovery is merged and tested. The user requested Phase 4;
new-machine recovery is paused pending their Kubernetes setup. Docker Desktop's
existing Kubernetes cluster serves unrelated workloads. A second live gateway
with an empty ledger could reset admission accounting.

## Decision

Use the documented k3d target in a dedicated cluster, with private kubeconfig,
explicit context and loopback ports. Do not modify the existing cluster.
Deploy fresh core data with random credentials, no provider keys, zero budget,
Jev disabled and deny-by-default networking. Reuse tracked gateway policy code
and pinned application images. Keep one gateway replica and Recreate updates for
the SQLite ledger. Validate with Compose stopped, then resume it.

The k3d node is privileged infrastructure operated by the local administrator;
application pods receive no privileged mode, host mounts, Docker socket or
service-account token. No coding agent is installed. Secrets encryption and local
ACLs protect storage but do not restrict a host/cluster administrator.

## Consequences

The node stores separate core image copies (about 4 GiB host delta including
infrastructure); no model weights are duplicated. Three fresh PVCs exercise
persistence without copying live chats or credentials. Runtime API/policy checks
pass; browser acceptance remains pending.

This does not validate a separate machine, provider cutover or Kubernetes backup.
A future migration must preserve records and reconcile monthly budget debits,
explicitly enable provider egress, and pass bounded live tests. Optional modules
remain deferred. Phase 4 stays PARTIAL until its remaining gates are completed.
