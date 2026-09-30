# Positive fixture receipts: a producer and a validated loader (2026-09-30)

Claude Opus 5.5. Source lock: Lab main `80879991` (tree `93ceaaa2`), XMage pin `9375f35a`. Campaign task B2 / OC-P1-08, issue #408.

## The defect (`DIRECTLY_VERIFIED`)

The assembler credits a FULL107 row from a native receipt only through `receipts.positive_fixture_credit()` (schema `commander-lab.positive-fixture-receipt/1.0.0`). That consumer was dead twice over:

1. **Nothing produced such a receipt.** No writer existed in `src/`, `scripts/`, `engine-bridge/` or `.github/`.
2. **Even a correct receipt would never have reached it.** `collect_receipts()` loads every file as a native-*suite* receipt and rejects every other schema, so a positive receipt placed in the receipt directory would have been rejected before the credit function ever saw it.

As a result, `native_promotions` is 0 whatever runs.

## Decision (systemic, option A: separate receipts)

A positive fixture receipt is a separate document. It lives in its own subdirectory (`receipts/positive/`) and is loaded by its own validator.

- **Why not a sub-record in the suite receipt?** A suite receipt proves that a suite ran. A fixture receipt proves that one row's obligation was observed, and it has its own identity and evidence. Mixing the two would let a green suite count carry fixture credit.
- **Loader.** `load_positive_fixture_receipt` / `collect_positive_fixture_receipts` check the schema, every required field (non-empty) and the content digest, all fail-closed. Whether a receipt earns credit (candidate head, runner digest, outcome, `POSITIVE_BEHAVIOUR`, denominator) stays with the unchanged `positive_fixture_credit`.
- **Separation.** The suite loader reads only the top level of the receipt directory, so it never sees, and never rejects, a positive receipt.

## Producer: exact placement obligations on the production midgame lane

`current_boundary/midgame_rows.py` closes the last two links of the documented PB-03 chain:

> `… construction truth → causal observation → exact semantic obligation → runner-bound native receipt → qualification credit`

For each declared denominator row whose requested state the lane constructs exactly by placement, the obligation is executed through the production lane and verified from engine facts:

- **Construction.** The engine places and reads back the frozen record. Only `EXACT`, or the lane's documented declaration-step priority allowance, proceeds.
- **Answers.** Only engine-offered options are used:
  - the record's `decision_script`, in order;
  - scripted priority passes;
  - mana from the record's own sources, in declared order;
  - an attacker assignment that is complete for the declarer (listed creatures attack the named player, all others are held).

  Any other decision stops the row unverified.
- **Verification.** Each `required_events` token needs positive evidence on the engine's public event tape (`get_midgame_events`, PR #409) or in the decision trace. A token kind the module does not understand is never assumed. Every terminal postcondition the record states is encoded as an explicit check against the engine's observation (life, trigger count, commander cast count, tapped state, no mana payment).
- **Receipt.** Only a fully verified row gets a receipt. It is bound to the candidate commit and runner digest, carries its obligation and observed evidence, and carries the digest of the full execution document. `execute_and_persist` deletes earlier receipts first, so a row that stops verifying loses its credit.

Causal-route rows (a stack spell or an elimination that must be caused) are not executed here. Whether they earn credit remains the Coordinator decision slot.

## Evidence

**Live chain (`DIRECTLY_VERIFIED`, on pin `9375f35a`, fresh lane process per row):** `execute_and_persist` → persist → `collect_positive_fixture_receipts` → `positive_fixture_credit` with the real runner digest gives **9 of 9 rows verified, 9 receipts, 0 rejected, 9 credited**.

| Row | Current boundary | Construction | Verified from |
|---|---|---|---|
| MICRO_TRIGGERS | BLOCKED | EXACT | ZONE_CHANGE, TRIGGERED_ABILITY, DAMAGED_PLAYER; one Surge trigger; P2 38 |
| PILOT_PRIORITY | UNKNOWN | EXACT | priority frame to P1; SPELL_CAST obj:pilot-bolt |
| PILOT_TARGET | UNKNOWN | EXACT | target frame to P1; P2 selected from the offered set |
| MICRO_TARGETS | UNKNOWN | EXACT | target frame with offers; P2 selected |
| WS05-MP-COMBAT-4 | BLOCKED | ALLOWED_VARIANCE | two ATTACKER_DECLARED to P2 and P3 |
| WS05-MP-COMBAT-5 | BLOCKED | ALLOWED_VARIANCE | three ATTACKER_DECLARED to P2, P3 and P4 |
| PILOT_DECLARE_ATTACKER | BLOCKED | ALLOWED_VARIANCE | declare frame; ATTACKER_DECLARED to P2; Bears tapped |
| WS05-CMD-TAX-2 | UNKNOWN | EXACT | COMMAND→STACK; 4 declared Mountains tapped (tax 4 over printed {0}); cast count 3 |
| CARD_02 | UNKNOWN | EXACT | COMMAND→STACK; resolved onto the battlefield; cast count 1; no mana asked |

**Tests (`TECHNICALLY_CONFORMANT`):** `tests/qualification/test_current_boundary_midgame_rows.py`, 40 tests.
- Every token kind has a positive and a negative case, and unknown kinds are never assumed.
- Terminal checks.
- An unverified row gets no receipt.
- Persist → load → credit.
- Credit is refused for another candidate, another runner or another denominator.
- A tampered receipt, a missing field or a wrong schema is rejected.
- Stale receipts are cleared.

**Bridge:** the placement response now carries `placed_objects` and `commander_objects`, with the same justification as the causal routes: those ids already appear in every offered action.

## Not in this PR: wiring (ownership)

**No FULL107 count changes from this PR.** The runner hook (execute after the native suites, bound to the runner identity) and the assembler read are two small hunks on the current-boundary lane's active surface (#395 re-seals the evidence tree; issue #408 records that ownership). They are handed over as a ready patch on #408.

Where the receipts are written is tied to campaign task B1: the wiring must target an explicit successor epoch, not the historical WSR22 tree.

CARD_24 verifies too, but the 29-card corpus is AF07's obligation and not a denominator row, so it is not in the credit registry.
