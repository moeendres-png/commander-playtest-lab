# QUORUNE Source Audit — WS219 (exact pin 64ef6569)

Source lock: `NullPriority/quorune` commit `64ef65691b2952e29dfb2422687123d3ff5fc1b4`, tree `3dbb9619ec75bdebec74636a0a0b037cd0d85028`, read-only root `/home/moeen/code/ws219-ref-quorune-64ef6569`. Verified via `git rev-parse HEAD` + `HEAD^{tree}`. No writes made to candidate. License: Apache-2.0 (`LICENSE`, sha256 `9e6da557…`). All verdicts CODE_DERIVED unless probe says DIRECTLY_VERIFIED.

## 1. Architecture

- `ARCHITECTURE.md:21-34`: `CommanderEngine` + typed subsystems sole authority; one serialized game actor; projection precedes serialization; unknown Oracle fails closed; Game Record v3.
- `README.md:20-32`: primary target 4P Commander; duel profile narrower testing only; "does not implement every CR/Oracle interaction"; fail trusted preflight / stop before mutation. Boundaries: `docs/PLATFORM_IMPLEMENTATION_STATUS.md`, `docs/RULES_COMPLETENESS_STATUS.md`, `docs/COMPILER_COVERAGE_STATUS.md`.
- Layout: `quorune/` 266 top-level `.py` + packages (`compiler/`, `rules/`, `effect_runtime/`, `semantic_runtime/`, `selection/`, `card_programs/`, `reusable_pieces/`); `rules/` indexes only; `schemas/` 17 (command-envelope, decision-packet, game-record-v3-*, card-program-v2, pilot-*); `server/` 5 files.
- Kernel entry: `quorune/engine.py` (7488 lines) + `rules/action_catalog.py:50-80`, `rules/casting/proposal.py:400-483`, `rules/casting/commit.py:1329`, `rules/casting/costs.py:515-547`, `turn_priority_owner.py:136,262-265,539-574`, `turn_step_owner.py:149-184`, `permissions.py:36-214`.

## 2. Rules kernel (partial, typed, fail-closed)

- Costs/mana: fixed cases implemented; commander tax `parsed_cost(cost, commander_tax)` (`mana.py:330-334`, `engine.py:3275-3319`, `rules/casting/costs.py:515-547`). Gap: alternate/additional costs, restricted mana incomplete (`RULES_COMPLETENESS_STATUS.md:50`; `RULES_DEPENDENCY_QUEUE.md:44` blocked).
- Priority/APNAP: implemented (`turn_priority_owner.py:136,539-574`; `model.py:851-853`; `selection/apnap.py:19-445`; `replacement/model.py:715-780`). Conservative yield (`model.py:793`).
- Stack: implemented (`model.py:544,858`; `engine.py:3515,3641,3976-4036`; `stack_resolution.py:70-99`).
- Combat: ordinary paths implemented (`combat*.py`, `engine.py:6160-6283` CR510.1/802.5 APNAP assignment). Gap: assignment/evasion/prevention/damage-result variants incomplete; single-defender multiplayer variants fail closed (`test_beginning_of_combat_rules.py:122`).
- Targeting: typed bounded (`targets.py`, `selection/targeting.py:257,942`). Gap: broad target/search/trigger/loop/shortcut grammar missing.
- Triggers: APNAP batching implemented (`trigger_{batches,discovery,processing}.py`, `delayed_triggers.py`). Gap: intervening-if/reflexive/normalized-event-binding blocked (`RULES_DEPENDENCY_QUEUE.md:52-53`).
- Replacement/prevention: typed subset only; universal participation + simultaneous ordering missing (`RULES_COMPLETENESS_STATUS.md:47-48`; queue `replacement-prevention/counter-producer-replacement-closure` ineligible, plus `replacement-applicability`, `self-replacement-and-prevention-ordering`, `damage-prevention`, `regeneration` blocked).
- Continuous/layers: partial; `_SUBLAYER_ORDER` only Copy 1a/1b + P/T 7a-7d (`continuous_effect_model.py:29-36`). Gap: complete layers/dependencies/timestamps/CDA; queue blocks 2136 cards / 4949 residuals.
- SBAs: subset (life≤0, poison≥10, empty-draw, commander losers, CR704.5 pure evaluator `state_based_actions.py:12-80`; `commander.py:126-137` CR903.10a).
- Zones: implemented (library/hand/battlefield/graveyard/exile/command/stack/outside; seeded shuffle `zone_transitions.py:964-1014`).
- Copy/control: represented kinds (`engine.py:3765-3977`, `stack_resolution.py:70-99`, `control_history.py:100-165`). Face-down/merged incomplete.
- Extra turns: implemented (`model.py:849`, `turn_step_owner.py:149-184,290` CR800.4j).
- Elimination CR800.4-equiv: baseline implemented (`engine.py:7159-7224`: owned objects leave, hidden stay hidden, stack pruned, control returns else exile, monarch handling). Note conservative baseline `engine.py:7200-7202`.
- Mulligan/start: London-multiplayer implemented (`commander.py:156-160,253-254`; `engine.py:1533-1817`; `model.py:807-821` free=0 duel/1 multiplayer, first-player-draw only 3+P CR103.8).

