package rqa2

import com.wingedsheep.engine.core.CastSpell
import com.wingedsheep.engine.core.DecisionContext
import com.wingedsheep.engine.core.DecisionPhase
import com.wingedsheep.engine.core.GameEvent
import com.wingedsheep.engine.core.PassPriority
import com.wingedsheep.engine.core.PaymentStrategy
import com.wingedsheep.engine.core.SubmitDecision
import com.wingedsheep.engine.core.YesNoDecision
import com.wingedsheep.engine.core.YesNoResponse
import com.wingedsheep.engine.state.GameState
import com.wingedsheep.engine.state.ZoneKey
import com.wingedsheep.engine.state.components.identity.CardComponent
import com.wingedsheep.engine.state.components.identity.ControllerComponent
import com.wingedsheep.engine.state.components.identity.FaceDownComponent
import com.wingedsheep.engine.state.components.identity.MayLookAtInExileComponent
import com.wingedsheep.engine.state.components.identity.OwnerComponent
import com.wingedsheep.engine.state.components.identity.RevealedToComponent
import com.wingedsheep.engine.state.components.player.ManaPoolComponent
import com.wingedsheep.engine.view.ClientEventTransformer
import com.wingedsheep.engine.view.ClientGameState
import com.wingedsheep.engine.view.ClientStateTransformer
import com.wingedsheep.engine.view.Visibility
import com.wingedsheep.gameserver.session.DecisionEnricher
import com.wingedsheep.gameserver.session.SpectatorSeat
import com.wingedsheep.gameserver.session.SpectatorStateBuilder
import com.wingedsheep.gym.GameEnvironment
import com.wingedsheep.gym.GameGymEnv
import com.wingedsheep.gym.contract.ObservationBuilder
import com.wingedsheep.gym.contract.TrainingObservation
import com.wingedsheep.sdk.core.Format
import com.wingedsheep.sdk.core.Zone
import com.wingedsheep.sdk.model.Deck
import com.wingedsheep.sdk.model.EntityId

// U16 — live principal-scoped no-leak qualification (CPL-side external driver).
//
// 4-player Commander pod with unique per-seat sentinel cards. For every viewer,
// the engine Visibility authority is queried per (card, viewer) and checked
// against three independent projection surfaces (managed Gym observation,
// server ClientState DTO, spectator DTO), plus decision enrichment, event
// projection, and error strings. The detector is proven non-vacuous by running
// it against the revealAll debug backdoor (must FLAG).

val SENTINELS = listOf("Centaur Courser", "Force of Nature", "Goblin Guide", "Savannah Lions")

fun podDecks(): List<Pair<String, Deck>> = SENTINELS.mapIndexed { i, s ->
    "P$i" to Deck.of("Forest" to 95, s to 2, "Morph Test Creature" to 2)
}

fun trueName(state: GameState, eid: EntityId): String? =
    state.getEntity(eid)?.get<CardComponent>()?.name

