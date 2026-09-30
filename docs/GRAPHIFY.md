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
backend. It indexed 78 code files into 555 nodes, 1,158 edges and 49 communities.
The index and venv occupy about 202 MiB. Three SQL files lacked the optional SQL
parser and were omitted. `cluster-only --no-label --no-viz` regenerated the report,
and `graphify query publishing` returned bounded symbol references. No production
controller lookup has been enabled.

`scripts/graphify_context.py` provides a read-only, public-worker/operator query
gate. `--stamp` records the source commit and graph SHA-256 after a completed
extraction. Each `--query` checks the exact public remote, clean checkout, live
GitHub main SHA, stamp and graph hash before returning capped, advisory context.
Stale or modified source/graph and unapproved roles fail closed. Git source always
wins; graph output cannot grant tool, spending or publication authority. The
wrapper was live-tested on VM9125 and its stale/role cases have unit tests.

Rebuild after main changes: refresh the public clone, run the code-only extraction,
then stamp again. Until this completes, queries should fail as stale. Persistence
is a rebuildable index, not authoritative state; no Graphify backup/restore has
been claimed. Controller integration, private-repository permission mapping,
incremental reindexing and context-quality/compaction evaluation remain pending.
