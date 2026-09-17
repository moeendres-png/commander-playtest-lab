# WS-46 CHECKPOINT 03C — NATIVE CONSTRUCTION SURFACE SOURCE AUDIT

## Status

`PASS / SOURCE_AUDIT_ONLY / ZERO_CONSTRUCTION_OR_BEHAVIOR_RUNTIME_CREDIT`

This checkpoint is persistent/resumable evidence for the exact native/provider state surfaces required to close the remaining v1.0.4 construction denominator. It grants no construction PASS, behavior PASS, AF gate, provider qualification, AF07, or Architecture Freeze.

## Source Lock

Commander Lab live head audited before this checkpoint:

- repository: `moeendres-png/commander-playtest-lab`
- branch: `ws46/xmage-v1.0.4-successor-qualification`
- commit: `4d1c661a9cf51eabe975a0f5d019eefbb4f2c3bf`
- tree: `a85e6c6df99413d13b69ec50ec86dd6f266d47b1`
- PR: `#160`, open, Draft, unmerged

Immutable WS-44 authority:

- commit: `12940248497a8795991cbbd2eedef72945528cfe`
- tree: `cd83c973b269711106d08ab5be2d7672f05bcb7c`
- namespace tree: `6579e119605b90248426a3121a47c487b2bb13cd`
- contract: `commander-lab.semantic-fixture-materialization/1.0.4`
- materialization SHA-256: `9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35`
- provider denominator: `107`

XMage candidate:

