package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.game.Game;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageActorIdentityProjectionAdversarialTest {

    @Test
    void knownDeckPrecomputedPrivilegedRefCannotPredictActorFacingHandle() throws Exception {
        Fixture first = fixture("ws34-known-deck-a");
        String privilegedRef = precomputedKnownDeckRef();
        assertEquals(
                privilegedRef,
                privilegedRefForHoney(first),
                "test must reproduce the actual deterministic privileged ledger reference"
        );
        JsonObject privilegedView = privilegedView(privilegedRef);

        String firstActorHandle = projectedObjectId(first.game(), first.players().get(0), privilegedView);
        String repeatedHandle = projectedObjectId(first.game(), first.players().get(0), privilegedView);
        String otherViewerHandle = projectedObjectId(first.game(), first.players().get(1), privilegedView);

        assertTrue(firstActorHandle.startsWith("obj-"));
        assertFalse(firstActorHandle.contains("card-P2-"));
        assertNotEquals(privilegedRef, firstActorHandle);
        assertEquals(firstActorHandle, repeatedHandle, "one viewer must receive a stable handle inside one game session");
        assertNotEquals(firstActorHandle, otherViewerHandle, "different viewers must not share an invertible object handle");

        Fixture second = fixture("ws34-known-deck-b");
        assertEquals(privilegedRef, privilegedRefForHoney(second));
        String secondSessionHandle = projectedObjectId(second.game(), second.players().get(0), privilegedView);
        assertNotEquals(firstActorHandle, secondSessionHandle, "independent games must not reuse a deterministic known-deck handle");
    }

    private static String projectedObjectId(Game game, XmageFullGamePlayer viewer, JsonObject privilegedView) {
        return XmageActorIdentityProjection.actorView(game, viewer, privilegedView)
                .get("object_id")
                .getAsString();
    }

    private static JsonObject privilegedView(String privilegedRef) {
        JsonObject view = new JsonObject();
        view.addProperty("object_id", privilegedRef);
        view.addProperty("name", "Visible transition sentinel");
        return view;
    }

    private static String privilegedRefForHoney(Fixture fixture) throws Exception {
        Card honey = fixture.players().get(1).getLibrary().getCards(fixture.game()).stream()
                .filter(card -> "Swords to Plowshares".equals(card.getName()))
                .findFirst()
                .orElse(null);
        assertNotNull(honey, "known-deck honey sentinel must be present in P2 library");
        Map<UUID, String> refs = physicalCardRefs(fixture.knowledgeLedger());
        return refs.get(honey.getMainCard().getId());
    }

    @SuppressWarnings("unchecked")
    private static Map<UUID, String> physicalCardRefs(XmageKnowledgeLedger ledger) throws Exception {
        Field field = XmageKnowledgeLedger.class.getDeclaredField("physicalCardRefs");
        field.setAccessible(true);
        return (Map<UUID, String>) field.get(ledger);
    }

    private static String precomputedKnownDeckRef() {
        List<String> main = new ArrayList<>(Collections.nCopies(99, "Plains"));
        main.set(0, "Swords to Plowshares");
        List<String> sortedMain = main.stream().sorted().toList();
        List<String> command = List.of("Isamaru, Hound of Konda");
        String deckFingerprint = sha256(
                "main=" + String.join("\u0000", sortedMain)
                        + "\u0001command=" + String.join("\u0000", command.stream().sorted().toList())
        );
        return "card-P2-" + sha256(
                deckFingerprint + "\u0000main\u0000Swords to Plowshares\u00001"
        ).substring(0, 20);
    }

    private static Fixture fixture(String label) throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>();
        for (int seat = 0; seat < 4; seat++) {
            List<String> mainboard = new ArrayList<>(Collections.nCopies(99, "Plains"));
            if (seat == 1) {
                mainboard.set(0, "Swords to Plowshares");
            }
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    label + "-seat-" + seat,
                    String.format("%064x", seat + 101),
                    mainboard,
                    List.of("Isamaru, Hound of Konda")
            );
            handles.add(imported.deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                label,
                handles,
                0,
                40,
                424242L,
                importer
        );
        return new Fixture(
                field(session, "game", Game.class),
                players(session),
                field(session, "knowledgeLedger", XmageKnowledgeLedger.class)
        );
    }

    @SuppressWarnings("unchecked")
    private static List<XmageFullGamePlayer> players(XmageFullGameSession session) throws Exception {
        return (List<XmageFullGamePlayer>) field(session, "players", List.class);
    }

    private static <T> T field(Object target, String name, Class<T> type) throws Exception {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return type.cast(field.get(target));
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exc) {
            throw new IllegalStateException(exc);
        }
    }

    private record Fixture(
            Game game,
            List<XmageFullGamePlayer> players,
            XmageKnowledgeLedger knowledgeLedger
    ) {
    }
}
