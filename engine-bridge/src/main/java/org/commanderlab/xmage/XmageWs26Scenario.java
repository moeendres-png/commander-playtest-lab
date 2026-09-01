package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.cards.decks.Deck;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.PutToBattlefieldInfo;
import mage.game.permanent.Permanent;
import mage.game.turn.PreCombatMainPhase;
import mage.game.turn.PreCombatMainStep;
import mage.players.Player;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * WS-26 qualification-only semantic starting-state adapter.
 *
 * <p>Only state that XMage can construct through its native test/scenario
 * facilities is accepted. Unsupported dimensions fail closed rather than
 * being approximated by Commander Lab.</p>
 */
final class XmageWs26Scenario {

    static final String SCHEMA_VERSION = "xmage-qualification-scenario/1.1.0";
    static final String LEGACY_SCHEMA_VERSION = "xmage-qualification-scenario/1.0.0";
    static final String NATURAL_GAME_START = "NATURAL_GAME_START";
    static final String NATIVE_STATE_LOAD = "NATIVE_STATE_LOAD";

    static final class ScenarioException extends RuntimeException {
        ScenarioException(String message) { super(message); }
    }

    record Applied(
            String scenarioId,
            String scenarioSha256,
            String executionEntryMode,
            Map<UUID, String> semanticObjectIds,
            JsonObject validation
    ) {}

    private static final Set<String> TOP = Set.of(
            "schema_version", "scenario_id", "seed", "starting_player_seat", "players",
            "execution_entry_mode", "temporal_state"
    );
    private static final Set<String> PLAYER = Set.of(
            "seat", "life", "commander_names", "zones",
            "natural_library_card_name", "natural_library_card_count"
    );
    private static final Set<String> ZONES = Set.of("hand", "library", "graveyard", "exile", "battlefield");
    private static final Set<String> CARD = Set.of("semantic_id", "card_name", "tapped", "controller_seat", "face");
    private static final Set<String> EXPLICITLY_UNSUPPORTED = Set.of(
            "attached_to", "counters", "face_down", "known_to", "native_object_id",
            "stack", "mana", "priority_holder", "active_player", "turn", "phase", "step"
    );
    private static final Set<String> TEMPORAL = Set.of(
            "turn_number", "active_player", "priority_player", "phase", "step"
    );

    private XmageWs26Scenario() {}

