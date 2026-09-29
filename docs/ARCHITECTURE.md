# Architecture

## Canonical target

```text
                              YOU
                               │
                     Coding UI / Agent
                               │
                    ┌──────────▼──────────┐
                    │   Agent Controller  │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
     OpenViking             Graphify           Git / GitHub
       Memory              Code Graph          Source Truth
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Deterministic Policy│
                    │ auth/data/approval  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ TypeSafe Jev       │
                    │ choice/score/prob. │
                    └──────────┬──────────┘
                               │
                        ┌──────▼──────┐
                        │ AI GATEWAY  │
                        │  LiteLLM    │
                        └──────┬──────┘
                               │
      ┌──────────────┬─────────┼──────────┬──────────────┐
      │              │         │          │              │
      ▼              ▼         ▼          ▼              ▼
   OpenAI          Gemini    Claude    OmniRoute        Local
      API             API       API     optional       Ollama /
                                                llama.cpp
                                                        │
                                                 GTX 1650 Ti
                                                   + 64 GB RAM
```

## Architectural roles

### Git/GitHub
Canonical source code and project history.

### Graphify
Structural representation of repositories and relationships in code. It augments Git; it does not replace it.

### OpenViking
Persistent contextual memory for agents, decisions, resources, and prior work. It augments Git; it does not replace it.

### Agent Controller
Future orchestration layer for architect, implementer, tester, reviewer, security, and documentation agents.

### Deterministic policy layer
Hard rules decide whether a task is permitted, which data classification applies, whether cloud execution is allowed, which tools are available, whether a human approval is mandatory, and which spend/concurrency limits apply. A probabilistic model cannot override these rules.

### TypeSafe Jev
Planned Phase 2 structured decision layer. Where validated, Jev may return typed choices, scores, or probabilities for task classification, complexity, routing, risk, or escalation. Jev is decision intelligence, not authority and not a generative coding model.

If Jev is unavailable, outside the evaluated task domain, malformed, or below the configured confidence/calibration threshold, the controller must use a deterministic fallback, fixed compliant route, or human review.

### LiteLLM
Mandatory central OpenAI-compatible gateway. Provider keys live behind the gateway whenever practical. LiteLLM performs the final provider/model routing only after deterministic policy and, where enabled, Jev decisioning.

### Open WebUI
Initial human-facing browser interface.

### Ollama / llama.cpp
Optional local inference. No model is downloaded by default.

## Routing trust rule

Fallback must never broaden data exposure.

Examples:
- `local-private` has no cloud fallback.
- a private route may fall back only to providers explicitly approved for the same data class.
- a free/experimental OmniRoute provider cannot become an implicit fallback for private work.
- a Jev recommendation cannot grant a provider, tool, data, or production permission that policy denied.

## Initial deployed architecture

```text
Browser
  -> Open WebUI
  -> LiteLLM
      -> OpenAI
      -> Gemini
LiteLLM -> PostgreSQL for gateway state
Open WebUI -> its persistent SQLite volume for UI state
```

The Phase 1 runtime is validated and PR #6 is merged. Phase 2 adds deterministic
policy as LiteLLM callbacks, plus a persistent `policy-data` SQLite admission ledger.
It requires no additional service/image. Jev live execution remains disabled;
only its offline decision contract is tested. See [ADR 0007](adr/0007-phase2-local-policy-ledger.md).

## Core principle
Document the full architecture now, install components only when they are needed and disk capacity allows it.

## Phase 1 implementation boundary

Compose defines only PostgreSQL, LiteLLM and Open WebUI. Cloud routes are included
only when their keys exist in local `.env`. WebUI receives a restricted gateway
inference key; provider keys and the master key remain in LiteLLM. The database
network is internal and PostgreSQL has no host port. UI/gateway ports bind to
127.0.0.1. See [ADR 0005](adr/0005-lean-authenticated-core.md).

The full Agent Controller, live Jev and optional local/provider-aggregation layers
remain targets. The current policy only admits public/synthetic text to the two
configured cloud providers; private/local-only inputs fail closed.
