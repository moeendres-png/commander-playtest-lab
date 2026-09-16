# WS232 VALIDATION (terminal runs on the sealed tree)

## Python unit (DIRECTLY_VERIFIED; `pytest -B -q -p no:randomly`)

- `tests/unit`: 771 passed. 5 failed + 40 collection errors, ALL
  pre-existing environment gaps, each classified: missing `openpyxl` /
  `fastapi` modules (import chains through `importers/google_drive.py`
  and service adapters) and subprocess `PYTHONPATH` for structural
  profiles (`ModuleNotFoundError: commander_lab` in the child). Zero
  touch WS232 surfaces (WS232 adds no `src/**` or `tests/unit/**`
  file). Same gap family as the WS229 terminal record.
- `tests/qualification`: 66/66 PASS (12 WS17 incl. manifest coverage,
  vocab, standing, authority, runtime, + 6 WS232 retention-predicate
  tests).

## JVM (DIRECTLY_VERIFIED; `mvn -o -pl . test`, offline lane)

- `XmageNumericDomainWs229Test` 12/12, `XmageDecisionRejectionWs229Test`
  16/16, `XmageVariablePlayerLifecycleTest` 12/12: 40/40 PASS,
  BUILD SUCCESS. No production change in WS232; the lane is confirmed
  intact underneath 1457 fresh-process evidence games.

## Runtime evidence (DIRECTLY_VERIFIED)

- 1457 indexed run records (`RUNTIME_RUN_INDEX.json`), every certified
  game one fresh OS process / fresh JVM (bridge-enforced
  one-game-per-process).
- Actual-card 29: 79 PASS / 8 UNKNOWN (per-cell attempts + causes in
  `ACTUAL_CARD_29_MATRIX.json`; uniform consume-level adjudication
  `WS232-ADJ-CARD-CONSUME-LEVEL-1.0.0` with provenance).
- Micro-rules 13: 27 PASS / 12 UNKNOWN (`MICRO_RULE_13_MATRIX.json`).
- Replay/RNG 5: 15 PASS / 0 UNKNOWN (record + dual replay per N;
  `REPLAY_RNG_5_MATRIX.json`).
- N-scoped disposition: 141 cells = 121 PASS / 20 UNKNOWN, prose-only
  retention mechanically rejected (`seal_disposition.py`).
- U5: amount (Damnations exact-X resolution), multi_amount (Gearhulk
  single-frame `[4]`), target_amount (Arc divide + companion),
  numeric-bearing replay (Arc tape 502 steps, dual PASS), 5P impact GREEN.
- Predicates: 47/47 STATIC_PASS + behavior discharge joined per N cell.
- Privacy: namespace scan 0 findings (no UUIDs/hands/libraries/labels/
  prompts/metadata).
- Standing: generator re-executed, outputs identical (NO_CHANGE).
- Manifest integrity: GREEN (hash suites 12/12).
- `ruff check` on all WS232 Python files + predicate tests: clean.

## Deliberately NOT run (scope compliance)

- FULL107: NOT_RUN. Blanket 135-fixture campaign: not run (S8 scope is
  retained-47 N-scoped + impacted U5).
- 4P gate: not rerun (no 4P-specific risk identified; repaired paths are
  count-free; 4P decision-mode evidence inherited).
- S9 trigger-rich closures (16 UNKNOWNs preserved, not targeted).
- Privacy canaries: not rerun (no touched projection path).
- No Architecture Freeze / Production Provider claim.
