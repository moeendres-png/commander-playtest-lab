# R19 Validation

## Identity / hygiene

- Branch `cpl/xmage-six-player-20260921`, base `faffab84` (successor
  tip, clean at creation; three-deck/physical-pool untouched).
- Changes: 8 prod files (gates/bounds/seeds/targets) + 2 test files
  (new gate test; variable-player + ws223 updates) + conformance
  script (counts/seed/target) + `docs/workstream_lab_sixplayer_20260921/`
  evidence (8 files). No deck/engine/pin changes.

## Qualification (DIRECTLY_VERIFIED)

- Java bridge: 155/155 (incl. 6P gate 2 + updated 1,7 negatives).
- Python: 761 passed; residual 19 failed (14 parked CI-wiring asserting
  workflow files this WS does not touch + 5 proven-pre-existing
  openpyxl-env, rerun-identical on pristine base class) + 40
  pre-existing collection errors (missing third-party deps).
- Live: 6P smoke PASS + 6P full-gate PASS (sealed JSONs in gate-evidence).
- Ruff: clean (below).

## Explicitly NOT_RUN / UNKNOWN

- CI smoke-lane wiring (parked successor scope, not this WS).
- FULL107, promotion, Freeze, Provider, stale consumers, repin.

## Verdict

Lab 2–6P SUPPORTED | 7P+ FAIL_CLOSED | FULL107 NOT_RUN |
ARCHITECTURE_FREEZE NOT_CLAIMED | PRODUCTION_PROVIDER NOT_SELECTED.
