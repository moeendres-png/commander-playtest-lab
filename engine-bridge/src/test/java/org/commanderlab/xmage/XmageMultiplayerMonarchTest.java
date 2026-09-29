package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.function.BooleanSupplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * CR 725 (the monarch) with an actual card at 3–6 players on the full-game
 * lane.
 *
 * <p>P1 casts Palace Sentinels (Oracle: "When this creature enters, you
 * become the monarch."). Every opponent controls a Grizzly Bears. The
 * engine's turn order is counterclockwise, so after P1 come PN, then
 * P(N−1).</p>
 *
 * <ul>
 *   <li>725.2: the monarch draws a card at the beginning of their end step.</li>
 *   <li>725.2: a creature dealing combat damage to the monarch makes its
 *       controller the monarch.</li>
 *   <li>725.4: if the monarch leaves the game, the active player becomes the
 *       monarch. If the monarch is the active player, the next player in turn
 *       order becomes the monarch. Both cases are chosen so that the two
 *       branches name different players.</li>
 * </ul>
 */
class XmageMultiplayerMonarchTest {

    private static final String SENTINELS = "Palace Sentinels";
    private static final String BEARS = "Grizzly Bears";
    private static final String PLAINS_LABEL = "Plains — {T}: Add {W}.";

    /** Stolen by PN in combat; PN (active) concedes: P(N−1) is next in turn order. */
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void combatDamageStealsAndAnActiveLeaverPassesToTheNextPlayer(int playerCount) {
        Fixture f = new Fixture("monarch-steal-" + playerCount + "p", playerCount);
        f.becomeMonarch();
        int libraryBefore = f.library("P1");
        String pn = "P" + playerCount;
        String prev = "P" + (playerCount - 1);

        f.driveUntil(() -> f.active(pn) && f.step() == PhaseStep.POSTCOMBAT_MAIN, pn);
        assertEquals(1, libraryBefore - f.library("P1"),
                "725.2: P1 drew one card at the beginning of their end step");
        assertEquals(f.id(pn), f.game.getMonarchId(),
                "725.2: " + pn + "'s Bears dealt combat damage to the monarch");
        assertEquals(38, f.life("P1"));

        f.concede(pn);
        assertEquals(f.id(prev), f.game.getMonarchId(),
                "725.4: the monarch was the active player, so the next player in turn "
                        + "order (" + prev + ") becomes the monarch");
    }

    /** P1 (not active) concedes during P(N−1)'s turn: the active player, not PN. */
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void aNonActiveLeaverPassesToTheActivePlayer(int playerCount) {
        Fixture f = new Fixture("monarch-leave-" + playerCount + "p", playerCount);
        f.becomeMonarch();
        String prev = "P" + (playerCount - 1);

        f.driveUntil(() -> f.active(prev) && f.step() == PhaseStep.PRECOMBAT_MAIN, null);
        assertEquals(f.id("P1"), f.game.getMonarchId(), "nobody dealt combat damage to P1");

        f.concede("P1");
        assertEquals(f.id(prev), f.game.getMonarchId(),
                "725.4: the active player (" + prev + ") becomes the monarch, not P"
                        + playerCount + " (next after P1)");
    }

    private static final class Fixture {
        final String tag;
        final XmageActualCardCorpusTest.Started started;
        final XmageFullGameSession session;
        final Game game;
        int decisions;

        Fixture(String tag, int playerCount) {
            this.tag = tag;
            List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:hand-P1-0-PalaceSentinels", SENTINELS, "P1", "P1",
                    mage.constants.Zone.HAND, false));
            for (int index = 0; index < 4; index++) {
                objects.add(new XmageNativeStateRestoration.RequestedObject(
                        "obj:bf-P1-" + index + "-Plains", "Plains", "P1", "P1",
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

        boolean active(String pid) {
            return id(pid).equals(game.getActivePlayerId());
        }

        PhaseStep step() {
            return game.getStep().getType();
        }

        int life(String pid) {
            return started.seats().get(pid).getLife();
        }

        int library(String pid) {
            return started.seats().get(pid).getLibrary().size();
        }

        void becomeMonarch() {
            assertEquals(null, game.getMonarchId(), "no monarch before the Sentinels");
            XmageActualCardCorpusTest.cast(started, tag + "-cast", SENTINELS);
            XmageActualCardCorpusTest.resolveAll(started, tag, PLAINS_LABEL,
                    XmageActualCardCorpusTest.NONE);
            assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", SENTINELS));
            assertEquals(id("P1"), game.getMonarchId(), "the Sentinels made P1 the monarch");
        }

        /** Passes and answers until {@code done} holds at a priority decision. */
        void driveUntil(BooleanSupplier done, String attackerAtP1) {
            for (int guard = 0; guard < 400; guard++) {
                String cls = XmageActualCardCorpusTest.decisionClass(started);
                if ("priority".equals(cls) && done.getAsBoolean()) {
                    return;
                }
                String actor = XmageActualCardCorpusTest.actorPid(started);
                JsonObject legal = session.legalActionsPayload();
                String stepTag = tag + "-" + (decisions++);
                switch (cls) {
                    case "priority" -> XmageActualCardCorpusTest.pass(started, stepTag);
                    case "declare_attacker" -> XmageFullGameTaxExecutionTest.submit(session,
                            stepTag, actor.equals(attackerAtP1)
                                    ? attackAt(legal, id("P1"))
                                    : XmageNativeStateRestorationTest.singleActionOfType(
                                            legal, "declare_attackers", "hold_attacker"));
                    case "declare_blocker" -> XmageActualCardCorpusTest.chooseNone(started, stepTag);
                    case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(started, stepTag,
                            "Mountain", Math.max(1, session.pendingDecisionPayload()
                                    .getAsJsonObject("decision")
                                    .get("minimum_selections").getAsInt()));
                    default -> fail("unexpected decision " + cls + " for " + actor);
                }
            }
            fail("[" + tag + "] drive bound breached");
        }

        void concede(String pid) {
            String principal = id(pid).toString();
            assertTrue(session.concedeOfferPayload(principal)
                    .get("concede_available").getAsBoolean(), pid + " may concede");
            JsonObject proposal = new JsonObject();
            proposal.addProperty("proposal_id", tag + "-concede-" + pid);
            proposal.addProperty("actor_id", principal);
            proposal.addProperty("player_id", principal);
            JsonObject result = session.submitConcede(proposal);
            assertEquals(principal, result.get("conceded_actor_id").getAsString());
            assertTrue(started.seats().get(pid).hasLost() || !started.seats().get(pid).isInGame(),
                    pid + " left the game");
        }

        private static JsonObject attackAt(JsonObject legal, UUID defender) {
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                        .getAsJsonObject("xmage_option_metadata");
                if (meta != null && meta.has("defender_id")
                        && defender.toString().equals(meta.get("defender_id").getAsString())) {
                    return element.getAsJsonObject();
                }
            }
            assertNotNull(null, "attack at P1 not offered: " + legal);
            return null;
        }
    }
}
