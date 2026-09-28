# Providers

## Initial providers
- OpenAI
- Gemini

Both credentials are empty in the deployed configuration by user instruction.
Neither provider has been called or validated against an account.

| Variable | Configurable example | Purpose |
|---|---|---|
| OPENAI_MODEL | openai/gpt-5.4-mini | Full LiteLLM provider/model identifier |
| OPENAI_ALIAS | openai-chat | Client-visible alias |
| GEMINI_MODEL | gemini/gemini-3.1-flash-lite | Full LiteLLM provider/model identifier |
| GEMINI_ALIAS | gemini-chat | Client-visible alias |

Identifiers were checked on 2026-09-29 against [OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
and [Google model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite).
They are examples, not claims of account access or latest-model recommendations.

Set `OPENAI_API_KEY` and/or `GEMINI_API_KEY` only in local `.env`. Use unquoted
`NAME=value` lines; the parser rejects whitespace, quotes, interpolation and
inline comments in values. Missing keys omit routes without preventing startup.
Run `manage.ps1 start` after edits, then `manage.ps1 test`. A provider completion
test is a separate step with a small synthetic prompt; core tests never send one.

WebUI receives a key restricted to model listing and chat-completion endpoints
for registered proxy models. It cannot administer gateway keys. No wildcard
model or fallback is configured. `local-private` is reserved and rejected as a
cloud alias. Capability routing, budgets and fallbacks remain Phase 2 work.

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
