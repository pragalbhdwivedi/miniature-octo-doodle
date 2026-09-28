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
- call LiteLLM for model access
- work in isolated repositories/workspaces

## Safety
It must not receive unrestricted production credentials or arbitrary host-level access.
