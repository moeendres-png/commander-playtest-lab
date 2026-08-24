package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.MageItem;
import mage.cards.Card;
import mage.constants.CommanderCardType;
import mage.constants.ManaType;
import mage.counters.CounterType;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.game.stack.StackObject;
import mage.players.Player;

import java.util.Collection;
import java.util.UUID;

/** Actor-scoped XMage state projection. Raw engine objects never leave the JVM. */
final class XmageFullGameStateRedactor {

    private XmageFullGameStateRedactor() {
    }

    static JsonObject actorView(Game game, Player actor) {
        JsonObject view = new JsonObject();
        view.addProperty("game_id", game.getId().toString());
        view.addProperty("actor_id", actor.getId().toString());
        view.addProperty("seat", seat(game, actor.getId()));
        view.addProperty("turn_number", game.getState().getTurnNum());
        addUuid(view, "active_player_id", game.getActivePlayerId());
        addUuid(view, "priority_player_id", game.getPriorityPlayerId());
        if (game.getTurnPhaseType() == null) {
            view.add("phase", JsonNull.INSTANCE);
        } else {
            view.addProperty("phase", game.getTurnPhaseType().name().toLowerCase());
        }
        if (game.getTurnStepType() == null) {
            view.add("step", JsonNull.INSTANCE);
        } else {
            view.addProperty("step", game.getTurnStepType().name().toLowerCase());
        }

        JsonArray players = new JsonArray();
        int currentSeat = 0;
        for (Player player : game.getPlayers().values()) {
            JsonObject p = new JsonObject();
            p.addProperty("player_id", player.getId().toString());
            p.addProperty("seat", currentSeat++);
            p.addProperty("life", player.getLife());
            p.addProperty("poison_counters", player.getCountersCount(CounterType.POISON));
            p.addProperty("hand_count", player.getHand().size());
            p.addProperty("library_count", player.getLibrary().size());
            p.addProperty("graveyard_count", player.getGraveyard().size());
            p.addProperty("has_lost", player.hasLost());
            p.addProperty("has_won", player.hasWon());
            p.addProperty("is_actor", player.getId().equals(actor.getId()));

            JsonArray battlefield = new JsonArray();
            for (Permanent permanent : game.getBattlefield().getAllPermanents()) {
                if (!player.getId().equals(permanent.getControllerId())) {
                    continue;
                }
                JsonObject item = publicPermanent(permanent);
                battlefield.add(item);
            }
            p.add("battlefield", battlefield);

            JsonArray graveyard = new JsonArray();
            for (Card card : player.getGraveyard().getCards(game)) {
                graveyard.add(publicCard(card));
            }
            p.add("graveyard", graveyard);

            JsonArray command = new JsonArray();
            Collection<Card> commanderCards = game.getCommanderCardsFromCommandZone(
                    player,
                    CommanderCardType.COMMANDER_OR_OATHBREAKER
            );
            for (Card card : commanderCards) {
                command.add(publicCard(card));
            }
            p.add("command", command);

            // Exile may contain face-down private cards. Expose only the public count here;
            // card identities are deliberately absent until XMage marks them publicly known.
            p.addProperty("exile_count", game.getExile().getCardsOwned(game, player.getId()).size());

            if (player.getId().equals(actor.getId())) {
                JsonArray hand = new JsonArray();
                for (Card card : player.getHand().getCards(game)) {
                    hand.add(publicCard(card));
                }
                p.add("hand", hand);

                JsonObject mana = new JsonObject();
                mana.addProperty("white", player.getManaPool().get(ManaType.WHITE));
                mana.addProperty("blue", player.getManaPool().get(ManaType.BLUE));
                mana.addProperty("black", player.getManaPool().get(ManaType.BLACK));
                mana.addProperty("red", player.getManaPool().get(ManaType.RED));
                mana.addProperty("green", player.getManaPool().get(ManaType.GREEN));
                mana.addProperty("colorless", player.getManaPool().get(ManaType.COLORLESS));
                p.add("mana_pool", mana);
                p.addProperty(
                        "land_plays_remaining",
                        Math.max(0, player.getLandsPerTurn() - player.getLandsPlayed())
                );
            }
            // Deliberately no opponent hand array and no library card/order array.
            players.add(p);
        }
        view.add("players", players);

        JsonArray stack = new JsonArray();
        for (StackObject stackObject : game.getStack()) {
            JsonObject item = new JsonObject();
            item.addProperty("object_id", stackObject.getId().toString());
            item.addProperty("name", stackObject.getName());
            stack.add(item);
        }
        view.add("stack", stack);
        return view;
    }

    static int seat(Game game, UUID playerId) {
        int seat = 0;
        for (Player player : game.getPlayers().values()) {
            if (player.getId().equals(playerId)) {
                return seat;
            }
            seat++;
        }
        return -1;
    }

    private static JsonObject publicPermanent(Permanent permanent) {
        JsonObject item = new JsonObject();
        item.addProperty("object_id", permanent.getId().toString());
        item.addProperty("name", permanent.getName());
        item.addProperty("controller_id", permanent.getControllerId().toString());
        item.addProperty("tapped", permanent.isTapped());
        return item;
    }

    private static JsonObject publicCard(Card card) {
        JsonObject item = new JsonObject();
        item.addProperty("object_id", card.getId().toString());
        item.addProperty("name", card.getName());
        return item;
    }

    @SuppressWarnings("unused")
    private static JsonArray ids(Collection<? extends MageItem> items) {
        JsonArray result = new JsonArray();
        for (MageItem item : items) {
            result.add(item.getId().toString());
        }
        return result;
    }

    private static void addUuid(JsonObject object, String property, UUID value) {
        if (value == null) {
            object.add(property, JsonNull.INSTANCE);
        } else {
            object.addProperty(property, value.toString());
        }
    }
}
