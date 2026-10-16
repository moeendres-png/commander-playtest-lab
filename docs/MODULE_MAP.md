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

## Entry points

`pyproject.toml` defines two console scripts:

- `commander-lab` -> `commander_lab.cli.main:app` (`cli/app.py` holds the commands).
- `commander-lab-optimizer` -> `commander_lab.optimizer_v2_cli:app`.

## Packages in `src/commander_lab/`

Churn = number of file touches since 2026-09-01 (a rough activity signal only).

| Package | Purpose | Status |
|---|---|---|
| `cli/` | Typer CLI (`app.py`, `main.py`) | active |
| `models/` | Pydantic data models (cards, game, mulligan, meta, engine runtime, counterfactual, diagnostics) | active (churn 53) |
| `storage/` | Atomic JSON/DB stores, hashing, run identity and integrity, result cache | active |
| `repositories/` | Read-only repositories over canonical project data | active |
| `cards/` | Card catalog and normalization | active |
| `importers/` | Deck/collection importers (CSV, XLSX, plaintext, Google Drive, opponents) | active |
| `primer/` | Primer-to-pilot compiler | active |
| `agents/` | Card knowledge, pilots, ensembles, guardrails, tracing, orchestration | active (guess: part is legacy demo/OpenAI workflow) |
| `engine/` | Engine boundary: action validation, process manager, runtime evidence, `structural/` model, `rules/` bridge to the external rules engine (XMage) incl. full-game drivers | active (churn 127, most active) |
| `whole_deck/` | Whole-deck lab: campaigns, decision authority, knowledge quality, mana, enrichment (60 files) | active (churn 125) |
| `mulligan/` | Mulligan lab and canonical mulligan logic | active |
| `optimization/` | Constraints, experiments, search, `jp5` | active (guess: `jp5` is phase-specific) |
| `candidates/` | External complete-deck candidate contracts and lossless gameplay handoff | active |
| `tools/` | Tool/service layer (registry, service, whole-deck prepare/run, candidate snapshots); `*_v120` files are versioned variants | active |
| `api/`, `mcp/` | Tool server and MCP server surfaces | active (guess, small) |
| `semantic_replay/` | Engine-neutral semantic replay tape contract | qual / active |
| `evals/` | Evals: golden, differential, invariants, agent eval | qual |
| `audit/` | Invariant audit runner/runtime | qual |
| `qualification/current_boundary/` | Current-boundary qualification: bridge launcher, game driver, midgame rows, replay twins, freeze record, knowledge projection | qual (churn 85) |
| `meta/`, `opponent_ensembles/` | Meta and opponent-ensemble stores | active (small) |
| `features/`, `analysis/`, `reporting/`, `observability/`, `provenance/`, `packages/` | Support: replay debugger/scenario editor, validation analysis, reporting helpers, local tracing, provenance graph, package extraction | active (guess, small) |
| `acceptance/` | Phase 10 acceptance | hist (guess) |

Top-level modules (about 45 `*.py` in `src/commander_lab/`), grouped by name:

- Optimizer/candidate workflow: `optimizer_cli`, `optimizer_v2_cli`, `candidate_evaluation`,
  `candidate_screening`, `cut_frontier`, `advancement`, `adaptive_budget`, `priority_workflows`,
  `workflow_session`, `workflow_identity`.
- Decision quality and statistics: `decision_*`, `canonical_features`, `semantic_*`,
  `tactical_evidence`, `counterfactual`, `robustness`, `model_*`, `opponent_uncertainty`.
- Qualification / freeze: `meta_qualification`, `freeze_readiness`, `technical_truth`,
  `fresh_rebuild*`, `first_run_preparation`, `rogshai_mvp_acceptance` (qual; the last is
  guess-hist, tied to a Rogshai MVP experiment).
- Data: `deck_registry`, `data_sync`, `commander_spellbook`, `variant_identity`, `mana_analysis`,
  `pod_scheduling*`, `playstyle`, `project_context`, `diagnostics`.

## Active scripts in `scripts/`

About 100 files. Referenced by CI workflows (`.github/workflows/`, 24 files) or touched since
2026-09-01 - these are the ones to know:

