# RQ-C1 Rules Authority Queue (Coordinator adjudication)

Status: QUEUED for Sol High. Muse makes NO final ambiguous Magic Rules
adjudication. Every packet below carries: scenario ID, cards, initial state
(ref scenario file), exact decision sequence (ref scenario file), relevant
current Comprehensive Rules sections (PROPOSED, unverified against the current
CR document), relevant Oracle text (Scryfall metadata mirror, METADATA_ONLY),
relevant official rulings (NONE collected: no Gatherer access in this
workstream), proposed expected state/events (ref scenario file), unresolved
ambiguity, exact question, and what future engine execution should assert.

Oracle-text metadata: `/tmp/opencode/rqc1_oracle.json` is a build-time
working file, NOT a corpus artifact (Scryfall mirror, METADATA_ONLY).
Oracle identifiers are embedded per card in each scenario file.

Conventions: `AUTHORITY_GATE_REQUIRED` scenarios (G04, K02) block their own
candidate execution until adjudicated. `READY_FOR_COORDINATOR_RULES_ADJUDICATION`
scenarios carry mechanically-derived proposals for confirmation.
`READY_FOR_CANDIDATE_EXECUTION` scenarios (A02, C02, F04) are Oracle-direct
with no interpretive step; listed for completeness, no question asked.

## Q-A01 (RQ-C1-A01, Rest in Peace + Doom Blade)

- Proposed CR: 614 (replacement effects), 400.7 (zone-change identity).
- Oracle: Rest in Peace (exile-instead sentence), Doom Blade.
- Proposed: destroy event replaced; Bear exiled directly; no dies triggers.
- Ambiguity: none material; confirm replacement-vs-trigger classification and
  that no graveyard touch occurs (double-check vs any ETB-exile-everything nuance: graveyards empty at setup).
- Question: Confirm the expected event chain (REPLACEMENT_APPLIED, no graveyard touch, no triggers).
- Future assert: exile location, empty graveyard, zero triggers.

## Q-A03 (RQ-C1-A03, Drudge Skeletons regeneration)

- Proposed CR: 614 (replacement), 702.13 (regenerate reminder semantics).
- Oracle: Drudge Skeletons activation + reminder text.
- Proposed: shield created in response; applied at destruction (tap, remove from combat, heal).
- Ambiguity: optional-application mechanics (may/decline offer) and shield timing.
- Question: Confirm shield-creation timing (must pre-exist destruction) and the tap/remove-from-combat/heal outcome for a non-combat destroy case.
- Future assert: tapped Bear-free survival, damage cleared, {B} paid.

## Q-A04 (RQ-C1-A04, Doubling Season + Hardened Scales + Stonecoil X=3)

- Proposed CR: 616 (multiple replacement effects, affected-controller order).
- Oracle: both enchantments' counter sentences; Serpent enters-with-X.
- Proposed: both orders legal; Scales-first yields 8, Season-first yields 7; scripted Scales-first.
- Ambiguity: who orders (controller of affected permanent) and whether both orders must be offered.
- Question: Confirm ordering authority (P0) and the 8-vs-7 arithmetic for X=3.
- Future assert: offered set size 2; terminal 8 counters on scripted order.

## Q-B01 (RQ-C1-B01, five Wardens)

- Proposed CR: 603 (triggers), APNAP stacking, same-controller ordering.
- Oracle: Soul Warden.
- Proposed: 5 triggers; stack P0,P0,P1,P2,P3 (bottom-up); P0 orders its two; life 42/41/41/41.
- Ambiguity: none material; confirm APNAP bottom-up order and intra-controller choice.
- Question: Confirm stack order and P0's two-trigger ordering right.
- Future assert: resolution order P3,P2,P1,P0b,P0a; exact life.

## Q-B02 (RQ-C1-B02, Flickerwisp)

