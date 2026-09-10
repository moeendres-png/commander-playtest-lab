package rqa2

import com.wingedsheep.engine.core.CastSpell
import com.wingedsheep.engine.core.Concede
import com.wingedsheep.engine.core.DeclareAttackers
import com.wingedsheep.engine.core.DeclareBlockers
import com.wingedsheep.engine.core.GameAction
import com.wingedsheep.engine.core.PassPriority
import com.wingedsheep.engine.core.PlayLand
import com.wingedsheep.engine.core.SubmitDecision
import com.wingedsheep.engine.state.GameState
import com.wingedsheep.engine.state.ZoneKey
import com.wingedsheep.engine.state.components.identity.CardComponent
import com.wingedsheep.engine.state.components.identity.ControllerComponent
import com.wingedsheep.engine.state.components.identity.LifeTotalComponent
import com.wingedsheep.engine.state.components.stack.ChosenTarget
import com.wingedsheep.gym.contract.ObservationBuilder
import com.wingedsheep.gym.contract.TrainingObservation
import com.wingedsheep.sdk.core.Format
import com.wingedsheep.sdk.core.Step
import com.wingedsheep.sdk.core.Zone
import com.wingedsheep.sdk.model.Deck
import com.wingedsheep.sdk.model.EntityId

// U1 — targeted rules-maturity runtime probes (CPL-side external driver).
//
// Each probe scripts LEGAL play (init + submitted actions only) and asserts the
// rules-expected observable outcome. A probe PASS is DIRECTLY_VERIFIED behavior
// evidence for Sol High adjudication — never EXTERNALLY_RULE_VALIDATED (that
// promotion is Coordinator-controlled). Failures are recorded, never repaired.

