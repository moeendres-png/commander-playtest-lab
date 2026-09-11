# WS55R — Forge Engine Gaps (RQ-C3 impact update)

Forge source is READ-ONLY in WS55R (pin `66caae16`, verified). Nothing below
was changed. Evidence classes: DIRECTLY_VERIFIED (WS55R runtime journals) or
CODE_DERIVED (source reads at the pin). No Rules verdict is attached to any
item. Items EG-1..EG-6 are carried from WS55 with RQ-C3 impact restated;
A04/C01/G04 roots are now closed with exact-fixture evidence or precise
architecture determination.

## EG-1 — Combat ordering offered only with `orderCombatants=true` (UNCHANGED, now NONBLOCKING)

- `Combat` reads `getRules().hasOrderCombatants()` (`Combat.java:78`);
  headless default false; WS55 provider exposes the flag as journaled fixture
  config only.
- RQ-C3 impact: generic `ordering` is REMOVED from the First-Wave union
  (E02 delta). E02 is READY unconditionally
  (`WS55R_E02_RECLASSIFICATION.json`). The orderBlockers 2-perm proof and the
  zone-move 6/6 proof are preserved as non-required capability
  (`RECLASSIFIED_NONBLOCKING`). No engine change requested.

## EG-2 (EBO-1) — ETB `+1/+1` counter placement yields zero (CONFIRMED under exact A04 fixture)

- WS55 shape: Stonecoil Serpent X=2 entered 0/0 and died; TravelPrep damage
  equaled base power; replacement audit milestone absent.
- WS55R exact fixture: Serpent X=3 announced by value (d954), 3 G paid
  natively (d955-957), spell resolved (d958-962) — 0 counters placed, 0/0
  died natively, zero `chooseSingleReplacementEffect:CALLED` milestones in
  1282 frames, no replacement_effect frame. Base ETB materialization fails
  with X paid (inner xPaid-vs-Moved-RE cause not isolated read-only).
- RQ-C3 impact: A04 replacement ordering can never arise (no applicable
  replacements). Engine-change packet layer (a) in
  `WS55R_A04_REPLACEMENT_ORDERING.json`. No provider-only repair is
  conformant.

## EG-3 — Regen-shield destroy handling bypasses generic ordering (UNCHANGED context)

- Drudge-95/196 + Rest in Peace shape: shield applied, other creature exiled,
  zero audit calls (dedicated destroy path, not generic
  `ReplacementHandler` ordering).
- RQ-C3 impact: historical context for A04 only (one of the three WS55
  non-exact shapes). The exact A04 fixture supersedes it; classification
  rests on `WS55R_A04_REPLACEMENT_ORDERING.json`. No engine change requested
  beyond the A04 packet.

## EG-4 — Stack-spell targeting candidacy is empty (CONFIRMED under corrected C01 fixture)

- WS55 shape (Merfolk/Berserker stack spell): `chooseTargetsFor` reached with
  `getAllCandidates` raw=0; pitch fizzled.
- WS55R corrected fixture (Elves stack spell, 5 Islands, Frog pitch):
  pitch-variant ACT authoritatively selected (d713/o3, exact single-match
  binding, engine ACCEPTED_CONTINUED) — then ZERO provider callbacks (no
  CANDIDATES milestone, no target/cost frames in 837 frames); spell stays in
  hand; life 40; Elves resolves natively.
- Source-derived mechanism: `TargetRestrictions.getAllCandidates`
  (`TargetRestrictions.java:568-593`) enumerates Players + Cards in tgtZone
  only; it never consults the stack for SpellAbilityStackInstances, so FoW's
  `TargetType$ Spell` has no resolvable candidate. Abort occurs inside
  engine `PlaySpellAbility.playSpellAbility` pre-cost requisites with silent
  rollback (exact single predicate UNKNOWN, non-blocking).
- RQ-C3 impact: C01 stages 6-11 NOT_REACHED (fail closed). No provider-only
  repair is conformant (any continuation would reconstruct targeting
  legality). See `WS55R_C01_COST_PITCH.json`.

## EG-5 — Engine lists unviable ACTs; silent decline on play (CONFIRMED as FoW-pitch presentation)

- `getAllPossibleAbilities(actor, true)` offers ACTs that cannot complete
  (here: both FoW variants incl. pitch, plus all five Island mana ACTs —
  all correctly offered); selecting the pitch variant completes silently
  nothing (no frame, no event, no error; spell in hand).
- The provider correctly does NOT filter (filtering would reconstruct
  legality, WS55 T6). The harness scripts viable options and asserts
  consequences; the C01 journal records the silent decline as engine
  behavior with exact binding evidence (d713).
- RQ-C3 impact: none beyond EG-4 (presentation layer of the same gap). No
  engine change requested by WS55R (offer-set authority preserved as
  required).

## EG-6 — Uncapped X announcement bounds (REUSED conformantly)

- `AbilityUtils.getAnnouncementBounds` defaults X max to `Integer.MAX_VALUE`;
  WS55 conformant ranged-integer path (bounds verbatim + by-value submit +
  native validation) reused unchanged: X=3 submitted by value (d954,
  `NUMRANGE:min=0:max=2147483647:announce=X:value=3`), engine-accepted,
  3 G paid.
- RQ-C3 impact: none (X seam PROVEN, A04-ready). No engine change requested.

## G04 concession — initiated-only by engine construction (DETERMINED, honest gap)

- Authoritative API `Player.concede()` (`Player.java:1989`, no checks) with
  native SBA transition (`checkGameOverCondition` → `Game.onPlayerLost`
  800.4 cleanup) exists, but initiation lives entirely in the GUI assembly
  (`IGameController.concede`, `PlayerControllerHuman.concede`,
  GameMenu/VMatchUI/shortcuts). `PlayerController` (forge-game Decision API)
  has no concession method, so no offer set exists to externalize and no
  current-principal action identity can be projected.
- No permanent CONCEDE option fabricated (would reconstruct an offered
  choice). No orchestration injection performed (would prove orchestration,
  not a Decision seam). See `WS55R_G04_CONCESSION.json`.
- RQ-C3 impact: G04 NOT_READY (seam gap + AG-1). Engine-offer addition or
  Coordinator architecture ruling required; both out of WS55R scope.

## Non-gaps (by design, preserved)

- `orderCosts`/`CostTap`/`CostAddMana`/mandatory-life auto paths mirror the
  Human controller exactly (no discretion automated).
- Concession never-offered is engine construction, not a missing seam
  (recorded as the G04 gap above, not as a defect).
