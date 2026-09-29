# Phase 2 policy operations

## Authority and scope

`gateway/callbacks.py` runs inside the pinned LiteLLM service. Before inference,
`gateway/policy.py` checks the caller's declared data class, administrator key
metadata, route, provider restrictions, text limits, budget and concurrency.
This is declarative classification, **not content inspection or DLP**. Unlabelled
WebUI input is public. Do not paste private material into public cloud chats.

Only text chat completions are supported. Tools, images, audio, client routing
overrides, additional completions, pricing overrides and unreviewed models are
rejected. The existing WebUI key remains limited to model discovery and chat.
Administrator access remains privileged and can change configuration.
WebUI defaults `function_calling` to `legacy` to avoid its native-mode automatic
builtin-tool injection. No tool is configured or approved; the gateway still
rejects nonempty tool definitions. Selecting native tools produces a policy denial.

| Intent alias | Primary | Single fallback |
|---|---|---|
| coding-fast, documentation | Gemini | OpenAI |
| coding-standard, coding-hard, architecture, review | OpenAI | Gemini |
| openai-chat | OpenAI | None |
| gemini-chat | Gemini | None |
| local-private | Unavailable: reject | Never cloud |

All capability aliases use the two existing configured models. Names express
intent; they do not establish model quality or introduce larger models. Missing
credentials omit that provider. Mappings are in `config/policy/policy.json`;
model IDs remain in local `.env`. New IDs require a reviewed pricing entry.
Configuration changes require rendering and restarting the gateway.

## Request restrictions

An API caller can narrow policy using metadata:

```json
{"model":"coding-standard","messages":[{"role":"user","content":"Synthetic example"}],"max_completion_tokens":64,"metadata":{"data_class":"synthetic","allowed_providers":["openai"]}}
```

Supported classes are public, synthetic, private and local-private. Private has
no approved cloud destination yet and is denied. Local-private returns unavailable
without upstream execution. Neither route is enabled by a model decision.
Administrator key metadata can set the same class/provider restrictions and
`require_approval: true`; request metadata can only narrow these. Approval-required
requests are rejected for human review; there is no client-supplied approval token.
Changing a label is not evidence of consent to export private data.

There are no same-provider retries and at most one approved fallback. Each actual
deployment attempt must match the ordered admission record. Provider restriction
survives quota errors/outages. No free/aggregated or optional provider is added.

## Budget and concurrency

`GATEWAY_MONTHLY_BUDGET_USD` defaults to **0** (spending disabled). The target
machine is configured for **US$100 per UTC calendar month**: amount supplied by
the user; monthly UTC period selected and stated during implementation.

This is a **conservative admission budget, not measured provider billing**.
Before execution, an atomic SQLite transaction permanently debits the upper
bound for every permitted attempt, including a fallback that may never be used.
Text UTF-8 bytes plus 4,096 template tokens bound input; output is capped at
1,024 tokens (or a smaller caller cap). The configured ceilings are $10 per
million input tokens and $100 per million output tokens for the two reviewed
model IDs. They intentionally exceed the pinned LiteLLM price catalogue entries.
These are policy ceilings, not vendor price quotations; review them when changing
models or pricing. Unknown models fail closed.

Failed requests and unused fallbacks are not refunded because billing may be
ambiguous. Admission can therefore stop well before an invoice reaches $100.
The ceiling covers this gateway after activation, not earlier use, other clients,
provider account charges or future Jev evaluation. Requests crossing midnight
are charged to their admission month. Monthly aggregates survive restart; do not
delete/reset the `policy-data` volume to recover capacity.

Maximum four admitted requests; 60-second provider request timeout, 120-second
stream iterator deadline and 300-second crash-recovery lease. Success, failure
and completed/disconnected streams release slots. A process crash retains debits
and stops the worker's 30-second lease renewal. Live requests keep their slots;
failed renewal terminates that worker rather than silently freeing live capacity.
An orphaned slot in a live worker conservatively remains occupied until restart.
After the worker stops, crashed requests occupy slots until lease expiry.
SQLite supports this single
host deployment; multi-host scaling and load capacity are not validated.

```powershell
./scripts/policy-status.ps1
python -m unittest discover -s tests -v
./scripts/test-policy-runtime.ps1
./scripts/test-providers.ps1 -RunLive -Aliases coding-standard,coding-fast
```

The runtime fault suite starts a second proxy and two synthetic provider protocols
on container loopback with synthetic credentials, an isolated ledger and no
database. It makes no real provider calls. The live probe is separately opt-in.

## Provenance and retention

The local ledger stores random admission IDs, UTC month, alias, approved
provider/model candidates, attempt order/reason, concurrency leases and aggregate
debits. It stores no prompt, response, API key or user identity. Response headers
include `x-gateway-request-id` and `x-gateway-decision: deterministic`.
Attempt outcome `accepted` is a deployment signal, not billing proof. `pending`
can also describe a stream without a deployment-success callback or an older
record; inspect request leases separately for concurrency. No invoice is inferred.
Post-admission provider errors are replaced with generic errors. LiteLLM message
and detailed spend logging remain disabled; normal operational logs rotate.
Do not publish raw runtime logs or database files. WebUI chat retention still
applies. Ledger retention is currently manual; no automatic deletion is installed.

## Jev evaluation boundary

No TypeSafe key is available. `.env` has a blank `TYPESAFE_API_KEY` field, omitted
from runtime containers. There is **no live Jev call or runtime enable switch**.
`gateway/jev.py` validates the documented Choice response and enforces the allowed
route set, finite probability/confidence values, domain checks and deterministic
fallback. Synthetic tests exercise malformed/unavailable decisions, low confidence
and authority violations. They are contract tests, not Jev accuracy/calibration.

Before enabling Jev: obtain a key locally, agree an evaluation spend allocation,
collect labelled synthetic task/risk/route cases, run the vendor endpoint in shadow
evaluation, record model version/accuracy/coverage and calibration, then review
domain-specific thresholds. The test threshold 0.9 is provisional. TypeSafe's
confidence statistic is not itself an accuracy probability. No private input may
be sent for this evaluation.

References checked during implementation:
[LiteLLM hooks](https://docs.litellm.ai/docs/proxy/call_hooks),
[TypeSafe API](https://docs.typesafe.ai/api),
[TypeSafe confidence](https://docs.typesafe.ai/confidence).
