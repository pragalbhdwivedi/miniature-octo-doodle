# Kubernetes

Phase 4 is PARTIAL. The local core and Ingress HTTP/API checks pass. Browser
acceptance, live provider inference and migration of existing Compose data are
pending. This is a fresh, zero-spend validation instance, not a cutover.

## Tested target and scope

- Dedicated `gatewayai` k3d 5.9.0 cluster, one k3s 1.35.5 server limited to 6 GiB RAM.
- Existing Docker Desktop context/workloads stay separate. Commands use a private
  kubeconfig and explicit `k3d-gatewayai` context; no default context switch.
- Same three digest-pinned core images as Compose; three fresh PVCs, one replica
  per service with `Recreate` updates. Do not scale the SQLite-backed gateway.
- Traefik Ingress on `http://127.0.0.1:3080` (also `localhost:3080`); Kubernetes API
  on `127.0.0.1:6550`. PostgreSQL and LiteLLM have only ClusterIP services.
- Fresh random secrets, scoped WebUI inference key, blank cloud credentials,
  budget zero, Jev disabled. Eight template aliases support discovery/policy tests;
  their presence does not mean live inference is available.
- Default-deny NetworkPolicy allows DNS, Traefik-to-UI, UI-to-gateway and
  gateway-to-PostgreSQL. External egress is denied, including from the gateway.
- No optional provider, model weights, agent or extra observability module.

## Commands (PowerShell, repository root)

Create `.venv` and install `requirements-ci.txt` if the existing validation
environment is absent. Docker Desktop/WSL2, `kubectl` and Python are prerequisites.

```powershell
# One-time creation; refuses an existing cluster.
./scripts/kubernetes.ps1 cluster
# Deploy/update validation core; never reads the live .env.
./scripts/kubernetes.ps1 deploy
./scripts/kubernetes.ps1 test
# Preserve all data while changing runtime activity.
./scripts/kubernetes.ps1 stop
./scripts/kubernetes.ps1 start
```

Cluster creation downloads the checksum-verified k3d binary into ignored `tmp/tools`
and Kubernetes infrastructure images. The k3s image has a reviewed immutable digest.
Bundled Traefik, DNS, local-path provisioner, ServiceLB and k3d helpers are required
infrastructure; metrics-server is disabled. The node pulls the application images
on first deployment. No local model is downloaded.

Preflight preserves 15 GiB critical / 25 GiB warning thresholds. Cluster creation
reserves 8 GiB; deployment reserves 4 GiB before application image pulls. Actual
host delta was approximately 4.09 GiB, including concurrent activity. Never delete
clusters, namespaces, PVCs or Docker volumes as a routine stop step.

Private credentials and kubeconfig live under physically resolved
`%LOCALAPPDATA%/GatewayAI/kubernetes`, outside Git/OneDrive, with current-user and
SYSTEM ACLs. Packaged terminals may resolve this into their package LocalCache;
the wrapper prints the actual directory, never secrets. `credentials.json` contains
the test WebUI login (`admin@gatewayai.local`) and random password. Keep it private.
K3s secrets encryption is enabled; cluster administrators still have full access.

`deploy/k8s/base/core.yaml` defines only core resources; the local overlay adds
Ingress. The deployment script supplies ConfigMaps from tracked code/policy,
generates Secrets, validates against the server, applies over stdin without
logging credentials, and waits for readiness. Applying the base alone does not
supply its required generated resources. Optional overlays need separate approval.

## Validation and remaining gates

`test` makes no cloud inference requests. It checks internal authentication,
restricted key scope, eight aliases, zero-budget denial, host Ingress login/model
discovery through both localhost names, database isolation and external TCP egress
denial. The synthetic routing/fallback/concurrency/streaming suite uses temporary
ledger state and loopback mock upstreams inside the pinned gateway.

All three pods were recreated with Compose stopped: PVC identities, administrator
login, scoped gateway key and tests survived. Compose was then resumed. This is
same-host persistence/independence evidence, not off-machine recovery.

The browser connector blocked the local URL. Native Computer Use stopped because
it could not determine the browser URL for policy enforcement. Browser rendering
and rendered chat remain unvalidated; complete that gate in a later browser session.

Before enabling Kubernetes cloud inference, select the real target and migration
scope, preserve/reconcile monthly debits, transfer trusted data and credentials,
explicitly permit gateway HTTPS egress, and validate bounded provider/browser
requests. These scripts deliberately have no live activation switch. Do not reset
the existing US$100 monthly budget by using this empty ledger.

Kubernetes PVC backup/restore, cluster restart/reboot, separate-machine recovery,
TLS/LAN exposure and production cutover remain unvalidated. The prior new-machine
recovery pause remains: a local k3d cluster is not a separate recovery machine.
See [build evidence](BUILD_STATUS.md) and [ADR 0010](adr/0010-isolated-kubernetes-validation.md).

Upstream references verified during implementation:
[k3d releases](https://github.com/k3d-io/k3d/releases/tag/v5.9.0),
[Ingress mapping](https://k3d.io/v5.8.3/usage/exposing_services/),
[K3s networking](https://docs.k3s.io/networking/networking-services).
