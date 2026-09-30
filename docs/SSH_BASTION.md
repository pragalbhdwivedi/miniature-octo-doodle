# Internal SSH bastion

Implemented and tested on 30 September 2026. Windows and WSL use a small,
dedicated Ubuntu VM listening on TCP 7000. Existing Omada OpenVPN supplies the
outside-network route; **outside-VPN acceptance remains pending by user choice**.
No public SSH port forwarding was added.

## Use

Both laptop clients have these aliases:

```sh
ssh gatewayai-via-bastion
ssh internal-ssh-admin
ssh -J internal-ssh user@INTERNAL_IP
```

The first opens the GatewayAI VM, the second manages the bastion, and the third
uses it for another authorized internal SSH target. Target authentication stays
on the laptop. Each destination still needs a trusted host key and an authorized
account/key. Do not disable strict host-key checking to make a connection work.

The `internal-ssh` account is forwarding-only: opening its shell is intentionally
denied. It permits onward TCP ports 22 and 7000, not arbitrary service ports.
The separate administrator account has a shell and sudo. SSH password and
keyboard-interactive login are disabled; root SSH is disabled. No private keys
were copied into the VM, and agent forwarding is disabled.

Existing Windows and WSL public keys were installed. Client configuration is in
`~/.ssh/config.d/internal-bastion.conf`, included by `~/.ssh/config`. Host keys
were obtained through the trusted hypervisor guest agent and pinned separately.
Original client configuration was backed up before adding the include.
See the [OpenSSH ProxyJump documentation](https://man.openbsd.org/ssh_config#ProxyJump).

## Operations and validation

The VM has 1 vCPU, 1 GiB RAM and a 32 GiB thin disk retained from its template.
Local Git-excluded `VM_NOTES/` records in GatewayAI and AADI hold actual addresses,
storage paths, fingerprints, usernames and the full inventory. The same inventory
is in Proxmox Notes; notes are not a credential store.

Narrow LAN ACLs permit entry to the bastion on 7000 and onward internal SSH.
Guest firewall rules independently restrict entry and destination ports.
Existing VPN settings and AADI ACLs were preserved.

Windows/WSL key login, GatewayAI ProxyJump, onward port 7000, sampled internal SSH
reachability and inbound access from the target VLAN passed. Forwarding-account
shell access and forwarding to an unauthorized service port were rejected.
These checks passed again after a planned guest reboot. They do not establish
access to every host, outside-VPN connectivity, backup recovery or NAS resilience.

For rollback, retain hypervisor console access. Restore each client's backed-up
SSH configuration and remove only this task's dedicated include/pin files after
checking for later edits. Disable only the two documented bastion ACLs and stop
the bastion VM if retiring the path. Do not remove disks, existing AADI rules,
VPN configuration or target credentials. Retest the replacement path first.

GatewayAI Docker/application deployment remains stopped; SSH acceptance alone
does not complete Phase 5 or create a remote web login.
