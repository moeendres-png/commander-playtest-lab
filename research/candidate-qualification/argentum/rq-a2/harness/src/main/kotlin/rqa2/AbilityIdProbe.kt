package rqa2

import com.wingedsheep.engine.core.ActivateAbility
import com.wingedsheep.engine.core.CastSpell
import com.wingedsheep.engine.core.GameAction
import com.wingedsheep.engine.core.PassPriority
import com.wingedsheep.engine.core.PlayLand
import com.wingedsheep.engine.core.SubmitDecision
import com.wingedsheep.engine.state.GameState
import com.wingedsheep.engine.state.ZoneKey
import com.wingedsheep.engine.state.components.identity.CardComponent
import com.wingedsheep.gameserver.protocol.ServerMessage
import com.wingedsheep.gameserver.replay.CompactReplay
import com.wingedsheep.gameserver.replay.ReplayCardPin
import com.wingedsheep.gameserver.replay.ReplayCheckpoint
import com.wingedsheep.gameserver.replay.ReplayCodec
import com.wingedsheep.gameserver.replay.ReplayFingerprint
import com.wingedsheep.gameserver.replay.ReplayPlayerInfo
import com.wingedsheep.gameserver.replay.ReplayPlayerSetup
import com.wingedsheep.gameserver.replay.ReplayReconstructor
import com.wingedsheep.gameserver.replay.ReplaySetup
import com.wingedsheep.sdk.core.AttackMode
import com.wingedsheep.sdk.core.Format
import com.wingedsheep.sdk.core.Zone
import com.wingedsheep.sdk.model.Deck
import com.wingedsheep.sdk.model.EntityId

// U22 — AbilityId / process-global identity effect probe.
//
// Modes:
//   record <spec> <replayFile> <digestFile>  — play spec, persist CompactReplay (pinned) + digests
//   replay <replayFile> <digestFile>          — re-fold a persisted replay via ReplayReconstructor
//   replayUnpinned <replayFile> <digestFile>  — re-fold with pinnedCards stripped
//
// Cross-process protocol (run in separate JVMs):
//   JVM-A: record S2 ; JVM-B: record S2  -> compare digest files (fresh-definition drift)
//   JVM-A: record S2 ; JVM-B: replay A's file (pinned + unpinned) -> persisted-replay compat

