# OpenViking

OpenViking is an optional persistent context store. Git/GitHub remains the
source of truth for code and task state; memory content is advisory and cannot
authorize dispatch, spending or publication.

## Intended responsibility
- project context
- resources
- prior agent work
- decisions and durable memories
- reusable skills/context

## Non-responsibility
It is not the source of truth for source code. Git/GitHub remains canonical.

## VM9125 deployment, 1 October 2026

The isolated `gatewayai-openviking` Compose project runs pinned OpenViking
v0.4.22 and a pinned CPU Ollama container. The Ollama container holds only the
274 MB `nomic-embed-text` embedding model; it has no published port and is on
an internal Docker network. OpenViking connects to that network and the existing
gateway provider-egress network to use the laptop's `qwen3:4b-thinking` through
the existing loopback bridge. It is bound **only to VM 127.0.0.1:1933**. No
Nginx Proxy Manager or LAN/phone route was added. The config disables intent
planning, sets one concurrent embedding/VLM request, and uses local AGFS and
vector storage. The VLM is text-only, so image/multimodal memory is not accepted.

Source and setup templates are in `deploy/openviking/` and
`scripts/openviking_*.py`. The live Compose file is
`/opt/gatewayai-openviking/compose.yaml`; root-only config, credential receipts,
Ollama model and persistent workspace are under `/var/lib/gatewayai-openviking`.
The root API key is an administrative bootstrap key. A separate
`gatewayai/operator` account and user key are used for resource calls; the
root key is denied data access by the server. The VM files are mode 0600 in a
mode 0700 directory. A protected, local copy of both credentials is at
`%USERPROFILE%\creds\gatewayai-openviking-login.json`, outside Git/OneDrive.
The service uses API keys rather than an email/password login. Connect with an
SSH loopback tunnel if operator access is needed:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:1933:127.0.0.1:1933 gatewayai-direct
```

The initial health endpoint returned v0.4.22 with API-key auth and Docker
reported the OpenViking container healthy. `openviking-server doctor` passed
config, native engine, AGFS, auth, embedding (768 dimensions), VLM configuration,
Ollama connectivity and disk checks; VikingBot was intentionally absent. A
public main-SHA document was ingested with `vectors_only`; task completion,
authenticated search (one result), anonymous denial (401), root-key data denial
(403), and operator-key read (200) all passed. The same public document's
`semantic_and_vectors` task completed after the first five-minute observation
window; authenticated search returned two results, with the same access checks.
After restarting only the two OpenViking Compose services, health and the same
authenticated semantic search passed again. This proves same-VM container
restart persistence for the tested public item, not off-machine recovery.
This is a bounded public-data
acceptance, not private-data permission, compaction quality, backup/restore or
controller integration evidence. The acceptance receipt is root-only on the VM.

## Automatic public context workflow, 1 October 2026

The VM operator runs `scripts/openviking_public.py` against the protected
`gatewayai/operator` account. The enabled
`gatewayai-openviking-sync.timer` starts its oneshot service about every 15
minutes. It imports only `PROJECT.md`, `docs/ROADMAP.md` and this document from
the exact current public GitHub main SHA, using `vectors_only`. A root-only
manifest records task IDs so a slow task resumes without a duplicate import.
Retrieval is disabled until all three tasks complete and remote main still
matches the manifest. A changed main starts a new bounded import; the old
revision is never returned by the adapter. This timer does not capture chats,
secrets, private repositories, or worker artifacts. It does not prune older
public revisions yet; monitor workspace growth before expanding the scope.

The operator-only controller review path accepts `openviking_root` in its
protected dispatch configuration. For an exact-main GatewayAI plan, it queries
the completed public resource prefix, reads at most three matched excerpts of
600 characters, and labels them untrusted advisory data in the independent
review and repair prompt. The Git candidate, task plan, deterministic policy,
budget and human publication gates remain authoritative. If OpenViking is
unavailable, still importing, stale, out of scope or too large for the prompt,
the review proceeds from Git alone. A digest of the optional advisory is
recorded with review evidence. No model call is made by the sync timer.

On VM9125 the timer was enabled and its first service run returned success.
All three public-main tasks completed at SHA
`843aa15c4011f0f00e29ff0c316306f84d7116bd`. A live `find` returned three
in-scope excerpts, and a controller adapter smoke test returned three hits and
denied a mismatched SHA. Unit tests cover incomplete/stale tasks, failed tasks,
out-of-scope results, controller prompt inclusion and Git-only fallback. An
actual paid reviewer run or WebUI chat capture was included in that first
activation. The subsequent bounded acceptances are recorded below.

The live script is `/opt/gatewayai-openviking/public.py`; the systemd units
are copied from `deploy/openviking/`. Protected state stays in
`/var/lib/gatewayai-openviking`. Stop the timer with
`sudo systemctl disable --now gatewayai-openviking-sync.timer` if rollback is
needed. Controller source and config rollback copies are in the root-only
`/var/lib/gatewayai-openviking/controller-rollback-20261001` directory.

Never copy the workspace or credentials into Git or OneDrive. The encrypted
backup and clean-guest restore acceptance are recorded below. Keep sensitive
institutional content out until derived-memory retention/deletion behavior has
been tested. A laptop outage
removes the VLM route; treat semantic processing as unavailable then.

## Private WebUI capture and bounded review acceptance, 1 October 2026

The owner selected automatic capture for all chats belonging to the existing
Open WebUI administrator account. A dedicated OpenViking account
`gatewayai-webui-admin` holds its own user key in the root-only VM file
`/var/lib/gatewayai-openviking/webui-private.json`. This key is separate from
the public `gatewayai/operator` key. No key or chat content is in Git.

`scripts/openviking_webui_private.py` reads the existing WebUI SQLite volume
**read-only** and mirrors the active text branch of every saved chat owned by
that exact WebUI user into one OpenViking session per chat. It ignores other
WebUI accounts and incomplete trailing user turns. A content digest makes
repeat runs a no-op. Edits replace the mirrored session; deletion of a WebUI
chat deletes its OpenViking session on the next successful sync. Oversized,
non-text or malformed chats stop the sync visibly rather than silently dropping
content. The VM-local systemd timer runs every two minutes; a root-only manifest
tracks mirrored session IDs. This is **raw session capture**: auto-commit and
long-term extraction are intentionally disabled because deletion of derived
memories has not been proven. It does not inject private chats into cloud
prompts or the coding reviewer. Archived WebUI branches, attachments and
temporary unsaved chats are outside this tested text scope.

The first live run mirrored five existing admin chats (60 messages). A second
run reported no changes. All five sessions reported zero commits and zero
extracted memories. A real mirror's read statuses were owner 200, public operator 404,
root data key 403 and anonymous 401. A separate synthetic account test passed
owner scoping, repeat no-op, changed-chat replacement and deleted-session 404.
The private timer and oneshot service reported active/success. These tests
establish account isolation for session reads and deletion of raw sessions;
they do not establish isolation of extracted memories or private search.

`scripts/openviking_review_acceptance.py` made one real, bounded LiteLLM
reviewer request with three public exact-main OpenViking excerpts. A root-only
reservation preceded HTTP; the conservative debit was $0.453800 under a $1
one-shot limit. At source SHA `3e8672b8412d2084fbd145bf6f42cb842ad90ffd`,
the synthetic correct candidate received `approve` with zero findings and
3,662 total tokens. Receipt and advisory digest are root-only under
`/var/lib/gatewayai-openviking/review-acceptance-20261001`. This validated the
retrieved-context reviewer call, not the full worker or PR publication path.

## Recovery boundary

An encrypted, consistent 243 MiB archive of the OpenViking workspace, keys,
configuration, public index, private sessions and embedding model is
stored outside Git and OneDrive at
`%USERPROFILE%\creds\gatewayai-openviking-20261001.tar.gz.gpg`. Its recovery
passphrase is in the separate protected file
`%USERPROFILE%\creds\gatewayai-openviking-recovery-20261001.pass`.
The test target is clean Ubuntu VM9127, documented in the Git-excluded
`VM_NOTES/9127-gatewayai-memory-restore.md`. The recovery Compose file has no
provider-egress network, no published port and no restart policy. GPG archive
authentication and tar listing passed before extraction. The restored v0.4.22
service returned three authenticated public search hits from the archived
exact-main index and retained all five private chat sessions. A private session
returned owner 200, public operator 404, root 403 and anonymous 401. The local
embedding model was present. The test containers were stopped afterward.
The source and target VMs share the same NAS backend, so this test does not
prove recovery after NAS/site loss. Full-core Phase 5 recovery/cutover remains
separate. See BUILD_STATUS for the measured acceptance.
