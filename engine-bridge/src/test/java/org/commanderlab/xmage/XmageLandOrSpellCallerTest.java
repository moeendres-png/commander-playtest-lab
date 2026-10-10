package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.abilities.common.SagaAbility;
import mage.counters.CounterType;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.commanderlab.xmage.DecisionClassMatrixHarness.Placed;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.Scenario;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.actions;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.proposal;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * #690: the land-or-spell callback's two engine callers at the pin.
 *
 * <p>{@link XmageFullGamePlayer#chooseLandOrSpellAbility} follows exactly one
 * declared engine caller ({@code CardUtil#castSpellWithAttributesForFree},
 * proven by the {@code land_or_spell} matrix row). The other caller at the pin is
 * {@code Vault112SadisticSimulationChapterEffect.apply} (Vault 112: Sadistic
 * Simulation, chapter III), whose legality this lane never declared. This test
 * drives that second caller on the real engine, from the real card's own chapter
 * III effect on a real restored game, and observes the fail-closed contract:</p>
 * <ul>
 *   <li>the typed failure {@code UNSUPPORTED_DECISION_CLASS};</li>
 *   <li>no decision frame and no option published for the land-or-spell
 *       choice;</li>
 *   <li>no ability chosen for the player: the exiled card is neither cast nor
 *       played.</li>
 * </ul>
 *
 * <p>The chapter is restored at chapter III (CR 714.2) by placing two lore
 * counters — chapters I and II resolved off-line — and letting the engine's own
 * lore-counter addition raise chapter III, rather than driving chapters I-II.
 * Nothing here fabricates a decision, an option or an outcome: the engine
 * supplies every choice it asks, and the test only answers the two the chapter
 * needs ({@code amount} for the {E} payment, then the exile selection).</p>
 */
class XmageLandOrSpellCallerTest {

    private static final String SAGA = "Vault 112: Sadistic Simulation";

    /** The exact fail-closed reason the production player codes for this caller. */
    private static final String FAILURE =
            "UNSUPPORTED_DECISION_CLASS: land-or-spell choice from an undeclared engine caller";

    /** The prompt the supported caller would publish; it must never appear here. */
    private static final String LAND_OR_SPELL_PROMPT = "Choose land or spell ability for ";

    @BeforeEach
    void orchestrationLaunch() {
        XmageRulesRngResultTape.keyForTests(new byte[32]);
    }

    @AfterEach
    void principalLaunch() {
        XmageRulesRngResultTape.keyForTests(null);
    }

    @Test
    void vault112ChapterThreeFailsClosedOnTheRealEngine() {
        DecisionClassMatrixHarness.Live live = openAtChapterThree();
        Game game = live.session().restorationGame();
        Player controller = live.seats().get("P1");

        int permanentsBefore = game.getBattlefield().getAllActivePermanents(controller.getId()).size();
        int libraryBefore = controller.getLibrary().size();
        int handAndGraveyardBefore = controller.getHand().size() + controller.getGraveyard().size();
        int energyBefore = controller.getCountersCount(CounterType.ENERGY);
        assertTrue(libraryBefore > 0, "the controller has a library to exile from");

        List<String> trace = new ArrayList<>();
        int selectionFrames = 0;
        for (int guard = 0; guard < 60 && live.session().parkedDecisionClass() != null; guard++) {
            JsonObject frame = live.session().legalActionsPayload();
            String decisionClass = frame.get("decision_class").getAsString();
            trace.add(decisionClass + ":" + frame.getAsJsonObject("decision").get("prompt").getAsString());
            assertFalse(frame.getAsJsonObject("decision").get("prompt").getAsString()
                            .startsWith(LAND_OR_SPELL_PROMPT),
                    "the undeclared caller received a decision frame: " + trace);
            switch (decisionClass) {
                // Chapter III sits on the stack; P1 passes priority onto it.
                case "priority" -> live.session().submitAction(proposal(frame,
                        DecisionClassMatrixHarness.single(frame,
                                action -> "pass_priority".equals(DecisionClassMatrixHarness.optionType(action)),
                                "vault112 pass")));
                // "How many {E} do you like to pay?" — the chapter's own declared question.
                case "amount" -> {
                    JsonObject payOne = proposal(frame, actions(frame).get(0));
                    payOne.getAsJsonObject("choices").addProperty("numeric_choice", 1);
                    live.session().submitAction(payOne);
                }
                default -> {
                    selectionFrames++;
                    live.session().submitAction(proposal(frame, actions(frame).get(0)));
                }
            }
        }

        // The callback failed closed instead of publishing or choosing anything.
        assertNotNull(live.session().pendingDecisionPayload().getAsJsonObject("failure"),
                "the land-or-spell callback from Vault 112 must fail closed; trace " + trace);
        assertNull(live.session().parkedDecisionClass(),
                "no decision stays pending after the fail-closed callback");

        // The coded fail-closed reason is recorded verbatim by the controller.
        // The engine thread then unwinds through the refusal, so a later
        // XMAGE_FULL_GAME_FAILED may follow it; the coded reason is the first.
        List<String> failures = new ArrayList<>();
        List<String> published = new ArrayList<>();
        for (JsonElement element : live.session().controllerTranscript()) {
            JsonObject event = element.getAsJsonObject();
            if (event.has("event_type")
                    && "controller_failure".equals(event.get("event_type").getAsString())) {
                failures.add(event.getAsJsonObject("payload").get("message").getAsString());
            }
            if (!event.has("kind") || !"decision_requested".equals(event.get("kind").getAsString())) {
                continue;
            }
            // No decision frame and no option were published for this choice.
            published.add(event.get("prompt").getAsString());
            event.getAsJsonArray("legal_option_labels").forEach(
                    option -> published.add(option.getAsString()));
        }
        assertFalse(published.stream().anyMatch(text -> text.startsWith(LAND_OR_SPELL_PROMPT)),
                "a land-or-spell decision frame or option was published: " + published);
        assertEquals(FAILURE, failures.get(0),
                "the typed fail-closed reason the production player codes for this caller: " + failures);

        // No ability was chosen for the player: the chapter paid, exiled exactly
        // what it paid for, and left the card where it was.
        assertTrue(selectionFrames >= 1, "the chapter asked for a card to exile before the "
                + "land-or-spell choice; trace " + trace);
        assertEquals(energyBefore - 1, controller.getCountersCount(CounterType.ENERGY),
                "chapter III paid the {E} it was asked for, so the effect ran to the callback");
        assertEquals(permanentsBefore, game.getBattlefield().getAllActivePermanents(controller.getId()).size(),
                "no ability was chosen for the player: nothing was played as a land");
        assertEquals(0, controller.getHand().size() + controller.getGraveyard().size() - handAndGraveyardBefore,
                "no ability was chosen for the player: nothing was cast");
    }

    /**
     * A real restored 2P game with the real card on P1's battlefield, advanced to
     * chapter III by the engine's own lore-counter addition (CR 714.2).
     */
    private static DecisionClassMatrixHarness.Live openAtChapterThree() {
        DecisionClassMatrixHarness.Live live = DecisionClassMatrixHarness.open(new Scenario(
                "matrix-vault112-chapter-three", 69001L,
                List.of(Placed.battlefield("P1", SAGA)),
                List.of(),
                "priority", "P1"));
        Game game = live.session().restorationGame();
        Player controller = live.seats().get("P1");
        Permanent saga = game.getBattlefield().getAllActivePermanents(controller.getId()).stream()
                .filter(permanent -> SAGA.equals(permanent.getName()))
                .findFirst()
                .orElseThrow(() -> new AssertionError("the real card is not on P1's battlefield"));
        Ability chapterSource = saga.getAbilities(game).stream()
                .filter(ability -> ability instanceof SagaAbility)
                .findFirst()
                .orElseThrow(() -> new AssertionError("the real card has no Saga ability"));
        // Chapter III needs {E} to pay: the energy is the chapter's own resource.
        controller.addCounters(CounterType.ENERGY.createInstance(1), controller.getId(), chapterSource, game);
        // CR 714.2: two lore counters stand for chapters I and II already resolved.
        // The counter store is written directly so no earlier chapter is faked;
        // only the third counter is added through the engine's own event, and
        // that is what raises chapter III.
        saga.getCounters(game).removeCounter(CounterType.LORE,
                saga.getCounters(game).getCount(CounterType.LORE));
        saga.getCounters(game).addCounter(CounterType.LORE.createInstance(2));
        assertTrue(saga.addCounters(CounterType.LORE.createInstance(), chapterSource, game),
                "the engine accepted chapter III's lore counter");
        assertEquals(3, saga.getCounters(game).getCount(CounterType.LORE), "chapter III is live");
        return live;
    }
}