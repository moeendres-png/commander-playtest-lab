# B8 takeover repair evidence — 2026-10-03

Direct Owner takeover: Lab #255 comment 5969650684. Historical Claude evidence and ownership are retained; this continuation is owned by CLAUDE-CAMPAIGN-TAKEOVER-20261003.

Source: published B8 `208c149ec86f04fc88fdb5e9f83f64485216c0f0`, with main `2296266e6ae56cddbd98836d91f1b3381b0b7cdb` merged normally. Included evidence JSON binds the precise working-source hashes and command for each run.

Five offline adversarial controls failed before the repair: decision-cap exit, premature terminal exit, changed numeric response, invalid second twin, and missing digest accepted as `None == None`. They pass after the repair. The attached GREEN run has 39 passing affected tests. The subsequent source-impact audit and affected tests have 66 passes.

The first full-suite run on the uncommitted merge returned 61 failures and 8 errors: 60 cases reject dirty tracked source by design, and nine workflow-impact cases exposed new transitive replay dependencies. Those gates were expanded without dropping any existing inputs. Full clean-commit CI and live twin execution remain required; this document does not claim they have passed.

The response-bound trace and progress contract are version 1.1.0. Both twins must cross turn 4 and stop at the turn-5 boundary with all four priority seats, valid seats, acknowledgements and matching recomputed digests. Actual pinned-engine execution is separate from these offline controls. No terminal full-game, deck-strength, card-behavior, external rules qualification or campaign eligibility claim is made.
