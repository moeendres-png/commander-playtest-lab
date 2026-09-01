package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.players.Player;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

/**
 * Compatibility facade for the full-game bridge.
 *
 * <p>WS-22 deliberately removes the former independent redaction authority.
 * Every outbound observation is produced by the registered
 * {@link XmageKnowledgeLedger}; actor-visible object identity is then replaced
 * by {@link XmageActorIdentityProjection} without changing visibility or
 * legality. The facade exists only so existing production call sites do not
 * gain a second visibility implementation.</p>
 */
final class XmageFullGameStateRedactor {

    private static final Map<Game, XmageKnowledgeLedger> LEDGERS =
            Collections.synchronizedMap(new WeakHashMap<>());

    private XmageFullGameStateRedactor() {
    }

    static void registerKnowledgeLedger(Game game, XmageKnowledgeLedger ledger) {
        if (game == null || ledger == null) {
            throw new IllegalArgumentException("game and knowledge ledger are required");
        }
        LEDGERS.put(game, ledger);
    }

    static XmageKnowledgeLedger knowledgeLedger(Game game) {
        XmageKnowledgeLedger ledger = LEDGERS.get(game);
        if (ledger == null) {
            throw new IllegalStateException("KNOWLEDGE_LEDGER_NOT_REGISTERED");
        }
        return ledger;
    }

    static void registerSeats(Game game, List<? extends Player> players) {
        knowledgeLedger(game).registerPlayers(game, players);
    }

    static JsonObject actorView(Game game, Player actor) {
        return actorView(game, actor, actor);
    }

    static JsonObject actorView(Game game, Player viewer, Player decisionSubject) {
        JsonObject privileged = knowledgeLedger(game).snapshot(game, viewer, decisionSubject);
        return XmageActorIdentityProjection.actorView(game, viewer, privileged);
    }

    static JsonArray livePlayerOrder(Game game) {
        return knowledgeLedger(game).livePlayerOrder(game);
    }

    static int stablePlayerCount(Game game) {
        return game == null ? 0 : knowledgeLedger(game).registeredPlayerCount();
    }

    static int seat(Game game, java.util.UUID playerId) {
        return knowledgeLedger(game).seat(playerId);
    }
}
