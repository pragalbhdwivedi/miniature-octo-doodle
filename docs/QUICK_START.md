# Quick Start

Current repository status is architecture/bootstrap only. Do not assume the runtime has been validated yet.

## Intended future flow
```powershell
git clone https://github.com/pragalbhdwivedi/miniature-octo-doodle.git
cd miniature-octo-doodle
Copy-Item .env.example .env
.\scripts\manage.ps1 preflight
```

Then fill local provider keys in `.env`.

After ChatGPT Work validates the current upstream images and Compose configuration:

```powershell
.\scripts\manage.ps1 start
.\scripts\manage.ps1 status
```

Expected initial browser endpoint:
- Open WebUI: http://127.0.0.1:3000

Expected internal/local gateway endpoint:
- LiteLLM: http://127.0.0.1:4000

Do not use this as proof the stack is already operational. See `docs/BUILD_STATUS.md`.
