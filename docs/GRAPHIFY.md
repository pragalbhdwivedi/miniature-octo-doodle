# Graphify

Graphify is reserved for structural understanding of source repositories.

## Intended responsibility
- index repositories
- extract code relationships
- expose graph/context to agents
- support repository-aware reasoning

## Non-responsibility
It does not replace Git/GitHub.

## Phase 9 bounded deployment, 1 October 2026

Graphify `graphifyy==0.9.72` is installed in an isolated Python venv under the
unprivileged `gatewayai-context` account on VM9125. Its source is a shallow,
public-only clone of this repository's main branch at
`8c57104bcf7d1386bf5f0075a0febaff9e526a22`. No Git hooks, agent skills,
provider keys, containers or host sockets were added. The account's home is mode
`0700`; source, venv and index live there, outside Git and the live core volumes.

`graphify extract --code-only --max-workers 2` used local AST parsing and no LLM
backend. The optional `tree-sitter-sql==0.3.11` parser was then added to the VM
venv to cover the three previously omitted SQL files. A fresh exact-main rebuild
now contains 580 nodes and 1,191 edges. A bounded `publishing` query returned
symbol references from that graph. No model or paid provider was called.

`scripts/graphify_context.py` provides a read-only, public-worker/operator query
gate. `--build` extracts into a fresh temporary directory, checks the source SHA
before and after extraction, then publishes the graph and SHA-256 provenance
manifest. Each `--query` checks the exact public remote, clean checkout, live
GitHub main SHA, stamp and graph hash before returning capped, advisory context.
Stale or modified source/graph and unapproved roles fail closed. Git source always
wins; graph output cannot grant tool, spending or publication authority. The
wrapper was live-tested on VM9125 and its stale/role/mid-build cases have unit tests.

`scripts/controller_graph_preview.py` adds an operator-only, read-only sidecar
for an exact public GatewayAI main plan. It refuses a different project, ref or
source SHA and returns capped advisory graph context alongside the plan hash.
It does not edit the plan or call a model, worker, dispatcher or publisher.
A synthetic exact-main plan was run through this sidecar on VM9125 and returned
the expected source SHA, `advisory_only`, zero model calls and no actions. The
synthetic plan was removed afterward. This is not a real controller dispatch.

Rebuild after main changes: refresh the public clone, then run `--build` once.
Until this completes, queries fail as stale. Persistence
is a rebuildable index, not authoritative state; no Graphify backup/restore has
been claimed. Automatic controller prompt use, private-repository permission
mapping, incremental reindexing and context-quality evaluation remain pending.
