# WS226 PATH_OWNERSHIP_MATRIX — who owns what on the combined tree

Base ownership: WS223 (`48885e8e`) owns the living runtime/CI lane.
Sibling namespaces are owned by their workstream and transferred blob-exact.
Living overlapping source is owned by the semantic-reconciliation rule below.
Manifests are owned by WS226 terminal repair (no stale sibling wins).

## WS223 base (preserved exactly unless integration repair needed)

- Living runtime/CI (DO NOT OVERWRITE):
  - `src/commander_lab/engine/rules/full_game.py` (smoke + `_drive`/`_open_game`
    refactor + tuple-unpack fix; WS224 has no change here — verified empty
    delta `3cdade1d..f075ab75` for this path)
  - `src/commander_lab/semantic_replay/*` (10 files)
  - `scripts/run_external_full_game_conformance.py`,
    `scripts/verify_dependency_lock.py`, `scripts/write_environment_receipt.py`,
    `scripts/generate_lock_appendix.py`
  - `requirements/lock.in`, `requirements/lock.txt`,
    `requirements/LOCK_PROVENANCE.json`
  - `.github/workflows/*` (15 files), `docker/xmage/Dockerfile`,
    `docker/forge/Dockerfile`
  - `tests/unit/test_ws223_cardinality_regression.py`,
    `tests/unit/test_ws223_environment_identity.py`,
    `tests/unit/test_semantic_replay_tape.py`,
    `tests/unit/test_xmage_full_game_decision_matrix.py`,
    `tests/qualification/test_ws17r_exact_main_runtime.py`,
    `tests/unit/test_ws_a1d_docker_pin_authority.py` (WS223 delta version)
- Sealed evidence (historical, immutable):
  - `qualification/ws218-semantic-replay-tape-v1/*` (full namespace)
  - `qualification/ws223-ci-cardinality-environment-lock/*` (full namespace)

## WS220 provenance (new to base, blob-exact via WS221/WS222 ancestry)

- Owner WS220, carried by WS221 (`189dcfc0`) and WS222 (`1dcfe898`)
  identically (same `1a6ffcda` bytes; transfer once, verify once):
  - `research/project-audit/ws220/*` (24 files: FINDINGS, SUCCESSOR_PROPOSALS,
    ACTION_GRAPH, audits, SOURCE_TRUTH_MAP, probes/stale_source_scan.py, etc.)

## WS221 (living governance + namespace, applied onto base)

- Living source (base at `67db0733` bytes → take WS221 bytes exactly; base
  has NO competing change — verified `git diff 67db0733 48885e8e` empty
  for each path):
  - `qualification/evidence_vocab_v1.py` (NEW, controlled 7-term vocab)
  - `qualification/harness.py` (reject-not-coerce: unmapped class rejected,
    PASS-without-RUNTIME_VERIFIED demoted; removes PASS→RUNTIME_VERIFIED
    and any-PASS→RUNTIME_PASS coercions — must survive)
  - `qualification/evidence/candidate_result_v1.schema.json` (8-line vocab bind)
  - `qualification/evidence/normalized_evidence_v1.schema.json` (8-line vocab bind)
  - `qualification/evidence/evidence_legacy_map_v1.json` (NEW, 40-line
    explicit legacy mapping)
  - `docs/OPERATIONAL_SIMULATION_POLICY.md` (37-line 2-5P source-truth fix)
  - `docs/architecture/deckbuilding-simulation-separation.md`
  - `docs/architecture/xmage-full-game-external-pilots.md`
  - `src/commander_lab/robustness.py` (lane message text only)
  - `tests/qualification/test_ws221_evidence_vocab.py` (NEW, 14 tests)
  - `tests/unit/test_operational_4p_policy.py` (contract update)
- Sealed namespace (blob-exact):
  - `qualification/ws221-foundation-integrity-source-truth/*` (24 files:
    CONTROLLED_VOCAB_DESIGN, EVIDENCE_VOCAB_INVENTORY, HARNESS_STRICTNESS,
    LEGACY_MAPPING, MANIFEST_* (NEGATIVE/REPAIR/ROOT_CAUSE), P_SRC_01_RESULT,
    RED_GATE_REPRODUCTION, SOURCE_TRUTH_INVENTORY, VALIDATION, etc.)
