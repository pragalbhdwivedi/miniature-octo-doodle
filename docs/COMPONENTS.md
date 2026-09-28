# Components

The machine-readable catalog lives in `config/components.yaml`.

## Core
- LiteLLM
- PostgreSQL
- Open WebUI
- OpenAI configuration
- Gemini configuration

## Optional
- Claude
- OmniRoute
- Ollama
- local model
- OpenViking
- Graphify
- coding agent
- Agent Controller

## Lifecycle
A component may be:
- available
- installed
- running
- stopped
- update_available
- unsupported
- blocked

The management utility will eventually expose install/status/remove operations while enforcing disk safety.
