package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.counters.Counter;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.game.turn.BeginningPhase;
import mage.game.turn.CombatDamageStep;
import mage.game.turn.CombatPhase;
import mage.game.turn.DeclareAttackersStep;
import mage.game.turn.DeclareBlockersStep;
import mage.game.turn.DrawStep;
import mage.game.turn.Phase;
import mage.game.turn.PostCombatMainPhase;
import mage.game.turn.PostCombatMainStep;
import mage.game.turn.PreCombatMainPhase;
import mage.game.turn.PreCombatMainStep;
import mage.game.turn.UpkeepStep;
import mage.players.Player;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Qualification-only native state-loader extension for WS42.
 *
 * <p>This class never computes Magic legality and never chooses an action. It
 * restores only explicitly requested snapshot fields through XMage's native
 * mutable state APIs, then independently reads those fields back. Runtime
 * rules consequences remain owned by XMage after the setup boundary.</p>
 */
final class XmageWs42NativeStateExtension {

    private XmageWs42NativeStateExtension() {
    }

    static JsonObject applySnapshotDimensions(
            JsonObject scenario,
            Game game,
            List<? extends Player> sessionPlayers,
            Map<UUID, String> semanticMap
    ) {
        Map<String, UUID> nativeBySemantic = invertSemanticMap(semanticMap);
        JsonArray playerSpecs = requireArray(scenario, "players");
        if (playerSpecs.size() != sessionPlayers.size()) {
            throw fail("WS42_NATIVE_EXTENSION_PLAYER_COUNT_MISMATCH");
        }

        // Exact life is restored after the legacy native loader has completed
        // its bootstrap cheat. Zero life is valid at the construction boundary;
        // state-based actions are deliberately not run until native continuation.
        for (JsonElement element : playerSpecs) {
            JsonObject spec = requireObject(element, "player");
            int seat = requireInt(spec, "seat");
            Player player = currentPlayer(game, sessionPlayers, seat);
            int life = requireInt(spec, "life");
            if (life < 0) {
                throw fail("WS42_NEGATIVE_LIFE_NOT_IN_CONTRACT:" + life);
            }
            player.setLife(life, game, null);
        }

        // First pass: controller and counters. Attachments are done only after
        // all permanents have reached their final native controller state.
        for (JsonElement playerElement : playerSpecs) {
            JsonObject playerSpec = requireObject(playerElement, "player");
            JsonObject zones = requireObject(playerSpec.get("zones"), "zones");
            JsonArray battlefield = optionalArray(zones, "battlefield");
            for (JsonElement cardElement : battlefield) {
                JsonObject cardSpec = requireObject(cardElement, "battlefield-card");
                String semanticId = requireString(cardSpec, "semantic_id");
                Permanent permanent = requirePermanent(game, nativeBySemantic, semanticId);
                int ownerSeat = requireInt(playerSpec, "seat");
                int controllerSeat = cardSpec.has("controller_seat") && !cardSpec.get("controller_seat").isJsonNull()
                        ? requireInt(cardSpec, "controller_seat") : ownerSeat;
                Player controller = currentPlayer(game, sessionPlayers, controllerSeat);
                permanent.setControllerId(controller.getId());

                if (cardSpec.has("counters")) {
                    JsonObject counters = requireObject(cardSpec.get("counters"), "counters");
                    permanent.getCounters(game).clear();
                    for (Map.Entry<String, JsonElement> entry : counters.entrySet()) {
                        if (!entry.getValue().isJsonPrimitive() || !entry.getValue().getAsJsonPrimitive().isNumber()) {
                            throw fail("WS42_COUNTER_NOT_INTEGER:" + semanticId + ":" + entry.getKey());
                        }
                        int amount = entry.getValue().getAsInt();
                        if (amount < 0) {
                            throw fail("WS42_NEGATIVE_COUNTER:" + semanticId + ":" + entry.getKey());
                        }
                        if (amount > 0) {
                            permanent.getCounters(game).addCounter(new Counter(entry.getKey(), amount));
                        }
                    }
                }
            }
        }

        for (JsonElement playerElement : playerSpecs) {
            JsonObject playerSpec = requireObject(playerElement, "player");
            JsonObject zones = requireObject(playerSpec.get("zones"), "zones");
            for (JsonElement cardElement : optionalArray(zones, "battlefield")) {
                JsonObject cardSpec = requireObject(cardElement, "battlefield-card");
                if (!cardSpec.has("attached_to") || cardSpec.get("attached_to").isJsonNull()) {
                    continue;
                }
                String semanticId = requireString(cardSpec, "semantic_id");
                String targetSemantic = requireString(cardSpec, "attached_to");
                Permanent permanent = requirePermanent(game, nativeBySemantic, semanticId);
                UUID targetId = nativeBySemantic.get(targetSemantic);
                if (targetId == null || game.getPermanent(targetId) == null) {
                    throw fail("WS42_ATTACHMENT_TARGET_MISSING:" + semanticId + ":" + targetSemantic);
                }
                permanent.attachTo(targetId, null, game);
            }
        }

        return validateSnapshotDimensions(scenario, game, sessionPlayers, semanticMap);
    }

