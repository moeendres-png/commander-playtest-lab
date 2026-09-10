package rqa2

import com.wingedsheep.engine.core.Concede
import com.wingedsheep.engine.core.GameAction
import com.wingedsheep.engine.core.PassPriority
import com.wingedsheep.engine.core.SubmitDecision
import com.wingedsheep.engine.state.ZoneKey
import com.wingedsheep.engine.state.components.identity.CommanderComponent
import com.wingedsheep.engine.state.components.identity.CommanderRegistryComponent
import com.wingedsheep.engine.state.components.identity.LifeTotalComponent
import com.wingedsheep.engine.state.components.player.PlayerLeftGameComponent
import com.wingedsheep.sdk.core.Format
import com.wingedsheep.sdk.core.Zone
import com.wingedsheep.sdk.model.Deck
import com.wingedsheep.sdk.model.EntityId

// U10 — 5-player technical feasibility probe (CPL-side external driver).
// F1: generic 5P FFA init + turn rotation + priority progression.
// F2: 5-player Commander pod (command zone, 40 life, registry).
// F3: elimination ladder 5 -> 1 via Concede (leave-game transition, winner).
// F4: 6-player smoke (optional per contract).

fun fiveDecks(n: Int): List<Pair<String, Deck>> =
    (0 until n).map { "P$it" to Deck.of("Forest" to 20, "Grizzly Bears" to 20) }

