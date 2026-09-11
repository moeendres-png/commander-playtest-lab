# WS55R — Sol High Rules-Authority Gates (persisted, not resolved)

WS55R resolves no MTG Rules questions. The three WS55 XHIGH authority gates
(plus the applied C-1 correction) are carried forward unchanged under RQ-C3
authority. Each gate's effect on the corrected Decision-seam classification is
stated explicitly; no gate blocks unrelated work.

Source pins (read-only): Forge `66caae16015bd403bc0a52fa6689afb5508f74d0`;
RQ-C3 `897d72f0b57bb8febe045870acaa3d2dba4bde56`.

## AG-1: G04 control-change vs concession equivalence (104.3a / 800.4)

- Question: whether the RQ-C3-G04 leave-game cleanup expectations (Control
  Magic controller leaves; Aura leaves with owner; Bear reverts to owner)
  are adjudicated identically for loss-by-concession vs loss-by-other-means,
  and which 800.4 sub-rules govern each assertion.
- WS55R seam status: INDEPENDENT. The G04 Decision-seam gap
  (`ENGINE_DECISION_NOT_EXTERNALLY_REACHABLE`, see
  `WS55R_G04_CONCESSION.json`) holds whether or not AG-1 is resolved: no
  offered concession action exists to externalize in either case.
- Blocking: G04 scenario readiness only (with the seam gap). Blocks no other
  scenario or kind.
- Evidence: `Player.concede()` → `GameLossReason.Conceded` → SBA
  `checkGameOverCondition` → `Game.onPlayerLost` 800.4 cleanup chain
  (source-derived, engine read-only). No concession outcome was executed or
  verified by WS55R (no injection, no behavior credit).

## AG-2: D06 mode-subset offerability vs target-legality pruning (601.2b / 115)

- Question: RQ-C1 asserted 31 nonempty mode subsets for Casualties-style
  "choose one or more"; Rules may prune target-less modes from the offer set.
- WS55R seam status: D06 Decision seam is READY under RQ-C3 (single o1 +
  multi sequential o1/o1 with exact AbilitySub binding + native resolutions;
  engine-pruned offered set stays authoritative). AG-2 gates only the
  mode-remediation acceptance criterion (outcome assertions), never the
  transport proof.
- Blocking: nothing in the Decision seam. Outcome-level only.
- Evidence: carried WS55 W-modes (preserved NO_IMPACT, no rerun).

## AG-3: E02 damage-split uniqueness (510.1c-d, 702.19)

- Question: uniqueness/legality boundary of 702.19b-compliant divisions
  (scripted 2/1/4 vs the wider compliant set).
- WS55R seam status: E02 Decision seam is READY unconditionally under RQ-C3
  (see `WS55R_E02_RECLASSIFICATION.json`). AG-3 gates outcome assertions
  only; the split-offered-via-Core-view surface is unaffected.
- Blocking: nothing in the Decision seam. Outcome-level only.
- Evidence: carried WS55 W-combat both paths (preserved NO_IMPACT, no rerun).

## Standing correction (applied in WS55, preserved)

- C-1: combat-damage surface assumption corrected (ws40 base with Core-view
  `chooseCombatDamage` already present; runtime witnessing was the only
  remaining work, completed in WS55). No action in WS55R.

## Discipline

- `BEHAVIOR_CREDIT = 0/107` · `FULL107 = NOT_RUN` ·
  `ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`.
- No Rules verdict is attached to any Forge behavior by WS55R. RQ-C3 expected
  outcomes remain `EXTERNALLY_RULE_VALIDATED` authority; candidate behavior
  remains `NOT_RUN` for credit.
