# WS226 STANDING_RECOMPUTE — deterministic recompute on the combined tree

Generator: `qualification/ws226-consolidated-cpl-authority-integration/standing_generator.py`
(WS225 logic reused; path-constant-only diff verified: 22 insertions, 20 deletions,
no verdict-logic change; `ROOT parents[3]→[2]` depth fix + `ws226-*` schema versions).

Inputs (in this namespace):
- `EVIDENCE_JOIN_CONTRACT.json` (exact WS225 copy)
- `EVIDENCE_OVERRIDES.json` (exact WS225 copy; 119 XMage PASS rows retained via
  `WS225_RETAIN_XMAGE_WS215` predicate; no row hand-flipped; BEHAVIOR_CREDIT 0)
- `CANDIDATE_FACTS.json` (exact WS225 copy; xmage engine pin `db134b97` unchanged,
  replay true, 29/29 frozen, 17/17 micro)
- `GATE_DIRECT_EVIDENCE.json` (exact WS225 copy EXCEPT xmage G01 FAIL→PASS scoped
  with v2 provenance + all G00 provenance updated to WS226 SOURCE_LOCK;
  forge/quorune/argentum G01 preserved FAIL fail-closed — see below)
- `G_AF_MAPPING.json`, `CURRENT_STANDING_SCHEMA.json`, `ADMISSION_STAGE_CONTRACT.json`,
  `CANDIDATE_ADMISSION_BAR.json`, `FAIR_COMPARISON_CONTRACT.json`,
  `HARNESS_PORTING_CHECKLIST.json` (exact copies; S5-cardinality ≠ S5-admission noted)

Outputs (in this namespace, deterministic):
`FIXTURE_EVIDENCE_TRACE.json` (652 rows), `XMAGE/FORGE/QUORUNE/ARGENTUM_STANDING.json`,
`FREEZE_READINESS_VIEW.json`, `OPEN_BLOCKERS.json`, `G01_STATUS.json`,
`ADMISSION_ASSESSMENTS.json`, `WS219_ADMISSION_DRY_RUN.json`,
`INCUMBENCY_BIAS_TEST.json`, `VALIDATION.json`.

Determinism proof (DIRECTLY_VERIFIED):
- Run 1 (in-namespace): outputs digest `5bc1a02dac066f3fcf33ddd4e6923e537c2f8b5360bd823102deaca563f438d4`
- Run 2 (`/tmp/opencode/ws226_second`): same digest `5bc1a02d…` MATCH
- `VALIDATION.json` records `generator_digest` + `outputs_digest` + `row_count 652`.

## XMage current adjudication (from exact traces)

- G01 PASS (scoped): byte-exact CR 4381ad1b + 30-page bounded Oracle + 42 bans
  (0 hits) + deck legality, offline `verify_authority.py` PASS. Scope: frozen 29
  denominator only; no bulk-oracle generalization.
- G02 PASS (cardinality 2–5P lifecycles; WS223 smoke + WS215 seals)
- G07 PASS (hidden-info sentinel + WS224 name canary hardening note)
- G09 PASS (replay/RNG tape lane; WS218 2–5P dual-replay + tamper matrix)
- G10 UNKNOWN (16 WS05 UNKNOWNs preserved: APNAP, extra-turn, CR800.4, damage,
  Partner, zones)
- G11 PASS (clean runtime record; matrix + twins clean)
- G13 FAIL (computed: not all G00–G12 PASS; G10/G12 block)
- AF01 UNKNOWN (no RSP 1.1 handshake runtime)
- AF02 PASS (technical cardinality)
- AF05 PASS (hidden-info; F-HIDE-02 as improvement note)
- AF07 PASS (caveat TD01 tiebreak, non-demoting)
- AF08 UNKNOWN (blocked, G10-linked)
- AF09 PASS (WS218 tape lane 2P–5P)
- AF10 PASS (clean runs + accounting + integrity)
- AF11 UNKNOWN (production topology unselected)
- Admission: FAIL (G13 FAIL); freeze_eligible false (all candidates).

## Other candidates (preserved)

- Forge: G01 FAIL (fail-closed; no candidate-specific deck-legality runs at Forge pin),
  AF00 PASS, AF04 FAIL (preserved whole-boundary violation), AF03/AF10/AF11 UNKNOWN,
  admission FAIL, DO_NOT_PROMOTE (S1 terminal). No privilege, same bar.
- Quorune: G01 FAIL (same fail-closed), AF00 PASS, fixtures NOT_RUN,
  DO_NOT_PROMOTE (S3 terminal 0/29). Matches WS219 seal.
- Argentum: G01 FAIL, AF00 PASS, NOT_RUN, DO_NOT_PROMOTE (S3 terminal 5/29 + Partner/OVERLOAD).
- WS219 dry run: both `DO_NOT_PROMOTE_CURRENT_PIN`, match true.
- Incumbency bias: `NO_INCUMBENCY_BIAS_DETECTED` (same code path; XMage S5-pending,
  not admitted; Forge S1-terminal).

Decision persisted: only XMage G01 flips (exact v2 trace with Lab-deck legality);
forge/quorune/argentum G01 stay FAIL fail-closed (no silent promotion; dispositions
preserved exactly). S5-cardinality (WS220 successor, CI) ≠ S5-admission (expensive
campaign); generator's stage contract decides (XMage S5-pending).
