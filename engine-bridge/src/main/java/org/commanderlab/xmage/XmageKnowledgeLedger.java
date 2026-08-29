package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.cards.Cards;
import mage.cards.decks.Deck;
import mage.constants.CommanderCardType;
import mage.constants.ManaType;
import mage.constants.Zone;
import mage.counters.CounterType;
import mage.game.Game;
import mage.game.LookedAt;
import mage.game.Revealed;
import mage.game.permanent.Permanent;
import mage.game.stack.StackObject;
import mage.players.Player;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Single authority for actor-entitled identity and visibility in the WS-22 XMage lane.
 *
 * <p>XMage remains the sole Rules Core. This class does not determine legal
 * actions. It consumes XMage's native public reveal windows, per-player look
 * windows, ownership/control, zones, face-down state, library order and zone
 * change counters, then projects only what a specific viewer is entitled to
 * know. Raw XMage UUIDs never form production observation identity.</p>
 */
final class XmageKnowledgeLedger {

    private record Incarnation(UUID cardId, int zoneChangeCounter) {
    }

    private final Map<UUID, Integer> seats = new LinkedHashMap<>();
    private final Map<Integer, UUID> playersBySeat = new LinkedHashMap<>();
    private final Map<UUID, String> physicalCardRefs = new HashMap<>();
    private final Map<UUID, String> dynamicObjectRefs = new LinkedHashMap<>();
    private final Map<UUID, Integer> lastZoneChangeCounter = new HashMap<>();
    private final Map<UUID, List<UUID>> lastLibraryOrder = new HashMap<>();
    private final Map<UUID, Set<Incarnation>> visibleIncarnations = new HashMap<>();
    private final Map<UUID, Map<UUID, LinkedHashMap<Integer, Incarnation>>> knownLibraryPositions = new HashMap<>();
    private final Map<UUID, Map<UUID, List<String>>> rememberedLibraryComposition = new HashMap<>();
    private final Map<UUID, Set<UUID>> zoneFullLookOwners = new HashMap<>();
    private int dynamicObjectSequence;

    void registerDeck(int zeroBasedSeat, Deck deck) {
        if (deck == null) {
            throw new IllegalArgumentException("deck is required");
        }
        String fingerprint = deckFingerprint(deck);
        Map<String, Integer> mainOccurrences = new HashMap<>();
        for (Card card : deck.getCards()) {
            int occurrence = mainOccurrences.merge(card.getName(), 1, Integer::sum);
            physicalCardRefs.put(
                    card.getMainCard().getId(),
                    stablePhysicalRef(zeroBasedSeat, fingerprint, "main", card.getName(), occurrence)
            );
        }
        Map<String, Integer> commandOccurrences = new HashMap<>();
        for (Card card : deck.getSideboard()) {
            int occurrence = commandOccurrences.merge(card.getName(), 1, Integer::sum);
            physicalCardRefs.put(
                    card.getMainCard().getId(),
                    stablePhysicalRef(zeroBasedSeat, fingerprint, "command", card.getName(), occurrence)
            );
        }
    }

    void registerPlayers(Game game, List<? extends Player> orderedPlayers) {
        if (game == null || orderedPlayers == null) {
            throw new IllegalArgumentException("game and orderedPlayers are required");
        }
        seats.clear();
        playersBySeat.clear();
        for (int seat = 0; seat < orderedPlayers.size(); seat++) {
            UUID playerId = orderedPlayers.get(seat).getId();
            if (seats.put(playerId, seat) != null) {
                throw new IllegalArgumentException("duplicate player identity");
            }
            playersBySeat.put(seat, playerId);
        }
        verifyLoadedDeckIdentity(game);
        synchronize(game);
    }

    int registeredPlayerCount() {
        return seats.size();
    }

    Player decisionAuthority(Game game, Player decisionSubject) {
        UUID controllerId = decisionSubject.getTurnControlledBy();
        if (controllerId == null || controllerId.equals(decisionSubject.getId()) || seat(controllerId) < 0) {
            return decisionSubject;
        }
        Player controller = game.getPlayer(controllerId);
        return controller == null ? decisionSubject : controller;
    }

