package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.decks.Deck;
import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.game.mulligan.MulliganType;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #1299 (SIMULATE E4): contract tests for bridge-side forced-decision answering
 * behind {@code commanderlab.fullGame.skipForcedDecisions}.
 */
class XmageFullGameForcedDecisionSkipTest {

    @AfterEach
    void clearProperty() {
        System.clearProperty(XmageFullGameDecisionController.SKIP_FORCED_DECISIONS_PROPERTY);
    }

    @Test
    void defaultOffPublishesForcedDecisionAndRequiresExternalAnswer() throws Exception {
        Fixture fixture = liveFixture();
        JsonArray offered = singlePassOption();
        AtomicReference<XmageFullGameDecisionController.DecisionResponse> out = new AtomicReference<>();

        Thread engine = new Thread(() -> out.set(fixture.controller.request(
                fixture.game,
                fixture.player,
                "priority",
                "Choose priority action",
                1,
                1,
                offered,
                new JsonObject(),
                null
        )));
        engine.start();

        JsonObject pending = awaitPending(fixture.controller);
        assertNotNull(pending, "default-off must publish the forced frame externally");
        assertEquals(0L, fixture.controller.forcedDecisionsSkipped());

        submitOption(fixture.controller, pending, "opt-pass");
        engine.join(5_000L);
        assertNotNull(out.get());
        assertEquals(List.of("opt-pass"), out.get().selectedOptionIds());
        assertEquals(1L, fixture.controller.decisionCount());
    }

    @Test
    void flagOnAnswersForcedSingleOptionImmediatelyWithIdenticalSemanticTranscriptAndReplay() throws Exception {
        Fixture offFixture = liveFixture();
        JsonArray offered = singlePassOption();
        Thread offThread = new Thread(() -> offFixture.controller.request(
                offFixture.game,
                offFixture.player,
                "priority",
                "Choose priority action",
                1,
                1,
                offered,
                new JsonObject(),
                null
        ));
        offThread.start();
        JsonObject pending = awaitPending(offFixture.controller);
        submitOption(offFixture.controller, pending, "opt-pass");
        offThread.join(5_000L);

        System.setProperty(XmageFullGameDecisionController.SKIP_FORCED_DECISIONS_PROPERTY, "true");
        Fixture onFixture = liveFixture();
        XmageFullGameDecisionController.DecisionResponse onResponse = onFixture.controller.request(
                onFixture.game,
                onFixture.player,
                "priority",
                "Choose priority action",
                1,
                1,
                offered,
                new JsonObject(),
                null
        );

        assertNull(onFixture.controller.pendingDecision(), "forced frame must not park as pending");
        assertEquals(1L, onFixture.controller.forcedDecisionsSkipped());
        assertEquals(1L, onFixture.controller.decisionCount());
        assertEquals(List.of("opt-pass"), onResponse.selectedOptionIds());

        JsonArray offTranscript = offFixture.controller.transcript();
        JsonArray onTranscript = onFixture.controller.transcript();
        assertEquals(offTranscript.size(), onTranscript.size());
        for (int index = 0; index < offTranscript.size(); index++) {
            JsonObject offEvent = offTranscript.get(index).getAsJsonObject();
            JsonObject onEvent = onTranscript.get(index).getAsJsonObject();
            for (String key : List.of(
                    "sequence", "kind", "decision_class", "actor_seat", "prompt",
                    "legal_option_types", "legal_option_labels",
                    "selected_option_types", "selected_option_labels", "numeric_choice"
            )) {
                assertEquals(offEvent.get(key), onEvent.get(key), "mismatch at event " + index + " key " + key);
            }
        }
        assertEquals(offFixture.controller.replayRecord(), onFixture.controller.replayRecord());
    }

