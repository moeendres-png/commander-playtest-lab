# WS215 COMMON_FIXTURE_DISPOSITION — 135/135 terminal

Denominator derived from the committed manifest
(`COMMON_FIXTURE_MANIFEST_v1.json`, sha256 `e7f34ea4…ca3bd4`): **135
fixtures** — player_count 4, multiplayer_commander 36, actual_card 29,
hidden_information 20, pilot_boundary 17, micro_rules 17,
pilot_boundary_negative 7, replay_rng 5.

| Disposition | Count | Meaning |
|-------------|-------|---------|
| `RERUN_REQUIRED` (rerun, PASS) | 72 | 24 WS215-scope fresh runtime PASS + 48 suite-rerun PASS (17 pilot_boundary + 7 negatives + 20 hidden_information + 4 mana/target-adjacent micro) |
| `RETAINED_AFTER_IMPACT_ADJUDICATION` | 47 | 29 actual_card + 13 micro_rules (engine-owned) + 5 replay_rng; rationales in JSON rows |
| `BLOCKED` | 0 | — |
| `UNKNOWN` | 16 | Fresh unknowns with exact causes (APNAP ×2, extra-turn ×2, CR800.4-control ×1, exile/hand/library zone ×6, commander-damage thresholds ×3, partner tax/damage ×2) |

Retained rationales (no silent grandfathering):

- actual_card (29): engine pin unchanged; card implementations untouched;
  caveat — the target-tiebreak determinism repair (TD01) may alter
  exact-score tie selections vs WS213-era runs; no card-behavior
  regression observed in bounded windows; zero behavior credit claimed;
  full behavior requalification belongs to a behavior successor
  (FULL107 remains NOT_RUN).
- micro_rules engine-semantic 13 (stack/triggers/modes/replacement/
  prevention/continuous/layers/SBA/...): engine-owned semantics with
  byte-identical Lab paths; mana/target-adjacent siblings
  (COSTS/MANA_PAYMENT/PRIORITY/TARGETS) freshly rerun.
- replay_rng 5: Replay v1 out of scope for WS215; PARTIAL retained with
  impact adjudication; injection ban preserved (see
  `SEMANTIC_REPLAY_IMPACT.md`).

Per-fixture rows: `COMMON_FIXTURE_DISPOSITION.json`.

Machine companion: same JSON (this file's table is the summary).