private val GEN_ABILITY = Regex("ability_\\d+")
private val UUID_RE = Regex("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

fun abilityStats(s: GameState): Map<String, Any?> {
    val str = s.toString()
    return mapOf(
        "genAbilityTokens" to GEN_ABILITY.findAll(str).count(),
        "uuidTokens" to UUID_RE.findAll(str).count(),
        "pendingId" to s.pendingDecision?.id,
        "pendingKind" to s.pendingDecision?.let { it::class.simpleName },
        "nextRoutingId" to s.nextRoutingId,
        "nextEntityId" to s.nextEntityId,
        "rng" to s.rng.state,
    )
}

fun findInHand(state: GameState, pid: EntityId, name: String): EntityId? =
    state.getZone(ZoneKey(pid, Zone.HAND)).find { eid ->
        state.getEntity(eid)?.get<CardComponent>()?.name == name
    }

fun trySubmit(
    processor: com.wingedsheep.engine.core.ActionProcessor,
    state: GameState,
    action: GameAction,
): GameState? {
    val r = processor.process(state, action).result
    if (r.error != null || (!r.isSuccess && !r.isPaused)) return null
    return r.newState
}

/** S2: play a land, cast Llanowar Elves, activate its mana ability once. */
fun playActivationGame(registry: com.wingedsheep.engine.registry.CardRegistry): PlayedGame {
    val decks = listOf(
        "Alice" to Deck.of("Forest" to 30, "Llanowar Elves" to 10),
        "Bob" to Deck.of("Forest" to 40),
    )
    val processor = newProcessor(registry)
    val enumerator = newEnumerator(registry)
    val init = initGame(registry, seatConfigs("S2-activation", decks), 4242L, Format.Standard, true)
    var state = init.state
    val actions = mutableListOf<GameAction>()
    val frames = mutableListOf(state)
    val steps = mutableListOf<String>()
    val actionEvents = mutableListOf<List<String>>()
    var coinFlips = 0
    var activated = false
    var stop = "script-end"
    repeat(60) {
        if (state.gameOver) { stop = "game-over"; return@repeat }
        val pending = state.pendingDecision
        if (pending != null) {
            val a = SubmitDecision(pending.playerId, respond(pending))
            val ns = trySubmit(processor, state, a) ?: run { stop = "submit-failed@$a"; return@repeat }
            steps.add("${state.phase}/${state.step}"); state = ns
            actions.add(a); frames.add(state)
            return@repeat
        }
        val pp = state.priorityPlayerId ?: run { stop = "no-priority"; return@repeat }
        val legal = enumerator.enumerate(state, pp).filter { it.affordable }
        var submitted = false
        // (1) the mana activation, exactly once
        if (!activated) {
            val act = legal.firstOrNull { it.action is ActivateAbility && it.isManaAbility }
            if (act != null) {
                val ns = trySubmit(processor, state, act.action)
                if (ns != null) {
                    steps.add("${state.phase}/${state.step}"); state = ns
                    actions.add(act.action); frames.add(state); actionEvents.add(emptyList())
                    activated = true; submitted = true
                }
            }
        }
        // (2) land drop
        if (!submitted) {
            val land = findInHand(state, pp, "Forest")
            if (land != null) {
                val ns = trySubmit(processor, state, PlayLand(pp, land))
                if (ns != null) {
                    steps.add("${state.phase}/${state.step}"); state = ns
                    actions.add(PlayLand(pp, land)); frames.add(state); actionEvents.add(emptyList())
                    submitted = true
                }
            }
        }
        // (3) cast Elves
        if (!submitted) {
            val elves = findInHand(state, pp, "Llanowar Elves")
            if (elves != null) {
                val a = CastSpell(pp, elves)
                val ns = trySubmit(processor, state, a)
                if (ns != null) {
                    steps.add("${state.phase}/${state.step}"); state = ns
                    actions.add(a); frames.add(state); actionEvents.add(emptyList())
                    submitted = true
                }
            }
        }
        if (!submitted) {
            val a = PassPriority(pp)
            val ns = trySubmit(processor, state, a) ?: run { stop = "pass-failed"; return@repeat }
            steps.add("${state.phase}/${state.step}"); state = ns
            actions.add(a); frames.add(state); actionEvents.add(emptyList())
        }
        if (activated && actions.size > 12) { stop = "activation-done"; return@repeat }
    }
    return PlayedGame("S2-activation", 4242L, decks, Format.Standard, actions, frames, steps, actionEvents, coinFlips, "$stop activated=$activated")
}

/** S3: cast cheap spells, then Tendrils of Agony with storm count >= 2. */
fun playStormGame(registry: com.wingedsheep.engine.registry.CardRegistry): PlayedGame {
    val decks = listOf(
        "Alice" to Deck.of("Swamp" to 24, "Careful Study" to 10, "Tendrils of Agony" to 6),
        "Bob" to Deck.of("Swamp" to 34, "Careful Study" to 6),
    )
    val processor = newProcessor(registry)
    val enumerator = newEnumerator(registry)
    val init = initGame(registry, seatConfigs("S3-storm", decks), 777L, Format.Standard, true)
    var state = init.state
    val actions = mutableListOf<GameAction>()
    val frames = mutableListOf(state)
    val steps = mutableListOf<String>()
    val actionEvents = mutableListOf<List<String>>()
    var coinFlips = 0
    var stop = "script-end"
    var stormCast = false
    var castsThisTurn = 0
    var lastTurn = 1
    val skipped = mutableListOf<String>()
    repeat(400) {
        if (state.gameOver) { stop = "game-over"; return@repeat }
        if (state.turnNumber > 10) { stop = "turn-cap"; return@repeat }
        if (state.turnNumber != lastTurn) { lastTurn = state.turnNumber; castsThisTurn = 0 }
        val pending = state.pendingDecision
        if (pending != null) {
            val a = SubmitDecision(pending.playerId, respond(pending))
            val r = processor.process(state, a).result
            if (r.error != null || (!r.isSuccess && !r.isPaused)) { stop = "submit-failed@$a:${r.error}"; return@repeat }
            steps.add("${state.phase}/${state.step}"); state = r.newState
            actions.add(a); frames.add(state)
            actionEvents.add(r.events.map { normalizedEvent(it as Any) })
            return@repeat
        }
        val pp = state.priorityPlayerId ?: run { stop = "no-priority"; return@repeat }
        var action: GameAction? = null
        // Prefer: Tendrils once storm count >= 2 and able.
        val tendrils = findInHand(state, pp, "Tendrils of Agony")
        if (!stormCast && tendrils != null && castsThisTurn >= 2) {
            val legal = enumerator.enumerate(state, pp).filter { it.affordable }
            val offer = legal.firstOrNull {
                it.action is CastSpell && (it.action as CastSpell).cardId == tendrils
            }
            if (offer != null) {
                val base = offer.action as CastSpell
                action = if (base.targets.isEmpty() && offer.requiresTargets) {
                    val valid = offer.validTargets ?: emptyList()
                    if (valid.size >= offer.minTargets) base.copy(
                        targets = valid.take(offer.minTargets).map { toChosenTarget(state, it) }
                    ) else null
                } else base
            }
        }
        if (action == null) {
            action = chooseAction(state, pp, enumerator, skipped) ?: PassPriority(pp)
        }
        val r = processor.process(state, action).result
        if (r.error != null || (!r.isSuccess && !r.isPaused)) {
            // Fall back to a pass; if the pass fails too, stop.
            val p = PassPriority(pp)
            val rp = processor.process(state, p).result
            if (rp.error != null || (!rp.isSuccess && !rp.isPaused)) { stop = "submit-failed@$action:${r.error}"; return@repeat }
            steps.add("${state.phase}/${state.step}"); state = rp.newState
            actions.add(p); frames.add(state)
            actionEvents.add(rp.events.map { normalizedEvent(it as Any) })
            return@repeat
        }
        if (action is CastSpell) castsThisTurn++
        if (action is CastSpell && findName(state, action.cardId) == "Tendrils of Agony") stormCast = true
        steps.add("${state.phase}/${state.step}"); state = r.newState
        actions.add(action); frames.add(state)
        actionEvents.add(r.events.map { normalizedEvent(it as Any) })
        coinFlips += r.events.count { it is com.wingedsheep.engine.core.CoinFlipEvent }
    }
    return PlayedGame("S3-storm", 777L, decks, Format.Standard, actions, frames, steps, actionEvents, coinFlips, "$stop stormCast=$stormCast")
}

fun findName(state: GameState, id: EntityId): String? =
    state.getEntity(id)?.get<CardComponent>()?.name

/** S4: cast Prodigal Sorcerer and activate its ping ability (definition-level ability id). */
fun playPingGame(registry: com.wingedsheep.engine.registry.CardRegistry): PlayedGame {
    val decks = listOf(
        "Alice" to Deck.of("Island" to 28, "Prodigal Sorcerer" to 12),
        "Bob" to Deck.of("Island" to 28, "Prodigal Sorcerer" to 12),
    )
    val processor = newProcessor(registry)
    val enumerator = newEnumerator(registry)
    val init = initGame(registry, seatConfigs("S4-ping", decks), 555L, Format.Standard, true)
    var state = init.state
    val actions = mutableListOf<GameAction>()
    val frames = mutableListOf(state)
    val steps = mutableListOf<String>()
    val actionEvents = mutableListOf<List<String>>()
    var coinFlips = 0
    var stop = "script-end"
    var pingAt = -1
    val skipped = mutableListOf<String>()
    repeat(500) {
        if (state.gameOver) { stop = "game-over"; return@repeat }
        if (state.turnNumber > 14) { stop = "turn-cap"; return@repeat }
        if (pingAt >= 0 && actions.size - pingAt > 8) { stop = "ping-done"; return@repeat }
        val pending = state.pendingDecision
        if (pending != null) {
            val a = SubmitDecision(pending.playerId, respond(pending))
            val r = processor.process(state, a).result
            if (r.error != null || (!r.isSuccess && !r.isPaused)) { stop = "submit-failed@$a:${r.error}"; return@repeat }
            steps.add("${state.phase}/${state.step}"); state = r.newState
            actions.add(a); frames.add(state)
            actionEvents.add(r.events.map { normalizedEvent(it as Any) })
            return@repeat
        }
        val pp = state.priorityPlayerId ?: run { stop = "no-priority"; return@repeat }
        val action = chooseAction(state, pp, enumerator, skipped) ?: PassPriority(pp)
        val r = processor.process(state, action).result
        if (r.error != null || (!r.isSuccess && !r.isPaused)) { stop = "submit-failed@$action:${r.error}"; return@repeat }
        if (action is ActivateAbility && findName(state, action.sourceId) == "Prodigal Sorcerer") pingAt = actions.size
        steps.add("${state.phase}/${state.step}"); state = r.newState
        actions.add(action); frames.add(state)
        actionEvents.add(r.events.map { normalizedEvent(it as Any) })
        coinFlips += r.events.count { it is com.wingedsheep.engine.core.CoinFlipEvent }
    }
    return PlayedGame("S4-ping", 555L, decks, Format.Standard, actions, frames, steps, actionEvents, coinFlips, "$stop pingAt=$pingAt")
}

fun playSpec(registry: com.wingedsheep.engine.registry.CardRegistry, spec: String): PlayedGame =
    when (spec) {
        "S1-study" -> playGame(
            "S1-study", registry,
            listOf(
                "Alice" to Deck.of("Swamp" to 28, "Careful Study" to 12),
                "Bob" to Deck.of("Swamp" to 28, "Careful Study" to 12),
            ), 2002L, Format.Standard, 10, 600, true, true,
        )
        "S2-activation" -> playActivationGame(registry)
        "S3-storm" -> playStormGame(registry)
        "S4-ping" -> playPingGame(registry)
        else -> throw IllegalArgumentException("unknown spec $spec")
    }

fun toReplay(game: PlayedGame, registry: com.wingedsheep.engine.registry.CardRegistry, pin: Boolean): CompactReplay {
    val init = initGame(registry, seatConfigs(game.name, game.playerDecks), game.seed, game.format, true)
    val nameById = game.playerDecks.mapIndexed { i, (n, _) -> init.playerIds[i].value to n }.toMap()
    val turnOrder = game.frames.last().turnOrder.ifEmpty { init.playerIds }
    val setup = ReplaySetup(
        seed = init.seed,
        format = game.format,
        attackMode = AttackMode.MULTIPLE,
        startingHandSize = 7,
        skipMulligans = true,
        useHandSmoother = false,
        handSmootherCandidates = 3,
        startingPlayerIndex = null,
        teams = null,
        players = game.playerDecks.mapIndexed { i, (n, d) ->
            ReplayPlayerSetup(init.playerIds[i].value, n, d, 20, null)
        },
        seatRoster = turnOrder.mapIndexed { i, pid ->
            ServerMessage.PlayerSeatInfo(pid.value, nameById[pid.value] ?: pid.value, i)
        },
    )
    return CompactReplay(
        gameId = "rq-a2-u22-${game.name}",
        players = turnOrder.map { pid -> ReplayPlayerInfo(pid.value, nameById[pid.value] ?: pid.value) },
        startedAt = "2026-09-10T00:00:00Z",
        endedAt = "2026-09-10T00:00:00Z",
        winnerName = null,
        setup = setup,
        actions = game.actions,
        yields = emptyList(),
        engineVersion = CANDIDATE_HEAD,
        pinnedCards = if (pin) ReplayCardPin.capture(registry, setup) else emptyList(),
        checkpoints = game.frames.mapIndexedNotNull { f, st ->
            if (f > 0 && f % 20 == 0) ReplayCheckpoint(f, ReplayFingerprint.of(st)) else null
        },
    )
}

fun frameJson(i: Int, s: GameState, dumpWhenGeneratedIds: Boolean = true): JO {
    val stats = abilityStats(s)
    val j = jo(
        "frame" to i,
        "canonical" to canonicalDigest(s),
        "fingerprint" to ReplayFingerprint.of(s),
        "rawHash" to sha256Hex(s.toString()),
        "stats" to stats,
    )
    if (dumpWhenGeneratedIds && (stats["genAbilityTokens"] as Int) > 0) {
        j["stateDump"] = s.toString()
    }
    return j
}

fun digestsJson(game: PlayedGame): Map<String, Any?> = mapOf(
    "game" to game.name,
    "seed" to game.seed,
    "actions" to game.actions.size,
    "stopReason" to game.stopReason,
    "frames" to game.frames.mapIndexed { i, s -> frameJson(i, s) },
)

fun main(args: Array<String>) {
    val mode = args.getOrNull(0) ?: throw IllegalArgumentException("mode required")
    val registry = newRegistry()
    when (mode) {
        "record" -> {
            val spec = args[1]; val replayFile = args[2]; val digestFile = args[3]
            val game = playSpec(registry, spec)
            val replay = toReplay(game, registry, pin = true)
            java.io.File(replayFile).apply { parentFile?.mkdirs() }.writeText(ReplayCodec.encode(replay))
            val root = jo(
                "mode" to "record",
                "spec" to spec,
                "candidate" to jo("head" to CANDIDATE_HEAD, "tree" to CANDIDATE_TREE),
                "pinnedCards" to replay.pinnedCards.size,
                "actionKinds" to game.actions.mapNotNull { it::class.simpleName }.distinct().sorted(),
                "activationActions" to game.actions.filterIsInstance<ActivateAbility>().map { actionSummary(it) },
                "game" to digestsJson(game),
            )
            writeJson(digestFile, root)
            println("recorded $spec: ${game.actions.size} actions stop=${game.stopReason} pinned=${replay.pinnedCards.size}")
        }
        "replay", "replayUnpinned" -> {
            val replayFile = args[1]; val digestFile = args[2]
            var replay = ReplayCodec.decode(java.io.File(replayFile).readText())
            if (mode == "replayUnpinned") replay = replay.copy(pinnedCards = emptyList(), checkpoints = emptyList())
            val recon = ReplayReconstructor(registry, null)
            val frames = (0..replay.actions.size).map { recon.reconstructStateAt(replay, it) }
            val full = runCatching { recon.reconstruct(replay) }.getOrNull()
            val root = jo(
                "mode" to mode,
                "candidate" to jo("head" to CANDIDATE_HEAD, "tree" to CANDIDATE_TREE),
                "frames" to frames.mapIndexed { i, s ->
                    if (s == null) jo("frame" to i, "null" to true)
                    else frameJson(i, s)
                },
                "stream" to jo(
                    "frameCount" to full?.frameCount,
                    "expected" to (1 + replay.actions.size),
                    "fidelity" to full?.fidelity?.name,
                    "divergedAt" to full?.divergedAtFrame,
                    "reason" to full?.divergenceReason,
                ),
            )
            writeJson(digestFile, root)
            println("$mode: frames=${frames.size} nulls=${frames.count { it == null }} fidelity=${full?.fidelity}")
        }
        "diffself" -> {
            // Same-JVM record + re-fold: print differing identity tokens per frame.
            val spec = args[1]; val digestFile = args[2]
            val game = playSpec(registry, spec)
            val replay = toReplay(game, registry, pin = true)
            val recon = ReplayReconstructor(registry, null)
            val rows = mutableListOf<Any?>()
            for (i in 0..game.actions.size) {
                val rs = recon.reconstructStateAt(replay, i)
                if (rs == null) {
                    rows.add(jo("frame" to i, "null" to true)); continue
                }
                val live = game.frames[i]
                val rawEq = rs == live
                val canonEq = canonicalDigest(rs) == canonicalDigest(live)
                val toks = if (!rawEq) diffTokens(live.toString(), rs.toString()) else emptyList()
                // Localize: which top-level dimension carries the differing token?
                rows.add(jo("frame" to i, "rawEqual" to rawEq, "canonicalEqual" to canonEq,
                    "differingTokens" to toks))
            }
            // Counter probe: how many generate() calls does a fresh definition load consume?
            writeJson(digestFile, jo("mode" to "diffself", "spec" to spec, "frames" to rows))
            for (r in rows) {
                val m = (r as JO).map
                if (m["rawEqual"] == false) println("frame ${m["frame"]}: canonEq=${m["canonicalEqual"]} toks=${m["differingTokens"]}")
            }
            println("diffself $spec done")
        }
        else -> throw IllegalArgumentException("unknown mode $mode")
    }
}

fun diffTokens(a: String, b: String): List<String> {
    val ta = GEN_ABILITY.findAll(a).map { it.value }.toSet()
    val tb = GEN_ABILITY.findAll(b).map { it.value }.toSet()
    val ua = UUID_RE.findAll(a).map { it.value }.toSet()
    val ub = UUID_RE.findAll(b).map { it.value }.toSet()
    return ((ta - tb).map { "only-live:$it" } + (tb - ta).map { "only-replay:$it" } +
        (ua - ub).map { "only-live-uuid:$it" } + (ub - ua).map { "only-replay-uuid:$it" })
        .sorted()
}
