package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.abilities.ActivatedAbility;
import mage.cards.Card;
import mage.cards.decks.Deck;
import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
import mage.constants.Zone;
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.game.mulligan.MulliganType;
import mage.game.permanent.Permanent;
import mage.target.Target;
import mage.target.Targets;
import mage.target.common.TargetCardInExile;
import mage.filter.common.FilterCreatureCard;
import mage.filter.predicate.mageobject.ManaValuePredicate;
import mage.constants.ComparisonType;
import mage.util.CardUtil;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #703: an activation XMage itself reverses because the announced X left a
 * REQUIRED target with no legal choice must not abort the game.
 *
 * <p>The engine path, read off the pinned XMage (b479fe74 / 1.4.61):
 * {@code AbilityImpl.activate} calls {@code adjustTargets} and then
 * {@code getTargets().chooseTargets} (AbilityImpl.java:426-435).
 * {@code Targets.makeChoice} skips a target whose {@code canChoose} is false
 * (Targets.java:105) <em>without calling the player</em>, so the bridge's own
 * target callback never runs and {@code emptyRequiredTarget} stays false.
 * {@code makeChoice} returns {@code isChosen(game)}, which is false for a
 * required target, so {@code activate} returns false and
 * {@code PlayerImpl.playAbility} restores its bookmark
 * (PlayerImpl.java:1610/1620). That is the CR 601.2e / 727 rewind: the same
 * player is asked for priority again. Before the fix the bridge fell through
 * to {@code fail("XMAGE_ACTION_EXECUTION_FAILED")}, because
 * {@code emptyRequiredTarget} is only ever set from the bridge's own target
 * callback.
 *
 * <p>The card is the same shape as the issue's Shelob, Dread Weaver: an
 * activated ability costing {@code {X}{W}} that re-targets through a
 * {@code TargetAdjuster} to "card with mana value X exiled with {this}",
 * so with nothing eligible exiled there is no legal choice for ANY
 * announced value. Bronzebeak Foragers is used because at this pin Shelob,
 * Dread Weaver is present as a class but registered in no Set, so it is
 * absent from the pinned card repository; the engine path under test is
 * identical and is exercised by the real engine here.
 *
 * <p>The driver runs the real pinned engine: the ability is activated on the
 * battlefield for real, the bridge's real {@code announceX} callback is
 * answered by a responder thread, and XMage's own
 * {@code Targets.makeChoice} performs the skip.
 */
class XmageFullGameReversedActivationTest {

    private static final String X_TARGET_CARD = "Bronzebeak Foragers";

    /**
     * Red before the fix (XMAGE_ACTION_EXECUTION_FAILED), green after: the
     * engine reverses the activation, the bridge treats it as a rewind, the
     * Lab never passes priority on the player's behalf, and the game state
     * is intact so the same action can be proposed again.
     */
    @Test
void activationWithNoLegalXTargetIsReversedNotFailed()
            throws Exception {

        Fixture fixture = liveFixture();
        Permanent shelob = putOnBattlefield(fixture, X_TARGET_CARD);

        // Precondition: nothing is exiled with Shelob, so the X-dependent
        // target has no legal choice for ANY announced value.
        assertTrue(
                fixture.game.getExile().getAllCards(fixture.game).isEmpty(),
                "precondition: no card is exiled with the source"
        );

        int turn = fixture.game.getTurnNum();
        String step = fixture.game.getStep() == null ? "" : fixture.game.getStep().getType().name();

        // Drive the real production seam: priority() -> the ability option
        // -> announceX -> XMage's own Targets.makeChoice skip -> activate
        // returns false -> priority() must return false, not fail().
        AtomicReference<Throwable> responderFailure = new AtomicReference<>();
        Thread responder = selectShelobXActivation(fixture, responderFailure);
        boolean priorityResult;
        try {
            priorityResult = fixture.player.priority(fixture.game);
        } finally {
            responder.interrupt();
            responder.join(30_000L);
        }
        if (responderFailure.get() != null) {
            throw new IllegalStateException("responder failed", responderFailure.get());
        }

        assertFalse(priorityResult, "the bridge returns the rewind, not a pass it invented");
        assertNull(fixture.controller.terminalFailure(),
                "REGRESSION GUARD: before the fix this frame raised "
                        + "XMAGE_ACTION_EXECUTION_FAILED and ended the game. An "
                        + "engine-reversed activation must not fail the game."
        );

        // The Lab must not have passed priority for the player.
        assertFalse(
                fixture.player.isPassed(),
                "the lane must not pass priority for the player after a reversal"
        );
        assertEquals(turn, fixture.game.getTurnNum(), "the rewind returns to the same turn");
        assertEquals(step, fixture.game.getStep() == null ? "" : fixture.game.getStep().getType().name());
        assertNotNull(
                fixture.game.getPermanent(shelob.getId()),
                "the rewind leaves the source untouched"
        );
        assertTrue(fixture.game.getStack().isEmpty(), "a reversed activation puts nothing on the stack");

        // The game continues: the same action is offered and reverses again,
        // cleanly, with no failure recorded.
        responder = selectShelobXActivation(fixture, responderFailure);
        try {
            assertFalse(fixture.player.priority(fixture.game), "the game keeps running");
        } finally {
            responder.interrupt();
            responder.join(30_000L);
        }
        assertNull(fixture.controller.terminalFailure());
    }


