# Validation — successor integration on base aebcfda3

## Identity / hygiene

- Branch `cpl/xmage-successor-integration-20260919`, base `aebcfda3`
  (clean at creation); donor `fa4cd8d1` read-only; engine pin
  `xmage-1.4.61` unchanged (Maven artifact identical both sides).
- No other workstream's branch/worktree modified (verified via
  `git status` in donor worktrees: clean before and after).
- Donor prod/test files ported byte-exact (retention static gate
  re-verifies SHAs); formatting retained as-is (`ruff check` clean;
  `ruff format` deltas accepted as donor style to preserve byte-fidelity).

## DIRECTLY_VERIFIED (re-ran on new base)

- Bridge full suite offline: **153/153 PASS** (62 pre-existing + 91
  ported), BUILD SUCCESS. Fail-before: 6 NoSuchFile (Lions fixture) →
  repaired by porting the technical-deck input; re-run green.
- Python collectible unit suite: **756 passed**; residual = 15 parked
  CI-wiring (ws223×14 + compat-workflow, fixed 1 via pin coherence) + 5
  proven-pre-existing-environmental (openpyxl; reran identically red on
  pristine aebcfda3). 34 modules uncollectible (31 openpyxl-chain +
  fastapi + hypothesis + 1 more) — pre-existing environmental class.
- Retention static gate 6/6 (47 predicates incl. byte-SHAs of ported
  Session/Provider/JsonlBridge/full_game + authority-lock content hash
  319e6921… verified on fetch).
- LIVE full gates (dual complete games → natural terminal, same-seed
  semantic replay comparison), new base, Isamaru technical decks:

| count | decisions | winner | semantic MATCH | raw MATCH | status |
|---|---|---|---|---|---|
| 2P | 12253 | seat 1 | true | false (process IDs) | PASS |
| 3P | 2071 | seat 1 | true | false | PASS |
| 4P | 4476 | seat 3 | true | false | PASS |
| 5P | 5953 | seat 2 | true | false | PASS |

  8 decision classes exercised per game (choose_object, choose_use,
  declare_attacker, declare_blocker, mana_payment, mulligan, priority,
  target); evidence_class technical_conformance_only; no private-state
  leakage (gate-enforced). Gate JSONs sealed in
  `docs/workstream_successor_integration_20260919/gate-evidence/`.
- Fail-before: 3P under 3-parallel JVM load failed at deck import
  (`XMAGE_CARD_REPOSITORY_INIT_FAILED` — card-DB bootstrap contention,
  infrastructure class WS215 already noted); reran solo → PASS. Sealed as
  `gate-3p-parallel-contention-failbefore.log`.

## Explicitly NOT_RUN / parked

- Dual-run replay beyond the 4-gate matrix, FULL107, 6P (fail-closed),
  APNAP extras, CI smoke-lane wiring (follow-up), hypothesis module
  (environmental), governance tests (never ported by design).
- No EXTERNALLY_RULE_VALIDATED claims; nothing MODELED/SYNTHETIC.

## Verdict

PORT = COMPLETE (prod 31 + tests 35 + fixtures 14 + 2 workflow lines) |
REQUAL = PASS (bridge 153/153, python 756, live 2/3/4/5P gates PASS,
replay MATCH ×4) | FULL107 = NOT_RUN |
ARCHITECTURE_FREEZE = NOT_CLAIMED | PRODUCTION_PROVIDER = NOT_SELECTED.
