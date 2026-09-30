# VPN and laptop remote-access check

30 September 2026. User requested WAN2 public-IP VPN access, a password-free
service directory, individual service hostnames and investigation of laptop RDP
from a phone. Host addresses and account identities remain in local private notes.

## OpenVPN: configured correctly; user confirmed outside access

The controller dashboard showed WAN2 active with the specified static public IP;
WAN1 had no address. The enabled OpenVPN server is already bound to WAN/LAN2,
UDP 1194, with password authentication and an internal DNS resolver. The current
server uses full tunnel. This supersedes the earlier local note describing split
tunnel; this task did not change tunnel mode.

The existing laptop client profile already targets that public IP and port.
Its CA and client certificate expire in 2035. No endpoint, key, password,
cryptographic policy or public port-forward change was needed. The user then
confirmed that OpenVPN connects from the phone outside the local network.

## WireGuard: server routes corrected; client setup pending

The existing manual site-to-site WireGuard interface listens on UDP 51820 and
offers no per-WAN selector in this controller view. The intended client endpoint
is the WAN2 address; external WireGuard reachability is not yet verified. The two road-warrior peers incorrectly claimed a default
route and a LAN subnet on the server side. The user confirmed client tunnel
addresses had not yet been assigned.

Assigned distinct /32 client addresses in the existing tunnel subnet, preserving
the interface address, port, MTU, keys, keepalive and enabled peers. Saved and
reopened the profile to verify both routes. The controller rejected the legacy
hyphenated name, so it was changed to `BDGOI_WireGuard`, with the same keys.
No endpoint is set on the server's roaming peers; clients initiate to WAN2.

Client profiles must use their assigned address, the existing matching keys,
WAN2:51820 endpoint, internal DNS, intended internal AllowedIPs and keepalive 25.
Matching client key custody, external UDP reachability and handshake are NOT
VERIFIED. No private key was displayed, exported, regenerated or committed.
OpenVPN remains the working remote-access path. This is not automatic WAN failover.

## RDP: user confirmed successful phone login

The laptop is Entra joined, with successful device authentication and PRT.
Remote Desktop is enabled, TermService runs, TCP 3389 listens, and its Windows
firewall rules are enabled. The existing work account is already a local
administrator. NLA was already disabled; this task did not change it, password
policy, local groups or firewall. Reaching the sign-in screen established the
transport path, not successful authentication.

Guided the user to the existing work-account identity using `AzureAD\<work-UPN>`
and the account password, rather than an unrelated personal Outlook account or
Windows PIN. After connecting OpenVPN, the user explicitly confirmed being logged
into the laptop from the phone. No password was collected/reset and no identity
rejoin or additional account was created.

References: [Microsoft Entra RDP](https://learn.microsoft.com/en-us/windows/client-management/client-tools/connect-to-remote-aadj-pc),
[TP-Link WireGuard guide](https://static.tp-link.com/upload/configuration-guides/2023/202304/20230426/%E3%80%90CG%E3%80%91Configure%20WireGuard%20VPN%20with%20Omada%20SDN%20Controller.pdf).
