package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #756: while paying the mana part of an ability that also costs {T} of its
 * source, the payment frame must not offer that source's own tap-for-mana
 * ability. The pinned engine pays the mana cost first, so tapping the source
 * for mana leaves the {T} cost unpayable and the activation fails.
 *
 * <p>Grim Backwoods (Oracle): "{T}: Add {C}. {2}{B}{G}, {T}, Sacrifice a
 * creature: Draw a card."
 */
class XmageFullGameTapSourceSelfFundingTest {

    private static final String BACKWOODS = "Grim Backwoods";
    private static final String BEARS = "Grizzly Bears";

    /** Red before the fix: the land's own {T}: Add {C} was offered and aborted the game. */
    @Test
    void tapAbilityPaymentDoesNotOfferItsOwnSourceForMana() {
        XmageMultiplayerScenario s = scenario("issue756-own-source", false);
        Game game = s.session.restorationGame();

        s.submit(labelled(s, BACKWOODS + " — {2}{B}{G}"));
        assertEquals("mana_payment", s.decisionClass(), s.labels().toString());
        assertTrue(s.labels().stream().noneMatch(label -> label.startsWith(BACKWOODS)),
                "REGRESSION GUARD: tapping " + BACKWOODS + " for mana would leave its own {T} "
                        + "cost unpayable: " + s.labels());

        for (int i = 0; i < 12 && "mana_payment".equals(s.decisionClass()); i++) {
            String next = s.labels().stream()
                    .filter(label -> label.startsWith("Spend ") || label.startsWith("Forest")
                            || label.startsWith("Swamp"))
                    .findFirst().orElseThrow(() -> new AssertionError(s.labels().toString()));
            s.submit(labelled(s, next));
        }
        if (!"priority".equals(s.decisionClass())) {
            s.submit(labelled(s, BEARS)); // the sacrifice cost
        }
        assertTrue(s.session.pendingDecisionPayload().get("failure").isJsonNull(),
                "the activation completes: " + s.session.pendingDecisionPayload().get("failure"));
        assertFalse(game.getStack().isEmpty(), "the draw ability is on the stack");
        mage.game.permanent.Permanent backwoods = game.getBattlefield().getAllActivePermanents().stream()
                .filter(permanent -> BACKWOODS.equals(permanent.getName())).findFirst().orElseThrow();
        assertEquals(backwoods.getId(), game.getStack().getFirst().getSourceId(),
                "the stacked ability is Grim Backwoods' own");
        assertTrue(backwoods.isTapped(), "its {T} cost was paid by the activation itself");
        assertTrue(game.getPlayer(backwoods.getControllerId()).getGraveyard().getCards(game).stream()
                .anyMatch(card -> BEARS.equals(card.getName())), "the sacrifice cost was paid");
    }

    /** The predicate on real engine abilities: only an owed {T}/{Q} of the same source hides an option. */
    @Test
    void onlyAnOwedTapOfTheSameSourceHidesItsManaAbility() {
        java.util.UUID source = java.util.UUID.randomUUID();
        mage.abilities.Ability tapMana = withSource(new mage.abilities.mana.ColorlessManaAbility(), source);
        assertTrue(XmageFullGamePlayer.needsSourceTapStillOwed(tapMana, tapAbility(source)));

        mage.abilities.Ability paidTap = tapAbility(source);
        paidTap.getCosts().forEach(mage.abilities.costs.Cost::setPaid);
        assertFalse(XmageFullGamePlayer.needsSourceTapStillOwed(tapMana, paidTap), "{T} already paid");

        mage.abilities.Ability freeMana = withSource(new mage.abilities.mana.SimpleManaAbility(
                Zone.BATTLEFIELD, mage.Mana.ColorlessMana(1), new mage.abilities.costs.mana.GenericManaCost(1)), source);
        assertFalse(XmageFullGamePlayer.needsSourceTapStillOwed(freeMana, tapAbility(source)),
                "a mana ability without {T} stays usable");

        assertFalse(XmageFullGamePlayer.needsSourceTapStillOwed(
                withSource(new mage.abilities.mana.ColorlessManaAbility(), java.util.UUID.randomUUID()),
                tapAbility(source)), "another permanent's mana ability stays usable");

        mage.abilities.Ability untapMana = withSource(new mage.abilities.mana.SimpleManaAbility(
                Zone.BATTLEFIELD, mage.Mana.ColorlessMana(1), new mage.abilities.costs.common.UntapSourceCost()), source);
        mage.abilities.Ability untapAbility = withSource(new mage.abilities.common.SimpleActivatedAbility(
                new mage.abilities.effects.common.DrawCardSourceControllerEffect(1),
                new mage.abilities.costs.common.UntapSourceCost()), source);
        assertTrue(XmageFullGamePlayer.needsSourceTapStillOwed(untapMana, untapAbility), "{Q} owed on both");
        assertFalse(XmageFullGamePlayer.needsSourceTapStillOwed(tapMana, untapAbility), "{T} vs {Q}");
    }

    private static mage.abilities.Ability tapAbility(java.util.UUID source) {
        mage.abilities.Ability ability = new mage.abilities.common.SimpleActivatedAbility(
                new mage.abilities.effects.common.DrawCardSourceControllerEffect(1),
                new mage.abilities.costs.mana.ManaCostsImpl<>("{2}{B}{G}"));
        ability.addCost(new mage.abilities.costs.common.TapSourceCost());
        return withSource(ability, source);
    }

    private static mage.abilities.Ability withSource(mage.abilities.Ability ability, java.util.UUID source) {
        ability.setSourceId(source);
        return ability;
    }

    /** Control: paying anything else still offers the land's mana ability. */
    @Test
    void otherPaymentsStillOfferTheLandsManaAbility() {
        XmageMultiplayerScenario s = scenario("issue756-other-payment", true);
        s.submit(XmageExternalRiskSignalTest.spellOffer(s.session.legalActionsPayload(), BEARS));
        assertEquals("mana_payment", s.decisionClass(), s.labels().toString());
        assertTrue(s.labels().stream().anyMatch(label -> label.startsWith(BACKWOODS + " — {T}: Add {C}")),
                "a spell's payment may use " + BACKWOODS + ": " + s.labels());
    }

    private static XmageMultiplayerScenario scenario(String tag, boolean bearsInHand) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", BACKWOODS, 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", BEARS, 1, Zone.BATTLEFIELD));
        for (int i = 0; i < 2; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 10 + i, Zone.BATTLEFIELD));
            objects.add(XmageMultiplayerScenario.obj("P1", "Swamp", 20 + i, Zone.BATTLEFIELD));
        }
        if (bearsInHand) {
            objects.add(XmageMultiplayerScenario.obj("P1", BEARS, 30, Zone.HAND));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(tag, 2, "P1", objects);
        assertEquals("P1", s.actor());
        return s;
    }

    private static JsonObject labelled(XmageMultiplayerScenario s, String prefix) {
        for (JsonElement element : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject candidate = element.getAsJsonObject();
            if (candidate.getAsJsonObject("metadata").get("label").getAsString().startsWith(prefix)) {
                return candidate;
            }
        }
        assertNotNull(null, "no option labelled " + prefix + "*: " + s.labels());
        return null;
    }
}