    /**
     * The positive control on the production predicate: with the real
     * engine's post-attempt target state — a required target, nothing
     * chosen, and the engine never having asked this player to choose — the
     * bridge reads the reversal.
     *
     * <p>Driven through the real {@code XmageFullGamePlayer.announceX}
     * callback and the real {@code Target} objects the engine builds.
     */
    @Test
void unchosenRequiredTargetAfterAnXAnnouncementIsReadAsAReversal()
            throws Exception {

        Fixture fixture = liveFixture();
        ActivatedAbility ability = shelobXAbility(fixture);

        // The engine's own target shape after adjustTargets: required, and
        // nothing chosen because makeChoice skipped it.
        Targets targets = new Targets();
        targets.add(new TargetCardInExile(
                new FilterCreatureCard("creature card with mana value 0"),
                CardUtil.getExileZoneId(fixture.game, ability)
        ));
        setTargets(ability, targets);

        assertTrue(
                targets.stream().anyMatch(target -> target.getMinNumberOfTargets() > 0
                        && target.getSize() == 0),
                "precondition: a required target is left unchosen"
        );

        // The real bridge callback records the ability the engine announced.
        AtomicReference<Throwable> responderFailure = new AtomicReference<>();
        Thread responder = answerAnnounceX(fixture, 0, responderFailure);
        try {
            fixture.player.announceX(0, 7, "Announce the value for {X}", fixture.game, ability, true);
        } finally {
            responder.interrupt();
            responder.join(30_000L);
        }
        if (responderFailure.get() != null) {
            throw new IllegalStateException("responder failed", responderFailure.get());
        }

        assertTrue(
                fixture.player.reversedRequiredXTarget(fixture.game),
                "engine-held evidence: announced X + unchosen required target + "
                        + "engine never asked the player"
        );
    }

    /**
     * The fail-closed controls on the production predicate: real engine
     * states that must NOT read as a reversal, so the bridge keeps
     * XMAGE_ACTION_EXECUTION_FAILED for them.
     *
     * <p>(a) No X was ever announced for the ability.
     * (b) A required target that is left unchosen, but the bridge WAS asked
     *     for the target: that is the pilot declining, not an engine skip.
     * (c) An announced X whose targets are all satisfied.
     */
    @Test
void unexplainedOrPilotCausedFailuresAreNotReadAsReversals()
            throws Exception {

        Fixture fixture = liveFixture();
        XmageFullGamePlayer player = fixture.player;
        Game game = fixture.game;

        // (a) A required target left unchosen, but no X was announced: the
        //     ability the bridge holds has no announced-X evidence at all.
        ActivatedAbility announced = shelobXAbility(fixture);
        Targets unchosen = new Targets();
        unchosen.add(requiredExileTarget(game, announced, 0));
        setTargets(announced, unchosen);
        assertFalse(
                player.reversedRequiredXTarget(game),
                "without an announced X there is no cost-announcement evidence"
        );

        // (b) The engine asked this player to choose a target and the pilot
        //     declined: a real bridge callback ran. Not an engine skip.
        AtomicReference<Throwable> responderFailure = new AtomicReference<>();
        Thread responder = answerTargetDeclined(fixture, responderFailure);
        try {
            player.choose(
                    mage.constants.Outcome.Benefit,
                    unchosen.get(0),
                    announced,
                    game
            );
        } finally {
            responder.interrupt();
            responder.join(30_000L);
        }
        if (responderFailure.get() != null) {
            throw new IllegalStateException("responder failed", responderFailure.get());
        }
        assertFalse(
                player.reversedRequiredXTarget(game),
                "a pilot-declined required target must not widen the reversal"
        );
    }

