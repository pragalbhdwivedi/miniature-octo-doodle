# Telegram approval gate (Phase 8 increment)

Status: implemented for a single exact draft-publication decision. On 2026-10-01,
the owner-provided bot token and a private `/start` update established the approved
user/chat identity. VM9125 has a protected root-only bot configuration, and a
VM-originated test message received Telegram API acknowledgment and the owner
confirmed phone receipt. A real private callback was accepted into PostgreSQL on
1 October, and production dispatch now requires Telegram approval for draft
publication. The first decision expired before publication. A fresh reviewed run
then received the owner's private callback; its exact decision was consumed by
the operator publication step and created draft PR #32. This validates only the
bounded draft-publication action. General notifications and choose/pause/resume
controls remain pending. See BUILD_STATUS for the evidence.

## Authority and action

Only the Linux operator can request or poll approvals. The bot never receives a
Docker socket, PostgreSQL credential, publisher token, gateway key or shell tool.
A Telegram callback records **approve** or **reject** for one `publish_draft`
action. It cannot publish by itself, merge, deploy, raise a budget, or resume an
uncertain worker/model/publisher operation. The operator must invoke the publisher
after rechecking the source, final artifact and task ownership.

The approval binds the exact run ID and SHA-256 of its publication receipt. Its
buttons carry a keyed MAC, fit Telegram's 64-byte callback limit, and are accepted
only from the configured numeric user in the configured private chat. PostgreSQL
enforces a 15-minute expiry, one request per run/action, terminal rejection,
one-shot decision, and atomic consumption with the transition to `publishing`.
No decision is inferred from a missing response. Database events retain the
approval ID, payload hash and Telegram update ID without storing the bot token.

The operator can manually poll once. A protected offset records handled updates.
Foreign/malformed callbacks are skipped. An ambiguous database or Telegram
operation stops the CLI; inspect the database and bot chat before a manual repeat.
A delivery failure may leave a pending but unseen request. It cannot be replaced
with a new request for the same run. This bounded implementation has no daemon,
automatic retry, general choose/pause/resume controls or notification fanout.

The operator must leave enough of the 15-minute window for the separate publish
step. A stored `approved` decision does not override expiry: PostgreSQL checks the
clock again when consuming it. On 1 October, a real private callback passed the
user/chat/MAC checks and was stored, but Telegram callback acknowledgment failed
after the database commit. The protected polling offset had not advanced. After
checking the stored update ID and exact approval, one manual poll skipped the
already-decided callback and advanced the offset. Publication later hit expiry;
the run stayed `approved`, the decision stayed unconsumed, and no GitHub branch or
publication journal existed. The reason Telegram refused callback acknowledgment
was not established. Never replay that expired decision or infer publication from
the phone button alone.

## Provisioning and activation

After the owner creates a bot, keep this JSON in a root-owned `0600` file outside
Git and synchronized storage, for example `/etc/gatewayai-controller/telegram.json`:

```json
{"bot_token":"<BotFather token>","user_id":123456789,"chat_id":123456789,
 "signing_key_hex":"<32 random bytes as 64 lowercase hex characters>"}
```

The numeric user and chat IDs must be the actual approved **private** chat. Do not
copy the example values. Generate the signing key locally and never print it in
logs or PRs. The transport uses only Telegram's HTTPS Bot API, disables proxy
environment inheritance and redirects, and sanitizes transport errors because
the token appears in the request URL. Review the protected file's ownership and
mode before adding `"telegram_approval_config":
"/etc/gatewayai-controller/telegram.json"` to the root-only operator dispatch
configuration. That field makes Telegram approval mandatory for controller draft
publication; removing it is an operator policy change. No service restart is
required because these are operator CLIs.

Apply schema 3 only after a protected controller database backup. Test a copy
first. The migration refuses versions other than 2 and preserves prior history:

```sh
sudo python3 scripts/controller-migrate-approvals.py \
  --container SELECTED_POSTGRES --admin-role ADMIN --database gatewayai_controller
```

For an approved pipeline, inspect its final patch and publication digest first:

```sh
sudo python3 scripts/controller_telegram.py request \
  --config /etc/gatewayai-controller/dispatch.json --run-id RUN_ID
sudo python3 scripts/controller_telegram.py poll \
  --config /etc/gatewayai-controller/dispatch.json
sudo python3 scripts/controller_telegram.py status \
  --config /etc/gatewayai-controller/dispatch.json --approval-id APPROVAL_ID
```

After the exact approval has been recorded, the separate operator resumes only
that stored publication action:

```sh
sudo python3 scripts/controller_pipeline.py publish \
  --config /etc/gatewayai-controller/dispatch.json --run-id RUN_ID \
  --approve-sha256 FINAL_PUBLICATION_DIGEST --telegram-approval-id APPROVAL_ID \
  --publisher-config /etc/gatewayai-worker/publisher.json
```

The approved decision is consumed in the same database transaction that enters
`publishing`, before GitHub publication. If GitHub or completion recording is
ambiguous, the run remains blocked for manual reconciliation; the decision cannot
be replayed. The final external action still uses the scoped journaled publisher.

## Acceptance boundary

Synthetic callback tests cover signed/tampered buttons, wrong identity/chat,
rejection, replay and offset handling. Schema-3 tests use a dedicated PostgreSQL
test database for expiry bounds, exact payload/identity checks, duplicate denial
and atomic consume/transition. These tests do not prove bot delivery, actual
Telegram identity, phone notification or end-to-end pause/resume. Those require
the owner's protected bot configuration and a controlled live run.

The AADI adapter stays disabled. AADI's current `Dev` branch is private and its
roadmap integration PR #23 remains open; the existing public-only worker and
gateway public/synthetic-text policy cannot ingest AADI source. Private source
access, task authority and permitted model data path need a separate reviewed
adapter and AADI task before that acceptance can proceed.
