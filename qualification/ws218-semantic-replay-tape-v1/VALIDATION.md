# WS218 VALIDATION

- Python impacted: `test_xmage_full_game.py` + `test_xmage_full_game_decision_matrix.py`
  (incl. new WS218 optional-neutral-target guard) + `test_semantic_replay_tape.py`
  (11) + `contract/test_phase85_protocol.py`: 46/46 PASS. `ruff check` clean
  on `src/commander_lab/semantic_replay` + tape tests.
- Broader `tests/unit`: not green lane-wide on this host for pre-existing
  environmental reasons (missing `openpyxl` import in unrelated tooling;
  WS215-class environmentals, none WS218-caused). No WS218 file depends on it.
- Java bridge: no Java changes in WS218; `mvn -o verify` (full-game/ws215/ws92
  filter) BUILD SUCCESS on the pinned engine.
- Fresh-process positives: 2P 611 / 3P 155 / 4P 257 / 5P 158 Lions tapes
  (seed 424242), each record-A + replay-B + replay-C all PASS (12 fresh JVMs).
  RNG post-start in all (196→784, 294→1176, 392→1568, 490→1960). Coverage:
  starting-player choose_object, mulligan + London-bottom targets, nontrivial
  targets, priority land/commander casts, mana pool+abilities, attackers/
  blockers + damage (2P life 34/13), command-zone choose_use, multi_amount
  numeric (2P ×5, turn 20), concessions + seat-mapped terminals (all).
- Tamper matrix: 19/19 fail closed with exact/allowed classes; diagnostics
  leak-free; no partial-mutation PASS.
- Hidden/process: tape scan 0 UUIDs + no hidden arrays; one-game-per-process
  refusal proven live; atomic writes + `.incomplete` discipline.
- Scans: no state/outcome injection patterns; consumer imports no
  pilot/policy (no second engine); bridge `replay_supported` still false.
- WS220 consumed read-only (`1a6ffcda...`); R1–R12 all PASS; R10 raw pinned
  non-normative; provider-neutrality proven (Forge sketch, no integration).
- Out of scope retained: S1/S3/S4/S5/S11, numeric-narrowing remediation,
  honeycard work, FULL107 (NOT_RUN), APNAP/extra-turn/damage thresholds +
  partner tax/damage UNKNOWNs (unchanged), 6P NOT_SUPPORTED (unchanged).

Classifications: positives/tampers/RNG/hidden/concession = RUNTIME_VERIFIED
(fresh JVM); contracts/schemas = CODE_DERIVED + unit/runtime pins; WS220
mapping = CODE_DERIVED from committed audit objects; unknowns = UNKNOWN.

Machine companion: `VALIDATION.json`.
