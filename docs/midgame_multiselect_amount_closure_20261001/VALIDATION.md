# Validation record — mid-game multiselect/amount closure

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

## Local code validation

| Command | Result | Classification |
|---|---|---|
| `python3 -m pytest -q tests/qualification/test_current_boundary_midgame_rows.py` | 87 passed | `DIRECTLY_VERIFIED` |
| `python3 -m pytest -q tests/qualification` (`bb59fe47`) | 824 passed, 13 skipped | `DIRECTLY_VERIFIED` |
| `python3 -m pytest tests -m "not external" -q` (`bb59fe47`) | 3010 passed, 15 skipped, 2 deselected | `DIRECTLY_VERIFIED` |
| `python3 -m pytest tests -m "not external" -q` (merged `840f9313`, includes AF05 #451) | 3042 passed, 15 skipped, 2 deselected | `DIRECTLY_VERIFIED` |
| `python3 -m pytest -q tests/qualification/test_current_boundary_midgame_rows.py tests/qualification/test_pre_freeze_contract_successor.py` (merged) | 107 passed | `DIRECTLY_VERIFIED` |
| `python3 -m ruff check` + `ruff format --check` on modified files | clean | `DIRECTLY_VERIFIED` |
| `mypy 1.20.2` strict on `midgame_rows.py` | no errors in the modified module (pre- and post-merge) | `DIRECTLY_VERIFIED` |
| `mvn -o test -Dtest=XmageFullGameActionProjectionTest,XmageFullGameGenericActionSubmissionTest,XmageDecisionRejectionWs229Test,XmageFullGameDecisionExecutionTest` | 39 passed | `DIRECTLY_VERIFIED` |
| `mvn -o test -Dtest=XmageMidgameLaneTest,XmageFullGameHexOfferTest` | 16 passed | `DIRECTLY_VERIFIED` |

The Java bridge source was not modified by this workstream; the Java suites are
run because the projection/decision controller is the surface that consumes the
new multi-select submission vector.

## Local full current-boundary runner and assembler (development, NON-CREDIT)

A local run of `scripts/run_current_boundary_qualification.py --candidate xmage`
followed by `scripts/assemble_current_boundary_evidence.py` on `577390fb`:

- `MIDGAME_ROW_EXECUTIONS.json`: 22/22 rows verified (the 19 prior rows plus the
  three new rows).
- `FULL107_XMAGE_RESULTS.json`: the three rows `PASS`,
  `evidence_class = FRESH_CURRENT_BOUNDARY_RUNTIME`,
  `execution_mode = MIDGAME_LANE_PLACEMENT_OBLIGATION`, each with its
  `midgame-lane:placement-obligation#<fixture>` receipt identity; xmage PASS
  count 24 -> 27.
- Local run fingerprint: runner digest `097484f2…`, engine artifact
  `e04062d2…` (the machine-local artifact predates the canonical pin, whose CI
  artifact digest is `bdaefe49…`).

Classification: `MODELED`. The local epoch was moved out of the worktree and is
deliberately not committed; at-pin credit comes only from the PB-03 CI epoch.

## Main drift and requalification

Two AF05 merges landed while this workstream was in flight:

1. PR #451 merged to main as `bcd903f2` (contract 1.0.8). This branch merged
   main as `497743d6` (clean, no file overlap) and re-ran all local validation
   on the merged head (`840f9313`): full suite 3042 passed, focused 107 passed,
   the three rows verify locally.
2. PR #452 (AF05 M2, HIDDEN_07/HIDDEN_08) merged to main as `a9159084`
   (contract 1.0.9) after the first post-drift PB-03 run was green on merge ref
   `00cad320`. This branch merged main as `9ca93860`.

Impact adjudication of the second drift:

- The successor contract 1.0.9 adds only `HIDDEN_07`/`HIDDEN_08`.
- `MICRO_COSTS`, `PILOT_TARGET_AMOUNT` and `PILOT_MULTI_AMOUNT` have byte-equal
  replace payloads, equal successor requested-state digests and equal correction
  classes in 1.0.8 and 1.0.9; their effective requested-state and obligation
  digests under 1.0.9 are exactly the ones the pre-drift CI epoch reported.
- The drift did not touch `midgame_rows.py`, the probe script, `midgame_lane.py`,
  the runner, the assembler, `receipts.py` or `materialization.py`. It did change
  `source_lock.py` and `knowledge_projection.py`, which are runner-digest inputs,
  so the pre-drift epoch's receipts are not current on the new source by the
  project's own freshness rule.

Classification: `REQUALIFICATION_REQUIRED` (source identity changed); row
semantics unaffected (row-level impact: none). The pre-drift epoch
(`00cad32010ca-1e5764089ab5`) is preserved as provenance outside the worktree
and is not committed. The authoritative evidence for the merged result is a
fresh PB-03 epoch on the post-1.0.9 merge ref.

## Authoritative at-pin execution

The PR's PB-03 workflow run is the authoritative execution: it builds the pinned
XMage candidate, runs the mid-game probe and the two-candidate current-boundary
runner, assembles the evidence, asserts the R-4 receipt invariants, and uploads
the source-bound epoch artifact. Its results and digests are recorded in the
terminal handoff once green.
