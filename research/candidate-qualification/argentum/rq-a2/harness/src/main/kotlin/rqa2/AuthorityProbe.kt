package rqa2

import com.wingedsheep.engine.core.CastSpell
import com.wingedsheep.engine.core.Concede
import com.wingedsheep.engine.core.DeclareAttackers
import com.wingedsheep.engine.core.DeclareBlockers
import com.wingedsheep.engine.core.GameAction
import com.wingedsheep.engine.core.PassPriority
import com.wingedsheep.engine.core.SubmitDecision
import com.wingedsheep.engine.state.ZoneKey
import com.wingedsheep.engine.state.GameState
import com.wingedsheep.gym.contract.ObservationBuilder
import com.wingedsheep.engine.state.components.identity.CardComponent
import com.wingedsheep.engine.state.components.player.PlayerLeftGameComponent
import com.wingedsheep.sdk.core.Format
import com.wingedsheep.sdk.core.ManaCost
import com.wingedsheep.sdk.core.Step
import com.wingedsheep.sdk.core.Subtype
import com.wingedsheep.sdk.core.TypeLine
import com.wingedsheep.sdk.core.Zone
import com.wingedsheep.sdk.dsl.Triggers
import com.wingedsheep.sdk.model.CardDefinition
import com.wingedsheep.sdk.model.CardScript
import com.wingedsheep.sdk.model.Deck
import com.wingedsheep.sdk.model.EntityId
import com.wingedsheep.sdk.scripting.EventPattern
import com.wingedsheep.sdk.scripting.TriggerBinding
import com.wingedsheep.sdk.scripting.TriggeredAbility
import com.wingedsheep.sdk.scripting.effects.DealDamageEffect
import com.wingedsheep.sdk.scripting.effects.GainLifeEffect
import com.wingedsheep.sdk.scripting.targets.EffectTarget
import com.wingedsheep.sdk.scripting.references.Player

// U2/U3 — authority-gate packets: smallest runtime fixtures exposing the behavior,
// actual behavior recorded. Muse does NOT resolve the official Rules question.

// Driver-local fixture cards (engine behavior probes, not corpus claims).
val LtbWatcher = CardDefinition.enchantment(
    name = "RQ-A2 LTB Watcher",
    manaCost = ManaCost.parse("{1}{W}"),
    oracleText = "Whenever a card leaves the battlefield, you gain 1 life.",
    script = CardScript.permanent(
        triggeredAbilities = listOf(
            TriggeredAbility.create(
                trigger = EventPattern.ZoneChangeEvent(from = Zone.BATTLEFIELD),
                binding = TriggerBinding.ANY,
                effect = GainLifeEffect(1),
            )
        )
    )
)

val UpkeepPing = CardDefinition(
    name = "RQ-A2 Upkeep Ping",
    manaCost = ManaCost.parse("{3}"),
    typeLine = TypeLine.artifact(emptySet()),
    oracleText = "At the beginning of each opponent's upkeep, this deals 1 damage to that player.",
    script = CardScript.permanent(
        triggeredAbilities = listOf(
            TriggeredAbility.create(
                trigger = Triggers.EachOpponentUpkeep.event,
                binding = TriggerBinding.ANY,
                effect = DealDamageEffect(1, EffectTarget.PlayerRef(Player.TriggeringPlayer)),
            )
        )
    )
)

