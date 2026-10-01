# Validation record — mid-game multiselect/amount closure

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

## Local code validation (worktree `bb59fe47`)

| Command | Result | Classification |
|---|---|---|
| `python3 -m pytest -q tests/qualification/test_current_boundary_midgame_rows.py` | 87 passed | `DIRECTLY_VERIFIED` |
| `python3 -m pytest -q tests/qualification` | 824 passed, 13 skipped | `DIRECTLY_VERIFIED` |
| `python3 -m pytest tests -m "not external" -q` | 3010 passed, 15 skipped, 2 deselected | `DIRECTLY_VERIFIED` |
| `python3 -m ruff check` + `ruff format --check` on modified files | clean | `DIRECTLY_VERIFIED` |
| `mypy 1.20.2` strict on `midgame_rows.py` | no errors in the modified module | `DIRECTLY_VERIFIED` |
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

## Authoritative at-pin execution

The PR's PB-03 workflow run is the authoritative execution: it builds the pinned
XMage candidate, runs the mid-game probe and the two-candidate current-boundary
runner, assembles the evidence, asserts the R-4 receipt invariants, and uploads
the source-bound epoch artifact. Its results and digests are recorded in the
terminal handoff once green.
