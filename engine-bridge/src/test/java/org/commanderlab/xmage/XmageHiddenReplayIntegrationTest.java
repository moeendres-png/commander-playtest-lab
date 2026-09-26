package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.effects.common.continuous.BecomesFaceDownCreatureEffect;
import mage.cards.Card;
import mage.constants.PhaseStep;
import mage.constants.TurnPhase;
import mage.constants.Zone;
import mage.game.CommanderFreeForAll;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** L7 hidden-state + privacy-safe replay integration qualification. */
class XmageHiddenReplayIntegrationTest {

    private static final long SEED = 424242L;

    @Test
    void exactLibraryOrderRestoresWithoutChangingPublicOrOpponentPrincipalHash() {
        Arrived arrived = arrive(plan("l7-library", false), "l7-library");
        Player p1 = arrived.seats().get("P1");
        Player p2 = arrived.seats().get("P2");

        List<String> before = libraryNames(p1, arrived.game());
        assertTrue(new HashSet<>(before).size() > 1,
                "Esika scaffolding must provide multiple card identities");
        List<String> requested = new ArrayList<>(before);
        Collections.rotate(requested, 1);
        assertNotEquals(before, requested, "test must request a different exact order");

        String publicHashBefore =
                XmageAuditEventLog.stateHash(XmageFullGameStateRedactor.publicView(arrived.game()));
        String p2HashBefore =
                XmageAuditEventLog.stateHash(XmageFullGameStateRedactor.actorView(arrived.game(), p2));

        XmageHiddenStateRestoration.Receipt receipt = XmageHiddenStateRestoration.apply(
                arrived.game(),
                arrived.seats(),
                arrived.restoration(),
                new XmageHiddenStateRestoration.Request(
                        List.of(new XmageHiddenStateRestoration.LibraryOrder("P1", requested)),
                        List.of()));

        assertEquals(1, receipt.librariesRestored());
        assertEquals(0, receipt.faceDownPermanentsRestored());
        assertEquals(requested, libraryNames(p1, arrived.game()));

        String publicHashAfter =
                XmageAuditEventLog.stateHash(XmageFullGameStateRedactor.publicView(arrived.game()));
        String p2HashAfter =
                XmageAuditEventLog.stateHash(XmageFullGameStateRedactor.actorView(arrived.game(), p2));
        assertEquals(publicHashBefore, publicHashAfter,
                "public replay reference must not encode hidden library order");
        assertEquals(p2HashBefore, p2HashAfter,
                "non-entitled principal reference must not encode opponent library order");

        JsonObject p1FromP2 = playerRow(
                XmageFullGameStateRedactor.actorView(arrived.game(), p2),
                p1.getId().toString());
        assertFalse(p1FromP2.has("library"));
        assertEquals(0, p1FromP2.getAsJsonArray("granted_library").size());
        assertEquals(requested.size(), p1FromP2.get("library_count").getAsInt());
    }

    @Test
    void incompleteLibraryOrderFailsClosedWithoutMutation() {
        Arrived arrived = arrive(plan("l7-incomplete", false), "l7-incomplete");
        Player p1 = arrived.seats().get("P1");
        List<UUID> beforeIds = new ArrayList<>(p1.getLibrary().getCardList());
        List<String> incomplete = new ArrayList<>(libraryNames(p1, arrived.game()));
        incomplete.remove(incomplete.size() - 1);

        XmageHiddenStateRestoration.HiddenStateException failure = assertThrows(
                XmageHiddenStateRestoration.HiddenStateException.class,
                () -> XmageHiddenStateRestoration.apply(
                        arrived.game(),
                        arrived.seats(),
                        arrived.restoration(),
                        new XmageHiddenStateRestoration.Request(
                                List.of(new XmageHiddenStateRestoration.LibraryOrder(
                                        "P1", incomplete)),
                                List.of())));
        assertTrue(failure.getMessage().startsWith("INCOMPLETE_LIBRARY_ORDER"));
        assertEquals(beforeIds, new ArrayList<>(p1.getLibrary().getCardList()));
    }

