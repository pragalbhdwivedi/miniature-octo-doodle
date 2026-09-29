# AI Gateway

LiteLLM is the mandatory central provider/model gateway.

## Client rule
Applications should use a single OpenAI-compatible endpoint exposed by LiteLLM instead of embedding separate provider SDKs wherever practical.

## Decision path

The control path is (Jev remains disabled pending live evaluation):

```text
request
  -> deterministic policy
  -> optional Jev structured decision
  -> LiteLLM
  -> approved provider/model
```

### Deterministic policy is authoritative
Before any probabilistic decision:
- classify the request/data
- enforce local-only/private/public rules
- check tool permissions
- enforce spend/concurrency ceilings
- require human approval where configured
- deny routes/providers that are not allowed

Jev or a generative model cannot override a hard deny or create authority.

### Jev decision layer
TypeSafe Jev is the selected Phase 2 evaluation target for narrow typed decisions such as:
- task class
- complexity
- risk/urgency
- provider/model class
- local vs approved cloud route
- escalation / human-review recommendation

Its result is orchestration input, not permission. On outage, malformed output, out-of-scope input, or low confidence/calibration, fall back to deterministic routing or human review.

## Capability aliases
Examples:
- coding-fast
- coding-standard
- coding-hard
- architecture
- review
- documentation
- local-private

Provider/model mappings remain configurable.

The six cloud capability aliases and two legacy provider aliases are implemented
in Phase 2. `local-private` fails closed and is not advertised. See
[tested policy operations](PHASE2_POLICY.md) for mappings and limitations.

## Routing principle
Aliases express intent. Provider-specific model identifiers are implementation details and must be verified at deployment time.

Fallback must stay inside the same or a stricter trust/data class.

## Privacy
`local-private` must only route to a local provider and must not fall back to cloud APIs.

OmniRoute remains optional and experimental. Free or aggregated providers must not receive private workloads merely because another route is unavailable or cheaper.

## Phase 2 acceptance targets
Before marking routing COMPLETE:
- deterministic deny rules win over Jev/model output
- Jev accuracy/calibration tested on labelled synthetic cases
- low-confidence and Jev-outage behavior tested
- provider outage/quota behavior tested
- local-private cannot escape to cloud under any failure mode
- fallback cannot broaden provider/data exposure
- route/model/provider provenance is recorded without leaking secrets
- budgets and concurrency controls are tested
