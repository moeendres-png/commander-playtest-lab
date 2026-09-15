# QUORUNE Admission — WS219

Verdict: **DO_NOT_PROMOTE_CURRENT_PIN**

Source lock: `64ef65691b2952e29dfb2422687123d3ff5fc1b4` (tree `3dbb9619…`). This is not Provider Selection. `ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Why not promote (exact blockers)

1. **AF07 terminal: 0/29 frozen cards SUPPORTED.** DIRECTLY_VERIFIED probe `probes/ws219_quorune_frontier_check.py`: 8 trusted (`Ishai, Rograkh, Narset-Parter, Dig Through Time, Psychosis Crawler, Butcher of Malakir, Gratuitous Violence, Basilisk Collar`) with zero behavior tests → at most PARTIAL; 21 residual fail-closed with minimum blockers in `continuous-effect-layers-and-dependencies`, `intervening-if-and-reflexive-trigger-grammar` + `normalized-event-binding`, `replacement-applicability` + `self-replacement-and-prevention-ordering`, `ordered-effect-composition`, `multiple-targets`, `unparsed-overload/cleave/choose-one/change-target`. Construction/readback gets zero behavior credit. Evidence: `coverage/card-unlock-frontier.json.gz` (31623 records) + `QUORUNE_FROZEN_CARD_MATRIX.json`.
2. **AF06 terminal: universal grammar blocked.** `docs/RULES_COMPLETENESS_STATUS.md:44-55` + `docs/RULES_DEPENDENCY_QUEUE.md:37-60+`: complete layers/dependencies/timestamps/CDA, universal replacement/prevention + simultaneous ordering, complete alternate/additional-cost grammar + restricted mana, intervening-if/reflexive + normalized-event-binding, broad target/search/trigger/loop/shortcut grammar, full combat variants — all blocked. 2136 cards sole-blocked by continuous layers; 4949 residuals in queue.
3. **Consequence for AF04/AF08:** complete authoritative legal-action surface and WS05 MUST runtime cannot be demonstrated while the above gaps fail closed (correctly) — completeness missing by design at this pin.

## What is credible (and why it is not enough)

- Sole Rules authority + fail-closed preflight/admission (`preflight.py:895-996`; `admission.py:49-50`) — credible AF03/AF04-design.
- Seat-projected principal-mandatory observation (`projection.py`; `permissions.py`) — credible AF05-design.
- 2-6 seats constructible, 4P primary; tax/damage/zones/Partner-family/mulligan/start/elimination-baseline in code — plausible AF02/AF08-path.
- Seeded RNG + Game Record v3 hash-chained command replay + clean-process resume design — closest to WS218 Tape v1 (AF09-design).
- README architecture quality is explicitly not enough per hard gates; admission requires denominator support, which is 0/29.

## Affected gates / denominator

- FAIL-closed (not PASS): AF06, AF07; consequently AF04 (completeness), AF08 (MUST runtime), AF10 (denominator accounting 0/175).
- Frozen denominator: 0 SUPPORTED / 20 PARTIAL / 9 MISSING / 0 UNKNOWN of 29.

## What would have to change upstream

- Lower the 21 residual frozen cards (close layers, event-binding grammar, replacement ordering, ordered-effect-composition, multiple/divided targets, overload/cleave/choose-one/change-target/modal grammar).
- Add real behavior tests for all 29 (currently 0/29; Vandalblast has only cost-path tests, still residual).
- Close universal layers/replacement/cost/target/trigger/combat gaps in `RULES_DEPENDENCY_QUEUE.md` order; re-run `card-unlock-frontier` + `COMPILER_COVERAGE_STATUS` to show exact fraction materially above 31.5% with frozen-29 all trusted + tested.
- Execute per-count 2-5P lifecycle + WS05 MUST + MICRO + HIDDEN + REPLAY fixtures at runtime.

## Why further current qualification would not alter admission

Additional runtime at this pin would only re-confirm fail-closed behavior on residuals (correct) and inventory existing tests; it cannot invent the missing lowering/grammar. The blocker is upstream implementation, not measurement. Expensive full-suite execution was therefore stopped per Early Stop Rule after the bounded frontier probe.

## Bounded next-step plan (if Coordinator ever re-opens)

1. Upstream closes the 6 recurring blocker families above.
2. Re-probe frontier: require 29/29 trusted + 0 minimum blockers.
3. Add 29 behavior tests (one per CARD_* fixture) + run them.
4. Then run MICRO_*, WS05-*, HIDDEN_*, REPLAY_* fixtures per-count.
5. Re-seal AF06/AF07/AF04/AF08/AF10 before any promotion discussion.