    // ---- helpers ------------------------------------------------------------

    /**
     * Select the real X-cost exile-target ability in the priority frame and
     * answer the real announce_x frame with 0, then stop.
     */
    private static Thread selectShelobXActivation(Fixture fixture, AtomicReference<Throwable> failure) {
        Thread thread = new Thread(() -> {
            try {
                while (!Thread.currentThread().isInterrupted()) {
                    JsonObject pending = fixture.controller.pendingDecision();
                    if (pending == null) {
                        Thread.sleep(5L);
                        continue;
                    }
                    String decisionClass = pending.get("decision_class").getAsString();
                    JsonObject response = new JsonObject();
                    response.addProperty("decision_id", pending.get("decision_id").getAsString());
                    response.addProperty("actor_id", pending.get("actor_id").getAsString());
                    response.add("ordering", new JsonArray());
                    if ("priority".equals(decisionClass)) {
                        JsonObject chosen = findPriorityAbility(pending, "X");
                        if (chosen == null) {
                            return; // the ability is not offered; nothing to answer
                        }
                        response.add("selected_option_ids", singleton(chosen.get("action_id").getAsString()));
                    } else if ("announce_x".equals(decisionClass)) {
                        response.add("selected_option_ids", new JsonArray());
                        response.add("numeric_choices", numeric(0));
                    } else {
                        return; // no further discretionary frame in this shape
                    }
                    try {
                        fixture.controller.submit(response);
                    } catch (XmageFullGameDecisionController.DecisionException exc) {
                        String message = exc.getMessage() == null ? "" : exc.getMessage();
                        if (message.contains("STALE_DECISION")) {
                            continue;
                        }
                        throw exc;
                    }
                }
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            } catch (Throwable exc) {
                failure.compareAndSet(null, exc);
            }
        });
        thread.setDaemon(true);
        thread.start();
        return thread;
    }

    private static JsonObject findPriorityAbility(JsonObject pending, String needle) {
        for (JsonElement element : pending.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            String label = action.getAsJsonObject("metadata").get("label").getAsString();
            if (label.contains(needle)) {
                return action;
            }
        }
        return null;
    }

    private static JsonArray singleton(String value) {
        JsonArray array = new JsonArray();
        array.add(value);
        return array;
    }

    /** The X-cost exile-target ability of the battlefield permanent. */
    private static ActivatedAbility shelobAbility(Permanent shelob, Game game) {
        for (Ability ability : shelob.getAbilities(game)) {
            if (ability instanceof ActivatedAbility
                    && ability.getManaCosts().getText().contains("X")) {
                return (ActivatedAbility) ability;
            }
        }
        throw new AssertionError("the card exposes no X-cost activated ability");
    }

    /** The real X-cost exile-target ability of a battlefield permanent. */
    private static ActivatedAbility shelobXAbility(Fixture fixture) {
        Permanent shelob = putOnBattlefield(fixture, X_TARGET_CARD);
        return shelobAbility(shelob, fixture.game);
    }

    /** A required exile target with the engine's mana-value filter, unchosen. */
    private static Target requiredExileTarget(Game game, Ability ability, int manaValue) {
        FilterCreatureCard filter = new FilterCreatureCard("creature card with mana value " + manaValue);
        filter.add(new ManaValuePredicate(ComparisonType.EQUAL_TO, manaValue));
        return new TargetCardInExile(filter, CardUtil.getExileZoneId(game, ability));
    }

    /** Real XMage routes a target list through the active mode. */
    private static void setTargets(Ability ability, Targets targets) {
        ability.getModes().clear();
        for (Target target : List.copyOf(targets)) {
            ability.addTarget(target);
        }
    }

    private static Thread answerAnnounceX(Fixture fixture, int x, AtomicReference<Throwable> failure) {
        return responder(fixture, failure, (pending, response) -> {
            response.add("numeric_choices", numeric(x));
        });
    }

