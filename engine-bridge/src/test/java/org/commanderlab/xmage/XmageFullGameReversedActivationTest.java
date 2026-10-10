package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.ActivatedAbility;
import mage.abilities.Ability;
import mage.cards.Card;
import mage.cards.decks.Deck;
import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
import mage.cards.repository.CardInfo;
import mage.cards.repository.CardRepository;
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.game.mulligan.MulliganType;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
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
 * target callback never runs; {@code makeChoice} returns
 * {@code isChosen(game)}, false for a required target, so {@code activate}
 * returns false and {@code PlayerImpl.playAbility} restores its bookmark
 * (PlayerImpl.java:1610/1620). That is the CR 601.2e / 727 rewind: the same
 * player is asked for priority again. The bridge previously fell through to
 * {@code fail("XMAGE_ACTION_EXECUTION_FAILED")} because
 * {@code emptyRequiredTarget} is only ever set from the bridge's target
 * callback.
 *
 * <p>Shelob, Dread Weaver is the real card from the issue: its
 * {@code {X}{1}{B}} ability re-targets to "creature card with mana value X
 * exiled with {this}" through a {@code TargetAdjuster}. With no eligible
 * exile for any X the filter is empty, so there is no legal choice at any
 * announced value.
 */
class XmageFullGameReversedActivationTest {

    private static final String SHELOB = "Shelob, Dread Weaver";

    /**
     * Red before the fix (XMAGE_ACTION_EXECUTION_FAILED), green after: the
     * engine reverses the activation, priority is re-asked for the SAME
     * player in the SAME window, the game continues, and the Lab never
     * passes priority on the player's behalf.
     */
    @Test
    void activationWithNoLegalXTargetIsReversedAndTheSamePlayerKeepsPriority() {
        Fixture fixture = liveFixture();
        Player player = fixture.player;
        Game game = fixture.game;
        Permanent shelob = putOnBattlefield(fixture, SHELOB);

        // Nothing is exiled with Shelob, so NO announced X has a legal target.
        assertTrue(
                game.getExile().getAllCards(game).isEmpty(),
                "precondition: no card is exiled with Shelob, so the X-dependent "
                        + "target has no legal choice for any announced value"
        );

        int turn = game.getTurnNum();
        String step = game.getStep() == null ? "" : game.getStep().getType().name();
        ActivatedAbility ability = shelobAbility(shelob, game);

        AtomicReference<Throwable> responderFailure = new AtomicReference<>();
        Thread responder = answerAnnounceX(fixture, 0, responderFailure);
        boolean activated;
        try {
            activated = player.activateAbility(ability, game);
        } finally {
            responder.interrupt();
            responder.join(30_000L);
        }
        if (responderFailure.get() != null) {
            throw new IllegalStateException("responder failed", responderFailure.get());
        }

        assertFalse(activated, "XMage reversed the activation: no legal X target");
        assertNull(
                fixture.controller.terminalFailure(),
                "the reversal must not fail the game closed"
        );

        // The Lab must not have passed priority for the player.
        assertFalse(
                player.isPassed(),
                "the lane must not pass priority for the player after a reversal"
        );
        assertEquals(turn, game.getTurnNum(), "the rewind returns to the same turn");
        assertEquals(step, game.getStep() == null ? "" : game.getStep().getType().name());

        // The game continues: the activation can be proposed again, and the
        // same reversal is still the engine's answer rather than a crash.
        responder = answerAnnounceX(fixture, 0, responderFailure);
        try {
            assertFalse(player.activateAbility(shelobAbility(shelob, game), game));
        } finally {
            responder.interrupt();
            responder.join(30_000L);
        }
        assertNull(fixture.controller.terminalFailure(), "the game keeps running");
        assertNotNull(game.getPermanent(shelob.getId()), "the source is untouched by the rewind");
    }

    /**
     * The fail-closed control: an activation the bridge cannot explain as an
     * engine reversal still fails closed. Here the ability never reaches the
     * X announcement (the engine refuses it outright), so none of the
     * reversed-action evidence exists.
     */
    @Test
    void unexplainedActivationFailureStillFailsClosed() {
        Fixture fixture = liveFixture();
        Player player = fixture.player;
        Game game = fixture.game;

        // An ability whose activation the engine refuses before any X is
        // announced and without asking the player for a target.
        ActivatedAbility unusable = new mage.abilities.common.SimpleActivatedAbility(
                new mage.abilities.effects.common.DoNothingEffect("issue703-control"),
                new mage.abilities.costs.mana.ManaCostsImpl<>("{X}{B}")
        );
        unusable.setControllerId(player.getId());
        unusable.setSourceId(player.getId());

        assertFalse(
                unusable.canActivate(player.getId(), game).canActivate(),
                "precondition: the engine itself refuses this activation"
        );

        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> player.priorityAfterUnexplainedFailure(unusable, game)
        );
        assertTrue(
                failure.getMessage().contains("XMAGE_ACTION_EXECUTION_FAILED"),
                "an unexplained activation failure must fail closed, got: " + failure.getMessage()
        );
        assertNotNull(fixture.controller.terminalFailure());
    }

    private static void assertNull(Object value) {
        org.junit.jupiter.api.Assertions.assertNull(value);
    }

    // ---- helpers ------------------------------------------------------------

    /** Answer the {@code announce_x} frame with {@code x}, then stop. */
    private static Thread answerAnnounceX(
            Fixture fixture,
            int x,
            AtomicReference<Throwable> failure
    ) {
        Thread responder = new Thread(() -> {
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
                    response.add("numeric_choices", numeric(x));
                    fixture.controller.submit(response);
                    return;
                }
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            } catch (Throwable exc) {
                failure.compareAndSet(null, exc);
            }
        });
        responder.setDaemon(true);
        responder.start();
        return responder;
    }

    private static JsonArray numeric(int value) {
        JsonArray array = new JsonArray();
        array.add(value);
        return array;
    }

    /** The {X}{1}{B} ability of the battlefield permanent. */
    private static ActivatedAbility shelobAbility(Permanent shelob, Game game) {
        for (Ability ability : shelob.getAbilities(game)) {
            if (ability instanceof ActivatedAbility && ability.getCosts().getText().contains("X")) {
                return (ActivatedAbility) ability;
            }
        }
        throw new AssertionError("Shelob exposes no X-cost activated ability");
    }

    private static Permanent putOnBattlefield(Fixture fixture, String cardName) {
        CardInfo info = CardRepository.instance.findCard(cardName);
        assertNotNull(info, "card must exist in the pinned XMage corpus: " + cardName);
        Card card = info.getCard();
        card.setOwnerId(fixture.player.getId());
        fixture.game.getState().addCard(card, fixture.player.getId());
        fixture.game.getState().setZone(card.getId(), mage.constants.Zone.BATTLEFIELD);
        Permanent permanent = fixture.game.getState().createPermanent(card, fixture.game);
        fixture.game.getBattlefield().addPermanent(permanent);
        fixture.game.applyEffects();
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
        return new Fixture(game, controller, player);
    }

    private record Fixture(
            Game game,
            XmageFullGameDecisionController controller,
            XmageFullGamePlayer player
    ) {
    }
}