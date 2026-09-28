# Kubernetes deployment

This directory is intentionally a scaffold until the Docker core is validated.

Planned structure:

```text
base/
overlays/
  local/
  ollama/
  openviking/
  graphify/
  omniroute/
  coding-agent/
  full/
```

Rules:
- base contains only the lightweight core
- optional components use overlays
- do not duplicate large local model storage
- expose the browser UI through Ingress
- keep PostgreSQL and model runtimes internal by default
- ChatGPT Work must validate manifests against the selected local Kubernetes runtime before marking Kubernetes COMPLETE