    @Test
    void flagOnNeverSkipsDiscretionaryDecisions() throws Exception {
        System.setProperty(XmageFullGameDecisionController.SKIP_FORCED_DECISIONS_PROPERTY, "true");
        Fixture fixture = liveFixture();

        // Case 1: two legal options (1..1) -> discretionary
        JsonArray twoOffered = new JsonArray();
        twoOffered.add(XmageFullGameDecisionController.option("opt-pass", "Pass priority", "pass_priority", new JsonObject()));
        twoOffered.add(XmageFullGameDecisionController.option("opt-cast", "Cast spell", "activated_ability", new JsonObject()));
        Thread t1 = new Thread(() -> fixture.controller.request(
                fixture.game, fixture.player, "priority", "Choose priority action",
                1, 1, twoOffered, new JsonObject(), null
        ));
        t1.start();
        JsonObject pending1 = awaitPending(fixture.controller);
        assertEquals("priority", pending1.get("decision_class").getAsString());
        submitOption(fixture.controller, pending1, "opt-pass");
        t1.join(5_000L);

        // Case 2: optional selection (0..1) with one legal option -> discretionary
        JsonArray oneTarget = new JsonArray();
        oneTarget.add(XmageFullGameDecisionController.option("opt-t1", "Target 1", "target", new JsonObject()));
        Thread t2 = new Thread(() -> fixture.controller.request(
                fixture.game, fixture.player, "target", "Select up to 1 target",
                0, 1, oneTarget, new JsonObject(), null
        ));
        t2.start();
        JsonObject pending2 = awaitPending(fixture.controller);
        assertEquals("target", pending2.get("decision_class").getAsString());
        submitOption(fixture.controller, pending2, "opt-t1");
        t2.join(5_000L);

        // Case 3: single option (1..1) but discretionary numeric range (1..3) -> discretionary
        JsonObject rangeCtx = new JsonObject();
        rangeCtx.addProperty("numeric_min", 1);
        rangeCtx.addProperty("numeric_max", 3);
        Thread t3 = new Thread(() -> fixture.controller.request(
                fixture.game, fixture.player, "target_amount", "Assign damage",
                1, 1, oneTarget, rangeCtx, null
        ));
        t3.start();
        JsonObject pending3 = awaitPending(fixture.controller);
        assertEquals("target_amount", pending3.get("decision_class").getAsString());
        submitOptionWithNumeric(fixture.controller, pending3, "opt-t1", 2);
        t3.join(5_000L);

        // Case 4: non-priority single option (1..1, e.g. target) must still reach Python (Condition 3)
        Thread t4 = new Thread(() -> fixture.controller.request(
                fixture.game, fixture.player, "target", "Select a creature you control",
                1, 1, oneTarget, new JsonObject(), null
        ));
        t4.start();
        JsonObject pending4 = awaitPending(fixture.controller);
        assertEquals("target", pending4.get("decision_class").getAsString());
        submitOption(fixture.controller, pending4, "opt-t1");
        t4.join(5_000L);

        assertEquals(0L, fixture.controller.forcedDecisionsSkipped());
        assertEquals(4L, fixture.controller.decisionCount());
    }

    @Test
    void humanSeatNeverSkipsForcedDecisionEvenWhenFlagOn() throws Exception {
        System.setProperty(XmageFullGameDecisionController.SKIP_FORCED_DECISIONS_PROPERTY, "true");
        Fixture fixture = liveFixture();
        fixture.controller.setHumanSeat(0, true);
        assertTrue(fixture.controller.isHumanSeat(0));

        JsonArray offered = singlePassOption();
        Thread engine = new Thread(() -> fixture.controller.request(
                fixture.game,
                fixture.player,
                "priority",
                "Choose priority action",
                1,
                1,
                offered,
                new JsonObject(),
                null
        ));
        engine.start();

        JsonObject pending = awaitPending(fixture.controller);
        assertNotNull(pending, "human seat must still receive forced frames externally");
        assertEquals(0L, fixture.controller.forcedDecisionsSkipped());
        submitOption(fixture.controller, pending, "opt-pass");
        engine.join(5_000L);
        assertEquals(1L, fixture.controller.decisionCount());
    }

    private static JsonArray singlePassOption() {
        JsonArray offered = new JsonArray();
        offered.add(XmageFullGameDecisionController.option(
                "opt-pass", "Pass priority", "pass_priority", new JsonObject()
        ));
        return offered;
    }

    private static void submitOption(
            XmageFullGameDecisionController controller,
            JsonObject pending,
            String optionId
    ) {
        submitOptionWithNumeric(controller, pending, optionId, null);
    }

    private static void submitOptionWithNumeric(
            XmageFullGameDecisionController controller,
            JsonObject pending,
            String optionId,
            Integer numeric
    ) {
        JsonObject submitted = new JsonObject();
        submitted.addProperty("decision_id", pending.get("decision_id").getAsString());
        submitted.addProperty("actor_id", pending.get("actor_id").getAsString());
        JsonArray selected = new JsonArray();
        selected.add(optionId);
        submitted.add("selected_option_ids", selected);
        submitted.add("ordering", new JsonArray());
        if (numeric != null) {
            submitted.addProperty("numeric_choice", numeric);
        }
        controller.submit(submitted);
    }

    private static JsonObject awaitPending(XmageFullGameDecisionController controller)
            throws InterruptedException {
        for (int attempt = 0; attempt < 1_000; attempt++) {
            JsonObject pending = controller.pendingDecision();
            if (pending != null) {
                return pending;
            }
            Thread.sleep(5L);
        }
        throw new IllegalStateException("no pending decision parked");
    }

    private static Fixture liveFixture() {
        XmageFullGameDecisionController controller =
                new XmageFullGameDecisionController(Duration.ofSeconds(10));
        XmageFullGamePlayer player = new XmageFullGamePlayer(
                "e4-forced-skip", RangeOfInfluence.ALL, controller
        );
        CommanderFreeForAll game = new CommanderFreeForAll(
                MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL,
                MulliganType.LONDON.getMulligan(1),
                40,
                7
        );
        game.setRulesSeed(1299L);
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
