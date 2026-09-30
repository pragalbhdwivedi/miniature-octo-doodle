# Linux core operations

This is the Phase 5 fresh, zero-spend deployment on the approved Ubuntu VM.
It is independent of the live Windows deployment. Provider keys are blank, the
monthly allowance is zero and Jev is disabled. No existing chats, accounts or
budget history have been migrated. See BUILD_STATUS for actual acceptance results.

## Deployment

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

## Local backup and restore drill

```sh
sudo python3 /opt/gatewayai/source/scripts/linux-recovery.py backup
sudo python3 /opt/gatewayai/source/scripts/linux-recovery.py drill
```

Backup briefly stops only this core, requires healthy matching source containers,
checks clean shutdown/no remaining volume writers, and resumes in a finally block.
It archives all three volumes, private runtime configuration and deployed source,
with SHA-256 checksums, in `/var/lib/gatewayai-recovery` (0700, archives 0600).
These backups contain credentials and are not encrypted. They remain on the VM;
they do not protect against loss of its host/NAS.

`drill` creates a fresh backup, verifies it, extracts archived source/configuration,
restores into new named volumes and checks every file's content before startup.
Fresh recovery containers use existing pinned images, internal networks, no host
ports, blank provider keys, zero allowance and restart disabled. Health, restored
admin/scoped-key access, eight aliases, budget rejection, PostgreSQL full dump read
and SQLite integrity are checked. Recovery containers stop in a finally block;
volumes and evidence remain for review. No cleanup or production cutover occurs.

This is a same-VM recovery rehearsal. Standalone existing-backup restore CLI,
off-machine encrypted retention, separate clean-host recovery and live cutover
remain additional work. Checksums detect corruption, not malicious replacement;
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
