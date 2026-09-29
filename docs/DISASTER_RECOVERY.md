# Disaster Recovery

Goal: rebuild the platform on a clean machine using this repository plus separately protected secrets/backups.

## Recovery order
1. Obtain a supported Windows/WSL2/Docker environment and the trusted source revision.
2. Obtain the protected backup bundle and exact pinned images; do not regenerate
   secrets for existing databases or start applications on the restore target yet.
3. Run preflight and `scripts/recovery.ps1 -Action verify -Backup <physical-path>`.
4. Restore with `-Action restore` into a fresh recovery project/volumes. The tool
   reconstructs containers from archived source and retains original databases.
5. Verify restored file hashes, database integrity, administrator sign-in,
   restricted gateway key, model discovery and the monthly ledger.
6. Keep zero budget, provider keys disabled and networks isolated until deliberate
   cutover. Never run both copies as spend-enabled gateways.
7. Before cutover, stop the old writer and reconcile all post-backup spend/debits.
8. Reconnect providers deliberately; repeat bounded provider/browser validation.
9. Restore optional modules only if previously approved/installed. None are part
   of the core recovery bundle. Reinstall model weights separately if authorized.

See [Backup and Restore](BACKUP_RESTORE.md) for commands, paths, measured scope
and limits. The automated drill stops its recovered containers and preserves data;
it does not perform cutover or off-machine backup transfer. New-machine and
power-loss recovery remain distinct from a successful same-host rehearsal.

The repository alone must never contain production secrets or private datasets.
