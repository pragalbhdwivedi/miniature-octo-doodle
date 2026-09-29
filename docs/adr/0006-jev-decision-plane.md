# ADR 0006: Separate policy, Jev decisions, and model execution

## Status
Accepted design direction. The deterministic runtime is implemented and validated.
Jev is explicitly disabled by user decision; [ADR 0008](0008-phase2-acceptance-jev-disabled.md)
defers live evaluation/calibration and activation beyond Phase 2 acceptance.

## Context
The platform needs to choose among local and cloud models without allowing cost, availability, or an AI-generated routing decision to weaken privacy, provider allowlists, tool permissions, or human approval.

Many routing and classification decisions are narrow and structured rather than generative. TypeSafe Jev is therefore selected as the first decision-model candidate to evaluate for these cases.

## Decision
Use three explicit layers:

1. **Deterministic policy and authority**
   - data/trust classification
   - provider/tool allowlists
   - local-only requirements
   - spend/concurrency limits
   - mandatory human approval
   - hard deny rules

2. **TypeSafe Jev decision intelligence**
   - typed choice / score / probability outputs
   - task class, complexity, risk, urgency, route class, escalation
   - only among options already permitted by policy
   - never grants authority

3. **LiteLLM model/provider execution**
   - common OpenAI-compatible gateway
   - executes the approved route
   - provider/model IDs remain configuration, not authority

## Failure behavior
If Jev is unavailable, malformed, outside the evaluated domain, or below the configured confidence/calibration threshold, use a deterministic fallback, a fixed compliant route, or human review.

Fallback may stay within the same or a stricter trust/data class. It may not broaden exposure.

`local-private` has no cloud fallback.

OmniRoute remains optional and experimental. Free/aggregated providers are not trusted fallbacks for private workloads merely because they are available.

## Validation before completion
Phase 2 must test:
- deterministic deny precedence
- labelled routing/classification cases
- calibration and low-confidence thresholds
- Jev outage/malformed response
- provider outage/quota exhaustion
- local-private isolation
- no fallback data-class broadening
- route/model/provider provenance without secret leakage
- budget and concurrency controls

## Consequences
The design adds a decision component but prevents the router from becoming an authority system. Provider/model choices can evolve without embedding security policy in prompts.

## Related
- Issue #3
- `docs/AI_GATEWAY.md`
- `docs/SECURITY.md`
- `docs/MODELS_AND_SKILLS.md`