## 3. Commander/multiplayer cardinality

- `command` zone (`commander.py:229-250`); tax `2×casts[oracle_id]` to GENERIC (`rules/casting/costs.py:515-547`); CR903.9 replacement (`commander_zones.py:1-217`); CR903.10a ledger keyed `commander:<seat>:<ordinal>` v2 (`commander.py:54-137`); `commander_damage_to_lose=21`, `starting_life=40` (`model.py:781-783`).
- Partner: `commander_pairing.py:1-384` kinds Partner/Partner-with/Background/Doctor's-Companion, capability-per-kind — typed family (registry `partial`).
- Cardinality constant `max_players=6` (`model.py:799`); constructor `2<=len(decks)<=max_players` (`commander.py:157-160`); `effective_profile` duel iff 2 else multiplayer. Runtime default `make_session(players=4)` (`tests/common.py:26-35`). Qualification evidence 4P-primary + duel-narrow (README); 3/5/6P constructible, no per-count conformance claim. Do not infer PASS from constant.

## 4. Legal-action generation

- `pending_decision: DecisionGroup|None` (`model.py:890`); `Capability{principal,actor,decision_id}`; `CommanderSession.packet(principal)` → `StateProjector.packet` (`session.py:238-251`, `projection.py:750`); `session.act(principal, response)` validates capability-for-principal (`session.py:549-659`, `service.py:320-456`, `permissions.py:101-156`); action IDs `pass/keep/mulligan/play_land/cast/activate/attack/block/assign_damage/resolve/choose/order/concede` (`session.py:36-64,304-313`); choice forms (`choice_forms.py:281,396,504`). Authority model credible; completeness bounded by typed program coverage (fail-closed outside).

## 5. Hidden information

- Omniscient `GameState` server-side only; `StateProjector` per-principal views (`projection.py:77-99`); facade comment "one session client per pilot context" (`session.py:68-74`); ADR 0002 seat projections, protocol 3.0.
- Mandatory principal: `session.packet(principal)`, `permissions.capability_for(principal)` (`permissions.py:101-108`), mismatch → `PermissionDenied`.
- Hiding: `_card_visible` (`projection.py:157-190`); `known_to/revealed_to` (`zone_object_state.py:120-173`); `_event_visible` seat/spectator/analyst scoping; commander damage rows withhold zone; elimination preserves pre-left knowledge only (`engine.py:7184-7197`); `GameConfig.hidden_information_mode="seat-projected"`.
- Entitlements: reveal/look/search via typed continuations with seat-scoped projection + rollback/replay (`selection/searching.py:348,616-617,988-989`).
- Controls: `hidden-information-audit.json` in record; `test_permissions_projection.py` et al. Correctness per-family, not universal over 31k Oracle.

## 6. Determinism/RNG/replay/record

- RNG: all Rules randomness via `random.Random(f"{seed}|…")` (initial shuffle `commander.py:253-254`; library shuffle `zone_transitions.py:1003-1006`; mulligan redraw `engine.py:1746`). `GameConfig.seed:int|None` (`model.py:791`); CLI `--seed`. No unseeded production path in sampled owners.
- Record: Game Record v3 dir (`manifest.json`, `initial-checkpoint.json.gz`, `checkpoint.json`, `commands.jsonl` with capability digest + RNG + before/after hashes, `events/decisions/opportunities/semantics/cursors/review/hidden-information-audit`). `RECORD_SCHEMA_VERSION=3`.
- Replay: `replay_mode="command_replay"` (`session.py:84`); `replay_record()` re-executes commands from initial checkpoint, verifies hashes (`record.py:953-1110,1110-1182`); canonical SHA256 excluding events/caps/presentation (`record.py:68-112`); clean-process resume via `plans.json` + reissued opaque capabilities. Exact only for supported programs/pins; unsupported fails preflight (fail-closed, not coverage).

