# Final Function Matrix

| Category | Function | Code | Tests | Practical | Validation | Maturity | Error or limit |
|---|---|---|---|---|---|---|---|
| Grundsystem | TXT deck import | yes | passed | passed | structural_only | complete |  |
| Grundsystem | CSV deck import | yes | passed | passed | structural_only | complete |  |
| Grundsystem | XLSX deck import | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Oracle name normalization | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Commander configuration | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Partner configuration | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Singleton validation | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Color identity validation | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Physical quantity validation | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Simultaneous allocation validation | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Deck hash | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Data snapshot hash | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Three-player pods | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Four-player pods | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Five-player pods | yes | passed | passed | structural_only | complete |  |
| Grundsystem | London Mulligan | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Commander tax | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Commander damage per commander/opponent | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Combat | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Removal | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Counterspells | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Protection | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Board wipes | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Recursion | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Graveyard hate | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Elimination | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Game end | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Deterministic seed derivation | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Worker-independent structural results | yes | passed | passed | structural_only | complete |  |
| Grundsystem | Mana and color stability | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Approximated structural mana model, not a complete rules engine. |
| Grundsystem | Stack semantics | yes | passed | passed_with_limitations | tactical_oracle | functional_with_limitations | External stack/priority semantics not validated. |
| Grundsystem | Priority semantics | yes | passed | passed_with_limitations | tactical_oracle | functional_with_limitations | External engine pending. |
| Piloten und Simulation | KorvoldPilot | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | RogShaiPilot | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Generic opponent pilots | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Weak pilot | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Average pilot | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Strong pilot | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Near-optimal heuristic pilot | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Ten specialized multi-pilot profiles | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Pilot information boundaries | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Protection windows | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Counter windows | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Rebuild decisions | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Finish decisions | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Pilot ensemble comparison | yes | passed | passed | structural_only | complete |  |
| Piloten und Simulation | Threat assessment | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Heuristic threat model. |
| Piloten und Simulation | Political visibility | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Politics and negotiation remain abstractions. |
| Optimierung | Commander denial | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Card ablation | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Package ablation | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Swap matrix | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Local search | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Beam search | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Package search | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Pareto front | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Approximate Shapley contributions | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Paired variant comparison | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Holdout evaluation | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Sensitivity analysis | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Red-team review | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Optimierung | Upgrade release gates | yes | passed | passed | structural_only | functional_with_limitations | Structural/model evidence only; no automatic deck application. |
| Erweiterungen | 12.1 Meta Knowledge Base | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Model/source evidence with documented limits. |
| Erweiterungen | 12.2 Primer-to-Pilot Compiler | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Model/source evidence with documented limits. |
| Erweiterungen | 12.3 Multi-Pilot Ensembles | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Model/source evidence with documented limits. |
| Erweiterungen | 12.4 Archetype and Package Extraction | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Model/source evidence with documented limits. |
| Erweiterungen | 12.5 Provenance | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Model/source evidence with documented limits. |
| Erweiterungen | 12.6 Local Meta Learning | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Implementation complete; zero real games prevents learning. |
| Erweiterungen | 12.7 Opponent Ensembles | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Model/source evidence with documented limits. |
| Erweiterungen | 12.8 Mulligan Lab | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Model/source evidence with documented limits. |
| Erweiterungen | 12.9 Counterfactual Replay | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Model alternative, not historical fact; external engine not used. |
| Erweiterungen | 12.10 Decision Diagnostics | yes | passed | passed_with_limitations | structural_only | functional_with_limitations | Diagnosis is not empirical proof. |
| Infrastruktur | SQLite migrations and integrity | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | Run manifests | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | Event logs | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | Replay export/import | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | Artifact hashes | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | Experiment registry | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | CLI | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | FastAPI | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | Function Tool HTTP server | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | Guardrails | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | Cost limits | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | Session persistence | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | Trace separation/redaction | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | Drive recovery artifacts | yes | passed | passed | structural_only | complete |  |
| Infrastruktur | Parquet write path | yes | passed | blocked | structural_only | partial | Optional pyarrow/fastparquet dependency is not installed. |
| Infrastruktur | Actual MCP server | no | not_run | not_run | structural_only | missing | Project exposes a FastAPI Function Tool server, not a true MCP transport. |
| Infrastruktur | OpenAI live orchestrator | yes | passed | blocked | structural_only | functional_with_limitations | OPENAI_API_KEY and openai/openai-agents packages are absent; offline adapter tests pass. |
| Infrastruktur | Google Drive final audit upload | yes | not_run | not_run | structural_only | partial | Completed locally; final upload/round-trip is performed after packaging if connector file upload succeeds. |
| Externe Regelengine | XMage adapter | yes | passed | passed_with_limitations | tactical_oracle | functional_with_limitations | No real XMage/Forge runtime executed. |
| Externe Regelengine | Forge adapter | yes | passed | passed_with_limitations | tactical_oracle | functional_with_limitations | No real XMage/Forge runtime executed. |
| Externe Regelengine | Engine process manager | yes | passed | passed_with_limitations | tactical_oracle | functional_with_limitations | No real XMage/Forge runtime executed. |
| Externe Regelengine | JSONL protocol | yes | passed | passed_with_limitations | tactical_oracle | functional_with_limitations | No real XMage/Forge runtime executed. |
| Externe Regelengine | Capability schema | yes | passed | passed_with_limitations | tactical_oracle | functional_with_limitations | No real XMage/Forge runtime executed. |
| Externe Regelengine | Tactical Oracle | yes | passed | passed_with_limitations | tactical_oracle | functional_with_limitations | No real XMage/Forge runtime executed. |
| Externe Regelengine | External runtime bootstrap scripts | yes | passed | passed_with_limitations | tactical_oracle | functional_with_limitations | No real XMage/Forge runtime executed. |
| Externe Regelengine | Real capability handshake | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Externe Regelengine | External deck import | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Externe Regelengine | External Commander multiplayer | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Externe Regelengine | External legal actions | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Externe Regelengine | External action submission | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Externe Regelengine | External illegal-action rejection | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Externe Regelengine | External event log | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Externe Regelengine | External replay | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Externe Regelengine | External partner validation | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Externe Regelengine | External Commander tax validation | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Externe Regelengine | External Commander damage validation | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Externe Regelengine | External stack validation | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Externe Regelengine | External priority validation | partial | skipped | blocked | external_rules_engine | partial | ENGINE_START_COMMAND is empty; Maven/Gradle/Docker absent; no external binary/source configured. |
| Reale Playtests | CSV/XLSX/JSON playtest import | yes | passed | passed | structural_only | complete | Synthetic fixtures only during audit. |
| Reale Playtests | Dataset versioning and corrections | yes | passed | passed | structural_only | complete | No real records imported. |
| Reale Playtests | Real-playtest calibration | yes | passed | blocked | real_playtest_observed | partial | missing_user_data: real_imported_games=0. |
