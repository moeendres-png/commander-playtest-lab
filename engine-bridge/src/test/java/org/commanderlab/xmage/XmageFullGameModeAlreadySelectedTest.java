package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.Modes;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.game.stack.Spell;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * F-75 / CR 700.2: an already-selected mode is not offered again.
 *
 * <p>{@code Modes.getAvailableModes} applies only the once-per-turn filter
 * ("isLimitUsageByOnce"); its own javadoc says the caller must filter
 * already-selected modes out. Both of XMage's players do that before offering a
 * mode ({@code HumanPlayer.chooseMode} skips every mode in
 * {@code getSelectedModes()} unless {@code isMayChooseSameModeMoreThanOnce()};
 * {@code ComputerPlayer.chooseMode} carries the same condition). The bridge did
 * not, so a "choose one or more" spell offered a mode the pilot had already
 * taken; re-picking it reached {@code Modes.addSelectedMode}, which throws
 * "Wrong call of addSelectedMode: mode already selected" and aborted the game.
 * The offered set must therefore be exactly the engine's legal set.</p>
 *
 * <p>Both cases are real registered cards at the pin, and the expectations are
 * derived from the engine's own {@code Modes} state rather than from a
 * hand-written mode list, so a rules or card change moves the assertion rather
 * than silently passing it:</p>
 * <ul>
 *   <li><b>Farewell</b> ({4}{W}{W}, "Choose one or more", four modes,
 *       max 4, no "may choose the same mode more than once"). The second mode
 *       frame must offer every remaining mode and must not offer the one just
 *       taken.</li>
 *   <li><b>Season of the Bold</b> ({3}{R}{R}, "Choose up to five {P} worth of
 *       modes. You may choose the same mode more than once"). The rule must not
 *       apply, so a mode taken in the first frame is offered again in the
 *       second frame.</li>
 * </ul>
 *
 * <p>Red control: {@link #farewellSecondModeFrameOmitsTheSelectedMode()} is the
 * only test here that fails on the pre-fix bridge (observed: exit 1,
 * "one fewer mode is offered the second time ==&gt; expected: &lt;3&gt; but was:
 * &lt;4&gt;"). The other two are controls that must stay green across the fix:
 * they prove the CR 700.2 exception still re-offers a mode, and that the
 * corrected frame still resolves the spell on the mode the pilot chose.</p>
 */
class XmageFullGameModeAlreadySelectedTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    /** Farewell: "Choose one or more" over artifacts/creatures/enchantments/graveyards. */
    private static final String FAREWELL = "Farewell";

    /** "You may choose the same mode more than once" (paw prints). */
    private static final String SEASON_OF_THE_BOLD = "Season of the Bold";

    private record Started(XmageFullGameSession session, Map<String, Player> seats) {
        Game game() {
            return session.restorationGame();
        }

        Player p(String pid) {
            return seats.get(pid);
        }
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String pid, String name, int index, Zone zone) {
        String slug = name.replaceAll("[^A-Za-z0-9]+", "");
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zone.name().toLowerCase() + "-" + pid + "-" + index + "-" + slug,
                name, pid, pid, zone, false);
    }

    /** 2P restoration at P1's turn 1 precombat main, P1 holding priority. */
    private static Started start(String tag,
            List<XmageNativeStateRestoration.RequestedObject> objects) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int seat = 1; seat <= 2; seat++) {
            String pid = "P" + seat;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", ROGRAKH, pid, 0));
        }
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                tag, 2, 424242L, List.copyOf(players), List.copyOf(commanders), objects,
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedPlayer player : players) {
            List<String> mainboard = new ArrayList<>();
            for (int index = 0; index < 99; index++) {
                mainboard.add("Mountain");
            }
            handles.add(importer.importCommanderDeck(tag + "-" + player.playerId(),
                    tag + "-hash", mainboard, List.of(ROGRAKH)).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new Started(session, seats);
    }

    // ------------------------------------------------------------------ frame

    private static String decisionClass(Started s) {
        return s.session().legalActionsPayload().get("decision_class").getAsString();
    }

    private static String actor(Started s) {
        return XmageNativeStateRestorationTest.pidOf(s.seats(),
                s.session().legalActionsPayload().get("actor_id").getAsString());
    }

    private static List<String> labels(Started s) {
        List<String> out = new ArrayList<>();
        for (JsonElement element : s.session().legalActionsPayload().getAsJsonArray("actions")) {
            out.add(element.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString());
        }
        return out;
    }

    /**
     * The engine mode ids offered in the pending frame, in engine-offered (card
     * printed) order. A mode option carries its engine mode id in "modes".
     */
    private static List<String> offeredModeIds(Started s) {
        List<String> out = new ArrayList<>();
        for (JsonElement element : s.session().legalActionsPayload().getAsJsonArray("actions")) {
            JsonArray modes = element.getAsJsonObject().getAsJsonArray("modes");
            assertEquals(1, modes.size(), "a mode option carries exactly one engine mode id");
            out.add(modes.get(0).getAsString());
        }
        return out;
    }

    private static JsonObject actionAt(Started s, int index) {
        return s.session().legalActionsPayload().getAsJsonArray("actions")
                .get(index).getAsJsonObject();
    }

    private static JsonObject actionContaining(Started s, String actionType, String labelPart) {
        for (JsonElement element : s.session().legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (actionType.equals(action.get("action_type").getAsString())
                    && action.getAsJsonObject("metadata").get("label").getAsString()
                            .contains(labelPart)) {
                return action;
            }
        }
        throw new AssertionError(actionType + " '" + labelPart + "' not offered in "
                + decisionClass(s) + " to " + actor(s) + ": " + labels(s));
    }

    private static int step;

    private static void take(Started s, String actionType, String labelPart) {
        XmageFullGameTaxExecutionTest.submit(s.session(), "mode709-" + (step++),
                actionContaining(s, actionType, labelPart));
    }

    /** Answers the pending mode frame with the option at {@code index}. */
    private static void chooseMode(Started s, int index) {
        XmageFullGameTaxExecutionTest.submit(s.session(), "mode709-" + (step++),
                actionAt(s, index));
    }

    /** Pays the pending mana cost from the named land type, spending pool mana first. */
    private static void payWith(Started s, String land) {
        for (int i = 0; i < 20 && "mana_payment".equals(decisionClass(s)); i++) {
            boolean poolOffered = labels(s).stream().anyMatch(l -> l.startsWith("Spend "));
            take(s, "pay_cost", poolOffered ? "Spend " : land);
        }
    }

    /** Answers the pending mode frame with nothing selected (stop choosing modes). */
    private static void stopChoosingModes(Started s, String tag) {
        JsonObject pending = s.session().pendingDecisionPayload().getAsJsonObject("decision");
        assertEquals(0, pending.get("minimum_selections").getAsInt(),
                "stopping is legal once the minimum is already met");
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", pending.get("actor_id").getAsString());
        proposal.addProperty("action_type", "structural_decision");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", pending.get("decision_id").getAsString());
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", new JsonArray());
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        s.session().submitAction(proposal);
    }

    /** The {@link Modes} the engine is choosing from for the spell on the stack. */
    private static Modes modesOnStack(Started s) {
        assertEquals(1, s.game().getStack().size(), "the cast spell is on the stack");
        Spell spell = (Spell) s.game().getStack().getFirst();
        return spell.getSpellAbility().getModes();
    }

    // ------------------------------------------------- Farewell: no re-offer

    /**
     * Farewell (CR 700.2, "Choose one or more"). After the first selection the
     * second frame must not offer that mode again.
     */
    @Test
    void farewellSecondModeFrameOmitsTheSelectedMode() {
        Started s = castFarewell("mode709-farewell");

        assertEquals("mode", decisionClass(s), "the caster chooses the modes");
        assertEquals("P1", actor(s));
        Modes modes = modesOnStack(s);
        assertEquals(4, modes.size(), "Farewell is a four-mode spell at the pin");
        assertEquals(1, modes.getMinModes(), "\"choose one or more\": at least one mode");
        assertEquals(4, modes.getMaxModes(s.game(), null), "at most all four modes");
        assertFalse(modes.isMayChooseSameModeMoreThanOnce(),
                "Farewell does not allow choosing a mode twice");

        List<String> firstFrame = offeredModeIds(s);
        assertEquals(4, firstFrame.size(), "all four Farewell modes are offered");
        String chosen = firstFrame.get(1);
        chooseMode(s, 1);

        // Second "choose one or more" frame: the taken mode is gone (CR 700.2).
        assertEquals("mode", decisionClass(s), "a second mode frame is asked");
        List<String> secondFrame = offeredModeIds(s);
        assertEquals(3, secondFrame.size(), "one fewer mode is offered the second time");
        assertFalse(secondFrame.contains(chosen),
                "the mode selected in the first frame must not be re-offered: "
                        + secondFrame + " contains " + chosen);
        Set<String> remaining = new LinkedHashSet<>(firstFrame);
        remaining.remove(chosen);
        assertEquals(remaining, new LinkedHashSet<>(secondFrame),
                "the offered set is exactly the first frame's modes minus the one taken");

        stopChoosingModes(s, "mode709-farewell-stop");
        resolveStack(s, "Plains");
        assertEquals(0, s.game().getStack().size(), "Farewell resolved on the one chosen mode");
    }

    /**
     * Resolution control: after the corrected second frame the pilot stops and
     * Farewell resolves on the single chosen mode, exiling the creatures. This
     * is the state the F-75 real-deck abort prevented (there, the pilot re-picked
     * the mode the bridge wrongly re-offered and {@code Modes.addSelectedMode}
     * threw "Wrong call of addSelectedMode: mode already selected", aborting the
     * game with {@code XMAGE_INTERNAL_ERRORS}). Green before and after the fix:
     * it pins the effect, not the offered set.
     */
    @Test
    void farewellStopsAfterOneModeAndResolves() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", FAREWELL, 0, Zone.HAND));
        for (int i = 0; i < 6; i++) {
            objects.add(obj("P1", "Plains", i, Zone.BATTLEFIELD));
        }
        objects.add(obj("P1", "Grizzly Bears", 0, Zone.BATTLEFIELD));
        objects.add(obj("P2", "Grizzly Bears", 0, Zone.BATTLEFIELD));
        Started s = start("mode709-farewell-resolve", objects);

        take(s, "activate_ability", "Cast " + FAREWELL);
        payWith(s, "Plains");
        assertEquals("mode", decisionClass(s));
        chooseMode(s, 1);
        assertEquals("mode", decisionClass(s));
        stopChoosingModes(s, "mode709-farewell-resolve-stop");

        resolveStack(s, "Plains");
        assertEquals(0, s.game().getStack().size(), "Farewell resolved without aborting");
        assertEquals(0, bearsOnBattlefield(s, "P1"), "P1's creature was exiled");
        assertEquals(0, bearsOnBattlefield(s, "P2"), "P2's creature was exiled");
    }

    /** Passes priority (paying any residual cost) until the stack is empty. */
    private static void resolveStack(Started s, String land) {
        for (int i = 0; i < 20 && s.game().getStack().size() > 0; i++) {
            if ("priority".equals(decisionClass(s))) {
                take(s, "pass_priority", "Pass");
            } else if ("mana_payment".equals(decisionClass(s))) {
                payWith(s, land);
            } else {
                break;
            }
        }
    }

    private static Started castFarewell(String tag) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", FAREWELL, 0, Zone.HAND));
        for (int i = 0; i < 6; i++) {
            objects.add(obj("P1", "Plains", i, Zone.BATTLEFIELD));
        }
        Started s = start(tag, objects);
        take(s, "activate_ability", "Cast " + FAREWELL);
        payWith(s, "Plains");
        return s;
    }

    // ------------------------------- Season of the Bold: the rule must not apply

    /**
     * Control for the CR 700.2 exception: "You may choose the same mode more
     * than once". The engine reports
     * {@code Modes.isMayChooseSameModeMoreThanOnce()} and both XMage players
     * honour it, so a taken mode must still be offered in the second frame.
     */
    @Test
    void seasonOfTheBoldReoffersAModeTheCardMayChooseTwice() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", SEASON_OF_THE_BOLD, 0, Zone.HAND));
        for (int i = 0; i < 5; i++) {
            objects.add(obj("P1", "Mountain", i, Zone.BATTLEFIELD));
        }
        Started s = start("mode709-season", objects);

        take(s, "activate_ability", "Cast " + SEASON_OF_THE_BOLD);
        payWith(s, "Mountain");
        assertEquals("mode", decisionClass(s), "the caster chooses the modes");
        assertEquals("P1", actor(s));
        Modes modes = modesOnStack(s);
        assertTrue(modes.isMayChooseSameModeMoreThanOnce(),
                "Season of the Bold allows choosing the same mode more than once");
        List<String> firstFrame = offeredModeIds(s);
        assertTrue(firstFrame.size() >= 2, "several Season of the Bold modes are offered");
        String chosen = firstFrame.get(0);
        chooseMode(s, 0);

        // The cheapest {P} mode still fits the paw-print budget, so every mode --
        // including the one just taken -- stays on offer.
        assertEquals("mode", decisionClass(s), "a second mode frame is asked");
        List<String> secondFrame = offeredModeIds(s);
        assertTrue(secondFrame.contains(chosen),
                "the mode the card may choose twice is still offered: " + secondFrame);
        assertEquals(new LinkedHashSet<>(firstFrame), new LinkedHashSet<>(secondFrame),
                "no mode is withheld on a card that may choose a mode twice");
    }

    // ---------------------------------------------------------------- helpers

    private static int bearsOnBattlefield(Started s, String pid) {
        int count = 0;
        for (Permanent permanent : s.game().getBattlefield().getAllPermanents()) {
            if ("Grizzly Bears".equals(permanent.getName())
                    && s.p(pid).getId().equals(permanent.getControllerId())) {
                count++;
            }
        }
        return count;
    }
}