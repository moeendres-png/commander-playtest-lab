package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.LookedAt;
import mage.game.ZoneChangeInfo;
import mage.game.combat.Combat;
import mage.game.combat.CombatGroup;
import mage.game.events.ZoneChangeEvent;
import mage.game.permanent.Permanent;
import mage.game.turn.TurnMod;
import mage.players.Player;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * WS46 v1.0.4 construction-only extension for state surfaces not closed by WS42.
 *
 * <p>This class performs no Magic legality in Commander Lab and chooses no
 * action.  It either mutates explicit XMage snapshot state through native
 * structures, derives state from native Rules-Core queries, or constructs a
 * still-pending XMage entry object without executing it.</p>
 */
final class XmageWs46NativeConstructionState {

    private XmageWs46NativeConstructionState() {
    }

    static JsonObject applyAndValidate(
            JsonObject scenario,
            Game game,
            List<? extends Player> players,
            Map<UUID, String> semanticMap,
            XmageKnowledgeLedger knowledgeLedger
    ) {
        Map<String, UUID> nativeBySemantic = invertSemanticMap(semanticMap);
        JsonObject result = new JsonObject();
        result.addProperty("validator", "xmage-ws46-native-construction-state/1.0.0");
        result.addProperty("rules_core_authoritative", true);
        result.addProperty("snapshot_restore_only", true);
        result.addProperty("historical_events_fabricated", false);
        result.addProperty("rules_behavior_credit_granted", false);

        result.add("combat_state", applyCombat(scenario, game, players, semanticMap, nativeBySemantic));
        result.add("extra_turn_creation", applyExtraTurns(scenario, game, players));
        result.add("elimination_trigger", validateEliminationEntry(scenario, game, players));
        result.add("knowledge_state", applyKnowledge(scenario, game, players, nativeBySemantic, knowledgeLedger));
        result.add("zone_move_event", prepareZoneMoveEntry(scenario, game, players, semanticMap, nativeBySemantic));
        result.addProperty("valid", true);
        return result;
    }

    private static JsonObject applyCombat(
            JsonObject scenario,
            Game game,
            List<? extends Player> players,
            Map<UUID, String> semanticMap,
            Map<String, UUID> nativeBySemantic
    ) {
        JsonObject result = new JsonObject();
        JsonObject requested = optionalObject(scenario, "ws42_combat_state");
        if (requested == null || requested.size() == 0) {
            result.addProperty("present", false);
            result.addProperty("valid", true);
            return result;
        }

        JsonObject temporal = requireObject(scenario.get("temporal_state"), "temporal_state");
        int activeSeat = playerSeat(requireString(temporal, "active_player"), players.size());
        Player attacker = currentPlayer(game, players, activeSeat);
        Combat combat = game.getCombat();
        combat.clear();
        combat.setAttacker(attacker.getId());
        combat.setDefenders(game);

        JsonObject attackers = optionalObject(requested, "attackers");
        if (attackers != null) {
            for (Map.Entry<String, JsonElement> entry : attackers.entrySet()) {
                UUID attackerId = requireSemanticNative(nativeBySemantic, entry.getKey());
                UUID defenderId = resolveDefender(entry.getValue().getAsString(), game, players, nativeBySemantic);
                if (!combat.addAttackerToCombat(attackerId, defenderId, game)) {
                    throw fail("WS46_COMBAT_ADD_ATTACKER_FAILED:" + entry.getKey() + ":" + entry.getValue().getAsString());
                }
            }
        }

        JsonObject blockers = optionalObject(requested, "blockers");
        if (blockers != null) {
            for (Map.Entry<String, JsonElement> entry : blockers.entrySet()) {
                UUID blockerId = requireSemanticNative(nativeBySemantic, entry.getKey());
                UUID attackerId = requireSemanticNative(nativeBySemantic, entry.getValue().getAsString());
                CombatGroup group = combat.findGroup(attackerId);
                Permanent blocker = game.getPermanent(blockerId);
                if (group == null || blocker == null || blocker.getControllerId() == null) {
                    throw fail("WS46_COMBAT_BLOCKER_MAPPING_FAILED:" + entry.getKey());
                }
                group.addBlockerToGroup(blockerId, blocker.getControllerId(), game);
            }
        }

        JsonObject readback = readCombat(game, players, semanticMap);
        readback.addProperty("present", true);
        readback.addProperty("historical_declare_events_fabricated", false);
        readback.addProperty("valid", true);
        return readback;
    }

