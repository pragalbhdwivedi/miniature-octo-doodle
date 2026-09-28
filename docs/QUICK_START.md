# Quick Start

Phase 1 core is implemented. All three containers and their internal and Windows
integration checks passed on 2026-09-29 after the host switched WSL to NAT.
Actual browser acceptance remains pending; provider inference is pending by instruction.
See [BUILD_STATUS.md](BUILD_STATUS.md) for the precise validation boundary.

## Setup
```powershell
git clone https://github.com/pragalbhdwivedi/miniature-octo-doodle.git
cd miniature-octo-doodle
.\scripts\manage.ps1 init
.\scripts\manage.ps1 preflight
```

`init` generates random secrets in local `.env` and refuses to overwrite it.
The initial WebUI login is `admin@example.com`; its generated password is
`WEBUI_ADMIN_PASSWORD` in `.env`. Change the email before first startup if desired.
Never paste this file into chat or Git. Existing accounts are not reset on startup.

Deploy and test each stage:

```powershell
.\scripts\manage.ps1 start -Stage gateway
.\scripts\manage.ps1 test -Stage gateway
.\scripts\manage.ps1 start
.\scripts\manage.ps1 test
```

Expected initial browser endpoint:
- Open WebUI: http://127.0.0.1:3000

Expected internal/local gateway endpoint:
- LiteLLM: http://127.0.0.1:4000

With empty provider keys, the model list is empty. Add keys only to local `.env`
when ready; see [PROVIDERS.md](PROVIDERS.md). Core tests never request inference.

For diagnosis, `manage.ps1 test -ContainerOnly` checks the internal network and
explicitly makes no host/browser readiness claim. `manage.ps1 stop` stops only
this project and preserves its containers and volumes.