    static JsonObject validateSnapshotDimensions(
            JsonObject scenario,
            Game game,
            List<? extends Player> sessionPlayers,
            Map<UUID, String> semanticMap
    ) {
        Map<String, UUID> nativeBySemantic = invertSemanticMap(semanticMap);
        JsonArray checks = new JsonArray();
        JsonArray playersReadback = new JsonArray();
        JsonArray objectsReadback = new JsonArray();
        JsonArray playerSpecs = requireArray(scenario, "players");

        for (JsonElement element : playerSpecs) {
            JsonObject spec = requireObject(element, "player");
            int seat = requireInt(spec, "seat");
            Player player = currentPlayer(game, sessionPlayers, seat);
            int expectedLife = requireInt(spec, "life");
            requireNative(player.getLife() == expectedLife, "life:P" + seat);
            JsonObject playerRow = new JsonObject();
            playerRow.addProperty("player", "P" + seat);
            playerRow.addProperty("life", player.getLife());
            playersReadback.add(playerRow);

            JsonObject zones = requireObject(spec.get("zones"), "zones");
            for (JsonElement cardElement : optionalArray(zones, "battlefield")) {
                JsonObject cardSpec = requireObject(cardElement, "battlefield-card");
                String semanticId = requireString(cardSpec, "semantic_id");
                Permanent permanent = requirePermanent(game, nativeBySemantic, semanticId);
                int expectedControllerSeat = cardSpec.has("controller_seat") && !cardSpec.get("controller_seat").isJsonNull()
                        ? requireInt(cardSpec, "controller_seat") : seat;
                Player expectedController = currentPlayer(game, sessionPlayers, expectedControllerSeat);
                requireNative(
                        expectedController.getId().equals(permanent.getControllerId()),
                        "controller:" + semanticId
                );

                JsonObject row = new JsonObject();
                row.addProperty("semantic_id", semanticId);
                row.addProperty("controller", "P" + expectedControllerSeat);
                JsonObject counterReadback = new JsonObject();
                JsonObject requestedCounters = cardSpec.has("counters")
                        ? requireObject(cardSpec.get("counters"), "counters") : new JsonObject();
                for (Map.Entry<String, JsonElement> entry : requestedCounters.entrySet()) {
                    int expected = entry.getValue().getAsInt();
                    int actual = permanent.getCounters(game).getCount(entry.getKey());
                    requireNative(actual == expected, "counter:" + semanticId + ":" + entry.getKey());
                    counterReadback.addProperty(entry.getKey(), actual);
                }
                row.add("counters", counterReadback);

                if (cardSpec.has("attached_to") && !cardSpec.get("attached_to").isJsonNull()) {
                    String targetSemantic = requireString(cardSpec, "attached_to");
                    UUID targetId = nativeBySemantic.get(targetSemantic);
                    requireNative(targetId != null && targetId.equals(permanent.getAttachedTo()), "attachment:" + semanticId);
                    row.addProperty("attached_to", targetSemantic);
                }
                objectsReadback.add(row);
            }
            checks.add("P" + seat + ":life-native");
        }

        JsonObject result = new JsonObject();
        result.addProperty("validator", "xmage-ws42-native-state-extension/1.0.0");
        result.addProperty("rules_core_authoritative", true);
        result.addProperty("snapshot_restore_only", true);
        result.addProperty("rules_behavior_credit_granted", false);
        result.add("players", playersReadback);
        result.add("battlefield_objects", objectsReadback);
        result.add("checks", checks);
        result.addProperty("valid", true);
        return result;
    }