    private static JsonObject readCombat(
            Game game,
            List<? extends Player> players,
            Map<UUID, String> semanticMap
    ) {
        Combat combat = game.getCombat();
        JsonObject attackers = new JsonObject();
        JsonObject blockers = new JsonObject();
        JsonArray unblocked = new JsonArray();
        Set<String> eligibleAttackers = new LinkedHashSet<>();
        Set<String> eligibleBlockers = new LinkedHashSet<>();

        for (CombatGroup group : combat.getGroups()) {
            String defender = playerOrSemanticRef(group.getDefenderId(), players, semanticMap);
            for (UUID attackerId : group.getAttackers()) {
                String attackerSemantic = requireSemanticRef(semanticMap, attackerId);
                attackers.addProperty(attackerSemantic, defender);
                if (group.getBlockers().isEmpty()) {
                    unblocked.add(attackerSemantic);
                }
                for (UUID blockerId : group.getBlockers()) {
                    String blockerSemantic = requireSemanticRef(semanticMap, blockerId);
                    blockers.addProperty(blockerSemantic, attackerSemantic);
                }
            }
        }

        Player attackingPlayer = game.getPlayer(game.getActivePlayerId());
        if (attackingPlayer == null) {
            JsonObject temporalAttacker = new JsonObject();
            // Native temporal state is applied by WS42 immediately after this
            // extension.  For construction legality discovery use Combat's own
            // attacker identity if active-player state is not yet installed.
            for (Player player : players) {
                for (UUID defender : combat.getDefenders()) {
                    if (player.getAvailableAttackers(defender, game).stream().anyMatch(p -> semanticMap.containsKey(p.getId()))) {
                        attackingPlayer = player;
                        break;
                    }
                }
                if (attackingPlayer != null) break;
            }
        }
        if (attackingPlayer != null) {
            for (UUID defender : combat.getDefenders()) {
                for (Permanent permanent : attackingPlayer.getAvailableAttackers(defender, game)) {
                    String semantic = semanticMap.get(permanent.getId());
                    if (semantic != null) eligibleAttackers.add(semantic);
                }
            }
        }

        Set<UUID> nativeAttackers = combat.getAttackers();
        for (Player player : players) {
            if (attackingPlayer != null && player.getId().equals(attackingPlayer.getId())) continue;
            for (Permanent blocker : player.getAvailableBlockers(game)) {
                boolean canBlock = nativeAttackers.isEmpty();
                for (UUID attackerId : nativeAttackers) {
                    if (blocker.canBlock(attackerId, game)) {
                        canBlock = true;
                        break;
                    }
                }
                if (canBlock) {
                    String semantic = semanticMap.get(blocker.getId());
                    if (semantic != null) eligibleBlockers.add(semantic);
                }
            }
        }

        JsonObject result = new JsonObject();
        result.add("attackers", attackers);
        result.add("blockers", blockers);
        JsonArray ea = new JsonArray();
        eligibleAttackers.forEach(ea::add);
        result.add("eligible_attackers", ea);
        JsonArray eb = new JsonArray();
        eligibleBlockers.forEach(eb::add);
        result.add("eligible_blockers", eb);
        result.add("unblocked_attackers", unblocked.deepCopy());
        result.add("unblocked", unblocked.deepCopy());
        result.addProperty("native_surface", "GameState.Combat/CombatGroup");
        return result;
    }

