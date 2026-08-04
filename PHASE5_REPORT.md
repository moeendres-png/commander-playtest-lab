# Phase 5 — OpenAI Agent and Local Function-Tool Server

## Status

Phase 5 is implemented on top of the Phase-4 repository.

- Implementation commit: `05682049d3c35fc5e4058307fc65862f4c978836`
- Package version: `0.5.0`
- Structural engine: `structural-0.4.0`
- Output label: `structural_model_estimates`
- Local current deck baselines unchanged
- Google Drive files unchanged
- OpenAI traces separated from deterministic game logs

## Local Function-Tool server

The FastAPI application exposes:

- `GET /health`
- `GET /v1/tools`
- `POST /v1/tools/{tool_name}:invoke`
- `POST /v1/workflows:run`

The server publishes and validates these 18 tools:

1. `validate_deck`
2. `inspect_deck`
3. `run_goldfish`
4. `run_matchup_batch`
5. `compare_decks`
6. `compare_variants_paired`
7. `run_card_ablation`
8. `run_package_ablation`
9. `run_commander_denial`
10. `generate_swap_matrix`
11. `search_variants`
12. `run_holdout`
13. `run_sensitivity`
14. `recommend_upgrades`
15. `validate_upgrade`
16. `ingest_playtest`
17. `calibrate`
18. `create_report`

Every invocation returns a structured `ToolResponse` with run identity, Git commit, engine version, data snapshot hash, deck hashes, scenario hash, seed, iteration count, elapsed time, log locations, warnings, and understandable errors.

## Agent architecture

The optional live runtime uses the OpenAI Agents SDK and Responses path:

- **Orchestrator Agent** interprets the goal, plans bounded validation, invokes tools and specialist agents, and returns `WorkflowReport` structured output.
- **Deck Analyst** evaluates role coverage, weaknesses, cuts, and candidate cards.
- **Simulation Analyst** selects scenarios, paired seeds, run sizes, sensitivity checks, and detects model failures.
- **Red-Team Reviewer** challenges role losses, overfitting, weak cuts, alternative explanations, and failed holdouts.

Agents receive only the Function Tools. They have no object reference to a mutable game state and cannot directly set life, move cards, add mana, edit deterministic logs, or force a winner.

## OpenAI SDK features

Implemented integration points:

- Agents SDK agent loop;
- Responses API path through OpenAI model names;
- strict Function Tools generated from Pydantic inputs;
- `WorkflowReport` Structured Output;
- persistent `SQLiteSession`;
- built-in SDK tracing with sensitive trace data disabled;
- blocking input guardrail against direct game-state mutation;
- output guardrail enforcing `structural_model_estimates` and tool-derived evidence;
- lifecycle hooks for model and tool trace events;
- aggregated usage accounting.

The live adapter targets `openai-agents>=0.18.3,<0.19` and `openai>=2.45,<3`, matching the current package dependency floor documented by the official package metadata at implementation time.

## Cost and action limits

`CostLimits` implements:

- maximum model calls;
- maximum total tokens;
- maximum output tokens per model call;
- configurable maximum estimated API cost;
- configurable input and output rates rather than hard-coded model prices;
- maximum simulation time;
- large-run approval threshold;
- hard iteration maximum;
- maximum searched variants.

Runs above the configured threshold require the explicit local approval token `APPROVED_LARGE_RUN`. The default hard maximum is 100,000 iterations. Tool failures are returned structurally instead of being silently ignored.

The simulation-time limit is checked at the deterministic tool boundary. Existing per-game turn, event, no-progress and spell limits remain active inside the structural engine.

## Log separation

Deterministic game evidence:

```text
data/runs/tool_runs/<invocation>/events/
```

Local OpenAI workflow traces:

```text
data/runs/openai_traces/<workflow>.jsonl
```

Persistent agent sessions:

```text
data/runs/openai_sessions.sqlite
```

The local agent trace records orchestration lifecycle and tool identities, not deterministic game events. OpenAI SDK tracing remains independently configurable.

## End-to-end demo

The offline demo performed the required workflow without model calls:

1. imported and validated `korvold/current`;
2. ran 80 structural four-player matches against the synthetic Aggro, Control, and Engine fixtures;
3. screened a possible cut;
4. tested the alternative with 80 paired seeds and identical starting positions;
5. ran two 80-game holdout pods;
6. produced a structured Markdown evidence report.

### Candidate

- Cut screened: `Scouring Swarm`
- Addition screened: `Idol of Oblivion`
- Candidate physical status: `project_context_present_not_revalidated_phase5`
- Screening status: candidate only, not confirmation

### Main paired comparison

- Games: 80
- Placement improvement: `+0.0250`
- Place-1 share delta: `+0.0250`
- Cards drawn delta: `+0.2000`
- Paired outcomes: 5 variant wins, 3 losses, 72 ties

### Holdout

- Control / Control / Engine: placement improvement `-0.0375`
- Aggro / Aggro / Control: placement improvement `+0.0375`
- Mean holdout placement improvement: `0.0`
- All holdouts nonnegative: `false`

### Decision

`Scouring Swarm → Idol of Oblivion` was **rejected** by the automated Phase-5 validation because one holdout pod became worse. This is a technical demonstration using synthetic fixtures, not a recommendation to change the real Korvold deck.

## Verification

- 84 tests passed.
- Python compilation passed.
- The FastAPI server listed exactly 18 tools and invoked them successfully.
- A workflow endpoint returns a clear service-unavailable error when the API key or optional SDK is absent.
- Tool wrappers expose only the validated Pydantic payload and strict mode.
- A fake SDK compatibility test verified four separate agents, structured outputs, sessions, reasoning configuration, and guardrail attachment.
- Large-run approval, paired reproducibility, role screening, holdout validation, and separate trace paths are covered by tests.

## Live-runtime limitation

The build container could not resolve external package hosts and its configured package index did not provide the optional OpenAI Agents SDK. Therefore no paid API request was executed and the live SDK adapter was not imported against an installed wheel in this environment.

The adapter was checked against the current official Agents SDK documentation and package metadata, and its interface is covered by a local fake-runtime test. A final live smoke test remains required on the user's local machine after installing `.[api,openai]` and supplying `OPENAI_API_KEY`.
