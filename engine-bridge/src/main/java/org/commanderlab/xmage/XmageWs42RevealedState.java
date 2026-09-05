package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.cards.Cards;
import mage.game.Game;
import mage.game.Revealed;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Qualification-only binding for the WS41 semantic {@code zone=revealed} state.
 *
 * <p>XMage does not model revealed cards as a physical {@code Zone.REVEALED}.
 * Public reveal state is instead native {@link Revealed} state owned by
 * {@link mage.game.GameState}.  WS42 therefore keeps the card in its native
 * storage zone and records semantic {@code revealed} only when this native
 * registry independently proves that the exact bound object is revealed.</p>
 *
 * <p>This class restores snapshot visibility only.  It never computes Magic
 * legality and never chooses a player action.</p>
 */
final class XmageWs42RevealedState {

    private static final String KEY_PREFIX = "ws42-qualification-reveal:";

    private XmageWs42RevealedState() {
    }

    static JsonObject applyAndValidate(
            JsonObject scenario,
            Game game,
            Map<UUID, String> semanticMap
    ) {
        JsonArray requested = optionalArray(scenario, "ws42_revealed_state");
        Map<String, UUID> nativeBySemantic = invert(semanticMap);
        Revealed revealed = game.getState().getRevealed();
        JsonArray readback = new JsonArray();

        for (JsonElement element : requested) {
            if (!element.isJsonObject()) {
                throw fail("WS42_REVEALED_SPEC_NOT_OBJECT");
            }
            JsonObject spec = element.getAsJsonObject();
            if (spec.size() != 1 || !spec.has("semantic_id")
                    || !spec.get("semantic_id").isJsonPrimitive()
                    || !spec.getAsJsonPrimitive("semantic_id").isString()) {
                throw fail("WS42_REVEALED_SPEC_INVALID");
            }
            String semanticId = spec.get("semantic_id").getAsString();
            UUID nativeId = nativeBySemantic.get(semanticId);
            if (nativeId == null) {
                throw fail("WS42_REVEALED_SEMANTIC_OBJECT_MISSING:" + semanticId);
            }
            Card card = game.getCard(nativeId);
            if (card == null) {
                throw fail("WS42_REVEALED_NATIVE_CARD_MISSING:" + semanticId);
            }

            String key = KEY_PREFIX + semanticId;
            Cards existing = revealed.getRevealed(key);
            if (existing != null && !existing.getCards(game).isEmpty()) {
                throw fail("WS42_REVEALED_NATIVE_KEY_PREEXISTED:" + semanticId);
            }
            revealed.createRevealed(key).add(card);

            Card nativeReadback = revealed.getCard(nativeId, game);
            if (nativeReadback == null || !nativeReadback.getMainCard().getId().equals(card.getMainCard().getId())) {
                throw fail("WS42_REVEALED_NATIVE_READBACK_MISMATCH:" + semanticId);
            }

            JsonObject row = new JsonObject();
            row.addProperty("semantic_id", semanticId);
            row.addProperty("native_revealed", true);
            readback.add(row);
        }

        // Complete qualification-namespace check: no extra WS42 reveal entry may
        // exist beyond the explicitly requested semantic objects.
        int qualifiedEntries = 0;
        for (Map.Entry<String, Cards> entry : revealed.entrySet()) {
            if (!entry.getKey().startsWith(KEY_PREFIX)) {
                continue;
            }
            for (Card card : entry.getValue().getCards(game)) {
                qualifiedEntries++;
                String semantic = semanticMap.get(card.getMainCard().getId());
                if (semantic == null || !entry.getKey().equals(KEY_PREFIX + semantic)) {
                    throw fail("WS42_REVEALED_UNREQUESTED_NATIVE_ENTRY:" + entry.getKey());
                }
            }
        }
        if (qualifiedEntries != requested.size()) {
            throw fail("WS42_REVEALED_NATIVE_ENTRY_COUNT_MISMATCH:requested="
                    + requested.size() + ":native=" + qualifiedEntries);
        }

        JsonObject result = new JsonObject();
        result.addProperty("validator", "xmage-ws42-native-revealed-state/1.0.0");
        result.addProperty("native_surface", "GameState.getRevealed");
        result.addProperty("physical_zone_fabricated", false);
        result.add("semantic_revealed_objects", readback);
        result.addProperty("valid", true);
        return result;
    }

    private static Map<String, UUID> invert(Map<UUID, String> semanticMap) {
        Map<String, UUID> result = new LinkedHashMap<>();
        for (Map.Entry<UUID, String> entry : semanticMap.entrySet()) {
            UUID prior = result.put(entry.getValue(), entry.getKey());
            if (prior != null) {
                throw fail("WS42_REVEALED_SEMANTIC_MAPPING_NOT_UNIQUE:" + entry.getValue());
            }
        }
        return result;
    }

    private static JsonArray optionalArray(JsonObject object, String key) {
        if (!object.has(key) || object.get(key).isJsonNull()) {
            return new JsonArray();
        }
        if (!object.get(key).isJsonArray()) {
            throw fail("WS42_REVEALED_STATE_NOT_ARRAY");
        }
        return object.getAsJsonArray(key);
    }

    private static IllegalStateException fail(String message) {
        return new IllegalStateException(message);
    }
}
