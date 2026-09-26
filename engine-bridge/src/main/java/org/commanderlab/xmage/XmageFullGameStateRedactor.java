package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.MageItem;
import mage.abilities.Ability;
import mage.cards.Card;
import mage.constants.CommanderCardType;
import mage.constants.ManaType;
import mage.counters.Counter;
import mage.counters.CounterType;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.game.stack.StackObject;
import mage.players.Player;
import mage.watchers.common.CommanderInfoWatcher;
import mage.watchers.common.CommanderPlaysCountWatcher;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/** Actor-scoped XMage state projection. Raw engine objects never leave the JVM. */
final class XmageFullGameStateRedactor {

    private XmageFullGameStateRedactor() {
    }

    /**
     * WS92-D2 Rules-entitled full-look grants (systemic reacquisition).
     * Paper search/scry/surveil is a look at the library: while a viewer
     * resolves a decision over library-zone cards, the engine alone selected
     * the eligible set and the adapter only projects identities the deciding
     * principal is entitled to see. Grants live only inside the decision
     * window (open before the external request, closed in a finally block);
     * outside a window every granted_library array is empty, so no hidden
     * identity crosses the boundary. Keyed by game id so concurrent games
     * cannot share grants. Read-only projection; no Rules semantics.
     */
    private static final Map<String, Map<String, Set<String>>> ZONE_FULL_LOOK =
            new ConcurrentHashMap<>();

    /**
     * Hidden identity registry for bounded L7 restored face-down permanents.
     * This stores identity only; authorization is derived dynamically from the
     * live native controller relationship. It is not a second permission model.
     */
    private static final Map<String, Map<UUID, String>> RESTORED_FACE_DOWN_IDENTITIES =
            new ConcurrentHashMap<>();

    static void beginZoneFullLook(Player viewer, Player owner, Game game) {
        if (viewer == null || owner == null || game == null) {
            return;
        }
        ZONE_FULL_LOOK
                .computeIfAbsent(game.getId().toString(), ignored -> new ConcurrentHashMap<>())
                .computeIfAbsent(viewer.getId().toString(), ignored -> ConcurrentHashMap.newKeySet())
                .add(owner.getId().toString());
    }

    static void endZoneFullLook(Player viewer, Player owner) {
        if (viewer == null || owner == null) {
            return;
        }
        for (Map<String, Set<String>> byViewer : ZONE_FULL_LOOK.values()) {
            Set<String> owners = byViewer.get(viewer.getId().toString());
            if (owners != null) {
                owners.remove(owner.getId().toString());
            }
        }
    }

    static void registerRestoredFaceDownIdentity(Game game, UUID permanentId, String cardIdentity) {
        if (game == null || permanentId == null || cardIdentity == null || cardIdentity.isBlank()) {
            throw new IllegalArgumentException("face-down identity registration requires game/id/name");
        }
        RESTORED_FACE_DOWN_IDENTITIES
                .computeIfAbsent(game.getId().toString(), ignored -> new ConcurrentHashMap<>())
                .put(permanentId, cardIdentity);
    }

    private static String restoredFaceDownIdentity(Game game, Permanent permanent, Player viewer) {
        if (game == null || permanent == null || viewer == null
                || !permanent.isFaceDown(game)
                || !viewer.getId().equals(permanent.getControllerId())) {
            return null;
        }
        Map<UUID, String> byPermanent =
                RESTORED_FACE_DOWN_IDENTITIES.get(game.getId().toString());
        return byPermanent == null ? null : byPermanent.get(permanent.getId());
    }

    private static boolean hasZoneFullLook(Game game, Player viewer, Player owner) {
        if (game == null || viewer == null || owner == null) {
            return false;
        }
        Map<String, Set<String>> byViewer = ZONE_FULL_LOOK.get(game.getId().toString());
        if (byViewer == null) {
            return false;
        }
        Set<String> owners = byViewer.get(viewer.getId().toString());
        return owners != null && owners.contains(owner.getId().toString());
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
                JsonObject item = publicPermanent(permanent, game, actor);
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

            // WS92-D1 grant-scoped library identities (systemic reacquisition).
            // Populated ONLY while the viewer holds a Rules-entitled full look
            // at this library (D2 window around a library-zone decision);
            // empty otherwise, so no hidden identity crosses the boundary
            // outside the window. Read-only projection; no Rules semantics.
            p.add("granted_library", grantedLibraryView(game, actor, player));

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
        // WS92-D3 public commander facts (systemic reacquisition). Command zone
        // contents are public; commander combat-damage totals are announced by
        // the Rules Core; command-zone cast counts determine the observable
        // commander tax. Read-only adapter projection; no Rules semantics.
        view.add("commander_status", commanderStatusView(game));
        return view;
    }

