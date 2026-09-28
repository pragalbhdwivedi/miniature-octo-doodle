# Providers

## Initial providers
- OpenAI
- Gemini

## Optional providers
- Anthropic Claude
- OmniRoute
- additional OpenAI-compatible endpoints
- local Ollama

## Rules
- provider absence must not break the entire platform
- credentials stay out of Git
- model identifiers are configurable
- free/unknown providers must not receive sensitive workloads automatically
- local-only routes must have no cloud fallback
