# XMage full-game measurements, 2026-10-12

Raw local measurements behind `docs/performance/XMAGE_FULL_GAME_SPEED_2026-10-12.md`.
They are local observations (4 cores, JDK 21), not qualification evidence.

Each result line holds the semantic transcript SHA-256 of one game, decisions, winners,
wall time and bridge child CPU time. The bar for every change: identical SHA-256 to the
baseline for every game.

## Files

- `results/ab_*.json`: 4 real 4P games (seeds 1-4) per variant.
  - `main` = pin 3cbf7741, `reuse` = mana reuse (#759), `scan` = reuse + bulk card scan,
    `cds` = scan + AppCDS, `labcds` = lab jar + CDS, `lazy` = lazy card copy prototype,
    `memo` = per-source memo (dropped), `fork` = single-copy variant (rejected: 1 of 14 games differed).
- `results/coverage_*.log`: 10 games from the coverage decks (5 pods, seeds 1-2).
- `tools/bench4p.py`: the runner used for these numbers (superseded by `scripts/benchmark_xmage_full_games.py`).
- `tools/coverage_ab.sh`: runs the 5 coverage pods.
- `tools/jfragg2.py`: attributes JFR execution samples to bridge call sites.
- `tools/single_copy.patch`: the rejected single-copy change to `PlayerImpl.getManaAvailable`.

## Known open items

- The smoke run on a freshly built main-pin bridge jar returned `BRIDGE_CLOSED` (seed 2),
  while the same pin earlier ran fine. Not yet diagnosed.
- JFR raw recordings are not committed (about 13 MB each); regenerate with `-XX:StartFlightRecording`.
- `results/par_lazy_r1.log`: an early parallel run of the lazy-copy prototype that failed with BRIDGE_ERROR; the rerun is in `coverage_lazy.log`.
