# MIDGAME_LANE_MULTISELECT_AMOUNT_CLOSURE_FINAL_HANDOFF_20261001

Workstream `MIDGAME-LANE-MULTISELECT-AMOUNT-CLOSURE-20261001` (issue #449; parent #255,
Coordinator sequencing comment 5931735894; ownership reservation comment 5931753920).

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

## Source Lock

| Role | Identity |
|---|---|
| Audit base main | `4e41bde6fd4f27dc448ae8c44f7af9212e3198fe`, tree `09e139d4bebfd3cb960b692c66297ab9385674df` |
| Owned branch | `hardening/midgame-multiselect-amount-closure-20261001` |
| Sealed branch head | ``f76c6cefebe65952d654424c4e59152252cdf2fa` (CI-validated code head; this evidence seal adds only the epoch, hash manifests, docs and state)`, tree ``609b3126…` (the seal commit tree; the CI identity below names the pre-seal merge ref)` |
| XMage candidate | `37e4df6c914f1e189e24f0ef59fa91734c922436` |
| Forge Rules-Core / bridge | `bb0a740d2bef725194798383c2452213ecdd0b37` / `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c` |
| Effective contract at run time | `commander-lab.full107/1.0.7-successor` |
| PB-03 CI run | ``36916800598` (PB-03 Current Boundary Runtime Qualification, conclusion success)` on merge ref ``1710cac9d2ebbfc4a0f736832b1c05fb029f78dd` (tree `210d2adeeac11e0a6bc8a32b4da99eb0c0a450e1`)` |
| Evidence epoch (authoritative, post-conflict head) | `qualification/current-boundary-epochs/b2e2ca316049-57f121f50e27/` (PB-03 run `36924534689` on merge ref `b2e2ca3160492db5e22d7c1cebe9b5679af82030`, 81/81 digests verified) |
| Earlier source-bound epoch (provenance) | `qualification/current-boundary-epochs/1710cac9d2eb-210d2adeeac1/` (PB-03 run `36916800598` on merge ref `1710cac9…`, 80/80 digests verified) |

## Terminal Main Lock

`recorded in the #449 terminal comment after the normal merge` (tree `recorded in the #449 terminal comment after the normal merge`), verified after the merge.

## Work Completed

