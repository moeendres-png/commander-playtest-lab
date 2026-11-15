# Muse PB-03 integration-ready packet

## Purpose

This packet preserves the remaining unique Muse PB-03 runtime tests without transferring historical PASS credit or forcing a merge of the broader PR #284.

## Donor identity

- branch: `donor/muse-xhigh-independent-20260928`
- head: `b7b16ef858e2d88bbb2946710eb054afe1246b78`
- tree: `1b6320abc0024bd90c093f9e68ecf056b88c0d3f`

## Existing #284 ports

| Asset | #284 port commit | Target path | Current disposition |
|---|---|---|---|
| Dimension admission | `16586477ba51cc5281f340f5ad4abd95dd5f810a` | `engine-bridge/src/test/java/org/commanderlab/xmage/XmagePb03DimensionAdmissionTest.java` | Safe zero-credit discriminator; separately ported on the clean Muse salvage branch |
| Tier-1 actual behavior | `e910e437c21ab5be6596845c4a54557c2e1a780e` | `engine-bridge/src/test/java/org/commanderlab/xmage/XmagePb03Tier1RowsTest.java` | Valuable; affected behavior credit blocked by P1 |
| Tier-2 command zone | `33d5bf343df6d55f3c557fa381d684f19a57e418` | `engine-bridge/src/test/java/org/commanderlab/xmage/XmagePb03Tier2CmdZoneTest.java` | Characterization/regression; not auto-promoted |
| Tier-2 control/turn | `8ba96bc3ecdc5737352b552b4126c3f10ce2df94` | `engine-bridge/src/test/java/org/commanderlab/xmage/XmagePb03Tier2ControlTurnTest.java` | Valuable; behavior credit inherits Tier-1 mana P1 |
| Tier-2 stack | `27644c2ba943ca19f2a07cfa56d1156bb58a8e39` | `engine-bridge/src/test/java/org/commanderlab/xmage/XmagePb03Tier2StackTest.java` | Valuable; behavior credit blocked by `firstPoolSpend` P1 |
| exact JUnit positive fixture extraction | `4f8ef7942e0cff7e039992a41b823ac0bcee359d`, `50f1dce3e3879c23105aa165f19591036d334d4e`, `048a993b7d769eb5f78f8978f40a7983bf835a24`, `a3ebf798d5734ae3bbbdb1fca2d621aca4a724c1` | current-boundary runner/receipt tests | Do not copy wholesale while Space Bunny owns overlapping runner paths; reapply after winner adjudication if still missing |

## P1 that must be removed before positive behavior credit

### Tier-1 shared mana helper

Current behavior:
- collect all engine-offered allowed `mana_ability` actions;
- sort by `action_id`;
- submit element zero;
- similarly sort/select first `mana_pool` action.

This is deterministic but not an authoritative choice.

### Tier-2 stack helper

`firstPoolSpend()` sorts pool offers and submits element zero.

## Required fail-closed hardening sequence

1. **Never use ordering as authority.**
   Remove sorting-as-selection as a semantic decision mechanism.

2. **Prefer exact fixture-scripted source binding.**
   Where the frozen obligation names a semantic source/order, map that semantic object to the engine-native object id and select the matching engine-offered action.

3. **Where the fixture does not specify a source, prove equivalence or require uniqueness.**
   A test may choose among alternatives only after establishing that all alternatives are semantically outcome-equivalent for the obligation. Otherwise fail closed and grant no row credit.

4. **Start with the strict uniqueness discriminator.**
   Replacing the current first-option behavior with an assertion that the eligible offer count is one is the correct fail-before control. Any test that then fails has exposed an unscripted discretionary choice and must receive an explicit semantic source script or remain non-credit.

5. **Do not weaken receipt extraction.**
   Positive fixture receipts must continue to come from exact passing Surefire testcase identities inside a source-bound native-suite receipt.

6. **Rerun from a clean committed head.**
   No historical Muse result JSON may substitute for the current execution.

## Known affected positive scenarios

At minimum:
- `MICRO_MODES`
- `MICRO_PREVENTION`
- `MICRO_TRIGGERS`
- `WS05-MP-TURN-5`
- `MICRO_CONTROL`
- Tier-2 stack scenarios that reach `firstPoolSpend()`.

The exact affected set must be measured by the uniqueness fail-before run rather than inferred from test names.

## Safe current test behavior

Examples already using acceptable patterns:
- exact target matching by engine/native identity;
- exact attack matching after asserting a unique offer;
- identical trigger alternatives asserted before selecting;
- identical cleanup discard labels asserted before selecting;
- Rules-RNG Heads/Tails choice observed and deliberately left unanswered when the fixture provides no script.

## Active ownership / overlap

At audit time #284 and Space Bunny PR #289 overlapped only:
- `scripts/run_current_boundary_qualification.py`
- `src/commander_lab/qualification/current_boundary/game_driver.py`
- `tests/qualification/test_current_boundary_redaction_placeholders.py`
- `tests/qualification/test_current_boundary_start2_observed_state.py`

The four Muse Tier-1/Tier-2 Java test files do not overlap #289.

Therefore:
- Java tests can be ported independently after P1 hardening;
- runner/receipt commits must be reconciled against the active completion winner rather than blindly cherry-picked.

## Integration recipe after P1 remediation

1. Fresh-lock current main.
2. Verify the current native restoration API still satisfies the tests.
3. Port/cherry-pick only the required Java tests/helpers.
4. Apply semantic/unique mana-choice hardening.
5. Run the affected Maven classes from a clean committed head.
6. Run External XMage Integration and Full Game Conformance.
7. Only after green runtime execution add/retain exact Surefire positive-fixture receipt mapping.
8. Run qualification tests proving failed/skipped/absent testcase receipts confer zero credit.
9. Impact-adjudicate the resulting FULL107 rows.
10. Do not import Muse-generated historical counts.

## Status

`MUSE_PB03_TESTS_PRESERVED = YES`

`MUSE_PB03_TESTS_INTEGRATION_READY = YES_WITH_P1_REMEDIATION`

`MUSE_PB03_BEHAVIOR_CREDIT_READY = NO`

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