    private static JsonObject applyExtraTurns(JsonObject scenario, Game game, List<? extends Player> players) {
        JsonArray requested = optionalArray(scenario, "ws42_extra_turn_creation");
        JsonArray readback = new JsonArray();
        if (requested.size() == 0) {
            JsonObject result = new JsonObject();
            result.addProperty("present", false);
            result.add("resolutions", readback);
            result.addProperty("valid", true);
            return result;
        }

        int expectedSequence = 1;
        for (JsonElement element : requested) {
            JsonObject spec = requireObject(element, "extra-turn-resolution");
            int sequence = requireInt(spec, "sequence");
            if (sequence != expectedSequence++) {
                throw fail("WS46_EXTRA_TURN_SEQUENCE_NONCONTIGUOUS:" + sequence);
            }
            int seat = playerSeat(requireString(spec, "player"), players.size());
            String source = requireString(spec, "source");
            TurnMod mod = new TurnMod(currentPlayer(game, players, seat).getId())
                    .withExtraTurn()
                    .withTag("WS46_EXTRA_TURN:" + sequence + ":" + source);
            game.getState().getTurnMods().add(mod);
        }

        for (TurnMod mod : game.getState().getTurnMods()) {
            if (!mod.isExtraTurn() || mod.getTag() == null || !mod.getTag().startsWith("WS46_EXTRA_TURN:")) continue;
            String[] parts = mod.getTag().split(":", 3);
            if (parts.length != 3) throw fail("WS46_EXTRA_TURN_TAG_INVALID:" + mod.getTag());
            JsonObject row = new JsonObject();
            row.addProperty("sequence", Integer.parseInt(parts[1]));
            row.addProperty("source", parts[2]);
            row.addProperty("player", playerRef(mod.getPlayerId(), players));
            row.addProperty("native_extra_turn", true);
            readback.add(row);
        }
        JsonObject result = new JsonObject();
        result.addProperty("present", true);
        result.addProperty("native_surface", "GameState.turnMods/TurnMod");
        result.add("resolutions", readback);
        result.addProperty("historical_spell_resolution_events_fabricated", false);
        result.addProperty("valid", readback.size() == requested.size());
        if (readback.size() != requested.size()) throw fail("WS46_EXTRA_TURN_READBACK_COUNT_MISMATCH");
        return result;
    }

    private static JsonObject validateEliminationEntry(JsonObject scenario, Game game, List<? extends Player> players) {
        JsonObject requested = optionalObject(scenario, "ws42_elimination_trigger");
        JsonObject result = new JsonObject();
        if (requested == null || requested.size() == 0) {
            result.addProperty("present", false);
            result.addProperty("valid", true);
            return result;
        }
        String playerRef = requireString(requested, "player");
        int seat = playerSeat(playerRef, players.size());
        Player player = currentPlayer(game, players, seat);
        String condition = requireString(requested, "condition");
        if (!"life_total_0".equals(condition)) {
            throw fail("WS46_ELIMINATION_CONDITION_UNSUPPORTED:" + condition);
        }
        if (player.getLife() != 0 || player.hasLost()) {
            throw fail("WS46_ELIMINATION_NATIVE_BOUNDARY_MISMATCH:" + playerRef + ":life=" + player.getLife() + ":lost=" + player.hasLost());
        }
        result.addProperty("present", true);
        result.addProperty("player", playerRef);
        result.addProperty("condition", "life_total_0");
        result.addProperty("native_life", player.getLife());
        result.addProperty("native_player_already_lost", player.hasLost());
        result.addProperty("sba_not_preexecuted", true);
        result.addProperty("native_surface", "Player.life + GameImpl.stateBasedActions");
        result.addProperty("valid", true);
        return result;
    }