    int seat(UUID playerId) {
        Integer value = playerId == null ? null : seats.get(playerId);
        return value == null ? -1 : value;
    }

    String playerRef(UUID playerId) {
        int value = seat(playerId);
        if (value < 0) {
            throw new IllegalStateException("UNREGISTERED_PLAYER_IDENTITY");
        }
        return "P" + (value + 1);
    }

    void beginZoneFullLook(Player viewer, Player libraryOwner, Game game) {
        synchronize(game);
        zoneFullLookOwners.computeIfAbsent(viewer.getId(), ignored -> new HashSet<>()).add(libraryOwner.getId());
        rememberLibraryComposition(viewer, libraryOwner, game);
    }

    void endZoneFullLook(Player viewer, Player libraryOwner) {
        Set<UUID> owners = zoneFullLookOwners.get(viewer.getId());
        if (owners == null) {
            return;
        }
        owners.remove(libraryOwner.getId());
        if (owners.isEmpty()) {
            zoneFullLookOwners.remove(viewer.getId());
        }
    }

    void shuffled(Player libraryOwner, Game game) {
        synchronizeZoneChanges(game);
        invalidateLibraryOrderAndIdentity(libraryOwner);
        lastLibraryOrder.put(libraryOwner.getId(), List.copyOf(libraryOwner.getLibrary().getCardList()));
        harvestNativeKnowledge(game);
    }

    boolean canSeeCardIdentity(Game game, Player viewer, Card card) {
        synchronize(game);
        return canSeeCardIdentityWithoutSync(game, viewer, card);
    }

    Set<String> forbiddenIdentityTokens(Game game, Player viewer) {
        synchronize(game);
        Set<String> forbidden = new LinkedHashSet<>();
        Set<String> authorizedNames = new HashSet<>();
        for (Card card : game.getCards()) {
            if (card != null && canSeeCardIdentityWithoutSync(game, viewer, card) && card.getName() != null) {
                authorizedNames.add(card.getName());
            }
        }
        for (Card card : game.getCards()) {
            if (card == null || canSeeCardIdentityWithoutSync(game, viewer, card)) {
                continue;
            }
            forbidden.add(card.getId().toString());
            forbidden.add(card.getMainCard().getId().toString());
            if (card.getName() != null && !card.getName().isBlank() && !authorizedNames.contains(card.getName())) {
                forbidden.add(card.getName());
            }
        }
        return forbidden;
    }

