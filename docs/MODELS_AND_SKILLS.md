# Models, tools, and skills discussed

Status: **research catalogue, not an installation or approval list**.

This file preserves the AI models, runtimes, coding agents, orchestration systems, context tools, safety tools and reusable skills discussed while designing this platform. Social-media claims remain discovery leads until the exact upstream project/version is verified.

## Current validated core routes

| Item | Current evidence |
|---|---|
| OpenAI `gpt-5.4-mini` | validated on the target machine through LiteLLM as `openai-chat` in Phase 1 |
| Google `gemini-3.1-flash-lite` | validated on the target machine through LiteLLM as `gemini-chat` in Phase 1 |
| LiteLLM | validated central gateway in Phase 1 |
| Open WebUI | validated browser UI in Phase 1 |

These validated routes do not imply that the other items below are installed.

## Decision and routing components

| Item | Role discussed | Status |
|---|---|---|
| **TypeSafe Jev** | typed choice/score/probability for routing, risk, task classification and escalation | selected Phase 2 evaluation target; not installed |
| **LiteLLM** | central provider/model gateway, aliases, routing, fallbacks, budgets | core gateway; Phase 2 routing controls pending |
| **OmniRoute** | optional aggregation of multiple/free providers | experimental later component |
| **Ollama / llama.cpp** | local inference | optional later component |

## Generative, decision, image, and speech models/families discussed

- OpenAI GPT-5.6 Sol
- OpenAI GPT-5.6 Terra
- OpenAI GPT-5.6 Luna
- OpenAI GPT-5.5
- OpenAI GPT-5.2
- OpenAI GPT-5.1-mini
- OpenAI GPT-5-Nano
- Anthropic Claude family
- Google Gemini family
- PrismML Ternary Bonsai 2 27B
- Qwen3 4B
- Qwen3-Coder-Next
- Qwen 3.5 32B
- Qwen3.8-Max
- Z.ai GLM-5.3 FlashX
- GLM-5.2 / glm-5.2-colibri
- DeepSeek family
- Kimi family / Kimi K3 references
- xAI Grok Imagine Image 2.0
- Kyutai Pocket TTS
- TypeSafe Jev

Some names above came from social-media screenshots and must be verified before use. Do not hard-code them into capability aliases merely because they were discussed.

## Coding agents, orchestration, context, and safety tools discussed

- OpenAI Codex / Codex CLI
- Anthropic Claude Code
- Cursor
- Google Antigravity
- OpenViking
- Graphify
- Ponytail
- NVIDIA SkillSpector
- Matt Pocock / agent skill collections
- Auto-Company
- ECC 63-agent / 249-skill bundle reference
- Unsloth Studio
- ARTEMIS
- AWS Pizza Bot
- Meta Muse Code
- Colibri
- Hyperspace Pods
- RackPeek
- Sentry
- PostHog
- Better Stack

## Reusable engineering skills explicitly discussed

Matt Pocock-style skills shown/discussed:
- `grill-me` — interrogate requirements before build
- `to-spec` — convert requirements into a specification
- `to-tickets` — split work into reviewable tasks
- `implement` — bounded implementation workflow
- `code-review` — independent review workflow

Other skill collections/tools:
- K-Dense-AI `scientific-agent-skills`
- Hermes Skills Hub
- generic Agent Skills pack for planning/coding/testing/publishing
- Ponytail staged pre-code workflow
- NVIDIA SkillSpector as a scanner for third-party skills rather than a skill pack itself
- RTK terminal/context-noise reduction claim
- UI UX Pro Max design-skill/plugin claim

## Other open-source/application candidates discussed

- OpenMAIC
- VoiceStudio
- OpenWA
- PaddleOCR
- Scrapling
- changedetection.io
- ppt-master
- OpenSEO
- trycompai/crm
- ai-website-cloner-template
- MySigMail
- Capptivo

## Adoption filter

Before adding any item above to the working platform, record:
1. canonical upstream repository/vendor and exact version
2. licence and commercial/institutional-use terms
3. maintainer/release activity
4. data sent, retained, or used for training
5. secrets and permissions required
6. supported OS/runtime/GPU
7. representative synthetic benchmark
8. failure/offline behavior
9. data/trust-class boundary tests
10. cost/quotas and uninstall/rollback path

Third-party agent skills are untrusted code/instructions until reviewed. Star counts, follower counts, viral posts and token claims are not security evidence.
