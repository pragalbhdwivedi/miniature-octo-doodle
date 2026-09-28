# Storage Budget

## Baseline
The initial laptop has a 256 GB NVMe with approximately 50 GB free at project start.

## Policy
- warning below 25 GB free
- critical below 15 GB free
- optional installers must stop at the critical threshold
- no automatic model downloads
- no automatic heavyweight optional images
- do not duplicate model weights between Docker and Kubernetes

## Initial objective
Keep the initial core platform around 10-12 GB of additional consumption where practical. Actual measured usage must replace estimates after deployment.

## Core storage consumers
- Docker/WSL2 virtual disk growth
- PostgreSQL
- LiteLLM
- Open WebUI
- image layers and build cache

## Later storage consumers
- Ollama runtime
- model weights
- OpenViking persistence
- Graphify indexes / graph database
- agent workspaces
- observability data

## Required operational commands
The project should provide:
- preflight disk report
- Docker usage report
- safe cleanup report
- explicit model-download size check

Never automatically delete persistent volumes, databases, or models.
