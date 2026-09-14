package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageFullGameObservationGatewayTest {

    @Test
    void actorViewHidesOpponentHandsAndAllLibraryIdentities() throws Exception {
        Fixture fixture = fixture();
        JsonObject view = XmageFullGameStateRedactor.actorView(fixture.game(), fixture.actor());
        JsonArray players = view.getAsJsonArray("players");

        assertEquals(4, players.size());
        for (int index = 0; index < players.size(); index++) {
            JsonObject player = players.get(index).getAsJsonObject();
            assertTrue(player.has("library_count"));
            assertFalse(player.has("library"), "library identities/order must never be exported");
            if (index == 0) {
                assertTrue(player.has("hand"), "actor must receive own hand");
            } else {
                assertFalse(player.has("hand"), "opponent hand identities must be hidden");
            }
        }
    }

    @Test
    void outboundEnvelopeFailsClosedOnHiddenObjectIdAndPrivateOnlyCardName() throws Exception {
        Fixture fixture = fixture();
        Card honey = fixture.honeyCard();
        assertNotNull(honey);

        JsonArray safeOptions = new JsonArray();
        safeOptions.add(XmageFullGameDecisionController.option(
                "pass",
                "Pass priority",
                "pass_priority",
                new JsonObject()
        ));
        XmageFullGameObservationGateway.SafeDecision safe =
                XmageFullGameObservationGateway.validate(
                        fixture.game(),
                        fixture.actor(),
                        "Choose a legal action",
                        new JsonObject(),
                        safeOptions,
                        null
                );
        assertEquals("Choose a legal action", safe.prompt());

        IllegalStateException idLeak = assertThrows(
                IllegalStateException.class,
                () -> XmageFullGameObservationGateway.validate(
                        fixture.game(),
                        fixture.actor(),
                        "forbidden-id=" + honey.getId(),
                        new JsonObject(),
                        safeOptions,
                        null
                )
        );
        assertTrue(idLeak.getMessage().contains("HIDDEN_INFORMATION_LEAK"));

        JsonObject metadata = new JsonObject();
        metadata.addProperty("forbidden_honeycard", honey.getName());
        JsonArray leakingOptions = new JsonArray();
        leakingOptions.add(XmageFullGameDecisionController.option(
                "hidden-choice",
                "Opaque choice",
                "generic",
                metadata
        ));
        IllegalStateException metadataLeak = assertThrows(
                IllegalStateException.class,
                () -> XmageFullGameObservationGateway.validate(
                        fixture.game(),
                        fixture.actor(),
                        "Choose",
                        new JsonObject(),
                        leakingOptions,
                        null
                )
        );
        assertTrue(metadataLeak.getMessage().contains("HIDDEN_INFORMATION_LEAK"));

        JsonObject source = new JsonObject();
        source.addProperty("forbidden_honeycard", honey.getName());
        IllegalStateException sourceLeak = assertThrows(
                IllegalStateException.class,
                () -> XmageFullGameObservationGateway.validate(
                        fixture.game(),
                        fixture.actor(),
                        "Choose",
                        new JsonObject(),
                        safeOptions,
                        source
                )
        );
        assertTrue(sourceLeak.getMessage().contains("HIDDEN_INFORMATION_LEAK"));
    }

    private static Fixture fixture() throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>();
        for (int seat = 0; seat < 4; seat++) {
            List<String> mainboard = new ArrayList<>(Collections.nCopies(99, "Plains"));
            if (seat == 1) {
                mainboard.set(0, "Swords to Plowshares");
            }
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    "ws18-observation-seat-" + seat,
                    String.format("%064x", seat + 1),
                    mainboard,
                    List.of("Isamaru, Hound of Konda")
            );
            handles.add(imported.deckHandle());
        }

        XmageFullGameSession session = new XmageFullGameSession(
                "ws18-observation-honeycard",
                handles,
                0,
                40,
                424242L,
                importer
        );
        Game game = field(session, "game", Game.class);
        List<XmageFullGamePlayer> players = players(session);
        Player actor = players.get(0);
        Player opponent = players.get(1);
        Card honey = null;
        for (Card card : opponent.getLibrary().getCards(game)) {
            if ("Swords to Plowshares".equals(card.getName())) {
                honey = card;
                break;
            }
        }
        assertNotNull(honey, "honeycard must remain in the hidden opponent library before game start");
        return new Fixture(game, actor, honey);
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

    private record Fixture(Game game, Player actor, Card honeyCard) {
    }
}
