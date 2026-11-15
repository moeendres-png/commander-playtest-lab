# Module ownership

| Layer | Modules | Responsibility | Forbidden dependency |
|---|---|---|---|
| deterministic_state_and_rules | `models`, `engine.structural` | State, legal transitions, deterministic simulation | agents/OpenAI |
| engine_adapters | `engine.rules`, `engine.process_manager` | External process/protocol boundary | reporting truth promotion |
| tactical_oracle | `engine.rules.tactical` | Offline tactical fixtures only | external validation claims |
| pilot_decision_logic | `agents.pilots` | Select among legal actions | direct state mutation |
| agent_orchestration | `agents`, `tools`, `api` | Tool planning and reports | deterministic state mutation |
| analysis_and_optimization | `analysis`, `optimization` | Statistics and candidate validation | canonical deck writes |
| storage_and_reporting | `storage`, `reporting`, `observability` | Atomic persistence, manifests, reports | game semantics |
