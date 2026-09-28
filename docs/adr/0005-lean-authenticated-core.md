# ADR 0005: Lean, authenticated Phase 1 core

Status: Accepted for Phase 1 implementation.

## Decision

Pin registry-verified image digests. Use LiteLLM's database image, Open WebUI's
slim image, PostgreSQL for gateway state and WebUI's default SQLite volume.
Start with zero models when credentials are absent. Expose only loopback ports,
isolate the database network, and restrict the WebUI gateway key to model listing
and chat-completion endpoints.

## Rationale and consequences

This preserves the central gateway without bundled models or provider/master
credentials in WebUI. Cloud aliases and model IDs remain configurable. Local
embeddings, speech and document-processing engines are outside Phase 1.
Environment configuration takes precedence at startup, so admin configuration
changes revert on restart. Host/browser access and provider inference require
separate evidence from container health.

Checked 2026-09-29: [LiteLLM deployment](https://docs.litellm.ai/docs/proxy/docker_quick_start),
[virtual keys](https://docs.litellm.ai/docs/proxy/virtual_keys),
[WebUI image variants](https://docs.openwebui.com/getting-started/quick-start/),
[WebUI configuration](https://docs.openwebui.com/reference/env-configuration/).
