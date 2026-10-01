package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.effects.common.continuous.BecomesFaceDownCreatureEffect;
import mage.cards.Card;
import mage.game.GameCommanderImpl;
import mage.game.permanent.Permanent;
import mage.players.Player;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * SLOT-04 lossless hidden-state materialization for a successor fixture record.
 *
 * <p>The Coordinator's SLOT-04 ruling keeps the L7 policy binding: an exact
 * library needs its complete native order, a partial library request fails
 * closed, and a face-down object needs an explicit semantic id plus an explicit
 * native {@code FaceDownType}. A successor record states both explicitly:</p>
 *
 * <ul>
 *   <li>{@code deck_state[*].checkpoint_library}: the complete top-to-bottom
 *       library of that player at the checkpoint, as runs that are either one
 *       requested library object ({@code semantic_id}) or a count of the
 *       player's declared scaffolding template card;</li>
 *   <li>{@code deck_state[*].checkpoint_hand}: optionally, the complete hand as
 *       the requested hand objects plus an exact count of template cards;</li>
 *   <li>{@code face_down_type} on a face-down battlefield object.</li>
 * </ul>
 *
 * <p>Nothing here infers a missing order or a missing type: a historical record
 * without these fields keeps failing closed exactly as before. All mutation is
 * delegated to the native RG-06A game-load APIs through
 * {@link XmageHiddenStateRestoration}; the one Lab-side step is placing the
 * requested library cards, after the opening hands, with the engine's typed
 * setup primitive. No permission model is added: entitlement to see a hidden
 * object is derived by the redactor from the live engine state.</p>
 *
 * <p>Verification is engine-direct and coded. A mismatch names the player, the
 * semantic object or the position, never a hidden card identity, so the
 * arrival response cannot leak what it verified.</p>
 */
final class XmageLosslessHiddenPlan {

    static final String LIBRARY_COMPLETENESS = "COMPLETE_TOP_TO_BOTTOM";
    static final String HAND_COMPLETENESS = "COMPLETE";

    /** One requested library object at its exact top-to-bottom index. */
    record LibraryObject(String semanticId, String cardIdentity, String owner, int position) {
    }

    /** One requested face-down battlefield object with its explicit native type. */
    record FaceDownObject(
            String semanticId,
            String cardIdentity,
            BecomesFaceDownCreatureEffect.FaceDownType type
    ) {
    }

    /** One player's declared deck/library/hand composition. */
    record PlayerDeck(
            String playerId,
            String templateIdentity,
            int templateCount,
            List<String> libraryOrder,
            Integer handTemplateCount
    ) {
    }

    static final XmageLosslessHiddenPlan EMPTY =
            new XmageLosslessHiddenPlan(List.of(), List.of(), List.of());

    private final List<PlayerDeck> decks;
    private final List<LibraryObject> libraryObjects;
    private final List<FaceDownObject> faceDownObjects;

    private XmageLosslessHiddenPlan(
            List<PlayerDeck> decks,
            List<LibraryObject> libraryObjects,
            List<FaceDownObject> faceDownObjects) {
        this.decks = List.copyOf(decks);
        this.libraryObjects = List.copyOf(libraryObjects);
        this.faceDownObjects = List.copyOf(faceDownObjects);
    }

    boolean isEmpty() {
        return decks.isEmpty() && libraryObjects.isEmpty() && faceDownObjects.isEmpty();
    }

    List<PlayerDeck> decks() {
        return decks;
    }

    List<LibraryObject> libraryObjects() {
        return libraryObjects;
    }

    List<FaceDownObject> faceDownObjects() {
        return faceDownObjects;
    }

    boolean declaresFaceDown(String semanticId) {
        return faceDownObjects.stream().anyMatch(object -> object.semanticId().equals(semanticId));
    }

    boolean declaresLibraryObject(String semanticId) {
        return libraryObjects.stream().anyMatch(object -> object.semanticId().equals(semanticId));
    }

    /** Card identities the materialization vehicle must also hold (library objects). */
    List<String> vehicleIdentities() {
        List<String> identities = new ArrayList<>();
        for (LibraryObject object : libraryObjects) {
            identities.add(object.cardIdentity());
        }
        return identities;
    }

