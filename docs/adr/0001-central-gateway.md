# ADR 0001: LiteLLM as central AI gateway

Status: Accepted

## Decision
Use LiteLLM as the central OpenAI-compatible gateway.

## Rationale
It separates clients from provider-specific credentials and model identifiers, enables routing/fallback/budget policies, and keeps future provider additions from requiring application rewrites.

## Consequence
Applications should connect to LiteLLM whenever practical.
