package rqa2

import com.wingedsheep.engine.core.CardsSelectedResponse
import com.wingedsheep.engine.core.GameAction
import com.wingedsheep.engine.core.PassPriority
import com.wingedsheep.engine.core.SubmitDecision
import com.wingedsheep.gameserver.replay.ReplayReconstructor
import com.wingedsheep.sdk.core.Format
import com.wingedsheep.sdk.model.Deck
import com.wingedsheep.sdk.model.EntityId

// U19 negative controls: a replay verifier that cannot detect tampering is not
// sufficient. Each control mutates the recorded (setup + inputs) stream and
// requires the re-fold to DETECT it (rejection or digest divergence), with the
// pre-mutation prefix still matching exactly (earliest-divergence sensitivity).
// N0 is the positive control (unmutated stream must replay EXACT).
// N5 documents the seat-id namespace constraint (e<N> seat ids collide with
// minted entity ids on reconstruction) through the candidate's own
// ReplayReconstructor: it must DIVERGE, never silently match.

data class ControlResult(
    val id: String,
    val description: String,
    val detected: Boolean,
    val mechanism: String, // EXACT_MATCH | REJECTED_AT i | DIVERGED_AT i | NULL_FRAME i
    val detail: String,
    val prefixFramesExact: Int,
)

fun foldFrom(
    seed: Long,
    decks: List<Pair<String, Deck>>,
    gameName: String,
    actions: List<GameAction>,
    playerIdOverride: ((Int, String) -> EntityId)? = null,
): Triple<List<String>, String?, Int> {
    // Returns (canonical digests incl. frame 0, error or null, compared prefix length).
    val registry = newRegistry()
    val processor = newProcessor(registry)
    val configs = if (playerIdOverride == null) seatConfigs(gameName, decks)
    else decks.mapIndexed { i, (n, d) ->
        com.wingedsheep.engine.core.PlayerConfig(n, d, 20, playerIdOverride(i, n))
    }
    val init = initGame(registry, configs, seed, Format.Standard, true)
    var state = init.state
    val digests = mutableListOf(canonicalDigest(state))
    for ((idx, action) in actions.withIndex()) {
        val r = processor.process(state, action).result
        if (r.error != null || (!r.isSuccess && !r.isPaused)) {
            return Triple(digests, "rejected at $idx (${actionSummary(action)}): ${r.error}", idx)
        }
        state = r.newState
        digests.add(canonicalDigest(state))
    }
    return Triple(digests, null, actions.size)
}

fun compareStreams(live: List<String>, re: List<String>): Pair<Boolean, Int?> {
    val n = minOf(live.size, re.size)
    for (i in 0 until n) if (live[i] != re[i]) return Pair(true, i)
    if (live.size != re.size) return Pair(true, n)
    return Pair(false, null)
}

