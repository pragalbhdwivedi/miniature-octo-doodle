# Quick Start

Phase 1 core is deployed and validated on the target machine. All three containers,
Windows integration checks, live OpenAI/Gemini completions and Edge browser chat
passed on 2026-09-29. The host uses WSL NAT for working localhost forwarding.
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
Set `GATEWAY_MONTHLY_BUDGET_USD` locally before inference; it defaults to 0.
This is a conservative admission allowance per UTC calendar month, not an invoice
counter. See [Phase 2 policy](PHASE2_POLICY.md). Keep `TYPESAFE_API_KEY` blank
until a separately bounded synthetic evaluation is ready; runtime Jev is disabled.

For diagnosis, `manage.ps1 test -ContainerOnly` checks the internal network and
explicitly makes no host/browser readiness claim. `manage.ps1 stop` stops only
this project and preserves its containers and volumes.
