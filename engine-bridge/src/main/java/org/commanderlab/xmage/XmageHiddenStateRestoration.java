package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.effects.common.continuous.BecomesFaceDownCreatureEffect;
import mage.cards.Card;
import mage.game.CommanderFreeForAll;
import mage.game.permanent.Permanent;
import mage.players.Player;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * L7 bounded hidden-state restoration surface.
 *
 * <p>The request is intentionally separate from the historical frozen fixture
 * schema. Old records carry neither a complete library permutation nor an
 * unambiguous face-down type, so they are not silently upgraded. This surface
 * accepts only lossless requests and delegates all mutation to the native Mage
 * RG-06A game-load APIs.</p>
 */
final class XmageHiddenStateRestoration {

    static final String SCHEMA_VERSION = "xmage-hidden-state-request-1.0.0";

    static final class HiddenStateException extends RuntimeException {
        HiddenStateException(String code, String detail) {
            super(code + ": " + detail);
        }
    }

    /** Exact top-to-bottom card-identity sequence for the entire live library. */
    record LibraryOrder(String playerId, List<String> orderedCardIdentities) {
    }

    /** Exact semantic battlefield object plus explicit native face-down type. */
    record FaceDownState(
            String semanticId,
            BecomesFaceDownCreatureEffect.FaceDownType faceDownType
    ) {
    }

    record Request(
            List<LibraryOrder> libraries,
            List<FaceDownState> faceDownStates
    ) {
    }

    record Receipt(
            int librariesRestored,
            int faceDownPermanentsRestored
    ) {
    }

    private XmageHiddenStateRestoration() {
    }

    static Request parse(JsonObject root) {
        if (root == null) {
            throw new HiddenStateException("INVALID_HIDDEN_STATE_REQUEST", "request is null");
        }
        if (!root.has("schema_version")
                || !SCHEMA_VERSION.equals(root.get("schema_version").getAsString())) {
            throw new HiddenStateException(
                    "UNSUPPORTED_HIDDEN_STATE_SCHEMA",
                    root.has("schema_version") ? root.get("schema_version").toString() : "missing");
        }

        List<LibraryOrder> libraries = new ArrayList<>();
        JsonArray libraryRows = root.has("libraries") && root.get("libraries").isJsonArray()
                ? root.getAsJsonArray("libraries") : new JsonArray();
        for (JsonElement element : libraryRows) {
            JsonObject row = element.getAsJsonObject();
            if (!row.has("player_id") || !row.has("ordered_card_identities")
                    || !row.get("ordered_card_identities").isJsonArray()) {
                throw new HiddenStateException(
                        "INVALID_LIBRARY_ORDER", "player_id and ordered_card_identities required");
            }
            List<String> identities = new ArrayList<>();
            for (JsonElement identity : row.getAsJsonArray("ordered_card_identities")) {
                if (!identity.isJsonPrimitive() || !identity.getAsJsonPrimitive().isString()) {
                    throw new HiddenStateException(
                            "INVALID_LIBRARY_ORDER", "library identity must be a string");
                }
                String value = identity.getAsString();
                if (value.isBlank()) {
                    throw new HiddenStateException(
                            "INVALID_LIBRARY_ORDER", "blank library identity");
                }
                identities.add(value);
            }
            libraries.add(new LibraryOrder(
                    row.get("player_id").getAsString(), List.copyOf(identities)));
        }

        List<FaceDownState> faceDown = new ArrayList<>();
        JsonArray faceRows = root.has("face_down") && root.get("face_down").isJsonArray()
                ? root.getAsJsonArray("face_down") : new JsonArray();
        for (JsonElement element : faceRows) {
            JsonObject row = element.getAsJsonObject();
            if (!row.has("semantic_id") || !row.has("face_down_type")) {
                throw new HiddenStateException(
                        "INVALID_FACE_DOWN_STATE", "semantic_id and face_down_type required");
            }
            final BecomesFaceDownCreatureEffect.FaceDownType type;
            try {
                type = BecomesFaceDownCreatureEffect.FaceDownType.valueOf(
                        row.get("face_down_type").getAsString());
            } catch (RuntimeException exc) {
                throw new HiddenStateException(
                        "INVALID_FACE_DOWN_STATE",
                        "unknown face_down_type " + row.get("face_down_type"));
            }
            faceDown.add(new FaceDownState(row.get("semantic_id").getAsString(), type));
        }
        return new Request(List.copyOf(libraries), List.copyOf(faceDown));
    }

