# WS229 VALIDATION (terminal runs on the sealed tree)

## Python (DIRECTLY_VERIFIED; `pytest -q -p no:randomly`)

- NEW `tests/unit/test_ws229_numeric_domain.py`: 55/55 PASS
  (scalar descriptor small/large/boundary/huge, joint valid + 5
  violation families + malformed/empty domains, Base raise ×2, hostile
  max+1/non-integer, mulligan cap, priority mana/lone-pass, pool
  single/multi/liveness, bottom flag ±, N-10, unoffered forging, tape
  vector validators, digest stability/binding, recorder capture ±/malformed).
- Impact sweep (matrix, full_game, pilots, variable_player, replay tape,
  ws224 canary, ws17 qualification, ws221 vocab, ws225 standing, ws222
  authority): 220/220 PASS terminal.
- Full `tests/unit`: 771 passed; remaining failures/errors are
  pre-existing environment gaps ONLY (missing `openpyxl`/`fastapi`
  modules; subprocess PYTHONPATH for structural profiles) — each
  classified in STANDING evidence; zero touch WS229 surfaces.
- Qualification: `test_ws17_qualification` 12/12; `test_ws221_evidence_vocab`
  manifest rows PASS; `test_ws225_standing` + `test_ws222_authority` PASS.
- `ruff check` on all touched Python files: clean (mypy unavailable in
  this environment — recorded, not claimed).

## JVM (DIRECTLY_VERIFIED; `mvn -o -pl . test`, offline lane)

- NEW `XmageNumericDomainWs229Test`: 12/12 (announce/amount live-callback
  small+span>16, joint live with binding total + single-frame proof,
  forged scalar/joint live rejections + lawful settle, N-22 transport +
  projection, joint projection violations, forced-move transcript,
  reversed bounds, malformed scalars, target_amount blocker pin).
- NEW `XmageDecisionRejectionWs229Test`: 16/16 (N-01..N-06, N-09 live,
  N-11..N-13, N-17..N-21, N-07/N-08 live variants).
- Updated `XmageFullGameCombatDamageTest` 4/4 (joint),
  `XmageFullGamePlayerBoundaryTest` 4/4, `XmageFullGameActionProjectionTest`
  17/17 (unchanged rows green).
- FULL bridge suite incl live-game suites (VariablePlayerLifecycle 12,
  HiddenInformation, NameCanary 4, ConcedeAction 5, Ws204 census,
  ExternalDecision, RulesSeedBinding, CastChoice, GenericActionSubmission):
  153/153 PASS, BUILD SUCCESS (terminal).

## Live end-to-end (DIRECTLY_VERIFIED)

- 2P bounded smoke (Isamaru/Plains, 25 decisions): PASS.
- 3P bounded smoke (25 decisions): PASS.
- 6P: FAIL_CLOSED pre-launch.
- Card-driven Blaze fire: announce_x [0, 2^31-1] chosen + consumed;
  post-cancel activation failure reproduced IDENTICALLY on base
  (pre-existing dynamics, stash experiment).

## Deliberately NOT run (scope compliance)

- FULL107: NOT_RUN. 135-fixture campaign: not run (S8 scope).
- 4P full-game gate + 5P smoke: not rerun (cost; impact-selected
  regression suffices — see CARDINALITY_IMPACT.md).
- WS218 dual-replay numeric positives: no numeric-bearing recorded
  scenario exists yet (scalar digest stability keeps existing positives
  green by construction).
- Card-driven target_amount/amount/multi_amount fires: UNKNOWN with
  blockers (U5 scenario-engineering scope).
