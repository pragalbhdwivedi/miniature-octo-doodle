# ADR 0019: Persist exact Telegram decisions without bot execution authority

Date: 30 September 2026. Status: implemented for draft publication; live channel
acceptance pending.

Phase 8 adds a single Telegram human-control path. The bot only delivers a
bounded action request and records an identity-checked decision. The Linux
operator continues to own source refresh, sandbox operation, publication and
recovery. No model, bot callback or silent timeout can invoke those actions.

Schema 3 stores the final publication receipt hash, run, action, approved numeric
user/private chat, expiry and state in the dedicated controller database. Button
data is MAC-bound to that hash and random approval ID. A successful callback
changes only `pending` to `approved` or `rejected`; consuming an approved decision
and entering `publishing` are one transaction. Ambiguous side effects have no
automatic retry path. The production controller remains Telegram-disabled until
bot identity/credentials and live acceptance exist.

Only a draft PR action is supported in this increment. Later choose/pause/resume
and notification types must be added as explicit state transitions, not inferred
from free text or broad bot privileges. The existing Phase 5 recovery and Phase 7
AADI private-repository gates remain separate.
