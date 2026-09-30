# F-41: the bridge seated players so that turns ran against seat order

Status: FIXED in the XMage engine bridge (this PR). Claude Opus 5.5, 2026-09-30.

- **Classification:** `BRIDGE_SURFACE_DEFECT` (seating) in `XmageFullGameSession`, `XmageGameManager` and `Phase6DifferentialAdapter`. The engine was consistent; the bridge fed it the wrong seating.
- **Source lock:** Lab main `4c72da6a`, live XMage pin `9375f35a`.

## What happened

XMage's `CircularList.add` inserts each new element at the current position. So a table built by adding players P1, P2, …, PN has the engine turn order P1 → PN → … → P2. Priority, APNAP and "next player" all follow that order.

Every bridge lane added players in seat order, so every multiplayer game ran "backwards" relative to its seat numbers. The frozen contract orders a table by seat number:

- `WS05-MP-PRIO-5`: "Priority traverses exactly P1..P5 live ring";
- `WS05-MP-TRIG-3/5`: APNAP groups `[P1, P2, P3, …]` "in turn order";
- `CARD_20` (Syphon Mind): the discards are scripted P2, P3, P4.

Earlier work (F-15..F-18) noted the rotation as "counterclockwise, consistent, not a bug", and more than 100 test assertions pinned it. That was internally consistent, but it did not match the contract. The midgame probe's priority-ring terminal counted only distinct principals, not their order, so the mismatch never showed up there. It surfaced when the scripted-decision terminal (PR #406) found `CARD_20`'s first discard asked of P4, not P2.

## Fix

- **`XmageSeating.additionOrder`.** Every lane adds P1 first and then PN down to P2. The engine's own turn order is then P1 → P2 → … → PN. P-labels, deck handles and player names are unchanged.
- **`XmageSeating.seat`.** A seat is read from the engine's own turn-order ring, counted from the table's first player. Before, it was the index in the player map, which is add order. The ring keeps players who left, so seats are stable.
- **Consumers.** Every seat readout uses this: `ActorSafeIdentity`, the redactor's `seat` and player views, and the session's zone counts and outcomes. Views list players in seat order.

## Evidence

- **`XmageSeatingTest`** reads the engine's own ring (a `CircularList` copy of the game's player list, by player name) at 2–6 players:
  - one round from P1 is "Full Game Seat 1..N";
  - the seat readout is P-index − 1;
  - `additionOrder` is unit-tested.
- **`XmageGameManagerTest.theEngineTurnOrderIsSeatOrder`** checks the same for the generic lane ("Bridge Seat 1..N", 3–5 players).
- **Existing tests flipped red to green.** They are updated to seat order through one relabeling: the engine position that used to be called P(N+2−j) is now Pj.
  - Before the fix: 102 failures and 4 errors across 32 classes when the engine seated correctly, because they pinned P1 → PN → … → P2.
  - The pure order checks (APNAP, votes, join forces, block order, commander zone choices, discards) now expect ascending seats.
  - The "next player" tests (monarch, initiative, turn control, stolen commander, third-party combat, simultaneous loss, APNAP triggers, Tithe/Curse, attack and exchange direction) now name P2 and P3 where they named PN and P(N−1). Role-sensitive scenarios moved their roles along, for example the cursed player is now PN and the attacker P2.
  - `XmageTemporalProgressionDriverTest.reachesDeclareBlockersViaOneExplicitNativeAttack` had only passed through a stale priority slot. P2 was still *declaring blockers*, while the last declare-attackers priority holder happened to be P2. P2 now declines to block explicitly, and then genuinely holds priority in the declare blockers step.
- **Full bridge suite:** 826/0/1 plus 17 new seating assertions, checkstyle clean.

## Consequences and what is not done here

- **Earlier evidence.** Every earlier XMage multiplayer run measured the reversed rotation. Rows whose obligation depends on order (priority ring, APNAP, "next player", discards, votes) were measured against the wrong seating. Sealed artifacts are not rewritten; a successor current-boundary run is a Coordinator gate.
- **Forge.** Whether the Forge lane seats in contract order was not checked here.
- **Probe.** The midgame probe's priority-ring terminal should check order, not only count. That is a follow-up once PR #406 (which adds the seat-to-principal helper) is merged.