    private static XmageNativeStateRestoration.RestorationException fail(String code, String detail) {
        return new XmageNativeStateRestoration.RestorationException(code, detail);
    }

    private static String text(JsonObject object, String key) {
        if (object == null || !object.has(key) || object.get(key).isJsonNull()
                || !object.get(key).isJsonPrimitive()) {
            return null;
        }
        String value = object.get(key).getAsString();
        return value == null || value.isBlank() ? null : value;
    }

    private static int nonNegativeInt(JsonObject object, String key, String context) {
        if (object == null || !object.has(key) || !object.get(key).isJsonPrimitive()
                || !object.get(key).getAsJsonPrimitive().isNumber()) {
            throw fail("INVALID_DECK_STATE", context + " requires integer " + key);
        }
        double raw = object.get(key).getAsDouble();
        int value = object.get(key).getAsInt();
        if (raw != value || value < 0) {
            throw fail("INVALID_DECK_STATE", context + " " + key + " must be a non-negative integer");
        }
        return value;
    }

    /**
     * Parses the lossless hidden-state declarations of a record. A record that
     * declares none returns {@link #EMPTY}; the caller then keeps its historical
     * fail-closed behaviour for library and face-down objects.
     */
    static XmageLosslessHiddenPlan fromRecord(JsonObject record) {
        if (record == null || !record.has("semantic_objects")
                || !record.get("semantic_objects").isJsonArray()) {
            return EMPTY;
        }
        Map<String, JsonObject> objectsById = new LinkedHashMap<>();
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            if (!element.isJsonObject()) {
                continue;
            }
            JsonObject object = element.getAsJsonObject();
            String semanticId = text(object, "semantic_id");
            if (semanticId != null) {
                objectsById.put(semanticId, object);
            }
        }

        List<FaceDownObject> faceDown = new ArrayList<>();
        for (Map.Entry<String, JsonObject> entry : objectsById.entrySet()) {
            JsonObject object = entry.getValue();
            boolean isFaceDown = object.has("face_down") && object.get("face_down").isJsonPrimitive()
                    && object.get("face_down").getAsBoolean();
            String declaredType = text(object, "face_down_type");
            if (declaredType == null) {
                if (object.has("face_down_type") && !object.get("face_down_type").isJsonNull()) {
                    throw fail("INVALID_FACE_DOWN_TYPE", entry.getKey());
                }
                continue;
            }
            if (!isFaceDown) {
                throw fail("FACE_DOWN_TYPE_ON_FACE_UP_OBJECT", entry.getKey());
            }
            final BecomesFaceDownCreatureEffect.FaceDownType type;
            try {
                type = BecomesFaceDownCreatureEffect.FaceDownType.valueOf(declaredType);
            } catch (IllegalArgumentException exc) {
                throw fail("INVALID_FACE_DOWN_TYPE", entry.getKey() + " " + declaredType);
            }
            if (type == BecomesFaceDownCreatureEffect.FaceDownType.MANUAL) {
                throw fail("INVALID_FACE_DOWN_TYPE", entry.getKey() + " MANUAL is not a game-load type");
            }
            if (!"battlefield".equals(text(object, "zone"))) {
                throw fail("FACE_DOWN_OBJECT_NOT_BATTLEFIELD", entry.getKey());
            }
            String owner = text(object, "owner");
            if (owner == null || !owner.equals(text(object, "controller"))) {
                throw fail("UNSUPPORTED_CONTROL_DIVERGENCE", entry.getKey());
            }
            String identity = text(object, "card_identity");
            if (identity == null) {
                throw fail("INVALID_CARD_IDENTITY", entry.getKey());
            }
            faceDown.add(new FaceDownObject(entry.getKey(), identity, type));
        }
        if (faceDown.size() > 1) {
            // The native restore applies one face-down object per atomic request.
            throw fail("MULTIPLE_FACE_DOWN_STATES_UNSUPPORTED_ATOMICALLY",
                    Integer.toString(faceDown.size()));
        }

