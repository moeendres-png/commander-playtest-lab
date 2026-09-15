# WS220 Validation Record

## Direct runtime evidence (this workstream)

- `pytest tests/qualification/test_ws17_qualification.py` on HEAD 67db0733:
  **11 passed, 1 failed** (`test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts`;
  WS17_SHA256SUMS vs test_ws207_seed_binding.py; 0.55s). Classification:
  DIRECTLY_VERIFIED. Supports F-CI-02.
- `probes/stale_source_scan.py` (P-SRC-01) full-tree runs ×3 (pre/post
  refinement): 102 name traps, 13 four_p files, live/provenance pin split,
  11 aggregate-citing files. Deterministic, rerunnable. Supports F-SRC-01,
  F-EVID-01 scope note.
- `COMMON_FIXTURE_DISPOSITION.json` machine reads: 135 rows; 72/47/16
  verified; retained composition 29/13/5 verified. Supports B8/C6.
- `git diff 592f23c9..67db0733` Lab-path analysis (hunks 306/489/514/613/829/
  861/1104 + Java cardinality): behavioral changes confined to rerun classes
  + N≠4 inputs. Supports F-EVID-04a/b. Classification: CODE_DERIVED
  (static) — no runtime claim made from it.
- Backlog JSON validity + findings-field completeness: script-checked
  (25 findings, all required fields; 25 hypotheses valid JSON).

## Code-derived / static (no runtime)

- Orientation surveys (3 parallel), batch-1/2 subagent reports (6 total):
  treated as CODE_DERIVED inputs; every material claim re-verified by the
  auditor (probe, read, diff, or test) before promotion to findings.
- Java controller/projection/redactor/player reads; pilot RNG grep; redactor
  field analysis; replay-contract analysis (R1–R12). Static → findings marked
  confidence high only where code is dispositive (membership checks,
  fail-closed branches); NEEDS-RUNTIME items marked as gaps, not verdicts.

## Explicitly NOT run (with reason)

- Full pytest suite: decision value negative (one file answered the
  integrity question; seals fresh; tree unchanged since base).
- Maven/XMage builds, JVM matrices, FULL107: no uncertainty they would
  remove that static evidence + fresh seals don't already answer; cost
  unjustified per impact-first strategy. FULL107 additionally retired.
- WS218/WS219 surfaces: out of scope (ownership).

## Verdicts claimed

- 25 findings (11 P1 / 11 P2 / 3 P3; 0 P0) + 8 rejected/refined hypotheses.
- No ARCHITECTURE_FREEZE, no PRODUCTION_PROVIDER, no production/
  qualification-authority mutation, no pin change, no raw push (safe_push
  only, dry-run first).
- Missing evidence stays UNKNOWN: resumption reliability, engine-internal
  logs, historical artifact contents, Forge-side behavior, third-candidate
  bar effects — all labeled UNKNOWN/GAP, none upgraded.

## Terminal fields

- PRODUCTION_CODE_MODIFIED: NO
- QUALIFICATION_AUTHORITY_MODIFIED: NO
- ENGINE_PIN_MODIFIED: NO
- RAW_GIT_PUSH_USED: NO (safe_push.py only)
- ARCHITECTURE_FREEZE: NOT_CLAIMED
- PRODUCTION_PROVIDER: NOT_SELECTED
