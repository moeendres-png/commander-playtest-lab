# RQ-A2 — Ability-ID / Process-Global Identity Impact (U22)

Question: does process-global `AbilityId` generation affect semantic state equality, replay
equality, legal-option identity, event equality, persisted replay compatibility, or
cross-process reconstruction? Evidence: `evidence/u22/` (four same-game fresh-JVM pairs +
pinned/unpinned persisted replays + same-JVM token diff), all at the candidate lock.

## 1. Mechanism (CODE_DERIVED, then runtime-confirmed)

- `AbilityId.generate()` = process-global `AtomicLong` (`mtg-sdk/.../scripting/AbilityId.kt:15`).
  Consumed at (a) card-definition load (`TriggeredAbility.create` defaults, DSL builder
  defaults — deterministic given identical load order) and (b) runtime (storm/copy instance
  triggers in `CastSpellHandler`).
- `EntityId.generate()` = random UUID. RQ-A1 recorded it as absent from live paths; RQ-A2
  REFUTES that: one live use exists — `ActivateAbilityHandler.executeActivation` stamps a fresh
  `EntityId.generate()` as the activation's `ObjectReferenceEnvironment.resolutionKey`
  (`ActivateAbilityHandler.kt:687-691`). Identity-only, never matched against recorded input.
- Routing ids `r<N>` (`GameState.nextRoutingId`), entity ids `e<N>`, and `GameRng` state are
  state-threaded and stable across processes (all runs).

## 2. Same-game fresh-process comparison (DIRECTLY_VERIFIED)

| Game | Frames | Canonical match | Raw match | Notes |
|---|---|---|---|---|
| S1 Study/discards | 184/184 | 184 | 184 | pending ids + routing stable |
| S2 Elves activation | 61/61 | 61 | 61 | intrinsic `intrinsic_mana_G` id, deterministic |
| S3 Tendrils storm | 174/174 | 174 | 174 | 2 frames carry runtime storm ids; values coincided (same load order + same prefix) |
| S4 Sorcerer ping | 108/108 | 108 | 106 | 2 activation frames differ ONLY in the activation `resolutionKey` UUID |

Total: 527 frames canonical-EXACT across fresh JVMs; routing/entity/RNG identities stable.

## 3. Where raw identity moves (localized, behavior-neutral)

- **S3 same-JVM diff**: live storm minted `ability_12449`; the later re-fold minted
  `ability_12451/12452` — the global counter had advanced by the live game's own later
  consumption. Runtime-minted ids depend on process history, not just the game.
- **S4 cross-JVM**: the activation `resolutionKey` UUID differs per run (frames 99-100);
  `ability_33` (definition-level ping id) is IDENTICAL across JVMs (load-order deterministic).
- In every case the canonical (normalized) digest matches and all SUBSEQUENT frames match
  exactly — no Rules behavior reads these values across runs (decisions key on stable
  routing ids; yields key on definition-scoped `AbilityIdentity`).

## 4. Legal-option identity (DIRECTLY_VERIFIED)

- S4's recorded `ActivateAbility(abilityId=ability_33)` replays EXACT cross-process, pinned
  AND unpinned: the handler's definition lookup (`lookupActivatedAbility`: definition match,
  class-level-up, grants, intrinsic) resolves the same-corpus id deterministically.
- Test-fixture UUID definition ids (mana dorks) would fail closed cross-process
  (`DirectDefinition` miss → "Ability not found" error path, CODE_DERIVED) — bounded to
  fixtures, not the production corpus. S2 showed the intrinsic path is used instead.

## 5. Event equality

Normalized event streams match everywhere (U19 per-action events + S3 storm events).
`CoinFlipEvent` outcomes reproduce exactly (CONTROLLED_RULES_RNG).

## 6. Persisted replay compatibility

- `ReplayCodec` round-trips all replays byte-equal (DIRECTLY_VERIFIED).
- Pinned replays: `ReplayReconstructor` EXACT, fidelity EXACT (checkpoints verify).
- Unpinned replays: EXACT canonical, fidelity UNVERIFIED (no checkpoints by construction).
- Pinned cards cover DEFINITION drift; runtime-minted ids need no covering (rebind by
  position; decisions keyed by routing ids) — proven by the EXACT replays above.

## 7. Verdict

`RULES_SEMANTIC_IDENTITY` HOLDS cross-process on the tested paths (DIRECTLY_VERIFIED,
527 frames); `NON_RULES_DEBUG/TRANSPORT_IDENTITY` is isolated to (a) runtime
`AbilityId.generate()` values, (b) `EntityId.generate()` activation resolutionKeys,
(c) test-fixture UUID def ids. Normalization belongs safely in a non-Rules
provider/journal layer for the tested paths: no Rules path reads these values by identity
across runs (evidenced). No candidate change needed or made. A globally different
incidental ID does not fail Semantic Replay here.

## 8. Explicit UNKNOWN holes (not proven; must stay UNKNOWN)

- Yields/batches over synthetic identities are unexercised (`yieldsByPlayer` empty in all
  observed frames). An `AbilityIdentity(cardDefinitionId, abilityId)` built from a
  runtime-minted storm id would differ per run — "no Rules path reads these values" is
  proven only for yield-free/batch-free paths.
- Test-fixture UUID definition ids fail closed cross-process (`DirectDefinition` miss →
  "Ability not found"); normalization does not make fixture replays portable. Bounded to
  fixtures, not the production corpus.
- Persisted unpinned replays are EXACT-canonical but fidelity UNVERIFIED by construction
  (no checkpoints).
