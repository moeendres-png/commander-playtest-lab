# AUTONOMOUS MULTIPLAYER ADVANCEMENT HANDOFF

Claude Opus 5.5 (Claude Code), 2026-09-29.
`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## Source lock
- Lab `main` at campaign start: `da4253ab`. At the last merge: `2229380b` (#314).
- XMage pin `b19596980f27` (unchanged). Engine source read at that commit (`mage-rg-candidate-build`).
- Rules: CR 2026-09-25, sha256 `8d860e45…`. Oracle and rulings: Scryfall API, 2026-09-29.
- State file: `.foundry/claude-mp-campaign-20260929.json` (schema 2.0, STATE_OK).

## Work completed (all on the XMage full-game lane, actual cards, each at 3/4/5/6 players)

| PR | Content | Status |
|---|---|---|
| #311 | APNAP ordering of simultaneous upkeep triggers (Sulfuric Vortex) | merged |
| #312 | Each-player choices in APNAP order (Innocent Blood) | merged |
| #313 | **Production fix, CR 802.4a:** block options only against the blocker's own attackers (F-16) | merged |
| #314 | Defending-player targeting (Impetuous Devils), menace across defenders (Broadside Bombardiers), goad (Disrupt Decorum) | merged |
| #315 | Voting (Council's Judgment), monarch (Palace Sentinels), leaving mid-combat (800.4e), simultaneous commander deaths (903.9a) | auto-merge armed |

## New findings (details in `EVIDENCE_INTEGRITY_REVIEW.md`)
- **F-16 (P1), FIXED in #313.** The full-game lane offered every attacker to every defending blocker, and the engine silently dropped illegal blocks. Evidence from 3+P games in which one combat attacked two or more players needs impact adjudication.
- **F-15 (P2), open.** Restoration arrival runs beginning-phase triggers of restored permanents, and `completeArrival` does not compare. Routed to the restoration owner (#304 lane).
- **F-17 (P3), open.** Per-blocker decisions can offer a block that is illegal only as a whole declaration (menace). The engine settles it rules-correctly, but the pilot's selection can differ from the executed declaration.
- **F-18 (P3), open, engine.** Command-zone state-based-action choices are asked in seat order, not APNAP. This is also true upstream. The fix needs Rules Core / pin authority.
- **Confirmed correct, no change needed:**
  - the engine's counterclockwise turn order is consistent across turns, priority, APNAP and voting;
  - goad requirements;
  - "must block" requirements;
  - defending-player targeting;
  - monarch transfer, including both 725.4 branches;
  - 800.4a and 800.4e.

## Tests and evidence
- Bridge suite, last run: 468 run, 0 failures, 2 skipped (the START-2 v1.0.5 provenance skip and the F-18 CR-order test).
- Classification: native runtime technical evidence at the pin (DIRECTLY_VERIFIED engine state, Oracle- and CR-derived expectations).
- No FULL107 row, denominator, or qualification credit is claimed.

## Decisions reserved to Sol / authority gates
1. **F-16 impact adjudication.** Which full-game-lane multiplayer evidence (split-attack combats) needs requalification.
2. **F-18 engine fix.** Fork patch vs upstream report, and pin movement.
3. **F-15 restoration semantics.** Fail closed, restore after arrival, or compare after arrival.
4. **Evidence policy.** Whether these native multiplayer probes can feed any gate.

## Not done / routed
- **Forge multiplayer probes.** Forge identity and surfaces are owned by PB-09 (#297/#299) and Forge #6/#7. Running the same actual-card scenarios on Forge is the natural next step once those lanes settle.
- **Generic Protocol-2 lane.** It fails closed on blocks and is owned by #300/#284; no change was made.

## Housekeeping (operator)
- Obsolete stashes: `claude-seed-wip-20260929`, `claude-batch4-local-20260929`.
- Obsolete worktrees: `/home/moeen/code/claude-xmage-2p-draw-skip-20260929`, `/home/moeen/code/claude-corpus-completion-20260929`.
- The campaign worktree `/home/moeen/code/claude-mp-apnap-20260929` can go once #315 merges.

## Exact next action
Confirm #315 merged. Sol adjudicates F-16 impact and F-18. The Forge lane owner ports the probes in this handoff to Forge at 3–6P.