    static JsonObject applyTemporalState(
            JsonObject scenario,
            Game game,
            List<? extends Player> players
    ) {
        JsonObject temporal = requireObject(scenario.get("temporal_state"), "temporal_state");
        int turn = requireInt(temporal, "turn_number");
        int activeSeat = playerSeat(requireString(temporal, "active_player"), players.size());
        int prioritySeat = playerSeat(requireString(temporal, "priority_player"), players.size());
        String phaseName = requireString(temporal, "phase");
        String stepName = requireString(temporal, "step");
        if (turn < 1) {
            throw fail("WS42_TEMPORAL_TURN_INVALID:" + turn);
        }

        Phase phase = phaseFor(phaseName, stepName);
        game.getState().getTurn().setPhase(phase);
        game.getState().setTurnNum(turn);
        game.getState().setActivePlayerId(players.get(activeSeat - 1).getId());
        game.getState().setPriorityPlayerId(players.get(prioritySeat - 1).getId());
        game.getState().setPlayerByOrderId(players.get(activeSeat - 1).getId());

        requireNative(game.getState().getTurnNum() == turn, "temporal-turn");
        requireNative(players.get(activeSeat - 1).getId().equals(game.getActivePlayerId()), "temporal-active-player");
        requireNative(players.get(prioritySeat - 1).getId().equals(game.getPriorityPlayerId()), "temporal-priority-player");
        String actualPhase = game.getTurnPhaseType() == null ? "unknown" : game.getTurnPhaseType().name().toLowerCase();
        String actualStep = game.getTurnStepType() == null ? "unknown" : normalizeStep(game.getTurnStepType().name().toLowerCase());
        requireNative(actualPhase.equals(phaseName), "temporal-phase:" + phaseName + ":" + actualPhase);
        requireNative(actualStep.equals(stepName), "temporal-step:" + stepName + ":" + actualStep);

        JsonObject result = new JsonObject();
        result.addProperty("validator", "xmage-ws42-native-temporal-state/1.0.0");
        result.addProperty("turn_number", turn);
        result.addProperty("active_player", "P" + activeSeat);
        result.addProperty("priority_player", "P" + prioritySeat);
        result.addProperty("phase", phaseName);
        result.addProperty("step", stepName);
        result.addProperty("rules_core_authoritative", true);
        result.addProperty("valid", true);
        return result;
    }

    private static Phase phaseFor(String phaseName, String stepName) {
        return switch (phaseName + "/" + stepName) {
            case "precombat_main/main" -> {
                PreCombatMainPhase phase = new PreCombatMainPhase();
                phase.setStep(new PreCombatMainStep());
                yield phase;
            }
            case "postcombat_main/main" -> {
                PostCombatMainPhase phase = new PostCombatMainPhase();
                phase.setStep(new PostCombatMainStep());
                yield phase;
            }
            case "beginning/upkeep" -> {
                BeginningPhase phase = new BeginningPhase();
                phase.setStep(new UpkeepStep());
                yield phase;
            }
            case "beginning/draw" -> {
                BeginningPhase phase = new BeginningPhase();
                phase.setStep(new DrawStep());
                yield phase;
            }
            case "combat/declare_attackers" -> {
                CombatPhase phase = new CombatPhase();
                phase.setStep(new DeclareAttackersStep());
                yield phase;
            }
            case "combat/declare_blockers" -> {
                CombatPhase phase = new CombatPhase();
                phase.setStep(new DeclareBlockersStep());
                yield phase;
            }
            case "combat/combat_damage" -> {
                CombatPhase phase = new CombatPhase();
                phase.setStep(new CombatDamageStep(false));
                yield phase;
            }
            default -> throw fail("WS42_UNSUPPORTED_TEMPORAL_STATE:" + phaseName + "/" + stepName);
        };
    }

