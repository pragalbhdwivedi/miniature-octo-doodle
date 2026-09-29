# ADR 0008: Accept Phase 2 with Jev disabled

## Decision - 2026-09-29

The user requested: "Complete phase 2 (setup everything but disable jev for now).
If everything works then merge PR."

Phase 2 acceptance now covers the configured deterministic gateway, capability
aliases, bounded fallbacks, budget/concurrency enforcement, privacy/tool/approval
denials, provenance, provider-absence behavior and browser operation. Jev is
explicitly disabled, rather than a blocker to accepting this operational scope.
This supersedes the live-Jev prerequisite in ADR 0006 and the earlier PARTIAL
status in ADR 0007. It does not change the authority separation in either ADR.

The tracked decision-plane configuration selects deterministic mode and sets
`jev_enabled: false`. Rendering and gateway startup reject attempted activation.
The local key placeholder and offline Choice adapter/authority tests remain
prepared. No key is injected into containers, no Jev service/client is started,
and providing a key alone cannot activate it.

## Deferred activation gate

Live Jev integration, labelled shadow evaluation, model/domain validation,
accuracy/calibration and threshold review remain unvalidated and deferred until
separately authorized. They are not reported as working or complete. Activation
requires a reviewed implementation change, a locally configured key and an
explicit evaluation allowance. Jev never grants provider/tool/data permissions.

Local-private remains an enforced unavailable route with no cloud fallback;
installing a local inference engine/model is still optional, outside Phase 2.
No other deferred provider, model, controller, Kubernetes or memory component is
authorized by this acceptance. Phase 3 recovery is the next bounded milestone.
