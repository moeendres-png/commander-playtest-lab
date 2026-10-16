# docs/archive/ — historical provenance

Everything below this directory is **provenance only**. It is kept for audit and traceability and
is **not current instruction**: do not follow it as policy, and do not start work from it. Current
policy is `AGENTS.md`, `../PROJECT_MISSION.md`, `../CURRENT_EXECUTION_AUTHORITY.md` and
`../MODULE_MAP.md`; see `../README.md` for the navigation index.

## What is here

- `legacy_phase_artifacts/` — Phase 2–9 reports.
- Dated workstream and closure packets (`workstream_*_2026*/`, `*_2026MMDD/`, `*_erratum_*`,
  `ci479_*`, `b8_takeover_*`, ...), the `J_P*` phase records, `NEXT_STEP_HANDOFF_*`,
  `PROJECT_UPDATE_*`, and `phase*.md` reports.

Entries keep the relative sub-paths they had under `docs/`, so `docs/<name>` is now
`docs/archive/<name>`.

## What is not here

A historical-looking doc stays in `docs/` when anything outside the archive depends on it: code,
tests, workflows, config, sealed qualification manifests or `*SHA256SUMS*`, the core governing
docs, owner decisions, ADRs and freeze records, and `docs/claude/state/`.

## Rules

- Nothing under `src/`, `scripts/`, `tests/`, `.github/`, `config/`, `qualification/` or `.claude/`
  may reference a path inside this directory.
- Selection is reproducible: `python scripts/classify_docs.py` lists the movable entries and
  `python scripts/classify_docs.py --check` (run by `tests/unit/test_docs_archive.py`) fails when a
  historical doc sits outside the archive or code references the archive.
