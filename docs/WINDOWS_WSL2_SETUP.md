# Windows + WSL2 Setup

Target host:
- Windows 11
- Docker Desktop using WSL2 backend
- Ryzen 7 4800H
- 64 GB RAM
- GTX 1650 Ti 4 GB VRAM

## Implementation requirements
ChatGPT Work must validate:
- current WSL2 installation/version
- Docker Desktop WSL2 backend
- Compose availability
- disk location and WSL virtual disk growth
- NVIDIA driver / WSL GPU support
- Docker GPU visibility

Do not move Docker/WSL storage or compact virtual disks without documenting the exact tested procedure first.

## Tested localhost configuration

On 2026-09-29, the target host's mirrored WSL networking timed out on the core
published ports even after Desktop and WSL restarts. A backed-up, machine-local
change to `[wsl2] networkingMode=nat` restored Windows HTTP, authentication and
model discovery tests. Both core ports remain bound to 127.0.0.1.

See [the tested recovery and rollback procedure](TROUBLESHOOTING.md) before
changing another host. WSL network mode applies globally and NAT changes direct
LAN and Linux-to-Windows access; project startup does not edit it automatically.
Browser acceptance and remaining limits are in [BUILD_STATUS.md](BUILD_STATUS.md).
