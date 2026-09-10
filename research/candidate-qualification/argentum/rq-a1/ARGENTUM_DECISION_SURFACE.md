# RQ-A1 — Argentum Decision Surface Matrix

Source: `/tmp/rq-argentum-src` at lock `3f46367`. Classification: `CODE_DERIVED` (static source trace; no runtime probing). Labels per contract: `NATIVE_EXPLICIT | NATIVE_BUT_GUI_COUPLED | NATIVE_BUT_AI_COUPLED | INDEX_BASED | OBJECT_ID_BASED | SEMANTIC_ID_AVAILABLE | ADAPTER_REQUIRED | UNKNOWN`.

Machine-readable sidecar: `ARGENTUM_DECISION_SURFACE.csv` (same rows).

## Protocol recap

- Enumerated options: `LegalActionEnumerator.enumerate(state, playerId)` → `LegalAction(action: GameAction, …metadata)`.
- Questions: `PendingDecision` (~19 types) on the suspension stack; answers: typed `DecisionResponse` via `SubmitDecision(playerId, response)`.
- Guards: acting-player check, exact `pending.id == response.decisionId`, per-kind `DecisionValidators` against current option sets, session `interactionEpoch` freshness on live transports.
- No `gameId`/`state-revision` inside engine decisions; staleness handled by decision-ID equality + epoch (see Identity file).

## Matrix

