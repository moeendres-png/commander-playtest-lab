# RQ-X1 — Selection → Native Object → Execution (CODE_DERIVED, key cites DIRECTLY_VERIFIED)

Pin: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`. This is the critical WS48-lesson
file: a label matching an object is NOT sufficient — determine whether selection
binds the exact native object.

SHORT ANSWER: XMage binds by exact native UUID with server-side revalidation
(binding at choice + re-resolution at use). Label matching does NOT suffice.
`Choice` string-keys are the single exception (bounded, membership-checked).

## 1. Identity primitives (all native, all UUID)

| Primitive | Definition | Role |
|---|---|---|
| Object identity | `MageObjectImpl.objectId = UUID.randomUUID()` at construction (`mage/MageObjectImpl.java:28,57-58,98-100`); `CardImpl.assignNewId()` (`mage/cards/CardImpl.java:146-153`) | every card/permanent/token/spell/emblem instance |
| Ability identity | `AbilityImpl.id = UUID.randomUUID(); originalId = id` (`mage/abilities/AbilityImpl.java:66-67,101-103`); `newId()` on copy (`:151-170`) | every ability instance; copies keep `originalId` for lookup (`AbilitiesImpl.java:253,299-300`) |
| Effect / Mode identity | `EffectImpl.id = UUID.randomUUID()` (`:19,32`); `Mode.id = UUID.randomUUID()` (`mage/abilities/Mode.java:17,31`) | effect/mode instances |
| Player identity | `PlayerImpl(name,range)` mints `UUID.randomUUID()` (`mage/players/PlayerImpl.java:204-205`); `playerId = id` | in-game principal |
| Game identity | `GameImpl.id = UUID.randomUUID()` (`mage/game/GameImpl.java:177`) | game/session handle |
| Zone-aware binding | `MageObjectReference` = `sourceId:UUID + zoneChangeCounter:int` (`mage/MageObjectReference.java:25-58`); `refersTo()` compares id AND zcc (`:143-159`); dereference returns null on ZCC mismatch (`:169-199`) | server-side stale-object rejection |
| NOT identity | `MageIdentifier` enum (`mage/MageIdentifier.java:9-96`) — watcher/alternate-cast tagging only | must not be mistaken for object identity |

Two identical tokens have distinct UUIDs (`PermanentToken` per-instance random
id, `mage/game/permanent/PermanentToken.java:28-31,321`). Duplicate-equal
objects CANNOT be confused: every store is `Map<UUID,…>` checked by
`contains/containsKey/id.equals` (`TargetImpl.java:26,331,356,697,832`;
`PlayableObjectsList.java:16`; `AbilityPickerView.java:19`).

## 2. Request → response → resolution flow (server GAME thread → client → GAME thread)

Server→client (all carry verbatim UUIDs, DIRECTLY_VERIFIED carriers):

- `HumanPlayer.choose/chooseTarget` → `fireSelectTargetEvent(playerId, msg,
  possibleTargets:Set<UUID>|cards, required, …)` (`HumanPlayer.java:734-735,
  805-806,904,997,1105`; `GameImpl.java:3153-3166` signature
  `fireSelectTargetEvent(UUID playerId, MessageToClient, Set<UUID>, boolean,
  …)` — DIRECTLY_VERIFIED at `GameImpl.java:3153`).
- `fireGetChoiceEvent(playerId,msg,object,List<ActivatedAbility>)`
  (`GameImpl.java:3133`; `HumanPlayer.java:2308,2365,2433,2482`).
- `GameController` fans out per-player: `chooseAbility → AbilityPickerView`
  (`Map<UUID,String> choices`, `AbilityPickerView.java:19,45,66-68`);
  `target → CardsView/PermanentView + Set<UUID> targets`
  (`GameController.java:864-908`); each recipient gets its own
  `GameSessionPlayer.ask/target/select/…` with a per-viewer `GameView`
  (`GameSessionPlayer.java:49-124`).
- Client echoes the UUID: `CallbackClientImpl GAME_TARGET→pickTarget(…,
  getTargets())`, `GAME_CHOOSE_ABILITY→pickAbility` (`:317-346`);
  click handlers call `sendPlayerUUID(gameId, abilityId|card.getId()|playerId)`
  (`AbilityPicker.java:45-46,72-75`; `GamePanel.java:3081-3096`;
  `SessionHandler.java:135-136`).

Client→server (CALL thread → GAME thread handoff):

- `GameController.sendPlayerUUID/String/Boolean/Integer` (`:789-807,
  1059-1087,1157-1229`) checks only game-under-control + priority/control
  routing, then `GameSessionPlayer.sendPlayerUUID(data)` → 
...[truncated 6151 chars]