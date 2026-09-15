# Performance Boundary (WS228)

## Principle

Performance never justifies legality narrowing. The question here is only
which correct design has bounded cost.

## Domain-size reality (proven vs unknown)

- Typical reachable spans are small: X bounded by available mana (usually
  < 20 in conformance scenarios), life totals <= 40+, damage/divided
  amounts bounded by game state. These are engineering expectations, NOT
  proven bounds — no code caps engine-supplied maxima.
- Engine-supplied maxima distribution in real games is UNKNOWN (U1). S6
  live runs must record (min,max) per numeric step to build the empirical
  distribution (see S6_TEST_PLAN.md).
- Pathological spans are constructible in principle (e.g. an effect
  passing max=Integer.MAX_VALUE and relying on the human to pick an
  affordable value — a common XMage pattern for "up to" wordings).
  The WS228 probe materialized nothing (design B needs no run), but design
  A at span 10^6 would build a million PilotActionViews + evaluate + sort
  them per decision — per-decision seconds-to-minutes and proportional
  memory. At span 2^31 the process dies. This is not hypothetical
  optimization: it is the reason design A is rejected as preferred.

## Disposition

- Chosen design B: O(1) per numeric decision at ANY span (one descriptor,
  one pilot call, one membership check). Large-domain performance is
  closed as a concern for scalars AND vectors (legs count is small and
  engine-bounded; totals are two ints).
- No span cap, no truncation, no sampling: caps are narrowing by another
  name. If U1 ever shows spans that stress even O(1) handling (it cannot
  — two ints), the remedy is transport paging, never domain reduction.
- S6 must still assert a bounded-cost regression: a synthetic span-10^9
  scalar decision completes within the normal single-decision budget
  (this is a performance test of B's O(1) property, S6_TEST_PLAN.md P-N1).

## Incidental finding (not a defect)

Pilot shortlist (3-8) + full enumeration (design A) would silently
re-narrow at the ranking stage. Design B removes the ranking funnel from
the legality path, so shortlist returns to its proper role: pilot-internal
strategy among non-numeric options only.
