package rqa2

import com.wingedsheep.engine.core.PlayerConfig
import com.wingedsheep.engine.state.GameState
import com.wingedsheep.gameserver.replay.ReplayReconstructor
import com.wingedsheep.sdk.core.Format
import com.wingedsheep.sdk.model.Deck

// Temporary debug: compare live init vs ReplayReconstructor frame 0 dimension by dimension.
fun summarize(tag: String, s: GameState): String = buildString {
    appendLine("== $tag ==")
    appendLine("turnOrder=${s.turnOrder.map { it.value }} active=${s.activePlayerId?.value} pri=${s.priorityPlayerId?.value}")
    appendLine("turn=${s.turnNumber} phase=${s.phase} step=${s.step} ts=${s.timestamp}")
    appendLine("nextEntityId=${s.nextEntityId} rng=${s.rng.state} stack=${s.stack}")
    appendLine("zones=" + s.zones.entries.sortedBy { "${it.key.ownerId.value}:${it.key.zoneType}" }
        .joinToString(",") { "${it.key.ownerId.value}:${it.key.zoneType}=${it.value.size}[${it.value.take(3).joinToString("/") { v -> v.value }}...]" })
    appendLine("life=" + s.turnOrder.joinToString(",") { "${it.value}=${s.lifeTotal(it)}" })
    appendLine("pending=" + s.pendingDecision?.let { "${it::class.simpleName} id=${it.id} player=${it.playerId.value}" })
    appendLine("canon=" + canonicalDigest(s))
}

fun main(args: Array<String>) {
    val registry = newRegistry()
    val decks = listOf("Alice" to Deck.of("Forest" to 40), "Bob" to Deck.of("Forest" to 40))
    val live = initGame(registry, seatConfigs("dbg", decks), 1001L, Format.Standard, true)
    println(summarize("LIVE", live.state))
    val reconstructor = ReplayReconstructor(registry, null)
    val game = PlayedGame("dbg", 1001L, decks, Format.Standard, emptyList(), listOf(live.state), emptyList(), emptyList(), 0, "dbg")
    val replay = buildReplay(game, live.playerIds, live.seed)
    val rs = reconstructor.reconstructStateAt(replay, 0)!!
    println(summarize("RECON", rs))
    // Library order head comparison
    val libKey = { s: GameState, pid: String ->
        s.zones.entries.first { it.key.ownerId.value == pid && it.key.zoneType.name == "LIBRARY" }.value
    }
    for (pid in live.state.turnOrder.map { it.value }) {
        val a = libKey(live.state, pid)
        val b = libKey(rs, pid)
        println("$pid live-lib-head=${a.take(5).map { it.value }} recon-lib-head=${b.take(5).map { it.value }} sameOrder=${a == b}")
    }
    for ((tag, s) in listOf("LIVE" to live.state, "RECON" to rs)) {
        val zoned = s.zones.values.flatten().toSet()
        println("$tag entities.size=${s.entities.size} zonedSlots=${s.zones.values.sumOf { it.size }} stack=${s.stack.size}")
        println("$tag hasE0=${com.wingedsheep.sdk.model.EntityId("e0") in s.entities} hasE1=${com.wingedsheep.sdk.model.EntityId("e1") in s.entities}")
        println("$tag firstIds=${s.entities.keys.take(6).map { it.value }}")
        println("$tag unzoned=${(s.entities.keys - zoned - s.stack.toSet()).map { it.value to (s.entities[it]?.all()?.map { c -> c::class.simpleName }) }}")
        val missing = zoned.filter { it !in s.entities.keys }
        println("$tag zoneRefsMissingEntities=${missing.map { it.value }}")
    }
}
