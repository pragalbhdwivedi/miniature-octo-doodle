# Optional Windows laptop local model

This is the roadmap's optional Ollama/local-model capability lane, not Phase 9.
Phase 9 is OpenViking/Graphify context. The owner requested this laptop install
on 1 October 2026. It does not change the VM9125 LiteLLM routes or controller
policy; providers still pass through the deterministic policy and central gateway
when used by GatewayAI.

## Tested installation

- Native, per-user Windows Ollama 0.35.0; binary at
  `%LOCALAPPDATA%\Programs\Ollama\ollama.exe`, user startup shortcut present.
- Only retained model: `qwen3:4b-instruct`, ID `0edcdef34593`, 2.5 GB,
  Apache License 2.0. The bundled license was checked locally. The model store
  is `%USERPROFILE%\.ollama\models`, outside this Git/OneDrive repository.
- User environment: `OLLAMA_NO_CLOUD=1`, `OLLAMA_HOST=127.0.0.1:11434`.
  `%USERPROFILE%\.ollama\server.json` has `disable_ollama_cloud: true`.
  The active server reported cloud disabled and Windows TCP inspection showed
  only `127.0.0.1:11434` listening. It is unauthenticated, so do not bind it to
  a LAN address as a convenience.
- Synthetic `/api/generate` prompt returned an `is_even` Python function with
  `n % 2 == 0` in 7.21 seconds. `ollama ps` showed 73% GPU / 27% CPU at
  2,048-token context on the 4-GiB GTX 1650 Ti. A longer coding workflow,
  larger context, model quality and restart persistence have not been tested.
- The Qwen2.5 Coder 3B trial carried a research/non-commercial license and was
  removed. The Qwen3 4B thinking trial was also removed. Only the instruct model
  remains. C: free space after cleanup was 36.70 GiB, above the 25-GiB warning
  and 15-GiB critical thresholds.

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

WSL Ubuntu could not reach Windows `127.0.0.1:11434` in the tested NAT setup.
This install is Windows-local. A future WSL bridge or VM gateway connection needs
an explicit, authenticated access design for the laptop's changing networks,
then a LiteLLM capability alias and deterministic-policy review. None is enabled.
