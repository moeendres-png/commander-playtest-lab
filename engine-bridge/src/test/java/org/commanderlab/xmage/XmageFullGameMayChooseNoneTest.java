package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.abilities.Mode;
import mage.abilities.Modes;
import mage.cards.Card;
import mage.constants.PhaseStep;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #714: a "may choose none" modal ability needs no mode at all.
 *
 * <p>{@code Modes.isSelectedValid} accepts zero chosen modes when
 * {@code Modes.isMayChooseNone()} is set, and {@code HumanPlayer.chooseMode}
 * (pinned XMage) then shows only Done/Cancel. The bridge computed its minimum
 * without that flag, so such an ability asked for at least one mode: with no
 * choosable mode it took the doomed-cast rewind ({@code noViableMode}) although
 * XMage would accept the empty choice.</p>
 *
 * <p>Shadrix Silverquill is the one card at the pin that sets
 * {@code setMayChooseNone(true)} ("At the beginning of combat on your turn, you
 * may choose two. Each mode must target a different player."). Every mode
 * targets a player, so True Believer ("You have shroud") under each player's
 * control leaves no mode choosable. The expectations are read from the engine's
 * own {@code Modes} and target state, not restated.</p>
 *
 * <p>Red control: {@link #choosableModesStillAllowChoosingNone()} fails on the
 * pre-fix bridge (observed: "the card may choose none, so declining is a legal
 * answer ==&gt; expected: &lt;0&gt; but was: &lt;1&gt;"). The pre-fix bridge demanded
 * at least one mode, so a pilot could not take the legal "choose none" answer.
 * {@link #afterTheFirstPickTheCardsMinimumGovernsAgain()} is the second red
 * control: "choose none" ends only an empty selection (Modes.isSelectedValid), so
 * after one pick the card's minimum governs again.</p>
 *
 * <p>Control: {@link #noModeFrameWhenNothingIsChoosableAndTheCardMayChooseNone()}
 * is green before and after the fix. With every player shrouded, XMage itself
 * asks no mode question for Shadrix at the pin, so the doomed-rewind branch the
 * issue describes is not reachable through this card today; the test pins that
 * no mode frame appears, so a later engine change that does ask would meet the
 * corrected minimum (0) instead of the rewind.</p>
 */
class XmageFullGameMayChooseNoneTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";
    private static final String SHADRIX = "Shadrix Silverquill";
    private static final String TRUE_BELIEVER = "True Believer";

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
                tag, 2, 714714L, List.copyOf(players), List.copyOf(commanders), objects,
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
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

    private static String decisionClass(Started s) {
        return s.session().legalActionsPayload().get("decision_class").getAsString();
    }

    private static List<String> labels(Started s) {
        List<String> out = new ArrayList<>();
        for (JsonElement element : s.session().legalActionsPayload().getAsJsonArray("actions")) {
            out.add(element.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString());
        }
        return out;
    }

    private static int step;

    private static void passPriority(Started s) {
        for (JsonElement element : s.session().legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if ("pass_priority".equals(action.get("action_type").getAsString())) {
                XmageFullGameTaxExecutionTest.submit(s.session(), "mode714-" + (step++), action);
                return;
            }
        }
        throw new AssertionError("no pass offered in " + decisionClass(s) + ": " + labels(s));
    }

    /**
     * Passes priority out of precombat main until the first non-priority frame or
     * until the game has left the beginning-of-combat step. Returns the decision
     * class that stopped the walk.
     */
    private static String walkIntoCombat(Started s) {
        for (int i = 0; i < 12; i++) {
            String pending = decisionClass(s);
            if (!"priority".equals(pending)) {
                return pending;
            }
            PhaseStep current = s.game().getStep().getType();
            if (current != PhaseStep.PRECOMBAT_MAIN && current != PhaseStep.BEGIN_COMBAT) {
                return "left_begin_combat:" + current;
            }
            passPriority(s);
        }
        throw new AssertionError("the walk into combat did not settle");
    }

    private static Permanent shadrix(Started s) {
        for (Permanent permanent : s.game().getBattlefield().getAllPermanents()) {
            if (SHADRIX.equals(permanent.getName())) {
                return permanent;
            }
        }
        throw new AssertionError(SHADRIX + " is not on the battlefield");
    }

    /** The modes of Shadrix's beginning-of-combat trigger, read from the engine. */
    private static Ability shadrixTrigger(Started s) {
        Card card = shadrix(s);
        for (Ability ability : card.getAbilities(s.game())) {
            if (ability.getModes().size() == 3) {
                return ability;
            }
        }
        throw new AssertionError(SHADRIX + " has no three-mode ability");
    }

    @Test
    void noModeFrameWhenNothingIsChoosableAndTheCardMayChooseNone() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", SHADRIX, 0, Zone.BATTLEFIELD));
        objects.add(obj("P1", TRUE_BELIEVER, 0, Zone.BATTLEFIELD));
        objects.add(obj("P2", TRUE_BELIEVER, 0, Zone.BATTLEFIELD));
        Started s = start("mode714-shroud", objects);

        // Preconditions, from the engine: may choose none, and no mode is choosable
        // because every mode targets a player and both players have shroud.
        Ability trigger = shadrixTrigger(s);
        Modes modes = trigger.getModes();
        assertTrue(modes.isMayChooseNone(), SHADRIX + " may choose none at the pin");
        assertTrue(modes.getMinModes() > 0, "its printed minimum is not already zero");
        for (Mode mode : modes.values()) {
            assertFalse(mode.getTargets().canChoose(s.p("P1").getId(), trigger, s.game()),
                    "with both players shrouded no mode has a legal target: " + mode);
        }

        String stoppedAt = walkIntoCombat(s);
        assertFalse("mode".equals(stoppedAt),
                "a may-choose-none ability with nothing choosable must ask no mode frame "
                        + "(XMage accepts the empty choice); asked: " + labels(s));
        assertEquals(40, s.p("P1").getLife(), "no mode resolved for P1");
        assertEquals(40, s.p("P2").getLife(), "no mode resolved for P2");
    }

    @Test
    void choosableModesStillAllowChoosingNone() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", SHADRIX, 0, Zone.BATTLEFIELD));
        Started s = start("mode714-open", objects);

        assertTrue(shadrixTrigger(s).getModes().isMayChooseNone());
        String stoppedAt = walkIntoCombat(s);
        assertEquals("mode", stoppedAt, "with targetable players the trigger asks for modes");
        JsonObject pending = s.session().pendingDecisionPayload().getAsJsonObject("decision");
        assertNotNull(pending);
        assertEquals(0, pending.get("minimum_selections").getAsInt(),
                "the card may choose none, so declining is a legal answer");
        assertFalse(labels(s).isEmpty(), "the choosable modes are still offered");

        // Declining is accepted by the engine: the trigger resolves with no mode.
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "mode714-decline");
        proposal.addProperty("actor_id", pending.get("actor_id").getAsString());
        proposal.addProperty("action_type", "structural_decision");
        proposal.add("target_ids", new com.google.gson.JsonArray());
        proposal.add("selected_modes", new com.google.gson.JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", pending.get("decision_id").getAsString());
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", new com.google.gson.JsonArray());
        choices.add("ordering", new com.google.gson.JsonArray());
        proposal.add("choices", choices);
        s.session().submitAction(proposal);
        for (int i = 0; i < 6 && s.game().getStack().size() > 0; i++) {
            assertEquals("priority", decisionClass(s),
                    "no further mode or target frame after declining: " + labels(s));
            passPriority(s);
        }
        assertEquals(0, s.game().getStack().size(), "the declined trigger left the stack");
        assertEquals(40, s.p("P1").getLife(), "no mode resolved");
        assertEquals(40, s.p("P2").getLife(), "no mode resolved");
    }


    /**
     * CR 700.2 / {@code Modes.isSelectedValid}: "you may choose two" is zero or two,
     * never one. Once a mode is picked the card's minimum governs again, so the
     * second frame must not offer a decline (XMage would reject the one-mode choice
     * and roll the trigger back). Red on the first revision of this fix, which made
     * the minimum 0 whenever the card may choose none.
     */
    @Test
    void afterTheFirstPickTheCardsMinimumGovernsAgain() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", SHADRIX, 0, Zone.BATTLEFIELD));
        Started s = start("mode714-second", objects);

        Modes modes = shadrixTrigger(s).getModes();
        assertTrue(modes.getMinModes() > 1, "Shadrix needs two modes unless it chooses none");
        assertEquals("mode", walkIntoCombat(s));
        JsonObject first = s.session().legalActionsPayload().getAsJsonArray("actions")
                .get(0).getAsJsonObject();
        XmageFullGameTaxExecutionTest.submit(s.session(), "mode714-" + (step++), first);

        assertEquals("mode", decisionClass(s), "the second mode is asked");
        JsonObject pending = s.session().pendingDecisionPayload().getAsJsonObject("decision");
        assertEquals(1, pending.get("minimum_selections").getAsInt(),
                "with one mode chosen, declining would leave an invalid one-mode choice");
    }
}