    static Applied apply(
            JsonObject scenario,
            Game game,
            List<? extends Player> players,
            List<Deck> decks,
            XmageKnowledgeLedger ledger,
            long expectedSeed,
            int expectedStartingSeatZero
    ) {
        if (scenario == null || game == null || players == null || decks == null || ledger == null) {
            throw fail("INVALID_SCENARIO: scenario/game/players/decks/ledger are required");
        }
        rejectUnknown(scenario, TOP, "scenario");
        if (!Set.of(SCHEMA_VERSION, LEGACY_SCHEMA_VERSION).contains(text(scenario, "schema_version"))) {
            throw fail("INVALID_SCENARIO_SCHEMA");
        }
        String scenarioId = text(scenario, "scenario_id");
        String executionEntryMode = optionalText(scenario, "execution_entry_mode", NATIVE_STATE_LOAD);
        if (!Set.of(NATURAL_GAME_START, NATIVE_STATE_LOAD).contains(executionEntryMode)) {
            throw fail("INVALID_EXECUTION_ENTRY_MODE");
        }
        if (number(scenario, "seed") != expectedSeed) throw fail("SCENARIO_SEED_MISMATCH");
        if (integer(scenario, "starting_player_seat") != expectedStartingSeatZero + 1) {
            throw fail("SCENARIO_STARTING_PLAYER_MISMATCH");
        }

        JsonArray playerSpecs = array(scenario, "players");
        if (playerSpecs.size() != players.size() || decks.size() != players.size()) {
            throw fail("INVALID_PLAYER_COUNT");
        }

        Map<Integer, JsonObject> bySeat = new LinkedHashMap<>();
        Set<String> semanticIds = new LinkedHashSet<>();
        for (JsonElement element : playerSpecs) {
            if (!element.isJsonObject()) throw fail("INVALID_SCENARIO: player entry must be object");
            JsonObject spec = element.getAsJsonObject();
            rejectUnknown(spec, PLAYER, "player");
            int seat = integer(spec, "seat");
            if (seat < 1 || seat > players.size()) throw fail("INVALID_PLAYER_IDENTITY: seat=" + seat);
            if (bySeat.put(seat, spec) != null) throw fail("DUPLICATE_PLAYER_IDENTITY: seat=" + seat);
            validateCommanders(spec, decks.get(seat - 1), seat);
            JsonObject zones = object(spec, "zones");
            rejectUnknown(zones, ZONES, "zones");
            for (String zone : ZONES) {
                for (JsonElement cardElement : optionalArray(zones, zone)) {
                    if (!cardElement.isJsonObject()) throw fail("INVALID_SCENARIO: card entry must be object");
                    JsonObject card = cardElement.getAsJsonObject();
                    rejectUnknown(card, CARD, "card");
                    String semantic = text(card, "semantic_id");
                    if (!semanticIds.add(semantic)) throw fail("DUPLICATE_SEMANTIC_IDENTITY: " + semantic);
                    text(card, "card_name");
                    if (!"main".equals(optionalText(card, "face", "main"))) {
                        throw fail("INVALID_CARD_FACE_REFERENCE");
                    }
                    if (card.has("controller_seat") && !card.get("controller_seat").isJsonNull()
                            && integer(card, "controller_seat") != seat) {
                        throw fail("UNSUPPORTED_SCENARIO_DIMENSION: non-owner controller assignment");
                    }
                    if (!"battlefield".equals(zone) && booleanValue(card, "tapped", false)) {
                        throw fail("INVALID_SCENARIO: tapped only applies to battlefield");
                    }
                }
            }
        }
        for (int seat = 1; seat <= players.size(); seat++) {
            if (!bySeat.containsKey(seat)) throw fail("INVALID_PLAYER_IDENTITY: missing seat=" + seat);
        }

        if (NATURAL_GAME_START.equals(executionEntryMode)) {
            JsonObject validation = validateNaturalStart(decks, bySeat);
            return new Applied(
                    scenarioId,
                    sha256(canonical(scenario)),
                    executionEntryMode,
                    Map.of(),
                    validation
            );
        }

        // Full preflight before any native mutation: malformed input must be retry-safe.
        for (int zero = 0; zero < players.size(); zero++) {
            Map<String, Integer> requested = new HashMap<>();
            JsonObject zones = bySeat.get(zero + 1).getAsJsonObject("zones");
            for (String zone : ZONES) {
                for (JsonElement element : optionalArray(zones, zone)) {
                    requested.merge(text(element.getAsJsonObject(), "card_name"), 1, Integer::sum);
                }
            }
            Map<String, List<Card>> available = available(game, players.get(zero).getId());
            for (Map.Entry<String, Integer> entry : requested.entrySet()) {
                if (available.getOrDefault(entry.getKey(), List.of()).size() < entry.getValue()) {
                    throw fail("STALE_OBJECT_OR_CARD_REFERENCE: " + entry.getKey());
                }
            }
        }

        Map<UUID, String> semanticMap = new LinkedHashMap<>();
        for (int zero = 0; zero < players.size(); zero++) {
            int seat = zero + 1;
            Player player = players.get(zero);
            JsonObject spec = bySeat.get(seat);
            int life = integer(spec, "life");
            if (life <= 0) throw fail("INVALID_SCENARIO: life must be positive");

            EnumMap<Zone, String> reset = new EnumMap<>(Zone.class);
            reset.put(Zone.HAND, "clear");
            reset.put(Zone.LIBRARY, "clear");
            reset.put(Zone.OUTSIDE, "life:" + life);
            game.cheat(player.getId(), reset);

            Map<String, List<Card>> available = available(game, player.getId());
            Set<UUID> used = new HashSet<>();
            JsonObject zones = spec.getAsJsonObject("zones");
            List<Card> hand = bind(optionalArray(zones, "hand"), available, used, semanticMap);
            List<Card> library = bind(optionalArray(zones, "library"), available, used, semanticMap);
            List<Card> grave = bind(optionalArray(zones, "graveyard"), available, used, semanticMap);
            List<Card> exile = bind(optionalArray(zones, "exile"), available, used, semanticMap);
            List<PutToBattlefieldInfo> battlefield = bindBattlefield(
                    optionalArray(zones, "battlefield"), available, used, semanticMap
            );
            List<Card> insertion = new ArrayList<>(library);
            java.util.Collections.reverse(insertion); // native put-on-top => preserve semantic top-to-bottom
            game.cheat(player.getId(), insertion, hand, battlefield, grave, List.of(), exile);
        }

        JsonObject validation = validateNative(game, players, bySeat, semanticMap, ledger);
        return new Applied(
                scenarioId,
                sha256(canonical(scenario)),
                executionEntryMode,
                Map.copyOf(semanticMap),
                validation
        );
    }

