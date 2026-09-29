# ADR 0012: Use the user-selected Proxmox template 9001

Date: 2026-09-29
Status: Accepted target selection by explicit user instruction; runtime acceptance pending.

The user requested creation of the control-plane VM on their Proxmox cluster
using template 9001. Live inspection identifies it as the Ubuntu 24.04 template,
not Debian. This explicit selection supersedes the Debian-only Phase 5 target
in PR #11 / ADR 0011. It does not change provider, policy, budget or approval rules.

Create an independent full clone with 4 vCPU, 8 GiB RAM and 60 GiB disk, preserve
the template, install existing Windows/WSL public SSH keys without transferring
private keys, and validate guest identity, disk growth and administrative access.
The dedicated VM starts on host boot; this setting alone is not reboot evidence.

Keep Debian 12/13 compatibility in preflight and add native Ubuntu 24.04 support.
WSL and container hosts remain rejected. The script/runbook filenames are retained
for link compatibility. VM creation does not prove Docker, the gateway, browser
acceptance, off-machine backup or clean-host application recovery.