    /**
     * Global public-only projection. It is derived from the same redactor and
     * then strips every principal-private field. This is the only state allowed
     * to back a public replay/transcript hash.
     */
    static JsonObject publicView(Game game) {
        Player anchor = game.getPlayers().values().stream().findFirst()
                .orElseThrow(() -> new IllegalArgumentException("game has no players"));
        JsonObject view = actorView(game, anchor);
        view.remove("actor_id");
        view.remove("seat");
        for (JsonElement element : view.getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            player.remove("is_actor");
            player.remove("hand");
            player.remove("mana_pool");
            player.remove("land_plays_remaining");
            player.remove("granted_library");
            if (player.has("battlefield") && player.get("battlefield").isJsonArray()) {
                for (JsonElement permanentElement : player.getAsJsonArray("battlefield")) {
                    permanentElement.getAsJsonObject().remove("private_identity");
                }
            }
        }
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

    private static JsonObject publicPermanent(Permanent permanent, Game game, Player viewer) {
        JsonObject item = new JsonObject();
        item.addProperty("object_id", permanent.getId().toString());
        item.addProperty("name", permanent.getName());
        item.addProperty("controller_id", permanent.getControllerId().toString());
        item.addProperty("tapped", permanent.isTapped());
        boolean faceDown = permanent.isFaceDown(game);
        item.addProperty("face_down", faceDown);
        if (faceDown) {
            String privateIdentity = restoredFaceDownIdentity(game, permanent, viewer);
            if (privateIdentity != null) {
                item.addProperty("private_identity", privateIdentity);
            }
        }
        // WS92-D3 public physical characteristics of battlefield permanents
        // (systemic reacquisition). Power/toughness, damage and counters are
        // board-public; ability text is projected only for face-up permanents
        // so face-down identities cannot leak. Read-only; no Rules semantics.
        item.addProperty("power", permanent.getPower().getValue());
        item.addProperty("toughness", permanent.getToughness().getValue());
        item.addProperty("damage", permanent.getDamage());
        JsonArray counters = new JsonArray();
        List<String> counterNames = new ArrayList<>(permanent.getCounters(game).keySet());
        counterNames.sort(String::compareTo);
        for (String counterName : counterNames) {
            Counter counter = permanent.getCounters(game).get(counterName);
            if (counter == null) {
                continue;
            }
            JsonObject entry = new JsonObject();
            entry.addProperty("type", counter.getName());
            entry.addProperty("count", counter.getCount());
            counters.add(entry);
        }
        item.add("counters", counters);
        if (!permanent.isFaceDown(game)) {
            List<String> abilityRules = new ArrayList<>();
            for (Ability ability : permanent.getAbilities(game)) {
                String rule = ability.getRule();
                abilityRules.add(rule == null ? "" : rule);
            }
            abilityRules.sort(String::compareTo);
            JsonArray abilities = new JsonArray();
            abilityRules.forEach(abilities::add);
            item.add("abilities", abilities);
            item.addProperty("ability_count", abilityRules.size());
        } else {
            item.add("abilities", new JsonArray());
            item.addProperty("ability_count", 0);
        }
        return item;
    }

    private static JsonArray grantedLibraryView(Game game, Player viewer, Player owner) {
        JsonArray result = new JsonArray();
        if (!hasZoneFullLook(game, viewer, owner)) {
            return result;
        }
        for (Card card : owner.getLibrary().getCards(game)) {
            result.add(publicCard(card));
        }
        return result;
    }

    private static JsonArray commanderStatusView(Game game) {
        JsonArray result = new JsonArray();
        CommanderPlaysCountWatcher playsWatcher =
                game.getState().getWatcher(CommanderPlaysCountWatcher.class);
        for (Player player : game.getPlayers().values()) {
            // Union of the Rules-Core commander registry and the command-zone
            // cards: identity must survive the commander leaving the zone
            // (damage/tax stay observable), and must exist before registry
            // wiring completes. Read-only; no Rules semantics.
            Map<String, UUID> commanders = new java.util.LinkedHashMap<>();
            try {
                Set<UUID> registered = game.getCommandersIds(
                        player, CommanderCardType.COMMANDER_OR_OATHBREAKER, false);
                if (registered != null) {
                    for (UUID id : registered) {
                        commanders.putIfAbsent(id.toString(), id);
                    }
                }
            } catch (RuntimeException ignored) {
                // Fall through to the command-zone cards.
            }
            try {
                Collection<Card> zoned = game.getCommanderCardsFromCommandZone(
                        player, CommanderCardType.COMMANDER_OR_OATHBREAKER);
                if (zoned != null) {
                    for (Card card : zoned) {
                        if (card != null) {
                            commanders.putIfAbsent(card.getId().toString(), card.getId());
                        }
                    }
                }
            } catch (RuntimeException ignored) {
                // Registry source above already attempted.
            }
            List<UUID> ordered = new ArrayList<>(commanders.values());
            ordered.sort(java.util.Comparator.comparing(UUID::toString));
            for (UUID commanderId : ordered) {
                JsonObject entry = new JsonObject();
                entry.addProperty("owner_id", player.getId().toString());
                Card commanderCard = game.getCard(commanderId);
                entry.addProperty("name",
                        commanderCard == null ? "unknown commander" : commanderCard.getName());
                CommanderInfoWatcher damageWatcher = game.getState()
                        .getWatcher(CommanderInfoWatcher.class, commanderId);
                JsonArray damage = new JsonArray();
                if (damageWatcher != null) {
                    List<UUID> damaged = new ArrayList<>(damageWatcher.getDamageToPlayer().keySet());
                    damaged.sort(java.util.Comparator.comparing(UUID::toString));
                    for (UUID damagedId : damaged) {
                        if (seat(game, damagedId) < 0) {
                            continue;
                        }
                        JsonObject row = new JsonObject();
                        row.addProperty("player_id", damagedId.toString());
                        row.addProperty("total",
                                damageWatcher.getDamageToPlayer().getOrDefault(damagedId, 0));
                        damage.add(row);
                    }
                }
                entry.add("commander_damage_to_player", damage);
                if (playsWatcher == null) {
                    entry.add("casts_from_command", JsonNull.INSTANCE);
                } else {
                    entry.addProperty("casts_from_command",
                            playsWatcher.getPlaysCount(commanderId));
                }
                result.add(entry);
            }
        }
        return result;
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
