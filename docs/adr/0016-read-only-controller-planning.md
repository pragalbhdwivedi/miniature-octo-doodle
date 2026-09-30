# ADR 0016: Begin Phase 7 with read-only repository planning

Date: 30 September 2026. Status: implemented and bounded validation passed.

The user requested Phase7 after reviewing the existing PR stack. Phase6 live
publishing remains blocked by the missing repository-scoped credential. Begin
independent controller work without widening the worker's authority.

The first controller CLI fetches an approved public repository, current issue/PR
inventory and governance, then selects only an explicitly committed, labelled,
unowned task whose dependencies are complete. It emits a zero-budget plan tied
to the exact source and evidence hashes. It does not execute repository code,
invoke the privileged worker broker, call models, mutate GitHub or merge.

Missing/conflicting evidence causes a blocked plan. AADI remains disabled until
its own authority/branch contract is reconciled. No inference from roadmap text
alone can approve a task or production action.

Private JSON files are disposable review artifacts for this milestone, not a
replacement for the canonical PostgreSQL run/audit backend. PostgreSQL state,
atomic claims, dispatch, independent review, repair and publication orchestration
remain later Phase7 implementation. This milestone installs no daemon/image and
uses an unprivileged account for real read-only refresh acceptance.