fun main(args: Array<String>) {
    val outPath = args.getOrNull(0)
        ?: "/home/moeen/code/rq-a2-argentum-comparable-qualification/research/candidate-qualification/argentum/rq-a2/evidence/ARGENTUM_AUTHORITY_PROBES.json"
    val registry = newRegistry()
    registry.register(listOf(LtbWatcher, UpkeepPing))
    val processor = newProcessor(registry)
    val enumerator = newEnumerator(registry)
    val packets = mutableListOf<Any?>()

    // ---------------- U2: leave-game mass removal vs remaining LTB triggers ----------------
    run {
        val log = mutableListOf<String>()
        // 4P FFA: A(Bears) / B(Treason) / C(LTB Watcher + DTTC) / D(by standaard).
        val decks = listOf(
            "A" to Deck.of("Forest" to 20, "Mountain" to 8, "Grizzly Bears" to 8, "Goblin Guide" to 4),
            "B" to Deck.of("Mountain" to 20, "Forest" to 8, "Act of Treason" to 6, "Goblin Guide" to 6),
            "C" to Deck.of("Plains" to 16, "Swamp" to 8, "RQ-A2 LTB Watcher" to 6, "Death Trigger Test Creature" to 6),
            "D" to Deck.of("Forest" to 40),
        )
        val init = initGame(registry, seatConfigs("U2-leave", decks), 7101L, Format.Standard, true)
        var s = init.state
        val (a, b, c) = Triple(init.playerIds[0], init.playerIds[1], init.playerIds[2])
        val skipped = mutableListOf<String>()
        // Develop: A casts Bears; B steals them via Treason; C fields the Watcher.
        var err: String? = null
        fun submitOk(act: GameAction): Boolean {
            val r = processor.process(s, act).result
            if (r.error != null || (!r.isSuccess && !r.isPaused)) { err = "${actionSummary(act)}: ${r.error}"; return false }
            s = r.newState; return true
        }
        // Land drops may fail (already dropped) — that is never fatal here.
        fun tryLand(pp: EntityId): Boolean {
            val land = s.handOf(pp, "Forest", registry) ?: s.handOf(pp, "Mountain", registry)
                ?: s.handOf(pp, "Plains", registry) ?: s.handOf(pp, "Swamp", registry)
                ?: return false
            val r = processor.process(s, com.wingedsheep.engine.core.PlayLand(pp, land)).result
            if (r.error == null && (r.isSuccess || r.isPaused)) { s = r.newState; return true }
            return false
        }
        var guard = 0
        while (guard++ < 600) {
            if (s.gameOver) break
            val aOk = s.state2field(a, "Grizzly Bears", registry) != null
            val stolen = s.projectedCtrl("Grizzly Bears", registry) == b
            val watcher = s.state2field(c, "RQ-A2 LTB Watcher", registry) != null
            if (aOk && stolen && watcher) break
            val pending = s.pendingDecision
            if (pending != null) {
                if (!submitOk(SubmitDecision(pending.playerId, respond(pending)))) break
            } else {
                val pp = s.priorityPlayerId ?: break
                var acted = false
                if (pp == s.activePlayerId && s.stack.isEmpty() &&
                    (s.phase == com.wingedsheep.sdk.core.Phase.PRECOMBAT_MAIN || s.phase == com.wingedsheep.sdk.core.Phase.POSTCOMBAT_MAIN)) {
                    if (tryLand(pp)) acted = true
                    if (!acted) {
                        val want = when (pp) {
                            a -> if (!aOk) "Grizzly Bears" else null
                            b -> if (!stolen && s.handOf(b, "Act of Treason", registry) != null &&
                                s.state2field(a, "Grizzly Bears", registry) != null) "Act of Treason!" else null
                            c -> if (!watcher) "RQ-A2 LTB Watcher" else null
                            else -> null
                        }
                        if (want != null) {
                            val clean = want.trimEnd('!')
                            val cid = s.handOf(pp, clean, registry)
                            if (cid != null) {
                                val act = if (want.endsWith("!")) {
                                    val tgt = s.state2field(a, "Grizzly Bears", registry)!!
                                    CastSpell(pp, cid, targets = listOf(
                                        com.wingedsheep.engine.state.components.stack.ChosenTarget.Permanent(tgt)))
                                } else CastSpell(pp, cid)
                                if (submitOk(act)) acted = true
                            }
                        }
                    }
                }
                if (!acted) {
                    if (!submitOk(s.declareFor(pp, enumerator) ?: PassPriority(pp))) break
                }
            }
        }
        val setupOk = s.state2field(a, "Grizzly Bears", registry) != null &&
            s.projectedCtrl("Grizzly Bears", registry) == b &&
            s.state2field(c, "RQ-A2 LTB Watcher", registry) != null
        log.add("setup: bearsOnA=${s.state2field(a, "Grizzly Bears", registry) != null} " +
            "projectedCtrl=${s.projectedCtrl("Grizzly Bears", registry)?.value} " +
            "watcher=${s.state2field(c, "RQ-A2 LTB Watcher", registry) != null} err=${if (setupOk) null else err}")
        val bPermanents = s.getBattlefield().count {
            s.getEntity(it)?.get<com.wingedsheep.engine.state.components.identity.OwnerComponent>()?.playerId == b
        }
        val cLife0 = s.lifeTotal(c)
        // B (the thief) concedes: everything B owns leaves; theft must revert to A.
        val rc = processor.process(s, Concede(b)).result
        if (rc.error != null || (!rc.isSuccess && !rc.isPaused)) {
            log.add("concede failed: ${rc.error}")
        } else {
            s = rc.newState
            val bearsBack = s.state2field(a, "Grizzly Bears", registry) != null
            val ctrlBack = s.projectedCtrl("Grizzly Bears", registry)
            val cLife1 = s.lifeTotal(c)
            log.add("after B leaves: bOwnedPermanentsWere=$bPermanents bearsBackOnA=$bearsBack " +
                "projectedCtrl=${ctrlBack?.value} cLife=$cLife0->$cLife1 " +
                "bMarkedLeft=${s.getEntity(b)?.has<PlayerLeftGameComponent>() == true}")
            // Keep playing a full round; record any trigger resolutions for C.
            val triggerNotes = mutableListOf<String>()
            repeat(120) {
                if (s.gameOver) return@repeat
                val pending = s.pendingDecision
                if (pending != null) {
                    triggerNotes.add("decision ${pending::class.simpleName}@${pending.playerId.value}")
                    val r = processor.process(s, SubmitDecision(pending.playerId, respond(pending))).result
                    if (r.error == null && (r.isSuccess || r.isPaused)) s = r.newState else return@repeat
                } else {
                    val pp = s.priorityPlayerId ?: return@repeat
                    val r = processor.process(s, s.declareFor(pp, enumerator) ?: PassPriority(pp)).result
                    if (r.error == null && (r.isSuccess || r.isPaused)) s = r.newState else return@repeat
                }
            }
            log.add("post-leave round: cLife=${s.lifeTotal(c)} triggerNotes=$triggerNotes")
        }
        packets.add(jo("gate" to "U2",
            "question" to "CR 800.4a vs 800.4d: when a player leaves and their objects leave the game en masse, must the REMAINING players' leaves-the-battlefield triggers fire? (The leaver's own must not.) Second: CR 800.4c static-ability exile of leaver-controlled objects (source-cited, no live fixture).",
            "source" to "rules-engine/.../mechanics/sba/player/PlayerLeavesGameProcessor.kt:50-56 (two documented simplifications)",
            "fixture" to "4P FFA seed 7101: B steals A's Bears via Act of Treason, fields Watcher+DTTC on C, B concedes",
            "observed" to log,
            "status" to "BEHAVIOR-RECORDED; RULES-QUESTION-OPEN for Sol High"))
    }

    // ---------------- U3: 2HG per-opposing-teammate trigger fan-out ----------------
    run {
        val log = mutableListOf<String>()
        val decks = listOf(
            "T0A" to Deck.of("Forest" to 20, "Mountain" to 12, "RQ-A2 Upkeep Ping" to 4),
            "T0B" to Deck.of("Forest" to 40),
            "T1A" to Deck.of("Forest" to 40),
            "T1B" to Deck.of("Forest" to 40),
        )
        val cfg = com.wingedsheep.engine.core.GameConfig(
            players = decks.mapIndexed { i, (n, d) ->
                com.wingedsheep.engine.core.PlayerConfig(n, d, 20,
                    playerId = EntityId.of("rq-a2-U3-2hg-p$i"))
            },
            teams = listOf(listOf(0, 1), listOf(2, 3)),
            format = Format.TwoHeadedGiant(),
            skipMulligans = true,
            seed = 7201L,
        )
        var s = com.wingedsheep.engine.core.GameInitializer(registry).initializeGame(cfg).state
        val t0a = EntityId.of("rq-a2-U3-2hg-p0")
        var err: String? = null
        fun submitOk(act: GameAction): Boolean {
            val r = processor.process(s, act).result
            if (r.error != null || (!r.isSuccess && !r.isPaused)) { err = "${actionSummary(act)}: ${r.error}"; return false }
            s = r.newState; return true
        }
        // Develop: T0A casts the ping artifact (needs 3 mana of any).
        var guard = 0
        while (guard++ < 500) {
            if (s.gameOver) break
            if (s.state2field(t0a, "RQ-A2 Upkeep Ping", registry) != null) break
            val pending = s.pendingDecision
            if (pending != null) {
                if (!submitOk(SubmitDecision(pending.playerId, respond(pending)))) break
            } else {
                val pp = s.priorityPlayerId ?: break
                var acted = false
                if (pp == s.activePlayerId && s.stack.isEmpty() &&
                    (s.phase == com.wingedsheep.sdk.core.Phase.PRECOMBAT_MAIN || s.phase == com.wingedsheep.sdk.core.Phase.POSTCOMBAT_MAIN)) {
                    val land = s.handOf(pp, "Forest", registry) ?: s.handOf(pp, "Mountain", registry)
                    if (land != null && submitOk(PlayLandOf(pp, land))) acted = true
                    if (!acted && pp == t0a) {
                        val cid = s.handOf(pp, "RQ-A2 Upkeep Ping", registry)
                        if (cid != null && submitOk(CastSpell(pp, cid))) acted = true
                    }
                }
                if (!acted) if (!submitOk(s.declareFor(pp, enumerator) ?: PassPriority(pp))) break
            }
        }
        log.add("setup: pingOnField=${s.state2field(t0a, "RQ-A2 Upkeep Ping", registry) != null} err=${if (s.state2field(t0a, "RQ-A2 Upkeep Ping", registry) != null) null else err} teams=${s.teams}")
        // Advance to the opposing team's upkeep; count trigger firings + life movement.
        val team1 = listOf(EntityId.of("rq-a2-U3-2hg-p2"), EntityId.of("rq-a2-U3-2hg-p3"))
        val life0 = team1.associateWith { s.lifeTotal(it) }
        val shared0 = s.lifeTotal(team1[0])
        var firings = 0
        var sawUpkeep = false
        guard = 0
        while (guard++ < 300) {
            if (s.gameOver) break
            if (s.activePlayerId in team1 && s.state2step() == Step.UPKEEP) {
                sawUpkeep = true
                // count stack trigger abilities + answer decisions; then watch life
                repeat(40) {
                    val trigCount = s.stack.size
                    if (trigCount > firings) firings = trigCount
                    val pending = s.pendingDecision
                    if (pending != null) {
                        val r = processor.process(s, SubmitDecision(pending.playerId, respond(pending))).result
                        if (r.error == null && (r.isSuccess || r.isPaused)) s = r.newState else return@repeat
                    } else {
                        if (s.state2step() != Step.UPKEEP || s.activePlayerId !in team1) return@repeat
                        val pp = s.priorityPlayerId ?: return@repeat
                        val r = processor.process(s, PassPriority(pp)).result
                        if (r.error == null && (r.isSuccess || r.isPaused)) s = r.newState else return@repeat
                    }
                }
                break
            }
            val pending = s.pendingDecision
            if (pending != null) {
                if (!submitOk(SubmitDecision(pending.playerId, respond(pending)))) break
            } else {
                val pp = s.priorityPlayerId ?: break
                if (!submitOk(s.declareFor(pp, enumerator) ?: PassPriority(pp))) break
            }
        }
        val life1 = team1.associateWith { s.lifeTotal(it) }
        log.add("opposingUpkeepReached=$sawUpkeep maxStackTriggers=$firings " +
            "sharedLife=$shared0->${s.lifeTotal(team1[0])} perSeat=$life0->$life1")
        packets.add(jo("gate" to "U3",
            "question" to "CR 805.4d multiplicity: a nonactive player's 'each opponent's step' trigger while the opposing TEAM is active — fire once, or once per opposing teammate (twice in 2HG)? Engine fires once (TriggerMatcher.kt:1717-1718).",
            "source" to "rules-engine/.../event/TriggerMatcher.kt:1712-1718 + matchesPlayerForStep",
            "fixture" to "2HG seed 7201: T0A fields driver-local EachOpponentUpkeep ping artifact; advance to opposing team upkeep",
            "observed" to log,
            "status" to "BEHAVIOR-RECORDED; RULES-QUESTION-OPEN for Sol High"))
    }

    val root = jo(
        "probe" to "U2/U3 authority-gate runtime fixtures",
        "candidate" to jo("head" to CANDIDATE_HEAD, "tree" to CANDIDATE_TREE),
        "packets" to packets,
    )
    writeJson(outPath, root)
    println("wrote $outPath")
}

