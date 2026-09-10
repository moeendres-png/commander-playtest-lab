# WS55 — Forge Engine Gaps & Behavior Observations

Forge source is READ-ONLY in WS55. Nothing below was changed. Items are
recorded so the Coordinator / RQ-C2 / future engine work can disposition them.
Evidence classes: DIRECTLY_VERIFIED (runtime journals) or CODE_DERIVED
(source reads at pin `66caae16`). No Rules verdict is attached to any item.

## EG-1 — Combat ordering offered only with `orderCombatants=true`

- `Combat` reads `playerWhoAttacks.getGame().getRules().hasOrderCombatants()`
  (`Combat.java:78`); the flag defaults false and is set only from GUI
  preferences in hosted/quest matches. The headless qualification provider
  never sets it.
- Consequence: `orderBlockers/orderBlocker/orderAttackers` are engine-skipped
  (`Combat.java:493-552` fast paths) unless the session sets the flag.
- WS55 proof: W-combat-A (default) shows 0 order frames over a real
  double-block; W-combat-B (`COMMANDER_LAB_FORGE_ORDER_COMBATANTS=1`) shows
  the 2-permutation offer + binding + legacy damage. Same engine, same
  provider — the difference is configuration only.
- First-wave impact: RQ-C1 E02 step 3 ("both blocker-order permutations
  offered") is reachable only under `orderCombatants=true`. The WS55 provider
  exposes this as fixture config (journaled per run); the Coordinator must
  confirm the execution-time setting with RQ-C2/Sol (it selects the
  damage-assignment Rules variant).
- No engine change requested by WS55 (seam exists; reachability is config).

## EG-2 (EBO-1) — `+1/+1` counter placement yields zero in witnessed shapes

- Stonecoil Serpent cast with announced X=2 (native receipt proven at
  resolution, `(X=2)`) entered as 0/0 and died immediately (no counters).
- Travel Preparations resolved (`fizzled=false`, "puts a +1/+1 counter on
  Winding Constrictor") yet the recipient later dealt base power (2), i.e.
  zero counters present.
- In both shapes the replacement audit milestone
  (`chooseSingleReplacementEffect:CALLED`) is ABSENT — replacements were
  never applicable, consistent with zero counters placed.
- The X-decision seam itself is proven (bounds offered, value accepted,
  X=2 at resolution); only the downstream counter outcome is affected.
- First-wave impact: RQ-C1 A04's replacement-ordering event never arises
  (no applicable replacements). No Rules verdict attached; RQ-C2 /
  Forge-remediation scope. WS55 does NOT propose an engine change (root cause
  not isolated to a seam; provider-only repair would fabricate Rules).

## EG-3 — Regen-shield destroy handling bypasses generic ordering

- Drudge-95 (regen shield active) blocked Drudge-196 with Rest in Peace on
  the battlefield: two applicable destroy replacements (shield vs exile).
  The audit milestone is absent; the shield applied (95 survived tapped)
  while RIP exiled 196 — the engine never consulted
  `chooseSingleReplacementEffect`.
- Consistent with regeneration using a dedicated destroy path rather than
  the generic `ReplacementHandler` ordering point.
- First-wave impact: same as EG-2 for A04 (no multi-replacer order offered).

## EG-4 — Stack-spell targeting candidacy is empty

- Force of Will (pitch variant, Merfolk verifiably on stack) reached
  `chooseTargetsFor` with `getAllCandidates` returning ZERO raw candidates
  (audit milestone `CANDIDATES:raw=0`); the cast fizzled silently (no frame,
  by provider design for empty sets).
- Battlefield/player targeting is proven working (Bolt, Fireball, Piracy,
  Murder-singleton, Judith-trigger, TravelPrep). Only stack-spell candidacy
  observed empty (one shape; Cryptic-counter shares the script pattern).
- First-wave impact: RQ-C1 C01 needs spell targeting → C01 NOT_READY.
  J02 Delina targets battlefield creatures (script-checked) → unaffected.

## EG-5 — Engine lists unviable ACTs; silent decline on play

- `getAllPossibleAbilities(actor, true)` can offer ACTs that cannot complete
  (unpayable Judith with 1 land; untargetable Murder with empty boards).
  Selecting one returns no frame, no event, no error — the game continues.
- This is engine behavior, correctly NOT filtered by the provider (filtering
  would reconstruct legality). The harness must script viable options; WS55
  journals assert `spell_resolved` for scripted casts as workflow discipline.
- No engine change requested (offer-set authority preserved as required).

## EG-6 — Uncapped X announcement bounds

- `AbilityUtils.getAnnouncementBounds` defaults X max to `Integer.MAX_VALUE`
  (Stonecoil/Fireball), so exact enumeration is infeasible; WS55 added the
  conformant ranged-integer path (J8: engine bounds verbatim + by-value
  submit + native range validation).
- No engine change requested.

## Non-gaps (by design)

- Concession is never engine-offered (no `PlayerController` method offers
  it); initiation-only path. Not a missing seam.
- `orderCosts`/`CostTap`/`CostAddMana`/mandatory-life auto paths mirror the
  Human controller exactly (no discretion automated).

## Authority gates for Sol High (blocking classification, not WS55 scope)

- AG-1: G04 control-change vs concession equivalence (104.3a/800.4).
- AG-2: D06 mode-subset offerability vs target-legality pruning (601.2b/115).
- AG-3: E02 damage-split uniqueness (510.1c-d, 702.19).