    JsonObject snapshot(Game game, Player viewer, Player decisionSubject) {
        synchronize(game);
        JsonObject view = new JsonObject();
        view.addProperty("viewer_player_id", playerRef(viewer.getId()));
        view.addProperty("decision_subject_player_id", playerRef(decisionSubject.getId()));
        view.addProperty("decision_authority_player_id", playerRef(decisionAuthority(game, decisionSubject).getId()));
        view.addProperty("seat", seat(viewer.getId()));
        view.addProperty("decision_subject_seat", seat(decisionSubject.getId()));
        view.addProperty("turn_number", game.getState().getTurnNum());
        view.addProperty("player_count", registeredPlayerCount());
        view.addProperty("live_player_count", game.getPlayers().size());
        view.add("live_player_order", livePlayerOrder(game));
        addPlayerRef(view, "active_player_id", game.getActivePlayerId());
        addPlayerRef(view, "priority_player_id", game.getPriorityPlayerId());
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

        JsonArray playerViews = new JsonArray();
        for (int seatIndex = 0; seatIndex < registeredPlayerCount(); seatIndex++) {
            UUID playerId = playersBySeat.get(seatIndex);
            Player player = game.getPlayer(playerId);
            if (player == null) {
                continue;
            }
            JsonObject p = new JsonObject();
            p.addProperty("player_id", playerRef(playerId));
            p.addProperty("seat", seatIndex);
            p.addProperty("life", player.getLife());
            p.addProperty("poison_counters", player.getCountersCount(CounterType.POISON));
            p.addProperty("hand_count", player.getHand().size());
            p.addProperty("library_count", player.getLibrary().size());
            p.addProperty("graveyard_count", player.getGraveyard().size());
            p.addProperty("has_lost", player.hasLost());
            p.addProperty("has_won", player.hasWon());
            p.addProperty("has_left", player.hasLeft());
            p.addProperty("is_viewer", playerId.equals(viewer.getId()));
            p.addProperty("is_decision_subject", playerId.equals(decisionSubject.getId()));
            UUID turnController = player.getTurnControlledBy();
            if (turnController == null || seat(turnController) < 0) {
                p.add("turn_controlled_by", JsonNull.INSTANCE);
            } else {
                p.addProperty("turn_controlled_by", playerRef(turnController));
            }

            JsonArray battlefield = new JsonArray();
            for (Permanent permanent : game.getBattlefield().getAllPermanents()) {
                if (playerId.equals(permanent.getControllerId())) {
                    battlefield.add(permanentView(permanent, viewer, game));
                }
            }
            p.add("battlefield", battlefield);

            JsonArray graveyard = new JsonArray();
            for (Card card : player.getGraveyard().getCards(game)) {
                graveyard.add(cardView(card, game, true));
            }
            p.add("graveyard", graveyard);

            JsonArray command = new JsonArray();
            Collection<Card> commanderCards = game.getCommanderCardsFromCommandZone(player, CommanderCardType.COMMANDER_OR_OATHBREAKER);
            for (Card card : commanderCards) {
                command.add(cardView(card, game, true));
            }
            p.add("command", command);

            JsonArray exile = new JsonArray();
            for (Card card : game.getExile().getCardsOwned(game, playerId)) {
                exile.add(cardView(card, game, canSeeCardIdentityWithoutSync(game, viewer, card)));
            }
            p.add("exile", exile);
            p.addProperty("exile_count", exile.size());

            if (playerId.equals(viewer.getId()) || viewerControls(game, viewer, playerId)) {
                JsonArray hand = new JsonArray();
                for (Card card : player.getHand().getCards(game)) {
                    hand.add(cardView(card, game, true));
                }
                p.add("hand", hand);
            }

            if (playerId.equals(viewer.getId())) {
                JsonObject mana = new JsonObject();
                mana.addProperty("white", player.getManaPool().get(ManaType.WHITE));
                mana.addProperty("blue", player.getManaPool().get(ManaType.BLUE));
                mana.addProperty("black", player.getManaPool().get(ManaType.BLACK));
                mana.addProperty("red", player.getManaPool().get(ManaType.RED));
                mana.addProperty("green", player.getManaPool().get(ManaType.GREEN));
                mana.addProperty("colorless", player.getManaPool().get(ManaType.COLORLESS));
                p.add("mana_pool", mana);
                p.addProperty("land_plays_remaining", Math.max(0, player.getLandsPerTurn() - player.getLandsPlayed()));
            }

            p.add("known_library", knownLibraryView(viewer, player, game));
            p.add("remembered_library_composition", rememberedLibraryView(viewer, player));
            playerViews.add(p);
        }
        view.add("players", playerViews);

        JsonArray stack = new JsonArray();
        for (StackObject stackObject : game.getStack()) {
            JsonObject item = new JsonObject();
            item.addProperty("object_id", dynamicObjectRef(stackObject.getId(), "stack"));
            UUID controllerId = stackObject.getControllerId();
            if (controllerId == null || seat(controllerId) < 0) {
                item.add("controller_id", JsonNull.INSTANCE);
            } else {
                item.addProperty("controller_id", playerRef(controllerId));
            }
            Card sourceCard = game.getCard(stackObject.getSourceId());
            boolean visible = sourceCard == null || canSeeCardIdentityWithoutSync(game, viewer, sourceCard);
            item.addProperty("face_down", sourceCard != null && sourceCard.isFaceDown(game));
            item.addProperty("name", visible ? stackObject.getName() : "Face-down spell");
            stack.add(item);
        }
        view.add("stack", stack);
        return view;
    }

    JsonArray livePlayerOrder(Game game) {
        JsonArray order = new JsonArray();
        for (Player player : game.getPlayers().values()) {
            JsonObject item = new JsonObject();
            item.addProperty("player_id", playerRef(player.getId()));
            item.addProperty("seat", seat(player.getId()));
            order.add(item);
        }
        return order;
    }

