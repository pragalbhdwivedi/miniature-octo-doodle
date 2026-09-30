# Persistent state and controlled dispatch

This is an operator-only CLI, not a model tool or daemon. The unprivileged
`controller.py` remains read-only. Never grant an agent sudo, this dispatch CLI,
the host Docker socket or the controller database role.

## Provisioning

Reuse the approved local PostgreSQL container; check free disk first (16 GiB
required including reserve). No image, driver or service installation is needed.
Run `scripts/controller-init.py --container SELECTED_POSTGRES --admin-role ADMIN`
as the approved Linux administrator. This creates only a dedicated
`gatewayai_controller` database and two new roles. It refuses existing named
objects rather than adopting or modifying them. A partially failed first install
requires manual inspection; do not drop existing objects or blindly rerun it.

`gatewayai_controller_owner` is NOLOGIN and owns the schema. The runtime role
`gatewayai_controller` has no password, superuser, create-role or create-database
privileges. It uses the existing trusted local socket through administrator-owned
Docker exec; password-based network authentication remains unavailable to it.
Runtime mutations are limited to claim/finish functions, with SELECT for status.
It cannot directly change/delete runs or audit events, create schema objects or
read gateway tables. Host/database administrators are outside this boundary.

Prepare root-owned 0600 `/etc/gatewayai-controller/dispatch.json`, outside Git:

```json
{
  "container": "SELECTED_POSTGRES",
  "database": "gatewayai_controller",
  "runtime": "/var/lib/gatewayai-controller",
  "worker_runtime": "/var/lib/gatewayai-worker",
  "image": "sha256:VERIFIED_IMMUTABLE_WORKER_IMAGE",
  "coding_config": "/etc/gatewayai-worker/coding.json"
}
```

Both runtime directories must be root-owned 0700. Keep code/config registries
administrator-owned. This file contains locations, not copied gateway secrets.

## Prepare, review, dispatch

```sh
sudo python3 scripts/controller_dispatch.py prepare --config /etc/gatewayai-controller/dispatch.json
# Inspect the emitted request: source, task, commands, paths, image and budget.
sudo python3 scripts/controller_dispatch.py dispatch --config /etc/gatewayai-controller/dispatch.json \
  --request /var/lib/gatewayai-controller/RUN_ID.json --approve-sha256 REVIEWED_DIGEST
sudo python3 scripts/controller_dispatch.py status --config /etc/gatewayai-controller/dispatch.json --run-id RUN_ID
```

Preparation uses only the current committed, labelled, unowned eligible task.
The default budget is zero, suitable for offline jobs. A coding job requires
explicit `prepare --budget-usd AMOUNT` in (0, 1]; the amount becomes part of the
reviewed digest. The worker's permanent reservation and gateway monthly allowance
both remain enforced. No new model call is needed for the offline acceptance.

Dispatch refreshes source, governance, task, ownership and dependencies again.
Any selected-plan change rejects before claim. The database commits the claim
and audit event before invoking the worker with a fixed ID/source SHA. A worker
fetch race rejects before model/sandbox execution. GitHub metadata can still
change after the final read; there is no cross-system atomic transaction.

The worker cannot access the database or dispatch configuration. Normal completion
validates source/job/artifact hashes and cleanup before `review_required`; this
is not code review, publication or merge approval. That state retains task
ownership across source changes until the future independent-review workflow.
No automatic publishing, retry, scheduler or spend loop exists.

## Interrupted runs and recovery

`dispatching` is durable before invocation. Errors with ambiguous execution become
`uncertain`, retaining the single active-host claim. No lease expires this claim.
`reconcile --run-id RUN_ID` reads the existing result and immutable artifacts under
the same operator lock; it never executes a worker. Missing, mismatched or failed
cleanup evidence stays uncertain. There is no force-unlock/reset/retry command.
Inspect the exact worker container and private evidence before manual recovery.

Audit states: dispatching -> review_required / failed / uncertain;
uncertain -> review_required / failed / uncertain through evidence reconciliation.
Terminal runs never transition back to execution; the project/task/source tuple
can never be reclaimed. A task awaiting review also cannot run at a newer SHA.

The database lives in the existing PostgreSQL volume and is covered by whole-volume
cold snapshots taken **after** provisioning. Old backups do not contain it. Retain
the controller requests together with worker source/results/publication journals
and the coding-budget ledger in protected storage. Freeze dispatch before backup
or restore; reconcile all newer claims/artifacts/debits before reopening execution.
Never use an old database/ledger to regain attempt or spending capacity. Separate-
machine controller recovery and coordinated backup remain unvalidated.

## Validation

Unit tests cover changed approval/source/job, budget/image/authority denial,
DB-before-worker ordering, ambiguous failures, exact worker ID and fetch pin.
`tests/test_controller_postgres.py` is opt-in via a private
`GATEWAYAI_CONTROLLER_TEST_CONFIG` containing only `container`/`database`; it
accepts only `gatewayai_controller_test_<8 hex>` databases with the same schema.
It exercises real concurrent claims, fresh connections, audit ordering, replay,
review ownership and denied direct mutations. Use BUILD_STATUS for actual runs;
passing fixtures alone does not prove live repository dispatch.

Live acceptance on 30 September passed the committed zero-spend task, source pin,
durable claim, worker execution, cleanup and completion-failure reconciliation.
The first smoke fixture failed safely and was corrected in a new reviewed commit;
its audit record remains. See [BUILD_STATUS](BUILD_STATUS.md) for exact evidence.
The synthetic task is now done; prepare blocks until another approved task exists.