| # | Decision kind | Label | Binding (option → selection → execution) |
|---|---|---|---|
| 1 | Starting player | UNKNOWN | No live seam found. `GameInitializer` takes `startingPlayerIndex: Int?` config; no `PendingDecision`/`GameAction` for choosing. Externally decidable only via config, not verified as a decision. |
| 2 | Mulligan | NATIVE_EXPLICIT | `TakeMulligan / KeepHand / BottomCards(playerId, cardIds)` native actions; London bottom-count engine-computed; `BottomCards` validated against hand. |
| 3 | Priority / pass | NATIVE_EXPLICIT | `PassPriority(playerId)` enumerated; submit unchanged. |
| 4 | Cast spell | NATIVE_EXPLICIT | Concrete `CastSpell(…, cardId, faceIndex?, useAlternativeCost, alternativeCostType?, declaredCostSlot?, graveyardCastRider?, additionalCostPayment?, paymentStrategy, …)` variants. Variant = native pick; X/modes/targets complete via bounded channels below. |
| 5 | Activate ability | NATIVE_EXPLICIT | Concrete `ActivateAbility(…, sourceId, abilityId: AbilityId, …)`; `abilityId` pre-stamped by enumerators; single-target auto-pick variants embed targets. Engine-only `opponentTargetsChosen` marker rejected on client submit. |
| 6 | Mana-source selection | OBJECT_ID_BASED | `SelectManaSourcesDecision(availableSources: List<ManaSourceOption>, requiredCost, autoPaySuggestion, canDecline)` → `ManaSourcesSelectedResponse(selectedSources: List<EntityId>, autoPay, declined)`. |
| 7 | Mana payment | OBJECT_ID_BASED | `PaymentStrategy.AutoPay / FromPool / Explicit(manaAbilitiesToActivate: List<EntityId>, phyrexianLifePayments)`; `ManaPaymentWindow` + `enumerateManaAbilities` (CR 605.3a). Engine solves/validates. |
| 8 | Alternate / additional costs | NATIVE_EXPLICIT | Which stamped variant to submit (`alternativeCostType`, `useAlternativeCost`, `useWithoutPayingManaCost`, `declaredCostSlot`, `graveyardCastRider`, `faceIndex`, `AdditionalCostPayment` payloads). Never collapse `PlayLand` face variants. |
| 9 | X values | NATIVE_EXPLICIT | Inline `xValue` on cast/activation/cycle/turn-face-up + resolution-time `ChooseNumberDecision(min,max)` → `NumberChosenResponse`; `hasXCost/maxAffordableX/minX` hints; engine range-checks. |
| 10 | Modes | INDEX_BASED | `ChooseModeDecision(modes: List<ModeOption(index,text,available)>, minModes, maxModes)` → `ModesChosenResponse(List<Int>)`; cast-time `chosenModes: List<Int>` + `modeTargetsOrdered`; `BudgetModal` variant same shape. Indices are printed-order positions. |
| 11 | Targets (incl. optional) | OBJECT_ID_BASED | `ChooseTargetsDecision(targetRequirements, legalTargets: Map<Int,List<EntityId>>)` → `TargetsResponse(Map<Int,List<EntityId>>)`; membership + min/max + no-duplicates + same-owner/different-names/controllers/MV-cap validated. Optional = `minTargets == 0` (empty list legal). `canCancel` → `CancelDecisionResponse`. |
| 12 | Numeric choices | NATIVE_EXPLICIT | `ChooseNumberDecision(min,max)` → `NumberChosenResponse`; range-checked. |
| 13 | Colors | NATIVE_EXPLICIT | `ChooseColorDecision(availableColors)` → `ColorChosenResponse`; membership-checked. Plus `ChooseManaColor` / `ActivateAbility.manaColorChoice`. |
| 14 | Card names | INDEX_BASED | `ChooseOptionDecision(options: List<String>)` → `OptionChosenResponse(optionIndex)`; range-checked. `OptionMetadata.id` may ride along but response is the index. |
| 15 | Creature types | INDEX_BASED | Same `ChooseOptionDecision` with `options = Subtype.ALL_CREATURE_TYPES`; secret variant adds `secretTo` stamping only. |
| 16 | Ordering (library etc.) | OBJECT_ID_BASED | `OrderObjectsDecision` / `ReorderLibraryDecision` → `OrderedResponse`; exact-permutation enforced (`isSameCollection`). |
| 17 | Trigger ordering (APNAP/stack) | INDEX_BASED | Ordering pauses surface as `ChooseOptionDecision` (`TriggerProcessor.kt:~1066/1481`); engine exposes `apnapOrder`; response `optionIndex`. Per-path UI not exhaustively mapped. |
| 18 | Replacement ordering | INDEX_BASED | `ReplacementEffectProcessor` raises `ChooseOptionDecision`; `allowedToByFrom` enforced; validator range-checks. |
| 19 | Attackers | ADAPTER_REQUIRED | Exactly one template `DeclareAttackers(playerId, emptyMap())` + `validAttackers / mandatoryAttackers? / validAttackTargets?`. Pilot fills `attackers: Map<EntityId,EntityId>` from candidates. Empty template = no-op declaration (succeeds). Engine revalidates (permissions, mandatory, defenders, AttackMode). |
| 20 | Defender per attacker | ADAPTER_REQUIRED | Value side of the attacker map (defending player/planeswalker/battle from `CombatDefenders` rules). No separate decision object. |
| 21 | Blockers | ADAPTER_REQUIRED | Template `DeclareBlockers(playerId, emptyMap())` + `validBlockers / blockerMaxBlockCounts? / mandatoryBlockerAssignments?`. Pilot fills `blockers: Map<EntityId,List<EntityId>>`. Empty = block nobody. Engine revalidates. |
| 22 | Damage assignment | SEMANTIC_ID_AVAILABLE | Canonical: `CombatResolutionDecision(edges: List<DamageEdge{id="$sourceId->$targetId", sourceId, targetId, maximum, lethal, orderConstrained, editableBy, amount})` → `CombatResolutionResponse(edges: List<DamageEdgeAmount(edgeId, amount)>, …)`; engine resolves via cached edges, never parses the wire id. Legacy paths persist: `OrderBlockers` (object IDs), `AssignDamageDecision` → `DamageAssignmentResponse`. No separate order step ("no separate damage-assignment order step" per source). |
| 23 | Divide / distribute | OBJECT_ID_BASED | `DistributeDecision(totalAmount, targets, min/maxPerTarget, allowPartial)` → `DistributionResponse(Map<EntityId,Int>)`; sum + membership + bounds validated. Pre-chosen division rides as `damageDistribution` maps on cast/activation. |
| 24 | Discard | OBJECT_ID_BASED | `SelectCardsDecision(options, min/maxSelections, …)` → `CardsSelectedResponse`; membership + count (+MV floor / conditional minimums) validated. |
| 25 | Sacrifice | OBJECT_ID_BASED | Same `SelectCardsDecision` shape in-resolution; cost-time via `AdditionalCostData.validSacrificeTargets/sacrificeCount/costAfterSacrifice` + `AdditionalCostPayment`. Server revalidates. |
| 26 | Search | OBJECT_ID_BASED | `SearchLibraryDecision(options, min/maxSelections, cards: Map<EntityId,SearchCardInfo>, filterDescription)` → `CardsSelectedResponse`; `minSelections=0` encodes fail-to-find. |
| 27 | Hidden-zone selection | OBJECT_ID_BASED | Same search/select object-ID mechanism with masked presentation (`SearchCardInfo` embedded; `Visibility` per-card identity checks). Response carries only `EntityId`s. |
| 28 | Reveal | OBJECT_ID_BASED | No reveal wire type: reveal is a visibility side effect (`RevealedToComponent`, `MayLookAtInExileComponent`, `ForetoldComponent`) on a select/search flow. Pilot submits object IDs; visibility is engine-computed. |
| 29 | Scry | OBJECT_ID_BASED | Macro → composite pipeline (`ScryExecutor` → select + `PutOnTopOrBottomOfLibraryExecutor` (`ChooseOptionDecision`) + `MoveCollectionExecutor` (`ReorderLibraryDecision`)). Per-step native bindings; scry itself is not one atomic pick. |
| 30 | Surveil | OBJECT_ID_BASED | Same as scry via `SurveilExecutor` twin. |
| 31 | Piles | OBJECT_ID_BASED | Construction: `SplitPilesDecision(cards, numberOfPiles, pileLabels, cardInfo?)` → `PilesSplitResponse(piles)` with flattened exact-permutation check. Opponent's pile pick is a follow-up `ChooseOptionDecision` (index). |
| 32 | Voting | UNKNOWN | No vote/council/will-of-the-council decision type or executor found. Not verified as implemented. |
| 33 | Secret / simultaneous choices | INDEX_BASED | Sequential APNAP suspensions, not cryptographic simultaneity. Secret type-picks: `ChooseOptionDecision` + `NotedCreatureTypesComponent(secretTo)`. Secret numeric bids: per-player `ChooseNumberDecision` (`SecretBidExecutor`). |
| 34 | May / optional abilities | NATIVE_EXPLICIT | `YesNoDecision(yesText/noText, abilityIdentity?)` → `YesNoResponse`; batches via `BatchYesNoDecision(count)` → `BatchYesNoResponse(choice, applyToAll)`. Persistent yields can auto-answer (logged). |
| 35 | Optional replacement | INDEX_BASED | `ChooseOptionDecision` (apply/decline + which replacement); per-instance damage-redirection answers persist in `optionalDamageRedirectChoices` (missing = declined). |
| 36 | Copy choices | INDEX_BASED | Copy-which pauses as `ChooseOptionDecision` (`ModalAndCloneContinuationResumer`, `CopyEachTargetSpellExecutor`, …); new targets for the copy remain `ChooseTargetsDecision` (object IDs). |
| 37 | Commander replacement | NATIVE_EXPLICIT | 903.9a SBA yes/no prompt (`CommanderZoneChoiceContinuation` + `CommanderZoneChoiceAskedComponent` dedupe) → `YesNoResponse`. |
| 38 | Concession | NATIVE_EXPLICIT | `Concede(playerId)`; `validate() = null` (always legal, CR 104.3a). Multiplayer: eliminates only that seat. |

