package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.game.Game;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * The results of the engine's own Rules-RNG library shuffles, in a
 * process-independent form (AF09).
 *
 * <p>A shuffle's result is the order it left the library in. Native card ids
 * are process-local, so the result is recorded as a permutation of the
 * library's first-seen order: the order the deck put it in before the
 * engine's first shuffle, which every process with the same decks reproduces.
 * The same seed then yields the same permutation in every process and a
 * different seed a different one, so the result digest is replay evidence that
 * a call count alone is not.</p>
 *
 * <p>Only digests leave the engine. The tape is an orchestration channel for
 * the replay twin; no principal receives it and it carries no card identity.</p>
 */
final class XmageRulesRngResultTape {

    private static final Map<String, Map<UUID, List<UUID>>> BASELINES = new ConcurrentHashMap<>();
    private static final Map<String, List<JsonObject>> RESULTS = new ConcurrentHashMap<>();

    private XmageRulesRngResultTape() {
    }

    /** Called before the engine shuffles {@code playerId}'s library. */
    static void beforeShuffle(Game game, UUID playerId, List<UUID> order) {
        if (game == null || playerId == null || game.isSimulation()) {
            return;
        }
        BASELINES.computeIfAbsent(game.getId().toString(), ignored -> new ConcurrentHashMap<>())
                .putIfAbsent(playerId, List.copyOf(order));
    }

    /** Called after the engine shuffled {@code playerId}'s library. */
    static void afterShuffle(Game game, UUID playerId, long callsBefore, long callsAfter, List<UUID> order) {
        if (game == null || playerId == null || game.isSimulation()) {
            return;
        }
        List<JsonObject> results =
                RESULTS.computeIfAbsent(game.getId().toString(), ignored -> new ArrayList<>());
        synchronized (results) {
            JsonObject entry = new JsonObject();
            entry.addProperty("operation", "LIBRARY_SHUFFLE");
            entry.addProperty("sequence", results.size());
            entry.addProperty("seat", seatIndex(game, playerId));
            entry.addProperty("before", callsBefore);
            entry.addProperty("after", callsAfter);
            entry.addProperty("library_size", order.size());
            entry.addProperty("result_digest", digest(libraryTokens(game, playerId, order)));
            results.add(entry);
        }
    }

    /** Every recorded shuffle result of {@code game}, in engine order. */
    static JsonArray results(Game game) {
        JsonArray array = new JsonArray();
        List<JsonObject> results = RESULTS.get(game.getId().toString());
        if (results != null) {
            synchronized (results) {
                for (JsonObject entry : results) {
                    array.add(entry.deepCopy());
                }
            }
        }
        return array;
    }

    /**
     * A process-independent token for one card of {@code ownerId}'s deck: its
     * position in the first-seen library order, or its name for a card that
     * was never part of that order.
     */
    static String token(Game game, UUID ownerId, UUID cardId) {
        Map<UUID, List<UUID>> byOwner = BASELINES.get(game.getId().toString());
        List<UUID> baseline = byOwner == null ? null : byOwner.get(ownerId);
        int index = baseline == null ? -1 : baseline.indexOf(cardId);
        if (index >= 0) {
            return "d" + index;
        }
        Card card = game.getCard(cardId);
        return "n:" + (card == null ? "?" : card.getName());
    }

    static List<String> libraryTokens(Game game, UUID ownerId, List<UUID> order) {
        List<String> tokens = new ArrayList<>(order.size());
        for (UUID cardId : order) {
            tokens.add(token(game, ownerId, cardId));
        }
        return tokens;
    }

    static int seatIndex(Game game, UUID playerId) {
        int index = 0;
        for (UUID id : game.getState().getPlayerList()) {
            if (id.equals(playerId)) {
                return index;
            }
            index++;
        }
        return -1;
    }

    static String digest(List<String> tokens) {
        try {
            MessageDigest sha = MessageDigest.getInstance("SHA-256");
            for (String token : tokens) {
                sha.update(token.getBytes(StandardCharsets.UTF_8));
                sha.update((byte) '\n');
            }
            return HexFormat.of().formatHex(sha.digest());
        } catch (NoSuchAlgorithmException exc) {
            throw new IllegalStateException(exc);
        }
    }
}
