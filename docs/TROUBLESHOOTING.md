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

## 2026-09-29: Runtime probe assumed two providers

PR #8 review identified hard-coded OpenAI-to-Gemini expectations in the synthetic
runtime probe. This failed for supported single-provider installations. The probe
now derives primary/fallback expectations from the resolved route. `-Matrix`
creates isolated both-provider, OpenAI-only, Gemini-only and no-provider fixtures.
The single-provider outage cases expect a bounded failure rather than a nonexistent
fallback. All four initial fixtures passed; completion evidence is in BUILD_STATUS.

## 2026-09-29: Windows localhost timeouts resolved with WSL NAT

PostgreSQL/LiteLLM/WebUI container health and internal auth/login/discovery pass.
Windows curl and Edge cannot reach 127.0.0.1:3000 or :4000. Docker lists correct
loopback forwards; `Get-NetTCPConnection` shows no listener for those ports.
Docker's logs also report its existing Kubernetes localhost API timing out.
The failing host used WSL 2.7.14.0 / kernel 6.18.33.2, Windows build
26200.9550 and Docker Desktop 4.92.0 (Engine 29.8.0), with mirrored networking.

Desktop restart, gateway recreation and a full WSL shutdown/restart in mirrored
mode did not fix forwarding. WSL's shared network namespace did have listening
sockets on 127.0.0.1:3000/4000; absence from `Get-NetTCPConnection` alone did not
prove absence of a listener. Ubuntu also timed out. Header-only capture showed
SYN packets reaching `loopback0` on the correct destination port without a reply.
A temporary checksum-offload diagnostic did not help and was reverted. No
firewall, reverse-path filter or portproxy changes were made.

Changing only `networkingMode=mirrored` to `networkingMode=nat` in the host's
`%USERPROFILE%\.wslconfig`, followed by Docker stop / WSL shutdown / Docker start,
restored Windows localhost access. `wslinfo --networking-mode` reported `nat`.
Windows listeners now appear on 127.0.0.1:3000/4000. Full core smoke tests pass
through both `127.0.0.1` and `localhost`, including authentication and UI model
discovery. This isolates the failure to the mirrored networking path on this
host; the underlying WSL/Windows defect is not identified.

### Recovery procedure and scope

This is a machine-local workaround, not an automatic part of project startup.
WSL configuration is global: changing mode affects Ubuntu and other WSL2
distributions, and `wsl --shutdown` interrupts all WSL sessions. NAT changes
Linux-to-Windows localhost and direct LAN access semantics. Review dependencies
and arrange the interruption before applying it to another machine.

1. Record running workload names and volume names. Back up `.wslconfig` outside
   the repository; retain unrelated settings.
2. Under `[wsl2]`, set `networkingMode=nat`. Do not broaden Compose bindings.
3. Run `docker desktop stop --timeout 90`, then `wsl --shutdown`, then
   `docker desktop start --timeout 120`, checking each command succeeds.
4. Confirm `wsl -d Ubuntu -- wslinfo --networking-mode` returns `nat` and wait
   for all three core services to become healthy. Initial connections may return
   an empty response during application startup.
5. Run `./scripts/manage.ps1 test` without `-ContainerOnly`, then open
   `http://localhost:3000` in a browser. Verify existing workloads and volumes.

The target backup is `%USERPROFILE%\.wslconfig.gatewayai-20260929-034824.bak`.
To roll back, restore that file to `.wslconfig` and repeat the stop/shutdown/start
sequence during an arranged interruption. The mirrored-mode failure may return.
No Windows reboot or rollback test has been performed. No services were exposed
to the LAN and no optional components, models or images were installed.

References: [Microsoft WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking)
and [global WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config).
Browser acceptance is recorded separately in [BUILD_STATUS.md](BUILD_STATUS.md).

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