// --- small state helpers (probe-local) ---
fun GameState.state2field(p: EntityId, name: String, registry: com.wingedsheep.engine.registry.CardRegistry): EntityId? =
    getZone(ZoneKey(p, Zone.BATTLEFIELD)).firstOrNull {
        getEntity(it)?.get<CardComponent>()?.name == name
    }

fun GameState.handOf(p: EntityId, name: String, registry: com.wingedsheep.engine.registry.CardRegistry): EntityId? =
    getZone(ZoneKey(p, Zone.HAND)).firstOrNull {
        getEntity(it)?.get<CardComponent>()?.name == name
    }

fun GameState.projectedCtrl(name: String, registry: com.wingedsheep.engine.registry.CardRegistry): EntityId? {
    val o = ObservationBuilder(registry).build(this, turnOrder.first(), emptyList()).observation
        as com.wingedsheep.gym.contract.TrainingObservation
    val c = o.zones.filter { it.zoneType == Zone.BATTLEFIELD }.flatMap { it.cards }.firstOrNull {
        getEntity(it.entityId)?.get<CardComponent>()?.name == name
    }
    return c?.controllerId
}

fun PlayLandOf(p: EntityId, land: EntityId): com.wingedsheep.engine.core.PlayLand =
    com.wingedsheep.engine.core.PlayLand(p, land)

fun GameState.state2step(): Step = step

fun GameState.declareFor(
    pp: EntityId,
    enumerator: com.wingedsheep.engine.legalactions.LegalActionEnumerator,
): GameAction? {
    if (step == Step.DECLARE_ATTACKERS && pp == activePlayerId) {
        if (getEntity(pp)?.has<com.wingedsheep.engine.state.components.combat.AttackersDeclaredThisCombatComponent>() == true) return null
        return DeclareAttackers(pp, emptyMap())
    }
    if (step == Step.DECLARE_BLOCKERS && pp != activePlayerId) {
        if (getEntity(pp)?.has<com.wingedsheep.engine.state.components.combat.BlockersDeclaredThisCombatComponent>() == true) return null
        return DeclareBlockers(pp, emptyMap())
    }
    return null
}
