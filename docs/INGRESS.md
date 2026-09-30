# Internal HTTPS ingress with Nginx Proxy Manager

Status: DEPLOYED; HTTPS/API acceptance passed, browser acceptance pending.
Requested by the user on 30 September 2026.
NPM means Nginx Proxy Manager here. This adds an optional, explicitly requested
front door to the existing live VM; it does not create another spending gateway.

## Intended path

Laptop / approved internal networks / existing OpenVPN
-> Omada routing and stable destination/port ACL
-> VM VLAN address:443 / Nginx Proxy Manager
-> Open WebUI -> existing LiteLLM and admission ledger.

All services use the `*.aadi.dgoi.local` namespace. GatewayAI is
`https://ai.aadi.dgoi.local`. The user selected all internal VLANs and the existing
OpenVPN. Omada rejected a literal wildcard LAN DNS record as invalid, so each
service needs an explicit DNS record plus its own NPM proxy host. The GatewayAI
record is saved, enabled for all 13 configured LANs and resolves from the laptop.
The stable LAN-to-LAN TCP rule targets only the ingress VM's ports 80 and 443;
port 80 redirects the configured hostname to HTTPS. Host IPs and controller
inventory remain in Git-excluded VM notes.
NPM cannot bypass inter-VLAN routing or a firewall deny. VLAN 45 membership alone
does not authorize clients on other VLANs. SSH remains through the existing bastion.
No WAN port forwarding/public service exposure is part of this request.

## Deployment boundary

`compose.npm.yaml` defines a separate one-container Compose project with SQLite,
protected data/certificate binds and no Docker socket or privileged/host networking.
Set a reviewed image digest, the explicit VLAN bind address and protected absolute
state directory through a private environment file; no usable image default exists.
NPM 2.16.0 is pinned to
`jc21/nginx-proxy-manager@sha256:4393e642e233e5efd5adeb7f10918d4aaea71c9ed875b94190273fc8e87f9594`.
The image was pulled after a disk check: 50.51 GiB before, 48.73 GiB afterwards;
installed image size 1,909,394,336 bytes. Port 81 administration is loopback-only
through SSH. A separate administrator was created through the localhost setup
API and the generated credential stored outside Git/sync. Do not use this
version's INITIAL_ADMIN_PASSWORD bootstrap: its startup code logs that value.

The dedicated internal Docker network `gatewayai-webui-ingress` attaches only
NPM and the active Open WebUI service, through persisted configuration. The
portable core overlay is `compose.ingress-core.yaml`; the selected imported
runtime has the equivalent configuration persisted in its private compose.json.
Docker DNS upstream is `gatewayai-webui:8080`, WebSocket support is enabled,
proxy read/send timeouts are 600 seconds, and proxy buffering is disabled.
NPM's separate edge network supplies publication/egress;
WebUI retains its internal-only paths. Do not attach NPM to the database network,
publish PostgreSQL, expose LiteLLM administration, or mount provider secrets.
Only WebUI was recreated; the existing gateway, database, accounts and ledger
were retained. No second spending gateway was started.

## Private certificates

The private root is constrained to DNS names under `dgoi.local`, excludes IP
certificates and permits server authentication only. Its signing key stays in
the laptop's protected WSL home, never on the proxy VM or in Git/OneDrive.
The wildcard leaf covers one label under `aadi.dgoi.local`, including
`ai.aadi.dgoi.local`; it does not cover the apex or deeper nested names.
Leaf expiry: 30 September 2027. Root expiry: 29 September 2029. Custom certificates
are manually renewed; NPM's Let's Encrypt timer does not renew this private leaf.
Renew at least 30 days before expiry, upload the renewed leaf/key through the
loopback administration API, and repeat strict hostname/chain and browser checks.

CA SHA-256 fingerprint:
`3055aaa39e54375a01d61e62b15b1ad8f5e62afdc9dcf1bf2434af4696ac2960`.
Distribute only the public CA certificate to approved clients and verify this
fingerprint. Never distribute the signing key. WSL system trust is installed;
Windows CurrentUser CLI import requires a local confirmation; the user's requested
unattended policy-store attempt returned Access denied. Both waiting import
processes were stopped. Edge reported ERR_CERT_AUTHORITY_INVALID; no warning was
bypassed. This shell is not an administrator. The following prepared helper can
install just this public CA from an **administrator PowerShell** and verify readback:

```powershell
.\scripts\install-ingress-ca.ps1 `
  -CertificatePath "$env:LOCALAPPDATA\GatewayAI\ingress\ca.pem" `
  -ExpectedSha256 3055aaa39e54375a01d61e62b15b1ad8f5e62afdc9dcf1bf2434af4696ac2960
```

The helper has not been run elevated; Windows browser trust is still pending.
Other clients' trust and external OpenVPN DNS/access remain unvalidated.
At the user's request, the local Git-excluded `LOCAL_CERTIFICATES/` directory
contains the public root in DER `.cer` and PEM `.crt` formats plus an installation
note. Both copies were checked against the certificate fingerprint above. No
private key or password is included. This is suitable for manual phone/PC trust
distribution; it does not configure their VPN or DNS.

## Tested on 30 September 2026

- Omada DNS explicit hostname resolves to the selected VM; stable web ACL saved.
- WSL system-trusted HTTPS HTTP/2 200; Windows Python strict CA/hostname validation
  passed after adding the required leaf Authority Key Identifier extension.
- Preserved WebUI sign-in and eight aliases passed through HTTPS; unauthenticated
  model discovery rejected; a synthetic OpenAI streamed response passed.
- Laptop LAN connections to ports 81, 3000, 4000 and 5432 were unavailable.
- Windows curl/Schannel reported unavailable revocation status for this private
  certificate. No certificate checks were disabled to claim a pass.

Reboot acceptance passed: four healthy live containers, system-trusted WSL HTTPS
200, unchanged ledger and successful loopback refresh. NPM's separate encrypted
backup passed authenticated decrypt, SQLite integrity, admin/route persistence,
isolated-container health and Nginx configuration checks. The restored instance
has no published ports or upstream connectivity and is stopped with restart=no.
An encrypted off-VM copy has a matching SHA-256. These checks do not establish
recovery after losing this host or the CA signing key.

Pending: browser acceptance after Windows trust, all-VLAN/external-VPN client
tests and independent clean-host recovery.

## Backup and recovery scope

Preserve both the existing core portable bundle and a separate encrypted ingress
archive containing the private config directory (Compose, runtime environment,
administrator file, public CA and leaf/key) and state directory (SQLite, Nginx
configuration and certificates). Stop only the NPM project while capturing its
state, and restart it in a finally/cleanup step. Store the independent encryption
key outside Git/sync, with a separately protected off-VM copy. The CA signing key
has separate custody on the laptop; it is intentionally absent from the VM archive.

Before activating a restored proxy, validate archive authentication and safe member
paths, restore into a new private directory, check SQLite integrity, and launch an
isolated restart=no project using the pinned image, no published ports and no
upstream network. Check health and `nginx -t`, then stop the test copy. A real
cutover must reconstruct the selected WebUI network alias, DNS/ACL and client
trust and repeat HTTPS/browser acceptance. Never start a duplicate live gateway
or reuse a stale budget ledger as part of an ingress recovery.

Live preflight on 30 September 2026: three core containers healthy, 50.51 GiB free,
ports80/81/443 were unused. Existing ports3000/4000 remain loopback-only. Outside-VPN acceptance
remains pending until a real external connection test is performed.

References: [official setup](https://nginxproxymanager.com/setup/) and
[Docker-network guidance](https://nginxproxymanager.com/advanced-config/).