    private boolean canSeeCardIdentityWithoutSync(Game game, Player viewer, Card card) {
        if (card == null || viewer == null) {
            return false;
        }
        Card main = card.getMainCard();
        UUID mainId = main.getId();
        Zone zone = game.getState().getZone(mainId);
        if (zone == null) {
            zone = game.getState().getZone(card.getId());
        }
        UUID ownerId = card.getOwnerId();
        if (zone == Zone.HAND) {
            return ownerId != null && (ownerId.equals(viewer.getId()) || viewerControls(game, viewer, ownerId));
        }
        if (zone == Zone.LIBRARY) {
            if (ownerId != null && zoneFullLookOwners.getOrDefault(viewer.getId(), Set.of()).contains(ownerId)) {
                return true;
            }
            Player owner = ownerId == null ? null : game.getPlayer(ownerId);
            Card top = owner == null ? null : owner.getLibrary().getFromTop(game);
            if (owner != null && owner.isTopCardRevealed() && top != null && mainId.equals(top.getMainCard().getId())) {
                return true;
            }
            return hasCurrentGrant(viewer.getId(), card, game);
        }
        if (zone == Zone.BATTLEFIELD || zone == Zone.EXILED || zone == Zone.STACK) {
            if (!card.isFaceDown(game)) {
                return true;
            }
            if (card instanceof Permanent permanent && viewer.getId().equals(permanent.getControllerId())) {
                return true;
            }
            return hasCurrentGrant(viewer.getId(), card, game);
        }
        if (zone == Zone.GRAVEYARD || zone == Zone.COMMAND) {
            return true;
        }
        return hasCurrentGrant(viewer.getId(), card, game);
    }

    private JsonObject permanentView(Permanent permanent, Player viewer, Game game) {
        boolean visible = canSeeCardIdentityWithoutSync(game, viewer, permanent);
        JsonObject item = cardView(permanent, game, visible);
        item.addProperty("controller_id", playerRef(permanent.getControllerId()));
        item.addProperty("owner_id", playerRef(permanent.getOwnerId()));
        item.addProperty("tapped", permanent.isTapped());
        item.addProperty("damage", permanent.getDamage());
        item.addProperty("face_down", permanent.isFaceDown(game));
        return item;
    }

    private JsonObject cardView(Card card, Game game, boolean revealIdentity) {
        JsonObject item = new JsonObject();
        item.addProperty("object_id", incarnationRef(card, game));
        item.addProperty("face_down", card.isFaceDown(game));
        item.addProperty("name", revealIdentity ? card.getName() : "Hidden card");
        return item;
    }

    private JsonArray knownLibraryView(Player viewer, Player owner, Game game) {
        JsonArray result = new JsonArray();
        Map<UUID, LinkedHashMap<Integer, Incarnation>> byOwner = knownLibraryPositions.get(viewer.getId());
        if (byOwner == null) {
            return result;
        }
        LinkedHashMap<Integer, Incarnation> known = byOwner.get(owner.getId());
        if (known == null) {
            return result;
        }
        List<UUID> currentOrder = owner.getLibrary().getCardList();
        List<Integer> stale = new ArrayList<>();
        for (Map.Entry<Integer, Incarnation> entry : known.entrySet()) {
            int position = entry.getKey();
            Incarnation knownIncarnation = entry.getValue();
            if (position < 0 || position >= currentOrder.size() || !currentOrder.get(position).equals(knownIncarnation.cardId())) {
                stale.add(position);
                continue;
            }
            Card card = game.getCard(knownIncarnation.cardId());
            if (card == null || card.getMainCard().getZoneChangeCounter(game) != knownIncarnation.zoneChangeCounter()) {
                stale.add(position);
                continue;
            }
            JsonObject item = new JsonObject();
            item.addProperty("position_from_top", position);
            item.addProperty("object_id", incarnationRef(card, game));
            item.addProperty("name", card.getName());
            result.add(item);
        }
        stale.forEach(known::remove);
        return result;
    }

