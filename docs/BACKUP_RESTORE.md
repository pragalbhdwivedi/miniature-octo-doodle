# Backup and Restore

Phase 3 provides a consistent cold backup and a separate recovery rehearsal.
See BUILD_STATUS for actual tests; implementation alone is not recovery evidence.

```powershell
./scripts/recovery.ps1 -Action backup
./scripts/recovery.ps1 -Action verify -Backup "$env:LOCALAPPDATA/GatewayAI/recovery/backup-TIMESTAMP"
./scripts/recovery.ps1 -Action restore -Backup "$env:LOCALAPPDATA/GatewayAI/recovery/backup-TIMESTAMP"
```

Run from a clean committed checkout on the supported Windows/Docker Desktop
host. Existing pinned images must be available; the scripts never pull. Python
3.12+ is required. No optional service, local model or live Jev is included.

## Backup contents and interruption

The script requires all three source services healthy, checks storage, stops only
this project's UI/gateway and then PostgreSQL, and rejects unclean shutdown or
remaining volume writers. It captures all files from `postgres-data`,
`open-webui-data` and `policy-data`, including SQLite sidecar files. PostgreSQL's
whole cluster is copied only while stopped; external tablespaces/links are rejected.
The original containers resume in a finally block, with a health wait, even after
a snapshot failure. If restart fails, preserve everything and run core diagnostics.

Each backup contains those volume tar files, local `.env`, resolved Compose,
rendered gateway/policy configuration, a Git source archive and a SHA-256 manifest
with the source commit. Image layers are not duplicated. A missing manifest or
failed hash check makes a backup unusable. Hashes detect accidental corruption;
they do not authenticate a maliciously replaced backup. Restore trusted bundles only.

## Private storage

Artifacts live under `%LOCALAPPDATA%/GatewayAI/recovery`, outside Git and OneDrive.
The PowerShell entry point restricts NTFS access to the current user and SYSTEM.
Backups contain credentials, accounts and potentially chat content. They are
**not encrypted by this tool**; ACLs do not protect against administrators or disk
theft. Use an approved encrypted/off-machine destination for disaster protection,
preserving access restrictions. No remote upload, retention or deletion is automatic.
Keep the database password, LiteLLM salt/master key and WebUI secret together with
their original database snapshot. Never regenerate these during recovery.

## Isolated restore and clean container rebuild

Restore refuses existing project directories, containers, networks and volumes.
It extracts the tracked source into a fresh directory, creates three empty volumes,
restores them and compares every file's hash, owner and mode before startup.
It creates fresh containers from the pinned images using only recovered configuration
and archived source. The original repository's bind mounts and volumes are not used.

The new project is named `gatewayai-recovery-TIMESTAMP`; optional `-Name` must use
that prefix. Default ports are 127.0.0.1:4300 (UI) and :4400 (gateway). Alternate
ports can be supplied with `-WebUIPort` and `-GatewayPort`; live core ports are denied.
Both recovery networks are internal, cloud keys are omitted, allowance is zero,
Jev stays disabled and restart policy is off. Eight restored aliases may still be
listed, but inference is denied. This prevents an isolated drill from duplicating
real spend or sending stored data to a provider.

The drill checks service health, both localhost spellings, restored administrator
sign-in, the existing restricted inference key, model discovery and zero-budget
denial. It verifies the restored policy ledger remains byte-for-byte unchanged.
It stops recovery containers in a finally block and retains their volumes and a
private `result.json`. It never overwrites the live deployment or deletes data.

## Recovery boundaries

This is a same-host clean container/volume rebuild, not a new-machine, image
download, OS reinstall, host reboot or power-loss test. Physical PostgreSQL restore
requires the recorded compatible image/architecture. Retained recovery copies consume
disk until the user explicitly authorizes removal. The scripts do not perform cutover.

Before a real cutover, stop the old writer, verify the restored state and reconcile
all post-backup monthly admission debits. An older ledger can restore an already-used
allowance; keep spending disabled until reconciled. Provider keys must be reconnected
deliberately and bounded live/browser checks repeated. RPO is the time since the last
successful backup; measured drill duration is not a guaranteed RTO. A local backup
alone does not survive loss of this laptop.

References: [PostgreSQL filesystem backup](https://www.postgresql.org/docs/16/backup-file.html),
[Docker volume backup and restore](https://docs.docker.com/engine/storage/volumes/#back-up-restore-or-migrate-data-volumes).
