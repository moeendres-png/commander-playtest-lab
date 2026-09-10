# Architecture

## Project direction versus existing implementation

[Commander Simulator Next's mission](PROJECT_MISSION.md) governs future architecture
selection: maximally rules-correct gameplay supporting learning and deck optimization,
4P as the primary benchmark rather than a fixed architecture, 2–5P minimum conformance,
and preference for 6+ / variable player counts when they improve correctness,
simplicity, reuse, testability or research/implementation without reducing conformance.
Existing engines, simulators or frameworks may replace whole workstreams on evidence.
The layers below describe the existing system, not an Architecture Freeze or a mandate
to retain this implementation. `ARCHITECTURE_FREEZE = NOT CLAIMED`;
`PRODUCTION_PROVIDER = NOT SELECTED`.

The existing project separates eight layers:

1. immutable card, deck and game-state models;
2. structural simulation;
3. tactical oracle;
4. external engine adapters;
5. pilot decision logic;
6. analysis and constrained optimization;
7. tool and agent orchestration;
8. storage, reports and observability.

Agents and pilots cannot directly mutate game state. Pilots rank engine-provided legal actions. OpenAI agents can only call validated local tools. Every tool result includes run metadata, deck hashes, data snapshot hash, engine version, seed and estimate type.

Validation levels remain separate:

- `structural_only`;
- `tactical_oracle`;
- `external_rules_engine`.

The Phase-10 workflow never silently falls back from an external engine. Current opponent role profiles are local structural abstractions. Fixed precons are not treated as upgraded lists, and the Cosmic Spider-Man profile is explicitly a synthetic mid-budget completion.
