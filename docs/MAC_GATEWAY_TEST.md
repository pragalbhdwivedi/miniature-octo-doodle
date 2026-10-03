# Mac-backed GatewayAI coding test

The owner authorized a larger model on the 16 GiB Apple Silicon Mac on
3 October 2026. This is a separate synthetic test alias, not a replacement for
the existing Windows local-coding/supervisor routes or the Mac's accepted 4B setup.

## Model and execution boundary

Use `qwen3.5:9b` (currently 6.6 GB, Q4_K_M), then create the separate
`mac-coder-9b:latest` variant with 16,384 context. The native 4B acceptance used
a 64K allocation but only 2.3-3.4K actual prompt tokens. This new gateway smoke
test needs a short chat prompt and no agent tool schema. The 16K setting is for
this bounded test, not a recommendation to shrink the documented Codex harness
requirement. Larger model weights plus context must fit RAM; disk capacity
alone does not establish suitability. Retain the 4B model. Download only on
the Mac, not Windows, the control-plane VM, or a Codex Cloud runner.

Require 25 GiB free before the authorized download and retain the 15 GiB floor.
The bootstrap verifies Apple Silicon, >=16 GiB RAM, a local model store,
loopback Ollama, persistent cloud disable and effective server environment.
It creates only a dedicated model variant and private task state under
`~/Library/Application Support/GatewayAI/mac-test`. The key has no passphrase
for the narrowly restricted unattended tunnel; its file must stay 0600 and must
never leave the Mac. No admin SSH key, gateway API key or private key is bundled.

## Transport

```text
fixed synthetic test -> authenticated LiteLLM mac-coding-test route
  -> dedicated Docker-bridge proxy :11436
  -> gateway loopback :11436 -> SSH reverse tunnel -> Mac loopback Ollama :11434
```

OpenVPN is the required primary connection, per the owner's correction on
3 October. Its assigned Mac address may change after every connection. Set
`vpn_type` to `OpenVPN` and `vpn_address` to `auto` in the connection record.
The Mac resolves the gateway route's `utun`/`tun` interface and requires exactly
one private IPv4 address on it, then binds SSH to that address. Each new link
repeats discovery; no fixed client IP enrollment is needed. Activate the intended
OpenVPN client first. The route/interface check does not identify VPN software
or independently audit its handshake. No direct-LAN/public fallback is used.
Existing WireGuard connection records remain compatible when explicitly wanted.

The enrolled SSH public key is not restricted to a single source address. Existing
network firewall/routing policy remains unchanged; the account still has only the
fixed test command and loopback reverse-forward permission. VPN subnet access
must be validated from the Mac before claiming connectivity.

The Mac initiates the SSH tunnel inside OpenVPN. It needs no inbound Mac
SSH or exposed Ollama port. Port 11435 belongs to the existing Windows model
tunnel and must remain unchanged. Use a distinct `gatewayai-mac-test` account:
public-key-only authentication; no PTY, agent forwarding, X11 or local forwarding;
remote forwarding restricted to `127.0.0.1:11436`; force the root-owned
`mac_gateway_dispatch.py`. The only executable client command is
`mac-gateway-test`; it cannot choose shell commands, paths, prompts or models.
The account has no sudo or Docker group membership.

The deployment operator obtains the gateway ED25519 host public key through an
existing trusted connection and supplies a local `connection.json` with
`host`, `port` (22), `user` (`gatewayai-mac-test`), `host_key`, `vpn_address` (`auto`),
and `vpn_type` (`OpenVPN`) fields. Keep
host-specific connection records and generated public-key handoff outside Git.
The Mac script uses strict host pinning, no agent forwarding and one task key.
It never runs ssh-keyscan as a substitute for identity verification.

## Mac agent instructions

1. Use actual Mac terminal tools. A cloud checkout cannot download a model onto
   the Mac or reach its loopback. If attached only to a cloud runner, report that
   once and move the task to the Mac's local-folder session.
2. Fetch the reviewed `scripts/mac_gateway_setup.py` and the private connection
   record, then run `python3 mac_gateway_setup.py prepare`. Downloads are already
   authorized within the disk/RAM limits. This prints only an SSH **public** key
   for enrollment and preserves the existing accepted launcher/profile.
3. Return that public key to the gateway operator. Until it is enrolled, do not
   claim the Mac is linked. Private key transfer, passwords and broader login
   rights are unnecessary.
4. After enrollment, run `python3 mac_gateway_setup.py link` in a managed terminal
   that remains running. This is a foreground tunnel, not reboot persistence.
5. The gateway operator verifies the native model name/digest through the tunnel,
   stages and activates the dedicated alias/key, then authorizes the fixed test.
