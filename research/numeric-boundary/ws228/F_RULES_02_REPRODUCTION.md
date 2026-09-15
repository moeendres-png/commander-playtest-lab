# F-RULES-02 Reproduction (WS228)

Status: LIVE_DEFECT_REPRODUCED (research-probe level; production code unchanged).
F-RULES-02 remains OPEN until S6 remediation lands.

## WS220 claim (reconstructed from source, not trusted on summary)

F-RULES-02 (P1, CODE_DERIVED): `full_game.py` collapses span>16 numeric
domains to {min, mid, max} before pilot ranking; no test pins it; affects
X-spells, distributed amounts, modal counts. Desired: explicit disposition —
expand to full domain (or justified bounded set) + per-class live observation
of announce_x / amount / multi_amount.

## Exact narrowing point (first and only Lab-side narrowing)

File: src/commander_lab/engine/rules/full_game.py
Function: ExternalPilotDecisionPolicy._decide_numeric (lines 736-774)
Hunk (lines 750-754), identical on WS223 and WS226 (blob 7bd3bc28):

```python
if maximum - minimum <= 16:
    values = list(range(minimum, maximum + 1))
else:
    midpoint = minimum + (maximum - minimum) // 2
    values = sorted({minimum, midpoint, maximum})
```

Only the listed `values` become PilotActionViews (`numeric:{value}`); the
pilot contract (BasePilot.choose_action over offered views) gives the pilot
no other numeric path. Upstream (bridge context numeric_min/max) and
downstream (projection inclusive-range check) are both lossless — proven in
NUMERIC_DOMAIN_TRACE.json. The Lab pilot boundary is therefore the FIRST
and ONLY point where the legal domain narrows.

## Reproduction evidence (research-only probe, locked code, unmodified)

Probe: research/numeric-boundary/ws228/probes/numeric_boundary_probe.py
(drives production ExternalPilotDecisionPolicy.decide with a recording pilot
wrapper; captures offered PilotActionView ids per decision class and bound
pair). Full output: LIVE_PROBE_RESULTS.json. Evidence class: SYNTHETIC
research probe of Lab transformation semantics (proves which integers reach
the pilot; does NOT prove actual-card behavior).

| class | [min,max] | span | offered | missing | submitted |
|---|---|---|---|---|---|
| announce_x / amount / multi_amount / target_amount | [0,5] | 5 | 6 (all) | 0 | in-range |
| same 4 classes | [0,16] | 16 | 17 (all) | 0 | in-range |
| same 4 classes | [0,17] | 17 | 3 = {0,8,17} | 15 | 17 |
| same 4 classes | [0,100] | 100 | 3 = {0,50,100} | 98 | 100 |
| same 4 classes | [1,40] | 39 | 3 = {1,20,40} | 37 | (in-range) |
| same 4 classes | [0,1000000] | 10^6 | 3 | 999998 | (in-range) |

All five probe verdicts true: small_domain_full, boundary_16_full,
boundary_17_narrowed, large_domain_narrowed,
large_domain_offered_is_min_mid_max. F_RULES_02_REPRODUCED = true.

## Boundary semantics (exact)

- span <= 16 (i.e. at most 17 consecutive integers): full exposure.
- span >= 17: exactly {minimum, minimum+(maximum-minimum)//2, maximum}
  (deduped via set; degenerate equal values collapse).
- The submitted value always passes downstream validation because the
  projection checks inclusive range only — the defect is silent (no error,
  no log); interior legal values are simply never offerable.

## Corroborating static facts

- Zero existing tests reference span-16/midpoint narrowing (WS220 claim
  re-verified: grep over tests/ finds only small-domain numeric contexts,
  max span 5 in test_xmage_full_game_decision_matrix.py).
- Existing matrix test asserts only
  `numeric_min <= numeric_choice <= numeric_max` — satisfiable by the
  narrowed set, so the suite is blind to the defect by construction.
- Pilot shortlist (agents/pilots.py:274, shortlist 3-8) is pilot-internal
  ranking among OFFERED views, not a second narrowing: it cannot offer what
  Lab withheld. S6 assertions must therefore target the OFFERED set, not
  just the submitted value.

## What this reproduction does NOT prove (remains UNKNOWN)

- Actual-card live firing of announce_x/amount/multi_amount through a full
  JVM game on current pins (no full-game JVM run in WS228; S6 must supply
  per-class live observation incl. span>16 — see S6_TEST_PLAN.md).
- Reachable maxima distribution in real games (needed for the performance
  disposition; see PERFORMANCE_BOUNDARY.md).
