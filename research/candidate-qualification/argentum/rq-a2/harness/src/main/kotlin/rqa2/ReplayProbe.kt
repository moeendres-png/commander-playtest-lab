package rqa2

import com.wingedsheep.engine.core.GameAction
import com.wingedsheep.engine.core.SubmitDecision
import com.wingedsheep.engine.state.GameState
import com.wingedsheep.gameserver.protocol.ServerMessage
import com.wingedsheep.gameserver.replay.CompactReplay
import com.wingedsheep.gameserver.replay.ReplayCheckpoint
import com.wingedsheep.gameserver.replay.ReplayCodec
import com.wingedsheep.gameserver.replay.ReplayFingerprint
import com.wingedsheep.gameserver.replay.ReplayPlayerInfo
import com.wingedsheep.gameserver.replay.ReplayPlayerSetup
import com.wingedsheep.gameserver.replay.ReplayReconstructor
import com.wingedsheep.gameserver.replay.ReplaySetup
import com.wingedsheep.sdk.core.AttackMode
import com.wingedsheep.sdk.core.Format
import com.wingedsheep.sdk.model.Deck
import com.wingedsheep.sdk.model.EntityId

// U19 — replay round-trip fidelity probe (CPL-side external driver).
//
// Three meaningfully distinct games are played live through the engine,
// recording (setup + ordered inputs). Each is then:
//  (a) re-executed same-process from setup + inputs (fresh fold), and
//  (b) re-folded through the candidate's actual ReplayReconstructor from the
//      candidate's actual CompactReplay representation (codec round-tripped).
// Per-frame comparison uses the sharp canonical digest plus the candidate's
// own ReplayFingerprint; raw GameState == is also recorded (it is expected
// to differ once process-global AbilityId.generate() values enter state).

data class GameSpec(
    val name: String,
    val kind: String,
    val seed: Long,
    val decks: List<Pair<String, Deck>>,
    val active: Boolean,
    val maxTurns: Int,
    val maxActions: Int,
)

fun buildReplay(game: PlayedGame, initPlayerIds: List<EntityId>, recordedSeed: Long): CompactReplay {
    val liveTurnOrder = game.frames.last().turnOrder.ifEmpty { initPlayerIds }
    val nameById = game.playerDecks.mapIndexed { i, (n, _) -> initPlayerIds[i].value to n }.toMap()
    return CompactReplay(
        gameId = "rq-a2-${game.name}",
        players = liveTurnOrder.map { pid ->
            ReplayPlayerInfo(pid.value, nameById[pid.value] ?: pid.value)
        },
        startedAt = "2026-09-10T00:00:00Z",
        endedAt = "2026-09-10T00:00:00Z",
        winnerName = null,
        setup = ReplaySetup(
            seed = recordedSeed,
            format = game.format,
            attackMode = AttackMode.MULTIPLE,
            startingHandSize = 7,
            skipMulligans = true,
            useHandSmoother = false,
            handSmootherCandidates = 3,
            startingPlayerIndex = null,
            teams = null,
            players = game.playerDecks.mapIndexed { i, (n, d) ->
                ReplayPlayerSetup(
                    playerId = initPlayerIds[i].value,
                    name = n,
                    deck = d,
                    startingLife = 20,
                    commanderCardName = null,
                )
            },
            seatRoster = liveTurnOrder.mapIndexed { i, pid ->
                ServerMessage.PlayerSeatInfo(
                    playerId = pid.value,
                    name = nameById[pid.value] ?: pid.value,
                    seatIndex = i,
                )
            },
        ),
        actions = game.actions,
        yields = emptyList(),
        engineVersion = CANDIDATE_HEAD,
        pinnedCards = emptyList(),
        checkpoints = game.frames.mapIndexedNotNull { frameIdx, st ->
            if (frameIdx > 0 && frameIdx % 20 == 0) {
                ReplayCheckpoint(frameIdx, ReplayFingerprint.of(st))
            } else null
        },
    )
}