    static JsonObject applyTemporalState(
            JsonObject scenario,
            Game game,
            List<? extends Player> players
    ) {
        JsonObject temporal = object(scenario, "temporal_state");
        rejectUnknown(temporal, TEMPORAL, "temporal_state");
        int turn = integer(temporal, "turn_number");
        int activeSeat = playerSeat(temporal, "active_player", players.size());
        int prioritySeat = playerSeat(temporal, "priority_player", players.size());
        String phaseName = text(temporal, "phase");
        String stepName = text(temporal, "step");
        if (!"precombat_main".equals(phaseName) || !"main".equals(stepName)) {
            throw fail("UNSUPPORTED_SCENARIO_DIMENSION: temporal phase/step " + phaseName + "/" + stepName);
        }
        if (turn < 1) throw fail("INVALID_SCENARIO: turn_number must be positive");

        PreCombatMainPhase phase = new PreCombatMainPhase();
        phase.setStep(new PreCombatMainStep());
        game.getState().getTurn().setPhase(phase);
        game.getState().setTurnNum(turn);
        game.getState().setActivePlayerId(players.get(activeSeat - 1).getId());
        game.getState().setPriorityPlayerId(players.get(prioritySeat - 1).getId());
        game.getState().setPlayerByOrderId(players.get(activeSeat - 1).getId());

        requireNative(game.getState().getTurnNum() == turn, "temporal-turn");
        requireNative(game.getActivePlayerId().equals(players.get(activeSeat - 1).getId()), "temporal-active-player");
        requireNative(game.getPriorityPlayerId().equals(players.get(prioritySeat - 1).getId()), "temporal-priority-player");
        requireNative(game.getTurnPhaseType() != null && "PRECOMBAT_MAIN".equals(game.getTurnPhaseType().name()), "temporal-phase");
        requireNative(game.getTurnStepType() != null && "PRECOMBAT_MAIN".equals(game.getTurnStepType().name()), "temporal-step");

        JsonObject result = new JsonObject();
        result.addProperty("validator", "xmage-native-temporal-state/1.0.0");
        result.addProperty("turn_number", turn);
        result.addProperty("active_player", "P" + activeSeat);
        result.addProperty("priority_player", "P" + prioritySeat);
        result.addProperty("phase", phaseName);
        result.addProperty("step", stepName);
        result.addProperty("valid", true);
        return result;
    }

    static int requestedPrioritySeat(JsonObject scenario, int playerCount) {
        return playerSeat(object(scenario, "temporal_state"), "priority_player", playerCount);
    }

    private static int playerSeat(JsonObject source, String key, int playerCount) {
        String player = text(source, key);
        if (!player.matches("P[1-9][0-9]*")) throw fail("INVALID_PLAYER_IDENTITY: " + key + "=" + player);
        int seat = Integer.parseInt(player.substring(1));
        if (seat < 1 || seat > playerCount) throw fail("INVALID_PLAYER_IDENTITY: " + key + "=" + player);
        return seat;
    }

    private static JsonObject validateNaturalStart(List<Deck> decks, Map<Integer, JsonObject> specs) {
        JsonArray checks = new JsonArray();
        for (int zero = 0; zero < decks.size(); zero++) {
            int seat = zero + 1;
            JsonObject spec = specs.get(seat);
            String expectedName = text(spec, "natural_library_card_name");
            int expectedCount = integer(spec, "natural_library_card_count");
            Deck deck = decks.get(zero);
            requireNative(deck.getCards().size() == expectedCount, "natural-deck-count:P" + seat);
            requireNative(
                    deck.getCards().stream().allMatch(card -> expectedName.equals(card.getName())),
                    "natural-deck-identity:P" + seat
            );
            JsonObject zones = object(spec, "zones");
            for (String zone : ZONES) {
                requireNative(optionalArray(zones, zone).isEmpty(), "natural-start-has-injected-zone:P" + seat);
            }
            checks.add("P" + seat + ":commander+natural-library");
        }
        JsonObject result = new JsonObject();
        result.addProperty("validator", "xmage-native-natural-start-preflight/1.0.0");
        result.addProperty("execution_entry_mode", NATURAL_GAME_START);
        result.addProperty("fail_closed", true);
        result.add("checks", checks);
        result.addProperty("valid", true);
        return result;
    }

    private static void validateCommanders(JsonObject spec, Deck deck, int seat) {
        List<String> requested = new ArrayList<>();
        for (JsonElement element : array(spec, "commander_names")) {
            if (!element.isJsonPrimitive() || !element.getAsJsonPrimitive().isString()) {
                throw fail("INVALID_COMMANDER_OWNERSHIP: commander_names must be strings");
            }
            requested.add(element.getAsString().trim());
        }
        List<String> expected = requested.stream().sorted().toList();
        List<String> nativeDeck = deck.getSideboard().stream().map(Card::getName).sorted().toList();
        if (!expected.equals(nativeDeck)) {
            throw fail("INVALID_COMMANDER_OWNERSHIP: seat=" + seat + " requested=" + expected + " deck=" + nativeDeck);
        }
    }

