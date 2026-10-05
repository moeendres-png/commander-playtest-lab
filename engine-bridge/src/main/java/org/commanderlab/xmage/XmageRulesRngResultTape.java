package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.game.Game;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * The results of the engine's own Rules-RNG library shuffles, in a
 * process-independent form, for the AF09 clean-process replay twin.
 *
 * <p>A shuffle's result is the permutation it applied: for each position of
 * the shuffled library, the position that card held immediately before the
 * shuffle. That depends only on the Rules RNG and the library size, never on
 * which of several identical cards stood where, so the same seed reproduces it
 * in every process and a different seed changes it.</p>
 *
 * <p>This is an orchestration channel, not an observation. It exists only when
 * the launch carries an orchestration key ({@value #KEY_VARIABLE}); without
 * one nothing is recorded and the bridge refuses the request. Every digest is
 * an HMAC under that key, so whoever does not hold the key can neither read a
 * hidden order out of a digest nor test a guess against it.</p>
 */
final class XmageRulesRngResultTape {

    static final String KEY_VARIABLE = "COMMANDER_LAB_ORCHESTRATION_KEY";

    // Loaded lazily, on the first use of the channel, never at class load: a
    // malformed variable must not crash an ordinary game's first shuffle.
    private static volatile byte[] KEY;
    private static volatile boolean keyLoaded;
    private static volatile String keyProblem;
    private static final Map<String, Map<UUID, List<UUID>>> PRE_SHUFFLE = new ConcurrentHashMap<>();
    private static final Map<String, List<JsonObject>> RESULTS = new ConcurrentHashMap<>();

    private XmageRulesRngResultTape() {
    }

    private static synchronized void loadKey() {
        if (keyLoaded) {
            return;
        }
        keyLoaded = true;
        String hex = System.getenv(KEY_VARIABLE);
        if (hex == null || hex.isBlank()) {
            return;
        }
        try {
            byte[] key = HexFormat.of().parseHex(hex.trim());
            if (key.length < 16) {
                keyProblem = KEY_VARIABLE + " carries fewer than 128 bits";
                return;
            }
            KEY = key;
        } catch (IllegalArgumentException exc) {
            keyProblem = KEY_VARIABLE + " is not hexadecimal";
        }
    }

    /** Test seam: the key a test JVM's launch would carry (never set in production code). */
    static synchronized void keyForTests(byte[] key) {
        keyLoaded = true;
        keyProblem = null;
        KEY = key == null ? null : key.clone();
    }

    /** True only when the launch carried a well-formed orchestration key. */
    static boolean enabled() {
        loadKey();
        return KEY != null;
    }

    /** Why a key the launch carried was rejected, or null. */
    static String keyProblem() {
        loadKey();
        return keyProblem;
    }

    /** Called before the engine shuffles {@code playerId}'s library. */
    static void beforeShuffle(Game game, UUID playerId, List<UUID> order) {
        if (!enabled() || game == null || playerId == null || game.isSimulation()) {
            return;
        }
        PRE_SHUFFLE.computeIfAbsent(game.getId().toString(), ignored -> new ConcurrentHashMap<>())
                .put(playerId, List.copyOf(order));
    }

    /** Called after the engine shuffled {@code playerId}'s library. */
    static void afterShuffle(Game game, UUID playerId, long callsBefore, long callsAfter, List<UUID> order) {
        if (!enabled() || game == null || playerId == null || game.isSimulation()) {
            return;
        }
        Map<UUID, List<UUID>> byPlayer = PRE_SHUFFLE.get(game.getId().toString());
        List<UUID> before = byPlayer == null ? null : byPlayer.remove(playerId);
        List<String> permutation = new ArrayList<>(order.size());
        for (UUID cardId : order) {
            int index = before == null ? -1 : before.indexOf(cardId);
            permutation.add(index >= 0 ? Integer.toString(index) : "?");
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
            entry.addProperty("result_digest", digest(permutation));
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
     * The player's stable seat (F-41: turn order counted from the first seat).
     * Iterating the engine's PlayerList is no seat: that circular list iterates
     * from its moving current position, so the same player would get another
     * index once the turn pointer moved (a card-caused shuffle in a later
     * priority window was taped under the wrong seat).
     */
    static int seatIndex(Game game, UUID playerId) {
        return XmageSeating.seat(game, playerId);
    }

    /** HMAC-SHA-256 under the orchestration key; refuses without one. */
    static String digest(List<String> tokens) {
        if (!enabled()) {
            throw new IllegalStateException("orchestration channel not enabled for this launch");
        }
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(KEY, "HmacSHA256"));
            for (String token : tokens) {
                mac.update(token.getBytes(StandardCharsets.UTF_8));
                mac.update((byte) '\n');
            }
            return HexFormat.of().formatHex(mac.doFinal());
        } catch (GeneralSecurityException exc) {
            throw new IllegalStateException(exc);
        }
    }
}
