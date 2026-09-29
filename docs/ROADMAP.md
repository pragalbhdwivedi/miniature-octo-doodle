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

## Phase 2 - Gateway intelligence and decision plane
- deterministic policy layer
- model aliases
- TypeSafe Jev synthetic evaluation
- routing
- fallbacks
- budgets
- request/provenance logging policy
- local-private route with no cloud fallback
- provider outage and Jev-outage tests
- prove fallback cannot broaden data exposure

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
- Ollama / llama.cpp
- GPU validation
- one small coding model only

## Phase 6 - Optional provider aggregation
- Claude
- OmniRoute
- provider policy controls

## Phase 7 - Agent context
- OpenViking
- Graphify

## Phase 8 - Coding agent and skills
- isolated workspaces
- approval gates
- cost / iteration limits
- third-party skill provenance/security scanning
- selected reusable engineering skills

## Phase 9 - Agent Controller
- architect
- planner
- implementer
- tester
- reviewer
- security reviewer
- documentation agent
- deterministic policy + Jev + LiteLLM orchestration