class Script(
    val registry: com.wingedsheep.engine.registry.CardRegistry,
    decks: List<Pair<String, Deck>>,
    val seed: Long,
    val format: Format = Format.Standard,
    name: String = "probe",
    commanders: List<String> = emptyList(),
) {
    val processor = newProcessor(registry)
    val enumerator = newEnumerator(registry)
    val obsBuilder = ObservationBuilder(registry)
    var state: GameState
    val playerIds: List<EntityId>
    val byName: Map<String, EntityId>
    val decisions = mutableListOf<String>()
    val submitted = mutableListOf<String>()

    init {
        val init = if (commanders.isEmpty()) {
            initGame(registry, seatConfigs("U1-$name", decks), seed, format, true)
        } else {
            com.wingedsheep.engine.core.GameInitializer(registry).initializeGame(
                com.wingedsheep.engine.core.GameConfig(
                    players = decks.mapIndexed { i, (n, d) ->
                        com.wingedsheep.engine.core.PlayerConfig(n, d, 40,
                            playerId = EntityId.of("rq-a2-U1-$name-p$i"),
                            commanderCardName = commanders[i])
                    },
                    skipMulligans = true, format = format, seed = seed,
                )
            )
        }
        state = init.state
        playerIds = init.playerIds
        byName = decks.mapIndexed { i, (n, _) -> n to playerIds[i] }.toMap()
    }

    fun pid(n: String): EntityId = byName[n] ?: throw IllegalArgumentException("no seat $n")

    fun submit(a: GameAction): String? {
        val r = processor.process(state, a).result
        if (r.error != null || (!r.isSuccess && !r.isPaused)) return "${actionSummary(a)}: ${r.error}"
        state = r.newState
        submitted.add(actionSummary(a))
        r.events.forEach { /* transient; digests not needed here */ }
        return null
    }

    fun hand(p: EntityId, name: String): EntityId? =
        state.getZone(ZoneKey(p, Zone.HAND)).firstOrNull {
            state.getEntity(it)?.get<CardComponent>()?.name == name
        }

    fun field(p: EntityId, name: String): EntityId? =
        state.getZone(ZoneKey(p, Zone.BATTLEFIELD)).firstOrNull {
            state.getEntity(it)?.get<CardComponent>()?.name == name
        }

    fun life(p: EntityId): Int = state.lifeTotal(p)

    fun inGraveyard(p: EntityId, name: String): Boolean =
        state.getZone(ZoneKey(p, Zone.GRAVEYARD)).any {
            state.getEntity(it)?.get<CardComponent>()?.name == name
        }

    fun playLand(p: EntityId, land: String): String? {
        val id = hand(p, land) ?: return "no $land in hand"
        return submit(PlayLand(p, id))
    }

    fun cast(p: EntityId, name: String, targets: List<ChosenTarget> = emptyList()): String? {
        val id = hand(p, name) ?: return "no $name in hand"
        return submit(CastSpell(p, id, targets = targets))
    }

    fun answerAll(): String? {
        repeat(10) {
            val pending = state.pendingDecision ?: return null
            decisions.add("${pending::class.simpleName}@${pending.playerId.value}")
            val err = submit(SubmitDecision(pending.playerId, respond(pending)))
            if (err != null) return err
        }
        return if (state.pendingDecision == null) null else "decision-storm"
    }

    /** Pass until [cond] holds (checked after each pass), answering decisions. Cap 80. */
    fun settle(cond: () -> Boolean = { state.stack.isEmpty() }): String? {
        repeat(80) {
            if (cond()) return null
            val pending = state.pendingDecision
            if (pending != null) {
                decisions.add("${pending::class.simpleName}@${pending.playerId.value}")
                val err = submit(SubmitDecision(pending.playerId, respond(pending)))
                if (err != null) return err
            } else {
                val pp = state.priorityPlayerId ?: return "no-priority@${state.phase}/${state.step}"
                val a = combatDeclareIfNeeded(pp) ?: PassPriority(pp)
                val err = submit(a)
                if (err != null) return err
            }
        }
        return "settle-cap"
    }

    private fun combatDeclareIfNeeded(pp: EntityId): GameAction? {
        if (state.step == Step.DECLARE_ATTACKERS && pp == state.activePlayerId) {
            val t = enumerator.enumerate(state, pp).firstOrNull { it.action is DeclareAttackers }
            val atk = t?.validAttackers ?: emptyList()
            val tgt = t?.validAttackTargets ?: emptyList()
            if (state.getEntity(pp)?.has<com.wingedsheep.engine.state.components.combat.AttackersDeclaredThisCombatComponent>() == true) return null
            return DeclareAttackers(pp, if (atk.isNotEmpty() && tgt.isNotEmpty()) atk.associateWith { tgt.first() } else emptyMap())
        }
        if (state.step == Step.DECLARE_BLOCKERS && pp != state.activePlayerId) {
            if (state.getEntity(pp)?.has<com.wingedsheep.engine.state.components.combat.BlockersDeclaredThisCombatComponent>() == true) return null
            return DeclareBlockers(pp, emptyMap())
        }
        return null
    }

    /** Advance the game (passing/answering + automatic land drops on own mains) until [cond]. */
    fun develop(maxPasses: Int = 500, cond: () -> Boolean): String? {
        repeat(maxPasses) {
            if (state.gameOver) return "game-over"
            if (cond()) return null
            val pending = state.pendingDecision
            if (pending != null) {
                decisions.add("${pending::class.simpleName}@${pending.playerId.value}")
                val err = submit(SubmitDecision(pending.playerId, respond(pending)))
                if (err != null) return err
            } else {
                val pp = state.priorityPlayerId ?: return "no-priority@${state.phase}/${state.step}"
                var acted = false
                if (pp == state.activePlayerId && state.stack.isEmpty() &&
                    (state.phase == com.wingedsheep.sdk.core.Phase.PRECOMBAT_MAIN ||
                        state.phase == com.wingedsheep.sdk.core.Phase.POSTCOMBAT_MAIN)
                ) {
                    val land = state.getZone(ZoneKey(pp, Zone.HAND)).firstOrNull {
                        state.getEntity(it)?.get<CardComponent>()?.typeLine?.isLand == true
                    }
                    if (land != null && submit(PlayLand(pp, land)) == null) acted = true
                }
                if (!acted) {
                    val a = combatDeclareFor(pp) ?: PassPriority(pp)
                    val err = submit(a)
                    if (err != null) return err
                }
            }
        }
        return "develop-cap"
    }

    fun fieldCount(p: EntityId, name: String): Int =
        state.getZone(ZoneKey(p, Zone.BATTLEFIELD)).count {
            state.getEntity(it)?.get<CardComponent>()?.name == name
        }

    /** Like develop(), but also casts [wants] (seat -> card name) on their own mains. */
    fun developCasting(maxPasses: Int = 600, wants: (EntityId) -> String?, cond: () -> Boolean): String? {
        repeat(maxPasses) {
            if (state.gameOver) return "game-over"
            if (cond()) return null
            val pending = state.pendingDecision
            if (pending != null) {
                decisions.add("${pending::class.simpleName}@${pending.playerId.value}")
                val err = submit(SubmitDecision(pending.playerId, respond(pending)))
                if (err != null) return err
            } else {
                val pp = state.priorityPlayerId ?: return "no-priority@${state.phase}/${state.step}"
                var acted = false
                if (pp == state.activePlayerId && state.stack.isEmpty() &&
                    (state.phase == com.wingedsheep.sdk.core.Phase.PRECOMBAT_MAIN ||
                        state.phase == com.wingedsheep.sdk.core.Phase.POSTCOMBAT_MAIN)
                ) {
                    val land = state.getZone(ZoneKey(pp, Zone.HAND)).firstOrNull {
                        state.getEntity(it)?.get<CardComponent>()?.typeLine?.isLand == true
                    }
                    if (land != null && submit(PlayLand(pp, land)) == null) acted = true
                    if (!acted) {
                        val want = wants(pp)
                        val cid = want?.let { hand(pp, it) }
                        if (cid != null && submit(CastSpell(pp, cid)) == null) acted = true
                    }
                }
                if (!acted) {
                    val a = combatDeclareFor(pp) ?: PassPriority(pp)
                    val err = submit(a)
                    if (err != null) return err
                }
            }
        }
        return "develop-cap"
    }

    fun obs(p: EntityId): TrainingObservation =
        obsBuilder.build(state, p, emptyList()).observation as TrainingObservation

    fun projectedController(name: String): EntityId? {
        // Control-changing effects live in floatingEffects + projection (base
        // ControllerComponent keeps the owner) — read the projected controller.
        val o = obs(state.activePlayerId ?: playerIds.first())
        val c = o.zones.filter { it.zoneType == Zone.BATTLEFIELD }.flatMap { it.cards }.firstOrNull {
            state.getEntity(it.entityId)?.get<CardComponent>()?.name == name
        } ?: return null
        return c.controllerId
    }

    fun projectedPT(p: EntityId, name: String): Pair<Int?, Int?>? {
        val o = obs(p)
        val c = o.zones.filter { it.zoneType == Zone.BATTLEFIELD }.flatMap { it.cards }.firstOrNull {
            state.getEntity(it.entityId)?.get<CardComponent>()?.name == name
        } ?: return null
        return c.power to c.toughness
    }
}

data class ProbeResult(
    val id: String,
    val mechanic: String,
    val source: String,
    val setup: String,
    val decisions: List<String>,
    val submitted: List<String>,
    val pass: Boolean,
    val detail: String,
)

inline fun runProbe(id: String, mechanic: String, source: String, setup: String, block: (Script) -> String?): ProbeResult {
    return try {
        // block returns null on success or an error string; Script is created inside block
        val holder = mutableListOf<Script>()
        val err = blockWithScript(id, setup, holder, block)
        val s = holder.firstOrNull()
        ProbeResult(id, mechanic, source, setup, s?.decisions ?: emptyList(),
            s?.submitted?.takeLast(6) ?: emptyList(), err == null, err ?: "PASS")
    } catch (t: Throwable) {
        ProbeResult(id, mechanic, source, setup, emptyList(), emptyList(), false,
            "HARNESS-ERROR ${t::class.simpleName}: ${t.message}")
    }
}

// Script factory per probe id (keeps runProbe small).
inline fun blockWithScript(id: String, setup: String, holder: MutableList<Script>, block: (Script) -> String?): String? {
    val d = ScriptDefs.registryRef ?: throw IllegalStateException("registry not set")
    val spec = ScriptDefs.specs[id] ?: throw IllegalArgumentException("no spec $id")
    val s = Script(d, spec.decks, spec.seed, spec.format, id, spec.commanders)
    holder.add(s)
    return block(s)
}

