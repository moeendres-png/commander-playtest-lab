# WS223 Cardinality CI Contract

Merge-relevant lane: `.github/workflows/xmage-full-game-conformance.yml`.

## Live coverage (all real production full-game execution, no stubs)

| Count | Mode | Command | Gate |
|---|---|---|---|
| 2P | bounded smoke (25 decisions) | `--player-count 2 --smoke-decisions 25` | seed/count binding, mulligan+priority, no unsupported callback, clean shutdown |
| 3P | bounded smoke (25 decisions) | `--player-count 3 --smoke-decisions 25` | same |
| 4P | full game-over ×2 + replay gate | (default) | terminal, decisions>0, evidence class, private-state scan, semantic match, mulligan+priority |
| 5P | bounded smoke (45 decisions) | `--player-count 5 --smoke-decisions 45` | same as 2P/3P; 45 calibrated live 2026-09-15 (5P@25 misses priority) |
| 6P | fail-closed probe, no engine | `--player-count 6 --expect-fail-closed` | `FAIL_CLOSED`, `engine_launched=false` |

## Invariants

- Default script invocation is byte-for-byte the legacy 4P gate (same seed
  `20260824`, same artifact paths) — existing evidence continuity preserved.
- Per-count seeds are distinct (`20260824–20260827`) so game identities
  cannot collide across cardinalities.
- 6P support is not claimed anywhere; three further rejection layers back
  the probe (scenario model, `_validate_inputs`, pilot policy).
- Cost bound: one XMage build + one bridge build; 3×25 bounded decisions +
  one 4P pair; 90-minute job cap retained.
