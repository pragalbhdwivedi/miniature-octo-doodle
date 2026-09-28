# GPU Setup

The laptop GPU is an NVIDIA GTX 1650 Ti with 4 GB dedicated VRAM.

## Initial phase
GPU use is optional because the first deployment relies on cloud providers.

## Before local AI
Validate:
1. host NVIDIA driver
2. `nvidia-smi`
3. WSL GPU visibility
4. Docker GPU passthrough
5. available disk
6. local runtime compatibility

## Constraint
4 GB VRAM is not sufficient for large modern models entirely in VRAM. Local inference should start with one small quantized coding model and may use CPU/RAM offload where appropriate.

No model download occurs automatically.