1. **Fresh census and drift** — origin/main verified at the audit base before the
   first edit, before each push and before the merge; no unrelated drift. A
   concurrent AF05 workstream (PR #451) was checked for ownership overlap: its
   changed files do not intersect this workstream's write surface, and the
   sequencing gate is monitored for main drift.
2. **Forensic reproduction** — the actual engine frames for all three fixtures
   were reproduced on the production lane before any edit; fail-before proof:
   the three rows stopped at the missing `semantic_objects` /
   `amount_assignment` selector dispatch with EXACT construction.
3. **Selectors** — generic `semantic_objects` (multi-select targets) and
   `amount_assignment` (divided damage) selectors, plus the
   `amount_assignment:` and `cost_determined:` verifiers and two assignment
   terminal checks.
4. **Rows registered** — `MICRO_COSTS`, `PILOT_TARGET_AMOUNT`,
   `PILOT_MULTI_AMOUNT` with their record-bound mana sources and cost
   obligations.
5. **Controls** — unit fail-closed controls for every selector/verifier
   rejection class and live wrong-reason controls on the production executor.
6. **Validation and evidence** — focused and full suites, ruff, strict mypy,
   impacted Java suites, a local runner+assembler dry run (`MODELED`,
   non-credit; its epoch was discarded), and the authoritative PB-03 CI epoch.
7. **Independent review** — fresh-context read-only review, PASS with no
   P1/P2; P3 advisories repaired.
8. **Integration** — Draft PR #450 with source lock, fail-before, tests,
   runtime evidence and explicit no-provider/no-freeze state.

## New Findings

- Magma Opus divided damage is one `target_amount` frame per leg, and each
  frame carries the target and its share together; the record's
  `amount_assignment` is the assignment leg, not a separate post-target frame.
- The two Magma Opus records stop at the assignment obligation: the engine then
  asks for the spell's tap targets, which the records do not script; the lane
  must not invent them and the obligation is already observed.
- The Hex multi-select frame is the engine's true min-6/max-6 `target` frame;
  the record's `semantic_objects` list is submitted as one vector.
- The engine's cost determination is only visible in the payment frame after
  targets are chosen; the priority action metadata still shows the printed
  cost. This is why the MICRO_COSTS verifier binds the payment frame's own
  `unpaid_mana` plus the actually charged mana to the scripted cast.

## Decision-Frame Semantics

See `SELECTOR_DESIGN.md` in this directory for the exact reproduced frames,
option metadata, bounds and contexts.

## Selector Design

- `semantic_objects`: ordered identity list → one offer per identity in the
  placed-object or principal namespace; duplicate-identity, ambiguous-mapping,
  duplicate-option, empty-option-id and engine-cardinality violations fail
  closed; one `selected_option_ids` vector is submitted.
- `amount_assignment`: one engine frame per declared leg; each leg's target is
  resolved to exactly one offer and its amount must lie in the engine frame's
  `numeric_min..numeric_max`; a frame beyond the declared legs fails closed.
- `amount_assignment:<a>+<b>`: requires the ordered observed amounts to equal
  the token and the sum to equal the first frame's engine `amount_remaining`.
- `cost_determined:base_plus_N_generic`: requires exactly one scripted cast of
  the declared source, the first payment frame's `unpaid_mana` to equal the
  declared determined cost and the declared base plus N generic, and the run to
  have charged exactly that many mana with no floating tap.

## MICRO_COSTS Result

`PASS. Construction EXACT. The scripted priority cast of `obj:micro-hex` was submitted from the engine domain, the 6-of-6 multi-select target frame accepted all six requested engine options, and the engine's own payment frame determined `{7}{B}{B}` (base `{4}{B}{B}` + exactly 3 generic) and charged 9 mana in 9 pool spends across 18 engine payment decision ids. Receipt `3367a16e39b4fd8661670ac8…`; runtime receipt digest `454c050427ba5e86e9210bd0…`.`

## PILOT_TARGET_AMOUNT Result

`PASS. Construction EXACT. The engine accepted the two scripted divided-damage legs (`P2` 2, `obj:pilot-p3-target` 2; decision ids `d9ad289746ee…`, `a2d4da150600…`), the observed assignment total 4 equals the engine frame's own `amount_remaining` 4, and both assignment terminal checks hold. Receipt `e3ee6f645810715350165111…`; runtime receipt digest `3a23657fef49927bb28b3e15…`.`

## PILOT_MULTI_AMOUNT Result

`PASS. Construction EXACT. The `multi_amount` record reaches the same engine `target_amount` frames; the two accepted legs (decision ids `1dd6cd8a96e9…`, `94a6b677f99d…`) total 4 with engine `amount_remaining` 4. Receipt `aa7854049438b9ac740884eb…`; runtime receipt digest `111451e83f6686e6eba582ac…`.`

## Wrong-Reason Controls

| Control | Result |
|---|---|
| MICRO_COSTS without the target submission (reaches the real 6-target frame, never pays) | unverified; `cost_determined:base_plus_3_generic` missing |
| PILOT_TARGET_AMOUNT with one declared 2-damage leg | unverified; `amount_assignment:2+2` missing; assignment total false |
| PILOT_MULTI_AMOUNT with one declared 2-damage leg | unverified; `amount_assignment:2+2` missing; assignment total false |
| Reached-only / unscripted / no-decision-id / final-board-only assignment | no evidence |
| Wrong cast source, determined cost not base+3, taps without spends, floating payment, unreadable mana | no evidence |

## Changes

- `src/commander_lab/qualification/current_boundary/midgame_rows.py`
- `scripts/run_midgame_capability_probe.py`
- `tests/qualification/test_current_boundary_midgame_rows.py`
- `docs/midgame_multiselect_amount_closure_20261001/`
- `.foundry/midgame-multiselect-amount-closure-20261001.yaml`
- `qualification/current-boundary-epochs/<epoch>/`, `WS17_SHA256SUMS`,
  `qualification/SHA256SUMS`

## Tests / Evidence

`PB-03 CI run 36916800598: every workflow step green (bridge build, PB-03 contract tests, mid-game probe freshness, two-candidate runner, assembler, R-4 invariants, epoch hash and upload). The produced epoch has 80/80 digests verified against `CURRENT_BOUNDARY_SHA256SUMS`; `MIDGAME_ROW_EXECUTIONS.json` 22/22 rows verified at runner digest `10d3fd2cf76c09ae1b74a4a8e633225aa1ea55b4bf66c645caf836e0397e6178`; XMage `FULL107` 38 PASS / 0 FAIL / 31 UNKNOWN / 38 BLOCKED; loaded engine artifact `004c84e16dc2…` (file, 7107602 bytes) at candidate `37e4df6c914f…`, adapter `1710cac9d2eb…`. Local: focused 87 passed, qualification 824 passed, full suite 3010/3042/3047/3055 passed on successive merged heads, Java 55 passed (projection/submission/decision/midgame/hex), ruff + strict mypy clean.`

## Runtime Receipts

`Reconstructed at-pin claims: engine-authored decision frames (the `target_amount` per-leg frames and the Hex 6-of-6 `target` frame) → external selection from the offered domain → engine-accepted submission → exact semantic obligation → current source-bound positive receipt. The receipts are current for the CI merge ref 1710cac9 (runner digest `10d3fd2c…`, candidate `37e4df6c…`); a later main drift reclassifies them as provenance for that source, not as current credit on the new source.`

## PASS / FAIL / UNKNOWN

| Row | Verdict |
|---|---|
| MICRO_COSTS | ``PASS` (direct, source-bound, wrong-reason-resistant; at-pin CI epoch 1710cac9d2eb-210d2adeeac1)` |
| PILOT_TARGET_AMOUNT | ``PASS` (direct, source-bound, wrong-reason-resistant; at-pin CI epoch 1710cac9d2eb-210d2adeeac1)` |
| PILOT_MULTI_AMOUNT | ``PASS` (direct, source-bound, wrong-reason-resistant; at-pin CI epoch 1710cac9d2eb-210d2adeeac1)` |

## Independent Review

Fresh-context read-only review of the full diff: PASS, no P1/P2 findings.
Repaired P3 advisories: submitted engine option ids are persisted on every
scripted frame; `semantic_objects` fails closed on an offer without an option
id; three additional negative tests (missing option id, negative amount,
payment frame without the engine determination); design-doc precision on the
executor-vs-selector extra-assignment boundary. The local development epoch was
moved out of the worktree and is not committed.

## Historical Evidence Invalidated

The predecessor epoch `2b60482af250-d0fc69bb4022` remains byte-for-byte and is
valid provenance for its own source; it contains no positive receipt for these
three rows and no verdict was transferred from it. No historical receipt,
MODELED local result or prior epoch was used as current credit.

## Remaining Blockers

`None inside this workstream. The three rows are closed on the CI source. Concurrent workstreams (AF05/AF07/AF09) continue to merge contract successors; any post-merge main drift makes this epoch the source-bound provenance of this lineage and requires the next assembly to requalify on its own source, exactly as this workstream requalified across the 1.0.8/1.0.9/1.0.10 drifts it observed.`

## PR / Commit / Tree

`PR #450 (`hardening/midgame-multiselect-amount-closure-20261001`); code head validated by CI `f76c6cefebe65952d654424c4e59152252cdf2fa`; evidence seal adds the epoch `qualification/current-boundary-epochs/1710cac9d2eb-210d2adeeac1/`, regenerated `WS17_SHA256SUMS` / `qualification/SHA256SUMS`, this handoff, the validation record and the state file; the merge commit and terminal main tree are recorded in the #449 terminal comment.`

## Outputs

- `docs/midgame_multiselect_amount_closure_20261001/SELECTOR_DESIGN.md`
- `docs/midgame_multiselect_amount_closure_20261001/FAIL_BEFORE_AND_CONTROLS.md`
- `docs/midgame_multiselect_amount_closure_20261001/VALIDATION.md`
- `qualification/current-boundary-epochs/<epoch>/` (source-bound packet)
- `#450` PR and its CI runs

## Dependencies Unblocked

The three FULL107 rows no longer gate the mid-game lane; the Coordinator's
sequenced next step (AF05 knowledge projection) can consume the lane with the
generic selectors in place. No provider selection or Freeze is implied.

## Exact Next Action

`Mark PR #450 ready and merge it normally; then verify canonical main HEAD/tree, update #449 with this handoff and #255 with the dependency state, and stop.`

`MIDGAME_LANE_MULTISELECT_AMOUNT_CLOSURE = COMPLETE`
`PRODUCTION_PROVIDER = NOT_SELECTED`
`ARCHITECTURE_FREEZE = NOT_CLAIMED`
`SAFE_TO_CLOSE_SESSION = YES`
