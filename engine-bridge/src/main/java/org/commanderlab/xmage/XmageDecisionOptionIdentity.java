package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.CommanderCardType;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.game.stack.StackObject;
import mage.players.Player;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Lossless transport binding between native XMage decision option ids and the
 * semantic identities already emitted by {@link XmageKnowledgeLedger}.
 *
 * <p>This class never decides visibility or legality. It only pairs objects in
 * an already-authorized ledger snapshot with the same native objects XMage used
 * to construct a decision. UUID-shaped option ids that cannot be paired with a
 * visible semantic identity fail closed instead of crossing the production
 * boundary.</p>
 */
final class XmageDecisionOptionIdentity {

    record Binding(JsonArray externalOptions, Map<String, String> externalToNative) {
    }

    private XmageDecisionOptionIdentity() {
    }

    static Binding externalize(Game game, JsonObject actorView, JsonArray nativeOptions) {
        Map<String, String> nativeToExternal = visibleNativeToSemantic(game, actorView);
        Map<String, String> externalToNative = new LinkedHashMap<>();
        JsonArray externalOptions = new JsonArray();

        for (JsonElement element : nativeOptions) {
            if (!element.isJsonObject()) {
                throw blocker("decision option is not an object");
            }
            JsonObject nativeOption = element.getAsJsonObject();
            if (!nativeOption.has("option_id") || nativeOption.get("option_id").isJsonNull()) {
                throw blocker("decision option has no option_id");
            }
            String nativeId = nativeOption.get("option_id").getAsString();
            if (nativeId.isBlank()) {
                throw blocker("decision option has blank option_id");
            }
            String externalId = externalId(nativeId, nativeToExternal);
            String prior = externalToNative.putIfAbsent(externalId, nativeId);
            if (prior != null && !prior.equals(nativeId)) {
                throw blocker("two native XMage options collapse to one semantic option id");
            }
            JsonObject external = nativeOption.deepCopy();
            external.addProperty("option_id", externalId);
            externalOptions.add(external);
        }
        return new Binding(externalOptions, Map.copyOf(externalToNative));
    }

    private static String externalId(String nativeId, Map<String, String> nativeToExternal) {
        UUID uuid;
        try {
            uuid = UUID.fromString(nativeId);
        } catch (IllegalArgumentException ignored) {
            // XMage-independent stable ids (boolean/mode/ability ids, pass, etc.)
            // are already opaque protocol identities and require no object map.
            return nativeId;
        }
        String external = nativeToExternal.get(uuid.toString());
        if (external == null || external.isBlank()) {
            throw blocker("visible semantic identity is unavailable for native object option");
        }
        return external;
    }

    private static Map<String, String> visibleNativeToSemantic(Game game, JsonObject actorView) {
        Map<String, String> result = new LinkedHashMap<>();
        JsonArray playerViews = actorView.getAsJsonArray("players");
        if (playerViews == null) {
            throw blocker("ledger snapshot has no players array");
        }

        for (JsonElement element : playerViews) {
            JsonObject playerView = element.getAsJsonObject();
            int seat = playerView.get("seat").getAsInt();
            Player player = playerAtSeat(game, seat);
            if (player == null) {
                throw blocker("ledger seat cannot be resolved to XMage player");
            }
            String semanticPlayer = playerView.get("player_id").getAsString();
            putUnique(result, player.getId(), semanticPlayer);

            bindCards(result, player.getHand().getCards(game), optionalArray(playerView, "hand"), game);
            bindCards(result, player.getGraveyard().getCards(game), requiredArray(playerView, "graveyard"), game);
            bindCards(
                    result,
                    game.getCommanderCardsFromCommandZone(
                            player,
                            CommanderCardType.COMMANDER_OR_OATHBREAKER
                    ),
                    requiredArray(playerView, "command"),
                    game
            );
            bindCards(
                    result,
                    game.getExile().getCardsOwned(game, player.getId()),
                    requiredArray(playerView, "exile"),
                    game
            );

            List<Permanent> permanents = game.getBattlefield().getAllPermanents().stream()
                    .filter(permanent -> player.getId().equals(permanent.getControllerId()))
                    .toList();
            bindCards(result, permanents, requiredArray(playerView, "battlefield"), game);
        }

        JsonArray stackView = requiredArray(actorView, "stack");
        List<StackObject> stackObjects = new ArrayList<>();
        for (StackObject stackObject : game.getStack()) {
            stackObjects.add(stackObject);
        }
        if (stackObjects.size() != stackView.size()) {
            throw blocker("ledger stack cardinality changed during decision binding");
        }
        for (int index = 0; index < stackObjects.size(); index++) {
            JsonObject semantic = stackView.get(index).getAsJsonObject();
            putUnique(result, stackObjects.get(index).getId(), semantic.get("object_id").getAsString());
        }
        return result;
    }

    private static Player playerAtSeat(Game game, int seat) {
        for (Player player : game.getPlayers().values()) {
            if (XmageFullGameStateRedactor.seat(game, player.getId()) == seat) {
                return player;
            }
        }
        return null;
    }

    private static void bindCards(
            Map<String, String> result,
            Collection<? extends Card> nativeCards,
            JsonArray semanticCards,
            Game game
    ) {
        if (semanticCards == null) {
            return;
        }
        List<? extends Card> nativeList = new ArrayList<>(nativeCards);
        if (nativeList.size() != semanticCards.size()) {
            throw blocker("ledger zone cardinality changed during decision binding");
        }
        for (int index = 0; index < nativeList.size(); index++) {
            Card nativeCard = nativeList.get(index);
            JsonObject semantic = semanticCards.get(index).getAsJsonObject();
            String semanticId = semantic.get("object_id").getAsString();
            putUnique(result, nativeCard.getId(), semanticId);
            putUnique(result, nativeCard.getMainCard().getId(), semanticId);
        }
    }

    private static JsonArray requiredArray(JsonObject object, String property) {
        if (!object.has(property) || !object.get(property).isJsonArray()) {
            throw blocker("ledger snapshot missing array: " + property);
        }
        return object.getAsJsonArray(property);
    }

    private static JsonArray optionalArray(JsonObject object, String property) {
        return object.has(property) && object.get(property).isJsonArray()
                ? object.getAsJsonArray(property)
                : null;
    }

    private static void putUnique(Map<String, String> map, UUID nativeId, String semanticId) {
        if (nativeId == null || semanticId == null || semanticId.isBlank()) {
            return;
        }
        String key = nativeId.toString();
        String prior = map.putIfAbsent(key, semanticId);
        if (prior != null && !prior.equals(semanticId)) {
            throw blocker("one native XMage object maps to multiple semantic identities");
        }
    }

    private static IllegalStateException blocker(String detail) {
        return new IllegalStateException("COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER: " + detail);
    }
}
