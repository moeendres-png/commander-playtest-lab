# Provider Neutrality (WS228)

## Requirement (S6 hard constraint)

The neutral pilot contract must not couple to XMage internals. The chosen
design (B) satisfies this by construction.

## What crosses the Lab→pilot boundary (chosen design)

- ints (min, max, chosen value), strings (prompt, outcome hint, labels),
  stable option ids, and the two descriptor shapes in CHOSEN_DESIGN.md.
- No UUIDs (native identities never leave the bridge; Lab already maps to
  stable ids for mana/attack/block and to labels elsewhere).
- No engine objects (Ability, Game, Target, Choice, Modes), no
  ability_original_id, no mana_type enums, no MultiAmountType, no Outcome
  enum (lowercased outcome string only, as today).
- No step/stride/sentinel concepts (none exist in the proven domain model).

## What stays behind the provider boundary (qualified Rules Core + bridge)

- Derivation of min/max per callback (card/ability code).
- Eligible-set computation (possibleTargets, getPlayable, Choice sets).
- Native submission and final acceptance (callback return values).
- Inclusive-range projection check (bridge; provider-owned enforcement).
- Hidden-zone handling (WS92-D2 look window stays in the bridge).

## Multi-provider readiness

The descriptor {kind, min, max} / {legs, totals} is expressible by any
Rules Core with scalar-bounded numeric callbacks. A future provider whose
numeric callbacks carry non-interval domains must extend the descriptor
with an explicit domain shape (e.g. allow-list id set) — the contract
already anticipates this via the `kind` tag; S6 implements only
`contiguous_inclusive_int` and `joint_bounded_int_vector` and fails closed
on unknown kinds.

## Anti-coupling checklist for S6 reviewers

1. pilots.py imports no mage.*, no engine-bridge symbols. (Today: true.)
2. full_game.py numeric path references only context ints + outcome
   strings. (Today: true; keep true — do not project isManaPay,
   MultiAmountType, or source metadata into the descriptor.)
3. Replay tape numeric fields stay ints (no engine ids). (Today: true.)
4. No card-name hacks: S6 test scenarios select cards for their
   Rules-mechanical numeric callbacks (X-spell, divided damage, modal
   count), never string-matched names in implementation.
