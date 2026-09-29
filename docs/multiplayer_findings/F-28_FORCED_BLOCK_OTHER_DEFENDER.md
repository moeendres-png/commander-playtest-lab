# F-28: a "blocks if able" requirement could demand a block of another player's attacker (engine livelock)

Status: FIXED in the XMage fork (moeendres-png/mage#27). The Lab regression is disabled until the repin to a candidate that contains it. Found by the multiplayer discovery lane (Claude Opus 5.5), 2026-09-29.

- **Classification:** `RULES_CORE_DEFECT` in pinned XMage `Combat.checkBlockRequirementsAfter`. The code is unchanged in upstream `magefree/mage` master (checked 2026-09-29).
- **Source lock:** Lab main `7055740e`, live XMage pin `f79e4168` (candidate mage#24). Fix commit `268e3d0f` on `claude/xmage-f28-forced-block-802-4a-20260929`, a fast-forward from the pin.
- **Rules:**
  - CR 802.4a: a defending player's creatures can block only creatures attacking that player, a planeswalker that player controls, or a battle that player protects.
  - CR 509.1c: requirements are obeyed only as far as possible without violating restrictions.

## Defect

For "blocks this turn / each combat if able" requirements (`mustBlockAny` / `mustBlockAllAttackers`), the engine decided whether the creature *could* block with `Permanent.canBlock` alone. That method checks only that the attacker is an opponent's.

In multiplayer, a forced blocker whose only candidate attacker attacked another player was therefore required to block. The engine itself then rejects that block (`CombatGroup.canBlock`). Block declaration could never become valid:

- For a human or externally controlled player, `Combat.selectBlockers` re-asked in an endless `while (true)` loop.
- The full-game lane offers that creature no block options (its offers already use `CombatGroup.canBlock`, per the F-16 fix). So no decision ever reached the pilot, and the engine thread spun at Declare Blockers.
- A real game with such a board hangs forever.

The `mustBlockAttacker` path ("blocks that creature if able") already had the equivalent defending-player check.

Reachable in ordinary Commander play: any "blocks if able" effect on a creature (Culling Mark, Courtly Provocateur, creatures with "blocks each combat if able") held by a player who is attacked only by creatures it cannot block while another player is attacked.

## Fix (engine, at the pin)

The four requirement sites now use `Combat.canBlockInThisCombat`. It requires both:

- the attacker's current combat group is defending against the creature's controller, and
- `Permanent.canBlock`.

Two-player games are unchanged, because the only defending player is always the blocker's controller.

## Evidence

- **Lab lane** (`XmageMultiplayerForcedBlockTest`, 3–6P, actual cards). On pin `f79e4168`, all four cases hang at Declare Blockers:
  - The session reports no pending decision, with `terminal:false` and `engine_thread_alive:true`.
  - The engine thread is RUNNABLE in `Combat.selectBlockers` → `checkBlockRestrictions` / `canBlock`.
  - The test is `@Disabled` until the repin, and then asserts that combat completes with P2 at 38 and P3 at 36.
- **Native** (`ForcedBlockOtherDefenderTest`, 4P):
  - **Red before the fix:** a thread dump shows `main` RUNNABLE for 1260 CPU-s at `Combat.checkBlockRequirementsAfter(Combat.java:1113)`.
  - **Green after the fix:** 2/2, including a control case where the requirement is still enforced.
  - **Regression set:** `org.mage.test.multiplayer.**` plus the block-requirement tests. Result: 232 run, 0 failures, 0 errors, 5 skipped.
