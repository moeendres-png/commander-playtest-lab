# docs/ — index

Navigation aid, not authority. Where this page and a governing document disagree, the
governing document wins (`../AGENTS.md` §3). Filenames with `CURRENT`, `FINAL` or `LATEST`
confer no authority.

## What the product is

Commander Studio is a local application (`../src/commander_lab/studio`) to build Commander
decks, play them and simulate them. Games are full rules games on the pinned XMage engine
through the Java bridge (`../engine-bridge/`), played by the pilots in
`../src/commander_lab/engine/rules` and `../src/commander_lab/agents`. The sealed
qualification epoch (`../qualification/`, `../candidate-qualification/`,
`../src/commander_lab/qualification`, `../tests/qualification`) is the evidence that the engine
and bridge are fit for this; it is never edited.

## Current guidance

| Document | What it is |
|---|---|
| `PROJECT_MISSION.md` | Governing mission and gates |
| `OWNER_DECISIONS_STUDIO_20261112.md`, `OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md`, `OWNER_DECISION_SIX_PLAYER_MAX_20261108.md` | Owner decisions for the Studio (maximum 6 players, default 4) |
| `OWNER_DECK_FOCUS_CURRENT.md` | Owner-deck work focus: Chulane only |
| `STUDIO_ROADMAP_20261112.md`, `STUDIO_PLAN_SIMULATOR.md`, `STUDIO_TARGET_SCOPE.md` | Studio plan, simulator throughput steps, and consolidated Best-Of-All-Worlds target scope |
| `STUDIO_DECKBUILDER.md`, `STUDIO_GAME_VIEWER.md`, `DECKBUILDER_DATA_1205.md`, `DECKBUILDER_TIERLIST_DESIGN.md` | Deck builder, spectator page, data and tier-list design |
| `STUDIO_BRIDGE_GATE_TOOLING.md` | Bridge and gate tooling used by the Studio |
| `CURRENT_EXECUTION_AUTHORITY.md` | Who runs what, at which effort (with `AGENTS.md` §6–§8) |
| `CI_WHICH_CHECK_RUNS_WHEN.md`, `CI_GATES_IMPROVEMENT_PLAN_20261112.md` | Which check starts when; open CI points |
| `claude/REPIN_RUNBOOK.md` | How the engine pin is moved |
| `claude/SESSION_PLAYBOOK.md`, `claude/state/HANDOFF.md` | Session know-how; generated continuation index (git wins) |
| `engine_setup.md`, `installation.md`, `engine_troubleshooting.md` | Install and run the engine and the lab |
| `engine_adapter_protocol.md` | Bridge protocol (schema: `../schemas/engine_adapter_protocol.schema.json`) |
| `DECK_VARIANT_WORKFLOW.md`, `CUSTOM_DECKS.md`, `PRECON_VALIDATION.md`, `CARD_COVERAGE.md`, `coverage/` | Deck variants, own decks, precon and card coverage measurements |
| `performance/` | Dated measurements of speed and determinism; each header names pin and commit |
| `research/`, `studio/` | Data-derived reports and source catalogs behind the Studio's data pipeline |
| `EVIDENCE_INDEX_REQUIREMENTS.md`, `RETENTION_AND_LIFECYCLE_POLICY.md` | Evidence index schema and retention policy |
| `architecture/`, `architecture_freeze_20261010/`, `owner_decision_*/`, `engine_strategy_*/` | Architecture direction and the decisions that fixed it (XMage only) |

Several dated directories (`af09_*`, `architecture_freeze_readiness_*`, `final_prefreeze_*`,
`workstream_*`, `*_erratum_*`, `J_P*.json`, ...) stay in place because a test, script, workflow
or machine-read sealed record reads them by path. They are records of the sealed epoch, not
guidance. `orientation` pages kept for a test (`architecture.md`, `REPOSITORY_TRIAGE_INDEX.md`,
`commander-simulator-next.prd.md`) predate the Studio; read them as history.

## Archive

`archive/` holds documents that describe removed or finished things, as provenance only
(`archive/README.md`). Topics: `opencode-foundry`, `tool-service-mcp`,
`deck-optimizer-j-phases`, `mulligan-lab`, `meta-store-primer`, `structural-simulator`,
`rogshai-campaigns`, `audits-and-hygiene`, `handoffs-and-reviews`, `prefreeze-campaigns`,
`superseded`, `artifacts-history` (generated outputs moved from `artifacts/`), plus the older
dated packets directly under `archive/`. Each topic folder has a
README with why it was archived and the last commit at which the described code existed.

Selection is reproducible: `python scripts/classify_docs.py` (plan),
`--inventory FILE` (every document with class and anchor) and `--check`.
