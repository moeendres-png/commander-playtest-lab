package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.UUID;
import java.util.function.BooleanSupplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Protection from a player, with an actual card at 4P and 5P on the full-game lane.
 *
 * <p>True-Name Nemesis (Oracle: "As True-Name Nemesis enters, choose a player.
 * True-Name Nemesis has protection from the chosen player."). P1 casts it and
 * chooses P3; every opponent controls a Grizzly Bears. Protection from a player
 * means it can't be blocked by creatures that player controls; other opponents'
 * creatures can still block it.</p>
 *
 * <ul>
 *   <li>The choice offers every player (a player, not only an opponent).</li>
 *   <li>Attacking P3: the external block decision never offers P3's Bears as a
 *       blocker for the Nemesis, and P3 takes 3.</li>
 *   <li>Attacking P2: P2 is offered its Bears as a blocker for the Nemesis.</li>
 * </ul>
 */
class XmageMultiplayerProtectionFromPlayerTest {

    private static final String NEMESIS = "True-Name Nemesis";
    private static final String BEARS = "Grizzly Bears";
    private static final String ISLAND_LABEL = "Island — {T}: Add {U}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void theChosenPlayersCreaturesCantBlockIt(int playerCount) {
        Fixture f = new Fixture("tnn-p3-" + playerCount + "p", playerCount);
        Set<String> offered = f.castNemesisChoosing("P3");
        Set<String> everyone = new TreeSet<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            everyone.add("P" + seat);
        }
        assertEquals(everyone, offered, "the Nemesis's controller chooses among all players");

        f.attackWithNemesis("P3");
        assertTrue(f.blockersOfferedForNemesis.isEmpty(),
                "P3's creatures are never offered to block the Nemesis: " + f.blockersOfferedForNemesis);
        assertEquals(40 - 3, f.life("P3"), "the Nemesis was unblocked");
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void anotherOpponentsCreatureMayBlockIt(int playerCount) {
        Fixture f = new Fixture("tnn-p2-" + playerCount + "p", playerCount);
        f.castNemesisChoosing("P3");
        f.attackWithNemesis("P2");
        assertEquals(Set.of("P2:" + BEARS), f.blockersOfferedForNemesis,
                "P2 is offered exactly its Bears as a blocker for the Nemesis");
    }

    private static final class Fixture {
        final String tag;
        final XmageActualCardCorpusTest.Started started;
        final XmageFullGameSession session;
        final Game game;
        final Set<String> blockersOfferedForNemesis = new TreeSet<>();
        String chosen;
        int decisions;

        Fixture(String tag, int playerCount) {
            this.tag = tag;
            List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:hand-P1-0-TrueNameNemesis", NEMESIS, "P1", "P1",
                    mage.constants.Zone.HAND, false));
            for (int index = 0; index < 3; index++) {
                objects.add(new XmageNativeStateRestoration.RequestedObject(
                        "obj:bf-P1-" + index + "-Island", "Island", "P1", "P1",
                        mage.constants.Zone.BATTLEFIELD, false));
            }
            for (int seat = 2; seat <= playerCount; seat++) {
                objects.add(new XmageNativeStateRestoration.RequestedObject(
                        "obj:bf-P" + seat + "-0-Bears", BEARS, "P" + seat, "P" + seat,
                        mage.constants.Zone.BATTLEFIELD, false));
            }
            started = XmageActualCardCorpusTest.start(tag, playerCount, objects);
            session = started.session();
            game = session.restorationGame();
        }

        UUID id(String pid) {
            return started.seats().get(pid).getId();
        }

        String pidOf(UUID playerId) {
            for (var seat : started.seats().entrySet()) {
                if (seat.getValue().getId().equals(playerId)) {
                    return seat.getKey();
                }
            }
            return null;
        }

        int life(String pid) {
            return started.seats().get(pid).getLife();
        }

        Permanent nemesis() {
            return game.getBattlefield().getAllActivePermanents().stream()
                    .filter(p -> NEMESIS.equals(p.getName())).findFirst().orElse(null);
        }

        Set<String> castNemesisChoosing(String player) {
            chosen = player;
            Set<String> offered = new TreeSet<>();
            XmageActualCardCorpusTest.cast(started, tag + "-cast", NEMESIS);
            XmageActualCardCorpusTest.resolveAll(started, tag, ISLAND_LABEL,
                    (cls, step) -> choosePlayer(cls, tag + "-resolve-" + step, offered));
            assertNotNull(nemesis(), "the Nemesis is on the battlefield");
            return offered;
        }

        boolean choosePlayer(String cls, String stepTag, Set<String> offered) {
            if (!"choose_object".equals(cls) && !"target".equals(cls)) {
                return false;
            }
            JsonObject pick = null;
            for (JsonElement e : session.legalActionsPayload().getAsJsonArray("actions")) {
                JsonObject meta = e.getAsJsonObject().getAsJsonObject("metadata")
                        .getAsJsonObject("xmage_option_metadata");
                if (meta == null || !meta.has("object_id")) {
                    continue;
                }
                String pid = pidOf(UUID.fromString(meta.get("object_id").getAsString()));
                if (pid != null) {
                    offered.add(pid);
                    if (pid.equals(chosen)) {
                        pick = e.getAsJsonObject();
                    }
                }
            }
            if (pick == null) {
                fail("player choice: " + session.legalActionsPayload());
            }
            XmageFullGameTaxExecutionTest.submit(session, stepTag, pick);
            return true;
        }

        /** Drives to P1's next turn, attacks {@code defender} with the Nemesis, ends after combat. */
        void attackWithNemesis(String defender) {
            UUID nemesisId = nemesis().getId();
            boolean attacked = false;
            for (int guard = 0; guard < 500; guard++) {
                String cls = XmageActualCardCorpusTest.decisionClass(started);
                if ("priority".equals(cls) && attacked
                        && game.getStep().getType() == PhaseStep.POSTCOMBAT_MAIN) {
                    return;
                }
                String actor = XmageActualCardCorpusTest.actorPid(started);
                JsonObject legal = session.legalActionsPayload();
                String stepTag = tag + "-" + (decisions++);
                switch (cls) {
                    case "priority" -> XmageActualCardCorpusTest.pass(started, stepTag);
                    case "declare_attacker" -> {
                        JsonObject attack = null;
                        if ("P1".equals(actor)) {
                            for (JsonElement e : legal.getAsJsonArray("actions")) {
                                JsonObject meta = e.getAsJsonObject().getAsJsonObject("metadata")
                                        .getAsJsonObject("xmage_option_metadata");
                                if (meta != null && meta.has("defender_id")
                                        && nemesisId.toString().equals(meta.get("object_id").getAsString())
                                        && id(defender).toString().equals(meta.get("defender_id").getAsString())) {
                                    attack = e.getAsJsonObject();
                                }
                            }
                        }
                        if (attack != null) {
                            attacked = true;
                            XmageFullGameTaxExecutionTest.submit(session, stepTag, attack);
                        } else {
                            XmageFullGameTaxExecutionTest.submit(session, stepTag,
                                    XmageNativeStateRestorationTest.singleActionOfType(
                                            legal, "declare_attackers", "hold_attacker"));
                        }
                    }
                    case "declare_blocker" -> {
                        for (JsonElement e : legal.getAsJsonArray("actions")) {
                            JsonObject meta = e.getAsJsonObject().getAsJsonObject("metadata")
                                    .getAsJsonObject("xmage_option_metadata");
                            if (meta != null && meta.has("attacker_id")
                                    && nemesisId.toString().equals(meta.get("attacker_id").getAsString())) {
                                Permanent blocker = game.getPermanent(
                                        UUID.fromString(meta.get("blocker_id").getAsString()));
                                blockersOfferedForNemesis.add(pidOf(blocker.getControllerId())
                                        + ":" + blocker.getName());
                            }
                        }
                        XmageActualCardCorpusTest.chooseNone(started, stepTag);
                    }
                    case "choose_object" -> {
                        // discard to hand size in cleanup; the only extra cards are drawn Mountains
                        assertEquals(PhaseStep.CLEANUP, game.getStep().getType(), "only cleanup discards");
                        XmageActualCardCorpusTest.chooseNamed(started, stepTag, "Mountain",
                                session.pendingDecisionPayload().getAsJsonObject("decision")
                                        .get("minimum_selections").getAsInt());
                    }
                    default -> fail("unexpected decision " + cls + " for " + actor + " step "
                            + game.getStep().getType() + " prompt " + session.pendingDecisionPayload()
                            + " labels " + legal);
                }
            }
            fail("[" + tag + "] drive bound breached");
        }
    }
}
