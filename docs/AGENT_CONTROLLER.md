# Agent Controller

The Agent Controller is planned for Phase 7, after the Debian foundation and
isolated worker. No controller runtime is implemented or deployed yet. Follow
the [roadmap](ROADMAP.md) and [AADI integration contract](AADI_DEVELOPMENT_INTEGRATION.md).

## Intended roles
- Architect
- Planner
- Implementer
- Tester
- Reviewer
- Security reviewer
- Documentation agent

## Integration
The controller will:
- read source from Git/GitHub
- work correctly from refreshed Git alone before adding Graphify/OpenViking
- optionally use Graphify for code relationships and OpenViking for context in Phase 9
- enforce deterministic policy before model/tool selection
- keep Jev disabled until separately approved live evaluation in Phase 11
- call LiteLLM for approved model access
- work in isolated repositories/workspaces
- record runs and exact action-bound approvals, with Telegram as the sole human
  control channel (Phase 8); WhatsApp is excluded
- create reviewable branches and draft PRs; human approval is required for merge
  and production deployment

AADI is the first managed development project. Its repository remains authoritative
for its own requirements, branch rules and production architecture. This controller
does not become an AADI production runtime dependency.

## Decision boundary
The controller must treat three things separately:

1. **authority/policy**: deterministic rules, permissions, data classes, approval requirements
2. **decision intelligence**: Jev choice/score/probability where evaluated
3. **generative execution**: local/cloud models accessed through LiteLLM

A model or Jev result cannot self-authorize production access, dangerous tools, private-data egress, or a broader provider fallback.

## Skills
Third-party skills/plugins are untrusted code/instructions until reviewed. The planned skills workflow should include provenance, licence review, least privilege, and security scanning (for example NVIDIA SkillSpector where technically appropriate) before activation.

## Safety
It must not receive unrestricted production credentials, Docker host socket access, or arbitrary host-level access.
