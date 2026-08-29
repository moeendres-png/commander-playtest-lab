package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;
import mage.cards.Card;
import mage.game.Game;
import mage.players.Player;

import java.util.HashSet;
import java.util.Set;

/**
 * Single outbound visibility authority for external-pilot decision material.
 *
 * <p>The state redactor defines actor-visible state. This gateway additionally
 * audits every free-form decision channel (prompt, context, option id/label/
 * metadata and source metadata) before the controller is allowed to publish it.
 * A value that is known only from an opponent hand or a library fails closed.
 * The gateway never synthesizes replacement option identifiers or reconstructs
 * legality.</p>
 */
final class XmageFullGameObservationGateway {

    record SafeDecision(
            JsonObject actorView,
            String prompt,
            JsonObject context,
            JsonArray legalOptions,
            JsonObject sourceObject
    ) {
    }

    private XmageFullGameObservationGateway() {
    }

    static SafeDecision validate(
            Game game,
            Player actor,
            String prompt,
            JsonObject context,
            JsonArray legalOptions,
            JsonObject sourceObject
    ) {
        JsonObject actorView = XmageFullGameStateRedactor.actorView(game, actor);
        VisibilityIndex index = visibilityIndex(game, actor, actorView);

        String safePrompt = prompt == null ? "" : prompt;
        JsonObject safeContext = context == null ? new JsonObject() : context.deepCopy();
        JsonArray safeOptions = legalOptions == null ? new JsonArray() : legalOptions.deepCopy();
        JsonObject safeSource = sourceObject == null ? null : sourceObject.deepCopy();

        assertSafeString("prompt", safePrompt, index);
        assertSafeJson("context", safeContext, index);
        assertSafeJson("legal_options", safeOptions, index);
        if (safeSource != null) {
            assertSafeJson("source_object", safeSource, index);
        }
        return new SafeDecision(actorView, safePrompt, safeContext, safeOptions, safeSource);
    }

    private static VisibilityIndex visibilityIndex(Game game, Player actor, JsonObject actorView) {
        Set<String> visibleObjectIds = new HashSet<>();
        Set<String> visibleNames = new HashSet<>();
        collectVisible(actorView, visibleObjectIds, visibleNames);

        Set<String> hiddenObjectIds = new HashSet<>();
        Set<String> hiddenNames = new HashSet<>();
        for (Player player : game.getPlayers().values()) {
            if (!player.getId().equals(actor.getId())) {
                for (Card card : player.getHand().getCards(game)) {
                    hiddenObjectIds.add(card.getId().toString());
                    addName(hiddenNames, card.getName());
                }
            }
            // Library object identity and order are private even for its owner.
            for (Card card : player.getLibrary().getCards(game)) {
                hiddenObjectIds.add(card.getId().toString());
                addName(hiddenNames, card.getName());
            }
        }

        hiddenObjectIds.removeAll(visibleObjectIds);
        hiddenNames.removeAll(visibleNames);
        return new VisibilityIndex(Set.copyOf(hiddenObjectIds), Set.copyOf(hiddenNames));
    }

    private static void collectVisible(
            JsonElement element,
            Set<String> visibleObjectIds,
            Set<String> visibleNames
    ) {
        if (element == null || element.isJsonNull()) {
            return;
        }
        if (element.isJsonArray()) {
            for (JsonElement item : element.getAsJsonArray()) {
                collectVisible(item, visibleObjectIds, visibleNames);
            }
            return;
        }
        if (!element.isJsonObject()) {
            return;
        }
        JsonObject object = element.getAsJsonObject();
        if (object.has("object_id") && object.get("object_id").isJsonPrimitive()) {
            visibleObjectIds.add(object.get("object_id").getAsString());
        }
        if (object.has("name") && object.get("name").isJsonPrimitive()) {
            addName(visibleNames, object.get("name").getAsString());
        }
        for (String key : object.keySet()) {
            collectVisible(object.get(key), visibleObjectIds, visibleNames);
        }
    }

    private static void assertSafeJson(String path, JsonElement element, VisibilityIndex index) {
        if (element == null || element.isJsonNull()) {
            return;
        }
        if (element.isJsonPrimitive()) {
            JsonPrimitive primitive = element.getAsJsonPrimitive();
            if (primitive.isString()) {
                assertSafeString(path, primitive.getAsString(), index);
            }
            return;
        }
        if (element.isJsonArray()) {
            int i = 0;
            for (JsonElement item : element.getAsJsonArray()) {
                assertSafeJson(path + "[" + i++ + "]", item, index);
            }
            return;
        }
        JsonObject object = element.getAsJsonObject();
        for (String key : object.keySet()) {
            assertSafeJson(path + "." + key, object.get(key), index);
        }
    }

    private static void assertSafeString(String path, String value, VisibilityIndex index) {
        if (value == null || value.isEmpty()) {
            return;
        }
        for (String objectId : index.hiddenObjectIds()) {
            if (value.contains(objectId)) {
                throw new IllegalStateException(
                        "HIDDEN_INFORMATION_LEAK: private object id in " + path
                );
            }
        }
        String folded = value.casefold();
        for (String name : index.privateOnlyNames()) {
            if (!name.isBlank() && folded.contains(name)) {
                throw new IllegalStateException(
                        "HIDDEN_INFORMATION_LEAK: private card identity in " + path
                );
            }
        }
    }

    private static void addName(Set<String> names, String value) {
        if (value != null && !value.isBlank()) {
            names.add(value.casefold());
        }
    }

    private record VisibilityIndex(Set<String> hiddenObjectIds, Set<String> privateOnlyNames) {
    }
}
