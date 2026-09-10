package rqa2

import com.wingedsheep.engine.core.CardsSelectedResponse
import com.wingedsheep.engine.core.CastSpell
import com.wingedsheep.engine.core.GameAction
import com.wingedsheep.engine.core.PassPriority
import com.wingedsheep.engine.core.SelectCardsDecision
import com.wingedsheep.engine.core.SubmitDecision
import com.wingedsheep.engine.state.GameState
import com.wingedsheep.engine.state.ZoneKey
import com.wingedsheep.engine.state.components.identity.CardComponent
import com.wingedsheep.sdk.core.Format
import com.wingedsheep.sdk.core.Zone
import com.wingedsheep.sdk.model.Deck
import com.wingedsheep.sdk.model.EntityId

// Decision-seam checks: U12 starting-player seam, U15 trigger-ordering path,
// and stale action / decision freshness (fail-closed behavior proven at runtime).

fun main(args: Array<String>) {
    val outPath = args.getOrNull(0)
        ?: "/home/moeen/code/rq-a2-argentum-comparable-qualification/research/candidate-qualification/argentum/rq-a2/evidence/ARGENTUM_DECISION_FRESHNESS.json"
    val registry = newRegistry()
    registry.register(listOf(LtbWatcher))
    val processor = newProcessor(registry)
    val out = mutableListOf<Any?>()

    // ---------- U12: starting-player seam ----------
    run {
        val rows = mutableListOf<Any?>()
        for (idx in listOf(0, 1, 2)) {
            val decks = listOf(
                "A" to Deck.of("Forest" to 40), "B" to Deck.of("Forest" to 40),
                "C" to Deck.of("Forest" to 40))
            val init = com.wingedsheep.engine.core.GameInitializer(registry).initializeGame(
                com.wingedsheep.engine.core.GameConfig(
                    players = decks.mapIndexed { i, (n, d) ->
                        com.wingedsheep.engine.core.PlayerConfig(n, d, 20,
                            playerId = EntityId.of("rq-a2-u12-p$i"))
                    },
                    skipMulligans = true, seed = 8100L + idx, startingPlayerIndex = idx,
                )
            )
            rows.add(jo("startingPlayerIndex" to idx,
                "activePlayer" to init.state.activePlayerId?.value,
                "turnOrderHead" to init.state.turnOrder.firstOrNull()?.value,
                "pendingAtInit" to (init.state.pendingDecision?.let { it::class.simpleName }),
                "matchesIndex" to (init.state.activePlayerId == init.state.turnOrder.firstOrNull() &&
                    init.state.turnOrder.firstOrNull()?.value == "rq-a2-u12-p$idx")))
        }
        out.add(jo("check" to "U12-starting-player",
            "verdict" to "configuration-only input: GameConfig.startingPlayerIndex selects the starting seat; no PendingDecision/GameAction seam exists (static: no starting-player question among the 19 PendingDecision kinds; GameInitializer consumes the index directly)",
            "rows" to rows))
    }

    // ---------- Freshness: F1..F4 + cross-decision stale ----------
    run {
        val decks = listOf(
            "A" to Deck.of("Swamp" to 28, "Careful Study" to 12),
            "B" to Deck.of("Swamp" to 40))
        val init = initGame(registry, seatConfigs("FRESH", decks), 8200L, Format.Standard, true)
        var s = init.state
        val a = init.playerIds[0]; val b = init.playerIds[1]
        val rows = mutableListOf<Any?>()
        fun submitOk(act: GameAction): Boolean {
            val r = processor.process(s, act).result
            if (r.error != null || (!r.isSuccess && !r.isPaused)) return false
            s = r.newState; return true
        }
        // Develop until A faces a SelectCardsDecision (Study discard or cleanup).
        var guard = 0
        var target: SelectCardsDecision? = null
        while (guard++ < 600) {
            val pending = s.pendingDecision
            if (pending is SelectCardsDecision) { target = pending; break }
            if (pending != null) {
                if (!submitOk(SubmitDecision(pending.playerId, respond(pending)))) break
            } else {
                val pp = s.priorityPlayerId ?: break
                // cast Study when able on A's main
                var acted = false
                if (pp == a && s.activePlayerId == a && s.stack.isEmpty() &&
                    (s.phase == com.wingedsheep.sdk.core.Phase.PRECOMBAT_MAIN)) {
                    val st = s.getZone(ZoneKey(a, Zone.HAND)).firstOrNull {
                        s.getEntity(it)?.get<CardComponent>()?.name == "Careful Study"
                    }
                    val land = s.getZone(ZoneKey(a, Zone.HAND)).firstOrNull {
                        s.getEntity(it)?.get<CardComponent>()?.typeLine?.isLand == true
                    }
                    if (land != null) {
                        val r = processor.process(s, com.wingedsheep.engine.core.PlayLand(a, land)).result
                        if (r.error == null && (r.isSuccess || r.isPaused)) { s = r.newState; acted = true }
                    }
                    if (!acted && st != null && s.fieldCountOf(a, "Swamp") >= 1) {
                        val r = processor.process(s, CastSpell(a, st)).result
                        if (r.error == null && (r.isSuccess || r.isPaused)) { s = r.newState; acted = true }
                    }
                }
                if (!acted) {
                    val r = processor.process(s, PassPriority(pp)).result
                    if (r.error == null && (r.isSuccess || r.isPaused)) s = r.newState else break
                }
            }
        }
        val d = target
        if (d == null) {
            rows.add(jo("setup" to "FAILED: no SelectCardsDecision reached"))
        } else {
            // F1: valid current response succeeds.
            val good = CardsSelectedResponse(d.id, d.options.take(d.minSelections))
            var r = processor.process(s, SubmitDecision(d.playerId, good)).result
            rows.add(jo("F1-valid-current" to ((r.error == null && (r.isSuccess || r.isPaused)).toString())))
            if (r.error == null && (r.isSuccess || r.isPaused)) s = r.newState
            // F2: re-answer the same (now-stale) decision id.
            r = processor.process(s, SubmitDecision(d.playerId, good)).result
            rows.add(jo("F2-stale-same-id" to failClosed(r.error)))
            // F3: fabricated decision id.
            r = processor.process(s, SubmitDecision(d.playerId,
                CardsSelectedResponse("fabricated-id", emptyList()))).result
            rows.add(jo("F3-fabricated-id" to failClosed(r.error)))
            // F4: wrong actor answers a fresh decision (drive to the next one).
            var guard2 = 0
            var d2: SelectCardsDecision? = null
            while (guard2++ < 400) {
                val pending = s.pendingDecision
                if (pending is SelectCardsDecision) { d2 = pending; break }
                if (pending != null) {
                    val rr = processor.process(s, SubmitDecision(pending.playerId, respond(pending))).result
                    if (rr.error == null && (rr.isSuccess || rr.isPaused)) s = rr.newState else break
                } else {
                    val pp = s.priorityPlayerId ?: break
                    val rr = processor.process(s, PassPriority(pp)).result
                    if (rr.error == null && (rr.isSuccess || rr.isPaused)) s = rr.newState else break
                }
            }
            if (d2 == null) {
                rows.add(jo("F4-wrong-actor" to "SKIPPED: no second decision reached"))
            } else {
                val other = if (d2.playerId == a) b else a
                r = processor.process(s, SubmitDecision(other,
                    CardsSelectedResponse(d2.id, d2.options.take(d2.minSelections)))).result
                rows.add(jo("F4-wrong-actor" to failClosed(r.error)))
                // F5: answer the CURRENT decision with the PREVIOUS decision's id.
                r = processor.process(s, SubmitDecision(d2.playerId,
                    CardsSelectedResponse(d.id, d2.options.take(d2.minSelections)))).result
                rows.add(jo("F5-old-id-on-new-decision" to failClosed(r.error)))
            }
        }
        out.add(jo("check" to "decision-freshness", "rows" to rows))
    }

    // ---------- U15: trigger-ordering path ----------
    run {
        // P0 fields DTTC (dies: gain 3) + LTB Watcher (any battlefield exit: gain 1);
        // one DTTC death fires both under one controller -> ordering question?
        val decks = listOf(
            "A" to Deck.of("Swamp" to 16, "Plains" to 12, "Death Trigger Test Creature" to 6, "RQ-A2 LTB Watcher" to 6),
            "B" to Deck.of("Mountain" to 24, "Lightning Bolt" to 8, "Goblin Guide" to 8))
        val init = initGame(registry, seatConfigs("U15-order", decks), 8300L, Format.Standard, true)
        var s = init.state
        val a = init.playerIds[0]; val b = init.playerIds[1]
        val log = mutableListOf<String>()
        var err: String? = null
        fun submitOk(act: GameAction): Boolean {
            val r = processor.process(s, act).result
            if (r.error != null || (!r.isSuccess && !r.isPaused)) { err = "${actionSummary(act)}: ${r.error}"; return false }
            s = r.newState; return true
        }
        var guard = 0
        while (guard++ < 700) {
            if (s.gameOver) break
            val hasDttc = s.getZone(ZoneKey(a, Zone.BATTLEFIELD)).any {
                s.getEntity(it)?.get<CardComponent>()?.name == "Death Trigger Test Creature" }
            val hasWatch = s.getZone(ZoneKey(a, Zone.BATTLEFIELD)).any {
                s.getEntity(it)?.get<CardComponent>()?.name == "RQ-A2 LTB Watcher" }
            val bReady = s.getZone(ZoneKey(b, Zone.BATTLEFIELD)).any {
                s.getEntity(it)?.get<CardComponent>()?.name == "Mountain" } &&
                s.getZone(ZoneKey(b, Zone.HAND)).any {
                s.getEntity(it)?.get<CardComponent>()?.name == "Lightning Bolt" }
            if (hasDttc && hasWatch && bReady) break
            val pending = s.pendingDecision
            if (pending != null) {
                if (!submitOk(SubmitDecision(pending.playerId, respond(pending)))) break
            } else {
                val pp = s.priorityPlayerId ?: break
                var acted = false
                if (pp == s.activePlayerId && s.stack.isEmpty() &&
                    (s.phase == com.wingedsheep.sdk.core.Phase.PRECOMBAT_MAIN || s.phase == com.wingedsheep.sdk.core.Phase.POSTCOMBAT_MAIN)) {
                    val land = s.getZone(ZoneKey(pp, Zone.HAND)).firstOrNull {
                        s.getEntity(it)?.get<CardComponent>()?.typeLine?.isLand == true }
                    if (land != null) {
                        val r = processor.process(s, com.wingedsheep.engine.core.PlayLand(pp, land)).result
                        if (r.error == null && (r.isSuccess || r.isPaused)) { s = r.newState; acted = true }
                    }
                    if (!acted) {
                        val want = when (pp) {
                            a -> when {
                                !hasDttc -> "Death Trigger Test Creature"
                                !hasWatch -> "RQ-A2 LTB Watcher"
                                else -> null
                            }
                            else -> null
                        }
                        val cid = want?.let {
                            s.getZone(ZoneKey(pp, Zone.HAND)).firstOrNull { eid ->
                                s.getEntity(eid)?.get<CardComponent>()?.name == it } }
                        if (cid != null && submitOk(CastSpell(pp, cid))) acted = true
                    }
                }
                if (!acted) if (!submitOk(PassPriority(pp))) break
            }
        }
        log.add("setup: dttc+watcher on A, B has Bolt+Mountain; err=$err")
        val dttc = s.getZone(ZoneKey(a, Zone.BATTLEFIELD)).firstOrNull {
            s.getEntity(it)?.get<CardComponent>()?.name == "Death Trigger Test Creature" }
        if (dttc == null) {
            log.add("ABORT: DTTC not on field")
        } else {
            // B Bolts the DTTC; both triggers fire; record the ordering question type.
            var guard2 = 0
            while (guard2++ < 60) {
                if (s.priorityPlayerId == b && s.stack.isEmpty() && s.pendingDecision == null) break
                val pending = s.pendingDecision
                if (pending != null) {
                    if (!submitOk(SubmitDecision(pending.playerId, respond(pending)))) break
                } else {
                    val pp = s.priorityPlayerId ?: break
                    if (!submitOk(PassPriority(pp))) break
                }
            }
            val bolt = s.getZone(ZoneKey(b, Zone.HAND)).firstOrNull {
                s.getEntity(it)?.get<CardComponent>()?.name == "Lightning Bolt" }
            if (bolt == null) log.add("ABORT: B has no Bolt")
            else {
                submitOk(CastSpell(b, bolt, targets = listOf(
                    com.wingedsheep.engine.state.components.stack.ChosenTarget.Permanent(dttc))))
                // Now observe: what pauses, in what order?
                val seen = mutableListOf<String>()
                var guard3 = 0
                while (guard3++ < 40) {
                    val pending = s.pendingDecision
                    if (pending == null) {
                        if (s.stack.isEmpty()) break
                        val pp = s.priorityPlayerId ?: break
                        if (!submitOk(PassPriority(pp))) break
                    } else {
                        seen.add("${pending::class.simpleName}@${pending.playerId.value}:${pending.prompt.take(100)}")
                        if (!submitOk(SubmitDecision(pending.playerId, respond(pending)))) break
                    }
                }
                log.add("orderingQuestions=$seen")
                log.add("finalLife=${s.lifeTotal(a)}/${s.lifeTotal(b)} stackEmpty=${s.stack.isEmpty()}")
            }
        }
        out.add(jo("check" to "U15-trigger-ordering",
            "verdict" to "runtime-exposed: see orderingQuestions (empty = engine orders automatically without a PendingDecision on this path)",
            "log" to log))
    }

    val root = jo(
        "probe" to "decision seams + freshness",
        "candidate" to jo("head" to CANDIDATE_HEAD, "tree" to CANDIDATE_TREE),
        "checks" to out,
    )
    writeJson(outPath, root)
    println("wrote $outPath")
}

fun failClosed(err: String?): String =
    if (err != null) "FAIL-CLOSED: $err" else "NOT-FAIL-CLOSED (unexpected success)"

fun GameState.fieldCountOf(p: EntityId, name: String): Int =
    getZone(ZoneKey(p, Zone.BATTLEFIELD)).count {
        getEntity(it)?.get<CardComponent>()?.name == name
    }
