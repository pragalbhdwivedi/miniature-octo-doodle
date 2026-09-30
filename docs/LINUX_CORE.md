# Linux core operations

Phase 5 now runs the migrated live Compose core on the approved Ubuntu VM.
Windows data, credentials and budget ledger were retained; Windows remains
stopped with restart disabled. The fresh zero-spend project described first below
is retained stopped as an independent test deployment. Use the migration/live
operations sections for the current runtime; do not start the old Windows ledger.
See BUILD_STATUS for acceptance evidence and remaining recovery limits.

## Fresh zero-spend deployment

Install Docker Engine and the Compose plugin from the
[official Ubuntu repository](https://docs.docker.com/engine/install/ubuntu/).
The approved administrator operates Docker through sudo; no worker, application
container or browser UI receives its socket. No optional images/models are needed.

Place the reviewed source at `/opt/gatewayai/source`, owned by root. Before startup:

```sh
sudo python3 /opt/gatewayai/source/scripts/debian-preflight.py --runtime-parent /srv
sudo python3 /opt/gatewayai/source/scripts/linux-core.py init
sudo python3 /opt/gatewayai/source/scripts/linux-core.py start
sudo python3 /opt/gatewayai/source/scripts/linux-core.py test
sudo python3 /opt/gatewayai/source/scripts/linux-core.py status
```

`init` refuses occupied runtime/project volumes and never overwrites credentials.
`start` pulls only the three digest-pinned images, checks storage before/after,
starts PostgreSQL and LiteLLM, provisions a restricted inference key and starts
WebUI. Repeating startup preserves credentials and volumes. Configuration is
strictly checked against reviewed source; provider activation is rejected.

Secrets/configuration live in `/etc/gatewayai` (0700, files 0600). The administrator
login is in `/etc/gatewayai/login.txt`; do not print it in logs or copy it into Git,
OneDrive or project notes. A protected laptop copy is recorded only in local VM notes.

## Browser and SSH access

Existing Windows and WSL clients have `gatewayai-direct` and
`gatewayai-via-bastion` aliases with strict host-key checking. Direct access is
permitted only from the recorded current laptop address; use the bastion alias
when that address changes. Outside-VPN acceptance remains pending.

```sh
ssh gatewayai-direct
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:3180:127.0.0.1:3000 gatewayai-direct
```

Open `http://localhost:3180` while the tunnel is running. It is an SSH-tunneled
address, not a publicly hosted URL. Existing laptop ports 3000 and 3080 remain
owned by the earlier Compose and Kubernetes environments.

Both Docker networks are internal. Docker Engine suppresses published bindings
when containers have only internal networks, despite accepting Compose's port
declarations. The Linux tool installs two systemd socket proxies listening only
on `127.0.0.1:3000/4000`. They use the installed systemd proxy binary as dynamic,
unprivileged users, without a Docker socket or secrets. PostgreSQL has no proxy.
See [Docker networking](https://docs.docker.com/compose/how-tos/networking/).

`start` refreshes proxy target addresses after container recreation. After a
manual container/network change, run `linux-core.py loopback` and `test` to refresh
and verify. The units are `gatewayai-open-webui.socket/service` and
`gatewayai-litellm.socket/service`. Docker and socket units are enabled at boot;
containers use `unless-stopped`. Deliberately stopped containers remain stopped.
Docker may change dynamic bridge addresses on reboot. The root-owned
`gatewayai-loopback-refresh.service` waits up to 300 seconds for all three
containers in the explicitly selected project to be healthy, then rewrites the
proxy targets. It is an administrator deployment service, not a worker/controller
API; no application receives its Docker authority. The proxies themselves remain
unprivileged. Wait for this oneshot unit to finish successfully before testing
HTTP after boot; early connections can reset while readiness/refresh is pending.
The selected live project is recorded in its systemd unit. Manual container
recreation still requires the appropriate loopback command.

## Local backup and restore drill

```sh
sudo python3 /opt/gatewayai/source/scripts/linux-recovery.py backup
sudo python3 /opt/gatewayai/source/scripts/linux-recovery.py drill
```

Backup briefly stops only this core, requires healthy matching source containers,
checks clean shutdown/no remaining volume writers, and resumes in a finally block.
It archives all three volumes, private runtime configuration and deployed source,
with SHA-256 checksums, in `/var/lib/gatewayai-recovery` (0700, archives 0600).
These fresh-project backups contain credentials and are not encrypted. They remain on the VM;
they do not protect against loss of its host/NAS.

`drill` creates a fresh backup, verifies it, extracts archived source/configuration,
restores into new named volumes and checks every file's content before startup.
Fresh recovery containers use existing pinned images, internal networks, no host
ports, blank provider keys, zero allowance and restart disabled. Health, restored
admin/scoped-key access, eight aliases, budget rejection, PostgreSQL full dump read
and SQLite integrity are checked. Recovery containers stop in a finally block;
volumes and evidence remain for review. No cleanup or production cutover occurs.

This is a same-VM fresh-project recovery rehearsal. The portable existing-backup
restore, live migration and encrypted-retention workflow are described below.
Separate clean-host recovery remains unvalidated. Checksums detect corruption, not malicious replacement;
only trusted, protected backup artifacts are suitable for recovery.

## Controller foundation and remaining acceptance

The core is an administrator-operated service boundary. Future controller state
belongs in a separate protected directory/account, with task IDs, repository/head,
approval state, bounded budgets and audit results persisted independently of chat.
Workers must have isolated workspaces, no core secrets/Docker socket and no AADI
production authority. These are design constraints; no controller/worker is installed.

Before a live Windows-to-VM cutover, back up and reconcile existing users/chats,
keys and the monthly admission ledger. Preserve the approved US$100 UTC-month
allowance and already-recorded debits; never activate another fresh ledger with a
duplicate allowance. A migrated deployment needs provider/browser acceptance and
a tested rollback. Phase 5 remains partial until its remaining recovery/migration
gates are satisfied; creating a fresh zero-spend core does not satisfy those gates.

## Windows migration tooling

`scripts/linux-import.py --backup /var/lib/gatewayai-import/<backup> --name
 gatewayai-recovery-<unique>` accepts the trusted Windows recovery bundle in a
root-owned 0700 directory, with regular 0600 files. Transfer over authenticated
SSH. The importer verifies hashes/archive safety, uses existing pinned images,
restores into new volumes, checks exact files/ownership, databases, existing login,
scoped key, eight aliases and unchanged budget ledger. It runs synthetic routing
checks and stops the restored containers. Provider keys are blank, budget zero,
all networks internal and no host ports are published. This is also an independent
existing-backup restore command; it does not create a new snapshot first.

For a final handoff, commit the reviewed tooling, then run Windows
`./scripts/recovery.ps1 -Action backup -KeepStopped`. A successful snapshot leaves
only the source core stopped, disables its restart policies and records a local
`.migration-handoff.json` guard. `manage.ps1 start` refuses while the guard exists.
A failed snapshot resumes the source; a failed handoff remains stopped for operator
inspection. Verify all three source containers remain stopped with restart=no
before activation. Raw Docker commands bypass the guard and must not be used to
restart an obsolete ledger.

Transfer and independently restore that final bundle. After the isolated tests
pass, `linux-cutover.py activate --work <restored-directory> --backup <bundle>
--handoff-sha256 <manifest-sha256>` checks the matching handoff and data, journals
activation, retains the existing USD100 allowance/credentials and exposes cloud
egress only to LiteLLM. It stops the separate fresh zero-spend core and switches
the existing loopback socket proxies. No old volumes are deleted. An interrupted
activation must be repaired using these same VM volumes; never restart Windows
against its old admission ledger.

Before activation, rollback means leaving the isolated VM copy stopped and
resuming the unchanged Windows core after confirming no live VM was activated.
After activation, ownership moves to the VM. Rollback requires a new cold backup
of the current VM, an independently validated Windows restore and a frozen-source
handoff in the reverse direction. Do not delete the guard or reuse stale Windows
data. This post-activation reverse cutover remains a separate acceptance test.

For the migrated runtime, use `linux-cutover.py backup --work <directory>` for a
cold, hash-verified portable bundle, and `linux-import.py` to restore it without
spending. Use `linux-cutover.py loopback --work <directory>` after container
recreation. The earlier linux-core/linux-recovery commands operate only the
separate zero-spend project. A local backup alone is not off-machine retention.


## Encrypted off-VM retention

`encrypted-backup.py seal --source <portable-backup> --output <new-file>
--key-file <private-key-file>` uses authenticated Fernet encryption from the
already-installed `cryptography` dependency. It verifies the bundle before
sealing and verifies decryption in memory before writing. No package is installed
by this command. The key is a random URL-safe base64 32-byte key, in a regular
0600 file owned by the operator; keep an independent protected copy outside the
VM and outside Git/synced folders. Ciphertext alone cannot recover data.

Copy the encrypted file over authenticated SSH to protected off-VM storage,
compare its SHA-256, then test `unseal` from a returned copy. Unsealing authenticates
before writing any plaintext, refuses occupied output, validates exact inventory
and rechecks the internal backup manifest/archive safety. Use the independent
Linux import command on the recovered bundle for a zero-spend restore drill.
The encrypted copy and recovery key currently require manual custody; a separate
key escrow, automated retention and clean-host recovery are distinct gates.