fun main(args: Array<String>) {
    val outPath = args.getOrNull(0)
        ?: "/home/moeen/code/rq-a2-argentum-comparable-qualification/research/candidate-qualification/argentum/rq-a2/evidence/ARGENTUM_FIVE_PLAYER_PROBE.json"
    val registry = newRegistry()
    val processor = newProcessor(registry)
    val enumerator = newEnumerator(registry)
    val findings = mutableListOf<Any?>()

    // --- F1: 5P FFA ---
    run {
        val decks = fiveDecks(5)
        val init = initGame(registry, seatConfigs("F1-ffa5", decks), 9001L, Format.Standard, true)
        var s = init.state
        val checks = mutableListOf<String>()
        checks.add("playerCount=${init.playerIds.size}")
        checks.add("turnOrderSize=${s.turnOrder.size}")
        checks.add("allActiveDistinct=${s.turnOrder.distinct().size == 5}")
        checks.add("life=${s.turnOrder.map { s.lifeTotal(it) }}")
        checks.add("hands=${s.turnOrder.map { s.getZone(ZoneKey(it, Zone.HAND)).size }}")
        val seenActive = linkedSetOf<String>()
        val seenPriority = linkedSetOf<String>()
        val skipped = mutableListOf<String>()
        var err: String? = null
        repeat(250) {
            if (s.gameOver) return@repeat
            s.activePlayerId?.let { seenActive.add(it.value) }
            s.priorityPlayerId?.let { seenPriority.add(it.value) }
            val pending = s.pendingDecision
            val a: GameAction = if (pending != null) SubmitDecision(pending.playerId, respond(pending))
            else {
                val pp = s.priorityPlayerId ?: return@repeat
                chooseAction(s, pp, enumerator, skipped) ?: PassPriority(pp)
            }
            val r = processor.process(s, a).result
            if (r.error != null || (!r.isSuccess && !r.isPaused)) { err = "${actionSummary(a)}: ${r.error}"; return@repeat }
            s = r.newState
        }
        checks.add("seenActive=${seenActive.sorted()}")
        checks.add("seenPriorityHolders=${seenPriority.sorted()}")
        checks.add("allFiveActed=${seenActive.size == 5}")
        checks.add("submitError=$err")
        checks.add("turnNumber=${s.turnNumber}")
        findings.add(jo("test" to "F1-ffa5", "checks" to checks,
            "pass" to (err == null && seenActive.size == 5)))
    }

    // --- F2: 5P Commander pod ---
    run {
        val decks = (0 until 5).map { "C$it" to Deck.of("Forest" to 99) }
        val commanders = List(5) { "Test Hasty Prospector" }
        val r = com.wingedsheep.engine.core.GameInitializer(registry).initializeGame(
            com.wingedsheep.engine.core.GameConfig(
                players = decks.mapIndexed { i, (n, d) ->
                    com.wingedsheep.engine.core.PlayerConfig(n, d, 40,
                        playerId = EntityId.of("rq-a2-f2-p$i"), commanderCardName = commanders[i])
                },
                skipMulligans = true, format = Format.Commander(), seed = 9002L,
            )
        )
        val s = r.state
        val checks = mutableListOf<String>()
        checks.add("playerCount=${r.playerIds.size}")
        checks.add("life=${r.playerIds.map { s.lifeTotal(it) }}")
        val cmdZones = r.playerIds.map { pid ->
            val ids = s.getZone(ZoneKey(pid, Zone.COMMAND))
            val comp = ids.firstOrNull()?.let { s.getEntity(it)?.get<CommanderComponent>() }
            "${pid.value}:zone=${ids.size}:commander=${comp != null}:ownerOk=${comp?.ownerId == pid}"
        }
        checks.addAll(cmdZones)
        val regs = r.playerIds.map { pid ->
            s.getEntity(pid)?.get<CommanderRegistryComponent>()?.commanderIds?.size
        }
        checks.add("registries=$regs")
        checks.add("librarySizes=${r.playerIds.map { s.getZone(ZoneKey(it, Zone.LIBRARY)).size }}")
        // play a few turns
        var s2 = s
        val skipped = mutableListOf<String>()
        var err: String? = null
        val seen = linkedSetOf<String>()
        repeat(250) {
            if (s2.gameOver) return@repeat
            s2.activePlayerId?.let { seen.add(it.value) }
            val pending = s2.pendingDecision
            val a: GameAction = if (pending != null) SubmitDecision(pending.playerId, respond(pending))
            else {
                val pp = s2.priorityPlayerId ?: return@repeat
                chooseAction(s2, pp, enumerator, skipped) ?: PassPriority(pp)
            }
            val res = processor.process(s2, a).result
            if (res.error != null || (!res.isSuccess && !res.isPaused)) { err = "${actionSummary(a)}: ${res.error}"; return@repeat }
            s2 = res.newState
        }
        checks.add("rotationCovers5=${seen.size == 5} ($seen)")
        checks.add("submitError=$err")
        val allCmdr = cmdZones.all { it.contains("zone=1:commander=true:ownerOk=true") }
        findings.add(jo("test" to "F2-commander5", "checks" to checks,
            "pass" to (allCmdr && regs.all { it == 1 } && err == null && seen.size == 5)))
    }

    // --- F3: elimination ladder ---
    run {
        val decks = fiveDecks(5)
        val init = initGame(registry, seatConfigs("F3-elim5", decks), 9003L, Format.Standard, true)
        var s = init.state
        val order = s.turnOrder.toList()
        val steps = mutableListOf<String>()
        // Concede 4 players one by one (keeping the last), checking continuation.
        for (leaver in order.dropLast(1)) {
            val r = processor.process(s, Concede(leaver)).result
            if (r.error != null || (!r.isSuccess && !r.isPaused)) {
                steps.add("concede ${leaver.value} FAILED: ${r.error}")
                break
            }
            s = r.newState
            val left = s.getEntity(leaver)?.has<PlayerLeftGameComponent>() == true
            steps.add("concede ${leaver.value}: left=$left gameOver=${s.gameOver} winner=${s.winnerId?.value} active=${s.activePlayerId?.value} pri=${s.priorityPlayerId?.value}")
            // game must continue while 2+ remain
            if (!s.gameOver) {
                // advance a couple of priorities to prove the pod plays on
                repeat(4) {
                    val pp = s.priorityPlayerId ?: return@repeat
                    if (s.pendingDecision != null) return@repeat
                    val rr = processor.process(s, PassPriority(pp)).result
                    if (rr.error == null && (rr.isSuccess || rr.isPaused)) s = rr.newState else return@repeat
                }
                steps.add("  pod plays on: turn=${s.turnNumber} active=${s.activePlayerId?.value}")
            }
        }
        // Post-leave rotation on a FRESH 5P game: concede seat 0, then play two full
        // turns and assert turns only visit remaining seats.
        run {
            val init2 = initGame(registry, seatConfigs("F3-rot5", fiveDecks(5)), 9005L, Format.Standard, true)
            var t = init2.state
            val gone = t.turnOrder.first()
            t = processor.process(t, Concede(gone)).result.newState
            val startTurn = t.turnNumber
            val actives = linkedSetOf<String>()
            val skipped2 = mutableListOf<String>()
            var err2: String? = null
            // Skip the transient stale active (leaver's unfinished turn); collect once
            // the turn manager has advanced past it.
            var collecting = false
            repeat(300) {
                if (t.gameOver) return@repeat
                if (t.turnNumber > startTurn + 1) return@repeat
                if (t.turnNumber > startTurn) collecting = true
                if (collecting) t.activePlayerId?.let { actives.add(it.value) }
                val pending = t.pendingDecision
                val a: GameAction = if (pending != null) SubmitDecision(pending.playerId, respond(pending))
                else {
                    val pp = t.priorityPlayerId ?: return@repeat
                    chooseAction(t, pp, enumerator, skipped2) ?: PassPriority(pp)
                }
                val r = processor.process(t, a).result
                if (r.error != null || (!r.isSuccess && !r.isPaused)) { err2 = "${actionSummary(a)}: ${r.error}"; return@repeat }
                t = r.newState
            }
            steps.add("post-leave rotation: leaver=${gone.value} actives=$actives leaverRevisited=${gone.value in actives} err=$err2")
        }
        steps.add("final: gameOver=${s.gameOver} winner=${s.winnerId?.value} survivor=${order.last().value}")
        val pass = s.gameOver && s.winnerId == order.last()
        findings.add(jo("test" to "F3-elimination5", "steps" to steps, "pass" to pass))
    }

    // --- F4: 6P smoke ---
    run {
        val decks = fiveDecks(6)
        val init = initGame(registry, seatConfigs("F4-ffa6", decks), 9004L, Format.Standard, true)
        var s = init.state
        val skipped = mutableListOf<String>()
        var err: String? = null
        val seen = linkedSetOf<String>()
        repeat(150) {
            if (s.gameOver) return@repeat
            s.activePlayerId?.let { seen.add(it.value) }
            val pending = s.pendingDecision
            val a: GameAction = if (pending != null) SubmitDecision(pending.playerId, respond(pending))
            else {
                val pp = s.priorityPlayerId ?: return@repeat
                chooseAction(s, pp, enumerator, skipped) ?: PassPriority(pp)
            }
            val r = processor.process(s, a).result
            if (r.error != null || (!r.isSuccess && !r.isPaused)) { err = "${actionSummary(a)}: ${r.error}"; return@repeat }
            s = r.newState
        }
        findings.add(jo("test" to "F4-ffa6-smoke",
            "checks" to listOf("playerCount=${init.playerIds.size}", "seenActive=$seen", "err=$err", "turn=${s.turnNumber}"),
            "pass" to (err == null && init.playerIds.size == 6)))
    }

    val root = jo(
        "probe" to "U10 five-player feasibility",
        "candidate" to jo("head" to CANDIDATE_HEAD, "tree" to CANDIDATE_TREE),
        "staticScan" to jo(
            "engineFixedFourGate" to "none found (GameInitializer requires >=2, unbounded above)",
            "productLayerCaps" to listOf(
                "ScenarioBuilderService: dev-scenario injection capped at 4 seats (product surface, not engine)",
                "LobbyHandler: 2HG fixed at 4 (rules-correct); TeamVsTeam even>=4 (rules-correct)",
                "FreeForAllHandler: GameSession maxPlayers = lobby playerStates.size (unbounded by handler); lobby default maxPlayers=8",
                "SealedSession count>4 hit is the 4-copy deckbuilding rule (unrelated)"
            ),
        ),
        "tests" to findings,
        "overall" to (findings.all { (it as JO).map["pass"] == true }),
    )
    writeJson(outPath, root)
    println("wrote $outPath")
}