fun main(args: Array<String>) {
    val outPath = args.getOrNull(0)
        ?: "/home/moeen/code/rq-a2-argentum-comparable-qualification/research/candidate-qualification/argentum/rq-a2/evidence/ARGENTUM_HIDDEN_INFO_ADVERSARY.json"
    val registry = newRegistry()
    val visibility = Visibility(registry)
    val obsBuilder = ObservationBuilder(registry)
    val transformer = ClientStateTransformer(registry)
    val enricher = DecisionEnricher(registry)
    val spectatorBuilder = SpectatorStateBuilder(registry, transformer)
    val processor = newProcessor(registry)
    val enumerator = newEnumerator(registry)

    // --- Setup: 4P Commander pod, fixed seed, live play ---
    val commanders = List(4) { "Test Hasty Prospector" }
    val decks = podDecks()
    val init = PodInit2(registry, decks, commanders, 5001L)
    var state = init.state
    val seats: List<EntityId> = init.playerIds
    val actions = mutableListOf<com.wingedsheep.engine.core.GameAction>()
    val liveEvents = mutableListOf<GameEvent>()
    val skipped = mutableListOf<String>()
    repeat(120) {
        if (state.gameOver) return@repeat
        if (state.turnNumber > 6) return@repeat
        val pending = state.pendingDecision
        if (pending != null) {
            val a = SubmitDecision(pending.playerId, respond(pending))
            val r = processor.process(state, a).result
            if (r.error != null || (!r.isSuccess && !r.isPaused)) return@repeat
            state = r.newState; actions.add(a); liveEvents.addAll(r.events); return@repeat
        }
        val pp = state.priorityPlayerId ?: return@repeat
        val a = chooseAction(state, pp, enumerator, skipped) ?: PassPriority(pp)
        val r = processor.process(state, a).result
        if (r.error != null || (!r.isSuccess && !r.isPaused)) return@repeat
        state = r.newState; actions.add(a); liveEvents.addAll(r.events)
    }

    // --- Planted scenario state (setup, not replay inputs): ---
    var s = state
    val p0 = seats[0]; val p1 = seats[1]; val p2 = seats[2]; val p3 = seats[3]
    val morphLog = mutableListOf<String>()
    var morphId = s.getZone(ZoneKey(p0, Zone.HAND)).firstOrNull {
        trueName(s, it) == "Morph Test Creature"
    }
    if (morphId == null) {
        val (ns, id) = mintCardInHand(registry, s, p0, "Morph Test Creature")
        s = ns; morphId = id
        morphLog.add("minted $id")
    } else morphLog.add("found $morphId")
    // Wait for a clean P0 sorcery-speed window, then file the face-down cast.
    var waited = 0
    var castDone = false
    while (!castDone && waited < 120) {
        waited++
        val pending = s.pendingDecision
        if (pending != null) {
            val r = processor.process(s, SubmitDecision(pending.playerId, respond(pending))).result
            if (r.error == null && (r.isSuccess || r.isPaused)) s = r.newState else break
            continue
        }
        val pp = s.priorityPlayerId ?: break
        val sorcerySpeed = pp == p0 && s.activePlayerId == p0 && s.stack.isEmpty() &&
            (s.phase == com.wingedsheep.sdk.core.Phase.PRECOMBAT_MAIN ||
                s.phase == com.wingedsheep.sdk.core.Phase.POSTCOMBAT_MAIN)
        if (sorcerySpeed && morphId in s.getZone(ZoneKey(p0, Zone.HAND))) {
            // Top up in the same breath: pools empty across phases.
            s = s.updateEntity(p0) { c ->
                c.with((c.get<ManaPoolComponent>() ?: ManaPoolComponent()).addColorless(3))
            }
            val r = processor.process(s, CastSpell(p0, morphId!!,
                paymentStrategy = PaymentStrategy.FromPool, castFaceDown = true)).result
            morphLog.add("cast: success=${r.isSuccess} paused=${r.isPaused} error=${r.error}")
            if (r.error == null && (r.isSuccess || r.isPaused)) { s = r.newState; castDone = true }
            else break
        } else {
            val r = processor.process(s, PassPriority(pp)).result
            if (r.error == null && (r.isSuccess || r.isPaused)) s = r.newState else break
        }
    }
    morphLog.add("waited=$waited castDone=$castDone")
    repeat(30) {
        val pending = s.pendingDecision
        if (pending != null) {
            val r = processor.process(s, SubmitDecision(pending.playerId, respond(pending))).result
            if (r.error == null && (r.isSuccess || r.isPaused)) s = r.newState else return@repeat
        } else {
            val pp = s.priorityPlayerId ?: return@repeat
            val r = processor.process(s, PassPriority(pp)).result
            if (r.error == null && (r.isSuccess || r.isPaused)) s = r.newState else return@repeat
        }
    }
    val faceDownIds = s.getZone(ZoneKey(p0, Zone.BATTLEFIELD)).filter {
        s.getEntity(it)?.has<FaceDownComponent>() == true
    }
    morphLog.add("faceDownOnBattlefield=$faceDownIds")
    // (b) temporary reveal: reveal one P0 hand card to P1 only.
    val revealTarget = s.getZone(ZoneKey(p0, Zone.HAND)).firstOrNull()
    if (revealTarget != null) {
        s = s.updateEntity(revealTarget) { c ->
            c.with((c.get<RevealedToComponent>() ?: RevealedToComponent(emptySet())).withPlayer(p1))
        }
    }
    // (c) hidden exile with a look grant for P3 only.
    val exileTarget = s.getZone(ZoneKey(p2, Zone.HAND)).firstOrNull()
    var exiledId: EntityId? = null
    if (exileTarget != null) {
        s = s.removeFromZone(ZoneKey(p2, Zone.HAND), exileTarget)
        s = s.updateEntity(exileTarget) { c ->
            c.with(FaceDownComponent).with(MayLookAtInExileComponent.to(p3))
        }
        s = s.addToZone(ZoneKey(p2, Zone.EXILE), exileTarget)
        exiledId = exileTarget
    }
    state = s
    val fState = state

    fun authority(zoneKey: ZoneKey, eid: EntityId, viewer: EntityId, spectator: Boolean = false): Boolean =
        visibility.isCardIdentityVisibleTo(fState, zoneKey, eid, viewer, spectator)

    // --- Check 1: managed Gym observations, structural, true-name based ---
    fun checkGymObs(obs: TrainingObservation, viewer: EntityId): Pair<List<String>, List<String>> {
        val leaks = mutableListOf<String>()
        val overmasks = mutableListOf<String>()
        val listed = obs.zones.associate { (it.ownerId to it.zoneType) to it.cards.associate { c -> c.entityId to c.name } }
        for (zv in obs.zones) {
            for (card in zv.cards) {
                val key = ZoneKey(zv.ownerId, zv.zoneType)
                val vis = authority(key, card.entityId, viewer)
                val truth = trueName(fState, card.entityId)
                if (!vis && card.name == truth) leaks.add("LEAK ${card.entityId.value} true-name '$truth' in ${zv.ownerId.value}/${zv.zoneType} to ${viewer.value}")
            }
        }
        for ((key, ids) in fState.zones) {
            val shown = listed[key.ownerId to key.zoneType] ?: emptyMap()
            for (eid in ids) {
                val vis = authority(key, eid, viewer)
                val truth = trueName(fState, eid)
                if (vis) {
                    val shownName = shown[eid]
                    if (shownName == null) overmasks.add("OVERMASK ${eid.value} '$truth' unlisted in ${key.ownerId.value}/${key.zoneType} to ${viewer.value}")
                    else if (shownName != truth) overmasks.add("OVERMASK ${eid.value} shown-as '$shownName' want '$truth' to ${viewer.value}")
                }
            }
        }
        for (item in obs.stack) {
            val vis = visibility.isCardIdentityVisibleTo(fState, Zone.STACK, item.entityId, viewer)
            val truth = trueName(fState, item.entityId)
            if (!vis && item.name == truth) leaks.add("LEAK stack ${item.entityId.value} '$truth' to ${viewer.value}")
        }
        return leaks to overmasks
    }

    // --- Check 2: server ClientState DTO, structural ---
    // A hidden entity may have NO card entry (hand/library) or a MASKED entry
    // (face-down in a public zone: generic name, blanked stats/text, helper art).
    // A true-name entry for a hidden entity is a leak; so is a revealedName
    // disclosed to a viewer without the grant.
    fun checkDto(dto: ClientGameState, viewer: EntityId, spectator: Boolean): List<String> {
        val leaks = mutableListOf<String>()
        val where = if (spectator) " (spectator)" else ""
        for ((key, ids) in fState.zones) {
            for (eid in ids) {
                val vis = visibility.isCardIdentityVisibleTo(fState, key, eid, viewer, spectator)
                if (vis) continue
                val entry = dto.cards[eid] ?: continue
                val truth = trueName(fState, eid)
                if (key.zoneType == Zone.HAND || key.zoneType == Zone.LIBRARY) {
                    leaks.add("DTO-LEAK hidden-zone entry ${eid.value} '$truth' in ${key.ownerId.value}/${key.zoneType} to ${viewer.value}$where")
                } else if (entry.name == truth) {
                    leaks.add("DTO-LEAK true-name ${eid.value} '$truth' in ${key.ownerId.value}/${key.zoneType} to ${viewer.value}$where")
                }
                if (entry.revealedName != null && entry.revealedName == truth) {
                    leaks.add("DTO-LEAK revealedName ${eid.value} '$truth' to ${viewer.value}$where (no grant)")
                }
            }
        }
        // own-deck-only decklist
        val ownedNames = fState.entities.keys
            .filter { fState.getEntity(it)?.get<OwnerComponent>()?.playerId == viewer }
            .mapNotNull { trueName(fState, it) }.toSet()
        for (entry in dto.deck) {
            if (entry.cardName !in ownedNames) leaks.add("DTO-DECK-LEAK '${entry.cardName}' in ${viewer.value} decklist")
        }
        if (spectator && dto.deck.isNotEmpty()) leaks.add("DTO-DECK-NONEMPTY-FOR-SPECTATOR")
        return leaks
    }

    // --- Check 3: projected client events, name-level vs current hidden zones ---
    val nameRe = Regex("cardName=([^,\\)]+)")
    fun checkEvents(projected: String, viewer: EntityId): List<String> {
        val leaks = mutableListOf<String>()
        val named = nameRe.findAll(projected).map { it.groupValues[1] }.toSet()
        for (n in named) {
            if (n == "null") continue
            // A name is a leak only if it belongs to a card CURRENTLY hidden from this viewer
            // (hands/libraries of others, ungranted face-down). Public-zone cards are fine.
            var hiddenOwner: String? = null
            for ((key, ids) in fState.zones) {
                if (key.zoneType != Zone.HAND && key.zoneType != Zone.LIBRARY) continue
                if (key.ownerId == viewer) continue
                if (ids.any { trueName(fState, it) == n }) { hiddenOwner = key.ownerId.value; break }
            }
            // face-down hidden identities
            if (hiddenOwner == null) {
                outer@ for ((key, ids) in fState.zones) {
                    for (eid in ids) {
                        if (trueName(fState, eid) == n &&
                            !visibility.isCardIdentityVisibleTo(fState, key, eid, viewer)
                        ) { hiddenOwner = "facedown@${key.ownerId.value}/${key.zoneType}"; break@outer }
                    }
                }
            }
            if (hiddenOwner != null) leaks.add("EVENT-LEAK '$n' (hidden: $hiddenOwner) in ${viewer.value} stream")
        }
        return leaks
    }

    val perViewer = mutableListOf<Any?>()
    val dtoFindings = mutableListOf<Any?>()
    val eventFindings = mutableListOf<Any?>()
    var totalLeaks = 0
    for (v in seats) {
        val legal = if (fState.pendingDecision == null && fState.priorityPlayerId == v && !fState.gameOver)
            enumerator.enumerate(fState, v) else emptyList()
        val obs = obsBuilder.build(fState, v, legal).observation as TrainingObservation
        val (leaks, overmasks) = checkGymObs(obs, v)
        constrainLegalOptions(legal, fState, visibility, v, leaks as MutableList<String>)
        val dto = transformer.transform(fState, v, isSpectator = false)
        val dtoLeaks = checkDto(dto, v, spectator = false)
        // Project the FULL live event stream (draws, moves, combat) per viewer.
        val evText = ClientEventTransformer.transform(liveEvents, v).toString()
        val evLeaks = checkEvents(evText, v)
        totalLeaks += leaks.size + dtoLeaks.size + evLeaks.size
        perViewer.add(jo("viewer" to v.value, "gymLeaks" to leaks, "gymOvermasks" to overmasks,
            "legalActionCount" to legal.size))
        dtoFindings.add(jo("viewer" to v.value, "dtoLeaks" to dtoLeaks))
        eventFindings.add(jo("viewer" to v.value, "eventLeaks" to evLeaks,
            "liveEventKinds" to liveEvents.mapNotNull { it::class.simpleName }.distinct().sorted(),
            "projectedSample" to evText.take(1500)))
    }

    // --- Planted-leak controls: revealAll MUST trip the gym detector ---
    val controlHits = mutableListOf<Any?>()
    for (v in seats) {
        val obsAll = obsBuilder.build(fState, v, emptyList(), revealAll = true).observation as TrainingObservation
        val (leaksAll, _) = checkGymObs(obsAll, v)
        controlHits.add(jo("viewer" to v.value, "revealAllLeakFindings" to leaksAll.size,
            "detectorFires" to leaksAll.isNotEmpty(), "sample" to leaksAll.take(3)))
    }

    // --- Spectator DTO: both hands masked ---
    val roster = seats.mapIndexed { i, pid ->
        com.wingedsheep.gameserver.protocol.ServerMessage.PlayerSeatInfo(pid.value, "P$i", i)
    }
    val specSeats = seats.mapIndexed { i, pid -> SpectatorSeat(pid, "P$i") }
    val specUpdate = spectatorBuilder.buildState(fState, specSeats, roster, "rq-a2-h1")
    val specDto = specUpdate.gameState
    val specLeaks = if (specDto == null) listOf("NO-GAMESTATE-IN-SPECTATOR-UPDATE")
    else checkDto(specDto, seats[0], spectator = true)

    // --- Decisions: live pending if any, plus synthetic option-bearing decisions ---
    val livePending = fState.pendingDecision
    val probeDecision = livePending ?: YesNoDecision(
        id = "r-probe-1", playerId = p0, prompt = "probe",
        context = DecisionContext(phase = DecisionPhase.RESOLUTION),
    )
    val actorView = enricher.enrich(probeDecision, fState, probeDecision.playerId).toString()
    val otherView = enricher.enrich(probeDecision, fState, seats.first { it != probeDecision.playerId }).toString()
    // Synthetic SelectCards addressed to P0 over P0's own hand (hidden from others),
    // WITH cardInfo (what a real search/select carries). Non-actors never receive
    // enrich() output in production (they get OpponentDecisionStatus), so assert on
    // that path; the actor must still see its own options.
    val decisionPayloadLeaks = mutableListOf<String>()
    run {
        val p0hand = fState.getZone(ZoneKey(p0, Zone.HAND))
        val p0handNames = p0hand.mapNotNull { trueName(fState, it) }.toSet()
        val info = p0hand.associateWith { eid ->
            com.wingedsheep.engine.core.SearchCardInfo(
                name = trueName(fState, eid) ?: "?", manaCost = "", typeLine = "")
        }
        val select = com.wingedsheep.engine.core.SelectCardsDecision(
            id = "r-probe-select", playerId = p0, prompt = "probe select",
            context = DecisionContext(phase = DecisionPhase.RESOLUTION),
            options = p0hand, minSelections = 1, maxSelections = 1,
            cardInfo = info,
        )
        for (v in seats) {
            if (v == p0) continue
            val status = enricher.createOpponentDecisionStatus(select, fState, v).toString()
            for (n in p0handNames) {
                if (n.length > 3 && n in status) {
                    decisionPayloadLeaks.add("DECISION-LEAK status '$n' (P0 hand) to ${v.value}")
                }
            }
        }
        // Actor must still see its own options.
        val actorText = enricher.enrich(select, fState, p0).toString()
        if (p0hand.isNotEmpty() && p0handNames.none { it in actorText }) {
            decisionPayloadLeaks.add("DECISION-OVERMASK actor P0 cannot see own SelectCards options")
        }
    }
    totalLeaks += decisionPayloadLeaks.size

    // --- Errors on copies ---
    val errorRows = mutableListOf<Any?>()
    run {
        val errs = mutableListOf<String>()
        val holder = fState.priorityPlayerId
        val other = seats.firstOrNull { it != holder }
        if (holder != null && other != null) {
            errs.add(processor.process(fState, PassPriority(other)).result.error ?: "no-error")
        }
        errs.add(processor.process(fState, SubmitDecision(p0, YesNoResponse("fabricated-id", true))).result.error ?: "no-error")
        val cid = fState.getZone(ZoneKey(p1, Zone.HAND)).firstOrNull()
        if (cid != null) {
            errs.add(processor.process(fState, CastSpell(p1, cid)).result.error ?: "no-error")
        }
        val hiddenNames = seats.flatMap { pid ->
            (fState.getZone(ZoneKey(pid, Zone.HAND)) + fState.getZone(ZoneKey(pid, Zone.LIBRARY)))
                .mapNotNull { trueName(fState, it) }
        }.toSet()
        val leaked = errs.filter { e -> hiddenNames.any { n -> n.length > 3 && n in e } }
        totalLeaks += leaked.size
        errorRows.add(jo("errors" to errs, "hiddenNameLeaks" to leaked))
    }

    // --- Positive MUST-SEE assertions (failures recorded as POSITIVE-GAP) ---
    val positives = mutableListOf<String>()
    fun mustSee(viewer: EntityId, eid: EntityId, why: String) {
        val key = fState.zones.entries.firstOrNull { eid in it.value }?.key
        val obs = obsBuilder.build(fState, viewer, emptyList()).observation as TrainingObservation
        val shown = obs.zones.flatMap { it.cards }.associate { it.entityId to it.name }
        val truth = key?.let { trueName(fState, eid) }
        if (key == null || truth == null) positives.add("POSITIVE-GAP $why: entity vanished")
        else if (!visibility.isCardIdentityVisibleTo(fState, key, eid, viewer))
            positives.add("POSITIVE-GAP $why: authority says hidden (setup wrong?)")
        else if (shown[eid] != truth)
            positives.add("POSITIVE-GAP $why: authority-visible but shown as '${shown[eid]}'")
    }
    // own hands visible
    for (v in seats) {
        fState.getZone(ZoneKey(v, Zone.HAND)).take(2).forEach { mustSee(v, it, "own-hand $v") }
    }
    // revealed card visible to grantee
    if (revealTarget != null) mustSee(p1, revealTarget, "revealed-to-P1")
    // exiled card visible to look-grant holder
    if (exiledId != null) mustSee(p3, exiledId, "exile-look-grant-P3")
    // face-down permanents visible (as masked) to controller is NOT required; controller
    // sees through own morph? Record what the controller sees without asserting either way.
    val positivesFailed = positives.filter { it.startsWith("POSITIVE-GAP") }

    // --- Gym topology (sentinels planted into hands via restore; structural) ---
    val topo = mutableMapOf<String, Any?>()
    run {
        val topoDecks = SENTINELS.mapIndexed { i, s -> "T$i" to Deck.of("Forest" to 98, s to 1) }
        val env = GameEnvironment.create(registry)
        val gymEnv = GameGymEnv(env, 0, false)
        gymEnv.reset(com.wingedsheep.engine.core.GameConfig(
            players = topoDecks.mapIndexed { i, (n, d) ->
                com.wingedsheep.engine.core.PlayerConfig(n, d, 40,
                    playerId = EntityId.of("rq-a2-topo-p$i"), commanderCardName = commanders[i])
            },
            skipMulligans = true,
            format = Format.Commander(),
            seed = 5001L,
        ))
        // Plant each seat's sentinel into its hand deterministically (setup surgery).
        var planted = env.state
        val perspective = env.playerIds[0]
        for (pid in env.playerIds) {
            val idx = env.playerIds.indexOf(pid)
            val want = SENTINELS[idx]
            val eid = planted.entities.keys.firstOrNull { trueName(planted, it) == want }
                ?: continue
            val from = planted.zones.entries.firstOrNull { eid in it.value }?.key ?: continue
            if (from.zoneType == Zone.HAND && from.ownerId == pid) continue
            planted = planted.removeFromZone(from, eid)
            planted = planted.addToZone(ZoneKey(pid, Zone.HAND), eid)
        }
        env.restore(planted, env.playerIds)
        val envSeats = env.state.turnOrder
        val opponents = envSeats.filter { it != perspective }
        // Raw in-process state: opponent sentinel identities recoverable?
        val rawHits = mutableListOf<String>()
        for (pid in opponents) {
            for (eid in env.state.getZone(ZoneKey(pid, Zone.HAND))) {
                val n = trueName(env.state, eid)
                if (n != null && n != "Forest") rawHits.add("$n@${pid.value}")
            }
        }
        // Managed observation for the perspective seat: opponent sentinel identities listed?
        val obsP = env.playerIds[0]
        val obs0 = ObservationBuilder(registry).build(env.state, obsP, emptyList()).observation as TrainingObservation
        val listedNames = obs0.zones.flatMap { it.cards }.map { it.name }.toSet()
        val obsHits = mutableListOf<String>()
        for (pid in opponents) {
            for (eid in env.state.getZone(ZoneKey(pid, Zone.HAND))) {
                val n = trueName(env.state, eid)
                if (n != null && n != "Forest" && n in listedNames) obsHits.add("$n@${pid.value}")
            }
        }
        topo["perspective"] = perspective.value
        topo["envSeats"] = envSeats.map { it.value }
        topo["rawStateExposesOpponentSentinels"] = rawHits
        topo["managedObserveExposesOpponentSentinels"] = obsHits
        topo["caveatDemonstrated"] = rawHits.isNotEmpty() && obsHits.isEmpty()
    }

    totalLeaks += specLeaks.size
    val root = jo(
        "probe" to "U16 hidden-information adversary",
        "candidate" to jo("head" to CANDIDATE_HEAD, "tree" to CANDIDATE_TREE),
        "setup" to jo(
            "mode" to "4-player Commander pod, seed 5001, live play + planted face-down/reveal/exile",
            "actionsPlayed" to actions.size,
            "morphLog" to morphLog,
            "faceDownBattlefield" to faceDownIds.map { it.value },
            "revealedToP1" to revealTarget?.value,
            "revealedName" to revealTarget?.let { trueName(fState, it) },
            "hiddenExile" to exiledId?.value,
            "exiledName" to exiledId?.let { trueName(fState, it) },
        ),
        "perViewer" to perViewer,
        "plantedLeakControls" to controlHits,
        "dtoChecks" to dtoFindings,
        "spectatorLeaks" to specLeaks,
        "decisionEnrichment" to jo(
            "livePendingWas" to (livePending?.let { it::class.simpleName + "@" + it.playerId.value }),
            "actorVsOtherDiffer" to (actorView != otherView),
            "payloadLeaks" to decisionPayloadLeaks,
        ),
        "eventChecks" to eventFindings,
        "errorChecks" to errorRows,
        "positiveAssertions" to jo("gaps" to positivesFailed, "gapCount" to positivesFailed.size),
        "gymTopology" to topo,
        "totalLeakFindings" to totalLeaks,
    )
    writeJson(outPath, root)
    println("wrote $outPath totalLeaks=$totalLeaks positiveGaps=${positivesFailed.size}")
}

