# Future development backlog

The 2 October 2026 seed of 110 proposals has been retired at the owner's request. The live supervisor cancels unadmitted proposals with a reason and retains their identifiers, text, timestamps and audit events. Git history retains the original catalogue. Completed, review-ready, blocked and already linked work stays in the live ledger; retirement does not imply integration or erase evidence.

`config/supervisor/future_tasks.json` now contains only the eight original proposals already completed or linked to intake. It is a bootstrap identity record, not a source of fresh executable work. The live queue also contains later generated proposals that have their own FUT IDs. The current GitHub repositories, registered development scopes, exact source paths and protected tests determine admission. A model proposal cannot create a new scope.

| ID | Project | Live boundary at refresh | Task |
|---|---|---|---|
| FUT-000001 | AADI | Completed | Validate every ERP requirement clause before comparison |
| FUT-000002 | AADI | Draft review | Bound ERP version and requirement parsing |
| FUT-000004 | AADI | Completed | Expose mapping-specific diagnostic reasons |
| FUT-000005 | AADI | Completed | Fingerprint validated aggregate snapshots |
| FUT-000006 | AADI | Draft review | Validate the snapshot evaluation clock explicitly |
| FUT-000007 | GatewayAI | Completed | Validate the allowed route catalogue before selection |
| FUT-000008 | GatewayAI | Linked intake; exact writable paths overlap held work | Require explicit boolean routing trust flags |
| FUT-000010 | GatewayAI | Linked intake awaiting scope admission | Reject non-object policy metadata consistently |

Do not reuse or renumber FUT IDs. A new proposal must cite exact existing repository paths, fit a registered source and test scope, pass independent admission, and have no blocked path claim or unmet dependency. A ready proposal is not an implemented change. The worker may draft a PR only after its isolated tests and review pass; merge and deployment remain separate decisions. The supervisor's audit ledger and GitHub PRs, rather than this index, carry current execution status.