    @Test
    void nativeFaceDownRejectionCannotPartiallyApplyPreparedLibraryOrder() {
        Arrived arrived = arrive(plan("l7-atomic", true), "l7-atomic");
        Player p1 = arrived.seats().get("P1");
        List<UUID> beforeIds = new ArrayList<>(p1.getLibrary().getCardList());
        List<String> requested = new ArrayList<>(libraryNames(p1, arrived.game()));
        Collections.rotate(requested, 1);

        XmageHiddenStateRestoration.HiddenStateException failure = assertThrows(
                XmageHiddenStateRestoration.HiddenStateException.class,
                () -> XmageHiddenStateRestoration.apply(
                        arrived.game(),
                        arrived.seats(),
                        arrived.restoration(),
                        new XmageHiddenStateRestoration.Request(
                                List.of(new XmageHiddenStateRestoration.LibraryOrder(
                                        "P1", requested)),
                                List.of(new XmageHiddenStateRestoration.FaceDownState(
                                        "obj:p1-bears",
                                        BecomesFaceDownCreatureEffect.FaceDownType.MORPHED)))));
        assertTrue(failure.getMessage().startsWith("NATIVE_FACE_DOWN_RESTORE_REJECTED"));
        assertEquals(beforeIds, new ArrayList<>(p1.getLibrary().getCardList()),
                "library must not mutate when the native face-down precondition fails");
        Permanent bears = arrived.game().getPermanent(
                arrived.restoration().injectedObjectId("obj:p1-bears"));
        assertFalse(bears.isFaceDown(arrived.game()));
    }

    @Test
    void restoredFaceDownIdentityIsVisibleOnlyToCurrentController() throws Exception {
        Arrived arrived = arrive(plan("l7-facedown", true), "l7-facedown");
        UUID bearsId = arrived.restoration().injectedObjectId("obj:p1-bears");

        XmageHiddenStateRestoration.Receipt receipt = XmageHiddenStateRestoration.apply(
                arrived.game(),
                arrived.seats(),
                arrived.restoration(),
                new XmageHiddenStateRestoration.Request(
                        List.of(),
                        List.of(new XmageHiddenStateRestoration.FaceDownState(
                                "obj:p1-bears",
                                BecomesFaceDownCreatureEffect.FaceDownType.MANIFESTED))));
        assertEquals(1, receipt.faceDownPermanentsRestored());

        JsonObject p1Item = battlefieldItem(
                XmageFullGameStateRedactor.actorView(
                        arrived.game(), arrived.seats().get("P1")),
                bearsId.toString());
        JsonObject p2Item = battlefieldItem(
                XmageFullGameStateRedactor.actorView(
                        arrived.game(), arrived.seats().get("P2")),
                bearsId.toString());
        JsonObject publicItem = battlefieldItem(
                XmageFullGameStateRedactor.publicView(arrived.game()),
                bearsId.toString());

        assertTrue(p1Item.get("face_down").getAsBoolean());
        assertEquals("Grizzly Bears", p1Item.get("private_identity").getAsString());
        assertFalse(p2Item.has("private_identity"));
        assertFalse(publicItem.has("private_identity"));
        assertNotEquals("Grizzly Bears", p2Item.get("name").getAsString());
        assertNotEquals("Grizzly Bears", publicItem.get("name").getAsString());

        XmageFullGameDecisionController controller = controller(arrived.session());
        for (JsonElement element : controller.transcript()) {
            JsonObject event = element.getAsJsonObject();
            assertFalse(event.has("private_actor_state_reference"),
                    "exportable transcript event must not retain private state hashes");
        }
    }

    @Test
    void publicStateReferenceIsPublicOnlyAndTranscriptCannotBePrivateHashOracle()
            throws Exception {
        Arrived arrived = arrive(plan("l7-transcript", true), "l7-transcript");
        XmageHiddenStateRestoration.apply(
                arrived.game(),
                arrived.seats(),
                arrived.restoration(),
                new XmageHiddenStateRestoration.Request(
                        List.of(),
                        List.of(new XmageHiddenStateRestoration.FaceDownState(
                                "obj:p1-bears",
                                BecomesFaceDownCreatureEffect.FaceDownType.MANIFESTED))));

        JsonObject pending = arrived.session().pendingDecisionPayload()
                .getAsJsonObject("decision");
        assertTrue(pending.get("public_state_reference").getAsString()
                .startsWith("public-view:"));
        assertTrue(pending.get("private_actor_state_reference").getAsString()
                .startsWith("actor-view:"));

        XmageFullGameDecisionController controller = controller(arrived.session());
        String transcript = controller.transcript().toString();
        assertFalse(transcript.contains("private_actor_state_reference"));
        assertFalse(transcript.contains("Grizzly Bears"),
                "private restored face-down identity must not enter audit transcript");
    }

