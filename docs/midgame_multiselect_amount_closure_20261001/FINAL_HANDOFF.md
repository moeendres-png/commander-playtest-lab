# MIDGAME_LANE_MULTISELECT_AMOUNT_CLOSURE_FINAL_HANDOFF_20261001

Workstream `MIDGAME-LANE-MULTISELECT-AMOUNT-CLOSURE-20261001` (issue #449; parent #255,
Coordinator sequencing comment 5931735894; ownership reservation comment 5931753920).

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

## Source Lock

| Role | Identity |
|---|---|
| Audit base main | `4e41bde6fd4f27dc448ae8c44f7af9212e3198fe`, tree `09e139d4bebfd3cb960b692c66297ab9385674df` |
| Owned branch | `hardening/midgame-multiselect-amount-closure-20261001` |
| Sealed branch head | `TBD_SEAL_COMMIT`, tree `TBD_SEAL_TREE` |
| XMage candidate | `37e4df6c914f1e189e24f0ef59fa91734c922436` |
| Forge Rules-Core / bridge | `bb0a740d2bef725194798383c2452213ecdd0b37` / `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c` |
| Effective contract at run time | `commander-lab.full107/1.0.7-successor` |
| PB-03 CI run | `TBD_CI_RUN` on merge ref `TBD_CI_MERGE_REF` |
| Evidence epoch | `qualification/current-boundary-epochs/TBD_EPOCH_ID/` (digests verified against `CURRENT_BOUNDARY_SHA256SUMS`) |

## Terminal Main Lock

`TBD_TERMINAL_MAIN` (tree `TBD_TERMINAL_TREE`), verified after the merge.

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

`TBD_MICRO_COSTS_RESULT`

## PILOT_TARGET_AMOUNT Result

`TBD_PTA_RESULT`

## PILOT_MULTI_AMOUNT Result

`TBD_PMA_RESULT`

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

`TBD_TESTS_EVIDENCE`

## Runtime Receipts

`TBD_RUNTIME_RECEIPTS`

## PASS / FAIL / UNKNOWN

| Row | Verdict |
|---|---|
| MICRO_COSTS | `TBD_MICRO_VERDICT` |
| PILOT_TARGET_AMOUNT | `TBD_PTA_VERDICT` |
| PILOT_MULTI_AMOUNT | `TBD_PMA_VERDICT` |

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

`TBD_REMAINING_BLOCKERS`

## PR / Commit / Tree

`TBD_PR_COMMITS`

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

`TBD_NEXT_ACTION`
