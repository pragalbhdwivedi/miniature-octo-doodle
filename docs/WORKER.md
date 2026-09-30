# Phase 6 isolated worker

Status: offline execution and gateway-backed one-turn coding DEPLOYED AND TESTED.
Scoped publication is implemented and mock/plan-tested; live publication awaits
a repository-scoped credential. Overall Phase 6 remains PARTIAL.
The Phase 7 controller is not installed.

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
Without a `coding` specification the model budget must be zero. With one, an
operator-controlled gateway adapter handles inference before container startup;
the sandbox remains offline and never receives credentials.

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

## Recovery and Phase 6 limits

Rebuild the worker image from the tracked Dockerfile, record its new image ID,
then run a fresh job against a new fetched snapshot. No prior worker workspace
or secret is required. This is disposable-worker recovery, not live gateway
restore or separate-machine recovery evidence.

Remaining acceptance: install an operator-provided repository-scoped GitHub
credential and validate actual branch/draft PR creation. The adapter below has
no default-branch update or merge operation. Controller task selection and
Telegram approvals remain Phases 7 and 8.

The isolation flags follow [Docker's runtime controls](https://docs.docker.com/engine/containers/run/).

## Gateway-backed coding

`scripts/worker_coding.py` implements one bounded model turn, not an autonomous
shell agent. The operator supplies the task, exact public context/output paths,
capability alias and independent sandbox test commands. Mandatory governance
files present in the fetched source are included. Oversized context fails closed
rather than silently dropping instructions. Only public allowlisted repositories
are supported; AADI is not activated.

The model returns full-file JSON edits. Paths, base hashes, modes, text and size
are validated before applying them inside the existing offline sandbox. A model
cannot add tools/commands, credentials, network access or publication authority.
There is one gateway call, no client retries/repair iterations, at most 1024 output
tokens and a 100-second total HTTP deadline. Sandbox execution retains its separate
120-second job maximum and independent 150-second container deadline.

Create a root-owned 0600 JSON configuration **outside Git/sync** with these fields:
`gateway_url` (local `http://127.0.0.1:4000`), `gateway_key` (dedicated chat-only key),
and `policy_file` (the actual root-owned 0600 resolved policy mounted in LiteLLM).
The VM configuration is `/etc/gatewayai-worker/coding.json`. The deployed key allows
only the five reviewed coding/documentation/review aliases and `/v1/chat/completions`;
management access was denied. Provider/master keys remain in the gateway.

Copy `config/worker/coding-job.json` to protected runtime storage and explicitly
set `model_budget_usd` (default 0 disables spending, maximum 1 USD per run):

```sh
sudo python3 scripts/worker.py --job /protected/coding-job.json \
  --image sha256:VERIFIED_IMAGE_ID --coding-config /etc/gatewayai-worker/coding.json
```

Before HTTP, `coding-budget.sqlite3` atomically and permanently reserves the same
conservative input/template/output pricing ceilings for both allowed gateway
attempts. The actual mounted policy is checked against those ceilings. A unique
run ID can be debited only once; replay, concurrent duplicate calls, insufficient
budget and policy price/attempt drift fail closed. Failed/ambiguous calls are not
refunded. The gateway separately enforces the existing $100/month allowance.
Neither ledger is a provider invoice; the run ledger is an additional limit, not
extra monthly spending capacity. Retain the ledger with the private run artifacts;
never roll it back to regain capacity. Live administrator policy changes/restarts
must be reconciled with the adapter's ceilings before further coding runs.

## Reviewed scoped publication

`scripts/worker_publish.py` is a separate operator CLI. It checks successful sandbox
cleanup, exact run/project/ref, immutable source/job hashes, approved write paths
and the SHA-256 of `changes.json`. Hidden paths/workflows and credential inventory
paths are excluded. Review both `review.patch` and authoritative `changes.json`
(including modes) before supplying the digest. The hash binds the chosen bytes;
it is not a substitute for human review or a cryptographic approver identity.

```sh
# Read-only plan; no GitHub credential or mutation:
sudo python3 scripts/worker_publish.py --run /var/lib/gatewayai-worker/RUN_ID \
  --approve-sha256 REVIEWED_CHANGES_SHA256
# Publish the exact reviewed plan:
sudo python3 scripts/worker_publish.py --run /var/lib/gatewayai-worker/RUN_ID \
  --approve-sha256 REVIEWED_CHANGES_SHA256 --config /etc/gatewayai-worker/publisher.json
```

The publisher configuration is root-owned 0600 outside Git/sync, containing
`repository` and `github_token`. The prepared VM field is empty and disabled.
Use a short-lived GitHub App installation token or fine-grained token limited to
this repository with Contents and Pull requests write permissions. The CLI checks
the configured repository; GitHub's credential permissions provide the independent
repository boundary. It cannot prove a supplied token has no broader permissions;
that must be verified during provisioning. No token is copied into the worker.

Only a new `worker/<run-id>` branch and a draft PR may be created. The fetched base
must still match GitHub's default branch SHA; stale work requires a fresh run and
review. Existing branches are never updated, forced or deleted. No merge,
production deployment or workflow-file publication operation exists. GitHub branch
rules still apply. Repository CI may run on the new branch/PR; this does not grant
permission to merge or deploy. Requests use fixed GitHub endpoints, no environment
proxy or redirects, and generic credential-free errors.

A private publication journal is written before network mutation. Partial failures
retain the journal and any created Git objects/branch; automatic retries are
blocked. Inspect the exact run on GitHub before manual recovery. A late base race
still leaves the new commit parent bound to the reviewed source. Live publishing
has not been validated without the scoped credential.

API references: [LiteLLM virtual keys](https://docs.litellm.ai/docs/proxy/virtual_keys)
and [GitHub create-reference API](https://docs.github.com/en/rest/git/refs).
