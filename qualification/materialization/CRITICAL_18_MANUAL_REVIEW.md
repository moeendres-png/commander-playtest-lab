# WS-30 CRITICAL 18 MANUAL SEMANTIC REVIEW

This review is mandatory because WS-28 proved that same fixture ID did not imply equivalent historical setup. Each entry below explains why the WS-30 scenario preserves the frozen obligation and why neither historical provider setup is normative. Candidate behavior is evidence only.

## 1. `PLAYER_COUNT_2P`

**OBLIGATION_PRESERVED.** Commander lifecycle with 2 real players, 40 life, Rograkh + 99 Mountains, command-zone commander and real opening hand. This follows the Commander-centric production contract rather than Forge 20-life technical lifecycle or XMage Isamaru/Plains history.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 2. `PLAYER_COUNT_3P`

**OBLIGATION_PRESERVED.** Same canonical Commander lifecycle expanded to exactly 3 real seats; identity is seat/player semantic, not engine seat object.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 3. `PLAYER_COUNT_4P`

**OBLIGATION_PRESERVED.** Exactly four Commander players with identical neutral deck template and lifecycle. This is the decision-evidence default pod size but receives no candidate credit.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 4. `PLAYER_COUNT_5P`

**OBLIGATION_PRESERVED.** Exactly five Commander players using dynamic live-player semantics; proves the technical 5P production scope without copying either finalist setup.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 5. `PILOT_MULLIGAN`

**OBLIGATION_PRESERVED.** Uses a real 4P Commander pregame hand and the multiplayer free-first-mulligan rule. The tested obligation is external discretionary mulligan selection from provider legal options; setup is neutral and fail-closed.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 6. `PILOT_PRIORITY`

**OBLIGATION_PRESERVED.** P1 receives a provider DecisionFrame at priority with a concrete Lightning Bolt cast available. The selector identifies the semantic cast/target, never option number or candidate action ID.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 7. `PILOT_TARGET`

**OBLIGATION_PRESERVED.** Lightning Bolt target selection is concrete and deterministic; P2 is selected only if the Rules Core offers P2 as legal. Historical Bolt versus hidden-target candidate setups are not reused.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 8. `HIDDEN_01`

**OBLIGATION_PRESERVED.** P1 observes P2 hand count while the deterministic honey-card identity and metadata remain prohibited on all pilot-visible channels. This directly materializes count-visible/identity-hidden.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 9. `HIDDEN_02`

**OBLIGATION_PRESERVED.** P1 observes P2 library count while identity and order are prohibited. No historical provider hidden-zone probe is authoritative.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 10. `MICRO_STACK`

**OBLIGATION_PRESERVED.** Bolt is already on stack targeting P2 Grizzly Bears; P2 responds with Giant Growth, so native stack LIFO resolution and final survival are directly testable. Stable semantic IDs replace engine stack IDs.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 11. `MICRO_REPLACEMENT`

**OBLIGATION_PRESERVED.** A deterministic 3-damage creature event under Gratuitous Violence tests a replacement effect as 3->6. This deliberately avoids adopting either historical commander-zone or Rest in Peace scenario.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 12. `WS05-MP-COMBAT-4`

**OBLIGATION_PRESERVED.** P1 assigns distinct attackers to P2 and P3 in one declaration. This directly tests multiple defending players and preserves defender identity without borrowing historical Bears/Runeclaw layouts.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 13. `RNG_RULES_TAPE`

**OBLIGATION_PRESERVED.** The common replay experiment records a provider-native library shuffle on RulesRngTape; pilot mode choice is separately on DecisionTape. Semantic randomness is replayed, not raw PRNG identity.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 14. `REPLAY_DECISION_TAPE`

**OBLIGATION_PRESERVED.** The exact create-devils semantic selector and its matched semantic option projection are recorded. Provider option IDs are not cross-provider identity.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 15. `REPLAY_EVENT_TAPE`

**OBLIGATION_PRESERVED.** Meaningful normalized shuffle/decision/token events are recorded while internal event chatter may vary.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 16. `REPLAY_CLEAN_PROCESS`

**OBLIGATION_PRESERVED.** A fresh process reconstructs the same initial digest and replays RulesRngTape + DecisionTape to equal semantic checkpoints; raw UUID/process identity is ignored.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 17. `REPLAY_STATE_HASHES`

**OBLIGATION_PRESERVED.** Privileged/public/P1-scoped semantic hashes are checkpointed with process-local identities excluded, preserving WS-06 hidden-information boundaries.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

## 18. `CARD_02`

**OBLIGATION_PRESERVED.** Rograkh starts as P1 commander in command zone with zero prior command-zone casts; P1 casts it for printed cost 0 and zero tax. This is directly keyed to WS-29 CARD_02 authority rather than either finalist history.

Independence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.