- Manifests touched by WS221 (`WS17_SHA256SUMS`, `qualification/SHA256SUMS`):
  NOT taken as final (stale for WS218/WS223/WS222/WS224/WS225 additions).
  Repair logic (same-commit refresh invariant) is retained; bytes recomputed
  at WS226 terminal.

## WS225 (generated governance, new to base, blob-exact + recompute)

- Sealed namespace (blob-exact, historical inputs preserved):
  - `qualification/reporting/ws225/*` (37 files: SOURCE_LOCK,
    G_AF_MAPPING, EVIDENCE_JOIN_CONTRACT, CURRENT_STANDING_SCHEMA,
    standing_generator.py 587 lines, EVIDENCE_OVERRIDES, GATE_DIRECT_EVIDENCE,
    CANDIDATE_FACTS, XMAGE/FORGE/QUORUNE/ARGENTUM_STANDING, FREEZE_READINESS,
    OPEN_BLOCKERS, G01_STATUS (FAIL at WS225 lock), ADMISSION_ASSESSMENTS,
    CANDIDATE_ADMISSION_BAR, ADMISSION_STAGE_CONTRACT,
    HARNESS_PORTING_CHECKLIST, FAIR_COMPARISON_CONTRACT, INCUMBENCY_BIAS_TEST,
    WS219_ADMISSION_DRY_RUN, FIXTURE_EVIDENCE_TRACE 16029 lines,
    FULL107_ROLE, WS17_AGGREGATE_ADJUDICATION, POST_LOCK_DRIFT, VALIDATION,
    FINAL_HANDOFF, companions)
  - `qualification/aggregate/WS225_ROLLUP_STATUS.json` (additive rollup pointer)
- Tests (blob-exact, living regression):
  - `tests/qualification/test_ws225_standing.py` (26 tests: generator,
    regeneration, negatives, admission symmetry)
- Generated views (`*_STANDING.json`, `FREEZE_READINESS_VIEW.json`,
  `OPEN_BLOCKERS.json`, `G01_STATUS.json`, `ADMISSION_ASSESSMENTS.json`):
  HISTORICAL at WS225 lock (G01 FAIL, pre-WS222/WS223/WS224). Do NOT treat
  as current. WS226 recomputes fresh views in its own namespace; never
  hand-edits WS225 verdicts.
- S5 terminology: WS220 successor S5 (cardinality CI) ≠ WS225 admission
  Stage S5 (expensive full qualification admission). Generator's stage
  contract decides; do not conflate.

## WS222 (authority, new to base, blob-exact + living migration)

- Sealed namespace (blob-exact, 72 files):
  - `qualification/ws222-g01-authority-reacquisition/*` (AUTHORITY_LOCK_v2.json
    377 lines + REQUIREMENT_MATRIX + COORDINATOR_GATE + CR_OFFICIAL_SOURCE +
    CR_REPEATABILITY + CURRENT_G01_REPRODUCTION + G01_ADJUDICATION +
    IMPACT_ADJUDICATION + ORACLE_* (SCOPE/CORRESPONDENCE/IDENTITY/OFFICIAL_SOURCE) +
    RULINGS_ANALYSIS + SOURCE_LOCK + SUCCESSOR_AUTHORITY_LOCK + VALIDATION +
    artifacts/{cr,oracle,ban} + tooling/{acquire_cr,acquire_oracle,
    build_oracle_snapshot,capture_ban,verify_authority} + frozen29.names.json)
  - Scope: official byte-exact CR (`MagicCompRules_20260819.txt` 977822 B,
    sha `4381ad1b…27423f`), bounded official Gatherer Oracle (30 pages for
    frozen 29), Commander/B&R (42 bans, 0 hits in frozen29/RogShai87/Kaervek77),
    deck-legality evidence. Do NOT generalize to all Magic cards.