fun constrainLegalOptions(
    legal: List<com.wingedsheep.engine.legalactions.LegalAction>,
    state: GameState,
    visibility: Visibility,
    viewer: EntityId,
    leaks: MutableList<String>,
) {
    val text = legal.toString()
    for ((key, ids) in state.zones) {
        for (eid in ids) {
            if (visibility.isCardIdentityVisibleTo(state, key, eid, viewer)) continue
            val name = trueName(state, eid) ?: continue
            if (name.length > 3 && name in text) leaks.add("LEGAL-OPTION-LEAK '$name' to ${viewer.value}")
        }
    }
}

data class PodInit(val state: GameState, val playerIds: List<EntityId>)

fun PodInit2(
    registry: com.wingedsheep.engine.registry.CardRegistry,
    decks: List<Pair<String, Deck>>,
    commanders: List<String>,
    seed: Long,
): PodInit {
    val r = com.wingedsheep.engine.core.GameInitializer(registry).initializeGame(
        com.wingedsheep.engine.core.GameConfig(
            players = decks.mapIndexed { i, (n, d) ->
                com.wingedsheep.engine.core.PlayerConfig(n, d, 40,
                    playerId = EntityId.of("rq-a2-h1-p$i"), commanderCardName = commanders[i])
            },
            skipMulligans = true,
            format = Format.Commander(),
            seed = seed,
        )
    )
    return PodInit(r.state, r.playerIds)
}

fun mintCardInHand(
    registry: com.wingedsheep.engine.registry.CardRegistry,
    state: GameState,
    pid: EntityId,
    name: String,
): Pair<GameState, EntityId> {
    val def = registry.requireCard(name)
    val id = EntityId.generate()
    var c = com.wingedsheep.engine.state.ComponentContainer.of(
        CardComponent(
            cardDefinitionId = def.name, name = def.name, manaCost = def.manaCost,
            typeLine = def.typeLine, oracleText = def.oracleText, baseStats = def.creatureStats,
            baseKeywords = def.keywords, baseFlags = def.flags, colors = def.colors,
            ownerId = pid, spellEffect = def.spellEffect,
            hasNonManaActivatedAbility = def.hasNonManaActivatedAbility,
            hasActivatedAbility = def.hasActivatedAbility,
            hasAdventure = def.isAdventure, isDoubleFaced = def.isDoubleFaced,
            originalSetCode = def.setCode,
        ),
        OwnerComponent(pid), ControllerComponent(pid),
    )
    c = com.wingedsheep.engine.core.CardEntityFactory.applyDefinitionDecorations(c, def)
    var s = state.withEntity(id, c)
    s = s.addToZone(ZoneKey(pid, Zone.HAND), id)
    return s to id
}
