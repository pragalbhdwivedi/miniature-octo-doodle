# ADR 0013: Internal hostname ingress on the existing control VM

Date: 30 September 2026. Status: accepted by user instruction; deployed with
remaining client acceptance gates recorded in BUILD_STATUS.md.

The user requested Nginx Proxy Manager on the current VM so changing laptop IPs
do not require a new application ACL. Services use `*.aadi.dgoi.local`; GatewayAI
is `ai.aadi.dgoi.local`. Scope is all internal VLANs and existing OpenVPN, with no
public internet exposure. A private certificate setup was explicitly selected.

Run a separate digest-pinned NPM Compose project with SQLite, loopback-only admin
and web publication on the VM VLAN address. Attach NPM only to a dedicated internal
WebUI network and its separate edge network. Keep the existing LiteLLM, database,
provider secrets and persistent budget ledger unchanged. The default three-service
core remains usable without NPM.

Use stable LAN routing to one destination's web ports. NPM does not bypass ACLs.
The controller rejects wildcard LAN DNS syntax, so create explicit service DNS
records and separate proxy hosts while sharing a wildcard private certificate.
Keep the constrained CA signing key off the proxy and distribute only the public
root to clients. Private certificates require manual renewal and client trust.

Back up NPM state separately, encrypted; retain the core recovery format and
spend reconciliation rules. Independent clean-host recovery, reverse live cutover
and outside-VPN acceptance remain separate gates, not implied by proxy deployment.
