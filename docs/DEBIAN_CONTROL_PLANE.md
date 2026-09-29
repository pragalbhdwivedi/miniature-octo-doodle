# Phase 5: Dedicated Debian control plane

Status: preparation PARTIAL. Read-only preflight implemented; target deployment
NOT STARTED. No Debian VM has been identified, contacted or validated.

## Target and admission

Provide the dedicated VM hostname/IP and SSH user or existing SSH alias. If the VM
does not exist, identify its virtualization host and proposed resources first.
Never paste keys/passwords into chat or commit them. Existing AADI, Docker Desktop
and unrelated hosts are not implicit deployment targets.

Initial recommendation: Debian 13, 4 vCPU, 8 GiB RAM, 60 GiB disk, no GPU. Debian 12
is also accepted by preflight. These are planning values, not measured capacity.
The approved operator must first establish SSH access and install Git, Python 3.11+
and the supported Docker Engine/Compose plugin. Installation is not automated yet.
Use [Docker's Debian instructions](https://docs.docker.com/engine/install/debian/)
and [Debian release information](https://www.debian.org/releases/index.html)
(checked 2026-09-29; Debian 13 stable, Docker supports 12 and 13).

On the approved VM, from a reviewed checkout:

```sh
python3 scripts/debian-preflight.py --runtime-parent /srv
```

The operator must be able to inspect Docker and its storage directory. Where
root permission is needed, have the approved administrator run the preflight;
the script never elevates privileges or changes permissions itself. Rootless
Docker/systemd user-service support is not implemented. Docker host authority
belongs to this deployment operator, never a future coding worker.

The command emits a JSON report and exits 0 only when all checks pass. It reads
OS/virtualization, CPU/RAM, local Docker context and engine, Compose, systemd and
available disk. It briefly binds and closes loopback ports 3000/4000 without
listening. It reads no `.env`, credentials, container environment or database.
It neither installs nor starts anything. Preserve reports privately; host details
must be reviewed/redacted before including evidence in this public repository.

Admission requires:

- Native Debian 12/13 VM; Windows, Ubuntu/WSL and containers are rejected.
- At least 4 vCPU and 7 GiB visible RAM (allows kernel overhead on an 8 GiB VM).
- Local Unix Docker endpoint; remote contexts and endpoint/TLS overrides rejected
  before any engine request. Linux Engine, not Docker Desktop.
- Docker active and enabled under systemd; Compose plugin available.
- Existing absolute runtime parent and readable Docker data directory, each
  retaining at least 15 GiB after the 12 GiB core reserve. Warn below 25 GiB projected.
- No running containers and available loopback 3000/4000 ports. This is a **fresh
  target** check, not a health check to run after deployment. Stopped containers,
  volumes and host ownership still require operator inventory/review.

A PASS is only admission evidence. It does not verify host ownership, SSH security,
firewall policy, internet/image retrieval, digest availability, service operation,
backup capacity, power-loss behavior or recovery. Never remove occupied resources
to make preflight pass; resolve the target identity first.

## Remaining implementation and acceptance milestones

1. **Target admission:** record approved identity/resources, SSH and preflight
   results; inspect existing storage/workloads without modifying them. Repeat disk
   checks immediately before any image pull and include separate backup reserves.
2. **Linux startup and secret handling:** implement the Linux counterpart of the
   reviewed Windows startup/config rendering. Keep private configuration outside
   Git, directory mode 0700 and files 0600; never overwrite existing secrets.
   Deploy only digest-pinned PostgreSQL, LiteLLM and WebUI with independent project
   and volumes, scoped UI inference key, blank provider keys, zero budget and Jev
   disabled. No models, controller image or optional module is approved by listing it.
3. **Fresh runtime:** validate database, login, scoped key, aliases, budget denial,
   synthetic routing/fallback/concurrency and persistence. Verify loopback-only
   3000/4000 and unpublished PostgreSQL. Retain UI-to-gateway-only configuration and
   deny agents host sockets/production authority. Test browser via an SSH tunnel;
   tunnel/URL commands will use the identified VM, not an invented address.
4. **Always-on and recovery:** validate service recreation, planned VM reboot,
   protected backup, independent restore and clean-host/image retrieval. The
   Windows recovery wrapper is not Linux recovery evidence. Off-machine retention
   and the previously paused new-machine drill remain unvalidated until an approved
   destination/target and resumed scope exist.
5. **Approved migration and controller foundation:** before live cutover reconcile
   the existing monthly admission debit and US$100 UTC-month allowance, migrate
   existing chats/account/key data without a budget reset, and validate bounded
   provider/browser requests. Record rollback and ownership. Define protected
   controller run-state/service boundaries without giving workers host authority;
   full worker/controller implementations belong to Phases 6/7.

Phase 5 remains partial until its target runtime, recovery and operational evidence
are recorded. The current live browser is `http://localhost:3000`; local Phase 4
validation is `http://localhost:3080`. No remote Debian web address or new login
exists yet. Existing local credentials remain in their protected local files.