## Second-legality flags (adapter/AI-side construction)

All funnel through `ActionProcessor`/`GameSimulator`/session gates and are engine-revalidated, but each *constructs or narrows* the submitted object instead of echoing an untouched enumerated template. None is a production-reachable legality fabricator; all are recorded so the pilot contract can distinguish "echo" from "assemble":

- `ai/.../Strategist.kt`: simulates, then materializes winner (`chooseCommittedTargets`, `bindBestX`, `expandXCostAbilities`, `preferKickerVariants`); combat → `CombatAdvisor`; filters `MeaningfulActionFilter` + `affordable && !isManaAbility`; fallback `pass ?: legalActions.first()`.
- `ai/.../CombatAdvisor.kt`: builds `DeclareAttackers/DeclareBlockers` maps from candidate lists + simulations.
- `ai/.../AIPlayer.kt`: `chooseAction` selects, but `playPriorityWindow` synthesizes mandatory-based combat fallbacks; decision path builds `SubmitDecision`.
- `ai/.../EngineAiPlayerController.kt`: unmasked-state controller; single-action shortcut echoes `legalActions.first().action` except combat.
- `ai/llm/LlmAiPlayerController.kt`: parses LLM text into `DeclareAttackers/DeclareBlockers` from `validAttackers/validBlockers` indices.
- `ai/.../GameSimulator.kt`: synthesizes `SubmitDecision` (trivial/resolver-driven) + `PassPriority` auto-passes to reach quiet states. Harness, engine-checked.
- `game-server/.../GamePlayHandler.kt (~1408-1432)`: AI fallback synthesis incl. no-op `DeclareAttackers(emptyMap())`.
- `game-server/.../AiWebSocketSession.kt`: async AI adapter builds `SubmitDecision` fallbacks; carries epoch through thinking/approval.
- `game-server/.../GameSession.kt`: builds `Concede(playerId)`; empty-`DeclareAttackers` probe/undo paths.
- `gym/.../ActionParams.kt` (`ActionParameterizer.apply`): copies attacker/blocker/cast/activation templates with caller params; `resolveTarget` reconstructs `ChosenTarget` variant from bare `EntityId` via current-state lookup (documented as reading game-state fact, not request data); `allowOnly` rejects inapplicable params.
- `gym GameGymEnv/GameEnvironment`: per-step integer registry; `submitDecision` builds `SubmitDecision` after ID check; `playGame` falls back to first affordable action.

Not found in production paths: direct engine-internal calls (`sa.resolve()` substitutes), standalone `AbilitySub` substitutes, `EntityId.generate()` for live objects, or option-list filtering that drops legal variants (the `PlayLand`-face warning in `engine-server-interface.md` is a documented hazard, not an observed violation; `web-client/src` option-filtering not traced — see Unknown Ledger).

## GUI/AI-coupled facets (secondary, not row labels)

- GUI must defer/re-filter by chosen X (`xConstrainsTarget*`), run targeting before manual mana phase (`manaCostPerExtraTarget`), price but not re-derive (`costAfterSacrifice`). Deferral, not legality.
- `LegalAction.tapForGenericRequired` is engine-side only, consumed solely by built-in AI (`Strategist.withAutomaticTapForGeneric`).
