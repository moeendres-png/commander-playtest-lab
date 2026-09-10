package rqa2

import com.wingedsheep.engine.core.ActionProcessor
import com.wingedsheep.engine.core.AssignDamageDecision
import com.wingedsheep.engine.core.BatchYesNoDecision
import com.wingedsheep.engine.core.BatchYesNoResponse
import com.wingedsheep.engine.core.BudgetModalDecision
import com.wingedsheep.engine.core.BudgetModalResponse
import com.wingedsheep.engine.core.CardsSelectedResponse
import com.wingedsheep.engine.core.CastSpell
import com.wingedsheep.engine.core.ChooseColorDecision
import com.wingedsheep.engine.core.CoinFlipEvent
import com.wingedsheep.engine.core.ChooseModeDecision
import com.wingedsheep.engine.core.ChooseNumberDecision
import com.wingedsheep.engine.core.ChooseOptionDecision
import com.wingedsheep.engine.core.ChooseReplacementDecision
import com.wingedsheep.engine.core.ChooseTargetsDecision
import com.wingedsheep.engine.core.ColorChosenResponse
import com.wingedsheep.engine.core.CombatResolutionDecision
import com.wingedsheep.engine.core.CombatResolutionResponse
import com.wingedsheep.engine.core.DamageAssignmentResponse
import com.wingedsheep.engine.core.DamageEdgeAmount
import com.wingedsheep.engine.core.DecisionResponse
import com.wingedsheep.engine.core.DeclareAttackers
import com.wingedsheep.engine.core.DeclareBlockers
import com.wingedsheep.engine.core.DistributeDecision
import com.wingedsheep.engine.core.DistributionResponse
import com.wingedsheep.engine.core.GameAction
import com.wingedsheep.engine.core.GameConfig
import com.wingedsheep.engine.core.GameInitializer
import com.wingedsheep.engine.core.ManaSourcesSelectedResponse
import com.wingedsheep.engine.core.ModesChosenResponse
import com.wingedsheep.engine.core.NumberChosenResponse
import com.wingedsheep.engine.core.OptionChosenResponse
import com.wingedsheep.engine.core.OrderObjectsDecision
import com.wingedsheep.engine.core.OrderedResponse
import com.wingedsheep.engine.core.PassPriority
import com.wingedsheep.engine.core.PendingDecision
import com.wingedsheep.engine.core.PilesSplitResponse
import com.wingedsheep.engine.core.PlayerConfig
import com.wingedsheep.engine.core.ReorderLibraryDecision
import com.wingedsheep.engine.core.ReplacementChosenResponse
import com.wingedsheep.engine.core.SearchLibraryDecision
import com.wingedsheep.engine.core.SelectCardsDecision
import com.wingedsheep.engine.core.SelectManaSourcesDecision
import com.wingedsheep.engine.core.SplitPilesDecision
import com.wingedsheep.engine.core.SubmitDecision
import com.wingedsheep.engine.core.TargetsResponse
import com.wingedsheep.engine.core.YesNoDecision
import com.wingedsheep.engine.core.YesNoResponse
import com.wingedsheep.engine.legalactions.LegalAction
import com.wingedsheep.engine.legalactions.LegalActionEnumerator
import com.wingedsheep.engine.registry.CardRegistry
import com.wingedsheep.engine.state.GameState
import com.wingedsheep.engine.state.ZoneKey
import com.wingedsheep.engine.state.components.combat.AttackersDeclaredThisCombatComponent
import com.wingedsheep.engine.state.components.combat.AttackingComponent
import com.wingedsheep.engine.state.components.combat.BlockersDeclaredThisCombatComponent
import com.wingedsheep.engine.state.components.identity.PlayerComponent
import com.wingedsheep.engine.state.components.stack.ChosenTarget
import com.wingedsheep.engine.support.TestCards
import com.wingedsheep.sdk.core.Format
import com.wingedsheep.sdk.core.Step
import com.wingedsheep.sdk.model.Deck
import com.wingedsheep.sdk.model.EntityId
import java.security.MessageDigest

const val CANDIDATE_HEAD = "3f46367d87c88bcf156a843a9e69fd29e1693872"
const val CANDIDATE_TREE = "2adf51caa8f9c6a9908ea961fa988ebb5eb1959f"

fun newRegistry(): CardRegistry = CardRegistry().apply { register(TestCards.all) }

