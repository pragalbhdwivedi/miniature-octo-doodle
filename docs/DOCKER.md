# Docker

Docker Compose is the first operational deployment.

## Default startup
The default Compose configuration must start only the lightweight core.

## Optional profiles
Planned:
- local-ai
- memory
- graph
- free-providers
- coding-agent
- observability

An ordinary `docker compose up` must not pull all optional images.

## Host safety
Do not mount the Docker socket into the web UI or coding agent unless a later reviewed design explicitly requires it and documents the risk.
