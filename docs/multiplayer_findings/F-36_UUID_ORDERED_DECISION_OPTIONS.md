# F-36: decision options were ordered by random object ids (bridge; replay)

Status: FIXED in the full-game lane (this PR). Found by the whole-game replay harness (`XmageFullGameReplayTwinTest`, reversed-choice pilot variant). Claude Opus 5.5, 2026-09-30.

- **Classification:** `BRIDGE_SURFACE_DEFECT` that breaks semantic replay, in `XmageFullGamePlayer`.
- **Source lock:** Lab main `70e95e33`, live XMage pin `f79e4168`.
- **Project rule, AGENTS.md §5:** deterministic semantic replay. The lane's own WS92-D5 principle already says native UUIDs "must never sequence decision frames", but it was applied only to attackers and blockers.

## Defect

Four decision surfaces sorted their objects by `UUID::toString`: targets (including library searches), divide-as-you-choose targets, attack defenders, and blocked attackers. The mode order and the ability order at priority and payment were also keyed on random ids.

Object ids are random per game. So "the first Plains" offered by a library search was a different physical card in each replay. The following seeded shuffle then started from a different sequence, the libraries diverged, and so did the rest of the game.

- Measured: the same 5P real-deck game with the same seed and the same semantic pilot produced three different game histories in four runs.
- The first difference was P5's library order right after Path to Exile's land search.

## Fix

`stableObjectOrder`, keyed on Rules-visible, twin-stable content:

| Object | Order key |
|---|---|
| Players | name |
| Permanents | name, controller, zone-change counter, power/toughness, tapped state, damage |
| Stack objects | stack position |
| Cards in hidden or ordered zones | zone, owner, position (library order, top first, as the searching player sees it; graveyard, hand and exile in insertion order), name |

- Modes keep their printed order.
- Abilities are ordered by their source's stable key, then rule text.
- UUIDs remain only as a tie-breaker between objects that are indistinguishable by all of the above.

## Evidence

- `XmageFullGameStableOptionOrderTest`, 2P and 4P, with Terramorphic Expanse over a Mountain/Forest library:
  - The search offers library order.
  - Taking the first Mountain gives the identical library afterwards in two same-seed games.
  - Red 2/2 on the unfixed lane (UUID order), green 2/2 with the fix.
- The replay harness (variant pilot): the same 5P game four times is identical four times. Before the fix, it gave three different histories.