    /**
     * Historical frozen records are intentionally not inferred into this
     * request. A library object with only zone_position is not a full
     * permutation; face_down=true does not identify Morph/Manifest/Cloak/etc.
     */
    static Request fromFrozenRecord(JsonObject record) {
        if (record == null || !record.has("semantic_objects")
                || !record.get("semantic_objects").isJsonArray()) {
            throw new HiddenStateException(
                    "INVALID_FROZEN_RECORD", "semantic_objects missing");
        }
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            JsonObject object = element.getAsJsonObject();
            String zone = object.has("zone") ? object.get("zone").getAsString() : "";
            if ("library".equals(zone)) {
                throw new HiddenStateException(
                        "LEGACY_LIBRARY_ORDER_AMBIGUOUS",
                        object.has("semantic_id")
                                ? object.get("semantic_id").getAsString() : "library object");
            }
            if (object.has("face_down") && object.get("face_down").getAsBoolean()) {
                throw new HiddenStateException(
                        "LEGACY_FACE_DOWN_TYPE_AMBIGUOUS",
                        object.has("semantic_id")
                                ? object.get("semantic_id").getAsString() : "face-down object");
            }
        }
        return new Request(List.of(), List.of());
    }

    static Receipt apply(
            CommanderFreeForAll game,
            Map<String, Player> playersByPid,
            XmageNativeStateRestoration restoration,
            Request request
    ) {
        if (game == null || playersByPid == null || restoration == null || request == null) {
            throw new HiddenStateException(
                    "INVALID_HIDDEN_STATE_REQUEST",
                    "game, players, restoration and request are required");
        }
        if (request.libraries() == null || request.faceDownStates() == null) {
            throw new HiddenStateException(
                    "INVALID_HIDDEN_STATE_REQUEST", "request lists must not be null");
        }

        // One face-down object per atomic request. RG-06A itself supports
        // individual objects; limiting the Lab request avoids partial mutation
        // if a later face-down object would fail a native compatibility check.
        if (request.faceDownStates().size() > 1) {
            throw new HiddenStateException(
                    "MULTIPLE_FACE_DOWN_STATES_UNSUPPORTED_ATOMICALLY",
                    Integer.toString(request.faceDownStates().size()));
        }

        Map<String, List<UUID>> preparedLibraries = prepareLibraries(
                game, playersByPid, request.libraries());
        PreparedFaceDown preparedFaceDown = prepareFaceDown(
                game, restoration, request.faceDownStates());

        // Apply the one potentially rules-sensitive face-down request first.
        // The native RG-06A method completes all of its own validation before
        // mutation. Library mutations follow only after full Lab prevalidation.
        if (preparedFaceDown != null) {
            try {
                BecomesFaceDownCreatureEffect.restoreFaceDownStateForGameLoad(
                        preparedFaceDown.permanentId(),
                        preparedFaceDown.type(),
                        game);
            } catch (IllegalArgumentException exc) {
                throw new HiddenStateException(
                        "NATIVE_FACE_DOWN_RESTORE_REJECTED",
                        String.valueOf(exc.getMessage()));
            }
            XmageFullGameStateRedactor.registerRestoredFaceDownIdentity(
                    game,
                    preparedFaceDown.permanentId(),
                    preparedFaceDown.cardIdentity());
        }

        for (Map.Entry<String, List<UUID>> entry : preparedLibraries.entrySet()) {
            Player player = requirePlayer(playersByPid, entry.getKey());
            try {
                player.getLibrary().restoreOrderForGameLoad(entry.getValue(), game);
            } catch (IllegalArgumentException exc) {
                throw new HiddenStateException(
                        "NATIVE_LIBRARY_RESTORE_REJECTED",
                        entry.getKey() + ": " + exc.getMessage());
            }
        }

        XmageNativeStateRestoration.revalidate(game);
        return new Receipt(preparedLibraries.size(), preparedFaceDown == null ? 0 : 1);
    }

    private static Map<String, List<UUID>> prepareLibraries(
            CommanderFreeForAll game,
            Map<String, Player> playersByPid,
            List<LibraryOrder> requests
    ) {
        Map<String, List<UUID>> prepared = new HashMap<>();
        Set<String> seenPlayers = new HashSet<>();
        for (LibraryOrder request : requests) {
            if (request == null || request.playerId() == null
                    || request.playerId().isBlank()
                    || request.orderedCardIdentities() == null) {
                throw new HiddenStateException(
                        "INVALID_LIBRARY_ORDER", "null/blank library request");
            }
            if (!seenPlayers.add(request.playerId())) {
                throw new HiddenStateException(
                        "DUPLICATE_LIBRARY_ORDER", request.playerId());
            }
            Player player = requirePlayer(playersByPid, request.playerId());
            List<UUID> current = new ArrayList<>(player.getLibrary().getCardList());
            if (current.size() != request.orderedCardIdentities().size()) {
                throw new HiddenStateException(
                        "INCOMPLETE_LIBRARY_ORDER",
                        request.playerId() + " requested "
                                + request.orderedCardIdentities().size()
                                + " of " + current.size() + " cards");
            }

            Map<String, List<UUID>> byIdentity = new HashMap<>();
            for (UUID id : current) {
                Card card = game.getCard(id);
                if (card == null) {
                    throw new HiddenStateException(
                            "LIBRARY_CARD_MISSING", request.playerId() + " " + id);
                }
                byIdentity.computeIfAbsent(card.getName(), ignored -> new ArrayList<>()).add(id);
            }
            for (List<UUID> ids : byIdentity.values()) {
                ids.sort(java.util.Comparator.comparing(UUID::toString));
            }

            Map<String, Integer> nextIndex = new HashMap<>();
            List<UUID> ordered = new ArrayList<>(current.size());
            for (String identity : request.orderedCardIdentities()) {
                if (identity == null || identity.isBlank()) {
                    throw new HiddenStateException(
                            "INVALID_LIBRARY_ORDER", "blank card identity");
                }
                List<UUID> candidates = byIdentity.get(identity);
                int index = nextIndex.getOrDefault(identity, 0);
                if (candidates == null || index >= candidates.size()) {
                    throw new HiddenStateException(
                            "LIBRARY_MEMBERSHIP_MISMATCH",
                            request.playerId() + " missing " + identity);
                }
                ordered.add(candidates.get(index));
                nextIndex.put(identity, index + 1);
            }
            for (Map.Entry<String, List<UUID>> entry : byIdentity.entrySet()) {
                if (nextIndex.getOrDefault(entry.getKey(), 0) != entry.getValue().size()) {
                    throw new HiddenStateException(
                            "LIBRARY_MEMBERSHIP_MISMATCH",
                            request.playerId() + " omitted " + entry.getKey());
                }
            }
            prepared.put(request.playerId(), List.copyOf(ordered));
        }
        return Map.copyOf(prepared);
    }

    private static PreparedFaceDown prepareFaceDown(
            CommanderFreeForAll game,
            XmageNativeStateRestoration restoration,
            List<FaceDownState> requests
    ) {
        if (requests.isEmpty()) {
            return null;
        }
        FaceDownState request = requests.get(0);
        if (request == null || request.semanticId() == null || request.semanticId().isBlank()
                || request.faceDownType() == null
                || request.faceDownType() == BecomesFaceDownCreatureEffect.FaceDownType.MANUAL) {
            throw new HiddenStateException(
                    "INVALID_FACE_DOWN_STATE", "explicit non-MANUAL type required");
        }

        UUID permanentId;
        try {
            permanentId = restoration.injectedObjectId(request.semanticId());
        } catch (XmageNativeStateRestoration.RestorationException exc) {
            throw new HiddenStateException(
                    "UNKNOWN_FACE_DOWN_OBJECT", request.semanticId());
        }
        Permanent permanent = game.getPermanent(permanentId);
        if (permanent == null) {
            throw new HiddenStateException(
                    "FACE_DOWN_OBJECT_NOT_BATTLEFIELD", request.semanticId());
        }
        if (permanent.isFaceDown(game)) {
            throw new HiddenStateException(
                    "FACE_DOWN_OBJECT_ALREADY_HIDDEN", request.semanticId());
        }

        String identity = null;
        for (XmageNativeStateRestoration.RequestedObject object : restoration.plan().objects()) {
            if (request.semanticId().equals(object.semanticId())) {
                if (object.zone() != mage.constants.Zone.BATTLEFIELD) {
                    throw new HiddenStateException(
                            "FACE_DOWN_OBJECT_NOT_BATTLEFIELD", request.semanticId());
                }
                identity = object.cardIdentity();
                break;
            }
        }
        if (identity == null || identity.isBlank()) {
            throw new HiddenStateException(
                    "UNKNOWN_FACE_DOWN_OBJECT", request.semanticId());
        }
        return new PreparedFaceDown(permanentId, identity, request.faceDownType());
    }

    private static Player requirePlayer(Map<String, Player> playersByPid, String pid) {
        Player player = playersByPid.get(pid);
        if (player == null) {
            throw new HiddenStateException("UNKNOWN_ACTOR", String.valueOf(pid));
        }
        return player;
    }

    private record PreparedFaceDown(
            UUID permanentId,
            String cardIdentity,
            BecomesFaceDownCreatureEffect.FaceDownType type
    ) {
    }
}
