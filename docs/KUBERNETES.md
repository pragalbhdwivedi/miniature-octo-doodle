# Kubernetes

Kubernetes is a supported deployment target, but not required for the first working core.

## Local target
Use k3d unless implementation-time validation establishes a better lightweight option.

## Principles
- Docker Compose first
- Kubernetes second
- do not require both to run simultaneously
- do not duplicate local model weights
- base manifests contain only core services
- optional systems use overlays

## Planned layout
```text
deploy/k8s/
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

Ingress should expose the web UI while PostgreSQL and local model services remain internal.
