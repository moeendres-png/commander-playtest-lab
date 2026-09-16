# U5-E Cardinality Impact (post-WS229 5P + N-scoped replay)

## 5P post-WS229 impact: GREEN (DIRECTLY_VERIFIED)

- 5P Lions record through the repaired stack: 507 steps, dual replay
  PASS (507/507 x2), RNG 490 -> 1960 (identical to the WS218 lane values:
  engine/RNG path stable across the WS229 remediation).
- 5P decision-class census through repaired paths: priority, target,
  choose_object, choose_use, mana_payment, mulligan, declare_attacker,
  declare_blocker (no unsupported callback; no failure).
- 5P micro evidence (combat, SBA, zones, replacement, randomness,
  triggers-tokens) and 41/47 retained 5P disposition cells close the
  inherited 5P hole where provoked; the remainder stay explicitly UNKNOWN.
- 5P was never assumed from 2P/3P: dedicated 5P games, decks, seeds, and
  tapes throughout (card campaign 5P cells, Lions 5P records, anthem/static
  5P runs).

## 2P/3P

Same record+dual-replay treatment (360/403 steps; RNG 196->784 /
294->1176, identical to WS218 lane values). No 4P campaign (contract:
4P only on positive decision value; none identified — the repaired paths
are count-free per CARDINALITY_IMPACT_MAP, and 4P decision-mode evidence
is inherited, not re-run for ceremony).

## 6P

NOT_SUPPORTED / fail-closed, untouched by WS232 (no 6P run; boundary
revalidated by contract, not by probing — the MIN/MAX guard code path is
unchanged and predicate-bound via the session blob).

## Machine companion

`REPLAY_RNG_5_MATRIX.json`; `runs/replay/WS232_REPLAY_lions-{2,3,5}P.json`.