    private JsonArray rememberedLibraryView(Player viewer, Player owner) {
        JsonArray result = new JsonArray();
        Map<UUID, List<String>> byOwner = rememberedLibraryComposition.get(viewer.getId());
        if (byOwner == null) {
            return result;
        }
        List<String> names = byOwner.get(owner.getId());
        if (names != null) {
            names.forEach(result::add);
        }
        return result;
    }

    private void synchronize(Game game) {
        synchronizeZoneChanges(game);
        detectUnknownLibraryReorders(game);
        harvestNativeKnowledge(game);
    }

    private void synchronizeZoneChanges(Game game) {
        for (Card card : game.getCards()) {
            if (card == null) {
                continue;
            }
            Card main = card.getMainCard();
            UUID id = main.getId();
            int now = main.getZoneChangeCounter(game);
            Integer before = lastZoneChangeCounter.put(id, now);
            if (before == null || before == now) {
                continue;
            }
            for (Set<Incarnation> grants : visibleIncarnations.values()) {
                grants.removeIf(value -> value.cardId().equals(id));
            }
            for (Map<UUID, LinkedHashMap<Integer, Incarnation>> byOwner : knownLibraryPositions.values()) {
                for (LinkedHashMap<Integer, Incarnation> positions : byOwner.values()) {
                    positions.entrySet().removeIf(entry -> entry.getValue().cardId().equals(id));
                }
            }
        }
    }

    private void detectUnknownLibraryReorders(Game game) {
        for (UUID ownerId : seats.keySet()) {
            Player owner = game.getPlayer(ownerId);
            if (owner == null) {
                continue;
            }
            List<UUID> current = List.copyOf(owner.getLibrary().getCardList());
            List<UUID> previous = lastLibraryOrder.put(ownerId, current);
            if (previous == null || previous.equals(current)) {
                continue;
            }
            for (Map<UUID, LinkedHashMap<Integer, Incarnation>> byOwner : knownLibraryPositions.values()) {
                byOwner.remove(ownerId);
            }
            if (previous.size() == current.size() && new HashSet<>(previous).equals(new HashSet<>(current))) {
                invalidateLibraryIdentityGrants(owner);
            }
        }
    }

    private void harvestNativeKnowledge(Game game) {
        Revealed revealed = game.getState().getRevealed();
        for (Cards cards : revealed.values()) {
            Collection<Card> publicCards = cards.getCards(game);
            for (UUID viewerId : seats.keySet()) {
                grantCurrent(viewerId, publicCards, game);
            }
        }

        for (UUID viewerId : seats.keySet()) {
            Player viewer = game.getPlayer(viewerId);
            if (viewer == null) {
                continue;
            }
            LookedAt lookedAt = game.getState().getLookedAt(viewerId);
            for (Cards cards : lookedAt.values()) {
                Collection<Card> privateCards = cards.getCards(game);
                grantCurrent(viewerId, privateCards, game);
                recordKnownLibraryPositions(viewer, privateCards, game);
            }
        }
    }

    private void recordKnownLibraryPositions(Player viewer, Collection<? extends Card> cards, Game game) {
        Set<UUID> lookedIds = new HashSet<>();
        for (Card card : cards) {
            if (card != null) {
                lookedIds.add(card.getId());
                lookedIds.add(card.getMainCard().getId());
            }
        }
        for (UUID ownerId : seats.keySet()) {
            Player owner = game.getPlayer(ownerId);
            if (owner == null) {
                continue;
            }
            List<UUID> order = owner.getLibrary().getCardList();
            LinkedHashMap<Integer, Incarnation> positions = null;
            for (int index = 0; index < order.size(); index++) {
                UUID id = order.get(index);
                if (!lookedIds.contains(id)) {
                    continue;
                }
                Card card = game.getCard(id);
                if (card == null) {
                    continue;
                }
                if (positions == null) {
                    positions = knownLibraryPositions
                            .computeIfAbsent(viewer.getId(), ignored -> new HashMap<>())
                            .computeIfAbsent(ownerId, ignored -> new LinkedHashMap<>());
                }
                positions.put(index, incarnation(card, game));
            }
        }
    }