    private static String normalizeStep(String value) {
        return switch (value) {
            case "precombat_main", "postcombat_main" -> "main";
            default -> value;
        };
    }

    private static Map<String, UUID> invertSemanticMap(Map<UUID, String> semanticMap) {
        Map<String, UUID> result = new LinkedHashMap<>();
        for (Map.Entry<UUID, String> entry : semanticMap.entrySet()) {
            UUID previous = result.put(entry.getValue(), entry.getKey());
            if (previous != null && !previous.equals(entry.getKey())) {
                throw fail("WS42_DUPLICATE_SEMANTIC_NATIVE_MAPPING:" + entry.getValue());
            }
        }
        return result;
    }

    private static Permanent requirePermanent(Game game, Map<String, UUID> nativeBySemantic, String semanticId) {
        UUID id = nativeBySemantic.get(semanticId);
        Permanent permanent = id == null ? null : game.getPermanent(id);
        if (permanent == null) {
            throw fail("WS42_NATIVE_PERMANENT_MISSING:" + semanticId);
        }
        return permanent;
    }

    private static Player currentPlayer(Game game, List<? extends Player> sessionPlayers, int seat) {
        if (seat < 1 || seat > sessionPlayers.size()) {
            throw fail("WS42_PLAYER_SEAT_INVALID:" + seat);
        }
        Player current = game.getPlayer(sessionPlayers.get(seat - 1).getId());
        if (current == null) {
            throw fail("WS42_CURRENT_PLAYER_MISSING:P" + seat);
        }
        return current;
    }

    private static int playerSeat(String player, int playerCount) {
        if (player == null || !player.matches("P[1-9][0-9]*")) {
            throw fail("WS42_PLAYER_ID_INVALID:" + player);
        }
        int seat = Integer.parseInt(player.substring(1));
        if (seat < 1 || seat > playerCount) {
            throw fail("WS42_PLAYER_ID_OUT_OF_RANGE:" + player);
        }
        return seat;
    }

    private static JsonArray requireArray(JsonObject object, String key) {
        if (object == null || !object.has(key) || !object.get(key).isJsonArray()) {
            throw fail("WS42_JSON_ARRAY_REQUIRED:" + key);
        }
        return object.getAsJsonArray(key);
    }

    private static JsonArray optionalArray(JsonObject object, String key) {
        if (object == null || !object.has(key) || object.get(key).isJsonNull()) {
            return new JsonArray();
        }
        if (!object.get(key).isJsonArray()) {
            throw fail("WS42_JSON_ARRAY_REQUIRED:" + key);
        }
        return object.getAsJsonArray(key);
    }

    private static JsonObject requireObject(JsonElement element, String label) {
        if (element == null || element.isJsonNull() || !element.isJsonObject()) {
            throw fail("WS42_JSON_OBJECT_REQUIRED:" + label);
        }
        return element.getAsJsonObject();
    }

    private static int requireInt(JsonObject object, String key) {
        if (object == null || !object.has(key) || !object.get(key).isJsonPrimitive()
                || !object.get(key).getAsJsonPrimitive().isNumber()) {
            throw fail("WS42_JSON_INTEGER_REQUIRED:" + key);
        }
        return object.get(key).getAsInt();
    }

    private static String requireString(JsonObject object, String key) {
        if (object == null || !object.has(key) || !object.get(key).isJsonPrimitive()
                || !object.get(key).getAsJsonPrimitive().isString()) {
            throw fail("WS42_JSON_STRING_REQUIRED:" + key);
        }
        return object.get(key).getAsString();
    }

    private static void requireNative(boolean condition, String check) {
        if (!condition) {
            throw fail("WS42_NATIVE_VALIDATION_FAILED:" + check);
        }
    }

    private static IllegalStateException fail(String message) {
        return new IllegalStateException(message);
    }
}
