# Kubernetes deployment

`base/core.yaml` defines the three core services, persistent claims, limited
service account and default-deny networking. `overlays/local/ingress.yaml`
exposes only WebUI through the dedicated k3d cluster's loopback Ingress.

Use `scripts/kubernetes.ps1`; it supplies private Secrets and tracked ConfigMaps,
sets local-path storage, performs server validation and waits for readiness.
Directly applying the base alone does not supply those required resources.

This is a tested zero-spend validation instance with fresh data. Browser acceptance
passed; live data/provider migration remains pending. See [operations](../../docs/KUBERNETES.md).
No optional overlay is installed. Never delete PVCs or clusters to stop the runtime.