- Proposed CR: 603.7 (delayed triggers), 400.7 (new object).
- Oracle: Flickerwisp both sentences.
- Proposed: delayed trigger created at ETB resolution; fires next end step though Wisp remains; Bear returns new.
- Ambiguity: delayed-trigger source independence (trigger fires even if Wisp leaves? not tested here; Wisp remains).
- Question: Confirm creation point and return-under-owner as new object.
- Future assert: Bear battlefield-new; stack empty after end step.

## Q-B03 (RQ-C1-B03, Felidar Sovereign)

- Proposed CR: 603.4 (intervening-if).
- Oracle: Felidar Sovereign upkeep sentence.
- Proposed: trigger created at 40; Bolt to 37 in response; resolution recheck fails; no win.
- Ambiguity: two-point checking (creation + resolution) for this templating.
- Question: Confirm that the `if` here is an intervening-if gating both points (not a resolution-only condition like Mayael's Aria, which was rejected for this slot for that reason).
- Future assert: no win at 37; game continues. Variant path (upkeep below 40: no trigger) noted for later harnesses.

## Q-B04 (RQ-C1-B04, Kokusho + Blood Artist; Murder destroyer)

- Proposed CR: 603 (dies triggers), 113.7a/603.10 (LKI), APNAP, 700.4 (dies).
- Oracle: Blood Artist, Kokusho. Murder text UNVERIFIED (general knowledge): confirm `Destroy target creature` {1}{B}{B} or substitute an Oracle-confirmed equivalent before execution.
- Proposed: both triggers fire; stack P0-bottom/P1-top; Kokusho resolves (P0/P2/P3 -5, P1 +15); Artist resolves (P1 -1, P0 +1); final 36/54/35/35.
- Ambiguity: Kokusho life-gain-equals-lost arithmetic across 3 opponents (15).
- Question: Confirm fan-out arithmetic and APNAP resolution order.
- Future assert: exact life totals; Kokusho in graveyard.

## Q-C01 (RQ-C1-C01, Force of Will)

- Proposed CR: 601 (casting), 602 alternative/additional costs family.
- Oracle: Force of Will both sentences.
- Proposed: pitch route (1 life + exile blue card) and hard-cast 3UU both offered; scripted pitch; Elves countered.
- Ambiguity: none material; confirm both routes must be offered.
- Question: Confirm pitch-vs-hard-cast offer duality and Island-as-blue-card eligibility.
- Future assert: P0 39; Island exiled; Elves in graveyard uncast.

## Q-C03 (RQ-C1-C03, Fireball X=5, 2 targets)

- Proposed CR: 601 (cost computation), 601.2d (division declaration; proposed number only).
- Oracle: Fireball both sentences.
- Proposed: cost 5+X-route + {R} + {1} second-target = 7; division 2/2 with 1 remainder lost; P1/P2 at 38.
- Ambiguity: remainder handling (lost, not assigned) and division-being-determined (no chooser).
- Question: Confirm 7-mana total, 2/2 split, remainder lost, no chooser-division offered.
- Future assert: life 38/38; no division decision in offered set.

## Q-C04 (RQ-C1-C04, Fierce Guardianship; Cultivate target)

- Proposed CR: alternative-cost condition gating.
- Oracle: Fierce Guardianship. Cultivate text UNVERIFIED: confirm or substitute an Oracle-confirmed noncreature spell before execution.
- Proposed: free cast legal while P0 controls commander (Ghalta body); Cultivate countered.
- Ambiguity: condition check point (on casting).
- Question: Confirm commander-control gating and zero-mana payment legality.
- Future assert: zero mana paid; Cultivate in graveyard unresolved.

## Q-D01 (RQ-C1-D01, Cryptic Command counter + bounce)

- Proposed CR: modal-spell rules (proposed section only): choose-two distinctness, per-mode targets, mode-order resolution.
- Oracle: Cryptic Command.
- Proposed: 6 two-mode combinations offered; no repeats; scripted pair resolves counter-then-bounce.
- Ambiguity: mode-order resolution and repeat prohibition.
- Question: Confirm distinctness, offer cardinality 6, and resolution in mode order.
- Future assert: Elves in graveyard; Bear in P2 hand.

## Q-D02 (RQ-C1-D02, Twincast + Bolt)

- Proposed CR: 707 (copying spells; proposed section only).
- Oracle: Twincast; Lightning Bolt.
- Proposed: stack-copy created (P0 controls, new stack object); may-choose-new-targets exercised (P2); 3+3 damage; both spells to graveyard.
- Ambiguity: copy controllership and new-target legality scope.
- Question: Confirm copy is a P0-controlled new stack object and retarget-to-P2 is legal.
- Future assert: P1/P2 at 37; stack empty; no extra copies.

## Q-D03 (RQ-C1-D03, Bolt + Growth)

- Proposed CR: stack LIFO (proposed), target-legality recheck (proposed 608.2b), lethal-damage SBA.
- Oracle: Bolt; Growth.
- Proposed: Growth resolves first (5/5); Bolt marks 3 (non-lethal); Bear survives damaged.
- Ambiguity: none material.
- Question: Confirm LIFO order with per-resolution legality recheck.
- Future assert: Bear alive 5/5 with 3 marked; both spells in graveyards.

## Q-D04 (RQ-C1-D04, Phantasmal Image + Doom Blade)

- Proposed CR: 707 (copy entry), 603 (becomes-targeted trigger), illegal-target fizzle.
- Oracle: Image; Doom Blade (Image-as-Bear is nonblack: legal target).
- Proposed: Image enters as Bear+Illusion+trigger; Blade targets Image; trigger resolves first (sacrifice); Blade fizzles.
- Ambiguity: trigger-vs-spell resolution order and fizzle on all-targets-illegal.
- Question: Confirm sacrifice pre-emption and Blade-with-no-effect outcome.
- Future assert: Image sacrificed (graveyard); Blade in graveyard no-effect; original Bear alive.

## Q-D05 (RQ-C1-D05, Rolling Thunder X=4, 2/1/1)

- Proposed CR: division-declaration rules (proposed).
- Oracle: `divided as you choose among any number of targets`.
- Proposed: partitions of 4 across 3 targets offered; scripted 2/1/1; Bear destroyed; P2/P3 at 39.
- Ambiguity: partition-sum-equals-X enforcement.
- Question: Confirm offer shape (all integer partitions summing to 4) and scripted outcome.
- Future assert: Bear in graveyard; P2/P3 39.

## Q-D06 (RQ-C1-D06, Casualties of War 3 modes)

- Proposed CR: choose-one-or-more modal rules (proposed).
- Oracle: Casualties of War. Ornithopter text UNVERIFIED: confirm 0/2 artifact creature or substitute any vanilla artifact before execution.
- Proposed: 31 nonempty subsets offered; scripted artifact+creature+land with one typed target each; all three destroyed in mode order.
- Ambiguity: subset cardinality 31 and per-mode target typing.
- Question: Confirm offer cardinality and mode-order resolution.
- Future assert: Ornithopter + Bear + Forest in graveyards.

## Q-E01 (RQ-C1-E01, Propaganda multi-defender)

- Proposed CR: 508 (declare attackers), attack-restriction costs.
- Oracle: Propaganda per-creature sentence.
- Proposed: Bear-A->P0 pays {2}; Bear-B->P2 pays 0; damage 2+2; P0/P2 at 38.
- Ambiguity: per-creature (not per-attack) payment and defender mapping.
- Question: Confirm per-P0-bound-creature tax and legality of the split attack.
- Future assert: {2} paid once; life 38/38.

## Q-E02 (RQ-C1-E02, Tyrant double-block)

- Proposed CR: 509 (blockers/ordering), 510 (damage assignment), 702.19 (trample; proposed).
- Oracle: Carnage Tyrant (7/6 trample); blockers vanilla + 1/1.
- Proposed: order Bear-first offered among 2 permutations; assignment 2+1+4-rollover; blockers destroyed; P0 at 36.
- Ambiguity: lethal-first enforcement and remainder-to-player.
- Question: Confirm 2-to-Bear/1-to-Elves/4-to-P0 split on scripted order.
- Future assert: blockers in graveyard; Tyrant alive; P0 36.

## Q-E03 (RQ-C1-E03, deathtouch block)

- Proposed CR: 702.2 (deathtouch; proposed), 510 simultaneous damage, lethal SBA.
- Oracle: Deadly Recluse reminder.
- Proposed: 1 deathtouch damage lethal to Bear; 2 damage lethal to 1/2 Recluse; mutual destruction; no player damage.
- Ambiguity: none material.
- Question: Confirm mutual-destruction outcome.
- Future assert: both in graveyards; life unchanged.

## Q-F01 (RQ-C1-F01, Rampant Growth)

- Proposed CR: search-library rules incl. fail-to-find (proposed 701.19b), shuffle.
- Oracle: Rampant Growth.
- Proposed: searcher-only visibility; found-path + fail-to-find both offerable; scripted found; shuffle journaled.
- Ambiguity: fail-to-find offerability for a basic-land search.
- Question: Confirm fail-to-find must be offerable and the shuffle must be a journaled RNG event.
- Future assert: tapped Forest; journaled shuffle; counts-only for others.

## Q-F02 (RQ-C1-F02, Duress)

- Proposed CR: reveal/choose/discard sequencing (proposed).
- Oracle: Duress.
- Proposed: P1 hand revealed to P0 only; only noncreature-nonland offered; chosen discarded; rest private again.
- Ambiguity: reveal scoping (to-controller-of-spell only) and privacy restoration.
- Question: Confirm P2/P3 observe counts only throughout, and post-resolution privacy.
- Future assert: chosen card in graveyard; rest private to P1.

## Q-F03 (RQ-C1-F03, Willbender)

- Proposed CR: 702.36 (morph; proposed), turn-face-up special action, single-target redirect.
- Oracle: Willbender both sentences.
- Proposed: face-down identity hidden (2/2 public); turn-up special action; trigger retargets Bolt Bear->Elves; Elves dies; Bear lives.
- Ambiguity: special-action timing (no response) and new-target legality.
- Question: Confirm hidden-until-turn-up, unrespondable turn-up, and Elves as legal new target.
- Future assert: Willbender face-up; Elves in graveyard; Bear alive.

## Q-G01 (RQ-C1-G01, Council's Judgment 2-2)

- Proposed CR: will-of-council voting (proposed).
- Oracle: Council's Judgment.
- Proposed: sequential open votes P0..P3; scripted 2-2 tie; both permanents exiled.
- Ambiguity: vote ordering/ openness and tie-inclusive exile.
- Question: Confirm turn-order open voting and that ties exile all tied permanents.
- Future assert: Bear + Elves exiled.

## Q-G02 (RQ-C1-G02, commander movement + tax)

- Proposed CR: 903.9a (movement choice; proposed), 903.8 (tax; proposed).
- Oracle: Ghalta (body). Murder text UNVERIFIED (see Q-B04).
- Proposed: owner offered graveyard-vs-command-zone; scripted command zone; recast costs 8+2=10; ETB zero (empty hand).
- Ambiguity: tax arithmetic on first recast (+2).
- Question: Confirm movement offer duality and 10-mana recast total.
- Future assert: Ghalta battlefield; cast-count 1.

## Q-G03 (RQ-C1-G03, commander damage; REDESIGNED seeding)

- Proposed CR: commander-damage loss (proposed 704.5c-adjacent), 800-series loss handling.
- Oracle: Ghalta (12/12 trample).
- Proposed: 12 pre-ledgered (PRE_DECISION construction); native unblocked 12 hit totals 24; P1 loses.
- Ambiguity: ledger-seeding locus (workstream-design, adjudicated XHIGH: PRE_DECISION construction restore before the first decision, not mid-combat injection) and loss threshold 21.
- Question: Confirm loss-at-21 with summed ledger and that pre-game ledger seeding is a legitimate fixture shape.
- Future assert: P1 lost; others remain.

## Q-G04 (RQ-C1-G04, Control Magic + leaver) — AUTHORITY_GATE_REQUIRED

- Proposed CR: 800.4 (leave-game cleanup; proposed).
- Oracle: Control Magic.
- Proposed: P0 leaves; P0-owned Aura leaves with P0; P1-owned Bear stays under P1.
- Ambiguity: cleanup sequencing (simultaneity vs ordering; Aura-vs-creature disposition; control revert path).
- Question: EXACT: when the Aura controller leaves while the owner of the enchanted creature remains, does the Aura leave the game with its owner and does control revert to the creature owner with no gap? What is the exact cleanup order to assert?
- Future assert (pending answer): Bear under P1; Aura gone with P0. DO NOT execute before adjudication.

## Q-G05 (RQ-C1-G05, Braids)

- Proposed CR: end-step trigger with may-sacrifice; each-opponent handling order (proposed).
- Oracle: Braids full sentence.
- Proposed: P0 sacrifices land; P1/P3 sacrifice lands; P2 declines (no permanents), loses 2; P0 draws exactly 1.
- Ambiguity: turn-order handling and per-opponent consequence/draw counting (one draw per non-sacrificer).
- Question: Confirm handling order, type-filtered offers, and draw count 1.
- Future assert: P2 38; P0 +1 card; sacrificed lands in graveyards.

## Q-H01 (RQ-C1-H01, Clone under Humility)

- Proposed CR: 613 (layers; proposed): copy layer-1 before ability-removal/P-T-setting; timestamp-independence of cross-layer application.
- Oracle: Clone; Humility.
- Proposed: Clone copies Bear (2/2) in layer 1; Humility strips abilities + sets 1/1; final ability-less 1/1 regardless of cast order.
- Ambiguity: none beyond layer order; confirm timestamp-independence across layers.
- Question: Confirm layer-1-before-6/7b with timestamp-independence.
- Future assert: Clone 1/1 no abilities; Bear 1/1 no abilities.

## Q-H02 (RQ-C1-H02, Growth vs Frog both orders)

- Proposed CR: 613.7 (timestamp order; proposed).
- Oracle: Growth; Turn to Frog.
- Proposed: Growth-then-Frog = 1/1 blue Frog; Frog-then-Growth = 4/4 blue Frog.
- Ambiguity: base-setting vs modifier interaction across timestamps.
- Question: Confirm both finals (1/1 and 4/4) with color/type in both paths.
- Future assert: PATH_A 1/1; PATH_B 4/4.

## Q-I01 (RQ-C1-I01, Momentary Blink)

- Proposed CR: 400.7 (new object; proposed), attachment SBA, counters-cease.
- Oracle: Momentary Blink; Pacifism.
- Proposed: Bear exiled (counter ceases); Pacifism unattached to graveyard (owner P1); Bear returns new (plain 2/2).
- Ambiguity: Aura destination (owner graveyard) and no-reattachment.
- Question: Confirm counter-cease, Pacifism-to-P1-graveyard, clean 2/2 return.
- Future assert: Bear plain 2/2; Pacifism in P1 graveyard.

## Q-I02 (RQ-C1-I02, Reanimate)

- Proposed CR: zone-change identity (proposed 400.7), control-vs-ownership on reanimation.
- Oracle: Reanimate.
- Proposed: Bear (P1 graveyard) to battlefield under P0; P0 loses 2 (mana value 2); new object.
- Ambiguity: mana-value-as-life-loss value (2 for Bear).
- Question: Confirm owner/controller split and 2-life payment.
- Future assert: Bear P0-controlled/P1-owned; P0 38.

## Q-I03 (RQ-C1-I03, Traveler + Reap + Artist)

- Proposed CR: token lifecycle (proposed 111.8), dies triggers, token-ceases SBA (proposed 704.5d), cost-sacrifice timing.
- Oracle: Traveler; Reap; Artist.
- Proposed: Traveler death fires Artist + makes Spirit; Reap sacrifices Spirit (cost); token death fires Artist; token ceases (no graveyard card); P1 38, P0 42, P0 draws 2.
- Ambiguity: token-dies-fires-trigger-before-ceasing; token never a graveyard card.
- Question: Confirm trigger-on-token-death plus ceases-without-graveyard-card.
- Future assert: exact life; no token object anywhere; Traveler + Reap in graveyards.

## Q-J01 (RQ-C1-J01, Mana Crypt)

- Proposed CR: coin-flip Rules randomness (proposed); trigger conditioning.
- Oracle: Mana Crypt.
- Proposed: upkeep trigger; Rules-RNG flip journaled (domain win/loss); loss path 3 damage (P0 37); win variant no damage.
- Ambiguity: journal shape (deferred to execution contract; corpus requires the six journal fields).
- Question: Confirm flip-in-Rules-RNG with journaled outcome (no chooser).
- Future assert: journaled flip; life per path.

## Q-J02 (RQ-C1-J02, Delina)

- Proposed CR: d20 Rules randomness with band mapping; attack-trigger token copy; may-recur offer.
- Oracle: Delina full table text.
- Proposed: scripted 17 (15-20 band); tapped-attacking Bear-copy; may-roll-again offered, declined; token exiled at end of combat.
- Ambiguity: band boundaries (1-14 vs 15-20) and token characteristics (nonlegendary + exile clause).
- Question: Confirm 17 lands in the roll-again band, the token is nonlegendary with end-of-combat exile, and declining ends recursion.
- Future assert: journaled 17; one token created-then-exiled; no token remains.

## Q-J03 (RQ-C1-J03, Hymn)

- Proposed CR: at-random selection from hidden zone (proposed); no-chooser rule.
- Oracle: `Target player discards two cards at random`.
- Proposed: Rules-RNG 2-of-4 selection journaled; discarded public; retained private; NO hidden-choice offered.
- Ambiguity: none beyond no-chooser enforcement.
- Question: Confirm that no chooser decision may be offered for this selection.
- Future assert: journaled pair discarded; pair retained private.

## Q-K01 (RQ-C1-K01, Wrath accounting)

- Proposed CR: mass-destroy SBA; dies-including-self triggers; same-controller ordering; enters-vs-dies distinction.
- Oracle: Wrath (`They can't be regenerated`); Artist; Warden.
- Proposed: 3 Artist triggers (self + Warden + Bear), 0 Warden triggers; P0 orders 3; P1 -3 (37), P0 +3 (43).
- Ambiguity: Artist triggering on its own simultaneous death.
- Question: Confirm self-inclusive dies (Artist fires on itself) and zero Warden triggers (no ETB).
- Future assert: exact life; trigger counts 3/0.

## Q-K02 (RQ-C1-K02, cross-controller Clone) — AUTHORITY_GATE_REQUIRED

- Proposed CR: legend rule same-controller gating (proposed 704.5j); dies definition (proposed 700.4).
- Oracle: Clone; Ghalta (legendary); Artist (witness).
- Proposed: different controllers coexist; no transit; zero triggers.
- Ambiguity (second path): same-controller Clone-of-own-legend transit DOES occur; whether that transit fires dies triggers (700.4/704.5j interaction) is the interpretive half.
- Question: EXACT: (1) confirm cross-controller coexistence with no transit; (2) for the same-controller variant, does the legend-rule transit to graveyard count as dies for trigger purposes?
- Future assert (pending answer): coexistence + zero triggers now; same-controller path gated on answer. DO NOT execute the same-controller variant before adjudication.

## No-question list (Oracle-direct, READY_FOR_CANDIDATE_EXECUTION)

- RQ-C1-A02 (Fog): Oracle prevention sentence applied directly.
- RQ-C1-C02 (Altar's Reap): Oracle additional-cost + draw applied directly.
- RQ-C1-F04 (Preordain): Oracle scry reminder applied directly.

## Unverified-text flags (Oracle confirmation required before ANY candidate execution)

- Murder (B04, G02): confirm `Destroy target creature` {1}{B}{B} or substitute.
- Cultivate (C04): confirm text or substitute another noncreature spell.
- Ornithopter (D06): confirm 0/2 artifact creature or substitute any vanilla artifact.
