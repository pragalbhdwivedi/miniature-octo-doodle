# Roadmap

## Phase 0 - Repository and architecture
- source-of-truth documentation
- component registry
- security/storage rules

## Phase 1 - Core Docker platform
- preflight
- PostgreSQL
- LiteLLM
- Open WebUI
- OpenAI
- Gemini

## Phase 2 - Gateway intelligence
- model aliases
- routing
- fallbacks
- budgets
- request logging policy
- local-private route

## Phase 3 - Recovery
- backup
- restore
- clean rebuild test
- disk reporting

## Phase 4 - Kubernetes
- k3d
- base manifests
- Ingress
- same core services
- no duplicate large model storage

## Phase 5 - Optional local AI
- Ollama
- GPU validation
- one small coding model only

## Phase 6 - Optional provider aggregation
- Claude
- OmniRoute
- provider policy controls

## Phase 7 - Agent context
- OpenViking
- Graphify

## Phase 8 - Coding agent
- isolated workspaces
- approval gates
- cost / iteration limits

## Phase 9 - Agent Controller
- architect
- planner
- implementer
- tester
- reviewer
- security reviewer
- documentation agent
