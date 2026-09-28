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
                        ┌──────▼──────┐
                        │ AI GATEWAY  │
                        │  LiteLLM    │
                        └──────┬──────┘
                               │
      ┌──────────────┬─────────┼──────────┬──────────────┐
      │              │         │          │              │
      ▼              ▼         ▼          ▼              ▼
   OpenAI          Gemini    Claude    OmniRoute        Local
 Sol/Terra/Luna      API       API     Free APIs       Ollama
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

### LiteLLM
Mandatory central OpenAI-compatible gateway. Provider keys live behind the gateway whenever practical.

### Open WebUI
Initial human-facing browser interface.

### Ollama
Optional local inference. No model is downloaded by default.

## Initial deployed architecture

```text
Browser
  -> Open WebUI
  -> LiteLLM
      -> OpenAI
      -> Gemini
  -> PostgreSQL for gateway state
```

## Core principle
Document the full architecture now, install components only when they are needed and disk capacity allows it.