| Script | Why it matters |
|---|---|
| `run_current_boundary_qualification.py`, `assemble_current_boundary_evidence.py` | Current-boundary qualification and its evidence assembly (frequently changed) |
| `run_external_full_game_conformance.py`, `run_real_4p_full_game_smoke.py`, `run_midgame_capability_probe.py` | Real-engine conformance/smoke workflows |
| `run_full_game_deck_comparison.py`, `run_optimizer_v2_full_game_route.py`, `run_replay_twin_campaign.py` | Full-game deck comparison, optimizer route, replay twins |
| `run_candidate_handoff_conformance.py`, `run_candidate_paired_triage.py`, `run_candidate_evaluation_frontier.py` | Candidate workflows (CI) |
| `derive_rules_engines_capabilities.py`, `generate_full_game_contract_artifacts.py`, `seal_xmage_full_game_artifacts.py` | Contract/capability derivation and sealing |
| `verify_packaging_smoke.py`, `verify_container_provenance.py`, `verify_engine.sh`, `run_broad_secret_scan.py`, `security_evidence.py` | Packaging, provenance, engine and security checks |
| `bootstrap_engine_*.sh`, `start_engine.sh`, `stop_engine.sh`, `docker_*` | Engine setup and lifecycle |
| `run_isolated_pytest_suite.py`, `audit_workflow_impact.py` | Test isolation and workflow-impact auditing |
| `claude_handoff.py` | Regenerates `docs/claude/state/HANDOFF.md` |

Likely historical (not referenced by workflows; guess from names): `run_external_b3/b4*_regression.py`,
`run_j_p4_*`, `run_j_p5_*`, `run_j_p6_*`, `run_phase8_validation.py`. Note some `run_external_b4*`
are referenced by `external-engine-integration.yml`; verify before removing anything.

## Other top-level directories

- `engine-bridge/` - Java bridge to the rules engine; `vendor/`, `docker/` - engine pin and build.
- `config/` - pins and policy JSON (`rules_engines.json`); `schemas/` - JSON schemas.
- `tests/` - `unit/`, `qualification/`, `foundry/`, `integration/`, `property/`, `golden/`, etc.
- `qualification/`, `candidate-qualification/`, `evidence/`-style trees - sealed evidence; do not edit.
- `handoffs/`, `research/`, `artifacts/` - provenance material (guess: mostly hist).
- Root reports (`MIGRATION_CLOSEOUT.md`, `XMAGE_FULL_GAME_*`, `ARCHITECTURE_MIGRATION_REPORT.md`) - hist.

## Docs: current vs historical

Current / governing (start here):

- `README.md`, `AGENTS.md`, `docs/PROJECT_MISSION.md`, `docs/CURRENT_EXECUTION_AUTHORITY.md`,
  `docs/README.md`, `docs/REPOSITORY_TRIAGE_INDEX.md`, `docs/EVIDENCE_INDEX_REQUIREMENTS.md`,
  `docs/RETENTION_AND_LIFECYCLE_POLICY.md`, `docs/OPERATIONAL_SIMULATION_POLICY.md`.
- `docs/foundry-execution/` - canonical Foundry execution system (start at its `README.md`).
- `docs/claude/` - session playbook; `docs/claude/state/HANDOFF.md` is a continuation index only
  (git, tests and sealed evidence remain source truth).
- `docs/architecture/` and `docs/architecture.md` - design direction; `docs/engine_*.md`,
  `docs/rules-engine-bridge-protocol.md`, `docs/validation_levels.md`, `docs/installation.md`,
  `docs/known_limitations.md` - reference/how-to (guess: current, check dates).
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
| Superseded authority | `docs/COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md`, the 2026-09-10 coordinator authority file (superseded by `CURRENT_EXECUTION_AUTHORITY.md`; `docs/README.md` now points at `CURRENT_EXECUTION_AUTHORITY.md`) |
| PROJECT_UPDATE_* | `docs/PROJECT_UPDATE_*.md` (Aug 2026 scope snapshots) |

Dated directories are the freshest *work*, not necessarily the current *policy*; the 2026-09 to
2026-10 ones (for example `af07_actual_card_campaign_20261001`, `provider_readiness_packet_20261007`)
are recent evidence packets that policy documents cite.
