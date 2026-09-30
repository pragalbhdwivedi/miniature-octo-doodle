# Optional Windows laptop local model

This is the roadmap's optional Ollama/local-model capability lane, separate from
Phase 9's OpenViking/Graphify context work.
The owner requested the laptop installation and two additional models on
1 October 2026. The two new models are optional aliases in the existing VM9125
LiteLLM/Open WebUI app; the PC agent below is a separate local evaluation tool.

## Tested laptop installation

- Native, per-user Windows Ollama 0.35.0; binary at
  `%LOCALAPPDATA%\Programs\Ollama\ollama.exe`, user startup shortcut present.
- Retained models: `qwen3:4b-instruct` (2.5 GB, prior local baseline),
  [Devstral Small 2 `devstral-small-2:24b`](https://ollama.com/library/devstral-small-2:24b)
  (15 GB Q4 coding model) and
  [Qwen3 `qwen3:4b-thinking`](https://ollama.com/library/qwen3:4b-thinking)
  (2.5 GB supervisor model). The model store is `%USERPROFILE%\.ollama\models`,
  outside this Git/OneDrive repository. The official model pages identify the
  two additions as Apache 2.0; model weights are not backed up in this project.
- User environment: `OLLAMA_NO_CLOUD=1`, `OLLAMA_HOST=127.0.0.1:11434`.
  `%USERPROFILE%\.ollama\server.json` has `disable_ollama_cloud: true`.
  The active server reported cloud disabled and Windows TCP inspection showed
  only `127.0.0.1:11434` listening. It is unauthenticated, so do not bind it to
  a LAN address as a convenience.
- The prior 4B instruct model returned a correct `is_even` function in 7.21 s,
  with 73% GPU / 27% CPU at 2,048-token context. Devstral returned the same
  correct logic in 45.3 s on the laptop API; `ollama ps` reported 92% CPU /
  8% GPU at 2,048 tokens, consistent with heavy system-RAM/CPU use. The 4B
  thinking model reviewed a synthetic odd/even defect through LiteLLM in 32.8 s
  and reported the correction; it used 33% CPU / 67% GPU at 4,096 tokens.
- The Qwen2.5 Coder 3B trial carried a research/non-commercial license and was
  removed before this request. The earlier Qwen3 thinking trial had also been
  removed; the owner explicitly requested its new supervisor installation.
  C: had 33.9 GiB free before the two pulls and 17.76 GiB immediately after,
  above the 15-GiB critical floor but below the 25-GiB warning level. Do not
  pull another model without a new disk estimate.

## Local use and checks

In Windows PowerShell, use `ollama run qwen3:4b-instruct`, or call the local API:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/version
ollama list
ollama ps
```

If `ollama` is not yet on an existing terminal's PATH, start a new terminal or
run `& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"` by full path. Check `ollama ps`
while a request is loaded to see the actual GPU/CPU split. The first load can be
slower than subsequent requests. Do not download additional models automatically;
measure free storage before any approved addition.

WSL Ubuntu could not reach Windows `127.0.0.1:11434` in the prior NAT test.
The VM uses a separate outbound SSH reverse tunnel from the laptop to its own
loopback `127.0.0.1:11435`; the `GatewayAI Local Model Tunnel` limited-user
Windows scheduled task reconnects it after SSH loss. On VM9125, an unprivileged
`systemd-socket-proxyd` exposes that loopback port only on the live gateway's
Docker provider-egress bridge. That network has only the LiteLLM container.
Ollama itself still listens only on Windows loopback. The VM proxy is not a
public/LAN service. The scheduled task passed manual start and child-process
reconnect; next-logon/reboot/no-session behavior is unverified. If the laptop
is off or the tunnel is down, local aliases fail; they have no cloud fallback.

The existing `https://ai.aadi.dgoi.local` Open WebUI displays `local-coding`
and `local-supervisor` in addition to its eight existing aliases. Open WebUI
still calls only LiteLLM. Its policy admits these routes for public/synthetic
text, keeps private/local-private labels blocked, prohibits tools and mixed
local/cloud fallbacks, and records zero USD debit for local inference while
retaining the concurrency/output ceilings. See BUILD_STATUS for live request,
outage and ledger evidence. This does not enable a private AADI-source route.

The existing admin login was copied to the protected local file
`%USERPROFILE%\creds\gatewayai-webui-login.json` (user/SYSTEM ACL only).
The file contains the URL, email, password, localhost tunnel alternative and
local public CA path. Do not copy it into Git or a synced folder. The HTTPS
certificate chains to the saved internal CA. A public-only copy for client
installation is `%USERPROFILE%\creds\gatewayai-internal-ca.crt`. Windows now
shows that CA in both user and machine trusted roots, and Edge opens the HTTPS
sign-in page without a warning. Phone/other-PC trust requires importing the
public CA separately; authenticated HTTPS browser model selection is pending.

The Windows user environment sets `OLLAMA_MAX_LOADED_MODELS=2` to avoid an
observed stall unloading Devstral before the supervisor could load. This is an
operational setting for the two approved local models. A bounded public-source
probe then produced a reviewable patch and separate Qwen critique; Git accepted
the patch check while the source tree stayed clean. This is not a
production-quality agent acceptance claim.

## Operation and recovery

- Windows Task Scheduler: `GatewayAI Local Model Tunnel`, limited interactive
  user, at logon. Its script/logs are under the physical package `LocalCache`
  path recorded in the Git-excluded VM9125 note, outside OneDrive. The script
  uses `gatewayai-via-bastion` and retries after SSH exit. Internal bastion
  access passed; an outside-OpenVPN laptop test remains pending.
- VM9125: `gatewayai-local-ollama.socket` listens on the current live
  `provider-egress` Docker bridge gateway at port 11435. Its unprivileged
  `gatewayai-local-ollama.service` forwards to the SSH loopback listener on the
  same VM. `deploy/local-model/` contains the unit template. Confirm the bridge
  gateway and that only LiteLLM is attached before rendering the template on a
  rebuild; do not reuse `172.26.0.1` blindly after network recreation.
- The live gateway's protected `gateway-config.json`, `policy.json` and two
  policy modules were backed up under the VM's root-only
  `/var/lib/gatewayai-import/local-model-rollback-20261001` before enabling the
  aliases. Roll back only those configuration/code files and recreate LiteLLM;
  **never restore an older budget ledger** to undo this feature. A protected
  staged renderer is `scripts/local_model_routes.py`; do not place live config
  or environment secrets in Git. Recheck all three core health states, the
  current budget debit, WebUI login and model list after any recreation.
- The laptop is the inference host. If it is asleep, offline or outside an
  internal/VPN path, both local aliases fail closed. Check the Windows task,
  VM loopback `/api/version`, systemd socket, Docker bridge and current model
  list in that order. A restart of Ollama or the laptop is not proof of
  auto-recovery until the exact model call succeeds again.

## Bounded PC agent

`scripts/local_agent.py` is an optional Windows-local evaluation agent. It reads
only one to eight named, tracked, ordinary UTF-8 files (up to 64 KiB total) from
a clean checkout of this exact public repository. It checks the source SHA again
after both model calls. A coding model writes a structured proposal and optional
full-file replacements for selected paths. The script makes a bounded unified
diff and runs `git apply --check`; a separate thinking model critiques the
candidate. The JSON record and any `.patch` file are saved in
`%LOCALAPPDATA%\GatewayAI\agent-runs`, outside Git and OneDrive, as
`human_review_required`. The agent has no model-driven shell/tool execution, source-edit,
Git push, PR, merge, deployment, credential or spending authority. Model text is
untrusted advice. It is not the VM's production controller, LiteLLM route or a
Phase 10 multi-agent system.

From a clean checkout, a bounded invocation is:

```powershell
python scripts/local_agent.py --repo . --task "Review a small public code change" `
  --file scripts/local_agent.py --coder-model devstral-small-2:24b `
  --supervisor-model qwen3:4b-thinking
```

The owner also confirmed both local aliases worked from a phone through the
existing HTTPS WebUI. This is user-reported acceptance; the next-logon/reboot
tunnel recovery and authenticated Edge picker remain unverified. A later C:
measurements found 7.37 and then 12.93 GiB free, below the project's 15-GiB critical
floor, so no further optional laptop model/image installs are allowed until
space has been recovered and remeasured.

The local agent now requires its clean public checkout HEAD to equal the live
remote `main` SHA before calling either model. The live LiteLLM callback now
uses the configured 300-second stream ceiling only for all-Ollama routes;
cloud/mixed/unrecognized routes retain 120 seconds. Unit checks cover both
boundaries. An authenticated HTTPS WebUI request to `local-coding` streamed
1,026 SSE chunks and the completion marker in 553.1 seconds end to end; the
ledger recorded Ollama `stream_completed` and no active request afterward.
That total includes WebUI/network delivery and does not measure the callback's
own iterator duration.

The live two-model result and laptop disk/performance measurements are recorded
in `docs/BUILD_STATUS.md`; do not infer production coding quality from one
synthetic run. Model files remain in Ollama's user store, never in Git/OneDrive.