fun main(args: Array<String>) {
    val outPath = args.getOrNull(0) ?: "../evidence/ARGENTUM_REPLAY_NEGATIVE_CONTROLS.json"
    val decks = listOf(
        "Alice" to Deck.of("Swamp" to 28, "Careful Study" to 12),
        "Bob" to Deck.of("Swamp" to 28, "Careful Study" to 12),
    )
    val seed = 2002L
    val gameName = "G2-decision-bearing"

    val registry = newRegistry()
    val live = playGame(gameName, registry, decks, seed, Format.Standard, 10, 600, true, true)
    val liveDigests = live.frames.map { canonicalDigest(it) }
    val results = mutableListOf<ControlResult>()

    fun evaluate(id: String, desc: String, mutated: List<GameAction>, mSeed: Long = seed): ControlResult {
        val (re, err, _) = foldFrom(mSeed, decks, gameName, mutated)
        if (err != null) {
            val at = Regex("rejected at (\\d+)").find(err)?.groupValues?.get(1)?.toIntOrNull() ?: -1
            // Earliest semantic divergence, if any, precedes the rejection point.
            val firstDiff = re.zip(liveDigests).indexOfFirst { (a, b) -> a != b }.takeIf { it >= 0 }
            val (mechanism, prefix) = if (firstDiff != null && (at < 0 || firstDiff <= at)) {
                "DIVERGED_AT_${firstDiff}_THEN_REJECTED_AT_$at" to firstDiff
            } else {
                "REJECTED_AT_$at" to if (at >= 0) at + 1 else 0
            }
            return ControlResult(id, desc, true, mechanism, err, prefix)
        } else {
            val (diverged, at) = compareStreams(liveDigests, re)
            return if (diverged) {
                // Earliest-divergence causality: prefix before the mutation must match.
                ControlResult(id, desc, true, "DIVERGED_AT $at",
                    "re-fold applied but digest differs at frame $at", at ?: -1)
            } else {
                ControlResult(id, desc, false, "EXACT_MATCH",
                    "MUTATION NOT DETECTED: re-fold is digest-identical", re.size)
            }
        }
    }

    // N0 — positive control.
    val (re0, err0, _) = foldFrom(seed, decks, gameName, live.actions)
    val (div0, _) = compareStreams(liveDigests, re0)
    results.add(ControlResult("N0-positive-control",
        "unmutated setup+inputs must replay digest-identical (verifier non-vacuous positive)",
        err0 == null && !div0, if (err0 == null && !div0) "EXACT_MATCH" else "UNEXPECTED_${err0 ?: "divergence"}",
        "compared ${re0.size} frames", re0.size))

    // N1a — altered selected input: empty a SelectCards response (below its minimum).
    val firstSubmit = live.actions.indexOfFirst { it is SubmitDecision }
    if (firstSubmit >= 0) {
        val orig = live.actions[firstSubmit] as SubmitDecision
        val resp = orig.response as? CardsSelectedResponse
        if (resp != null) {
            val mutated = live.actions.toMutableList()
            mutated[firstSubmit] = orig.copy(response = resp.copy(selectedCards = emptyList()))
            val r = evaluate("N1a-altered-input-empty-selection",
                "CardsSelectedResponse emptied below minSelections at action $firstSubmit", mutated)
            results.add(r)
            // N1b — altered selected input, same shape: pick different cards if possible.
            val pending = live.frames[firstSubmit].pendingDecision
            val options = (pending as? com.wingedsheep.engine.core.SelectCardsDecision)?.options
                ?: (pending as? com.wingedsheep.engine.core.SearchLibraryDecision)?.options
                ?: emptyList()
            val alt = options.takeLast(resp.selectedCards.size)
            if (alt.toSet() != resp.selectedCards.toSet() && alt.size == resp.selectedCards.size) {
                val mutated2 = live.actions.toMutableList()
                mutated2[firstSubmit] = orig.copy(response = resp.copy(selectedCards = alt))
                results.add(evaluate("N1b-altered-input-reselected",
                    "CardsSelectedResponse swapped to different legal cards at action $firstSubmit", mutated2))
            } else {
                results.add(ControlResult("N1b-altered-input-reselected",
                    "skipped: no distinct same-size selection available at action $firstSubmit",
                    true, "SKIPPED_VACUOUS", "no distinct alternative; N1a remains the selected-input control", 0))
            }
        }
    }

    // N1c — altered actor: first PassPriority submitted by the opponent instead.
    val firstPass = live.actions.indexOfFirst { it is PassPriority }
    if (firstPass >= 0) {
        val orig = live.actions[firstPass] as PassPriority
        val other = live.actions.map { it.playerId }.first { it != orig.playerId }
        val mutated = live.actions.toMutableList()
        mutated[firstPass] = orig.copy(playerId = other)
        results.add(evaluate("N1c-altered-actor",
            "PassPriority actor swapped to opponent at action $firstPass", mutated))
    }

    // N2 — altered seed.
    run {
        val (re, err, _) = foldFrom(seed + 1, decks, gameName, live.actions)
        if (err != null) {
            val at = Regex("rejected at (\\d+)").find(err)?.groupValues?.get(1)?.toIntOrNull() ?: -1
            results.add(ControlResult("N2-altered-seed", "seed+1 with identical inputs",
                true, "REJECTED_AT_$at", err, 0))
        } else {
            val (diverged, at) = compareStreams(liveDigests, re)
            results.add(ControlResult("N2-altered-seed", "seed+1 with identical inputs",
                diverged, if (diverged) "DIVERGED_AT $at" else "EXACT_MATCH",
                if (diverged) "initial frame already differs: seed routes into shuffle/turn order" else "NOT DETECTED",
                0))
        }
    }

    // N3 — reordered inputs: swap the first cross-player adjacent pair.
    run {
        var swapAt = -1
        for (i in 0 until live.actions.size - 1) {
            if (live.actions[i].playerId != live.actions[i + 1].playerId) { swapAt = i; break }
        }
        if (swapAt < 0) swapAt = 0
        val mutated = live.actions.toMutableList()
        val tmp = mutated[swapAt]; mutated[swapAt] = mutated[swapAt + 1]; mutated[swapAt + 1] = tmp
        results.add(evaluate("N3-reordered-inputs",
            "swapped actions $swapAt and ${swapAt + 1} (${actionSummary(live.actions[swapAt])} <-> ${actionSummary(live.actions[swapAt + 1])})",
            mutated))
    }

    // N4 — omitted input: drop the first action.
    run {
        val mutated = live.actions.drop(1)
        val (re, err, _) = foldFrom(seed, decks, gameName, mutated)
        if (err != null) {
            val at = Regex("rejected at (\\d+)").find(err)?.groupValues?.get(1)?.toIntOrNull() ?: -1
            results.add(ControlResult("N4-omitted-input", "dropped action 0 (${actionSummary(live.actions[0])})",
                true, "REJECTED_AT_$at", err, 1))
        } else {
            // Frame alignment shifts by one; compare re[i] against live[i+1].
            var at: Int? = null
            for (i in re.indices) {
                if (i + 1 >= liveDigests.size || re[i] != liveDigests[i + 1]) { at = i; break }
            }
            results.add(ControlResult("N4-omitted-input", "dropped action 0 (${actionSummary(live.actions[0])})",
                at != null, if (at != null) "DIVERGED_AT re-frame $at" else "EXACT_MATCH",
                if (at != null) "shifted stream diverges at re-frame $at (live frame ${at + 1})" else "NOT DETECTED", 1))
        }
    }

    // N5 — seat-id namespace collision through the candidate's own reconstructor.
    run {
        val reg2 = newRegistry()
        val liveInit = initGame(reg2, seatConfigs(gameName, decks), seed, Format.Standard, true)
        val replay = buildReplay(live, liveInit.playerIds, liveInit.seed)
        val recon = ReplayReconstructor(reg2, null)
        val okStates = (0..live.actions.size).map { recon.reconstructStateAt(replay, it) }
        val fullNull = okStates.indexOfFirst { it == null }
        val canonMatch = okStates.mapIndexed { i, s -> s?.let { canonicalDigest(it) == liveDigests[i] } ?: false }
        // Now the colliding variant: seat ids inside the e<N> namespace.
        val (reCol, errCol, _) = foldFrom(seed, decks, gameName, live.actions) { i, _ -> EntityId("e$i") }
        val replayCol = runCatching {
            val reg3 = newRegistry()
            val initCol = initGame(reg3, decks.mapIndexed { i, (n, d) ->
                com.wingedsheep.engine.core.PlayerConfig(n, d, 20, EntityId("e$i"))
            }, seed, Format.Standard, true)
            buildReplay(live, initCol.playerIds, initCol.seed)
        }.getOrNull()
        val reconCol = replayCol?.let {
            val reg3 = newRegistry()
            val rc = ReplayReconstructor(reg3, null)
            val states = (0..live.actions.size).map { f -> rc.reconstructStateAt(it, f) }
            val firstNull = states.indexOfFirst { s -> s == null }
            val firstMismatch = states.mapIndexed { f, s ->
                s?.let { canonicalDigest(it) != liveDigests[f] } ?: true
            }.indexOfFirst { it }.takeIf { it >= 0 }
            "firstNull=$firstNull firstMismatch=$firstMismatch"
        } ?: "setup failed: $errCol"
        val full = runCatching { recon.reconstruct(replay) }.getOrNull()
        results.add(ControlResult("N5-seat-id-namespace",
            "candidate ReplayReconstructor on sane (non-colliding) seats must be EXACT; colliding e<N> seats must DIVERGE, never silently match",
            fullNull == -1 && canonMatch.all { it } && (replayCol == null || reconCol.contains("Mismatch") || reconCol.contains("Null")),
            "sane: frames=${okStates.size} nullAt=$fullNull allMatch=${canonMatch.all { it }} fidelity=${full?.fidelity}; colliding: $reconCol",
            "sane replay fidelity=${full?.fidelity} frames=${full?.frameCount}; colliding recon=$reconCol; live-fold-with-colliding-seats error=$errCol",
            okStates.size))
    }

    val root = jo(
        "probe" to "U19 negative replay controls",
        "candidate" to jo("repo" to "wingedsheep/argentum-engine", "head" to CANDIDATE_HEAD, "tree" to CANDIDATE_TREE),
        "game" to jo("name" to gameName, "seed" to seed, "actions" to live.actions.size, "stopReason" to live.stopReason),
        "controls" to results.map { r ->
            jo("id" to r.id, "description" to r.description, "detected" to r.detected,
                "mechanism" to r.mechanism, "detail" to r.detail, "prefixFramesExact" to r.prefixFramesExact)
        },
        "verdict" to jo(
            "allDetected" to results.all { it.detected || it.mechanism == "SKIPPED_VACUOUS" },
        ),
    )
    writeJson(outPath, root)
    println("wrote $outPath")
    for (r in results) println("${r.id}: detected=${r.detected} ${r.mechanism} | ${r.detail}")
}