    private void rememberLibraryComposition(Player viewer, Player owner, Game game) {
        List<String> names = owner.getLibrary().getCards(game).stream().map(Card::getName).sorted().toList();
        rememberedLibraryComposition.computeIfAbsent(viewer.getId(), ignored -> new HashMap<>()).put(owner.getId(), names);
    }

    private void invalidateLibraryOrderAndIdentity(Player owner) {
        UUID ownerId = owner.getId();
        for (Map<UUID, LinkedHashMap<Integer, Incarnation>> byOwner : knownLibraryPositions.values()) {
            byOwner.remove(ownerId);
        }
        invalidateLibraryIdentityGrants(owner);
    }

    private void invalidateLibraryIdentityGrants(Player owner) {
        Set<UUID> currentIds = new HashSet<>(owner.getLibrary().getCardList());
        for (Set<Incarnation> grants : visibleIncarnations.values()) {
            grants.removeIf(value -> currentIds.contains(value.cardId()));
        }
    }

    private boolean viewerControls(Game game, Player viewer, UUID subjectId) {
        Player subject = game.getPlayer(subjectId);
        return subject != null
                && subject.getTurnControlledBy() != null
                && subject.getTurnControlledBy().equals(viewer.getId())
                && !subject.getId().equals(viewer.getId());
    }

    private boolean hasCurrentGrant(UUID viewerId, Card card, Game game) {
        Set<Incarnation> grants = visibleIncarnations.get(viewerId);
        return grants != null && grants.contains(incarnation(card, game));
    }

    private void grantCurrent(UUID viewerId, Collection<? extends Card> cards, Game game) {
        Set<Incarnation> grants = visibleIncarnations.computeIfAbsent(viewerId, ignored -> new HashSet<>());
        for (Card card : cards) {
            if (card != null) {
                grants.add(incarnation(card, game));
            }
        }
    }

    private Incarnation incarnation(Card card, Game game) {
        Card main = card.getMainCard();
        return new Incarnation(main.getId(), main.getZoneChangeCounter(game));
    }

    private String incarnationRef(Card card, Game game) {
        Card main = card.getMainCard();
        UUID mainId = main.getId();
        String physical = physicalCardRefs.get(mainId);
        if (physical == null) {
            physical = dynamicObjectRef(mainId, "card");
        }
        return physical + "@z" + main.getZoneChangeCounter(game);
    }

    private String dynamicObjectRef(UUID rawId, String prefix) {
        if (rawId == null) {
            return prefix + "-none";
        }
        return dynamicObjectRefs.computeIfAbsent(rawId, ignored -> {
            dynamicObjectSequence++;
            return prefix + "-" + String.format("%06d", dynamicObjectSequence);
        });
    }

    private void verifyLoadedDeckIdentity(Game game) {
        for (UUID id : new ArrayList<>(physicalCardRefs.keySet())) {
            if (game.getCard(id) == null) {
                throw new IllegalStateException("SEMANTIC_CARD_IDENTITY_REGISTRATION_FAILED: deck card id not loaded into XMage game");
            }
        }
    }

    private void addPlayerRef(JsonObject object, String property, UUID value) {
        if (value == null || seat(value) < 0) {
            object.add(property, JsonNull.INSTANCE);
        } else {
            object.addProperty(property, playerRef(value));
        }
    }

    private static String stablePhysicalRef(int zeroBasedSeat, String deckFingerprint, String deckZone, String name, int occurrence) {
        return "card-P" + (zeroBasedSeat + 1) + "-"
                + sha256(deckFingerprint + "\u0000" + deckZone + "\u0000" + name + "\u0000" + occurrence).substring(0, 20);
    }

    private static String deckFingerprint(Deck deck) {
        List<String> main = deck.getCards().stream().map(Card::getName).sorted().toList();
        List<String> command = deck.getSideboard().stream().map(Card::getName).sorted().toList();
        return sha256("main=" + String.join("\u0000", main) + "\u0001command=" + String.join("\u0000", command));
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(bytes.length * 2);
            for (byte b : bytes) {
                result.append(String.format("%02x", b));
            }
            return result.toString();
        } catch (NoSuchAlgorithmException exc) {
            throw new IllegalStateException("SHA-256 unavailable", exc);
        }
    }
}
