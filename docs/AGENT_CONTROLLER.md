# Agent Controller

The Agent Controller is a future orchestration layer, not part of the initial install.

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
- use Graphify for code relationships
- use OpenViking for persistent context
- enforce deterministic policy before model/tool selection
- use TypeSafe Jev for validated structured routing/risk/classification decisions
- call LiteLLM for approved model access
- work in isolated repositories/workspaces

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
