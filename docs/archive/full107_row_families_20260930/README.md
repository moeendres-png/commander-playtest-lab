# FULL107 direct producer: more row families (#425 section C), 2026-09-30

Claude Opus 5.5. Source lock: Lab main `ed94cf0a`, XMage authority `9375f35a` (`config/rules_engines.json`). Scope reserved on #425 (section C only).

## Finding: the mana measurement counted declared sources, not the charge (`DIRECTLY_VERIFIED`)

In the #411 producer, `mana_paid:N` and `commander_tax:+N_generic` counted the mana abilities the lane tapped. But the lane tapped **every** declared source before spending anything from the pool. A mana ability only adds mana to the pool; the engine charges the cost through pool spends. So the tap count described the record's declaration, not the charge.

- **Live reproduction:** PILOT_ANNOUNCE_X with X=2 costs {2}{U}{U} = 4 mana. It tapped all 5 declared Islands, spent 4 and floated one U, and the old measure read 5.
- **Consequence:** WS05-CMD-TAX-2 (credited since #411) was measured this way. A 4-mana charge and any smaller one would both have read as 4 with its 4 declared Mountains.
- **Its credit was correct in outcome:** re-verified under the corrected measure, the engine charges exactly 4. But until now it was not measured for the right reason.

The fix has two parts:
1. **Measure.** The charged mana is the number of pool spends (`_mana_charged`). If tapped and spent mana disagree (mana floated), the measure refuses to answer.
2. **Policy.** The single advancing pool spend comes before tapping the next declared source, so a source is tapped only while the cost still needs mana. As before, no colour choice is made for the pilot.

The earlier record `docs/positive_fixture_receipts_20260930/README.md` ("4 declared Mountains tapped") remains provenance of its own measurement.

## New rows

| Row | Players | Obligation (record) | Verified from engine facts |
|---|---|---|---|
| WS05-CMD-TAX-4 | 4 | Rograkh, two prior casts: {4} tax, cast count 3 | COMMAND→STACK; engine charged 4 ({0} printed); cast count 3 |
| PILOT_ANNOUNCE_X | 4 | X=3 bound into spell and cost | announce_x frame answered 3 and accepted; charged 5 = X+{U}{U}; 3 LIBRARY→HAND for P1 |
| PILOT_CHOOSE_MODE | 4 | provider-offered Devil-token mode | mode frame; bound offer selected; 3 Devil CREATED_TOKEN; no DAMAGED_PERMANENT |
| WS05-CMD-START-3 | 3 | in 3P the starting player P1 draws on the first turn | tape from the game start: the engine's first BEGIN_TURN is P1's; exactly one LIBRARY→HAND for P1 in turn 1's DRAW step (the record's checkpoint). Negative control: the same tokens on the 2P record miss the draw (CR 103.8a) |
| PILOT_TRIGGER_ORDER | 4 | Arena and Remora trigger together at upkeep; Arena ordered first | ordering frame offering exactly 2; both TRIGGERED_ABILITY for P1, put Arena then Remora (the reversed script puts Remora first) |

New lane capability:
- **Decision-family mapping.** The record's `choose_mode` is the engine's `mode`; every other family is spelled alike.
- **Integer selector.** The number goes only to the engine's numeric offer (`choices.numeric_choice`); a non-integer or a missing offer fails closed.
- **Mode-key binding.** A `semantic_mode_key` has no machine definition in the record; its meaning comes from the record's own postcondition prose. The row binds it to text of the engine mode it names, and that text must occur in exactly one offered mode label, otherwise the row fails closed.
- **Engine-side checks:**
  - charged mana;
  - library→hand moves for a player;
  - created tokens by name;
  - no damage to any permanent (proves the other mode did not also resolve).
- **Vacuous-obligation guard.** A row with no required event and no terminal check is never verified; it would verify for any behaviour. The triage run met exactly this case with WS05-CMD-PARTNER-DMG under an empty spec.