    @Test
    void legacyFrozenLibraryAndFaceDownRecordsRemainFailClosed() {
        XmageHiddenStateRestoration.HiddenStateException library = assertThrows(
                XmageHiddenStateRestoration.HiddenStateException.class,
                () -> XmageHiddenStateRestoration.fromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord("HIDDEN_02")));
        assertTrue(library.getMessage().startsWith("LEGACY_LIBRARY_ORDER_AMBIGUOUS"));

        JsonObject synthetic = new JsonObject();
        JsonArray objects = new JsonArray();
        JsonObject object = new JsonObject();
        object.addProperty("semantic_id", "obj:legacy-facedown");
        object.addProperty("zone", "battlefield");
        object.addProperty("face_down", true);
        objects.add(object);
        synthetic.add("semantic_objects", objects);
        XmageHiddenStateRestoration.HiddenStateException faceDown = assertThrows(
                XmageHiddenStateRestoration.HiddenStateException.class,
                () -> XmageHiddenStateRestoration.fromFrozenRecord(synthetic));
        assertTrue(faceDown.getMessage().startsWith("LEGACY_FACE_DOWN_TYPE_AMBIGUOUS"));
    }

    @Test
    void explicitJsonRequestRequiresLosslessFaceDownType() {
        JsonObject root = new JsonObject();
        root.addProperty("schema_version", XmageHiddenStateRestoration.SCHEMA_VERSION);
        root.add("libraries", new JsonArray());
        JsonArray faceDown = new JsonArray();
        JsonObject row = new JsonObject();
        row.addProperty("semantic_id", "obj:x");
        faceDown.add(row);
        root.add("face_down", faceDown);

        XmageHiddenStateRestoration.HiddenStateException failure = assertThrows(
                XmageHiddenStateRestoration.HiddenStateException.class,
                () -> XmageHiddenStateRestoration.parse(root));
        assertTrue(failure.getMessage().startsWith("INVALID_FACE_DOWN_STATE"));
    }

    @Test
    void sameSeedFreshSessionsRestoreSameSemanticHiddenStateWithoutPublicLeak() {
        Arrived first = arrive(plan("l7-replay-a", true), "l7-replay-a");
        Arrived second = arrive(plan("l7-replay-b", true), "l7-replay-b");

        List<String> orderA = sortedSemanticOrder(first.seats().get("P1"), first.game());
        List<String> orderB = sortedSemanticOrder(second.seats().get("P1"), second.game());
        assertEquals(orderA, orderB);

        XmageHiddenStateRestoration.Request requestA =
                new XmageHiddenStateRestoration.Request(
                        List.of(new XmageHiddenStateRestoration.LibraryOrder("P1", orderA)),
                        List.of(new XmageHiddenStateRestoration.FaceDownState(
                                "obj:p1-bears",
                                BecomesFaceDownCreatureEffect.FaceDownType.MANIFESTED)));
        XmageHiddenStateRestoration.Request requestB =
                new XmageHiddenStateRestoration.Request(
                        List.of(new XmageHiddenStateRestoration.LibraryOrder("P1", orderB)),
                        List.of(new XmageHiddenStateRestoration.FaceDownState(
                                "obj:p1-bears",
                                BecomesFaceDownCreatureEffect.FaceDownType.MANIFESTED)));

        XmageHiddenStateRestoration.apply(
                first.game(), first.seats(), first.restoration(), requestA);
        XmageHiddenStateRestoration.apply(
                second.game(), second.seats(), second.restoration(), requestB);

        assertEquals(orderA, libraryNames(first.seats().get("P1"), first.game()));
        assertEquals(orderB, libraryNames(second.seats().get("P1"), second.game()));
        assertEquals(
                semanticPublicProjection(first),
                semanticPublicProjection(second),
                "fresh-session replay must agree on public semantics without hidden identity hashes");
    }

    private static XmageNativeStateRestoration.Plan plan(String id, boolean bears) {
        List<XmageNativeStateRestoration.RequestedObject> objects = bears
                ? List.of(new XmageNativeStateRestoration.RequestedObject(
                        "obj:p1-bears", "Grizzly Bears", "P1", "P1",
                        Zone.BATTLEFIELD, false))
                : List.of();
        return new XmageNativeStateRestoration.Plan(
                id, 3, SEED,
                List.of(
                        new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P3", 3, 40)),
                List.of(
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Esika, God of the Tree", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P3-A", "Rograkh, Son of Rohgahh", "P3", 0)),
                List.of(),
                objects,
                1, TurnPhase.PRECOMBAT_MAIN, PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
    }

    private static Arrived arrive(XmageNativeStateRestoration.Plan plan, String tag) {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, tag);
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new Arrived(session, restoration, seats);
    }

    private static List<String> libraryNames(Player player, CommanderFreeForAll game) {
        List<String> result = new ArrayList<>();
        for (UUID id : player.getLibrary().getCardList()) {
            Card card = game.getCard(id);
            if (card == null) {
                throw new AssertionError("missing library card " + id);
            }
            result.add(card.getName());
        }
        return result;
    }

    private static List<String> sortedSemanticOrder(Player player, CommanderFreeForAll game) {
        List<String> result = new ArrayList<>(libraryNames(player, game));
        Collections.sort(result);
        return result;
    }

    private static JsonObject playerRow(JsonObject view, String playerId) {
        for (JsonElement element : view.getAsJsonArray("players")) {
            JsonObject row = element.getAsJsonObject();
            if (playerId.equals(row.get("player_id").getAsString())) {
                return row;
            }
        }
        throw new AssertionError("player row missing " + playerId);
    }

    private static JsonObject battlefieldItem(JsonObject view, String objectId) {
        for (JsonElement playerElement : view.getAsJsonArray("players")) {
            JsonObject player = playerElement.getAsJsonObject();
            for (JsonElement permanentElement : player.getAsJsonArray("battlefield")) {
                JsonObject permanent = permanentElement.getAsJsonObject();
                if (objectId.equals(permanent.get("object_id").getAsString())) {
                    return permanent;
                }
            }
        }
        throw new AssertionError("battlefield object missing " + objectId);
    }

    private static XmageFullGameDecisionController controller(XmageFullGameSession session)
            throws Exception {
        Field field = XmageFullGameSession.class.getDeclaredField("controller");
        field.setAccessible(true);
        return (XmageFullGameDecisionController) field.get(session);
    }

    /**
     * Twin-stable public semantics for this bounded L7 test. Native UUIDs and
     * game ids are intentionally excluded; hidden identities/order are absent
     * by construction from the public projection.
     */
    private static JsonObject semanticPublicProjection(Arrived arrived) {
        JsonObject view = XmageFullGameStateRedactor.publicView(arrived.game()).deepCopy();
        view.remove("game_id");
        view.remove("active_player_id");
        view.remove("priority_player_id");
        for (JsonElement playerElement : view.getAsJsonArray("players")) {
            JsonObject player = playerElement.getAsJsonObject();
            player.remove("player_id");
            for (JsonElement permanentElement : player.getAsJsonArray("battlefield")) {
                permanentElement.getAsJsonObject().remove("object_id");
                permanentElement.getAsJsonObject().remove("controller_id");
            }
            for (String zone : List.of("graveyard", "command")) {
                if (!player.has(zone) || !player.get(zone).isJsonArray()) {
                    continue;
                }
                for (JsonElement cardElement : player.getAsJsonArray(zone)) {
                    cardElement.getAsJsonObject().remove("object_id");
                }
            }
        }
        if (view.has("commander_status") && view.get("commander_status").isJsonArray()) {
            for (JsonElement element : view.getAsJsonArray("commander_status")) {
                JsonObject commander = element.getAsJsonObject();
                commander.remove("owner_id");
                if (commander.has("commander_damage_to_player")) {
                    for (JsonElement damageElement
                            : commander.getAsJsonArray("commander_damage_to_player")) {
                        damageElement.getAsJsonObject().remove("player_id");
                    }
                }
            }
        }
        return view;
    }

    private record Arrived(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats
    ) {
        CommanderFreeForAll game() {
            return session.restorationGame();
        }
    }
}
