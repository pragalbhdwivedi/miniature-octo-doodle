# Local AI

Local inference is optional.

## Hardware
- GTX 1650 Ti, 4 GB VRAM
- 64 GB system RAM
- Ryzen 7 4800H

## Initial rule
Do not install Ollama or download any model during base deployment.

## Later rule
Install Ollama separately, then select at most one small quantized coding model initially.

Before model download:
1. check free disk
2. show expected download footprint
3. preserve the critical free-space reserve
4. require explicit approval

Large 14B/27B/32B/70B-class downloads are deferred while storage is constrained.
