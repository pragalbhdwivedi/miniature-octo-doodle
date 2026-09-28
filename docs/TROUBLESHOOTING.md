# Troubleshooting

Expand this file with real failures and tested fixes as implementation proceeds.

Initial categories:
- Docker Desktop / WSL2
- disk pressure
- NVIDIA GPU visibility
- LiteLLM startup
- PostgreSQL connection
- Open WebUI connection
- provider authentication
- Kubernetes networking
- Ingress
- optional component installation

Do not invent successful fixes. Record tested resolutions.

## 2026-09-29: healthy containers, Windows localhost timeouts (unresolved)

PostgreSQL/LiteLLM/WebUI container health and internal auth/login/discovery pass.
Windows curl and Edge cannot reach 127.0.0.1:3000 or :4000. Docker lists correct
loopback forwards; `Get-NetTCPConnection` shows no listener for those ports.
Docker's logs also report its existing Kubernetes localhost API timing out.
WSL uses mirrored networking, but causation has not been established.

An explicitly authorized Docker Desktop restart restored running workloads but
did not fix forwarding. Recreating the gateway also did not repair host access.
Keep the host-access milestone BLOCKED. Do not widen bindings to all interfaces,
disable firewalls or delete volumes to bypass this result. Further diagnosis
should inspect Desktop port forwarding and WSL/Windows network state, then
re-run `manage.ps1 test` and check the browser. `-ContainerOnly` is diagnostic only.

## Resolved implementation findings

- Candidate LiteLLM version tags with `-stable` did not exist; registry verification
  selected the published database v1.103.0 image and pinned its digest.
- Explicit model names on the WebUI virtual key exposed unavailable aliases even
  with no configured providers. A key following registered proxy models, restricted
  to listing/chat endpoints, plus disabled WebUI arena now yields empty lists.
- Compose does not recreate a service solely because a bind-mounted config changed.
  Guarded startup explicitly recreates LiteLLM, preserving its PostgreSQL volume.
- Environment restoration must remove originally absent variables, rather than
  creating empty variables that override `.env`. Regression test covers this.
