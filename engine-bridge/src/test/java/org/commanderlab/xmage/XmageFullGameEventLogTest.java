package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.game.Game;
import org.junit.jupiter.api.Test;

import java.util.HashSet;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #662 SLOT-06: {@code export_event_log} on the full-game production lane.
 *
 * <p>The log is the engine's own public event tape: monotonic sequence, players
 * by seat, linked to the decision stream by the decision count, and free of
 * hidden information (no hand or library card of any player is named, and no
 * engine object id appears). It is refused before the game starts.</p>
 */
class XmageFullGameEventLogTest {

    @Test
    void publicEventLogIsMonotonicSeatNamedAndFreeOfHiddenCards() throws Exception {
        XmageFullGameSession session = FullGameTestPilot.realDeckSession("issue662-event-log", 2, 6640L);
        FullGameTestPilot.play(session, 120);
        JsonObject log = session.eventLogPayload(0);
        JsonArray events = log.getAsJsonArray("events");
        assertTrue(events.size() > 10, "a real game produces public events: " + events.size());
        assertEquals("public", log.get("observation_scope").getAsString());
        assertEquals(session.pendingDecisionPayload().get("decision_count").getAsLong(),
                log.get("decision_count").getAsLong());

        long previous = 0;
        for (JsonElement element : events) {
            long sequence = element.getAsJsonObject().get("sequence").getAsLong();
            assertTrue(sequence > previous, "monotonic sequence");
            previous = sequence;
        }
        // Incremental read: exactly the events after an offset.
        int half = events.size() / 2;
        assertEquals(events.size() - half, session.eventLogPayload(half).getAsJsonArray("events").size());

        // Hidden information: no card currently in a hand or library is named, and
        // no engine object id appears anywhere.
        Game game = session.restorationGame();
        Set<String> hiddenNames = new HashSet<>();
        Set<String> engineIds = new HashSet<>();
        game.getPlayers().values().forEach(player -> {
            for (Card card : player.getHand().getCards(game)) {
                hiddenNames.add(card.getName());
                engineIds.add(card.getId().toString());
            }
            for (Card card : player.getLibrary().getCards(game)) {
                engineIds.add(card.getId().toString());
            }
            engineIds.add(player.getId().toString());
        });
        String text = log.toString();
        for (String id : engineIds) {
            assertFalse(text.contains(id), "engine id leaked into the public log: " + id);
        }
        // A name may be public through another copy (e.g. a land on the battlefield);
        // the tape only names objects with a public identity at the event.
        for (JsonElement element : events) {
            JsonObject event = element.getAsJsonObject();
            if (event.has("public_identity") && !event.get("public_identity").getAsBoolean()) {
                assertFalse(event.has("source_name") || event.has("target_name"),
                        "an event without public identity names an object: " + event);
            }
        }
        assertTrue(hiddenNames.size() > 0);
        // A name that only exists in hidden zones right now (no copy in any public
        // zone) is named by no event. The test pilot only plays lands and passes, so
        // no card went from a public zone back to a hidden one.
        Set<String> publicNames = new HashSet<>();
        game.getBattlefield().getAllPermanents().forEach(permanent -> publicNames.add(permanent.getName()));
        game.getExile().getAllCards(game).forEach(card -> publicNames.add(card.getName()));
        game.getStack().forEach(object -> publicNames.add(object.getName()));
        game.getState().getCommand().forEach(object -> publicNames.add(object.getName()));
        game.getPlayers().values().forEach(player ->
                player.getGraveyard().getCards(game).forEach(card -> publicNames.add(card.getName())));
        Set<String> hiddenOnly = new HashSet<>(hiddenNames);
        hiddenOnly.removeAll(publicNames);
        assertTrue(hiddenOnly.size() > 0, "the control is not vacuous");
        for (JsonElement element : events) {
            JsonObject event = element.getAsJsonObject();
            for (String field : new String[] {"source_name", "target_name"}) {
                if (event.has(field) && !event.get(field).isJsonNull()) {
                    assertFalse(hiddenOnly.contains(event.get(field).getAsString()),
                            "the public log names a card that is only in hidden zones: " + event);
                }
            }
        }
    }

    @Test
    void eventLogRejectsOutOfRangeOffsetAndUnstartedGame() throws Exception {
        XmageFullGameSession session = FullGameTestPilot.realDeckSession("issue662-event-log-bounds", 2, 6641L);
        int size = session.eventLogPayload(0).get("latest_offset").getAsInt();
        assertThrows(IllegalArgumentException.class, () -> session.eventLogPayload(size + 1));
        assertThrows(IllegalArgumentException.class, () -> session.eventLogPayload(-1));

        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        request.addProperty("request_id", "issue662-log");
        request.addProperty("message_type", "export_event_log");
        request.add("payload", new JsonObject());
        JsonObject response = com.google.gson.JsonParser.parseString(
                bridge.handle(request.toString()).json()).getAsJsonObject();
        assertFalse(response.get("success").getAsBoolean(), "no event log without a game");
    }
}
