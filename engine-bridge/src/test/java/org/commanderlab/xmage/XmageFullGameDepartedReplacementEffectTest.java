package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
import mage.cards.decks.Deck;
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.game.mulligan.MulliganType;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * CR 800.4a: a player who left the game makes no choices. The engine can still
 * ask such a player to order replacement effects, for example for a permanent
 * that is destroyed in the state-based-action pass in which its controller
 * lost to the same combat damage (plan seed 13, pod 040: the game was already
 * won when the lane failed with {@code PLAYER_LEFT_GAME_UNSUPPORTED_DECISION:
 * replacement_effect}).
 *
 * <p>XMage's own {@code HumanPlayer.chooseReplacementEffect} leaves its
 * {@code while (canRespond())} loop for a player who cannot respond and returns
 * 0. The bridge now does the same: no frame is published, the retirement is
 * recorded, and the lane goes on.</p>
 */
class XmageFullGameDepartedReplacementEffectTest {

    private static final Map<String, String> EFFECTS = new LinkedHashMap<>();

    static {
        EFFECTS.put("effect-a", "Exile that permanent instead (first source)");
        EFFECTS.put("effect-b", "Exile that permanent instead (second source)");
    }

    @Test
    void aDepartedPlayersReplacementChoiceIsAnsweredWithTheNativeNoResponse() {
        Fixture fixture = liveFixture();
        fixture.player.leave();
        assertFalse(fixture.player.isInGame(), "the player left the game");

        int index = fixture.player.chooseReplacementEffect(EFFECTS, new LinkedHashMap<>(), fixture.game);

        assertEquals(0, index, "HumanPlayer returns 0 once the player cannot respond");
        assertNull(fixture.controller.terminalFailure(), "the lane does not fail closed");
        assertNull(fixture.controller.pendingDecision(), "no frame is published for a player who left");
        JsonObject cancelled = null;
        for (JsonElement event : fixture.controller.transcript()) {
            JsonObject entry = event.getAsJsonObject();
            if (entry.has("event_type")
                    && "engine_decision_cancelled".equals(entry.get("event_type").getAsString())) {
                cancelled = entry.getAsJsonObject("payload");
            }
        }
        assertTrue(cancelled != null, "the retirement is recorded");
        assertEquals("replacement_effect", cancelled.get("decision_class").getAsString());
        assertEquals("player_left_game", cancelled.get("reason").getAsString());
    }

    @Test
    void aPlayerStillInTheGameIsAskedAndItsChoiceIsReturned() throws Exception {
        Fixture fixture = liveFixture();
        AtomicReference<Integer> answer = new AtomicReference<>();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread engine = new Thread(() -> {
            try {
                answer.set(fixture.player.chooseReplacementEffect(
                        EFFECTS, new LinkedHashMap<>(), fixture.game));
            } catch (Throwable exc) {
                failure.set(exc);
            }
        });
        engine.setDaemon(true);
        engine.start();

        assertTrue(fixture.controller.awaitPendingOrTerminal(Duration.ofSeconds(30)),
                "the engine thread parked on a frame");
        JsonObject pending = fixture.controller.pendingDecision();
        assertEquals("replacement_effect", pending.get("decision_class").getAsString());
        JsonArray options = pending.getAsJsonArray("legal_options");
        assertEquals(2, options.size());
        String second = options.get(1).getAsJsonObject().get("option_id").getAsString();

        JsonObject response = new JsonObject();
        response.addProperty("decision_id", pending.get("decision_id").getAsString());
        response.addProperty("actor_id", pending.get("actor_id").getAsString());
        JsonArray selected = new JsonArray();
        selected.add(second);
        response.add("selected_option_ids", selected);
        response.add("ordering", new JsonArray());
        fixture.controller.submit(response);

        engine.join(30_000L);
        assertNull(failure.get(), "the callback returned normally");
        assertEquals(1, answer.get(), "the selected effect's index is handed back");
        assertNull(fixture.controller.terminalFailure());
    }

    private static Fixture liveFixture() {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        XmageFullGamePlayer player = new XmageFullGamePlayer(
                "departed-replacement", RangeOfInfluence.ALL, controller
        );
        CommanderFreeForAll game = new CommanderFreeForAll(
                MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL,
                MulliganType.LONDON.getMulligan(1),
                40,
                7
        );
        game.setRulesSeed(4242L);
        game.addPlayer(player, new Deck());
        return new Fixture(game, controller, player);
    }

    private record Fixture(
            Game game,
            XmageFullGameDecisionController controller,
            XmageFullGamePlayer player
    ) {
    }
}