## 7. Card/Oracle lowering (measured ~31.5% exact, fail-closed)

- Pinned Oracle snapshot → `OracleCardIR` → CardProgram V2 + SemanticProgram index (`COMPILER_COVERAGE_STATUS.md:18-24`); `oracle-ir-v189`, schema v2; behavior only from source-spanned CardPrograms + registered owners, never fixed-identity generic behavior.
- Counts (DIRECTLY_VERIFIED via probe `probes/ws219_quorune_frontier_check.py` + generated docs): Commander Oracle objects `31623`, exact fraction `0.31534`, capability records `267`, residuals `30351`, blocked caps `4`; pinned rules `3309`, queued `2860`. Frontier records `31623` confirmed by probe.
- Frozen-29 probe result (DIRECTLY_VERIFIED): 8 trusted (`Ishai, Rograkh, Narset-Parter, Dig Through Time, Psychosis Crawler, Butcher of Malakir, Gratuitous Violence, Basilisk Collar`) with zero blockers at card level; 21 residual with minimum blockers concentrating in `continuous-effect-layers-and-dependencies`, `intervening-if-and-reflexive-trigger-grammar` + `normalized-event-binding`, `replacement-applicability` + `self-replacement-and-prevention-ordering`, `ordered-effect-composition`, `multiple-targets`, `unparsed-overload/cleave/choose-one/change-target`. Zero of 29 have behavior tests (only Vandalblast has 2 cost-option casting tests, still residual on overload body; Boseiju synthetic fixture only). Construction/readback gets zero behavior credit.
- Unsupported: fail-closed by design (`RULES_COMPLETENESS_STATUS.md:12-15,60-65`; `preflight.py:895-996`; `admission.py:49-50` admitted = exact && 0 residuals; error taxonomy `Unsupported*/Material residual`).

## 8. Tests (inventory, NOT RUN as suite)

- `tests/test_*.py` = 343 (matches `PLATFORM status:26-27` modules 343 / shards 13); `quorune/*.py` = 266.
- Rules/core, Commander/multiplayer (`test_command_zone_rules`, `test_commander_{damage_identity,pairing,match_readiness}`, `test_multiplayer_rules:161`, `test_concession_rules`, `test_monarch_rules`, `test_goad_rules`), determinism/replay (`*_replays_exactly`, `test_deterministic_full_game`, `test_game_record_v3`, `test_record_lifecycle_v060`), hidden-info (`test_permissions_projection`, `test_selection_ownership`, `test_semantic_searches`), legal-action API (`test_action_proposals`, `test_application_protocol`, `test_protocol{,_reference}`, `test_decision_opportunities`, `test_game_actor`), exact-closure suites (`test_exact_{mishra,zimone,deck_interactions,combat_keywords,keyword_families,land_families,mana_families}_*`). No 29-card suite. Inventory proves breadth, not PASS. `UNKNOWN != PASS`.

## 9. Declared unsupported (exact pointers)

- `RULES_COMPLETENESS_STATUS.md:44-55`; `PLATFORM status:33-37`; `COMPILER status:28-32`; `RULES_DEPENDENCY_QUEUE.md:37-60+` (21 subsystems; continuous-layer/replacement/target/duration/static/event/activated-cost residuals blocked).
- Code: `NotImplemented/Unsupported*` taxonomy + `preflight.py:37-80` gates; `engine.py:7200-7202` control baseline; `test_beginning_of_combat_rules.py:122` multiplayer variants fail closed; tutor fail-closed (`semantic_packs/tutor-searches.json:516-603`).

## Bottom line

Deterministic, seat-projected, command-replayed, fail-closed partial Commander engine (2-6 seats constructible, 4P primary). Typed coverage of priority/APNAP, stack, SBA subset, zones, mulligan/start, commander tax/damage/zones/Partner-family, seeded RNG, Game Record v3 + hash-chained replay, ~31.5% exact lowering — all CODE_DERIVED except frontier counts + Partner gate + preflight/admission logic which are DIRECTLY_VERIFIED by probe. Material gaps to Full-Rules: universal layers/dependencies/timestamps/CDA; universal replacement/prevention + simultaneous ordering; complete costs/restricted-mana; face-down/merged/special-action/unusual-zone/copy/linked completeness; broad target/search/trigger/loop/shortcut grammar; full combat variants; ambient cross-card closure; per-count 2-5P runtime conformance; frozen-29 0/29 SUPPORTED.