- Tests (blob-exact): `tests/qualification/test_ws222_authority.py` (5 tests)
- Living migration (WS226-owned, new bytes):
  - `qualification/manifests/AUTHORITY_LOCK_v2.json` (EXACT blob copy of the
    namespace lock; verification stays `--ns
    qualification/ws222-g01-authority-reacquisition --lock
    qualification/manifests/AUTHORITY_LOCK_v2.json`; v1 untouched)
  - Standing inputs: WS226 generator consumes v2 for xmage G01 PASS (scoped).
    `GATE_RESULTS.json` historical FAIL row preserved as provenance; living
    standing recomputes PASS from exact v2 trace (no silent promotion).
  - `REQUALIFICATION_REQUIRED` stays empty (integration changes no material
    semantics; WS222 impact adjudication lists zero required reruns).

## WS224 (privacy, new to base, blob-exact; production untouched)

- Living tests (NEW, no base conflict):
  - `engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameNameCanaryTest.java`
    (614 lines, 4 tests 2P–5P; supplements UUID oracle, never replaces)
  - `tests/unit/test_ws224_name_canary.py` (21 tests + 24 boundary)
- Sealed namespace (blob-exact, 33 files + driver):
  - `qualification/ws224-hidden-info-name-canary/*` (CANARY_2P/3P/4P/5P,
    CANARY_CONTRACT, surface/error/grant/historical/process/replay scans,
    LEAK_SURFACE_INVENTORY 223 lines, SOURCE_LOCK, SURFACE_SCANS,
    VALIDATION, runs/{BOUNDARY_4P,REPLAY_4P,ws224-tape-4p 1435 lines,
    HISTORICAL_*}, ws224_driver.py 510 lines)
  - Preserves: UUID oracle, name oracle, 2P–5P matrix, replay privacy,
    historical advisory (66 POTENTIAL_LEAK_ARTIFACT advisory, 0 CONFIRMED,
    0 rewrites). `ENGINE_INTERNAL_LOG_STATUS` stays UNKNOWN (no upgrade).
- `src/commander_lab/engine/rules/full_game.py`: NO WS224 change (verified).
  WS223 current bytes stand; no blind overwrite.

## WS226 (new integration namespace, WS226-owned)

- `qualification/ws226-consolidated-cpl-authority-integration/*` (this work):
  SOURCE_LOCK, LINEAGE_GRAPH, PATH_OWNERSHIP_MATRIX, OVERLAP_MATRIX,
  INTEGRATION_PLAN, INTEGRATED_SOURCE_INVENTORY, EVIDENCE_RETENTION_IMPACT,
  AUTHORITY_V2_INTEGRATION, HIDDEN_INFO_INTEGRATION, CI_ENVIRONMENT_INTEGRATION,
  REPLAY_INTEGRATION, MANIFEST_REPAIR, F_CI_02_VALIDATION, STANDING_RECOMPUTE
  (+ generator copy + fresh inputs/outputs), G_AF_CURRENT_VIEW, OPEN_BLOCKERS,
  POST_INTEGRATION_READINESS, VALIDATION, FINAL_HANDOFF (+ JSON companions).
- Standing recompute outputs live here (not in `ws225/`); WS225 views frozen.

## Manifests / generated / runtime taxonomy

- Living authority: `qualification/manifests/AUTHORITY_LOCK_v1.json`
  (historical, frozen) + `AUTHORITY_LOCK_v2.json` (new current, exact copy).
- Living contracts: `COMMON_FIXTURE_MANIFEST_v1.json` (authority_refs stay
  v1 — WS222 explicitly deferred fixture migration to S2 rollup; WS226 does
  not rewrite 135 rows), `GATE_RESULTS.json` (historical FAIL preserved;
  living G01 PASS recomputed in WS226 standing from v2 trace).
- Generated views: `ws225/*_STANDING.json` etc. (stale, frozen) vs
  `ws226/*_STANDING.json` etc. (current, recomputed deterministically).
- Manifests: `WS17_SHA256SUMS` + `qualification/SHA256SUMS` (repaired terminal;
  same-commit invariant maintained).
