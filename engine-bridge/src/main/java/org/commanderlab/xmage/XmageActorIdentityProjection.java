package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;
import mage.game.Game;
import mage.players.Player;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;

/**
 * Viewer/session-scoped identity projection for actor-visible XMage material.
 *
 * <p>The knowledge ledger remains the sole visibility authority. Its internal
 * object references are useful as privileged semantic/replay identities, but
 * they must never cross the actor boundary because some of them are derived
 * from deck/card semantics. This class replaces only already-authorized object
 * references with opaque, non-semantic handles. It does not reveal cards,
 * determine legality, or alter Rules RNG.</p>
 *
 * <p>Privileged semantic identities are session-stable for one viewer. Native
 * XMage UUID aliases are deliberately <em>not</em> session-stable: a physical
 * XMage object may retain its UUID across a zone transition while the semantic
 * model advances to a new current incarnation. Native aliases are therefore
 * rebuilt from the current privileged snapshot for every outbound projection.
 * A collision inside one current snapshot still fails closed.</p>
 */
final class XmageActorIdentityProjection {

    private static final Map<Game, SessionState> SESSIONS =
            Collections.synchronizedMap(new WeakHashMap<>());

    private XmageActorIdentityProjection() {
    }

    static JsonObject actorView(Game game, Player viewer, JsonObject privilegedView) {
        if (game == null || viewer == null || privilegedView == null) {
            throw new IllegalArgumentException("game, viewer and privileged view are required");
        }
        SessionState session = SESSIONS.computeIfAbsent(game, ignored -> new SessionState());
        ViewerState state = session.viewer(viewer.getId());
        JsonObject projected = privilegedView.deepCopy();
        registerObjectIds(projected, state);
        replaceKnownRefs(projected, state, Map.of());
        return projected;
    }

    static JsonElement outbound(
            Game game,
            Player viewer,
            JsonObject privilegedActorView,
            JsonElement value
    ) {
        if (value == null) {
            return null;
        }
        SessionState session = SESSIONS.computeIfAbsent(game, ignored -> new SessionState());
        ViewerState state = session.viewer(viewer.getId());
        registerObjectIds(privilegedActorView, state);
        Map<String, String> currentNativeAliases = state.currentNativeAliases(
                XmageDecisionOptionIdentity.visibleNativeToSemantic(game, privilegedActorView)
        );
        JsonElement projected = value.deepCopy();
        replaceKnownRefs(projected, state, currentNativeAliases);
        return projected;
    }

    private static void registerObjectIds(JsonElement element, ViewerState state) {
        if (element == null || element.isJsonNull() || element.isJsonPrimitive()) {
            return;
        }
        if (element.isJsonArray()) {
            for (JsonElement child : element.getAsJsonArray()) {
                registerObjectIds(child, state);
            }
            return;
        }
        JsonObject object = element.getAsJsonObject();
        JsonElement objectId = object.get("object_id");
        if (objectId != null && objectId.isJsonPrimitive()
                && objectId.getAsJsonPrimitive().isString()) {
            state.opaque(objectId.getAsString());
        }
        for (Map.Entry<String, JsonElement> entry : object.entrySet()) {
            registerObjectIds(entry.getValue(), state);
        }
    }

    private static void replaceKnownRefs(
            JsonElement element,
            ViewerState state,
            Map<String, String> currentNativeAliases
    ) {
        if (element == null || element.isJsonNull()) {
            return;
        }
        if (element.isJsonArray()) {
            JsonArray array = element.getAsJsonArray();
            for (int index = 0; index < array.size(); index++) {
                JsonElement child = array.get(index);
                if (child.isJsonPrimitive() && child.getAsJsonPrimitive().isString()) {
                    String replacement = state.lookup(child.getAsString(), currentNativeAliases);
                    if (replacement != null) {
                        array.set(index, new JsonPrimitive(replacement));
                    }
                } else {
                    replaceKnownRefs(child, state, currentNativeAliases);
                }
            }
            return;
        }
        if (element.isJsonPrimitive()) {
            return;
        }
        JsonObject object = element.getAsJsonObject();
        for (String key : java.util.List.copyOf(object.keySet())) {
            JsonElement child = object.get(key);
            if (child != null && child.isJsonPrimitive()
                    && child.getAsJsonPrimitive().isString()) {
                String replacement = state.lookup(child.getAsString(), currentNativeAliases);
                if (replacement != null) {
                    object.addProperty(key, replacement);
                }
            } else {
                replaceKnownRefs(child, state, currentNativeAliases);
            }
        }
    }

    private static final class SessionState {
        private final Map<UUID, ViewerState> viewers = new HashMap<>();

        synchronized ViewerState viewer(UUID viewerId) {
            return viewers.computeIfAbsent(viewerId, ignored -> new ViewerState());
        }
    }

    private static final class ViewerState {
        private final Map<String, String> opaqueByPrivileged = new HashMap<>();

        synchronized String opaque(String privilegedRef) {
            if (privilegedRef == null || privilegedRef.isBlank()) {
                throw new IllegalStateException("ACTOR_IDENTITY_PROJECTION_INVALID_REFERENCE");
            }
            return opaqueByPrivileged.computeIfAbsent(
                    privilegedRef,
                    ignored -> "obj-" + UUID.randomUUID()
            );
        }

        synchronized String lookup(
                String privilegedRef,
                Map<String, String> currentNativeAliases
        ) {
            String direct = opaqueByPrivileged.get(privilegedRef);
            return direct == null ? currentNativeAliases.get(privilegedRef) : direct;
        }

        synchronized Map<String, String> currentNativeAliases(
                Map<String, String> nativeToPrivileged
        ) {
            Map<String, String> aliases = new HashMap<>();
            for (Map.Entry<String, String> entry : nativeToPrivileged.entrySet()) {
                String opaqueReference = opaque(entry.getValue());
                String prior = aliases.putIfAbsent(entry.getKey(), opaqueReference);
                if (prior != null && !prior.equals(opaqueReference)) {
                    throw new IllegalStateException("ACTOR_IDENTITY_PROJECTION_ALIAS_COLLISION");
                }
            }
            return Map.copyOf(aliases);
        }
    }
}
