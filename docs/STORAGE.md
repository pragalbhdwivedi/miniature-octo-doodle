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

## Phase 4 increment

Dedicated k3d infrastructure and its containerd core image copies consumed an
observed 4.09 GiB host delta (including concurrent activity), leaving 41.30 GiB.
No model weights are present or duplicated. The single node uses three fresh
local-path PVCs: PostgreSQL 1 GiB, UI/policy 256 MiB each. Local-path requested
capacity is not a hard disk quota; continue host preflight monitoring. Cluster
creation reserves 8 GiB and app deployment 4 GiB above the existing critical floor.
Stop the cluster to save runtime resources; deleting it can destroy PVC data.
Kubernetes backups/retention remain unvalidated and are not covered by Compose's
recovery script. No automatic cleanup is provided.

## Requested internal proxy increment

NPM 2.16.0 added one explicitly authorized image, 1,909,394,336 installed bytes.
VM free disk was 50.51 GiB before and 48.73 GiB after pulling it. Its SQLite,
proxy configuration and leaf certificates use a private host directory. The
encrypted ingress backup was 34,788 bytes and copied off VM with matching hash;
the isolated restore shares the existing image and retains its small private
state directory. No pruning, optional model download or additional database
image was performed. Ingress and core backups are distinct; preserve both and
the separate CA signing-key custody. See INGRESS.md and BUILD_STATUS.md.

## Phase 6 worker increment

The requested worker image is approximately 306 MB, including Python/Git, with no
agent CLI or local model. Pre-build VM free disk was 48.72 GiB; the post-build
sample was 48.53 GiB (shared layer compression makes this different from the
reported image size). Only trusted build steps use package-network access.
Worker writes use 256 MiB workspace/64 MiB temporary tmpfs within a 768 MiB RAM
ceiling. Private fetched source, logs and review artifacts remain on disk after
container removal; future retention is not automatic. The broker serializes runs
and reserves 1 GiB above the 15 GiB floor on both runtime and Docker storage.
