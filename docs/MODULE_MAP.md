# Module map (onboarding)

Navigation aid, **not authority**. Where this map and `AGENTS.md`, `docs/PROJECT_MISSION.md`
or `config/rules_engines.json` disagree, those win. Statuses below are derived from
imports, `pyproject.toml` entry points, `.github/workflows/` references and
`git log --since=2026-09-01 --name-only`; entries marked **(guess)** are inferred from file
names only and were not verified. A file name containing `CURRENT`/`FINAL` proves nothing
(`AGENTS.md`).

Status legend: **active** = product path, **qual** = qualification / evidence machinery,
**hist** = historical provenance (kept, not the place to start).

## Read first

1. `README.md` - entry point and source-of-truth table.
2. `AGENTS.md` - durable agent policy (`CLAUDE.md` is only an entrypoint to it).
3. `docs/PROJECT_MISSION.md` - governing mission and gates.
4. `docs/CURRENT_EXECUTION_AUTHORITY.md` - current executor routing.
5. `docs/README.md` - navigation index of `docs/`.
6. `config/rules_engines.json` - sole machine-readable engine pins.
7. `docs/DECK_VARIANT_WORKFLOW.md` - deck-variant workflow (filter, then real games).

## Entry points

`pyproject.toml` defines one console script:

- `commander-lab` -> `commander_lab.cli.main:app` (`candidates ...` and `engine-verify`;
  `python -m commander_lab.engine.verify_cli` runs the engine check alone).

## Packages in `src/commander_lab/`

12 subpackages currently exist under `src/commander_lab/`:

| Package | Purpose | Status |
|---|---|---|
| `cli/` | Typer CLI (`app.py`, `main.py`) — `candidates ...` and `engine-verify` | active |
| `models/` | Pydantic data models (cards, core/rules enums, structural deck profiles, engine runtime) | active |
| `storage/` | Atomic JSON/SQLite stores, hashing, run identity and integrity, result cache | active |
| `repositories/` | Candidate repositories (`candidates.py`) | active |
| `cards/` | Card catalog and normalization, `commander_flags` | active |
| `agents/` | Card knowledge, deck guides, deck plan, live routing, pilots, style | active |
| `engine/` | Engine boundary: action validation, process manager, runtime evidence, `structural/` model, `rules/` bridge to XMage incl. full-game drivers | active |
| `candidates/` | External complete-deck candidate contracts and lossless gameplay handoff | active |
| `semantic_replay/` | Engine-neutral semantic replay tape contract and canonicalizer | qual / active |
| `evals/` | Differential evaluation and scoring models (`differential`, `models`) | qual |
| `qualification/current_boundary/` | Current-boundary qualification: bridge launcher, game driver, midgame rows, replay twins, freeze record, knowledge projection | qual |
| `studio/` | Commander Studio (`docs/STUDIO_DECKBUILDER.md`): SQLite store (`studio.sqlite3`), importers, public card data, immutable deck revisions, counted universes, strength index, local web UI (`web.py`, `static/`), and game logs / spectator & play views (`games.py`, `play.py`, `play_batch.py`, `launch.py`, `docs/STUDIO_GAME_VIEWER.md`) | active |

There are 13 non-`__init__` top-level `*.py` modules in `src/commander_lab/`, grouped by name:

- Features, deck analysis and statistics: `canonical_features`, `decision_statistics`, `deck_profile`, `deck_readiness`, `deck_registry`, `deck_variant`, `mana_analysis`, `owner_data`, `semantic_features`.
- Qualification / freeze: `freeze_readiness`, `meta_qualification`, `project_context`, `technical_truth`.

Modules whose paths are checked or hashed by qualification or truth code (`project_context`, `technical_truth`) stay at top level.

## Active scripts in `scripts/`

114 scripts (`.py`/`.sh`), referenced by the 17 workflows in `.github/workflows/` or used for Studio data and game measurements:

| Script | Why it matters |
|---|---|
| `run_current_boundary_qualification.py`, `assemble_current_boundary_evidence.py`, `assemble_freeze_record.py` | Current-boundary qualification, freeze record, and evidence assembly |
| `run_external_full_game_conformance.py`, `run_real_4p_full_game_smoke.py`, `run_midgame_capability_probe.py` | Real-engine conformance and smoke workflows |
| `run_full_game_deck_comparison.py`, `run_replay_twin_campaign.py` | Paired full-game deck comparison and replay twins |
| `derive_rules_engines_capabilities.py`, `generate_full_game_contract_artifacts.py`, `seal_xmage_full_game_artifacts.py` | Contract/capability derivation and sealing |
| `verify_packaging_smoke.py`, `verify_container_provenance.py`, `verify_engine.sh`, `run_broad_secret_scan.py`, `security_evidence.py`, `ci_gate.py` | Packaging, provenance, engine, security, and CI gate checks |
| `bootstrap_engine_*.sh`, `docker_resolve_engine_pin.py` | Engine setup and pin resolution |
| `audit_workflow_impact.py`, `classify_docs.py` | Test-isolation audit and active/archive document classification |
| `determinism_probe.py`, `precon_pod_sweep.py`, `benchmark_xmage_full_games.py`, `measure_precon_imports.py`, `pilot_decision_report.py`, `measure_throughput_steady_state.py` | Real-game measurement: determinism, precon pod sweeps, speed and identity benchmarks, import coverage, pilot reports (`docs/performance/`) |
| `import_chulane_corpus.py`, `map_corpus_oracle_ids.py`, `build_corpus_fill.py`, `derive_edhrec_signals.py`, `derive_global_signals.py`, `build_spellbook_shells.py`, `spellbook_combos_fetch.py`, `collect_playgroup_card_atlas.py`, `deck_bracket_label.py` | Commander Studio data pipeline: corpus import/mapping, counted fills, signal derivation, Spellbook combos/shells, Playgroup card atlas, deck bracket utility |
| `regenerate_hash_manifests.py` | Rebuilds `qualification/SHA256SUMS` and `WS17_SHA256SUMS` |
| `claude_handoff.py` | Regenerates `docs/claude/state/HANDOFF.md` (engine pin and newest sealed epoch from `config/rules_engines.json`, open lanes, heads) |

