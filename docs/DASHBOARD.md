# Internal service dashboard

Deployed and tested 30 September 2026 at `http://dash.aadi.dgoi.local`.
HTTPS is also available with the existing internal CA. The directory has no
password, cookies, external assets, telemetry, integrations or service credentials.
The linked applications retain their own authentication.

| Service | Address | Current evidence |
| --- | --- | --- |
| Directory | `http://dash.aadi.dgoi.local` | Browser rendering, links and search passed |
| GatewayAI | `https://ai.aadi.dgoi.local` | Existing authenticated ingress retained |
| Institution portal | `https://hrms.aadi.dgoi.local` | Preserved login, protected students page and logout passed |
| Development console | `https://console.aadi.dgoi.local` | Preserved login, protected source-health page and logout passed |

The user selected a simple Homarr-like directory and hostnames for every service.
A static directory in the already deployed NPM container supplies this without
another image, database, login or model download. Only the dashboard permits
HTTP; the authenticated application hostnames redirect HTTP to HTTPS.
NPM administration remains loopback-only. Databases, provider administration,
OpenWA API and temporary ERP/Identity test runtimes are not published as web apps.

## Deployment and maintenance

`dashboard/` contains the static page, styles, search and a non-secret example
catalogue. Store the live `services.json` outside Git. Do not put tokens, account
names, private records or query-string credentials in directory links.

On the existing ingress VM, as its administrator:

```sh
sudo python3 scripts/deploy-dashboard.py --source dashboard --services /protected/services.json
sudo python3 scripts/deploy-service-proxies.py --routes /etc/gatewayai-ingress/service-routes.json
```

The first command copies only the three public static assets and catalogue into
the existing NPM `/data/dashboard` bind, backs up the previous route/assets,
upserts only the dashboard host, validates Nginx and compares the served HTML.
It permits GET/HEAD and returns errors for absent files, dotfiles and writes.
It checks the 15 GiB reserve before changing files. TLS uses the existing wildcard.

The second command reads an operator-controlled JSON array with `name`, `port`,
`scheme`, `original_origin`, and, for TLS upstreams, `ca_file` and `tls_name`.
Optional `link_replacements` contains exact old/new HTTPS navigation URLs.
Actual backend addresses and the live route file remain in protected inventory.
Only approved entries belong here; this is an administrator deployment tool,
not an API available to an agent worker or browser application.

Each named service gets an unprivileged systemd socket proxy bound only to the
NPM edge bridge, forwarding to the VM's loopback SSH reverse port. It does not
publish another LAN port. The proxy script saves the previous NPM hosts and any
existing systemd units before applying configuration. Missing tunnels fail closed.

On Windows, `scripts/service-tunnels.ps1` supervises two outbound SSH forwards and
a loopback-only `kubectl port-forward` to the existing console service. The task
`AADI Service Hostname Tunnels` runs as the existing interactive user at logon,
with limited privileges, hidden windows and IgnoreNew. A named mutex prevents
duplicate supervisors. The original supervisor was stopped only after verifying
its PID/start time and child ownership. The initial task start exposed an
app-virtualized LocalAppData path; its action now uses the physical package
LocalCache path. Manual task start and automatic tunnel retry after a Docker
Desktop restart passed, followed by fresh authenticated access and denial checks
for both applications. Next-logon/reboot execution is NOT TESTED.
Laptop power, Docker Desktop, Kubernetes and the signed-in user remain dependencies.
For a changing laptop network use the already configured bastion SSH alias.

The previous AADI recovery task still uses the old laptop address and a broken
compatibility API bridge. Its failure was diagnosed, not silently treated as
recovered. The default Docker Desktop Kubernetes API now responds directly.
This hostname path uses that working API and bypasses the stale LAN relays without
changing the application image, configuration, accounts, database or PVCs.

## Authentication and transport boundary

HRMS TLS is verified against its existing upstream certificate and `localhost`
SAN, through the encrypted SSH tunnel. Console HTTP exists only inside the
existing local service path, SSH tunnel and dedicated ingress bridge.

NPM sends the application's existing Host and translates only the exact matching
new public Origin to its original configured Origin. Foreign Origins pass through
unchanged and are denied by the application. CSRF tokens are not created or
bypassed. The single old institution navigation URL in console HTML is translated
to the HRMS hostname. No application record content is changed.

New DNS record `AADI-Dashboard` includes HRMS and console aliases and the same
13 internal LAN selections as the existing AI record. No wildcard DNS or WAN web
forward was added. The VPN uses the existing internal resolver. Device certificate
trust and phone DNS/browser acceptance are separate from successful VPN connection.

## Verification and remaining limits

- Actual deployment of both scripts and Nginx syntax checks passed; no image pull.
- DNS resolution and strict CA/hostname-verified HTTPS passed for all four names.
- HRMS and console existing-account sign-in, protected reads, logout, anonymous
  denial and foreign-origin rejection passed. No record updates were tested.
- Dashboard desktop rendering, three links and search passed in Edge. Responsive
  CSS is implemented; phone rendering has not been inspected.
- VM free space: 48.53 GiB; laptop: 38.84 GiB. Static assets are approximately
  10 KiB. The free-space difference from earlier checkpoints is not an image cost.
- No new provider inference, application migration, password change or VM creation.
- User confirmed outside-network OpenVPN connection and successful RDP login;
  this does not establish phone browser trust, every VLAN or WireGuard acceptance.

Rollback: restore the backed-up dashboard files and selected NPM host definitions;
disable only the two new service routes/socket units and the Windows tunnel task
if withdrawing hostname transport. Preserve old access paths, DNS AI record,
accounts, volumes and source data. Do not restart the frozen Windows AI gateway.
Latest encrypted ingress export includes the new route/static configuration;
clean-host restore and tunnel recovery after reboot remain unvalidated.

Related: [ingress](INGRESS.md), [remote-access checks](REMOTE_ACCESS_CHECK.md).