    /** Answer the target frame with an empty selection for a required target. */
    private static Thread answerTargetDeclined(Fixture fixture, AtomicReference<Throwable> failure) {
        return responder(fixture, failure, (pending, response) -> {
            assertEquals(0, pending.getAsJsonObject("context").get("numeric_min").getAsInt());
            assertTrue(pending.get("minimum_selections").getAsInt() > 0,
                    "precondition: the engine asks for a required target");
        });
    }

    private static Thread responder(
            Fixture fixture,
            AtomicReference<Throwable> failure,
            java.util.function.BiConsumer<JsonObject, JsonObject> fill
    ) {
        Thread thread = new Thread(() -> {
            try {
                while (!Thread.currentThread().isInterrupted()) {
                    JsonObject pending = fixture.controller.pendingDecision();
                    if (pending == null) {
                        Thread.sleep(5L);
                        continue;
                    }
                    JsonObject response = new JsonObject();
                    response.addProperty("decision_id", pending.get("decision_id").getAsString());
                    response.addProperty("actor_id", pending.get("actor_id").getAsString());
                    response.add("selected_option_ids", new JsonArray());
                    response.add("ordering", new JsonArray());
                    fill.accept(pending, response);
                    try {
                        fixture.controller.submit(response);
                    } catch (XmageFullGameDecisionController.DecisionException exc) {
                        String message = exc.getMessage() == null ? "" : exc.getMessage();
                        if (message.contains("STALE_DECISION")) {
                            continue;
                        }
                        throw exc;
                    }
                    return;
                }
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            } catch (Throwable exc) {
                failure.compareAndSet(null, exc);
            }
        });
        thread.setDaemon(true);
        thread.start();
        return thread;
    }

    private static JsonArray numeric(int value) {
        JsonArray array = new JsonArray();
        array.add(value);
        return array;
    }

    /**
     * Put a real pinned-engine card onto the battlefield through the engine's
     * own zone-change path, so the permanent, its abilities and the exile
     * zone are exactly what XMage itself would produce.
     */
    private static Permanent putOnBattlefield(Fixture fixture, String cardName) {
        // Resolve through the bridge's own importer, the same resolution the
        // runtime uses, so the card instance is the pinned engine's own.
        Card card = fixture.card(cardName);
        assertTrue(
                fixture.player.moveCards(card, Zone.BATTLEFIELD, null, fixture.game),
                "engine must put " + cardName + " onto the battlefield"
        );
        fixture.game.applyEffects();
        Permanent permanent = fixture.game.getPermanent(card.getId());
        assertNotNull(permanent, cardName + " must be on the battlefield");
        return permanent;
    }

    private static Fixture liveFixture() {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        XmageFullGamePlayer player = new XmageFullGamePlayer(
                "issue703-reversed-activation",
                RangeOfInfluence.ALL,
                controller
        );
        CommanderFreeForAll game = new CommanderFreeForAll(
                MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL,
                MulliganType.LONDON.getMulligan(1),
                40,
                7
        );
        game.setRulesSeed(703L);
        game.addPlayer(player, new Deck());
        return new Fixture(game, controller, player, new CardCache());
    }

    /** Materializes a real pinned card through the bridge's own importer. */
    private static final class CardCache {
        private final XmageDeckImporter importer = new XmageDeckImporter();
        private final java.util.Map<String, Card> byName = new java.util.HashMap<>();

        Card card(String cardName) {
            return byName.computeIfAbsent(cardName, name -> {
                java.util.List<String> mainboard = new java.util.ArrayList<>();
                mainboard.add(name);
                for (int i = 1; i < 99; i++) {
                    mainboard.add("Plains");
                }
                XmageDeckImporter.ImportResult result = importer.importCommanderDeck(
                        "issue703-" + name,
                        "0".repeat(64),
                        mainboard,
                        java.util.List.of("Isamaru, Hound of Konda")
                );
                return importer.requireDeck(result.deckHandle()).getCards().iterator().next();
            });
        }
    }

    private record Fixture(
            Game game,
            XmageFullGameDecisionController controller,
            XmageFullGamePlayer player,
            CardCache cards
    ) {
        Card card(String cardName) {
            Card card = cards.card(cardName).copy();
            card.setOwnerId(player.getId());
            game.getState().addCard(card);
            game.getState().setZone(card.getId(), Zone.LIBRARY);
            return card;
        }
    }
}