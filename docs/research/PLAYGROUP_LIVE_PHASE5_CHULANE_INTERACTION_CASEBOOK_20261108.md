# Chulane pilot & opponent interaction — Phase 5 decision test casebook

**Date:** 2026-11-08. **Status:** `PROPOSED_NOT_RUN`. Designed for pinned XMage native offer-only decisions, not generic structural-simulator winrate proof. **No source decks, agent pilots, Rules Core, or collection assets altered.**

**Scope:** (A) The Chulane seat's own risk/response decisions and (B) opponent seats' decisions when facing Chulane, in ordinary 4P and separately qualified 6P games. Real card ownership, mana, priority, counter targets, stack and triggers always come from XMage.

## Oracle for every case

- Construct fixture with **real cards, real legal `decision_id` and `option_id`** and actor-scoped view. Never force a game result, hidden card or ability into the engine.
- Evaluate **acceptable offered-option set**, unacceptable offered-option set, timing and counterfactual explanation. A better policy may choose one of several good actions; it need not reproduce an exact label.
- A card not in hand/deck, unpaid mana or a missing response window means that option must **not** appear. The test is failed if a policy invents it.
- Run matched seeds and all seat rotations for game evidence. Replays and actor-safe logs must be equivalent for unaffected decisions; exact source/pin captured in evidence.
- The numbers below are **ID labels**, not claims of completed or independently Rules-validated combos.

## Scenario matrix

| ID | Acting seat | Scenario (public setup + engine-authorized actions) | Expected strategic judgment / negative control | Diagnostic |
|---|---|---|---|---|
| CH-A01 | Chulane | Opponent casts targeted removal against Chulane; own cheap protective instant legally offered | Protect only if future value outweighs spending the answer vs. pending win threats | Correct protector chosen; survival later |
| CH-A02 | Chulane | Same threat with **zero legal protection/counter offered** | No fake protection, no opponent-answer simulation, fail closed if malformed option | Forbidden invented action count = 0 |
| CH-A03 | Chulane | Opponent places high-impact win spell on stack while own Chulane is exposed to low-value removal | Counter true immediate win line, not always preserve Commander first | Win-threat counter/response preference |
| CH-A04 | Chulane | Opponent casts harmless spell; low mana and one real Counterspell | Keep Counterspell for later meaningful stack target, not reflexive counter | `counter_cast_when_low_worth` |
| CH-A05 | Chulane | Own main phase, Chulane online, one 1–2 MV creature plus available land and stack empty | Develop creature to draw and place land, unless genuine lethal/wipe exposure dominates | Chulane creature cast rate and follow-up land |
| CH-A06 | Chulane | Own board 3+ creatures and public enemy mana with possible wipe; one last creature and a protection card | Avoid unbounded overextension when value marginal; don't assume enemy has a wipe | Margin-based risk, no private-hand inference |
| CH-A07 | Chulane | Public opponent represents wipe but **no wipe legally in that opponent's hand** (fixture truth) | Opponent must not cast phantom wipe; our pilot may act on uncertainty only, not certainty | Unauthorized action count = 0 |
| CH-A08 | Chulane | Wipe on stack; one protection and one counter as real legal responses | Evaluate which saves relevant board/commander with actual effect and cost | Survival + mana + resolves |
| CH-A09 | Chulane | `Whitemane Lion` offered as a legal cast when Chulane is on board | Exploit bounce/ETB draw only when such a real legal sequence exists; no ghost flash/loop | Cast/trigger order, native decisions |
| CH-A10 | Chulane | `Whitemane Lion` or comparable bounce ability without Chulane and no protection need | Do not repeatedly bounce own objects for no value or loop indefinitely | No-progress decisions per turn |
| CH-A11 | Chulane | `Lonis`, `Academy Manufactor`, many Clues/Treasures; a nonartifact creature wipe is offered by opponent | Correctly distinguish creature/Clue/artifact threat; Clues are **not creature tokens** | Threat classification / legal affected objects |
| CH-A12 | Chulane | Eight same-named artifacts and `Mechanized Production` nearing upkeep | Consider alternate win clock and protecting it; do not invent premature win or trigger | Engine terminal/outcome and priority |
| CH-A13 | Chulane | `Psychosis Crawler` threatened while ability triggers or multiple players in game | Protect draw-damage payoff if credible; actual damage only via engine | No fabricated table damage |
| CH-B01 | Opponent | Chulane is on battlefield with two cheap bounce creatures but another opponent has an immediate lethal threat | Respond to immediate victory pressure, not always attack Chulane | Chosen target priorities |
| CH-B02 | Opponent | Chulane becomes engine with public `Lonis`/`Academy Manufactor` and Clue generation | Prioritize high leverage piece as determined by real target legality; not naive highest mana value | Precision of meaningful removal target |
| CH-B03 | Opponent | Wipe legitimately available; Chulane has 4 creatures, player B has 5, acting opponent has their own 6 | Weigh own casualties and total opponents, not `2.5x` unconditional wipe | Bad-wipe-while-ahead, opportunity rate |
| CH-B04 | Opponent | Removal spell has several legal permanent targets, one Chulane engine and one harmless mana rock | Choose strategic target under visible board state; reject 'always target most removed globally' | Removal target worth and baseline |
| CH-B05 | Opponent | Legal Counterspell held with enough mana, Chulane triggers draw/land after a creature cast | Counter creature only when expected effect outvalues later threat; cannot counter already-resolved Chulane trigger with a normal counterspell | Legal stack object / utility |
| CH-B06 | Opponent | Six-player battle with Chulane + four other opponents, competing lethal clocks | Interaction balances table threat without overfocus; never assume any unseen private cards | Win share per seat / opponent focus |
| CH-B07 | Opponent | Blue deck has zero legal counter options, public Chulane cast is on stack | Can't magically respond even if external mix says `19% Counter` | `no_fake_reaction` |
| CH-B08 | Opponent | Same nominal board as CH-B07, but Counterspell in private hand and affordable (actor-only) | Other players do not receive the hidden card; the actor can consider it | Actor privacy negative controls |
| CH-C01 | All | Same seed, same versions, same pod, fresh-process twin | Deterministic XMage semantic outcome and policy decision fingerprints where stable | Twin/replay comparison |
| CH-C02 | All | Candidate policy chooses off-menu option / stale decision | Rejected without effect; absolutely no fallback | Fail-closed violations |
| CH-C03 | All | 6P heavy-trigger stack with Chulane token board | Bounded time/RSS, no loops or private leak; no claim until runtime tested | CPU, memory, failure and decision counts |
| CH-C04 | All | Candidate reports high win share but worsens 4P deck ranking agreement | Separate playing strength from ranking/optimization distortion | `scripts/rank_sensitivity.py` verdict |

