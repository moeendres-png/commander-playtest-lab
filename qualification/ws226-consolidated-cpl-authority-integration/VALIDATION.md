# WS226 VALIDATION — impact-selected validation (terminal record)

## Scope (no blind 135-rerun; full_game.py untouched → WS223 seals stand)

1. `tests/qualification/test_ws221_evidence_vocab.py` — vocab + harness
   reject-not-coerce negatives + manifest coverage/mismatch.
2. `tests/qualification/test_ws222_authority.py` + `tooling/verify_authority.py`
   offline with living `manifests/AUTHORITY_LOCK_v2.json` — v2 current.
3. `tests/qualification/test_ws17_qualification.py` (full file, incl. F-CI-02).
4. `tests/unit/test_ws223_environment_identity.py` + `test_ws223_cardinality_regression.py`.
5. `tests/unit/test_semantic_replay_tape.py` (WS218 guards).
6. `tests/unit/test_ws224_name_canary.py` (21 Python canaries).
7. `tests/qualification/test_ws225_standing.py` (26 frozen-view tests).
8. WS226 generator determinism (2 runs, digest `5bc1a02d…` MATCH) + 
   `test_ws17r_exact_main_runtime.py` + `test_operational_4p_policy.py`.
9. Java: `XmageFullGameNameCanaryTest` + `XmageFullGameHiddenInformationTest`
   via Maven ONLY if tree context changed (else NOT_RUN with reason; JVM absent
   in this container → record explicitly).
10. 2P/3P/4P/5P bounded smoke + 6P fail-closed where impact requires (rely on
    WS223 seals + cardinality regression; no 135-fixture rerun without impact reason).

## Results (terminal, DIRECTLY_VERIFIED on the combined tree)

- `tests/qualification/test_ws17_qualification.py` (full file, 12 tests): 12/12 PASS,
  incl. `test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts` (F-CI-02 GREEN).
- `tests/qualification/test_ws221_evidence_vocab.py`: 14/14 PASS (vocab discipline,
  harness rejection x5, admission blocking, legacy mapping, schema accept/reject,
  manifest coverage + mismatch negative). Pre-repair 13/14 (manifest RED, expected);
  post-repair 14/14.
- `tests/qualification/test_ws222_authority.py`: 5/5 PASS (offline) +
  `tooling/verify_authority.py --ns qualification/ws222-g01-authority-reacquisition
  --lock qualification/manifests/AUTHORITY_LOCK_v2.json` → PASS (CR 4381ad1b + 30 pins).
- `tests/qualification/test_ws225_standing.py`: 26/26 PASS (frozen WS225 views intact).
- `tests/qualification/test_ws17r_exact_main_runtime.py`: 3/3 PASS.
- `tests/unit/test_ws224_name_canary.py`: 21/21 PASS.
- `tests/unit/test_operational_4p_policy.py`: 7/7 PASS.
- `tests/unit/test_semantic_replay_tape.py`: 11/11 PASS (WS218 guards).
- `tests/unit/test_ws223_cardinality_regression.py`: 32/32 PASS (2–5P smoke + 6P fail-closed).
- `tests/unit/test_ws223_environment_identity.py`: 11/11 PASS.
- WS226 generator determinism: 2 independent runs, outputs digest
  `5bc1a02dac066f3fcf33ddd4e6923e537c2f8b5360bd823102deaca563f438d4` MATCH;
  `VALIDATION.json` row_count 652.
- `ruff check` on vocab/harness/tooling/generator/tests: clean.
- Negative control: single-byte tamper of `SOURCE_LOCK.json` → F-CI-02 FAIL (gate bites);
  restore → PASS.
- Java: `XmageFullGameNameCanaryTest` (4/4 at WS224 lock) + `XmageFullGameHiddenInformationTest`
  (1/1) NOT re-executed in WS226 (Maven/JVM absent in this container; production Java
  unchanged from WS224 base `3cdade1d`; new canary file blob-exact from PASS seal;
  Python canary 21/21 + UUID oracle preserved). Recorded as NOT_RUN (impact: none).
- 135-fixture behavior rerun: NOT performed (no impact reason; full_game.py untouched;
  WS222/WS224 impact adjudications list zero required reruns; BEHAVIOR_CREDIT 0).
- Classifications: standings CODE_DERIVED views over RUNTIME_VERIFIED /
  DIRECTLY_VERIFIED / SOURCE_DERIVED sealed inputs; no new runtime; credit 0.

Machine companion: `VALIDATION.json`.
