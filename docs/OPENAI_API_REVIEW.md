# Bounded OpenAI API review

`ongoing_api_review.py` is an optional Linux operator adapter for reviewing public
repository candidates and saved test evidence through the existing LiteLLM
gateway. It does not execute tests, code, merge, deploy, or read arbitrary files.
The Windows worker must submit already-admitted public/synthetic text and its
candidate digest over the existing protected operator connection.

The OpenAI API allowance is separate from ChatGPT/Codex subscription limits.
Account enrollment, eligible models, daily allowance and other account usage
must be verified by the operator. A successful API response and local token
counter do not prove zero billing. All receipts therefore explicitly retain
`free_usage_verified: false`. The existing monthly gateway budget still applies.

## Admission and configuration

Keep the root-owned `0600` adapter configuration outside Git and synced folders.
Its `gateway_config` points to another root-owned `0600` JSON file containing
`gateway_url`, `gateway_key` and `policy_file`, using the existing local gateway
format. Only loopback HTTP is admitted. Never copy the upstream OpenAI key into
the worker or this adapter. Use a dedicated gateway virtual key restricted to
`review`, `/v1/chat/completions`, public data and the OpenAI provider.

```json
{
  "enabled": false,
  "gateway_config": "/etc/gatewayai-worker/api-review-gateway.json",
  "expected_model": "openai/gpt-5.4-mini",
  "daily_token_cap": 0,
  "max_output_tokens": 1024,
  "ledger_path": "/var/lib/gatewayai-controller/api-review/reservations.sqlite3"
}
```

Zero budget or disabled configuration makes no inference call. An enabled
configuration requires an explicit positive daily cap, at most 2.5 million
reserved tokens. This cap is a conservative adapter budget, not a discovery of
the account's free allowance. The configured model must match the current
OpenAI provider entry in the gateway's reviewed `review` policy. Do not silently
upgrade a model, change sharing settings, or enable another provider.

Input JSON has exactly `request_id`, `prompt`, `data_class` (public/synthetic)
and `candidate_sha256`. Prompt text is bounded to 24 KB. Output is capped at
1024 tokens; the response must be complete JSON with pass/repair, findings,
confidence and confidence reason. Tool calls, refusals, model drift and missing
or inconsistent usage cannot produce acceptance. LiteLLM may return the alias
`review` in its response. The receipt then identifies the configured OpenAI model
with `model_basis: gateway_policy` and preserves `returned_model: review`; it does
not fabricate an observed provider snapshot model. The policy is checked before
and after the call.

## Daily accounting and recovery

Before network I/O, a SQLite transaction reserves UTF-8 message bytes plus
4096 template-overhead tokens plus the maximum output. Concurrent requests
cannot exceed the configured UTC-day budget. Reservations are not refunded,
even for HTTP failures or malformed results. Reported input/output usage is
recorded separately; it does not replace the conservative reservation.

Request IDs are unique across days. A completed exact replay returns the saved
receipt without another network call. Changed request content is rejected.
An interrupted or ambiguous attempt cannot be replayed automatically. Received
raw output is saved in the protected ledger before schema validation so an
operator can reconcile failures without spending on another inference. There
is no retry or other-provider fallback; request metadata narrows providers to
OpenAI and the gateway disables upstream retries.

This adapter is implemented and tested independently. Enabling it in the ongoing
worker requires separate deployment/configuration and evidence that its selected
model belongs to the owner's intended allowance. Code review remains distinct
from running the isolated acceptance suite and from GitHub integration review.
An explicit operator `--reconcile` invocation can validate a retained response
offline against the exact request fingerprint. It never performs network inference.

References: [OpenAI API limits](https://developers.openai.com/api/docs/guides/rate-limits)
and [Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).
