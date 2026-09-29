package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.game.command.Dungeon;
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
 * The initiative with an actual card at 3–6 players on the full-game lane.
 *
 * <p>P1 casts White Plume Adventurer (Oracle: "When this creature enters,
 * you take the initiative."). Every opponent controls a Grizzly Bears. The
 * engine's turn order is counterclockwise, so after P1 come PN, then
 * P(N−1).</p>
 *
 * <ul>
 *   <li>Taking the initiative ventures into Undercity. The first room,
 *       Secret Entrance, searches for a basic land; the only ones in these
 *       libraries are Mountains.</li>
 *   <li>A creature dealing combat damage to the player with the initiative
 *       gives its controller the initiative, and that player ventures.</li>
 *   <li>CR 726.4: if the holder leaves the game, the active player takes the
 *       initiative. If the holder is the active player, the next player in
 *       turn order takes it. Either way the new holder ventures. The pin
 *       {@code b19596980f} leaves the initiative with the player who left.
 *       This is F-20 (commander-playtest-lab#327, fixed on
 *       moeendres-png/mage#21); fixed in the XMage multiplayer candidate
 *       f79e4168 (moeendres-png/mage#24) and enabled by the 2026-09-29 successor
 *       repin. CR 726.4 was verified verbatim against CR 2026-09-25.</li>
 * </ul>
 *
 * <p>Rule numbers are inferred: the initiative section follows the
 * monarch's, which is CR 725 in the edition cited by
 * {@link XmageMultiplayerMonarchTest}. The CR text was not re-read in the
 * session that wrote this test.</p>
 */
class XmageMultiplayerInitiativeTest {

    private static final String WHITE_PLUME = "White Plume Adventurer";
    private static final String BEARS = "Grizzly Bears";
    private static final String PLAINS_LABEL = "Plains — {T}: Add {W}.";
    private static final String SECRET_ENTRANCE = "Secret Entrance";

    /** PN's Bears deal combat damage to P1, and PN takes the initiative and ventures. */
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void takingAndStealingTheInitiativeVentures(int playerCount) {
        Fixture f = new Fixture("initiative-steal-" + playerCount + "p", playerCount);
        f.takeInitiative();
        String pn = "P" + playerCount;

        // after PN's draw step (the libraries are all Mountains), before combat
        f.driveUntil(() -> f.active(pn) && f.step() == PhaseStep.PRECOMBAT_MAIN
                && f.game.getStack().isEmpty(), null);
        long mountainsBefore = f.mountainsInHand(pn);
        f.driveUntil(() -> f.active(pn) && f.step() == PhaseStep.POSTCOMBAT_MAIN
                && f.game.getStack().isEmpty(), pn);
        assertEquals(38, f.life("P1"));
        assertEquals(f.id(pn), f.game.getInitiativeId(),
                pn + "'s Bears dealt combat damage to the player with the initiative");
        assertEquals(SECRET_ENTRANCE, f.room(pn), pn + " ventured when it took the initiative");
        assertEquals(mountainsBefore + 1, f.mountainsInHand(pn),
                "Secret Entrance put a basic land from " + pn + "'s library into its hand");
        assertEquals(SECRET_ENTRANCE, f.room("P1"),
                "the former holder P1 did not venture when it lost the initiative");
    }

    /** PN takes the initiative, then concedes on its own turn: P(N−1) is next in turn order. */
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void anActiveHolderLeavingPassesToTheNextPlayer(int playerCount) {
        Fixture f = new Fixture("initiative-active-leave-" + playerCount + "p", playerCount);
        f.takeInitiative();
        String pn = "P" + playerCount;
        String prev = "P" + (playerCount - 1);
        f.driveUntil(() -> f.active(pn) && f.step() == PhaseStep.POSTCOMBAT_MAIN
                && f.game.getStack().isEmpty(), pn);
        assertEquals(f.id(pn), f.game.getInitiativeId());
        long mountainsBefore = f.mountainsInHand(prev);

        f.concede(pn);
        assertEquals(f.id(prev), f.game.getInitiativeId(),
                "726.4: the holder was the active player, so the next player in turn "
                        + "order (" + prev + ") takes the initiative");
        f.driveUntil(() -> f.game.getStack().isEmpty() && f.room(prev) != null, null);
        assertEquals(SECRET_ENTRANCE, f.room(prev), prev + " ventured when it took the initiative");
        assertEquals(mountainsBefore + 1, f.mountainsInHand(prev),
                "Secret Entrance put a basic land from " + prev + "'s library into its hand");
    }

    /** P1 (not active) concedes during P(N−1)'s turn: the active player, not PN. */
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void aNonActiveHolderLeavingPassesToTheActivePlayer(int playerCount) {
        Fixture f = new Fixture("initiative-leave-" + playerCount + "p", playerCount);
        f.takeInitiative();
        String pn = "P" + playerCount;
        String prev = "P" + (playerCount - 1);
        f.driveUntil(() -> f.active(prev) && f.step() == PhaseStep.PRECOMBAT_MAIN
                && f.game.getStack().isEmpty(), null);
        assertEquals(f.id("P1"), f.game.getInitiativeId(), "nobody dealt combat damage to P1");
        long mountainsBefore = f.mountainsInHand(prev);

        f.concede("P1");
        assertEquals(f.id(prev), f.game.getInitiativeId(),
                "726.4: the active player (" + prev + ") takes the initiative, not "
                        + pn + " (next after P1)");
        f.driveUntil(() -> f.game.getStack().isEmpty() && f.room(prev) != null, null);
        assertEquals(SECRET_ENTRANCE, f.room(prev), prev + " ventured when it took the initiative");
        assertEquals(mountainsBefore + 1, f.mountainsInHand(prev),
                "Secret Entrance put a basic land from " + prev + "'s library into its hand");
        assertEquals(null, f.room(pn), pn + " did not take the initiative");
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
                    "obj:hand-P1-0-WhitePlumeAdventurer", WHITE_PLUME, "P1", "P1",
                    mage.constants.Zone.HAND, false));
            for (int index = 0; index < 3; index++) {
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

        String room(String pid) {
            Dungeon dungeon = game.getPlayerDungeon(id(pid));
            return dungeon == null || dungeon.getCurrentRoom() == null
                    ? null : dungeon.getCurrentRoom().getName();
        }

        long mountainsInHand(String pid) {
            return started.seats().get(pid).getHand().getCards(game).stream()
                    .filter(card -> "Mountain".equals(card.getName())).count();
        }

        void takeInitiative() {
            assertEquals(null, game.getInitiativeId(), "nobody has the initiative yet");
            long mountainsBefore = mountainsInHand("P1");
            XmageActualCardCorpusTest.cast(started, tag + "-cast", WHITE_PLUME);
            XmageActualCardCorpusTest.resolveAll(started, tag, PLAINS_LABEL,
                    (cls, step) -> answer(cls, tag + "-resolve-" + step));
            assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", WHITE_PLUME));
            assertEquals(id("P1"), game.getInitiativeId(), "White Plume Adventurer: P1 took the initiative");
            assertEquals(SECRET_ENTRANCE, room("P1"), "taking the initiative ventured into Undercity");
            assertEquals(mountainsBefore + 1, mountainsInHand("P1"),
                    "Secret Entrance put a basic land from the library into P1's hand");
        }

        /**
         * Answers the non-priority decisions these scenarios can raise: a
         * library search for a basic land (only Mountains) or White Plume
         * Adventurer's "untap a creature you control" (only itself).
         */
        boolean answer(String cls, String stepTag) {
            if (!"choose_object".equals(cls) && !"target".equals(cls)) {
                return false;
            }
            JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
            int minimum = Math.max(1, pending.get("minimum_selections").getAsInt());
            String prompt = pending.has("prompt") ? pending.get("prompt").getAsString() : "";
            String first = session.legalActionsPayload().getAsJsonArray("actions").get(0)
                    .getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString();
            String name = first.startsWith(WHITE_PLUME) ? WHITE_PLUME : "Mountain";
            assertTrue(first.startsWith(name), "unexpected choice " + first + " for " + prompt);
            XmageActualCardCorpusTest.chooseNamed(started, stepTag, name, minimum);
            return true;
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
                    default -> {
                        if (!answer(cls, stepTag)) {
                            fail("unexpected decision " + cls + " for " + actor);
                        }
                    }
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