    private static JsonObject applyKnowledge(
            JsonObject scenario,
            Game game,
            List<? extends Player> players,
            Map<String, UUID> nativeBySemantic,
            XmageKnowledgeLedger ledger
    ) {
        JsonObject requested = optionalObject(scenario, "ws42_knowledge_state");
        JsonObject result = new JsonObject();
        if (requested == null || requested.size() == 0) {
            result.addProperty("present", false);
            result.addProperty("valid", true);
            return result;
        }

        for (JsonElement viewerElement : optionalArray(requested, "viewer_states")) {
            JsonObject viewerState = requireObject(viewerElement, "knowledge-viewer");
            int metadataViewerSeat = playerSeat(requireString(viewerState, "viewer"), players.size());
            Player metadataViewer = currentPlayer(game, players, metadataViewerSeat);

            for (JsonElement idElement : optionalArray(viewerState, "known_object_identities")) {
                String semantic = idElement.getAsString();
                Card card = requireCard(game, nativeBySemantic, semantic);
                game.getState().getLookedAt(metadataViewer.getId()).createLookedAt("WS46 known identity").add(card);
            }

            for (JsonElement grantElement : optionalArray(viewerState, "face_down_look_permissions")) {
                JsonObject grant = requireObject(grantElement, "face-down-look");
                int viewerSeat = playerSeat(requireString(grant, "viewer"), players.size());
                Player viewer = currentPlayer(game, players, viewerSeat);
                Card card = requireCard(game, nativeBySemantic, requireString(grant, "object"));
                game.getState().getLookedAt(viewer.getId()).createLookedAt("WS46 face-down look").add(card);
            }

            for (JsonElement rangeElement : optionalArray(viewerState, "known_library_ranges")) {
                JsonObject range = requireObject(rangeElement, "known-library-range");
                int viewerSeat = playerSeat(requireString(range, "viewer"), players.size());
                int ownerSeat = playerSeat(requireString(range, "player"), players.size());
                int start = requireInt(range, "start");
                int count = requireInt(range, "count");
                Player viewer = currentPlayer(game, players, viewerSeat);
                Player owner = currentPlayer(game, players, ownerSeat);
                List<UUID> order = owner.getLibrary().getCardList();
                if (start < 0 || count < 0 || start + count > order.size()) {
                    throw fail("WS46_KNOWLEDGE_LIBRARY_RANGE_INVALID:P" + ownerSeat + ":" + start + ":" + count);
                }
                LookedAt lookedAt = game.getState().getLookedAt(viewer.getId());
                for (int index = start; index < start + count; index++) {
                    Card card = game.getCard(order.get(index));
                    if (card == null) throw fail("WS46_KNOWLEDGE_LIBRARY_CARD_MISSING:" + index);
                    lookedAt.createLookedAt("WS46 known library range").add(card);
                }
            }

            for (JsonElement permissionElement : optionalArray(viewerState, "temporary_permissions")) {
                JsonObject permission = requireObject(permissionElement, "temporary-permission");
                String kind = requireString(permission, "permission");
                if (permission.has("object")) {
                    Card card = requireCard(game, nativeBySemantic, requireString(permission, "object"));
                    String viewerRef = requireString(permission, "viewer");
                    if ("reveal".equals(kind) && "ALL_PLAYERS".equals(viewerRef)) {
                        game.getState().getRevealed().createRevealed("WS46 temporary reveal").add(card);
                    } else if ("look".equals(kind) || "look_at_face_down_exile".equals(kind)) {
                        int viewerSeat = playerSeat(viewerRef, players.size());
                        Player viewer = currentPlayer(game, players, viewerSeat);
                        game.getState().getLookedAt(viewer.getId()).createLookedAt("WS46 temporary look").add(card);
                    } else {
                        throw fail("WS46_KNOWLEDGE_OBJECT_PERMISSION_UNSUPPORTED:" + kind + ":" + viewerRef);
                    }
                } else if ("search".equals(kind) && permission.has("zone")) {
                    String zone = requireString(permission, "zone");
                    int viewerSeat = playerSeat(requireString(permission, "viewer"), players.size());
                    String expectedZone = "P" + viewerSeat + ".library";
                    if (!expectedZone.equals(zone)) throw fail("WS46_KNOWLEDGE_SEARCH_ZONE_UNSUPPORTED:" + zone);
                    Player viewer = currentPlayer(game, players, viewerSeat);
                    ledger.beginZoneFullLook(viewer, viewer, game);
                } else if (permission.has("controlled_player") && permission.has("controller")) {
                    int controlledSeat = playerSeat(requireString(permission, "controlled_player"), players.size());
                    int controllerSeat = playerSeat(requireString(permission, "controller"), players.size());
                    currentPlayer(game, players, controlledSeat).setTurnControlledBy(currentPlayer(game, players, controllerSeat).getId());
                } else {
                    throw fail("WS46_KNOWLEDGE_PERMISSION_UNSUPPORTED:" + permission);
                }
            }
        }

        // Force the existing provider visibility authority to harvest native
        // Revealed/LookedAt state and expose request-independent actor views.
        JsonArray actorViews = new JsonArray();
        for (Player viewer : players) {
            actorViews.add(ledger.snapshot(game, viewer, viewer));
        }
        result.addProperty("present", true);
        result.addProperty("native_surfaces", "GameState.Revealed+LookedAt+Player.turnController+XmageKnowledgeLedger");
        result.add("actor_views", actorViews);
        result.addProperty("whole_requested_knowledge_state_copied_as_proof", false);
        result.addProperty("valid", true);
        return result;
    }

