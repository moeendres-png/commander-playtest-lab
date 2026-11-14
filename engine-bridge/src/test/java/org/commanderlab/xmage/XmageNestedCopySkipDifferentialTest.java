package org.commanderlab.xmage;

import mage.MageObject;
import mage.Mana;
import mage.ObjectColor;
import mage.abilities.Ability;
import mage.abilities.common.SimpleStaticAbility;
import mage.abilities.effects.common.InfoEffect;
import mage.abilities.common.AsEntersBattlefieldAbility;
import mage.cards.Card;
import mage.cards.repository.CardRepository;
import mage.players.Player;
import mage.util.CardUtil;
import mage.abilities.ActivatedAbility;
import mage.abilities.mana.ManaOptions;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Differential test for the nested playable-copy skip in
 * {@link XmageFullGamePlayer#getManaAvailable(Game)}: when the game passed in is already a
 * playable-calculation copy, the bridge runs a mirror of the engine's body on it instead of
 * letting the engine copy the game again.
 *
 * <p>Two comparisons per scenario, on real game states built with the shared multiplayer
 * harness (seat P1 is the bridge player, P2 an opponent, real cards):
 * <ol>
 * <li>Mana: the mirrored body run on a fresh {@code createSimulationForPlayableCalc()} copy
 *     equals the engine's {@code PlayerImpl.getManaAvailable} on the real game (sorted
 *     {@code Mana.toString()} lists). Both are reached through package-private accessors.</li>
 * <li>Playable list: {@code getPlayable(game, false, Zone.ALL, false)} with the switch on
 *     equals the result with it off (sorted {@code sourceName|rule} lists). One JVM, one
 *     player instance: the switch is the package-private static
 *     {@link XmageFullGamePlayer#nestedCopySkip}, flipped in try/finally.</li>
 * </ol>
 * Cards: Utopia Sprawl enchants a Forest, so scenarios (a) and (d) use Savannah (a Forest Plains that
 * taps for G or W, no shock prompt) with a separate City of Brass; every other card is as requested.
 */
class XmageNestedCopySkipDifferentialTest {

    private static final String P1 = "P1";
    private static final String P2 = "P2";

    private static XmageMultiplayerScenario scenario(String tag,
            List<XmageNativeStateRestoration.RequestedObject> objects) {
        return XmageMultiplayerScenario.start("nested-skip-" + tag, 2, P1, objects);
    }

    private static XmageNativeStateRestoration.RequestedObject on(
            String pid, String name, int index) {
        return XmageMultiplayerScenario.obj(pid, name, index, Zone.BATTLEFIELD);
    }

    private static XmageNativeStateRestoration.RequestedObject inHand(
            String pid, String name, int index) {
        return XmageMultiplayerScenario.obj(pid, name, index, Zone.HAND);
    }

    private static XmageFullGamePlayer bridge(XmageMultiplayerScenario s, String pid) {
        return (XmageFullGamePlayer) s.seats.get(pid);
    }

    private static Permanent permanent(Game game, String pid, XmageMultiplayerScenario s, String name) {
        for (Permanent p : game.getBattlefield().getAllActivePermanents()) {
            if (p.getName().equals(name) && p.getControllerId().equals(s.seats.get(pid).getId())) {
                return p;
            }
        }
        throw new AssertionError(name + " not on the battlefield for " + pid);
    }

    /**
     * Puts a real Utopia Sprawl onto the battlefield of {@code pid}, attached to that player's
     * {@code landName}, with the chosen colour recorded as the engine would on entry. The card
     * is placed through the engine's own cheat placement; only its "as enters, choose a colour"
     * replacement is dropped from this instance (it would ask the parked seat a question the
     * harness does not drive), and the colour is stored in the same state slot it would use.
     */
    private static void enchant(Game game, XmageMultiplayerScenario s, String pid,
            String landName, ObjectColor chosen) {
        Player owner = s.seats.get(pid);
        Card card = CardRepository.instance.findCard("Utopia Sprawl").createCard();
        card.getAbilities().removeIf(a -> a instanceof AsEntersBattlefieldAbility);
        game.loadCards(new java.util.HashSet<>(List.of(card)), owner.getId());
        Ability fake = new SimpleStaticAbility(Zone.OUTSIDE, new InfoEffect("harness placement"));
        fake.setControllerId(owner.getId());
        fake.setSourceId(card.getId());
        CardUtil.putCardOntoBattlefieldWithEffects(fake, game, card, owner, false);
        game.applyEffects();
        Permanent aura = game.getPermanent(card.getId());
        assertNotNull(aura, "Utopia Sprawl is on the battlefield");
        Permanent land = permanent(game, pid, s, landName);
        aura.attachTo(land.getId(), fake, game);
        land.addAttachment(aura.getId(), fake, game);
        game.getState().setValue(aura.getId() + "_color", chosen);
        game.applyEffects();
    }

    private static List<String> manaStrings(ManaOptions options) {
        List<String> out = new ArrayList<>();
        for (Mana mana : options) {
            out.add(mana.toString());
        }
        Collections.sort(out);
        return out;
    }

    private static List<String> playableStrings(XmageFullGamePlayer player, Game game) {
        List<String> out = new ArrayList<>();
        for (ActivatedAbility ability : player.getPlayable(game, false, Zone.ALL, false)) {
            MageObject source = game.getObject(ability.getSourceId());
            out.add((source == null ? "?" : source.getName()) + "|" + ability.getRule());
        }
        Collections.sort(out);
        return out;
    }

    private static List<String> playableWithSwitch(boolean on, XmageFullGamePlayer player, Game game) {
        boolean before = XmageFullGamePlayer.nestedCopySkip;
        XmageFullGamePlayer.nestedCopySkip = on;
        try {
            return playableStrings(player, game);
        } finally {
            XmageFullGamePlayer.nestedCopySkip = before;
        }
    }

    /** Both assertions for one player of one scenario. */
    private static void assertBothWays(String label, Game game, XmageFullGamePlayer player) {
        Game copy = game.createSimulationForPlayableCalc();
        XmageFullGamePlayer onCopy = (XmageFullGamePlayer) copy.getPlayer(player.getId());
        assertTrue(copy.isSimulation() && copy.inCheckPlayableState(),
                label + ": precondition: the copy is a playable-calculation copy");
        List<String> engine = manaStrings(player.manaAvailableEnginePathForTest(game));
        List<String> mirrored = manaStrings(onCopy.manaAvailableMirroredForTest(copy));
        assertFalse(engine.isEmpty(), label + ": precondition: the player has mana to compare");
        assertEquals(engine, mirrored,
                label + ": mirrored body on a playable copy must equal the engine's "
                        + "getManaAvailable (expected = engine, actual = mirrored)");

        List<String> off = playableWithSwitch(false, player, game);
        List<String> on = playableWithSwitch(true, player, game);
        assertFalse(off.isEmpty(), label + ": precondition: something is playable");
        assertEquals(off, on,
                label + ": playable list with the nested-copy skip ON must equal OFF "
                        + "(expected = off/engine path, actual = on/mirrored path)");
    }

    @Test
    void utopiaSprawlOnMultiOptionLand() {
        XmageMultiplayerScenario s = scenario("sprawl", List.of(
                on(P1, "Savannah", 0), on(P1, "City of Brass", 2),
                on(P1, "Forest", 3), on(P2, "Forest", 0), inHand(P1, "Grizzly Bears", 0)));
        Game game = s.session.restorationGame();
        enchant(game, s, P1, "Savannah", ObjectColor.RED);
        List<String> options = manaStrings(bridge(s, P1).manaAvailableEnginePathForTest(game));
        assertTrue(options.stream().anyMatch(o -> o.contains("{R}")),
                "precondition: the Utopia Sprawl trigger adds its chosen colour (R): " + options);
        assertBothWays("(a) Utopia Sprawl", game, bridge(s, P1));
    }

    @Test
    void zendikarResurgentWithSignetAndBasics() {
        XmageMultiplayerScenario s = scenario("resurgent", List.of(
                on(P1, "Zendikar Resurgent", 0), on(P1, "Simic Signet", 1),
                on(P1, "Forest", 2), on(P1, "Island", 3), on(P2, "Forest", 0),
                inHand(P1, "Grizzly Bears", 0)));
        assertBothWays("(b) Zendikar Resurgent + Signet", s.session.restorationGame(), bridge(s, P1));
    }

    @Test
    void forbiddenOrchardNonManaTrigger() {
        XmageMultiplayerScenario s = scenario("orchard", List.of(
                on(P1, "Forbidden Orchard", 0), on(P1, "Forest", 1), on(P2, "Forest", 0),
                inHand(P1, "Grizzly Bears", 0)));
        assertBothWays("(c1) Forbidden Orchard", s.session.restorationGame(), bridge(s, P1));
    }

    @Test
    void treasureNabberOnOpponentSide() {
        XmageMultiplayerScenario s = scenario("nabber", List.of(
                on(P1, "Sol Ring", 0), on(P1, "Forest", 1),
                on(P2, "Treasure Nabber", 0), on(P2, "Forest", 1),
                inHand(P1, "Grizzly Bears", 0)));
        assertBothWays("(c2) Treasure Nabber", s.session.restorationGame(), bridge(s, P1));
    }

    /**
     * Assist: the engine's AssistAbility asks the OPPONENT for mana on the same game it was
     * given. With the engine path that opponent call copies the game itself; with the mirror
     * it runs on the shared playable copy. Checked on the playable list and on the
     * opponent's options computed twice on one copy (as two assisted spells would).
     */
    @Test
    void assistSpellWhileOpponentHasSprawlSetup() {
        XmageMultiplayerScenario s = scenario("assist", List.of(
                on(P1, "Island", 0), on(P1, "Island", 1),
                inHand(P1, "Huddle Up", 0),
                on(P2, "Savannah", 0), on(P2, "City of Brass", 2)));
        Game game = s.session.restorationGame();
        enchant(game, s, P2, "Savannah", ObjectColor.RED);
        XmageFullGamePlayer me = bridge(s, P1);
        XmageFullGamePlayer opponent = bridge(s, P2);

        List<String> off = playableWithSwitch(false, me, game);
        List<String> on = playableWithSwitch(true, me, game);
        assertTrue(off.stream().anyMatch(a -> a.startsWith("Huddle Up|")),
                "precondition: Huddle Up is playable on the engine path: " + off);
        assertEquals(off, on,
                "(d) playable list with the skip ON must equal OFF (assist reads the opponent's mana)");

        List<String> engineTwice = new ArrayList<>();
        // Engine behaviour: each call copies the game, so the calls cannot influence each other.
        engineTwice.addAll(manaStrings(opponent.manaAvailableEnginePathForTest(game)));
        engineTwice.add("--");
        engineTwice.addAll(manaStrings(opponent.manaAvailableEnginePathForTest(game)));

        Game copy = game.createSimulationForPlayableCalc();
        XmageFullGamePlayer opponentOnCopy = (XmageFullGamePlayer) copy.getPlayer(opponent.getId());
        List<String> mirroredTwice = new ArrayList<>();
        mirroredTwice.addAll(manaStrings(opponentOnCopy.manaAvailableMirroredForTest(copy)));
        mirroredTwice.add("--");
        mirroredTwice.addAll(manaStrings(opponentOnCopy.manaAvailableMirroredForTest(copy)));
        assertEquals(engineTwice, mirroredTwice,
                "(d) DIFFERENCE: the opponent's second getManaAvailable on the SAME playable copy "
                        + "(mirrored, no inner copy) differs from the engine's two-copy behaviour");
    }

    /**
     * Study Hall with one other land: the {1},{T} ability must not be paid by Study Hall's own
     * {T} ability. Run through the bridge's affordability guard with the skip on and off; the
     * guard taps the source on a copy and asks for mana on that same copy, which is where the
     * mirror runs without an inner copy.
     */
    @Test
    void studyHallOwnTapDoesNotPayItsOwnCost() {
        for (boolean otherLand : new boolean[] {false, true}) {
            List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>(List.of(
                    on(P1, "Study Hall", 0), on(P2, "Forest", 0), inHand(P1, "Grizzly Bears", 0)));
            if (otherLand) {
                objects.add(on(P1, "Forest", 1));
            }
            XmageMultiplayerScenario s = scenario("studyhall" + otherLand, objects);
            Game game = s.session.restorationGame();
            XmageFullGamePlayer me = bridge(s, P1);
            String label = "(e) Study Hall, other land=" + otherLand;

            assertBothWays(label, game, me);

            Permanent hall = permanent(game, P1, s, "Study Hall");
            Ability any = null;
            for (Ability a : hall.getAbilities(game)) {
                if (a.isManaAbility() && !((ActivatedAbility) a).getManaCostsToPay().isEmpty()) {
                    any = a;
                }
            }
            assertNotNull(any, label + ": precondition: Study Hall's {1},{T} ability exists");
            ManaOptions available = me.manaAvailableEnginePathForTest(game);
            boolean before = XmageFullGamePlayer.nestedCopySkip;
            boolean affordableOn;
            boolean affordableOff;
            try {
                XmageFullGamePlayer.nestedCopySkip = true;
                affordableOn = me.manaCostAffordable((ActivatedAbility) any, available, game);
                XmageFullGamePlayer.nestedCopySkip = false;
                affordableOff = me.manaCostAffordable((ActivatedAbility) any, available, game);
            } finally {
                XmageFullGamePlayer.nestedCopySkip = before;
            }
            assertEquals(affordableOff, affordableOn, label + ": guard verdict, skip ON vs OFF");
            assertEquals(otherLand, affordableOn,
                    label + ": {1},{T} is payable only by ANOTHER land, never by its own {T}");
        }
    }
}
