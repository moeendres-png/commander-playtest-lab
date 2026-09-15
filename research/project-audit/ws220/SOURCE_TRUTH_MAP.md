# WS220 Source-Truth Map

Authority order verified on HEAD 67db0733 (see P-SRC-01 probe, rerunnable via
`python3 research/project-audit/ws220/probes/stale_source_scan.py`).

## Living authority (cite these)

1. `config/rules_engines.json` — sole machine-readable pin authority
   (XMage db134b97; Forge forge-2.0.14 @ a37a865a secondary; NO_PROVIDER_READY).
2. `docs/PROJECT_MISSION.md` — mission, 2–5P mandate, outcome-first policy.
3. Lane code + `docs/architecture/xmage-full-game-external-pilots.md`
   (modulo its stale :13 exactly-4P sentence).
4. Per-workstream seals (ws213/ws215 VALIDATION + FINAL_HANDOFF +
   COMMON_FIXTURE_DISPOSITION) for their scoped claims only.

## Frozen provenance (never cite as current)

- Migration/closeout reports (package 1.23.3/1.24.0 baselines, cfc36f44 pin).
- J-P3 contracts/spikes/runbooks (xmage_1.4.60V3, forge-2.0.14-era process).
- Phase-8.5 templates, B0 bridge doc, WS17 aggregates + candidate reports.
- `XMAGE_FULL_GAME_CLOSEOUT.md:11` pin (superseded; do not repin from it).

## Stale-but-reachable (reconcile, do not follow)

- `docs/OPERATIONAL_SIMULATION_POLICY.md` — 4P-only, untouched since 136afc8b.
- `docs/architecture/deckbuilding-simulation-separation.md:247`
  (`player_count = 4` scenario contract).
- `src/commander_lab/robustness.py` 4P error text + `test_operational_4p_policy.py`
  (contained to Structural lane; update with S11).
- `scripts/run_external_full_game_conformance.py:82` hardcoded 4P (fix with S5).

## Filename-trap inventory (verify per use, never trust by name)

102 CURRENT/FINAL/LATEST names (P-SRC-01 §name_traps). Living ones needing
per-use verification: `data/decision/DECISION_CONTRACT_CURRENT.json`,
`docs/CARD_COVERAGE_CURRENT.md`, `docs/CARD_KNOWLEDGE_POLICY_CURRENT.md`,
`data/collections/current/*`, `data/cards/*CURRENT*`. Historical bulk under
`artifacts/` is provenance, not state.
