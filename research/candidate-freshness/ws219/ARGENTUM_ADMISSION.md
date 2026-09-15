# ARGENTUM Admission — WS219

Verdict: **DO_NOT_PROMOTE_CURRENT_PIN**

Source lock: `3f46367d87c88bcf156a843a9e69fd29e1693872` (tree `2adf51ca…`). This is not Provider Selection. `ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`. Built-in AI was never treated as Rules authority; excludability assessed separately.

## Why not promote (exact blockers)

1. **AF07 terminal: 18/29 frozen cards MISSING.** DIRECTLY_VERIFIED probe `probes/ws219_argentum_card_check.py` (`distinct_card_names=13915`): only 11 `card()` defs (`Wash Away`, `Dig Through Time`, `Finale of Revelation`, `Shriekmaw`, `Syphon Mind`, `Gratuitous Violence`, `Bolt Bend`, `Makeshift Mannequin`, `Warstorm Surge`, `Basilisk Collar`, `Path of Ancestry`); 18 absent (no `card()`, no snapshot). Of the 11, only 5 have dedicated behavior tests → SUPPORTED (`WashAway`, `DigThroughTime`, `FinaleOfRevelation`, `SyphonMind`, `MakeshiftMannequin`); 6 are PARTIAL (cardDef+snapshot, zero dedicated tests). Evidence: `ARGENTUM_FROZEN_CARD_MATRIX.json`.
2. **Partner init block (AF07+AF08 terminal for Commander).** DIRECTLY_VERIFIED `rules-engine/.../core/GameInitializer.kt:38-44` ("Phase 1 supports a single commander; partner/Background pairings are Phase 4") + `PlayerConfig.commanderCardName:String?` singular + `game-server/.../deck/DeckValidator.kt:323` Partner unsupported. All four Partner commanders in the frozen denominator (`Ishai, Rograkh, Esior, Kediss`) have no `card()` AND could not initialize a Partner game even if defined.
3. **OVERLOAD absent (AF06/AF07).** `mtg-sdk/.../core/Keyword.kt` has no OVERLOAD (111 keywords, STORM present); only inert `was-overloaded` flag. `Vandalblast` therefore impossible at this pin.
4. **Split/aftermath/saga-MDFC wiring missing for frozen split cards.** `Wear // Tear` (fuse), `Find // Finality` (aftermath-split), `Boseiju Reaches Skyward // Branch of Boseiju` (saga-MDFC) assayed `MULTI_FACE` with no `card()`; infra exists but unwired for these cards.
5. **AF06 parity: replacement non-draw domains.** Only draw domain migrated to central `ReplacementEffectProcessor`; others on own dispatchers (`architecture-principles.md:873-878`). Frozen cards touching damage/life/token/zone-change replacement need per-domain proof.
6. **AF09: Slot-only, not clean-process semantic replay.** `SnapshotCodec.kt:17-50` in-process `Slot` only ("leaves room for byte-blob once we need"); no clean-process semantic replay under Commander-Lab definition. AF05 gaps also open (emblems unobserved; `HiddenSlotRewrite` side-lists out of scope).

## What is credible (and why it is not enough)

- Immutable pure-state core + sole `ActionProcessor` authority + pure-data `cardDef` DSL + fail-closed missing-card model — credible AF03/AF04-design.
- 22-family enumerator + 17 PendingDecision/DecisionResponse — broad AF04 surface (but incomplete: see blockers).
- Mandatory-principal visibility (`Visibility.kt`, `ClientStateTransformer`, `ObservationBuilder` with debug-only `revealAll`) — credible AF05-design with documented gaps.
- 2-6P FFA + teams + tax/zone/damage/mulligan/start/elimination in code — plausible AF02/AF08-path except Partner.
- Seeded SplitMix64 RNG + same-seed byte-identity + CompactReplay+checkpoints — credible determinism, but in-process only (AF09 gap).
- Built-in AI excludable from engine via `rules-engine` directly / `stepExactlyOne` (but NOT via gym without refactor: `gym/build.gradle: implementation(project(":ai"))`). AI exclusion does not repair card/replacement/replay gaps.

## Affected gates / denominator

- FAIL-closed (not PASS): AF07 (5/29 SUPPORTED, 6/29 PARTIAL, 18/29 MISSING), AF04 (completeness), AF06 (replacement parity), AF08 (Partner-dependent MUST), AF09 (clean-process replay), AF10 (0/175).
- Frozen denominator: 5 SUPPORTED / 6 PARTIAL / 18 MISSING / 0 UNKNOWN of 29.

## What would have to change upstream

- Implement 18 missing frozen `card()` defs + snapshots (incl. 4 Partner commanders, Veyran, Harmonic, Narset-Parter, Jeska-Thrice, Magma Opus, Wear//Tear, Flare, Vandalblast, Psychosis, Kaervek-Merciless, Butcher, Burn, Find//Finality, Boseiju-Reaches).
- Implement Partner/Background Phase-4 + color-indicator + lobby commander plumbing; implement OVERLOAD; wire split/aftermath/saga-MDFC for the three frozen split cards.
- Migrate non-draw replacement domains to central processor with per-domain proof; close emblems + HiddenSlotRewrite side-lists observation gaps.
- Promote SnapshotCodec to byte-blob + prove clean-process CompactReplay reconstruction with tapes/hashes (WS218 Tape v1).
- Add behavior tests for the 6 PARTIAL cards; untangle gym→ai dep for adapter path.
- Execute per-count 2-5P + WS05 MUST + MICRO + HIDDEN + REPLAY fixtures at runtime.

## Why further current qualification would not alter admission

Additional runtime at this pin would only re-confirm that missing cards fail closed at discovery/init (correct) and inventory existing tests; it cannot invent 18 card implementations, Partner, OVERLOAD, or byte-blob replay. The blocker is upstream implementation, not measurement. Expensive Gradle execution was therefore stopped per Early Stop Rule after bounded probes.

## Bounded next-step plan (if Coordinator ever re-opens)

1. Upstream implements the 18 cards + Partner + OVERLOAD + split wiring.
2. Re-probe `card()` census: require 29/29 defs + snapshots.
3. Add/extend behavior tests to 29/29 SUPPORTED (dedicated scenario test per CARD_*).
4. Prove replacement-domain parity for frozen-touching domains + close hidden gaps + byte-blob replay proof.
5. Then run full AF02/AF04/AF05/AF06/AF07/AF08/AF09/AF10 fixture campaign before any promotion discussion.