    private static Map<String, List<Card>> available(Game game, UUID owner) {
        Map<String, List<Card>> result = new HashMap<>();
        for (Card card : game.getCards()) {
            if (card == null || !owner.equals(card.getOwnerId())) continue;
            if (!card.getId().equals(card.getMainCard().getId())) continue;
            result.computeIfAbsent(card.getName(), ignored -> new ArrayList<>()).add(card);
        }
        for (List<Card> cards : result.values()) {
            cards.sort(Comparator.comparing(c -> c.getId().toString()));
        }
        return result;
    }

    private static List<Card> bind(
            JsonArray specs,
            Map<String, List<Card>> available,
            Set<UUID> used,
            Map<UUID, String> semanticMap
    ) {
        List<Card> result = new ArrayList<>();
        for (JsonElement element : specs) {
            JsonObject spec = element.getAsJsonObject();
            Card card = bindOne(spec, available, used);
            semanticMap.put(card.getId(), text(spec, "semantic_id"));
            result.add(card);
        }
        return result;
    }

    private static List<PutToBattlefieldInfo> bindBattlefield(
            JsonArray specs,
            Map<String, List<Card>> available,
            Set<UUID> used,
            Map<UUID, String> semanticMap
    ) {
        List<PutToBattlefieldInfo> result = new ArrayList<>();
        for (JsonElement element : specs) {
            JsonObject spec = element.getAsJsonObject();
            Card card = bindOne(spec, available, used);
            semanticMap.put(card.getId(), text(spec, "semantic_id"));
            result.add(new PutToBattlefieldInfo(card, booleanValue(spec, "tapped", false)));
        }
        return result;
    }

    private static Card bindOne(JsonObject spec, Map<String, List<Card>> available, Set<UUID> used) {
        String name = text(spec, "card_name");
        for (Card card : available.getOrDefault(name, List.of())) {
            if (used.add(card.getId())) return card;
        }
        throw fail("STALE_OBJECT_OR_CARD_REFERENCE: no unused native card for " + name);
    }

    private static JsonObject validateNative(
            Game game,
            List<? extends Player> players,
            Map<Integer, JsonObject> specs,
            Map<UUID, String> semanticMap,
            XmageKnowledgeLedger ledger
    ) {
        JsonObject result = new JsonObject();
        JsonArray checks = new JsonArray();
        for (int zero = 0; zero < players.size(); zero++) {
            Player player = players.get(zero);
            JsonObject spec = specs.get(zero + 1);
            requireNative(player.getLife() == integer(spec, "life"), "life:P" + (zero + 1));
            JsonObject zones = spec.getAsJsonObject("zones");
            validateZone(game, player, optionalArray(zones, "hand"), Zone.HAND, semanticMap);
            validateZone(game, player, optionalArray(zones, "library"), Zone.LIBRARY, semanticMap);
            validateZone(game, player, optionalArray(zones, "graveyard"), Zone.GRAVEYARD, semanticMap);
            validateZone(game, player, optionalArray(zones, "exile"), Zone.EXILED, semanticMap);
            validateBattlefield(game, player, optionalArray(zones, "battlefield"), semanticMap);
            ledger.snapshot(game, player, player); // validate single knowledge authority can reason about the state
            checks.add("P" + (zero + 1) + ":life-zones-knowledge");
        }
        result.addProperty("validator", "xmage-native-state-query/1.0.0");
        result.addProperty("fail_closed", true);
        result.addProperty("semantic_object_count", semanticMap.size());
        result.add("checks", checks);
        result.addProperty("valid", true);
        return result;
    }

    private static void validateZone(
            Game game,
            Player player,
            JsonArray specs,
            Zone expected,
            Map<UUID, String> semanticMap
    ) {
        for (JsonElement element : specs) {
            String semantic = text(element.getAsJsonObject(), "semantic_id");
            UUID id = nativeId(semanticMap, semantic);
            requireNative(expected == game.getState().getZone(id), "zone:" + semantic);
            Card card = game.getCard(id);
            requireNative(card != null && player.getId().equals(card.getOwnerId()), "owner:" + semantic);
        }
    }