    private static JsonObject prepareZoneMoveEntry(
            JsonObject scenario,
            Game game,
            List<? extends Player> players,
            Map<UUID, String> semanticMap,
            Map<String, UUID> nativeBySemantic
    ) {
        JsonObject entry = optionalObject(scenario, "ws46_zone_move_entry");
        JsonObject result = new JsonObject();
        if (entry == null || entry.size() == 0) {
            result.addProperty("present", false);
            result.addProperty("valid", true);
            return result;
        }
        String semanticId = requireString(entry, "semantic_id");
        UUID nativeId = requireSemanticNative(nativeBySemantic, semanticId);
        Permanent permanent = game.getPermanent(nativeId);
        if (permanent == null) throw fail("WS46_ZONE_MOVE_PERMANENT_MISSING:" + semanticId);
        int ownerSeat = playerSeat(requireString(entry, "owner"), players.size());
        Player owner = currentPlayer(game, players, ownerSeat);
        Zone from = zone(requireString(entry, "from"));
        Zone to = zone(requireString(entry, "to"));
        if (game.getState().getZone(nativeId) != from) {
            throw fail("WS46_ZONE_MOVE_NATIVE_SOURCE_ZONE_MISMATCH:" + semanticId + ":" + game.getState().getZone(nativeId) + ":" + from);
        }

        ZoneChangeEvent event = new ZoneChangeEvent(permanent, null, owner.getId(), from, to);
        ZoneChangeInfo info = to == Zone.LIBRARY ? new ZoneChangeInfo.Library(event, true) : new ZoneChangeInfo(event);

        // Read back solely from the constructed XMage entry object. Do not run
        // ZonesHandler here; replacement effects and Commander SBA choices are
        // behavior obligations and must execute only on resume.
        result.addProperty("present", true);
        result.addProperty("commander_id", requireString(entry, "commander_id"));
        result.addProperty("semantic_id", requireSemanticRef(semanticMap, event.getTargetId()));
        result.addProperty("owner", playerRef(event.getPlayerId(), players));
        result.addProperty("from", zoneName(event.getFromZone()));
        result.addProperty("to", zoneName(event.getToZone()));
        result.addProperty("commander_choice_timing", requireString(entry, "commander_choice_timing"));
        result.addProperty("pending_not_executed", true);
        result.addProperty("native_entry_class", info.getClass().getName());
        result.addProperty("historical_zone_change_event_fabricated", false);
        result.addProperty("valid", true);
        return result;
    }

    private static Zone zone(String value) {
        return switch (value) {
            case "battlefield" -> Zone.BATTLEFIELD;
            case "graveyard" -> Zone.GRAVEYARD;
            case "exile" -> Zone.EXILED;
            case "hand" -> Zone.HAND;
            case "library" -> Zone.LIBRARY;
            case "command" -> Zone.COMMAND;
            default -> throw fail("WS46_ZONE_UNSUPPORTED:" + value);
        };
    }

    private static String zoneName(Zone zone) {
        return zone == Zone.EXILED ? "exile" : zone.name().toLowerCase();
    }

    private static UUID resolveDefender(String ref, Game game, List<? extends Player> players, Map<String, UUID> nativeBySemantic) {
        if (ref.matches("P[1-9][0-9]*")) return currentPlayer(game, players, playerSeat(ref, players.size())).getId();
        return requireSemanticNative(nativeBySemantic, ref);
    }

    private static String playerOrSemanticRef(UUID id, List<? extends Player> players, Map<UUID, String> semanticMap) {
        for (int index = 0; index < players.size(); index++) {
            if (players.get(index).getId().equals(id)) return "P" + (index + 1);
        }
        return requireSemanticRef(semanticMap, id);
    }