- repository: `moeendres-png/mage`
- commit: `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
- tree: `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`

Historical successor-runtime credit imported: `0`.

## Fresh v1.0.4 Construction Surface Census

Checkpoint 03B / corrected source-bound audit established:

- `combat_state`: 12 records
- `knowledge_grants`: 11 records
- `extra_turn_creation`: 2 records
- `elimination_trigger`: 6 records
- `zone_move_event`: 8 records
- `natural_game_start`: 0 records
- unique records with one or more of those surfaces: 39

The historical seven-record `natural_game_start` assumption is superseded by the immutable v1.0.4 census (`0`).

## Native Surface Classification

### 1. `combat_state`

Classification: `DIRECT_NATIVE_RESTORE_AND_READBACK`

Exact XMage source surfaces:

- `GameState.combat` is copied/restored as native `Combat` state.
- `Combat.addAttackerToCombat(attackerId, defenderId, game)` mutates the native combat snapshot without declaring an attacker through the rules event path.
- `CombatGroup.addBlockerToGroup(blockerId, playerId, game)` explicitly adds a blocker without creating `DECLARE_BLOCKER` events.
- High-level `Combat.declareAttacker` / `CombatGroup.addBlocker` MUST NOT be used for snapshot restore because they execute declaration/replacement semantics and historical events.
- Native legal candidate surfaces exist on `PlayerImpl`: `getAvailableAttackers(defenderId, game)` uses battlefield active creatures plus `Permanent.canAttack`, and `getAvailableBlockers(game)` returns native active block candidates.

Construction policy:

- requested attackers/blockers/unblocked structure is restored/read from native `Combat`/`CombatGroup` state;
- `eligible_attackers` / `eligible_blockers` are derived from Rules-Core legal candidate queries at the exact snapshot, never copied as authoritative legality metadata.

### 2. `extra_turn_creation`

Classification: `DIRECT_NATIVE_TURNMOD_RESTORE_AND_READBACK`

Exact XMage source surfaces:

- `GameState.turnMods` is copied/restored native game state.
- `GameState.getTurnMods()` exposes it.
- `TurnMods` is `Serializable`, `Copyable`, and consumes extra turns from the end of the list via `useNextExtraTurn()`.
- `new TurnMod(playerId).withExtraTurn()` creates the native one-time extra-turn modification.

For the frozen two-resolution records, adding native extra-turn mods in semantic resolution order preserves XMage's LIFO next-turn ordering. No Time Warp/Nexus spell-resolution event may be synthesized.

### 3. `elimination_trigger`

Classification: `DERIVED_NATIVE_FROM_PLAYER_STATE_AND_SBA`

Exact XMage source surface:

`GameImpl` state-based actions test native player state directly: a player with `life <= 0` and `canLoseByZeroOrLessLife()` loses when SBAs execute.

Construction policy:

- WS42's existing native life restore sets the zero-life snapshot before Rules-Core continuation;
- do not mark the player lost during construction;
- independently normalize `elimination_trigger` from the native zero-life state and the frozen semantic condition profile;
- behavior resume must let XMage's real SBA machinery perform elimination.

### 4. `zone_move_event`

Classification: `PENDING_RULES_CORE_ENTRY_EVENT`

Exact XMage source surfaces:

- public `ZoneChangeEvent` constructors represent target/source/player/from-zone/to-zone without executing the event;
- public `ZoneChangeInfo` and `ZoneChangeInfo.Library` wrap that event;
- `ZonesHandler.maybeRemoveFromSourceZone` invokes `game.replaceEvent(event)` before the real move;
- `ZonesHandler` then performs actual movement and zone-change handling only if the event is not replaced;
- Commander graveyard/exile return choice is subsequently handled by XMage state-based actions using the real `player.chooseUse(...)` path.

Construction policy:

- materialize only the exact pending Battlefield -> destination entry event/metadata needed for resume;
- do not execute the move during construction;
- do not encode YES/NO pilot outcomes in construction state;
- on behavior resume, HAND/LIBRARY must pass through the real replacement-before-move boundary; GRAVEYARD/EXILE must move first and then pass through the real Commander SBA choice.

### 5. `knowledge_state` dynamic grants

Classification: `NATIVE_REVEALED_LOOKEDAT_TURN_CONTROL_PLUS_PROVIDER_VISIBILITY_LEDGER_REQUIRING_EXPLICIT_STATE_LOADER_FOR_NONEMPTY_GRANTS`

Exact native/provider surfaces:

- `GameState.getRevealed()` is native public reveal state.
- `GameState.getLookedAt(playerId)` is native per-player private look state; `LookedAt` is serializable/copyable and stores cards by look window.
- `PlayerImpl.setTurnControlledBy(playerId)` mutates native turn-control state; turn-control fields are copied/restored.
- existing `XmageKnowledgeLedger` derives visibility from native zones, `Revealed`, `LookedAt`, face-down state, library order and zone-change counters.
- it invalidates known library positions/identity grants on zone-change counter changes and library reorder/shuffle.
- it derives controlled-player decision authority from `decisionSubject.getTurnControlledBy()`.
- it has an explicit full-zone-look provider state (`beginZoneFullLook` / `endZoneFullLook`) used for search/look semantics and remembered library composition.

Construction policy:

- nonempty frozen grants must be installed through exact native `LookedAt` / `Revealed` / turn-control state where those surfaces exist;
- full-zone search/look state may use an explicit source-bound provider state-loader into `XmageKnowledgeLedger`, because that ledger is the existing actor-entitled observation authority, not pilot legality;
- no whole requested `knowledge_state` echo may be accepted as proof;
- channel policy, obligations, honey sentinels and permitted/prohibited metadata remain qualification metadata, not asserted native Rules state;
- dynamic grant/readback equality must come from native/provider observation state and invalidation behavior.

## Hidden-Identity Warning Preserved

The unpatched base `XmageKnowledgeLedger.stablePhysicalRef(...)` derives physical references from seat, deck fingerprint, deck zone, card name and occurrence. That form is NOT acceptable for WS46 AF05/opaque-identity qualification.

The historical WS42 hidden-identity overlay is implementation provenance only. Fresh v1.0.4 construction/security runtime must reapply or supersede it and prove that physical handles disclose no card identity, deck fingerprint, seat, zone, occurrence, native UUID, or Rules RNG state.

## Gates

- Reconciliation: `PASS`
- Fresh exact XMage build/native Commander-history + commander-damage restore: `PASS`
- Native construction-surface source audit: `PASS`
- Native construction runtime: `0/107` credited by this checkpoint
- Fresh behavior runtime: `0/107` credited by this checkpoint
- AF04/AF05/AF06/AF08/AF09: `NOT_GRANTED_BY_THIS_CHECKPOINT`
- CARD_02 behavior: `NOT_RUN_BY_THIS_CHECKPOINT`
- `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED`: `FALSE`

## Exact Next Action

Implement the v1.0.4-specific translator/native-state extension/readback/independent normalizer on these exact surfaces, then run a fresh source-bound 107-record construction workflow from record 1. Remediate every technically repairable mismatch until construction reaches 107/107 or a genuine terminal blocker is proven.
