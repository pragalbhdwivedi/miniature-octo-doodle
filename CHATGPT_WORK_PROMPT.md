# ChatGPT Work Handoff

Work directly from this repository.

1. Pull/refresh `pragalbhdwivedi/miniature-octo-doodle`.
2. Read `PROJECT.md` first.
3. Then read `PROJECT_STATE.md`, `AGENTS.md`, `WORK_INSTRUCTIONS.md`, `docs/ARCHITECTURE.md`, and `docs/BUILD_STATUS.md`.
4. Inspect current issues and begin with the earliest incomplete milestone.
5. Use GitHub as the source of truth and keep documentation synchronized with implementation.
6. Do not install optional/heavy components until the core is tested and the storage thresholds permit it.
7. Never commit secrets or machine-local runtime data.
8. Before changing architecture, inspect existing ADRs and continue the established design unless a reviewed change is necessary.
9. At the end of each milestone, commit tested changes and update BUILD_STATUS with evidence.

The initial implementation target is:

```text
Browser
  -> Open WebUI
  -> LiteLLM
      -> OpenAI
      -> Gemini
  -> PostgreSQL
```

The full documented target additionally includes the Agent Controller, OpenViking, Graphify, Git/GitHub, Claude, OmniRoute, and optional local Ollama inference, but these are install-later modules.
