package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.MageItem;
import mage.abilities.Ability;
import mage.cards.Card;
import mage.constants.AsThoughEffectType;
import mage.constants.CommanderCardType;
import mage.constants.ManaType;
import mage.counters.Counter;
import mage.counters.CounterType;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.game.stack.Spell;
import mage.game.stack.StackObject;
import mage.players.Player;
import mage.watchers.common.CommanderInfoWatcher;
import mage.watchers.common.CommanderPlaysCountWatcher;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

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

    /**
     * F-26 principal-scoped observation log. XMage keeps looked-at and
     * revealed cards only until the next client update, so the player hooks
     * record the engine's own look/reveal calls here. A look is visible to
     * the looking principal and, under CR 723.4, the principal controlling that
     * player when the look occurs; a reveal is public to every principal. Card
     * names only (no object ids), in engine call order. Keyed by game id.
     */
    private static final Map<String, List<ObservedCards>> OBSERVED_CARDS =
            new ConcurrentHashMap<>();

    private static final class ObservedCards {
        private final boolean revealed;
        private final UUID principalId;
        private final UUID controllerId;
        private final int turn;
        private final String title;
        private final List<String> names;
        private final List<UUID> owners;

        private ObservedCards(boolean revealed, UUID principalId, UUID controllerId, int turn,
                              String title, List<String> names, List<UUID> owners) {
            this.revealed = revealed;
            this.principalId = principalId;
            this.controllerId = controllerId;
            this.turn = turn;
            this.title = title;
            this.names = names;
            this.owners = owners;
        }
    }

    /** {@code title} is the engine's own window title for the look (CardUtil). */
    static void recordLookedAt(Game game, UUID viewerId, String title, Collection<Card> cards) {
        record(game, false, viewerId, title, cards, false);
    }

    /**
     * {@code update} mirrors XMage's own split: a logged reveal is a new
     * event (Revealed.add), an unlogged one refreshes a standing display
     * such as a hand played revealed (Revealed.update) and so replaces the
     * earlier entry of the same revealer and title instead of appending.
     */
    static void recordRevealed(Game game, UUID revealerId, String title, Collection<Card> cards,
                               boolean update) {
        record(game, true, revealerId, title, cards, update);
    }

    private static void record(Game game, boolean revealed, UUID principalId, String title,
                               Collection<Card> cards, boolean update) {
        if (game == null || principalId == null || cards == null || cards.isEmpty()) {
            return;
        }
        List<String> names = new ArrayList<>();
        List<UUID> owners = new ArrayList<>();
        for (Card card : cards) {
            names.add(card.getName());
            owners.add(card.getOwnerId());
        }
        List<ObservedCards> log = OBSERVED_CARDS
                .computeIfAbsent(game.getId().toString(), ignored -> new CopyOnWriteArrayList<>());
        ObservedCards entry = new ObservedCards(
                revealed,
                principalId,
                turnController(game, principalId),
                game.getState().getTurnNum(),
                title,
                names,
                owners
        );
        if (update) {
            log.removeIf(old -> old.revealed == revealed && old.principalId.equals(principalId)
                    && Objects.equals(old.title, title));
        } else if (!revealed) {
            // A standing "look at the top card any time" repeats the same look
            // every time effects apply; only a look that shows something new
            // (a different card set from the same source) is recorded again.
            for (int i = log.size() - 1; i >= 0; i--) {
                ObservedCards old = log.get(i);
                if (!old.revealed && old.principalId.equals(principalId)
                        && Objects.equals(old.title, title)) {
                    if (old.names.equals(names) && old.owners.equals(owners)) {
                        return;
                    }
                    break;
                }
            }
        }
        log.add(entry);
    }

    /** Controller of this principal at this instant, excluding ordinary self-control. */
    private static UUID turnController(Game game, UUID principalId) {
        if (game == null || principalId == null) {
            return null;
        }
        Player principal = game.getPlayer(principalId);
        if (principal == null) {
            return null;
        }
        UUID controllerId = principal.getTurnControlledBy();
        return controllerId == null || controllerId.equals(principalId) ? null : controllerId;
    }

    /**
     * CR 723.4 current-state entitlement: a viewer may see private in-game
     * information available to itself or to a player it currently controls.
     */
    private static boolean canViewPrivateStateFor(Game game, Player viewer, UUID principalId) {
        if (game == null || viewer == null || principalId == null) {
            return false;
        }
        if (viewer.getId().equals(principalId)) {
            return true;
        }
        Player principal = game.getPlayer(principalId);
        return principal != null && viewer.getId().equals(principal.getTurnControlledBy());
    }

    private static JsonArray observedView(Game game, Player viewer, boolean revealed) {
        JsonArray result = new JsonArray();
        List<ObservedCards> log = OBSERVED_CARDS.get(game.getId().toString());
        if (log == null) {
            return result;
        }
        for (ObservedCards entry : log) {
            if (entry.revealed != revealed
                    || (!revealed
                            && !entry.principalId.equals(viewer.getId())
                            && !viewer.getId().equals(entry.controllerId))) {
                continue;
            }
            JsonObject item = new JsonObject();
            item.addProperty("turn", entry.turn);
            addString(item, "title", entry.title);
            if (revealed) {
                item.addProperty("revealed_by_seat", seat(game, entry.principalId));
            }
            JsonArray cards = new JsonArray();
            for (int i = 0; i < entry.names.size(); i++) {
                JsonObject card = new JsonObject();
                card.addProperty("name", entry.names.get(i));
                card.addProperty("owner_seat", seat(game, entry.owners.get(i)));
                cards.add(card);
            }
            item.add("cards", cards);
            result.add(item);
        }
        return result;
    }

    /**
     * F-28: the cards a look window shows. The engine hands every library-zone
     * decision its own card set (a search: the searched library; Fact or
     * Fiction or a top-N look: only those cards); a grant shows exactly that
     * set, never the rest of the owner's library or its order. One decision
     * window is open per game at a time, so keyed by game id and owner id.
     */
    private static final Map<String, Map<String, Set<UUID>>> ZONE_LOOK_CARDS =
            new ConcurrentHashMap<>();

    static void beginZoneFullLook(Player viewer, Player owner, Game game, Collection<UUID> cardIds) {
        if (viewer == null || owner == null || game == null || cardIds == null) {
            return;
        }
        ZONE_LOOK_CARDS
                .computeIfAbsent(game.getId().toString(), ignored -> new ConcurrentHashMap<>())
                .put(owner.getId().toString(), Set.copyOf(cardIds));
        ZONE_FULL_LOOK
                .computeIfAbsent(game.getId().toString(), ignored -> new ConcurrentHashMap<>())
                .computeIfAbsent(viewer.getId().toString(), ignored -> ConcurrentHashMap.newKeySet())
                .add(owner.getId().toString());
    }

    static void endZoneFullLook(Player viewer, Player owner) {
        if (viewer == null || owner == null) {
            return;
        }
        for (Map<String, Set<UUID>> byOwner : ZONE_LOOK_CARDS.values()) {
            byOwner.remove(owner.getId().toString());
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
        if (game == null || permanent == null || viewer == null || !permanent.isFaceDown(game)) {
            return null;
        }
        // F-30: the controller may look at its face-down permanent (CR 708.5),
        // as may its turn controller (CR 723.4) and anyone the engine grants
        // LOOK_AT_FACE_DOWN. A face-down token has no hidden card.
        Card card = game.getCard(permanent.getId());
        boolean entitled = canViewPrivateStateFor(game, viewer, permanent.getControllerId())
                || (card != null && mayLookAtFaceDown(game, viewer, card));
        if (!entitled) {
            return null;
        }
        Map<UUID, String> byPermanent =
                RESTORED_FACE_DOWN_IDENTITIES.get(game.getId().toString());
        String restored = byPermanent == null ? null : byPermanent.get(permanent.getId());
        if (restored != null) {
            return restored;
        }
        return card == null || card.getName().isEmpty() ? null : card.getName();
    }

    private static boolean hasZoneFullLook(Game game, Player viewer, Player owner) {
        if (game == null || viewer == null || owner == null) {
            return false;
        }
        Map<String, Set<String>> byViewer = ZONE_FULL_LOOK.get(game.getId().toString());
        if (byViewer == null) {
            return false;
        }
        for (Player principal : game.getPlayers().values()) {
            if (!canViewPrivateStateFor(game, viewer, principal.getId())) {
                continue;
            }
            Set<String> owners = byViewer.get(principal.getId().toString());
            if (owners != null && owners.contains(owner.getId().toString())) {
                return true;
            }
        }
        return false;
    }

    /** Add a string-valued field, or JSON null when the value is absent. */
    private static void addString(JsonObject target, String key, String value) {
        if (value == null) {
            target.add(key, JsonNull.INSTANCE);
        } else {
            target.addProperty(key, value);
        }
    }

    static JsonObject actorView(Game game, Player actor) {
        JsonObject view = new JsonObject();
        view.addProperty("game_id", game.getId().toString());
        view.addProperty("actor_id", actor.getId().toString());
        view.addProperty("seat", seat(game, actor.getId()));
        view.addProperty("turn_number", game.getState().getTurnNum());
        // Masked in place: a viewer must not learn an opponent's real principal
        // id from who currently holds priority or the active turn.
        addString(view, "active_player_id",
                ActorSafeIdentity.optionalForSeat(game, actor, game.getActivePlayerId()));
        addString(view, "priority_player_id",
                ActorSafeIdentity.optionalForSeat(game, actor, game.getPriorityPlayerId()));
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
            // Actor-safe: the viewer sees its own id, every other principal is an
            // opaque token that is stable for this game.
            p.addProperty("player_id", ActorSafeIdentity.forSeat(game, actor, player));
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

            // Exile may contain face-down private cards: the count is public, and
            // identities follow the F-29 exile view below.
            p.addProperty("exile_count", game.getExile().getCardsOwned(game, player.getId()).size());
            // F-29: face-up exiled cards are public; a face-down one is shown
            // only to a principal the engine lets look at it (LOOK_AT_FACE_DOWN,
            // e.g. Gonti, Hideaway, foretell). Others see only the count.
            p.add("exile", exileView(game, actor, player));

            // CR 723.4: mark exactly the rows whose private in-game state this
            // principal may observe. Downstream replay canonicalization relies on
            // this explicit authorization rather than trusting stray private fields.
            boolean privateStateVisible =
                    canViewPrivateStateFor(game, actor, player.getId());
            p.addProperty("private_state_visible", privateStateVisible);

            // WS92-D1 grant-scoped library identities (systemic reacquisition).
            // Populated ONLY while the viewer holds a Rules-entitled full look
            // at this library (D2 window around a library-zone decision);
            // empty otherwise, so no hidden identity crosses the boundary
            // outside the window. Read-only projection; no Rules semantics.
            p.add("granted_library", grantedLibraryView(game, actor, player));

            // A player who plays with the top card of their library revealed
            // (Courser of Kruphix, Future Sight) shows it to every principal.
            Card revealedTop = player.isTopCardRevealed() ? player.getLibrary().getFromTop(game) : null;
            p.add("library_top_revealed", revealedTop == null ? JsonNull.INSTANCE : publicCard(revealedTop));

            // CR 723.4: the controller of a player sees the private in-game
            // information that player can see while the control relationship exists.
            if (privateStateVisible) {
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
            // F-30: a face-down spell (morph, disguise, manifest) has no public
            // characteristics (CR 708.4); only its controller may look at it
            // (CR 708.5), extended to that player's turn controller (CR 723.4).
            boolean faceDown = stackObject instanceof Spell && ((Spell) stackObject).isFaceDown(game);
            if (faceDown) {
                item.addProperty("face_down", true);
                addString(item, "name",
                        canViewPrivateStateFor(game, actor, stackObject.getControllerId())
                                ? stackObject.getName() : null);
            } else {
                item.addProperty("name", stackObject.getName());
            }
            stack.add(item);
        }
        view.add("stack", stack);
        // WS92-D3 public commander facts (systemic reacquisition). Command zone
        // contents are public; commander combat-damage totals are announced by
        // the Rules Core; command-zone cast counts determine the observable
        // commander tax. Read-only adapter projection; no Rules semantics.
        view.add("commander_status", commanderStatusView(game, actor));
        // F-26: what the engine showed this principal (looks) and everyone (reveals).
        view.add("looked_at", observedView(game, actor, false));
        view.add("revealed", observedView(game, actor, true));
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

        // actorView legitimately exposes the viewer's own native UUID. A public
        // replay/transcript view has no principal viewer, so normalize that last
        // raw principal id back to the same public seat token used for every
        // other principal before stripping actor-private fields.
        String rawAnchorId = anchor.getId().toString();
        String publicAnchorId = "op-" + seat(game, anchor.getId());
        replacePrincipalId(view, "active_player_id", rawAnchorId, publicAnchorId);
        replacePrincipalId(view, "priority_player_id", rawAnchorId, publicAnchorId);

        view.remove("actor_id");
        view.remove("seat");
        view.remove("looked_at");
        for (JsonElement element : view.getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            replacePrincipalId(player, "player_id", rawAnchorId, publicAnchorId);
            player.remove("is_actor");
            player.remove("private_state_visible");
            player.remove("hand");
            player.remove("mana_pool");
            player.remove("land_plays_remaining");
            player.remove("granted_library");
            if (player.has("exile") && player.get("exile").isJsonArray()) {
                JsonArray publicExile = new JsonArray();
                for (JsonElement exiled : player.getAsJsonArray("exile")) {
                    if (!exiled.getAsJsonObject().has("face_down")) {
                        publicExile.add(exiled);
                    }
                }
                player.add("exile", publicExile);
            }
            if (player.has("battlefield") && player.get("battlefield").isJsonArray()) {
                for (JsonElement permanentElement : player.getAsJsonArray("battlefield")) {
                    JsonObject permanent = permanentElement.getAsJsonObject();
                    replacePrincipalId(
                            permanent,
                            "controller_id",
                            rawAnchorId,
                            publicAnchorId
                    );
                    permanent.remove("private_identity");
                }
            }
        }
        for (JsonElement stackElement : view.getAsJsonArray("stack")) {
            JsonObject stackItem = stackElement.getAsJsonObject();
            if (stackItem.has("face_down")) {
                stackItem.add("name", JsonNull.INSTANCE);
            }
        }
        if (view.has("commander_status") && view.get("commander_status").isJsonArray()) {
            for (JsonElement statusElement : view.getAsJsonArray("commander_status")) {
                JsonObject status = statusElement.getAsJsonObject();
                replacePrincipalId(status, "owner_id", rawAnchorId, publicAnchorId);
                if (status.has("commander_damage_to_player")
                        && status.get("commander_damage_to_player").isJsonArray()) {
                    for (JsonElement damageElement
                            : status.getAsJsonArray("commander_damage_to_player")) {
                        replacePrincipalId(
                                damageElement.getAsJsonObject(),
                                "player_id",
                                rawAnchorId,
                                publicAnchorId
                        );
                    }
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

    /**
     * Historical internal public-board projection seam retained for WS92
     * reflection-based qualification. Passing no viewer must never expose a
     * restored face-down private identity.
     */
    private static JsonObject publicPermanent(Permanent permanent, Game game) {
        return publicPermanent(permanent, game, null);
    }

    private static JsonObject publicPermanent(Permanent permanent, Game game, Player viewer) {
        JsonObject item = new JsonObject();
        item.addProperty("object_id", permanent.getId().toString());
        item.addProperty("name", permanent.getName());
        item.addProperty(
                "controller_id",
                ActorSafeIdentity.optionalForSeat(game, viewer, permanent.getControllerId())
        );
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

    private static JsonArray exileView(Game game, Player viewer, Player owner) {
        JsonArray result = new JsonArray();
        for (Card card : game.getExile().getCardsOwned(game, owner.getId())) {
            if (!card.isFaceDown(game)) {
                result.add(publicCard(card));
            } else if (mayLookAtFaceDown(game, viewer, card)) {
                JsonObject item = publicCard(card);
                item.addProperty("face_down", true);
                result.add(item);
            }
        }
        return result;
    }

    /** The engine lets the viewer, or a player whose turn it controls (CR 723.4), look at the card. */
    private static boolean mayLookAtFaceDown(Game game, Player viewer, Card card) {
        if (viewer == null) {
            return false;
        }
        for (Player principal : game.getPlayers().values()) {
            if (canViewPrivateStateFor(game, viewer, principal.getId())
                    && !game.getContinuousEffects().asThough(card.getId(),
                            AsThoughEffectType.LOOK_AT_FACE_DOWN, null, principal.getId(), game).isEmpty()) {
                return true;
            }
        }
        return false;
    }

    private static JsonArray grantedLibraryView(Game game, Player viewer, Player owner) {
        JsonArray result = new JsonArray();
        if (!hasZoneFullLook(game, viewer, owner)) {
            return result;
        }
        Map<String, Set<UUID>> byOwner = ZONE_LOOK_CARDS.get(game.getId().toString());
        Set<UUID> shown = byOwner == null ? null : byOwner.get(owner.getId().toString());
        if (shown == null) {
            return result;
        }
        for (Card card : owner.getLibrary().getCards(game)) {
            if (shown.contains(card.getId())) {
                result.add(publicCard(card));
            }
        }
        return result;
    }

    private static JsonArray commanderStatusView(Game game, Player viewer) {
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
                entry.addProperty("owner_id", ActorSafeIdentity.forSeat(game, viewer, player));
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
                        row.addProperty("player_id", ActorSafeIdentity.optionalForSeat(
                                game, viewer, damagedId));
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

    private static void replacePrincipalId(
            JsonObject object,
            String property,
            String rawId,
            String replacement
    ) {
        if (object == null || !object.has(property) || object.get(property).isJsonNull()) {
            return;
        }
        JsonElement value = object.get(property);
        if (value.isJsonPrimitive()
                && value.getAsJsonPrimitive().isString()
                && rawId.equals(value.getAsString())) {
            object.addProperty(property, replacement);
        }
    }

    private static void addUuid(JsonObject object, String property, UUID value) {
        if (value == null) {
            object.add(property, JsonNull.INSTANCE);
        } else {
            object.addProperty(property, value.toString());
        }
    }
}
