# RQ-A2 — MTG Rules Authority Gates (for Sol High)

Muse does not resolve official Comprehensive Rules questions. Each packet below carries the
exact candidate source, the smallest runtime fixture (where feasible), the actual observed
behavior, and the precise question. Independent work is complete; nothing here blocks the
terminal disposition (all gates concern rule-text interpretation, not architecture).

## AUTHORITY_GATE-1 (U2): CR 800.4a vs 800.4d — remaining players' LTB triggers off mass leave-game removals

- **Source**: `rules-engine/.../mechanics/sba/player/PlayerLeavesGameProcessor.kt:50-56`
  (documented simplification: remaining players' leaves-the-battlefield triggers off these
  mass removals don't fire; the leaver's own never fire).
- **Fixture** (`evidence/ARGENTUM_AUTHORITY_PROBES.json`, gate U2): 4P FFA seed 7101. B steals
  A's Bears (Act of Treason), C fields driver-local `RQ-A2 LTB Watcher`
  ("Whenever a card leaves the battlefield, you gain 1 life", ANY binding), B concedes with
  5 owned permanents.
- **Observed**: theft reverts to A (projected control back to A, Bears on A's board);
  B marked left; pod continues; C life 20 → 20 (Watcher fired zero times off 5 objects
  leaving the game); no trigger decisions raised for C in the following round.
- **Question**: when a player leaves and all objects they own leave the game en masse, does
  CR 800.4a/800.4d require the remaining players' leaves-the-battlefield triggers to fire
  (with the leaver's own triggers excluded)? If yes, the silence is a defect; if the mass
  removal is not a battlefield-exit event for trigger purposes, the silence is correct.

## AUTHORITY_GATE-2 (U2b): CR 800.4c — static-ability exile of leaver-controlled objects

- **Source**: same file, second documented simplification (exiling an object the leaver
  controlled via a static ability on a permanent owned by another player).
- **Fixture**: none executed (no minimal live fixture built; proposed: O-Ring-style static
  exile hosted by another player, leaver leaves, observe the exiled card).
- **Question**: what must happen to such objects under CR 800.4c, and does the documented
  simplification deviate? (Lower priority: narrow card-shape surface.)

## AUTHORITY_GATE-3 (U3): CR 805.4d — per-opposing-teammate step-trigger fan-out in 2HG

- **Source**: `rules-engine/.../event/TriggerMatcher.kt:1712-1731` ("the trigger fires once").
- **Fixture** (gate U3): 2HG seed 7201, T0A fields driver-local `RQ-A2 Upkeep Ping`
  ("At the beginning of each opponent's upkeep, deals 1 to that player"); advance to the
  opposing team's upkeep.
- **Observed**: upkeep reached; exactly ONE trigger on the stack (`maxStackTriggers=1`);
  shared life 30 → 29 (one damage, both seats resolve 29 via shared life).
- **Question**: must a nonactive player's "each opponent's step" trigger fire once per
  opposing teammate (twice, one per member of the opposing 2HG team), or once? If per
  teammate, the single firing is a defect (bounded: 2HG/team step triggers).

## AUTHORITY_GATE-4 (U16-DEFECT-2): CR 708.5 — controller vision of own face-down exiled cards

- **Source**: `rules-engine/.../view/ClientStateTransformer.kt:781` (face-down masking applies
  only when `isSpectator || controllerId != viewingPlayerId`; the controller sees the true
  identity in exile without any `MayLookAtInExile` grant).
- **Fixture** (`evidence/ARGENTUM_HIDDEN_INFO_ADVERSARY.json`): 4P Commander pod; P2 hand card
  exiled face-down with a look grant for P3 only.
- **Observed**: P2's server DTO carries the TRUE name; P3's DTO carries it via `revealedName`
  (grant path correct); P0/P1/spectator see the masked entry; the Gym observation masks it
  for ALL viewers including P2 (DTO/gym divergence).
- **Question**: may a controller see their own face-down card in exile without an effect
  permitting it (CR 708.5 bars looking at face-down cards in other zones), or must the DTO
  mask the controller exactly as the Gym observation does? (Related: U16-DEFECT-1, the draw
  event leak, is classified as an engine defect outright — no Rules interpretation needed —
  but Sol High may re-scope its severity.)

## AUTHORITY_GATE-5 (U15): CR 603.3b — automatic same-controller trigger ordering

- **Source**: `rules-engine/.../event/TriggerProcessor.kt:67-74` (APNAP-ordered detector output;
  same-controller order = detector order, no question asked). RQ-A1 decision-matrix row 17
  ("trigger ordering INDEX_BASED via ChooseOptionDecision") is CORRECTED: the cited pause
  sites are modal-mode choice (:1066) and opponent-chooser (:1481), not trigger ordering.
  Trigger-related PendingDecisions are may-questions (YesNo/BatchYesNo), modal/target/number
  choices — all authoritative.
- **Fixture** (`evidence/ARGENTUM_DECISION_FRESHNESS.json`, U15): two different same-controller
  triggers (dies + leaves) fire simultaneously; both resolve (life 20 → 24) with ZERO ordering
  question raised.
- **Question**: is engine-automatic ordering of a controller's simultaneous triggers an
  acceptable simplification where outcomes are independent, or must the controller be asked
  (at least when order is material)? Scope of any required fix.

## AUTHORITY_GATE-6 (U1-observation): priority in declare-attackers with no possible attackers

- **Source**: turn/combat advancement (TurnManager/AttackPhaseManager area).
- **Fixture** (RQ-A2 U19 G1 + U1 G2-early): step histogram shows direct
  `BEGIN_COMBAT → END_COMBAT` transitions with no `DECLARE_ATTACKERS`/`DECLARE_BLOCKERS`
  priority windows when no creature can attack.
- **Question**: must players receive priority in the declare-attackers step even with no
  possible attackers (CR 117/508), or is fast-forwarding acceptable? If priority is owed,
  the skip is a defect (priority-window loss, e.g. for combat tricks).
