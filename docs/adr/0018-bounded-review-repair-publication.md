# ADR 0018: Separate review and repair from publication authority

Date: 30 September 2026. Status: implemented; live acceptance in BUILD_STATUS.

The user requested independent review, bounded repair and publication orchestration.
Extend the operator-controlled PostgreSQL workflow without installing an autonomous
agent daemon. Keep the unprivileged planner, inference adviser, sandbox and publisher
as distinct authorities.

A fresh review context and independently supplied sandbox tests assess the exact
candidate. An approving model cannot override failed tests or publish. At most one
repair can propose file changes in the original scope; tests and a new independent
review must pass again. The operator then approves the exact final artifact/review
receipt before a journaled draft PR creation. Source/ownership are refreshed before
the pipeline and publication; the publisher checks the source once more.

Store a one-shot pipeline and immutable stage debits in PostgreSQL. The aggregate
$1 ceiling includes the original coding debit and up to three advisory calls, each
covering the allowed provider fallback. No refunds, replay, implicit budget increase
or automatic ambiguous-result recovery. Existing monthly authority remains intact.

Advisory context is intentionally compact: exact task/candidate, PROJECT/AGENTS,
selected files and test result, with complete governance refreshed by the controller.
It never silently truncates historical instructions to fit the provider. Same-model
review is possible behind aliases; independence is role/context, not model diversity.
Hard path/test/budget/publication rules never depend solely on reviewer confidence.

Retain old audit records and take a private DB backup before the additive schema-2
migration. No database network changes, packages/images, new credentials or broader
host access are needed. Telegram approvals, AADI activation and clean-host recovery
remain separate gates. See [operations](../CONTROLLER_REVIEW.md).