    private static void validateBattlefield(
            Game game,
            Player player,
            JsonArray specs,
            Map<UUID, String> semanticMap
    ) {
        for (JsonElement element : specs) {
            JsonObject spec = element.getAsJsonObject();
            String semantic = text(spec, "semantic_id");
            Permanent permanent = game.getPermanent(nativeId(semanticMap, semantic));
            requireNative(permanent != null, "battlefield:" + semantic);
            requireNative(player.getId().equals(permanent.getOwnerId()), "battlefield-owner:" + semantic);
            requireNative(player.getId().equals(permanent.getControllerId()), "battlefield-controller:" + semantic);
            requireNative(permanent.isTapped() == booleanValue(spec, "tapped", false), "battlefield-tapped:" + semantic);
        }
    }

    private static UUID nativeId(Map<UUID, String> map, String semantic) {
        return map.entrySet().stream()
                .filter(e -> semantic.equals(e.getValue()))
                .map(Map.Entry::getKey)
                .findFirst()
                .orElseThrow(() -> fail("NATIVE_VALIDATION_FAILED: stale semantic id " + semantic));
    }

    private static void requireNative(boolean ok, String detail) {
        if (!ok) throw fail("NATIVE_VALIDATION_FAILED: " + detail);
    }

    private static void rejectUnknown(JsonObject object, Set<String> allowed, String context) {
        for (String key : object.keySet()) {
            if (allowed.contains(key)) continue;
            if (EXPLICITLY_UNSUPPORTED.contains(key)) {
                throw fail("UNSUPPORTED_SCENARIO_DIMENSION: " + key);
            }
            throw fail("INVALID_SCENARIO_FIELD: " + context + "." + key);
        }
    }

    private static JsonObject object(JsonObject source, String key) {
        if (!source.has(key) || !source.get(key).isJsonObject()) throw fail("INVALID_SCENARIO: object " + key);
        return source.getAsJsonObject(key);
    }

    private static JsonArray array(JsonObject source, String key) {
        if (!source.has(key) || !source.get(key).isJsonArray()) throw fail("INVALID_SCENARIO: array " + key);
        return source.getAsJsonArray(key);
    }

    private static JsonArray optionalArray(JsonObject source, String key) {
        if (!source.has(key) || source.get(key).isJsonNull()) return new JsonArray();
        if (!source.get(key).isJsonArray()) throw fail("INVALID_SCENARIO: array " + key);
        return source.getAsJsonArray(key);
    }

    private static String text(JsonObject source, String key) {
        if (!source.has(key) || source.get(key).isJsonNull() || !source.get(key).isJsonPrimitive()) {
            throw fail("INVALID_SCENARIO: text " + key);
        }
        String value = source.get(key).getAsString().trim();
        if (value.isEmpty()) throw fail("INVALID_SCENARIO: blank " + key);
        return value;
    }

    private static String optionalText(JsonObject source, String key, String fallback) {
        return !source.has(key) || source.get(key).isJsonNull() ? fallback : source.get(key).getAsString().trim();
    }

    private static long number(JsonObject source, String key) {
        String raw = text(source, key);
        if (!raw.matches("-?\\d+")) throw fail("INVALID_SCENARIO: integer " + key);
        return Long.parseLong(raw);
    }

    private static int integer(JsonObject source, String key) {
        long value = number(source, key);
        if (value < Integer.MIN_VALUE || value > Integer.MAX_VALUE) throw fail("INVALID_SCENARIO: range " + key);
        return (int) value;
    }

    private static boolean booleanValue(JsonObject source, String key, boolean fallback) {
        if (!source.has(key) || source.get(key).isJsonNull()) return fallback;
        if (!source.get(key).isJsonPrimitive() || !source.get(key).getAsJsonPrimitive().isBoolean()) {
            throw fail("INVALID_SCENARIO: boolean " + key);
        }
        return source.get(key).getAsBoolean();
    }

    private static String canonical(JsonElement value) {
        if (value == null || value.isJsonNull() || value.isJsonPrimitive()) return value == null ? "null" : value.toString();
        if (value.isJsonArray()) {
            List<String> items = new ArrayList<>();
            for (JsonElement e : value.getAsJsonArray()) items.add(canonical(e));
            return "[" + String.join(",", items) + "]";
        }
        List<String> keys = new ArrayList<>(value.getAsJsonObject().keySet());
        keys.sort(String::compareTo);
        List<String> fields = new ArrayList<>();
        com.google.gson.Gson gson = new com.google.gson.Gson();
        for (String key : keys) fields.add(gson.toJson(key) + ":" + canonical(value.getAsJsonObject().get(key)));
        return "{" + String.join(",", fields) + "}";
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exc) {
            throw new IllegalStateException(exc);
        }
    }

    private static ScenarioException fail(String message) { return new ScenarioException(message); }
}
