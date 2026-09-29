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

## Phase 1 implementation

Preflight checks the repository and Docker storage drives, verifies a local
Docker Desktop WSL2 engine, and fails before a pull if the conservative 12 GiB
core reserve would leave less than 15 GiB. Policy thresholds cannot be lowered
through `.env`. The warning remains 25 GiB. A second disk check follows pulls.

Core images have immutable digests; the WebUI slim variant omits the local ML
stack. Docker logs rotate at 10 MB x 3 per container. No prune/volume deletion or
VHDX relocation/compaction is performed. See BUILD_STATUS for actual image,
volume and host free-space measurements; host disk delta includes concurrent
activity and is not a precise measure of this project's physical allocation.

## Phase 2 increment

No additional image or model was pulled for Phase 2. The gateway adds the small
`policy-data` SQLite volume; its initial ledger is 28,672 bytes. No existing volume
was replaced. Preserve its monthly debits during Phase 3 recovery work. Current
host/global Docker measurements are recorded in BUILD_STATUS, separately from
this project's attributable footprint.

## Phase 3 recovery storage

Backups include three volume archives, local secrets/configuration and tracked
source. Recovery retains fresh volumes plus comparison archives; no image layers
are duplicated. The guard checks recovery and Docker storage locations with a
reserve of three times the measured volume bytes plus 1 GiB, retaining at least
15 GiB free. Packaged AppData paths are resolved before Docker mounts.
Failed and successful rehearsals are retained for review; no automatic prune or
volume deletion occurs. See BUILD_STATUS for measured artifact sizes and remaining
space. Off-machine encrypted retention is not configured by this local workflow.
