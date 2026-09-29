# Docker

Docker Compose is the first operational deployment. The project is named
`miniature-octo-doodle`. Use `scripts/manage.ps1` from any working directory;
it resolves this repository's files and propagates native command failures.

## Default startup
The default Compose configuration starts only PostgreSQL, LiteLLM and Open WebUI.
`init` generates local secrets once. `start` checks Docker Desktop/WSL2, daemon
and projected disk reserve, renders configuration, validates Compose, pulls only
pinned core images and waits for service health. PostgreSQL and LiteLLM start
first, then a route-scoped inference key is provisioned for WebUI.

`start -Stage gateway` stops after the gateway stage. `configure` renders the
file but does not reload the proxy; use `start` after provider changes.

The images are PostgreSQL 16.15 Alpine, LiteLLM database v1.103.0 and Open WebUI
v0.11.4-slim. Immutable index digests are in `.env.example`. No bundled local
model runtime is installed. The slim UI does not provide local embeddings,
speech or document-processing engines.

PostgreSQL uses `postgres-data`; WebUI keeps its SQLite state in `open-webui-data`.
Phase 2 gateway admission/provenance uses `policy-data`; preserve this volume
across restarts and include it in future backup/restore validation.
Compose prefixes volumes with the project name. The database network is internal.
Only LiteLLM and PostgreSQL join it; WebUI reaches LiteLLM on the core network.

`stop` preserves state. Do not delete volumes or regenerate secrets to fix startup.
Backup/restore and clean rebuild testing remain Phase 3 work. Logs rotate at
10 MB x 3 files per service. Inspect logs locally and redact sensitive upstream
errors before sharing. Use `docker compose config --quiet` to avoid printing secrets.

## Optional profiles
Deferred, not defined or installed in the core:
- local-ai
- memory
- graph
- free-providers
- coding-agent
- observability

An ordinary `docker compose up` must not pull all optional images.

## Host safety
Do not mount the Docker socket into the web UI or coding agent unless a later reviewed design explicitly requires it and documents the risk.
