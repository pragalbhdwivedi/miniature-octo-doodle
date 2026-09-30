# Backup and Restore

Phase 3 provides a consistent cold backup and a separate recovery rehearsal.
See BUILD_STATUS for actual tests; implementation alone is not recovery evidence.

For the separate Phase 5 Linux VM, use [Linux core recovery](LINUX_CORE.md#local-backup-and-restore-drill).
The Windows commands below do not operate that VM.

```powershell
./scripts/recovery.ps1 -Action backup
./scripts/recovery.ps1 -Action verify -Backup 'FULL-PHYSICAL-BACKUP-PATH-PRINTED-ABOVE'
./scripts/recovery.ps1 -Action restore -Backup 'FULL-PHYSICAL-BACKUP-PATH-PRINTED-ABOVE'
```

Run from a clean committed checkout on the supported Windows/Docker Desktop
host. Existing pinned images must be available; the scripts never pull. Python
3.12+ is required. No optional service, local model or live Jev is included.

## Backup contents and interruption

Before creating a backup, running environments (including image defaults), mount
targets/sources/modes and configured images must match the local configuration.
Bound configuration and gateway source files newer than container startup are
rejected conservatively; reconcile configuration and restart/recreate the affected
services first. Do not backdate files to bypass this freshness check. A PostgreSQL
TCP authentication probe also checks the actual stored password: changing
`POSTGRES_PASSWORD` in Compose does not rotate an existing database's password.
Source fingerprints are checked through capture to reject concurrent edits.
Errors never print environment values or credentials.

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
Packaged Windows terminals can redirect this folder into their `LocalCache/Local`
directory. The script resolves and prints the physical path; use that exact path
for restore, native tools and any later protected copy. Docker and Windows must
see the same files. A mounted-file visibility check runs before restore creates volumes.
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
that prefix. No recovery ports are published. Both recovery networks are internal,
cloud keys are omitted, allowance is zero,
Jev stays disabled and restart policy is off. Eight restored aliases may still be
listed, but inference is denied. This prevents an isolated drill from duplicating
real spend or sending stored data to a provider.

The drill checks a full PostgreSQL dump read to `/dev/null`, SQLite integrity,
service health, restored administrator
sign-in, the existing restricted inference key, model discovery and zero-budget
denial through container-local HTTP. The restored gateway also runs synthetic
primary/fallback, privacy, budget and concurrency probes on loopback. No real
provider inference is requested. It verifies the restored policy ledger remains
byte-for-byte unchanged. This deliberately isolated copy has no browser endpoint;
the original deployment's localhost checks are recorded separately.
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