fun registryDiagnostics(registry: CardRegistry): Map<String, Any?> {
    val allSets = try {
        com.wingedsheep.mtg.sets.MtgSetCatalog.all
    } catch (t: Throwable) {
        return mapOf("catalogError" to "${t::class.simpleName}: ${t.message}")
    }
    return mapOf(
        "catalogSetCount" to allSets.size,
        "catalogSetCodes" to allSets.take(12).map { it.code },
        "catalogCardCount" to allSets.sumOf { it.cards.size },
        "catalogBasicLandCount" to allSets.sumOf { it.basicLands.size },
        "hasForest" to registry.hasCard("Forest"),
        "hasMountain" to registry.hasCard("Mountain"),
        "hasLightningBolt" to registry.hasCard("Lightning Bolt"),
        "hasGrizzlyBears" to registry.hasCard("Grizzly Bears"),
        "hasGoblinGuide" to registry.hasCard("Goblin Guide"),
        "hasGoblinPsychopath" to registry.hasCard("Goblin Psychopath"),
    )
}

fun newProcessor(registry: CardRegistry): ActionProcessor = ActionProcessor(registry)

fun newEnumerator(registry: CardRegistry): LegalActionEnumerator =
    LegalActionEnumerator.create(registry)

fun initGame(
    registry: CardRegistry,
    players: List<PlayerConfig>,
    seed: Long,
    format: Format = Format.Standard,
    skipMulligans: Boolean = true,
    startingPlayerIndex: Int? = null,
): com.wingedsheep.engine.core.InitializationResult =
    GameInitializer(registry).initializeGame(
        GameConfig(
            players = players,
            skipMulligans = skipMulligans,
            startingPlayerIndex = startingPlayerIndex,
            format = format,
            seed = seed,
        )
    )

/**
 * Explicit, non-colliding seat ids for replay-safe initialization.
 *
 * RQ-A2 finding (driver-verified): GameInitializer only advances the entity
 * counter for minted (null-id) players. Replaying a game whose recorded seat
 * ids live in the engine-minted `e<N>` namespace with those ids passed back as
 * explicit PlayerConfig.playerId makes the library instantiation overwrite the
 * player entities (same counter start, same ids). Production (GameSession)
 * always uses non-colliding string seat ids ("player-1", ...), so the driver
 * mirrors that topology: explicit ids outside `e<N>`.
 */
fun seatConfigs(
    gameName: String,
    decks: List<Pair<String, Deck>>,
    startingLife: Int = 20,
): List<PlayerConfig> = decks.mapIndexed { i, (n, d) ->
    PlayerConfig(n, d, startingLife, playerId = EntityId.of("rq-a2-$gameName-p$i"))
}

// ---------------------------------------------------------------------------
// Canonical digests
// ---------------------------------------------------------------------------