        List<PlayerDeck> decks = new ArrayList<>();
        List<LibraryObject> libraryObjects = new ArrayList<>();
        Set<String> coveredLibraryObjects = new HashSet<>();
        if (record.has("deck_state") && !record.get("deck_state").isJsonNull()) {
            if (!record.get("deck_state").isJsonArray()) {
                throw fail("INVALID_DECK_STATE", "deck_state must be an array");
            }
            Set<String> seenPlayers = new HashSet<>();
            for (JsonElement element : record.getAsJsonArray("deck_state")) {
                if (!element.isJsonObject()) {
                    throw fail("INVALID_DECK_STATE", "deck_state entry must be an object");
                }
                JsonObject deck = element.getAsJsonObject();
                String playerId = text(deck, "player_id");
                if (playerId == null || !seenPlayers.add(playerId)) {
                    throw fail("INVALID_DECK_STATE", "missing or duplicate player_id");
                }
                JsonObject template = deck.has("library_template") && deck.get("library_template").isJsonObject()
                        ? deck.getAsJsonObject("library_template") : null;
                String templateIdentity = text(template, "card_identity");
                if (templateIdentity == null) {
                    throw fail("INVALID_DECK_STATE", playerId + " requires library_template.card_identity");
                }
                int templateCount = nonNegativeInt(template, "count", playerId + " library_template");

                List<String> libraryOrder = null;
                if (deck.has("checkpoint_library") && !deck.get("checkpoint_library").isJsonNull()) {
                    if (!deck.get("checkpoint_library").isJsonObject()) {
                        throw fail("INVALID_DECK_STATE", playerId + " checkpoint_library must be an object");
                    }
                    JsonObject library = deck.getAsJsonObject("checkpoint_library");
                    if (!LIBRARY_COMPLETENESS.equals(text(library, "completeness"))) {
                        throw fail("PARTIAL_LIBRARY_REQUEST",
                                playerId + " checkpoint_library is not " + LIBRARY_COMPLETENESS);
                    }
                    if (!library.has("runs") || !library.get("runs").isJsonArray()
                            || library.getAsJsonArray("runs").isEmpty()) {
                        throw fail("INVALID_DECK_STATE", playerId + " checkpoint_library requires runs");
                    }
                    libraryOrder = new ArrayList<>();
                    for (JsonElement runElement : library.getAsJsonArray("runs")) {
                        if (!runElement.isJsonObject()) {
                            throw fail("INVALID_DECK_STATE", playerId + " library run must be an object");
                        }
                        JsonObject run = runElement.getAsJsonObject();
                        String semanticId = text(run, "semantic_id");
                        if (semanticId != null) {
                            if (run.size() != 1) {
                                throw fail("INVALID_DECK_STATE",
                                        playerId + " an object run names only its semantic_id");
                            }
                            JsonObject object = objectsById.get(semanticId);
                            if (object == null || !"library".equals(text(object, "zone"))) {
                                throw fail("UNKNOWN_LIBRARY_OBJECT", semanticId);
                            }
                            if (!playerId.equals(text(object, "owner"))) {
                                throw fail("LIBRARY_OBJECT_OWNER_MISMATCH", semanticId);
                            }
                            if (!coveredLibraryObjects.add(semanticId)) {
                                throw fail("DUPLICATE_LIBRARY_OBJECT", semanticId);
                            }
                            int position = libraryOrder.size();
                            if (!object.has("zone_position") || !object.get("zone_position").isJsonPrimitive()
                                    || object.get("zone_position").getAsInt() != position) {
                                throw fail("LIBRARY_POSITION_MISMATCH",
                                        semanticId + " is run index " + position);
                            }
                            String identity = text(object, "card_identity");
                            if (identity == null) {
                                throw fail("INVALID_CARD_IDENTITY", semanticId);
                            }
                            libraryObjects.add(new LibraryObject(semanticId, identity, playerId, position));
                            libraryOrder.add(identity);
                            continue;
                        }
                        String identity = text(run, "card_identity");
                        if (identity == null || run.size() != 2) {
                            throw fail("INVALID_DECK_STATE",
                                    playerId + " a template run names card_identity and count only");
                        }
                        if (!identity.equals(templateIdentity)) {
                            throw fail("LIBRARY_RUN_NOT_TEMPLATE", playerId);
                        }
                        int count = nonNegativeInt(run, "count", playerId + " library run");
                        if (count == 0) {
                            throw fail("INVALID_DECK_STATE", playerId + " library run count must be positive");
                        }
                        for (int index = 0; index < count; index++) {
                            libraryOrder.add(identity);
                        }
                    }
                }

                Integer handTemplateCount = null;
                if (deck.has("checkpoint_hand") && !deck.get("checkpoint_hand").isJsonNull()) {
                    if (!deck.get("checkpoint_hand").isJsonObject()) {
                        throw fail("INVALID_DECK_STATE", playerId + " checkpoint_hand must be an object");
                    }
                    JsonObject hand = deck.getAsJsonObject("checkpoint_hand");
                    if (!HAND_COMPLETENESS.equals(text(hand, "completeness"))) {
                        throw fail("INVALID_DECK_STATE", playerId + " checkpoint_hand is not COMPLETE");
                    }
                    if (!templateIdentity.equals(text(hand, "template_card_identity"))) {
                        throw fail("HAND_TEMPLATE_MISMATCH", playerId);
                    }
                    handTemplateCount = nonNegativeInt(hand, "template_count", playerId + " checkpoint_hand");
                }
                decks.add(new PlayerDeck(playerId, templateIdentity, templateCount,
                        libraryOrder == null ? null : List.copyOf(libraryOrder), handTemplateCount));
            }
        }
        for (Map.Entry<String, JsonObject> entry : objectsById.entrySet()) {
            if ("library".equals(text(entry.getValue(), "zone"))
                    && !decks.isEmpty()
                    && !coveredLibraryObjects.contains(entry.getKey())) {
                // A declared deck state that leaves a requested library object out
                // is a partial library request.
                throw fail("PARTIAL_LIBRARY_REQUEST", entry.getKey());
            }
        }
        return new XmageLosslessHiddenPlan(decks, libraryObjects, faceDown);
    }

    /**
     * The declared template must be exactly the lane's scaffolding filler for the
     * player, so the template remainder in a checkpoint library is the engine's
     * own scaffolding cards and nothing is fabricated around it.
     */
    void validateScaffolding(String playerId, List<String> scaffoldingMainboard) {
        for (PlayerDeck deck : decks) {
            if (!deck.playerId().equals(playerId)) {
                continue;
            }
            boolean uniform = scaffoldingMainboard.stream().allMatch(deck.templateIdentity()::equals);
            if (!uniform || scaffoldingMainboard.size() != deck.templateCount()) {
                throw fail("LIBRARY_TEMPLATE_MISMATCH",
                        playerId + " declares " + deck.templateCount() + " template cards; the lane's "
                                + "scaffolding has " + scaffoldingMainboard.size());
            }
        }
    }

    /** Every declared player must be a requested player. */
    void validatePlayers(Set<String> requestedPlayers) {
        for (PlayerDeck deck : decks) {
            if (!requestedPlayers.contains(deck.playerId())) {
                throw fail("UNKNOWN_DECK_PLAYER", deck.playerId());
            }
        }
        for (LibraryObject object : libraryObjects) {
            if (!requestedPlayers.contains(object.owner())) {
                throw fail("UNKNOWN_DECK_PLAYER", object.owner());
            }
        }
    }

    /**
     * Post-arrival application, once, while the engine is parked: place the
     * requested library cards with the engine's typed setup primitive, then
     * restore every declared complete library order through the native RG-06A
     * game-load API. Libraries wait for the opening hands; the face-down object
     * does not ({@link #applyPreStart}).
     */
    void applyAfterArrival(
            GameCommanderImpl game,
            Map<String, Player> playersByPid,
            XmageNativeStateRestoration restoration) {
        if (isEmpty()) {
            return;
        }
        List<LibraryObject> ordered = new ArrayList<>(libraryObjects);
        // Bottom-most first, so each later putOnTop lands above it; the complete
        // native order restore below is authoritative either way.
        ordered.sort(Comparator.comparing(LibraryObject::owner)
                .thenComparing(LibraryObject::position, Comparator.reverseOrder()));
        for (LibraryObject object : ordered) {
            Player owner = playersByPid.get(object.owner());
            if (owner == null) {
                throw fail("UNKNOWN_ACTOR", object.owner());
            }
            Card card = restoration.reserveVehicleCard(object.semanticId(), object.cardIdentity(), game);
            game.cheat(owner.getId(), List.of(card), List.of(), List.of(), List.of(), List.of(), List.of());
            if (game.getState().getZone(card.getId()) != mage.constants.Zone.LIBRARY) {
                throw fail("LIBRARY_PLACEMENT_FAILED", object.semanticId());
            }
        }

        List<XmageHiddenStateRestoration.LibraryOrder> libraries = new ArrayList<>();
        for (PlayerDeck deck : decks) {
            if (deck.libraryOrder() != null) {
                libraries.add(new XmageHiddenStateRestoration.LibraryOrder(
                        deck.playerId(), deck.libraryOrder()));
            }
        }
        if (libraries.isEmpty()) {
            return;
        }
        try {
            // The face-down object was turned face down before game start
            // (applyPreStart); this request orders libraries only.
            XmageHiddenStateRestoration.apply(game, playersByPid, restoration,
                    new XmageHiddenStateRestoration.Request(List.copyOf(libraries), List.of()));
        } catch (XmageHiddenStateRestoration.HiddenStateException exc) {
            throw rejected(exc);
        }
    }

    /**
     * Turns the declared face-down object face down before game start, right
     * after its setup placement, through the L7 native face-down game-load
     * path. Done any later, the object would sit face up through the mulligans
     * and every opponent's decision frame in that window would name it.
     */
    void applyPreStart(GameCommanderImpl game, XmageNativeStateRestoration restoration) {
        if (faceDownObjects.isEmpty()) {
            return;
        }
        List<XmageHiddenStateRestoration.FaceDownState> faceDown = new ArrayList<>();
        for (FaceDownObject object : faceDownObjects) {
            faceDown.add(new XmageHiddenStateRestoration.FaceDownState(object.semanticId(), object.type()));
        }
        try {
            XmageHiddenStateRestoration.applyFaceDownPreStart(game, restoration, List.copyOf(faceDown));
        } catch (XmageHiddenStateRestoration.HiddenStateException exc) {
            throw rejected(exc);
        }
    }

    private static XmageNativeStateRestoration.RestorationException rejected(
            XmageHiddenStateRestoration.HiddenStateException exc) {
        // The native detail can name a library or face-down identity; only the code leaves.
        String message = String.valueOf(exc.getMessage());
        int separator = message.indexOf(':');
        return fail("LOSSLESS_HIDDEN_STATE_REJECTED",
                separator > 0 ? message.substring(0, separator) : "NATIVE_RESTORE_REJECTED");
    }

    /**
     * The engine-direct lossless verification: every check performed, by kind
     * and player or semantic object, and every mismatch found. Both are coded by
     * player, semantic object and position only; no card identity appears.
     */
    record Verification(List<String> checks, List<String> mismatches) {
        Verification {
            checks = List.copyOf(checks);
            mismatches = List.copyOf(mismatches);
        }
    }

    /** The mismatches of {@link #verify}. */
    List<String> mismatches(
            GameCommanderImpl game,
            Map<String, Player> playersByPid,
            XmageNativeStateRestoration restoration) {
        return verify(game, playersByPid, restoration).mismatches();
    }

    /**
     * Engine-direct verification of every lossless declaration. A consumer can
     * tell a check that passed from one that never ran: each performed check is
     * listed whether or not it found a mismatch.
     */
    Verification verify(
            GameCommanderImpl game,
            Map<String, Player> playersByPid,
            XmageNativeStateRestoration restoration) {
        List<String> checks = new ArrayList<>();
        List<String> mismatches = new ArrayList<>();
        if (isEmpty()) {
            return new Verification(checks, mismatches);
        }
        for (PlayerDeck deck : decks) {
            Player player = playersByPid.get(deck.playerId());
            if (player == null) {
                mismatches.add("deck_state player missing: " + deck.playerId());
                continue;
            }
            if (deck.libraryOrder() != null) {
                checks.add("library_order:" + deck.playerId());
                List<UUID> live = player.getLibrary().getCardList();
                List<String> expected = deck.libraryOrder();
                if (live.size() != expected.size()) {
                    mismatches.add("library_order " + deck.playerId() + ": requested "
                            + expected.size() + " cards observed " + live.size());
                } else {
                    for (int index = 0; index < live.size(); index++) {
                        Card card = game.getCard(live.get(index));
                        if (card == null || !expected.get(index).equals(card.getName())) {
                            mismatches.add("library_order " + deck.playerId()
                                    + ": diverges at position " + index);
                            break;
                        }
                    }
                }
            }
            if (deck.handTemplateCount() != null) {
                checks.add("hand_composition:" + deck.playerId());
                Set<UUID> injected = restoration.injectedHandIdsForTests(deck.playerId());
                int expectedSize = injected.size() + deck.handTemplateCount();
                if (player.getHand().size() != expectedSize) {
                    mismatches.add("hand_composition " + deck.playerId() + ": requested "
                            + expectedSize + " cards observed " + player.getHand().size());
                }
                for (Card card : player.getHand().getCards(game)) {
                    if (!injected.contains(card.getId()) && !deck.templateIdentity().equals(card.getName())) {
                        mismatches.add("hand_composition " + deck.playerId()
                                + ": a hand card is neither requested nor template");
                        break;
                    }
                }
            }
        }
        for (LibraryObject object : libraryObjects) {
            checks.add("library_object:" + object.semanticId());
            Player owner = playersByPid.get(object.owner());
            UUID nativeId;
            try {
                nativeId = restoration.injectedObjectId(object.semanticId());
            } catch (XmageNativeStateRestoration.RestorationException exc) {
                mismatches.add("library_object " + object.semanticId() + ": not placed");
                continue;
            }
            List<UUID> live = owner == null ? List.of() : owner.getLibrary().getCardList();
            if (object.position() >= live.size() || !nativeId.equals(live.get(object.position()))) {
                mismatches.add("library_object " + object.semanticId()
                        + ": not at requested position " + object.position());
            }
        }
        for (FaceDownObject object : faceDownObjects) {
            checks.add("face_down:" + object.semanticId());
            UUID nativeId;
            try {
                nativeId = restoration.injectedObjectId(object.semanticId());
            } catch (XmageNativeStateRestoration.RestorationException exc) {
                mismatches.add("face_down " + object.semanticId() + ": not placed");
                continue;
            }
            Permanent permanent = game.getPermanent(nativeId);
            Card card = game.getCard(nativeId);
            if (permanent == null || card == null) {
                mismatches.add("face_down " + object.semanticId() + ": not on the battlefield");
                continue;
            }
            if (!object.cardIdentity().equals(card.getName())) {
                mismatches.add("face_down " + object.semanticId() + ": underlying card is not the requested one");
            }
            BecomesFaceDownCreatureEffect.FaceDownType observed =
                    BecomesFaceDownCreatureEffect.findFaceDownType(game, permanent);
            if (!permanent.isFaceDown(game) || observed != object.type()) {
                mismatches.add("face_down " + object.semanticId() + ": requested " + object.type()
                        + " observed " + (permanent.isFaceDown(game) ? String.valueOf(observed) : "FACE_UP"));
            }
        }
        return new Verification(checks, mismatches);
    }

    /** Descriptor rows for the lane's supported-dimensions payload. */
    static JsonArray supportedDescriptor() {
        JsonArray rows = new JsonArray();
        rows.add("SLOT-04 lossless successor records: complete checkpoint library per declared player "
                + "(requested library objects at exact positions plus the scaffolding template "
                + "remainder), placed after the opening hands and ordered by the native game-load API");
        rows.add("SLOT-04 lossless successor records: one face-down battlefield object with an explicit "
                + "native FaceDownType (MANIFESTED, CLOAKED, MORPHED, MEGAMORPHED, DISGUISED)");
        rows.add("SLOT-04 lossless successor records: complete checkpoint hand (requested hand objects "
                + "plus an exact count of template cards)");
        return rows;
    }

    /** Package-private view for tests. */
    Map<String, Integer> libraryObjectPositionsForTests() {
        Map<String, Integer> positions = new HashMap<>();
        for (LibraryObject object : libraryObjects) {
            positions.put(object.semanticId(), object.position());
        }
        return positions;
    }
}
