# AI Gateway

LiteLLM is the mandatory central gateway.

## Client rule
Applications should use a single OpenAI-compatible endpoint exposed by LiteLLM instead of embedding separate provider SDKs wherever practical.

## Capability aliases
Examples:
- coding-fast
- coding-standard
- coding-hard
- architecture
- review
- documentation
- local-private

Provider/model mappings remain configurable.

## Routing principle
Aliases express intent. Provider-specific model identifiers are implementation details and must be verified at deployment time.

## Privacy
`local-private` must only route to a local provider and must not fall back to cloud APIs.
