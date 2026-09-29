# ADR 0009: Cold backup and isolated recovery rehearsal

## Decision - 2026-09-29

Use a short core-only shutdown to capture a consistent PostgreSQL cluster,
WebUI volume and policy ledger together. Store source/configuration and hash
manifests alongside the snapshot in an ACL-restricted folder outside Git/OneDrive.
Reuse the pinned existing images; add no backup service or host socket mount.

Restore only to a fresh recovery namespace and volumes. Verify every restored
file before starting rebuilt containers. Internal networks, removed cloud keys,
zero budget and disabled Jev prevent a rehearsal from becoming a second spender.
Preserve all original and restored volumes. Production cutover and off-machine
encrypted retention require separate deliberate operations.

## Consequences

Brief downtime is required. The physical PostgreSQL copy is version/architecture
specific. File hashes prove integrity, not backup authenticity. NTFS ACLs provide
local access restriction, not portable encryption. A stale ledger must never be
used to silently reset monthly spend. Backup age bounds RPO; restoration timing
is measured separately. See BACKUP_RESTORE and BUILD_STATUS for the tested scope.
