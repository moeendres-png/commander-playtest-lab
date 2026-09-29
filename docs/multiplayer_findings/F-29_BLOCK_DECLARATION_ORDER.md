# F-29: defending players declared blockers in hash order, not APNAP (engine)

Status: FIXED in the XMage fork (moeendres-png/mage#28, stacked on F-28 mage#27). The Lab regression is disabled until the repin to a candidate that contains it. Found by the multiplayer discovery lane (Claude Opus 5.5), 2026-09-29.

- **Classification:** `RULES_CORE_DEFECT` in pinned XMage `Combat.selectBlockers` and `resumeSelectBlockers`. It is also a semantic-replay defect.
- **Source lock:** Lab main `7055740e`, live XMage pin `f79e4168`. Fix commit `3c0fe388` on `claude/xmage-f29-block-order-apnap-20260929`, on top of F-28 `268e3d0f`.
- **Rule, CR 802.4:** "each defending player in APNAP order declares blockers as the declare blockers step begins. The first defending player declares all their blocks, then the second defending player, and so on."

## Defect

The engine iterated `getPlayerDefenders`, which is a `HashSet` of player ids. With several defending players, the order of block declarations was therefore arbitrary. Player ids are random UUIDs, so the order also changed from game to game, even with the same Rules seed and the same choices.

- **Rules impact:** a later defender legitimately sees earlier defenders' blocks (802.4), so the order is information that matters.
- **Replay impact:** identical inputs produced a different decision sequence. Recorded games using multi-defender combats were not deterministically replayable.

Six identical 4P games on the lane, with P1 attacking all three opponents, gave four different orders: `[P3,P4,P2]`, `[P4,P2,P3]`, `[P3,P2,P4]`, and others. 5P and 6P varied likewise.

## Fix (engine, at the pin)

`Combat.getPlayerDefendersInApnapOrder`: the defending players filtered from `Game.getPlayerIdsInApnapOrder()`, the F-21 APNAP primitive. It is used for the block-declaration loop and the `DECLARED_BLOCKERS` events.

Defending players that have left the game keep a place after the others, in turn order, so the set of iterated players is unchanged. Two-player games are unchanged.

## Evidence

- **Lab lane** (`XmageMultiplayerBlockOrderTest`, 3–6P, three games each; the expected order is PN, …, P2):
  - On pin `f79e4168`: red 4/4. For example, 6P gave `[P3, P5, P6, P2, P4]`.
  - The test is `@Disabled` until the repin.
- **Native** (`BlockDeclarationOrderTest`, 4P commander FFA, with A, D and C each active):
  - Red 2/3 without the fix; the third case matched by chance.
  - Green 3/3 with the fix.

## Impact on existing evidence

Evidence from full-game-lane games with several defending players in one combat carries a replay-determinism caveat on the old pin. Single-defender combats and 2P games are unaffected. This adds to the F-16 impact-adjudication scope for multi-defender combats.
