# ScenarioBootstrap capability matrix (source-bound)

Machine-readable authority: `receipts/SCENARIO_CAPABILITY_MATRIX.json`.

The matrix is **derived at runtime from the exact pinned bridge source blob**,
not from prose. `derive_capability_matrix()` asserts exact code fragments; if a
future pinned source removes one, it raises `ScenarioCapabilityDrift` and no row
credit can be produced until the matrix is re-derived and reviewed.

## Source identity at this epoch

| Role | Identity |
| --- | --- |
| Lab source | branch `hardening/forge-scenario-lane-20261001`, commit `a60ee600…` (recorded per receipt) |
| Forge Rules-Core candidate | `bb0a740d2bef725194798383c2452213ecdd0b37` (tree `4989b5bb…`) |
| Forge bridge/materialization | `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c` (commit tree `000066890d…`, `forge-protocol2-bridge` module tree `b1dbfc3dec…`) |
| Executing checkout | clean, HEAD `20e3e1f7…`, module tree equal to the bound module tree |
| `ScenarioBootstrap.java` blob | sha256 `9ae04d53dba4…` |
| `BridgeSession.java` blob | sha256 recorded in the matrix JSON |
| Protocol | 2.0.0; provider `forge`, release `2.0.14`, Java 21 |

## Supported construction contract (proven by fragment assertions)

| Field | Semantics | Runtime-visible in readback |
| --- | --- | --- |
| `battlefield[]` | `card` + required `controller`; `owner` defaults to controller; identity taken from the owner's command zone (real commander object) else library else `Card.fromPaperCard` | `zones.battlefield` + `zones.battlefield_details` (name, tapped, counters, P/T) |
| `battlefield[].tapped` | boolean | `battlefield_details[].tapped` |
| `battlefield[].counters` | object of `CounterEnumType` name → non-negative int | `battlefield_details[].counters` (display names; the lane maps `P1P1` ↔ `+1/+1`, `M1M1` ↔ `-1/-1`) |
| `battlefield[].attached_to` | host card name; resolved after all placements via native attach | **no attachment projection** (blocker for control/attachment rows) |
| `hands{player → [card]}` | natural hand returned to library, scripted cards taken from library else created | `zones.hand` per principal-scoped seat observation |
| `life{player → int}` | `Player.setLife` when different | `players[].life` |
| `players[].commander_damage_taken` | commander **name** → int, resolved to the real commander card object | `players[].commander_damage_received` (**name-keyed**) |

Hook placement (asserted in `BridgeSession.java`): the plan is stored once at
creation and applied inside `startGame(capturedGame, hook)`, i.e. during the
first-turn setup after mulligans, before the main loop. `givePriorityToPlayer`
is false while the hook runs; SBAs and triggers proceed natively afterwards.

## Explicit rejections (proven live and by source fragment)

| Neutral field | Engine behavior |
| --- | --- |
| `stack` (non-empty array) | create rejected: `game_creation_failed` / `scenario rejected: scenario must not inject stack` |
| `decision_script` (non-empty array) | create rejected: `game_creation_failed` / `scenario rejected: scenario must not inject decisions` |

Live proof at this epoch: `receipts/LIVE_REJECTION_PROBE.json`.

## Unknown fields are silently ignored

`ScenarioBootstrap.parse` reads only the keys it knows. A neutral state carrying
`combat_state`, `action_cost_state`, `temporal_state` or `knowledge_state` is
**accepted** by create with those dimensions absent from the constructed game.
Engine acceptance is therefore not construction: the lane classifies those
dimensions itself and the readback comparison detects the absence
(`run_silent_ignore_probe`, recorded per row). This is the fail-closed control
behind "unsupported scenario field fails closed".

## Readback observability limits (not construction limits)

| Requested dimension | Limit |
| --- | --- |
| card `owner` when owner ≠ controller | constructed, but the projection exposes controller rows only |
| attachments (`attached_to`) | constructed, but no attachment relation is projected |
| library contents/order | only `library_size` is projected; library ordering is not constructible |
| exile / graveyard | names only, no semantic identity mapping |
| face-down state | no bootstrap field and no generic projection |
| `controlled_since_turn_began` | no bootstrap field; attack eligibility is engine-derived |
| `prior_command_zone_cast_count` | no bootstrap field; command-zone cast counts cannot be seeded |
| combat state / step | no bootstrap field; bootstrap-placed attackers are summoning-sick on the first turn |
| temporal checkpoints other than the first turn's untap | reachable only by native progression, and a requested explicit hand cannot survive a natural draw step exactly (3P+) |

## Boundary findings for the Coordinator (Forge-side, not repaired here)

1. **Commander damage is name-keyed.** `ScenarioBootstrap` resolves and seeds
   commander damage by card name, and `StateProjection` emits the map by name.
   Two different commander identities with the same name cannot be given
   different damage amounts to the same player; the lane fails closed on that
   ambiguity instead of guessing.
2. **Bootstrap-placed permanents are summoning-sick on their first turn.** The
   hook runs during the first-turn untap after untap processing, so a
   battlefield placement cannot satisfy a turn-1 attack/block obligation.
3. **No owner/attachment projection.** Control-change and aura-cleanup
   obligations cannot be fully observed on the generic readback even when the
   state is constructible.