    private static String playerRef(UUID id, List<? extends Player> players) {
        for (int index = 0; index < players.size(); index++) {
            if (players.get(index).getId().equals(id)) return "P" + (index + 1);
        }
        throw fail("WS46_PLAYER_NATIVE_ID_UNKNOWN:" + id);
    }

    private static Map<String, UUID> invertSemanticMap(Map<UUID, String> semanticMap) {
        Map<String, UUID> result = new LinkedHashMap<>();
        for (Map.Entry<UUID, String> entry : semanticMap.entrySet()) {
            UUID previous = result.put(entry.getValue(), entry.getKey());
            if (previous != null && !previous.equals(entry.getKey())) throw fail("WS46_DUPLICATE_SEMANTIC_MAPPING:" + entry.getValue());
        }
        return result;
    }

    private static UUID requireSemanticNative(Map<String, UUID> nativeBySemantic, String semantic) {
        UUID id = nativeBySemantic.get(semantic);
        if (id == null) throw fail("WS46_SEMANTIC_NATIVE_MAPPING_MISSING:" + semantic);
        return id;
    }

    private static String requireSemanticRef(Map<UUID, String> semanticMap, UUID id) {
        String semantic = semanticMap.get(id);
        if (semantic == null) throw fail("WS46_NATIVE_SEMANTIC_MAPPING_MISSING:" + id);
        return semantic;
    }

    private static Card requireCard(Game game, Map<String, UUID> nativeBySemantic, String semantic) {
        UUID id = requireSemanticNative(nativeBySemantic, semantic);
        Card card = game.getCard(id);
        if (card == null) {
            Permanent permanent = game.getPermanent(id);
            if (permanent != null) card = permanent;
        }
        if (card == null) throw fail("WS46_NATIVE_CARD_MISSING:" + semantic);
        return card;
    }

    private static Player currentPlayer(Game game, List<? extends Player> players, int seat) {
        if (seat < 1 || seat > players.size()) throw fail("WS46_PLAYER_SEAT_INVALID:" + seat);
        Player player = game.getPlayer(players.get(seat - 1).getId());
        if (player == null) throw fail("WS46_CURRENT_PLAYER_MISSING:P" + seat);
        return player;
    }

    private static int playerSeat(String ref, int count) {
        if (ref == null || !ref.matches("P[1-9][0-9]*")) throw fail("WS46_PLAYER_REF_INVALID:" + ref);
        int seat = Integer.parseInt(ref.substring(1));
        if (seat < 1 || seat > count) throw fail("WS46_PLAYER_REF_OUT_OF_RANGE:" + ref);
        return seat;
    }

    private static JsonObject optionalObject(JsonObject object, String key) {
        if (object == null || !object.has(key) || object.get(key).isJsonNull()) return null;
        if (!object.get(key).isJsonObject()) throw fail("WS46_JSON_OBJECT_REQUIRED:" + key);
        return object.getAsJsonObject(key);
    }

    private static JsonArray optionalArray(JsonObject object, String key) {
        if (object == null || !object.has(key) || object.get(key).isJsonNull()) return new JsonArray();
        if (!object.get(key).isJsonArray()) throw fail("WS46_JSON_ARRAY_REQUIRED:" + key);
        return object.getAsJsonArray(key);
    }

    private static JsonObject requireObject(JsonElement element, String label) {
        if (element == null || element.isJsonNull() || !element.isJsonObject()) throw fail("WS46_JSON_OBJECT_REQUIRED:" + label);
        return element.getAsJsonObject();
    }

    private static String requireString(JsonObject object, String key) {
        if (object == null || !object.has(key) || !object.get(key).isJsonPrimitive() || !object.get(key).getAsJsonPrimitive().isString()) {
            throw fail("WS46_JSON_STRING_REQUIRED:" + key);
        }
        return object.get(key).getAsString();
    }

    private static int requireInt(JsonObject object, String key) {
        if (object == null || !object.has(key) || !object.get(key).isJsonPrimitive() || !object.get(key).getAsJsonPrimitive().isNumber()) {
            throw fail("WS46_JSON_INTEGER_REQUIRED:" + key);
        }
        return object.get(key).getAsInt();
    }

    private static IllegalStateException fail(String message) {
        return new IllegalStateException(message);
    }
}
