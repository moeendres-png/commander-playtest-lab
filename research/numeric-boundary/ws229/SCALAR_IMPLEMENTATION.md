# WS229 Scalar Implementation (H1-H4 scalar parts)

## Changed hunks (all in S6 blueprint surface)

- `src/commander_lab/engine/rules/full_game.py`
  - `decide()` numeric-only branch: `announce_x`/`amount` route to the new
    descriptor path; `multi_amount` routes to the joint path (H1).
  - `decide()` `target_amount` companion calls the descriptor path with
    decision class + prompt (H2).
  - `_decide_numeric` replaced: strict bound parsing (`_required_bound`:
    missing/bool/non-int/reversed fail closed), descriptor build, single
    `pilot.choose_number` call, strict-int + membership validation, int
    return. The `maximum - minimum <= 16` enumeration/collapse hunk is
    DELETED; no `numeric:{value}` PilotActionViews are built anywhere on
    the numeric path (H3).
  - Response carries `numeric_choice` (unchanged key).
- `src/commander_lab/agents/pilots.py`
  - `BasePilot.choose_number` default: `NotImplementedError` (fail closed).
  - `_NumericStrategyMixin` mixed into all six direct BasePilot subclasses
    (Korvold/RogShai/Aggro/Control/Engine/GenericCommanderPilot; every
    leaf inherits): DETERMINISTIC = outcome-aligned extreme
    (benefit->max, detriment->min, neutral->midpoint); STOCHASTIC =
    `rng.randint(min, max)` on the Lab-seeded rng (H4).

## Lossless proof (CODE_DERIVED + DIRECTLY_VERIFIED)

- Projection direction: descriptor min/max are the context ints verbatim;
  no value is added, removed, or transformed.
- Membership validation accepts EXACTLY the Core-accepted set
  (min <= v <= max over unit-stride ints) — the same predicate the bridge
  projection and the native accept loop enforce.
- Live bridge frames carry zero options + verbatim bounds
  (ANNOUNCE_X_LIVE / AMOUNT_LIVE captures); the Lab submits interior
  values (73 in [0,100], 18 in [1,40]) the old collapse could never offer.
- O(1) in domain width: one descriptor, one pilot call, one comparison;
  span-10^9 and live span-(2^31-1) runs complete in budget (P-N1,
  card-driven MAX_VALUE fire).

## Anti-fallback proof

Every invalid return class raises `FullGameProtocolError` with no
alternate arm: missing/reversed/bool/float/string bounds; non-int pilot
return (incl bool); out-of-domain pilot return (N-23 hostile max+1).
Controller + projection lanes reject non-integer numerics (string,
fractional) with `must be integer`; no truncation survives.
