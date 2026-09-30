# Phase 6 isolated worker

Status: zero-spend execution boundary DEPLOYED AND TESTED; overall Phase 6 PARTIAL.
This first milestone is the zero-spend
execution boundary. It does not yet install a model-driven coding agent, publish
worker changes to GitHub, or implement the Phase 7 controller.

The user authorized the next phase on 30 September 2026. Phase 5 recovery and
client trust gates remain open independently; this does not mark them complete.

## Roles and boundaries

An approved Linux administrator runs `scripts/worker.py`. It is a privileged
operator tool, never a worker command, WebUI integration, service API or agent
tool. It uses the local Docker daemon to create one restricted container per run.
Do not give a coding agent access to this broker, sudo or the host Docker socket.

The broker fetches only the public repository/ref pairs in
`config/worker/projects.json`, without credentials, hooks, global/system Git
configuration or interactive prompts. The initial registry permits this gateway
repository's `main` only. AADI is not activated by its appearance in the roadmap.
Every fetch resolves and records the current commit. The operator must reconcile
the repository's instructions and ownership before supplying a job; the worker
does not select tasks or interpret approvals.

The worker receives a read-only source archive and job declaration. It creates a
fresh Git repository/`worker/<run-id>` branch in a private tmpfs, then executes
explicit command argument arrays. Shell commands may be used **inside this
sandbox**, never on the host. The worker has:

- UID/GID 65532, read-only image, all capabilities dropped, no-new-privileges,
  default seccomp, no host-write mounts or Docker socket;
- no network, gateway key, provider key, SSH key, kubeconfig or production state;
- one CPU, 768 MiB RAM with no additional swap, 64 PIDs and 256 file descriptors;
- 256 MiB workspace and 64 MiB temporary storage; 16 MiB per-file limit;
- at most eight commands, 30 seconds per command, up to 120 seconds per execution
  run and an independent 150-second container lifetime if the broker disappears;
- two MiB captured output per command, at most 20 exact writable artifact paths
  and one MiB of changed artifact content.

This is container isolation on the control VM, not a separate kernel/VM boundary.
Do not activate unreviewed third-party jobs or production repositories here. A
separate worker VM/hardened runtime remains an option before broader activation.

## Build and run

Use an approved native Linux Docker host and a private root-owned directory
outside the checkout. Before building, check both runtime and Docker storage:
retain the repository's 15 GiB floor plus at least 1 GiB build/run reserve.
The worker does not require a GPU, models, Node, Codex CLI or extra services.

```sh
docker build -t gatewayai-worker:phase6 deploy/worker
docker image inspect gatewayai-worker:phase6 --format '{{.Id}}'
sudo python3 scripts/worker.py \
  --job config/worker/smoke-job.json \
  --image sha256:REPLACE_WITH_VERIFIED_LOCAL_IMAGE_ID
```

The Dockerfile pins the Python base digest and installs Git from signed Debian
repositories. Capture the resulting image ID and versions with each deployment;
APT packages can change during future rebuilds. Runtime requires the immutable
local image ID and never pulls implicitly. The smoke job creates a synthetic
file only in the disposable workspace and commits it locally; it does not push.

The root-only broker serializes runs with a lock and checks disk reserves again
before fetching. Git fetch has a 60-second limit, 512 MiB address-space limit and
64 MiB per-file ceiling; archive creation has the same memory/file bounds;
the source archive has a 32 MiB/10,000-file ceiling. Symlinks, hard links,
submodules and special source files are unsupported and fail closed.
Model budget must be zero. Supplying credentials or enabling spend is not a
supported job option, and no cloud fallback exists in this executor.

Target acceptance on 30 September 2026 passed fresh main fetch, synthetic
edit/test/local commit/artifact export, resource/privilege/filesystem/network
checks, timeout/output/path/history/symlink/default-branch-push denial and
disposable-worker recreation. Independent lifetime ended after 151.35 seconds.
No test container remained and no provider attempt was added. Full evidence and
known limits are in [BUILD_STATUS](BUILD_STATUS.md).

## Results and review

Each private run directory contains the resolved source, command logs,
`result.json`, and, on successful execution/export, `changes.json` and
`review.patch`. The authoritative artifact includes original file hashes,
new content and modes. The human-readable diff is for review, not an automatic
authorization to apply/publish. Binary changes are unsupported.

Export compares the workspace against the immutable original source archive,
not the worker's mutable Git index/history. Unexpected paths, symlinks and
oversized output fail closed. Result `review_required` means bounded execution
and artifact checks passed; it is not independent code review or a merge gate.
Tests can themselves be changed by an untrusted job, so their exit codes are
execution evidence rather than proof that the generated change is correct.

All containers are removed by exact run identity on success/failure; core
services and persistent volumes are never pruned. Broker interruption may leave
a stopped container after the independent timeout; the operator should inspect
only `gatewayai.role=isolated-worker` identities before removing a named residue.
Audit/snapshot artifacts are retained. No automatic retention/deletion is enabled.

## Recovery and remaining Phase 6 work

Rebuild the worker image from the tracked Dockerfile, record its new image ID,
then run a fresh job against a new fetched snapshot. No prior worker workspace
or secret is required. This is disposable-worker recovery, not live gateway
restore or separate-machine recovery evidence.

Remaining: a coding-agent executor through the central gateway with explicit
per-run cost reservations, operator-mediated publication to scoped review
branches, default/protected-branch denial at that boundary, and live end-to-end
coding/publishing acceptance. No default-branch push path currently exists.
Project-scoped GitHub credentials must stay outside the worker. Controller task
selection and Telegram approvals remain Phases 7 and 8.

The isolation flags follow [Docker's runtime controls](https://docs.docker.com/engine/containers/run/).
