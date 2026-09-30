# OpenViking

OpenViking is reserved for persistent contextual memory.

## Intended responsibility
- project context
- resources
- prior agent work
- decisions and durable memories
- reusable skills/context

## Non-responsibility
It is not the source of truth for source code. Git/GitHub remains canonical.

## Phase 9 status, 1 October 2026

Not installed. The current self-hosted setup needs an embedding model and a VLM
configuration as well as a persistence and recovery design. The requested two
laptop generation models do not supply that embedding setup. No extra embedding
weights, provider credential path or context service was added implicitly.
Memory ingestion, permission-scoped retrieval, compaction and restore therefore
remain untested. The first live Phase 9 increment is the bounded Graphify index;
Git-only controller behavior remains unchanged.

## Later work
Before installation, verify current upstream architecture, storage requirements, backup model, API surface, and compatibility with the Agent Controller.