6. In another Mac terminal run `python3 mac_gateway_setup.py test`. Observe
   Activity Monitor and `ollama ps`; record allocated context, GPU percentage,
   memory pressure, swap change and timings. If memory pressure becomes red,
   stop the inference and record the 9B runtime as unsuitable at this allocation.

## Gateway operator activation

Do not activate before enrollment/tunnel health. `mac_gateway_routes.render`
accepts the observed private Docker bridge on port 11436 and stages an additive
`mac-coding-test` route. Preserve every existing alias, policy, budget and data
volume. The sole candidate is `ollama/mac-coder-9b:latest`, with zero vendor-cost
debit, `reasoning_effort: none` and `num_ctx: 16384`. The installed LiteLLM 1.103.0
Ollama mapping was inspected and maps the non-GPT reasoning value `none` to
`think: false`. This is not yet a live 9B integration result.

Use the existing unprivileged systemd socket-proxy pattern with new Mac-specific
units, binding only the observed Docker provider bridge on port 11436 and
forwarding to gateway loopback 11436. Inspect the current bridge membership;
do not assume LiteLLM is its sole member (OpenViking was also present on inspection).
Keep public/synthetic admission only and existing tool/private-source denials.
For broader/private use, a dedicated service boundary requires separate work.

After root-only backups and source-hash comparison, activate only the added
config/policy entries during a controlled LiteLLM recreation and refresh its
loopback proxy. Never restore an old budget ledger. Create an inference key
restricted to this alias and chat-completion routes, with administrator metadata
`data_class=synthetic` and `allowed_providers=[ollama]`. Store it only in
`/etc/gatewayai-mac-test/inference.key`, root-owned, group-readable by the test
account (0640); it is never sent to the Mac. Do not give the account a master key.

The fixed acceptance script sends a short synthetic prompt through the gateway.
It admits only four arithmetic functions via a strict AST grammar and then runs
14 independent cases. No model-authored shell commands, imports, attributes,
calls, loops, arbitrary files, or real source are executed. Its result explicitly
leaves `provider_ledger_verified=false`: the operator must correlate the returned
admission ID with the durable gateway ledger and Mac server log/model digest.

Then stop ONLY the Mac tunnel and confirm that this alias fails without any
cloud attempt or debit. Reconnect and repeat. Test key rejection for another
alias/admin endpoint and preserve existing routes. These live checks are pending
until their evidence is recorded; offline tests are not substitutes.

## Status and rollback

Activated on 3 October: dedicated SSH key, Docker-bridge proxy, additive
`mac-coding-test` route and fixed-test inference key. Mac Ollama model discovery
passed through the tunnel from the gateway host and LiteLLM container. The 9B
variant and base model were present. Existing aliases/configuration were preserved;
source hashes and an idle admission ledger were checked before a controlled
LiteLLM restart. Core services returned healthy. Administrator endpoint and
other-model requests with the test key returned HTTP403.

The first synthetic gateway request failed HTTP502 when the Mac reverse tunnel
disconnected. Its durable ledger shows exactly one Ollama attempt, no cloud attempt,
zero model prices and a released admission. This is observed failure isolation,
not a successful coding test or a complete reconnect/outage acceptance cycle.
After reconnect, the fixed test passed all 14 arithmetic cases in 9.67 seconds.
An operator independently rechecked the saved source/hash and correlated the
admission with exactly one accepted `ollama/mac-coder-9b:latest` attempt, no cloud
attempt and a released admission. The live model digest matched the discovered
9B variant. Ollama reported 5,968,840,620 loaded bytes, all allocated to GPU,
and a 16,384-token context. Core containers remained healthy.

This accepts the bounded synthetic gateway coding test and observed recovery
following the disconnect. It does not establish autonomous-agent/real-project
coding capability. Mac memory-pressure/swap measurement, a deliberately controlled
outage cycle, and reboot persistence remain unvalidated.

The Mac screenshot reported an SSH known-hosts path-quoting issue. The repository
now quotes the Application Support path as an SSH option value; the existing Mac
agent had already corrected its running copy. Nine focused regression tests pass.

Rollback the new alias/key, dedicated account authorization and Mac-specific
socket/service only after checking for active tests. Stop the Mac foreground
tunnel. Retain evidence and existing 4B setup. Delete the 9B variant/weights only
if the owner explicitly requests it. Never remove the Windows tunnel, existing
keys, live gateway ledger or later configuration changes.

References checked: [Ollama model](https://ollama.com/library/qwen3.5:9b),
[Ollama macOS configuration](https://docs.ollama.com/faq),
[LiteLLM Ollama provider](https://docs.litellm.ai/docs/providers/ollama).