fun main(args: Array<String>) {
    val outPath = args.getOrNull(0) ?: "../evidence/ARGENTUM_REPLAY_ROUNDTRIP.json"
    val registry = newRegistry()
    val diag = registryDiagnostics(registry)
    println("RQ-A2 registry diagnostics: $diag")
    val processor = newProcessor(registry)
    val reconstructor = ReplayReconstructor(registry, null)

    val specs = listOf(
        GameSpec(
            name = "G1-pass-priority",
            kind = "simple-deterministic",
            seed = 1001L,
            decks = listOf(
                "Alice" to Deck.of("Forest" to 40),
                "Bob" to Deck.of("Forest" to 40),
            ),
            active = false, maxTurns = 99, maxActions = 80,
        ),
        GameSpec(
            name = "G2-decision-bearing",
            kind = "decision-bearing",
            seed = 2002L,
            decks = listOf(
                "Alice" to Deck.of("Swamp" to 28, "Careful Study" to 12),
                "Bob" to Deck.of("Swamp" to 28, "Careful Study" to 12),
            ),
            active = true, maxTurns = 10, maxActions = 600,
        ),
        GameSpec(
            name = "G3-rules-random",
            kind = "rules-random-coin-flip",
            seed = 3003L,
            decks = listOf(
                "Alice" to Deck.of("Mountain" to 26, "Goblin Psychopath" to 6, "Lightning Bolt" to 8),
                "Bob" to Deck.of("Mountain" to 26, "Goblin Psychopath" to 6, "Lightning Bolt" to 8),
            ),
            active = true, maxTurns = 14, maxActions = 800,
        ),
    )

    val gamesJson = mutableListOf<Any?>()
    val reexecJson = mutableListOf<Any?>()
    val reconJson = mutableListOf<Any?>()

    for (spec in specs) {
        val game = playGame(
            spec.name, registry, spec.decks, spec.seed,
            Format.Standard, spec.maxTurns, spec.maxActions, true, spec.active,
        )
        val liveFrames = game.frames
        val liveCanonical = liveFrames.map { canonicalDigest(it) }
        val liveFinger = liveFrames.map { ReplayFingerprint.of(it) }

        // Re-execution: fresh init from the same setup + verbatim input fold.
        val reinit = initGame(
            registry, seatConfigs(spec.name, spec.decks), spec.seed, Format.Standard, true,
        )
        val rePlayerIds = reinit.playerIds
        var reState = reinit.state
        val reCanonical = mutableListOf(canonicalDigest(reState))
        val reRawEqual = mutableListOf<Boolean>()
        var reError: String? = null
        for ((idx, action) in game.actions.withIndex()) {
            val r = processor.process(reState, action).result
            if (r.error != null || (!r.isSuccess && !r.isPaused)) {
                reError = "action $idx (${actionSummary(action)}): ${r.error}"
                break
            }
            reState = r.newState
            reCanonical.add(canonicalDigest(reState))
            reRawEqual.add(reState == liveFrames[idx + 1])
        }
        val reMatchAll = reError == null &&
            reCanonical.size == liveCanonical.size &&
            reCanonical.zip(liveCanonical).all { (a, b) -> a == b }
        val firstMismatch = reCanonical.zip(liveCanonical).indexOfFirst { (a, b) -> a != b }
            .takeIf { it >= 0 }

        // Candidate-actual replay path: CompactReplay -> codec -> ReplayReconstructor.
        val initForIds = initGame(
            registry, seatConfigs(spec.name, spec.decks), spec.seed, Format.Standard, true,
        )
        val replay = buildReplay(game, initForIds.playerIds, initForIds.seed)
        val codecRoundTrip = runCatching { ReplayCodec.decode(ReplayCodec.encode(replay)) }
            .getOrNull() == replay
        val reconFrames = mutableListOf<String>()
        var reconFail: String? = null
        for (frame in 0..game.actions.size) {
            val rs = reconstructor.reconstructStateAt(replay, frame)
            if (rs == null) { reconFail = "frame $frame returned null"; break }
            reconFrames.add(canonicalDigest(rs))
        }
        val reconMatchAll = reconFail == null &&
            reconFrames.zip(liveCanonical).all { (a, b) -> a == b }
        val reconFirstMismatch = reconFrames.zip(liveCanonical).indexOfFirst { (a, b) -> a != b }
            .takeIf { it >= 0 }
        val fullStream = runCatching { reconstructor.reconstruct(replay) }.getOrNull()
        val streamFrames = fullStream?.frameCount
        val fidelity = fullStream?.fidelity?.name
        val divergedAt = fullStream?.divergedAtFrame

        val submitCount = game.actions.count { it is SubmitDecision }
        val coinFlipEvents = game.coinFlipCount
        val decisionKinds = game.actions.filterIsInstance<SubmitDecision>()
            .mapNotNull { it.response::class.simpleName }.distinct().sorted()
        val eventKinds = game.actionEvents.flatten()
            .map { it.substringBefore('(') }.distinct().sorted()

        gamesJson.add(jo(
            "name" to spec.name,
            "kind" to spec.kind,
            "seed" to spec.seed,
            "recordedSeed" to initForIds.seed,
            "seedMatchesConfig" to (initForIds.seed == spec.seed),
            "players" to game.playerDecks.map { (n, d) ->
                jo("name" to n, "deck" to d.cards.groupingBy { it }.eachCount())
            },
            "format" to "Standard",
            "stopReason" to game.stopReason,
            "actionCount" to game.actions.size,
            "submitDecisionCount" to submitCount,
            "decisionResponseKinds" to decisionKinds,
            "coinFlipEvents" to coinFlipEvents,
            "actionKinds" to game.actions.mapNotNull { it::class.simpleName }.distinct().sorted(),
            "stepHistogram" to game.steps.groupingBy { it }.eachCount().toList().sortedBy { it.first }.map { jo("step" to it.first, "count" to it.second) },
            "eventKinds" to eventKinds,
            "firstActions" to game.actions.take(8).map { actionSummary(it) },
            "liveFinal" to jo(
                "canonical" to liveCanonical.last(),
                "fingerprint" to liveFinger.last(),
                "turnNumber" to liveFrames.last().turnNumber,
                "gameOver" to liveFrames.last().gameOver,
                "winner" to liveFrames.last().winnerId?.value,
                "lifeTotals" to lifeTotals(liveFrames.last()),
                "rngState" to liveFrames.last().rng.state,
            ),
            "initial" to jo(
                "canonical" to liveCanonical.first(),
                "fingerprint" to liveFinger.first(),
                "rngState" to liveFrames.first().rng.state,
            ),
        ))
        reexecJson.add(jo(
            "game" to spec.name,
            "mode" to "same-process fresh GameInitializer fold, verbatim inputs",
            "error" to reError,
            "framesCompared" to minOf(reCanonical.size, liveCanonical.size),
            "canonicalMatchAll" to reMatchAll,
            "firstMismatchFrame" to firstMismatch,
            "rawStateEqualAll" to (reRawEqual.isNotEmpty() && reRawEqual.all { it }),
            "rawStateEqualCount" to reRawEqual.count { it },
        ))
        reconJson.add(jo(
            "game" to spec.name,
            "codecRoundTripEqual" to codecRoundTrip,
            "reconstructor" to "ReplayReconstructor.reconstructStateAt per frame + reconstruct stream",
            "reconstructorError" to reconFail,
            "framesCompared" to minOf(reconFrames.size, liveCanonical.size),
            "canonicalMatchAll" to reconMatchAll,
            "firstMismatchFrame" to reconFirstMismatch,
            "streamFrameCount" to streamFrames,
            "streamExpectedFrames" to (1 + game.actions.size),
            "streamComplete" to (streamFrames == 1 + game.actions.size),
            "fidelity" to fidelity,
            "divergedAtFrame" to divergedAt,
            "checkpoints" to replay.checkpoints.size,
        ))
    }

    val root = jo(
        "probe" to "U19 replay round-trip fidelity",
        "candidate" to jo(
            "repo" to "wingedsheep/argentum-engine",
            "head" to CANDIDATE_HEAD,
            "tree" to CANDIDATE_TREE,
            "engineVersionField" to CANDIDATE_HEAD,
        ),
        "build" to jo(
            "jdk" to System.getProperty("java.version"),
            "driver" to "CPL-side rq-a2 harness (engine GameInitializer + ActionProcessor fold; candidate ReplayReconstructor + ReplayCodec + ReplayFingerprint)",
        ),
        "registry" to diag,
        "games" to gamesJson,
        "reexecution" to reexecJson,
        "reconstructor" to reconJson,
        "notes" to listOf(
            "canonical = sha256 over full GameState data-class rendering with generated ability ids (ability_N) and UUIDs normalized; routing ids r<N>, entity ids e<N> and GameRng state compared exactly.",
            "fingerprint = candidate-authoritative ReplayFingerprint.of per frame (coarse checkpoint signal).",
            "Raw GameState == is expected to fail once process-global AbilityId.generate() values enter state (U22 effect); canonical equality is the semantic criterion.",
            "G1 uses the pass-only policy (empty combat declarations + priority passes).",
        ),
    )
    writeJson(outPath, root)
    println("wrote $outPath")
}