data class ProbeSpec(
    val decks: List<Pair<String, Deck>>,
    val seed: Long,
    val format: Format,
    val commanders: List<String> = emptyList(),
)

object ScriptDefs {
    var registryRef: com.wingedsheep.engine.registry.CardRegistry? = null
    val specs = mutableMapOf<String, ProbeSpec>()
}

fun main(args: Array<String>) {
    val outPath = args.getOrNull(0)
        ?: "/home/moeen/code/rq-a2-argentum-comparable-qualification/research/candidate-qualification/argentum/rq-a2/evidence/ARGENTUM_RULES_DENSE_PROBES.json"
    val registry = newRegistry()
    ScriptDefs.registryRef = registry
    fun std2(a: List<Pair<String, Deck>>, seed: Long = 6100L) = ProbeSpec(a, seed, Format.Standard)
    fun cmd2(a: List<Pair<String, Deck>>, commanders: List<String>, seed: Long = 6100L) =
        ProbeSpec(a, seed, Format.Commander(), commanders)
    ScriptDefs.specs["P1-priority-stack"] = std2(listOf(
        "A" to Deck.of("Mountain" to 24, "Lightning Bolt" to 8, "Goblin Guide" to 8),
        "B" to Deck.of("Mountain" to 24, "Lightning Bolt" to 8, "Goblin Guide" to 8)))
    ScriptDefs.specs["P2-cost-mana"] = std2(listOf(
        "A" to Deck.of("Forest" to 24, "Grizzly Bears" to 16),
        "B" to Deck.of("Forest" to 40)))
    ScriptDefs.specs["P3-counters"] = std2(listOf(
        "A" to Deck.of("Mountain" to 24, "Lightning Bolt" to 8, "Goblin Guide" to 8),
        "B" to Deck.of("Island" to 24, "Counterspell" to 8, "Goblin Guide" to 8)))
    ScriptDefs.specs["P4-persist"] = std2(listOf(
        "A" to Deck.of("Forest" to 12, "Plains" to 12, "Safehold Elite" to 8),
        "B" to Deck.of("Mountain" to 24, "Lightning Bolt" to 8, "Goblin Guide" to 8)))
    ScriptDefs.specs["P5-layers"] = std2(listOf(
        "A" to Deck.of("Forest" to 12, "Plains" to 12, "Grizzly Bears" to 8, "Giant Growth" to 4, "Glorious Anthem" to 4),
        "B" to Deck.of("Forest" to 40)))
    ScriptDefs.specs["P6-copy"] = std2(listOf(
        "A" to Deck.of("Island" to 20, "Mountain" to 8, "Goblin Guide" to 8, "Grizzly Bears" to 4),
        "B" to Deck.of("Island" to 24, "Test Token Copy" to 8, "Goblin Guide" to 8)))
    ScriptDefs.specs["P7-control"] = std2(listOf(
        "A" to Deck.of("Forest" to 20, "Mountain" to 8, "Grizzly Bears" to 8, "Goblin Guide" to 4),
        "B" to Deck.of("Mountain" to 24, "Act of Treason" to 8, "Goblin Guide" to 8)))
    ScriptDefs.specs["P8-sba"] = std2(listOf(
        "A" to Deck.of("Mountain" to 24, "Lightning Bolt" to 8, "Goblin Guide" to 8),
        "B" to Deck.of("Forest" to 20, "Mountain" to 8, "Goblin Guide" to 8, "Grizzly Bears" to 4)))
    ScriptDefs.specs["P9-apnap"] = std2(listOf(
        "A" to Deck.of("Swamp" to 24, "Death Trigger Test Creature" to 8),
        "B" to Deck.of("Swamp" to 24, "Death Trigger Test Creature" to 8)))
    ScriptDefs.specs["P10-lethal"] = std2(listOf(
        "A" to Deck.of("Mountain" to 24, "Lightning Bolt" to 8, "Goblin Guide" to 8),
        "B" to Deck.of("Forest" to 40)))
    ScriptDefs.specs["P12-multidef"] = ProbeSpec(listOf(
        "A" to Deck.of("Forest" to 20, "Mountain" to 8, "Grizzly Bears" to 8, "Goblin Guide" to 4),
        "B" to Deck.of("Forest" to 24, "Grizzly Bears" to 8, "Goblin Guide" to 8),
        "C" to Deck.of("Forest" to 24, "Grizzly Bears" to 8, "Goblin Guide" to 8)), 6100L, Format.Standard)
    ScriptDefs.specs["P13-search"] = std2(listOf(
        "A" to Deck.of("Forest" to 20, "Evolving Wilds" to 8, "Grizzly Bears" to 8, "Goblin Guide" to 4),
        "B" to Deck.of("Forest" to 40)))
    ScriptDefs.specs["P10-lethal"] = std2(listOf(
        "A" to Deck.of("Mountain" to 24, "Lightning Bolt" to 8, "Goblin Guide" to 8),
        "B" to Deck.of("Forest" to 40)))
    ScriptDefs.specs["P11-commander"] = cmd2(
        listOf(
            "A" to Deck.of("Mountain" to 60, "Lightning Bolt" to 20, "Goblin Guide" to 19),
            "B" to Deck.of("Mountain" to 60, "Lightning Bolt" to 20, "Goblin Guide" to 19)),
        listOf("Test Hasty Prospector", "Test Hasty Prospector"))

    val results = mutableListOf<ProbeResult>()

    // P1 — priority/stack: Bolt resolves off the stack for 3.
    results.add(runProbe("P1-priority-stack", "priority/stack",
        "handlers/actions/spell/CastSpellHandler.kt; mechanics/stack/StackResolver.kt",
        "A casts Lightning Bolt at B; both pass") { s ->
        val a = s.pid("A"); val b = s.pid("B")
        var err = s.develop { s.fieldCount(a, "Mountain") >= 1 && s.hand(a, "Lightning Bolt") != null }
        if (err != null) return@runProbe err
        err = s.gotoMain(a); if (err != null) return@runProbe err
        val boltId = s.hand(a, "Lightning Bolt") ?: return@runProbe "Bolt left hand"
        // Priority order: active player holds priority at turn start window.
        if (s.state.priorityPlayerId != a) return@runProbe "priority not with active/caster: ${s.state.priorityPlayerId?.value}"
        err = s.submit(CastSpell(a, boltId, targets = listOf(ChosenTarget.Player(b))))
        if (err != null) return@runProbe err
        if (s.state.stack.isEmpty()) return@runProbe "stack empty right after cast"
        err = s.settle { s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        if (s.life(b) != 17) return@runProbe "expected B at 17, got ${s.life(b)}"
        if (!s.inGraveyard(a, "Lightning Bolt")) return@runProbe "Bolt not in owner graveyard"
        null
    })

    // P2 — cost/mana: Bears {1}{G} taps exactly two Forests via AutoPay.
    results.add(runProbe("P2-cost-mana", "cost payment + mana system",
        "mechanics/mana/CostCalculator.kt; mechanics/mana/ManaSolver.kt",
        "A casts Grizzly Bears with two Forests") { s ->
        val a = s.pid("A")
        var err = s.develop { s.fieldCount(a, "Forest") >= 2 && s.hand(a, "Grizzly Bears") != null }
        if (err != null) return@runProbe err
        err = s.gotoMain(a)
        if (err != null) return@runProbe err
        val bears = s.hand(a, "Grizzly Bears") ?: return@runProbe "Bears left hand"
        err = s.submit(CastSpell(a, bears))
        if (err != null) return@runProbe err
        err = s.settle { s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        if (s.field(a, "Grizzly Bears") == null) return@runProbe "Bears not on battlefield"
        val tappedForests = s.state.getZone(ZoneKey(a, Zone.BATTLEFIELD)).count {
            s.state.getEntity(it)?.get<CardComponent>()?.name == "Forest" &&
                s.state.getEntity(it)?.has<com.wingedsheep.engine.state.components.battlefield.TappedComponent>() == true
        }
        if (tappedForests < 2) return@runProbe "expected >=2 tapped Forests, got $tappedForests"
        null
    })

    // P3 — stack targeting/counter: Counterspell answers Bolt on the stack.
    results.add(runProbe("P3-counters", "stack targeting; counter",
        "mechanics/stack/StackResolver.kt (counterSpell)",
        "A Bolts B; B Counterspells the Bolt spell") { s ->
        val a = s.pid("A"); val b = s.pid("B")
        var err = s.develop {
            s.fieldCount(a, "Mountain") >= 1 && s.hand(a, "Lightning Bolt") != null &&
                s.fieldCount(b, "Island") >= 2 && s.hand(b, "Counterspell") != null
        }
        if (err != null) return@runProbe err
        err = s.gotoMain(a); if (err != null) return@runProbe err
        val bolt = s.hand(a, "Lightning Bolt") ?: return@runProbe "A has no Bolt"
        err = s.submit(CastSpell(a, bolt, targets = listOf(ChosenTarget.Player(b))))
        if (err != null) return@runProbe err
        if (s.state.stack.isEmpty()) return@runProbe "Bolt not on stack"
        val boltSpell = s.state.stack.last()
        err = s.settle { s.state.priorityPlayerId == b && s.state.stack.isNotEmpty() }
        if (err != null) return@runProbe err
        val cs = s.hand(b, "Counterspell") ?: return@runProbe "B has no Counterspell"
        err = s.submit(CastSpell(b, cs, targets = listOf(ChosenTarget.Spell(boltSpell))))
        if (err != null) return@runProbe "counterspell submit: $err"
        err = s.settle { s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        if (s.life(b) != 20) return@runProbe "B took damage: ${s.life(b)}"
        if (!s.inGraveyard(a, "Lightning Bolt")) return@runProbe "Bolt not countered to graveyard"
        null
    })

    // P4 — replacement (persist): Bolted Safehold Elite returns with a -1/-1 counter.
    results.add(runProbe("P4-persist", "replacement effect (persist)",
        "replacement/ReplacementEffectProcessor.kt; mechanics: persist",
        "B Bolts A's Safehold Elite; persist replaces death") { s ->
        val a = s.pid("A"); val b = s.pid("B")
        var err = s.developCasting(wants = { pp: EntityId -> if (pp == a) "Safehold Elite" else null }) {
            s.field(a, "Safehold Elite") != null && s.fieldCount(b, "Mountain") >= 1 &&
                s.hand(b, "Lightning Bolt") != null
        }
        if (err != null) return@runProbe err
        val elite = s.field(a, "Safehold Elite") ?: return@runProbe "Elite vanished"
        err = s.settle { s.state.priorityPlayerId == b && s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        err = s.submit(CastSpell(b, s.hand(b, "Lightning Bolt")!!,
            targets = listOf(ChosenTarget.Permanent(elite))))
        if (err != null) return@runProbe err
        err = s.settle { s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        if (s.inGraveyard(a, "Safehold Elite")) return@runProbe "Elite stayed dead (persist missing)"
        val back = s.field(a, "Safehold Elite") ?: return@runProbe "Elite neither yard nor field"
        val counters = s.obs(a).zones.flatMap { it.cards }.firstOrNull {
            it.entityId == back
        }?.counters ?: emptyMap<Any?, Any?>()
        if (counters.isEmpty()) return@runProbe "returned with no counters: $counters"
        if (s.life(a) != 20 || s.life(b) != 20) return@runProbe "life changed: ${s.life(a)}/${s.life(b)}"
        null
    })

    // P5 — layers/arithmetic: Anthem + Growth make Bears 6/6 (projected read).
    results.add(runProbe("P5-layers", "continuous effects + P/T setting",
        "mechanics/layers/StateProjector.kt",
        "Anthem static + Giant Growth on Grizzly Bears") { s ->
        val a = s.pid("A")
        var err = s.developCasting(wants = { pp: EntityId ->
            if (pp == a) {
                when {
                    s.field(a, "Grizzly Bears") == null && s.hand(a, "Grizzly Bears") != null -> "Grizzly Bears"
                    s.field(a, "Glorious Anthem") == null && s.hand(a, "Glorious Anthem") != null -> "Glorious Anthem"
                    else -> null
                }
            } else null
        }) {
            s.field(a, "Grizzly Bears") != null && s.field(a, "Glorious Anthem") != null &&
                s.hand(a, "Giant Growth") != null
        }
        if (err != null) return@runProbe err
        err = s.gotoMain(a); if (err != null) return@runProbe err
        val bears = s.field(a, "Grizzly Bears") ?: return@runProbe "Bears vanished"
        val growth = s.hand(a, "Giant Growth") ?: return@runProbe "no Growth"
        err = s.submit(CastSpell(a, growth, targets = listOf(ChosenTarget.Permanent(bears))))
        if (err != null) return@runProbe err
        err = s.settle { s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        val pt = s.projectedPT(a, "Grizzly Bears") ?: return@runProbe "Bears unreadable"
        if (pt.first != 6 || pt.second != 6) return@runProbe "expected 6/6, got $pt"
        null
    })

    // P6 — copy: Test Token Copy makes a second Goblin Guide.
    results.add(runProbe("P6-copy", "copy effect (token copy)",
        "handlers/effects: CreateTokenCopyOfTargetEffect",
        "B copies A's Goblin Guide") { s ->
        val a = s.pid("A"); val b = s.pid("B")
        var err = s.developCasting(wants = { pp: EntityId ->
            when {
                pp == a && s.field(a, "Goblin Guide") == null -> "Goblin Guide"
                else -> null
            }
        }) {
            s.field(a, "Goblin Guide") != null && s.fieldCount(b, "Island") >= 2 &&
                s.hand(b, "Test Token Copy") != null
        }
        if (err != null) return@runProbe err
        err = s.gotoMain(b); if (err != null) return@runProbe err
        val guide = s.field(a, "Goblin Guide") ?: return@runProbe "Guide vanished"
        val copy = s.hand(b, "Test Token Copy") ?: return@runProbe "no copy spell"
        err = s.submit(CastSpell(b, copy, targets = listOf(ChosenTarget.Permanent(guide))))
        if (err != null) return@runProbe err
        err = s.settle { s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        val guides = s.state.getZone(ZoneKey(a, Zone.BATTLEFIELD)).count {
            s.state.getEntity(it)?.get<CardComponent>()?.name == "Goblin Guide"
        } + s.state.getZone(ZoneKey(b, Zone.BATTLEFIELD)).count {
            s.state.getEntity(it)?.get<CardComponent>()?.name == "Goblin Guide"
        }
        if (guides < 2) return@runProbe "expected >=2 Guides, got $guides"
        null
    })

    // P7 — control change: Act of Treason steals Bears, reverts at EOT.
    results.add(runProbe("P7-control", "control change + EOT revert",
        "handlers/effects/permanent/control/GainControlExecutor.kt",
        "B steals A's Bears, attacks, loses it at EOT") { s ->
        val a = s.pid("A"); val b = s.pid("B")
        var err = s.developCasting(wants = { pp: EntityId -> if (pp == a) "Grizzly Bears" else null }) {
            s.field(a, "Grizzly Bears") != null && s.fieldCount(b, "Mountain") >= 3 &&
                s.hand(b, "Act of Treason") != null
        }
        if (err != null) return@runProbe err
        err = s.gotoMain(b); if (err != null) return@runProbe err
        val bears = s.field(a, "Grizzly Bears") ?: return@runProbe "Bears vanished"
        val treason = s.hand(b, "Act of Treason") ?: return@runProbe "no Treason"
        err = s.submit(CastSpell(b, treason, targets = listOf(ChosenTarget.Permanent(bears))))
        if (err != null) return@runProbe err
        err = s.settle { s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        val ctrl1 = s.projectedController("Grizzly Bears")
        if (ctrl1 != b) return@runProbe "projected controller not B after Treason: ${ctrl1?.value}"
        err = s.settle { s.projectedController("Grizzly Bears") == a }
        if (err != null) return@runProbe "control never reverted: $err"
        null
    })

    // P8 — SBA lethal: Bolted Guide dies by state-based action.
    results.add(runProbe("P8-sba", "state-based actions (lethal damage)",
        "mechanics/StateBasedActionChecker.kt",
        "A Bolts B's Goblin Guide; SBA removes it") { s ->
        val a = s.pid("A"); val b = s.pid("B")
        var err = s.developCasting(wants = { pp: EntityId -> if (pp == b) "Goblin Guide" else null }) {
            s.field(b, "Goblin Guide") != null && s.fieldCount(a, "Mountain") >= 1 &&
                s.hand(a, "Lightning Bolt") != null
        }
        if (err != null) return@runProbe err
        val guide = s.field(b, "Goblin Guide") ?: return@runProbe "Guide vanished"
        err = s.settle { s.state.priorityPlayerId == a && s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        err = s.submit(CastSpell(a, s.hand(a, "Lightning Bolt")!!,
            targets = listOf(ChosenTarget.Permanent(guide))))
        if (err != null) return@runProbe err
        err = s.settle { s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        if (!s.inGraveyard(b, "Goblin Guide")) return@runProbe "Guide not in graveyard"
        if (s.life(b) != 20) return@runProbe "B life moved: ${s.life(b)}"
        null
    })

    // P9 — APNAP/simultaneity: mutual DTTC deaths trigger in APNAP order, both gain 3.
    results.add(runProbe("P9-apnap", "APNAP trigger order + simultaneous death",
        "event/TriggerMatcher.sortByApnapOrder; DeathAndLeaveTriggerDetector",
        "mutual 1/1 deaths; active player's trigger first") { s ->
        val a = s.pid("A"); val b = s.pid("B")
        var err = s.developCasting(wants = { pp: EntityId -> "Death Trigger Test Creature" }) {
            s.field(a, "Death Trigger Test Creature") != null &&
                s.field(b, "Death Trigger Test Creature") != null
        }
        if (err != null) return@runProbe err
        // Fight on A's turn: attack with A's DTTC, block with B's.
        err = s.settle {
            s.state.activePlayerId == a && s.state.step == Step.DECLARE_ATTACKERS &&
                s.state.priorityPlayerId == a && s.state.stack.isEmpty()
        }
        if (err != null) return@runProbe err
        val atk = s.field(a, "Death Trigger Test Creature") ?: return@runProbe "A DTTC gone"
        err = s.submit(DeclareAttackers(a, mapOf(atk to b)))
        if (err != null) return@runProbe err
        err = s.settle {
            s.state.step == Step.DECLARE_BLOCKERS && s.state.priorityPlayerId == b
        }
        if (err != null) return@runProbe err
        val blk = s.field(b, "Death Trigger Test Creature") ?: return@runProbe "B DTTC gone"
        err = s.submit(DeclareBlockers(b, mapOf(blk to listOf(atk))))
        if (err != null) return@runProbe err
        err = s.settle { s.state.stack.isEmpty() && s.inGraveyard(a, "Death Trigger Test Creature") }
        if (err != null) return@runProbe err
        if (!s.inGraveyard(b, "Death Trigger Test Creature")) return@runProbe "B DTTC survived"
        if (s.life(a) != 23 || s.life(b) != 23) return@runProbe "lives ${s.life(a)}/${s.life(b)}, want 23/23"
        null
    })

    // P10 — lethal elimination: Bolt to a 3-life player ends the game.
    results.add(runProbe("P10-lethal", "elimination by lethal damage",
        "mechanics/sba/player/*LossCheck; sba/game/GameEndCheck.kt",
        "B set to 3 life (setup), A Bolts B") { s ->
        val a = s.pid("A"); val b = s.pid("B")
        s.state = s.state.updateEntity(b) { it.with(LifeTotalComponent(3)) }
        var err = s.develop {
            s.fieldCount(a, "Mountain") >= 1 && s.hand(a, "Lightning Bolt") != null
        }
        if (err != null) return@runProbe err
        err = s.gotoMain(a); if (err != null) return@runProbe err
        err = s.submit(CastSpell(a, s.hand(a, "Lightning Bolt")!!,
            targets = listOf(ChosenTarget.Player(b))))
        if (err != null) return@runProbe err
        err = s.settle { s.state.gameOver }
        if (err != null) return@runProbe err
        if (!s.state.gameOver) return@runProbe "game not over"
        if (s.state.winnerId != a) return@runProbe "winner ${s.state.winnerId?.value}, want A"
        null
    })

    // P12 — multi-defender combat: one attacker each at two different players.
    results.add(runProbe("P12-multidef", "multi-defender combat",
        "mechanics/combat/*; DeclareBlockersHandler multi-defender APNAP",
        "A attacks B and C simultaneously; B blocks, C doesn't") { s ->
        val a = s.pid("A"); val b = s.pid("B"); val c = s.pid("C")
        var err = s.developCasting(wants = { pp: EntityId ->
            if (pp == a && s.fieldCount(a, "Grizzly Bears") < 2) "Grizzly Bears" else null
        }) { s.fieldCount(a, "Grizzly Bears") >= 2 }
        if (err != null) return@runProbe err
        val t0 = s.state.turnNumber
        var waited = 0
        while (!(s.state.activePlayerId == a && s.state.step == Step.DECLARE_ATTACKERS &&
            s.state.priorityPlayerId == a && s.state.stack.isEmpty() && s.state.turnNumber > t0)
        ) {
            if (++waited > 250) return@runProbe "multidef-window-cap"
            if (s.state.gameOver) return@runProbe "game-over"
            val pending = s.state.pendingDecision
            if (pending != null) {
                val e2 = s.submit(SubmitDecision(pending.playerId, respond(pending)))
                if (e2 != null) return@runProbe e2
            } else {
                val pp = s.state.priorityPlayerId ?: return@runProbe "no-priority"
                val e2 = s.submit(s.combatDeclareFor(pp) ?: PassPriority(pp))
                if (e2 != null) return@runProbe e2
            }
        }
        val bears = s.state.getZone(ZoneKey(a, Zone.BATTLEFIELD)).filter {
            s.state.getEntity(it)?.get<CardComponent>()?.name == "Grizzly Bears"
        }
        if (bears.size < 2) return@runProbe "only ${bears.size} Bears"
        err = s.submit(DeclareAttackers(a, mapOf(bears[0] to b, bears[1] to c)))
        if (err != null) return@runProbe err
        // B blocks bear0; C blocks nothing.
        err = s.settle {
            s.state.step == Step.DECLARE_BLOCKERS && s.state.priorityPlayerId == b
        }
        if (err != null) return@runProbe err
        val bb = s.state.getZone(ZoneKey(b, Zone.BATTLEFIELD)).firstOrNull {
            s.state.getEntity(it)?.get<CardComponent>()?.typeLine?.isCreature == true
        }
        if (bb != null) {
            err = s.submit(DeclareBlockers(b, mapOf(bb to listOf(bears[0]))))
            if (err != null) return@runProbe err
        } else {
            err = s.submit(DeclareBlockers(b, emptyMap()))
            if (err != null) return@runProbe err
        }
        err = s.settle {
            s.state.step == Step.DECLARE_BLOCKERS && s.state.priorityPlayerId == c
        }
        if (err != null) return@runProbe err
        err = s.submit(DeclareBlockers(c, emptyMap()))
        if (err != null) return@runProbe err
        val lifeB0 = s.life(b); val lifeC0 = s.life(c)
        err = s.settle { s.state.phase != com.wingedsheep.sdk.core.Phase.COMBAT }
        if (err != null) return@runProbe err
        if (s.life(c) != lifeC0 - 2) return@runProbe "C took ${lifeC0 - s.life(c)}, want 2 (unblocked)"
        if (bb != null && s.life(b) != lifeB0) return@runProbe "B took damage through blocker"
        null
    })

    // P13 — hidden-zone choice: crack Evolving Wilds (find + fail-to-find paths).
    results.add(runProbe("P13-search", "library search + fail-to-find",
        "handlers/effects/library/*; SearchLibraryDecision minSelections=0",
        "A cracks Evolving Wilds") { s ->
        val a = s.pid("A")
        var err = s.develop { s.fieldCount(a, "Evolving Wilds") >= 1 }
        if (err != null) return@runProbe err
        err = s.gotoMain(a); if (err != null) return@runProbe err
        val wilds = s.field(a, "Evolving Wilds") ?: return@runProbe "Wilds vanished"
        val offer = s.enumerator.enumerate(s.state, a)
            .firstOrNull { it.action is com.wingedsheep.engine.core.ActivateAbility &&
                (it.action as com.wingedsheep.engine.core.ActivateAbility).sourceId == wilds }
            ?: return@runProbe "no Wilds activation enumerated"
        err = s.submit(offer.action)
        if (err != null) return@runProbe "crack submit: $err"
        // A library-search decision should pause here (as SearchLibraryDecision or,
        // as observed, a SelectCardsDecision over library options).
        val searchKinds = mutableListOf<String>()
        val forests0 = s.fieldCount(a, "Forest")
        repeat(20) {
            val pending = s.state.pendingDecision
            if (pending == null) {
                if (s.state.stack.isEmpty()) return@repeat
                val pp = s.state.priorityPlayerId ?: return@repeat
                val e2 = s.submit(PassPriority(pp))
                if (e2 != null) return@runProbe "pass: $e2"
                return@repeat
            }
            searchKinds.add("${pending::class.simpleName}")
            if (pending is com.wingedsheep.engine.core.SearchLibraryDecision) {
                val forestOpt = pending.options.firstOrNull {
                    s.state.getEntity(it)?.get<CardComponent>()?.name == "Forest"
                }
                val pick = if (forestOpt != null) listOf(forestOpt) else {
                    if (pending.minSelections == 0) emptyList()
                    else pending.options.take(pending.minSelections)
                }
                searchKinds.add("search-pick=${pick.size}-of-${pending.options.size}-min${pending.minSelections}")
                val e2 = s.submit(SubmitDecision(pending.playerId,
                    com.wingedsheep.engine.core.CardsSelectedResponse(pending.id, pick)))
                if (e2 != null) return@runProbe "search answer: $e2"
            } else if (pending is com.wingedsheep.engine.core.SelectCardsDecision) {
                searchKinds.add("select-opts=${pending.options.size}-min${pending.minSelections}-max${pending.maxSelections}")
                val forestOpt = pending.options.firstOrNull {
                    s.state.getEntity(it)?.get<CardComponent>()?.name == "Forest"
                }
                val pick = if (forestOpt != null) listOf(forestOpt) else {
                    if (pending.minSelections == 0) emptyList()
                    else pending.options.take(pending.minSelections)
                }
                searchKinds.add("select-pick=${pick.size}")
                val e2 = s.submit(SubmitDecision(pending.playerId,
                    com.wingedsheep.engine.core.CardsSelectedResponse(pending.id, pick)))
                if (e2 != null) return@runProbe "select answer: $e2"
            } else {
                val e2 = s.submit(SubmitDecision(pending.playerId, respond(pending)))
                if (e2 != null) return@runProbe "other decision: $e2"
            }
        }
        err = s.settle { s.state.stack.isEmpty() && s.state.pendingDecision == null }
        if (err != null) return@runProbe err
        if (searchKinds.isEmpty()) return@runProbe "no search/select decision seen"
        if (!s.inGraveyard(a, "Evolving Wilds")) return@runProbe "Wilds not sacrificed: $searchKinds"
        val forests1 = s.fieldCount(a, "Forest")
        if (forests1 != forests0 + 1) return@runProbe "Forest count $forests0->$forests1, want +1: $searchKinds"
        s.decisions.addAll(searchKinds)
        null
    })

    // P11 — Commander: cast from zone, 903.9a choice, tax, commander damage.
    results.add(runProbe("P11-commander", "commander cast/zone-choice/tax/damage",
        "core/GameInitializer.kt; mechanics/sba/permanent/CommanderZoneChoiceCheck.kt; mechanics/mana/CostCalculator.kt(calculateCommanderTax); mechanics/combat/CombatDamageManager.kt(accumulateCommanderDamage)",
        "1v1 Commander: cast Prospector, Bolt it, divert to command, recast with tax, hit for damage") { s ->
        val a = s.pid("A"); val b = s.pid("B")
        val cmdA0 = s.state.getZone(ZoneKey(a, Zone.COMMAND)).singleOrNull()
            ?: return@runProbe "no commander in A's command zone"
        var err = s.develop { s.fieldCount(a, "Mountain") >= 1 }
        if (err != null) return@runProbe err
        err = s.gotoMain(a); if (err != null) return@runProbe err
        val cmdA = s.state.getZone(ZoneKey(a, Zone.COMMAND)).singleOrNull()
            ?: return@runProbe "commander left zone early"
        err = s.submit(CastSpell(a, cmdA))
        if (err != null) return@runProbe "commander cast: $err"
        err = s.settle { s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        val pro1 = s.field(a, "Test Hasty Prospector") ?: return@runProbe "Prospector not on field"
        // B Bolts it (needs R + Bolt).
        err = s.develop { s.fieldCount(b, "Mountain") >= 1 && s.hand(b, "Lightning Bolt") != null }
        if (err != null) return@runProbe err
        err = s.settle { s.state.priorityPlayerId == b && s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        err = s.submit(CastSpell(b, s.hand(b, "Lightning Bolt")!!,
            targets = listOf(ChosenTarget.Permanent(pro1))))
        if (err != null) return@runProbe err
        // Expect the 903.9a zone choice; answer YES (divert to command).
        var sawChoice = false
        repeat(20) {
            val pending = s.state.pendingDecision
            if (pending == null) {
                if (s.state.stack.isEmpty()) return@repeat
                val pp = s.state.priorityPlayerId ?: return@repeat
                s.submit(PassPriority(pp)); return@repeat
            }
            if (pending is com.wingedsheep.engine.core.YesNoDecision) {
                sawChoice = true
                s.decisions.add("CommanderZoneChoice@${pending.playerId.value}:${pending.prompt.take(80)}")
                val e2 = s.submit(SubmitDecision(pending.playerId,
                    com.wingedsheep.engine.core.YesNoResponse(pending.id, true)))
                if (e2 != null) return@runProbe "choice answer: $e2"
            } else {
                val e2 = s.submit(SubmitDecision(pending.playerId, respond(pending)))
                if (e2 != null) return@runProbe "other decision: $e2"
            }
        }
        if (!sawChoice) return@runProbe "no 903.9a zone choice raised"
        err = s.settle { s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        val cmdBack = s.state.getZone(ZoneKey(a, Zone.COMMAND)).singleOrNull()
            ?: return@runProbe "Prospector not diverted to command zone"
        // Recast with tax: needs R+2. Develop to 3 Mountains, then cast.
        err = s.develop { s.fieldCount(a, "Mountain") >= 3 }
        if (err != null) return@runProbe err
        err = s.gotoMain(a); if (err != null) return@runProbe err
        err = s.submit(CastSpell(a, cmdBack))
        if (err != null) return@runProbe "taxed recast failed: $err"
        err = s.settle { s.state.stack.isEmpty() }
        if (err != null) return@runProbe err
        val pro2 = s.field(a, "Test Hasty Prospector") ?: return@runProbe "recast Prospector missing"
        val tapped = s.state.getZone(ZoneKey(a, Zone.BATTLEFIELD)).count {
            s.state.getEntity(it)?.get<CardComponent>()?.name == "Mountain" &&
                s.state.getEntity(it)?.has<com.wingedsheep.engine.state.components.battlefield.TappedComponent>() == true
        }
        if (tapped < 3) return@runProbe "tax not charged: only $tapped Mountains tapped for recast"
        // Commander damage: attack B with it (haste), expect 2 tracked.
        err = s.settle {
            s.state.activePlayerId == a && s.state.step == Step.DECLARE_ATTACKERS &&
                s.state.priorityPlayerId == a && s.state.stack.isEmpty()
        }
        if (err != null) return@runProbe err
        // summoning sickness? Prospector has haste; recast this turn is fine.
        err = s.submit(DeclareAttackers(a, mapOf(pro2 to b)))
        if (err != null) return@runProbe "attack: $err"
        err = s.settle { s.state.phase != com.wingedsheep.sdk.core.Phase.COMBAT }
        if (err != null) return@runProbe err
        val dmg = s.state.commanderDamageOf(pro2, b)
        if (dmg != 2) return@runProbe "commander damage $dmg, want 2"
        null
    })

    writeResults(outPath, results)
}

fun Script.manaSources(p: EntityId): Int =
    state.getZone(ZoneKey(p, Zone.BATTLEFIELD)).count {
        state.getEntity(it)?.get<CardComponent>()?.name == "Forest" ||
            state.getEntity(it)?.get<CardComponent>()?.name == "Mountain" ||
            state.getEntity(it)?.get<CardComponent>()?.name == "Island" ||
            state.getEntity(it)?.get<CardComponent>()?.name == "Plains" ||
            state.getEntity(it)?.get<CardComponent>()?.name == "Swamp"
    }

/** Advance to seat [p]'s precombat main with priority and empty stack (bounded). */
fun Script.gotoMain(p: EntityId): String? {
    repeat(120) {
        if (state.gameOver) return "game-over"
        if (state.priorityPlayerId == p && state.activePlayerId == p &&
            state.phase == com.wingedsheep.sdk.core.Phase.PRECOMBAT_MAIN && state.stack.isEmpty() &&
            state.pendingDecision == null
        ) return null
        val pending = state.pendingDecision
        if (pending != null) {
            val err = submit(SubmitDecision(pending.playerId, respond(pending)))
            if (err != null) return err
        } else {
            val pp = state.priorityPlayerId ?: return "no-priority"
            val a = combatDeclareFor(pp) ?: PassPriority(pp)
            val err = submit(a)
            if (err != null) return err
        }
    }
    return "gotoMain-cap"
}

fun Script.combatDeclareFor(pp: EntityId): GameAction? {
    if (state.step == Step.DECLARE_ATTACKERS && pp == state.activePlayerId) {
        if (state.getEntity(pp)?.has<com.wingedsheep.engine.state.components.combat.AttackersDeclaredThisCombatComponent>() == true) return null
        return DeclareAttackers(pp, emptyMap())
    }
    if (state.step == Step.DECLARE_BLOCKERS && pp != state.activePlayerId) {
        if (state.getEntity(pp)?.has<com.wingedsheep.engine.state.components.combat.BlockersDeclaredThisCombatComponent>() == true) return null
        return DeclareBlockers(pp, emptyMap())
    }
    return null
}

/** Pass turns until seat [p] holds [land] in hand (bounded by turn cap). */
fun Script.waitReady(p: EntityId, land: String, minTurns: Int): String? {
    repeat(200) {
        if (state.gameOver) return "game-over"
        if (hand(p, land) != null && state.turnNumber >= minTurns) return null
        if (state.turnNumber > 12) return "waitReady-cap"
        val pending = state.pendingDecision
        if (pending != null) {
            val err = submit(SubmitDecision(pending.playerId, respond(pending)))
            if (err != null) return err
        } else {
            val pp = state.priorityPlayerId ?: return "no-priority"
            val a = combatDeclareFor(pp) ?: PassPriority(pp)
            val err = submit(a)
            if (err != null) return err
        }
    }
    return "waitReady-cap"
}

fun writeResults(outPath: String, results: List<ProbeResult>) {
    val root = jo(
        "probe" to "U1 rules-dense probes (part 1)",
        "candidate" to jo("head" to CANDIDATE_HEAD, "tree" to CANDIDATE_TREE),
        "evidenceClass" to "DIRECTLY_VERIFIED behavior; never EXTERNALLY_RULE_VALIDATED",
        "probes" to results.map { r ->
            jo("id" to r.id, "mechanic" to r.mechanic, "source" to r.source,
                "setup" to r.setup, "decisions" to r.decisions,
                "lastSubmissions" to r.submitted, "pass" to r.pass, "detail" to r.detail)
        },
        "passCount" to results.count { it.pass },
        "probeCount" to results.size,
    )
    writeJson(outPath, root)
    println("wrote $outPath ${results.count { it.pass }}/${results.size}")
    for (r in results) println("${r.id}: ${if (r.pass) "PASS" else "FAIL"} ${r.detail.take(160)}")
}