## Recommended offline analysis tables

1. `interaction_opportunities`: real offered actions by `game × seat × turn × decision_class × stack_pressure_bin × board_width_bin × pod_size`.
2. `interaction_choices`: chosen offered action, cancelled payment vs actual stack entry/resolution, utility components, policy and seed lock.
3. `target_appropriateness`: evaluation by public immediate win threat, commander/engine piece, own-board damage, opportunity cost and a blinded adjudicated acceptable-option set.
4. `chulane_engine_events`: Chulane alive, casts/creature triggers/draws/extra lands, Clue quantity, boardwipe events, paid protection, terminal actual result — do not infer outcomes from offered choice alone.

## Reporting gates

- **G0 DATA/TRUTH:** every evaluation uses allowed public fixtures or owner-approved but never exported local deck snapshots; no `data/collections/**`.
- **G1 RULES:** native XMage allowed options, no phantom spell/target, fail-closed on unknown class/decider/stale ID; 4P default, 6P maximum.
- **G2 OBSERVABILITY:** per-seat available→selected→paid→stack→resolved chain separately captured; avoid treating 30 repeated priority pings as 30 independent human responses.
- **G3 STRATEGY:** report the adjudicated acceptable-option rate for **every** prespecified scenario and list every changed decision with a concrete strategic reason. No made-up numeric success threshold, no assumption that a different choice necessarily wins more.
- **G4 REPRODUCIBILITY:** fixed seed/pod rotations, frozen pilot/deck source, identical engine bridge, monotonic decisions and privacy; compare candidate vs baseline on matched blocks.
- **G5 STRENGTH:** actual full games to terminal, with failures shown, seat-rotated win shares/CI and ranking sensitivity; *no* success claim from one smoke, one selected seed, or a structural model.
- **G6 PERFORMANCE:** measure per-decision overhead, heap/RSS, game throughput, timeouts, loops especially 6P.
- **G7 ROLLBACK:** if a gate fails, leave external behavior prior disabled and retain previous stable strategy.

**A/B enrollment:** Work through 4P (Chulane + three opponents) first; 6P only after relevant readiness and 6P replay gaps assessed. The user has not authorized any operational 7+/8P game.

**Current verdict:** `DESIGN_COMPLETE`, `RULES_FIXTURES_NOT_CREATED`, `TESTS_NOT_RUN`, `STRATEGY_CHANGES_NOT_IMPLEMENTED`.

## References

- [Phase-5 audit](PLAYGROUP_LIVE_PHASE5_AI_SPARRING_PILOT_AUDIT_20261108.md)
- [Playgroup Sparring official methodology](https://playgroup.gg/playgroup-live/how-sparring-works)
- `data/deck_guides/guides/chulane.json` (MODELED, not verified match outcomes)
- `scripts/pilot_decision_report.py`, `scripts/threat_report.py`, `scripts/rank_sensitivity.py` (existing Lab tools)