**PILOT_TRIGGER_ORDER needed three lane changes (`DIRECTLY_VERIFIED`):**

1. **Zero counters.** A counter map whose only kind has count zero (`{"age": 0}`) was rejected as a counter request, although it places no counter. It is now the same request as no counters; any non-zero, negative or non-numeric count stays `UNSUPPORTED_COUNTERS` (PILOT_CHOOSE_ABILITY's loyalty 3 is still rejected).
2. **Arrival checkpoint.** The simultaneous upkeep triggers are ordered before anyone receives priority. The arrival driver now also stops at the record's **own first scripted decision**, and only when the engine is at the record's phase and step. Any other non-priority decision, or the same decision elsewhere, still fails closed.
3. **Completion while parked on `trigger_order`.** Arrival completion re-ran `checkStateAndTriggered` from the bridge thread while the engine thread was parked inside `GameImpl.checkTriggered` on that very decision. That re-entered it, and the engine asked the ordering again: "concurrent pending decision". While the engine is parked on `trigger_order`, the completion is now a pure readback: the engine itself has just checked SBA and triggers. Every other parked decision keeps the revalidation.

`XmageTemporalAdvancedProgressionTest` already showed that the engine offers both abilities. The stack order comes from the tape: XMage reports `TRIGGERED_ABILITY` as each ability is put on the stack.

**Negative controls (live, `DIRECTLY_VERIFIED`):**
- the Devil key bound to the damage mode → 0 tokens and damage dealt → unverified;
- X=2 instead of 3 → charged 4, 2 draws, `x_announced:3` missing → unverified.
- the reversed trigger order → the engine puts Remora first → `stack_order` false → unverified.

**Local chain (`DIRECTLY_VERIFIED`, pin `9375f35a`, fresh lane process per row):** 14 of 14 registered rows verify, including the 9 already credited.

## Triage: every remaining non-PASS row on the lane

Every row still UNKNOWN or BLOCKED on #421's PB-03 run (36768896191) was driven once through the lane with an empty spec. The table groups each residual by its exact cause.

| Group | Rows | Exact residual | Owner of the next step |
|---|---|---|---|
| Stack state requested | MICRO_COPY, MICRO_MANA_PAYMENT, MICRO_PRIORITY, MICRO_STACK, MICRO_ZONE_CHANGES, PILOT_CHOICE, PILOT_CHOOSE_OBJECT, PILOT_MANA_PAYMENT, PILOT_PILE, PILOT_REPLACEMENT_EFFECT, NEGATIVE_PARENT_CLASS_FALLBACK | `UNSUPPORTED_ZONE … requests stack`: a stack object must be *caused* | Coordinator decision slot (causal-route credit) |
| Library placement | PILOT_CHOOSE_USE, NEGATIVE_DEFAULT_YES_NO | `UNSUPPORTED_ZONE … requests library` | lane extension (exact library order) |
| Counters | PILOT_CHOOSE_ABILITY (loyalty 3) | `UNSUPPORTED_COUNTERS` | lane extension: Jeska's own ETB sets loyalty from commander casts, so an exact placement must set the counter after entry without a counter event |
| Pregame | PILOT_MULLIGAN, WS05-CMD-MULL-2, WS05-CMD-MULL-4 | `UNSUPPORTED_PHASE pregame` | game-start lane, not the midgame lane |
| Script names no causal step | MICRO_MODES, PILOT_TARGET_AMOUNT, PILOT_MULTI_AMOUNT, NEGATIVE_FIRST_OPTION, NEGATIVE_GUI_DEFAULT, NEGATIVE_RANDOM_OPTION, NEGATIVE_SILENT_SKIP, NEGATIVE_INTERNAL_AI | the `decision_script` begins at a decision inside a cast (or names none) without the cast that opens it; only `native_procedure` prose names it | fixture gap (Coordinator); the producer does not invent the cast |
| Mid-combat checkpoint | PILOT_DECLARE_BLOCKER, WS05-MP-BLOCK-4, MICRO_REPLACEMENT | arrival passes the requested DECLARE_BLOCKERS / COMBAT_DAMAGE step: a declared combat needs restoration plus a causal step | Coordinator (declared combat state) |
| State facts, no event | MICRO_LAYERS, MICRO_STATE_BASED_ACTIONS, WS05-CMD-PARTNER-ZONE, WS05-CMD-DMG-SPLIT, WS05-CMD-ELIM-4, MICRO_COMBAT, MICRO_PREVENTION | required tokens are state/SBA facts (P/T layers, SBA) that the tape does not carry; several also need declared combat | observation-based verifiers per token kind, then per-row onboarding |
| Cost enumeration | WS05-CMD-PARTNER-TAX | the record gives P1 no mana source, and XMage offers only affordable casts, so neither partner's taxed cost is observable from offers; the procedure asks for a native cost query | a cost-query surface (bridge) or a fixture with mana |
| Control divergence | MICRO_CONTROL | `UNSUPPORTED_CONTROL_DIVERGENCE` (control needs a resolved control-change effect) | causal route |
| Arrival decision | MICRO_CONTINUOUS_EFFECTS | the arrival driver refuses `trigger_order` before the checkpoint | arrival extension |
| Illegal scripted action | MICRO_COSTS | the record has **P2** cast Hex (a sorcery) while **P1** is the active player in precombat main; CR 307.1 allows a sorcery only in its caster's own main phase with an empty stack, so the engine correctly offers no cast | fixture defect (Coordinator); `EXTERNALLY_RULE_VALIDATED` against CR 307.1 and Hex's Oracle type line |

Out of reach of this lane by construction:
- HIDDEN_* (20): per-principal probes;
- REPLAY_* / RNG_RULES_TAPE (5): N-scoped replay;
- the causal-route rows: their deviation is the Coordinator's decision.

`PRODUCTION_PROVIDER = NOT SELECTED` · `ARCHITECTURE_FREEZE = NOT CLAIMED` · no denominator change.

## Coordinator questions this slice cannot answer (decision-ready)

The first three are technical facts plus one policy question each. None of them changes the denominator.

1. **Scripts that start inside a cast.** The rows MICRO_MODES, PILOT_TARGET_AMOUNT, PILOT_MULTI_AMOUNT, NEGATIVE_FIRST_OPTION, NEGATIVE_GUI_DEFAULT, NEGATIVE_RANDOM_OPTION and NEGATIVE_SILENT_SKIP share one gap:
   - their `decision_script` begins at the mode/target/amount decision;
   - only `native_procedure` names the cast that opens it (`NATIVE_BEGIN_PAYABLE_MAGMA_OPUS_CAST`, `…CAST_TO_MODE_DECISION`);
   - PILOT_CHOOSE_MODE, by contrast, scripts its own cast.

   *Question:* may the executor take the opening cast from `native_procedure` when it names exactly one castable object? Or must the fixtures gain the explicit priority step? The executor does neither on its own today.
2. **MICRO_COSTS asks for an illegal action.** P2 casts Hex (Sorcery) while P1 is active in precombat main. CR 307.1 allows a sorcery only in its caster's own main phase with an empty stack; the engine correctly offers no cast. *Question:* repair the fixture, for example by making P2 active? Changing the fixture changes its requested-state digest.
3. **The typed failure of the NEGATIVE_* rows.** The rows require `fail_closed:UNSUPPORTED_DISCRETIONARY_DECISION` when the external handler does not answer. The protocol has no message by which a handler declares a decision unsupported. The engine's own fail-closed on no answer is `DECISION_TIMEOUT` after the frame's timeout. *Question:* does `DECISION_TIMEOUT` satisfy "typed unsupported discretionary-decision failure", or is an explicit protocol response required? The executor does not relabel one as the other.
4. **Causal-route credit (existing slot).** It covers 11 stack-state rows plus the mid-combat and control-divergence rows.