External engine regression scripts (`run_external_b3_regression.py`, `run_external_b4*_regression.py`) are exercised by `.github/workflows/external-engine-integration.yml`.

## Other top-level directories

- `engine-bridge/` - Java bridge to the rules engine; `vendor/`, `docker/` - engine pin and build.
- `config/` - pins and policy JSON (`rules_engines.json`); `schemas/` - `engine_adapter_protocol.schema.json` and `engine_protocol/`.
- `tests/` - `unit/`, `contract/`, `qualification/`, `integration/`, `property/`, `golden/`, etc.
- `qualification/`, `candidate-qualification/` - sealed evidence; do not edit without an Owner decision.
- `artifacts/` - architecture/audit/contract JSON outputs checked by unit tests.
- Root reports (`MIGRATION_CLOSEOUT.md`, `XMAGE_FULL_GAME_*`, `ARCHITECTURE_MIGRATION_REPORT.md`) - historical migration records.

## Docs: current vs historical

Current / governing (start here):

- `README.md`, `AGENTS.md`, `docs/PROJECT_MISSION.md`, `docs/CURRENT_EXECUTION_AUTHORITY.md`,
  `docs/README.md`, `docs/REPOSITORY_TRIAGE_INDEX.md`, `docs/EVIDENCE_INDEX_REQUIREMENTS.md`,
  `docs/RETENTION_AND_LIFECYCLE_POLICY.md`, `docs/OPERATIONAL_SIMULATION_POLICY.md`.
- `docs/claude/` - session playbook and repin runbook; `docs/claude/state/HANDOFF.md` is a
  continuation index only (git, tests and sealed evidence remain source truth).
- `docs/performance/` - dated speed and determinism measurements; each file's header names the pin and commit.
- `docs/architecture/` and `docs/architecture.md` - design direction; `docs/engine_*.md`,
  `docs/engine_adapter_protocol.md`, `docs/installation.md` -
  reference/how-to (guess: current, check dates; superseded pages are in `docs/archive/`).
- `docs/architecture_freeze_20261010/`, `docs/owner_decision_20261013_forge_removal/`,
  `docs/engine_strategy_20261009/` - latest owner/architecture decisions (newest dated dirs).

Historical provenance (kept for audit; do not treat as instructions). Entries that no code,
manifest or governing document references are physically moved to `docs/archive/` (same relative
subpaths; see `docs/archive/README.md`; selection is reproducible with `scripts/classify_docs.py`).
The table below names the groups; a group member still directly under `docs/` is referenced by
code or a sealed manifest and stays in place:

| Group | Where |
|---|---|
| Phase / stage reports | `docs/archive/`, `docs/phase*.md`, `docs/J_P*`, `docs/NEXT_STEP_HANDOFF_*`, `docs/roadmap/` |
| Dated workstream records | `docs/workstream_*_2026*/` (about 40 dirs), `docs/*_2026MMDD/` closures |
| AF-lane and erratum records | `docs/af0*`, `docs/af456_*`, `docs/*_erratum_*`, `docs/forge_*`, `docs/xmage_*` |
| CI/PR-specific records | `docs/ci479_*`, `docs/pr*`, `docs/b8_takeover_*`, `docs/oc572_*` |
| Integrity/hygiene sweeps | `docs/project_integrity_*`, `docs/project_hygiene_*`, `docs/project_integration_hygiene_*`, `docs/test_signal_integrity_*` |
| Superseded authority | `docs/archive/opencode-foundry/` (the 2026-09-27 and 2026-09-10 coordinator authority files; superseded by `CURRENT_EXECUTION_AUTHORITY.md`) |
| PROJECT_UPDATE_* | `docs/PROJECT_UPDATE_*.md` (Aug 2026 scope snapshots) |

Dated directories are the freshest *work*, not necessarily the current *policy*; the 2026-09 to
2026-10 ones (for example `af09_replay_twins_20261001`, `provider_readiness_packet_20261007`)
are recent evidence packets that policy documents cite.