private val ABILITY_GEN = Regex("ability_\\d+")
private val UUID_RE = Regex("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

fun normalizeIds(s: String): String =
    UUID_RE.replace(ABILITY_GEN.replace(s, "ability_#"), "#uuid#")

fun sha256Hex(s: String): String {
    val bytes = MessageDigest.getInstance("SHA-256").digest(s.toByteArray(Charsets.UTF_8))
    return bytes.joinToString("") { "%02x".format(it) }
}

/**
 * Sharp semantic digest of a full GameState: the data-class rendering with
 * process-global nondeterminism normalized (generated ability ids, UUIDs).
 * Routing ids (r<N>), entity ids (e<N>), RNG state and every component are
 * compared exactly — any semantic divergence changes this digest.
 */
fun canonicalDigest(state: GameState): String = sha256Hex(normalizeIds(state.toString()))

fun normalizedEvent(e: Any): String = normalizeIds(e.toString())

// ---------------------------------------------------------------------------
// Deterministic decision responder (first-valid-choice policy).
// Every response is a recorded replay input; the policy itself needs no RNG.
// ---------------------------------------------------------------------------

fun respond(decision: PendingDecision): DecisionResponse = when (decision) {
    is ChooseTargetsDecision -> {
        val targets = decision.targetRequirements.associate { req ->
            val valid = decision.legalTargets[req.index] ?: emptyList()
            req.index to valid.take(req.minTargets)
        }
        TargetsResponse(decision.id, targets)
    }
    is SelectCardsDecision ->
        CardsSelectedResponse(decision.id, decision.options.take(decision.minSelections))
    is SearchLibraryDecision ->
        CardsSelectedResponse(decision.id, decision.options.take(decision.minSelections))
    is YesNoDecision -> YesNoResponse(decision.id, false)
    is BatchYesNoDecision -> BatchYesNoResponse(decision.id, choice = false, applyToAll = true)
    is ChooseModeDecision -> {
        val available = decision.modes.filter { it.available }
        ModesChosenResponse(decision.id, available.take(decision.minModes).map { it.index })
    }
    is BudgetModalDecision -> BudgetModalResponse(decision.id, emptyList())
    is ChooseColorDecision ->
        ColorChosenResponse(decision.id, decision.availableColors.first())
    is ChooseNumberDecision -> NumberChosenResponse(decision.id, decision.minValue)
    is DistributeDecision -> {
        val dist = mutableMapOf<EntityId, Int>()
        var remaining = decision.totalAmount
        for (target in decision.targets) {
            dist[target] = decision.minPerTarget
            remaining -= decision.minPerTarget
        }
        while (remaining > 0 && decision.targets.isNotEmpty()) {
            val target = decision.targets.first()
            dist[target] = (dist[target] ?: 0) + 1
            remaining--
        }
        DistributionResponse(decision.id, dist)
    }
    is OrderObjectsDecision -> OrderedResponse(decision.id, decision.objects)
    is ReorderLibraryDecision -> OrderedResponse(decision.id, decision.cards)
    is SplitPilesDecision -> {
        val n = maxOf(1, decision.numberOfPiles)
        val piles = List(n) { mutableListOf<EntityId>() }
        decision.cards.forEachIndexed { i, c -> piles[i % n].add(c) }
        PilesSplitResponse(decision.id, piles)
    }
    is ChooseOptionDecision -> OptionChosenResponse(decision.id, 0)
    is ChooseReplacementDecision -> {
        val allowed = decision.allowedToByFrom.getOrNull(0)
        val to = if (!allowed.isNullOrEmpty()) allowed.first() else 0
        ReplacementChosenResponse(decision.id, 0, to)
    }
    is AssignDamageDecision ->
        DamageAssignmentResponse(decision.id, decision.defaultAssignments)
    is CombatResolutionDecision ->
        CombatResolutionResponse(decision.id, decision.edges.map { DamageEdgeAmount(it.id, it.amount) })
    is SelectManaSourcesDecision ->
        ManaSourcesSelectedResponse(decision.id, emptyList(), autoPay = true)
    else -> throw IllegalArgumentException(
        "RQ-A2 responder has no policy for ${decision::class.simpleName}"
    )
}

// ---------------------------------------------------------------------------
// Action selection: authoritative candidates only, deterministic first-pick.
// ---------------------------------------------------------------------------

fun toChosenTarget(state: GameState, id: EntityId): ChosenTarget =
    if (state.getEntity(id)?.get<PlayerComponent>() != null) ChosenTarget.Player(id)
    else ChosenTarget.Permanent(id)

/**
 * Returns the action to submit for [pp], or null when nothing but a pass applies.
 * Combat declarations are assembled from the engine-advertised candidate lists
 * (the documented ADAPTER_REQUIRED seam); everything else echoes enumerated
 * templates, completing targets only from advertised valid-target sets.
 */
fun chooseAction(
    state: GameState,
    pp: EntityId,
    enumerator: LegalActionEnumerator,
    skipped: MutableList<String>,
): GameAction? {
    if (state.step == Step.DECLARE_ATTACKERS && pp == state.activePlayerId &&
        state.getEntity(pp)?.has<AttackersDeclaredThisCombatComponent>() != true
    ) {
        val template = enumerator.enumerate(state, pp)
            .firstOrNull { it.action is DeclareAttackers }
        val attackers = template?.validAttackers ?: emptyList()
        val targets = template?.validAttackTargets ?: emptyList()
        val map = if (attackers.isNotEmpty() && targets.isNotEmpty()) {
            attackers.associateWith { targets.first() }
        } else emptyMap()
        return DeclareAttackers(pp, map)
    }
    if (state.step == Step.DECLARE_BLOCKERS && pp != state.activePlayerId &&
        state.getEntity(pp)?.has<BlockersDeclaredThisCombatComponent>() != true
    ) {
        // Assemble from authoritative candidates: block the first attacker coming
        // at this seat with every valid blocker (over-blocking is legal).
        val template = enumerator.enumerate(state, pp)
            .firstOrNull { it.action is DeclareBlockers }
        val blockers = template?.validBlockers ?: emptyList()
        val incoming = state.getBattlefield().firstOrNull { id ->
            state.getEntity(id)?.get<AttackingComponent>()?.defenderId == pp
        }
        val map = if (incoming != null && blockers.isNotEmpty()) {
            blockers.associateWith { listOf(incoming) }
        } else emptyMap()
        return DeclareBlockers(pp, map)
    }
    val legal = enumerator.enumerate(state, pp).filter { it.affordable }
    for (la in legal) {
        val a = la.action
        if (a is PassPriority) continue
        if (la.isManaAbility) continue
        if (a is DeclareAttackers || a is DeclareBlockers) continue
        if (a is CastSpell && a.targets.isEmpty() && la.requiresTargets) {
            val valid = la.validTargets ?: emptyList()
            if (valid.size < la.minTargets) {
                skipped.add("${a::class.simpleName}@${pp.value}: only ${valid.size} valid targets")
                continue
            }
            val filled = valid.take(la.minTargets).map { toChosenTarget(state, it) }
            return a.copy(targets = filled)
        }
        return a
    }
    return null
}

data class PlayedGame(
    val name: String,
    val seed: Long,
    val playerDecks: List<Pair<String, Deck>>,
    val format: Format,
    val actions: List<GameAction>,
    val frames: List<GameState>, // frame 0 = initial, frame i = after actions[i-1]
    val steps: List<String>, // phase/step BEFORE each applied action (same length as actions)
    val actionEvents: List<List<String>>, // normalized event strings per applied action
    val coinFlipCount: Int, // CoinFlipEvent occurrences across the whole game
    val stopReason: String,
)

/** Play a game with the deterministic policy above; every submitted action is a replay input. */
fun playGame(
    name: String,
    registry: CardRegistry,
    playerDecks: List<Pair<String, Deck>>,
    seed: Long,
    format: Format = Format.Standard,
    maxTurns: Int = 12,
    maxActions: Int = 600,
    skipMulligans: Boolean = true,
    active: Boolean = true,
): PlayedGame {
    val processor = newProcessor(registry)
    val enumerator = newEnumerator(registry)
    // Explicit non-colliding seat ids (see seatConfigs): the recorded setup must
    // rebuild bit-identical players through ReplayReconstructor.
    val init = initGame(registry, seatConfigs(name, playerDecks), seed, format, skipMulligans)
    var state = init.state
    val actions = mutableListOf<GameAction>()
    val frames = mutableListOf(state)
    val steps = mutableListOf<String>()
    val actionEvents = mutableListOf<List<String>>()
    var coinFlips = 0
    val skipped = mutableListOf<String>()
    var stopReason = "action-cap"
    var i = 0
    while (i < maxActions) {
        if (state.gameOver) { stopReason = "game-over"; break }
        if (state.turnNumber > maxTurns) { stopReason = "turn-cap"; break }
        val pending = state.pendingDecision
        val action: GameAction = if (pending != null) {
            SubmitDecision(pending.playerId, respond(pending))
        } else {
            val pp = state.priorityPlayerId ?: run {
                stopReason = "no-priority-no-decision@${state.phase}/${state.step}"
                break
            }
            if (active) chooseAction(state, pp, enumerator, skipped) ?: PassPriority(pp)
            else {
                // Pass-only mode: still file empty combat declarations so priority can proceed.
                val decl: GameAction? = when {
                    state.step == Step.DECLARE_ATTACKERS && pp == state.activePlayerId &&
                        state.getEntity(pp)?.has<AttackersDeclaredThisCombatComponent>() != true ->
                        DeclareAttackers(pp, emptyMap())
                    state.step == Step.DECLARE_BLOCKERS && pp != state.activePlayerId &&
                        state.getEntity(pp)?.has<BlockersDeclaredThisCombatComponent>() != true ->
                        DeclareBlockers(pp, emptyMap())
                    else -> null
                }
                decl ?: PassPriority(pp)
            }
        }
        val result = processor.process(state, action).result
        if (result.error != null || (!result.isSuccess && !result.isPaused)) {
            stopReason = "submit-failed@${action::class.simpleName}:${result.error}"
            break
        }
        steps.add("${state.phase}/${state.step}")
        state = result.newState
        actions.add(action)
        frames.add(state)
        actionEvents.add(result.events.map { normalizedEvent(it as Any) })
        coinFlips += result.events.count { it is CoinFlipEvent }
        i++
    }
    if (i >= maxActions) stopReason = "action-cap"
    return PlayedGame(name, seed, playerDecks, format, actions, frames, steps, actionEvents, coinFlips, stopReason)
}

fun actionSummary(a: GameAction): String = when (a) {
    is SubmitDecision -> "SubmitDecision(${a.response::class.simpleName})@${shortPid(a.playerId)}"
    else -> "${a::class.simpleName}@${shortPid(a.playerId)}"
}

fun shortPid(id: EntityId): String = id.value

fun lifeTotals(state: GameState): Map<String, Int> =
    state.turnOrder.associate { it.value to state.lifeTotal(it) }
