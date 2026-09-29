package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.counters.CounterType;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.UUID;
import java.util.function.BooleanSupplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Battles (Sieges) with an actual card at 3–6 players on the full-game lane.
 *
 * <p>P1 casts Invasion of Zendikar (Battle — Siege, defense 3). As a Siege
 * enters, its controller chooses an opponent to protect it; a battle can be
 * attacked by any player other than its protector. Every opponent controls a
 * Grizzly Bears. The engine's turn order is counterclockwise
 * (P1, PN, P(N−1), …).</p>
 *
 * <ul>
 *   <li>Enabled: P1's protector decision offers exactly the opponents
 *       P2…PN; P1 picks P(N−1). PN's attack options include the battle and
 *       PN's Bears reduce its defense from 3 to 1; the protector P(N−1) is
 *       never offered the battle.</li>
 *   <li>F-22 (disabled): if the protector leaves the game, the battle must get
 *       a protector who is still in the game, chosen by its controller, and it
 *       stays attackable. The pin keeps the departed player as protector (the
 *       state-based check tests {@code game.getPlayer(protector) == null},
 *       which a player who left never satisfies), and nobody can attack the
 *       battle for the rest of the game.</li>
 * </ul>
 */
class XmageMultiplayerBattleTest {

    private static final String SIEGE = "Invasion of Zendikar";
    private static final String BEARS = "Grizzly Bears";
    private static final String FOREST_LABEL = "Forest — {T}: Add {G}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void protectorIsAnOpponentAndEveryoneElseMayAttackTheBattle(int playerCount) {
        Fixture f = new Fixture("battle-" + playerCount + "p", playerCount);
        String pn = "P" + playerCount;
        String protector = "P" + (playerCount - 1);
        Set<String> offered = f.castSiegeChoosing(protector);
        Set<String> opponents = new TreeSet<>();
        for (int seat = 2; seat <= playerCount; seat++) {
            opponents.add("P" + seat);
        }
        assertEquals(opponents, offered, "the protector is chosen among P1's opponents");
        assertEquals(f.id(protector), f.battle().getProtectorId());
        assertEquals(3, f.defense());

        f.driveUntil(() -> f.active(pn) && f.step() == PhaseStep.POSTCOMBAT_MAIN
                && f.game.getStack().isEmpty(), pn);
        assertTrue(f.battleOfferedTo.contains(pn), pn + " may attack the battle");
        assertEquals(1, f.defense(), pn + "'s Bears dealt 2 damage to the battle");

        f.driveUntil(() -> f.active(protector) && f.step() == PhaseStep.POSTCOMBAT_MAIN
                && f.game.getStack().isEmpty(), null);
        assertTrue(!f.battleOfferedTo.contains(protector), "the protector can't attack the battle");
    }

    @Disabled("F-22: at the pin a battle keeps a protector who left the game and can't be attacked")
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void aProtectorWhoLeavesIsReplacedAndTheBattleStaysAttackable(int playerCount) {
        Fixture f = new Fixture("battle-leave-" + playerCount + "p", playerCount);
        String pn = "P" + playerCount;
        f.castSiegeChoosing(pn);
        f.driveUntil(() -> f.active(pn) && f.step() == PhaseStep.PRECOMBAT_MAIN
                && f.game.getStack().isEmpty(), null);
        f.concede(pn);
        f.driveUntil(() -> f.game.getStack().isEmpty() && f.step() != PhaseStep.PRECOMBAT_MAIN
                || !f.active(pn), null);
        UUID protector = f.battle().getProtectorId();
        assertNotEquals(f.id(pn), protector, "a player who left the game can't protect a battle");
        assertNotNull(protector);
        assertTrue(f.game.getPlayer(protector).isInGame(), "the new protector is in the game");
        assertNotEquals(f.id("P1"), protector, "the protector is an opponent of the controller");
    }

    private static final class Fixture {
        final String tag;
        final XmageActualCardCorpusTest.Started started;
        final XmageFullGameSession session;
        final Game game;
        final Set<String> battleOfferedTo = new TreeSet<>();
        String protectorChoice;
        int decisions;

        Fixture(String tag, int playerCount) {
            this.tag = tag;
            List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:hand-P1-0-InvasionOfZendikar", SIEGE, "P1", "P1",
                    mage.constants.Zone.HAND, false));
            for (int index = 0; index < 4; index++) {
                objects.add(new XmageNativeStateRestoration.RequestedObject(
                        "obj:bf-P1-" + index + "-Forest", "Forest", "P1", "P1",
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

        Permanent battle() {
            return game.getBattlefield().getAllActivePermanents().stream()
                    .filter(p -> SIEGE.equals(p.getName())).findFirst().orElse(null);
        }

        int defense() {
            return battle().getCounters(game).getCount(CounterType.DEFENSE);
        }

        /** Casts the Siege; returns the players offered as protector. */
        Set<String> castSiegeChoosing(String protector) {
            protectorChoice = protector;
            Set<String> offered = new TreeSet<>();
            XmageActualCardCorpusTest.cast(started, tag + "-cast", SIEGE);
            XmageActualCardCorpusTest.resolveAll(started, tag, FOREST_LABEL,
                    (cls, step) -> answer(cls, tag + "-resolve-" + step, offered));
            assertNotNull(battle(), "the Siege is on the battlefield");
            return offered;
        }

        /** Protector choice (by player) or the library search (Mountains, the only basics). */
        boolean answer(String cls, String stepTag, Set<String> offeredProtectors) {
            if (!"choose_object".equals(cls) && !"target".equals(cls)) {
                return false;
            }
            JsonObject legal = session.legalActionsPayload();
            JsonObject protectorAction = null;
            boolean playerChoice = false;
            for (JsonElement e : legal.getAsJsonArray("actions")) {
                JsonObject meta = e.getAsJsonObject().getAsJsonObject("metadata")
                        .getAsJsonObject("xmage_option_metadata");
                if (meta == null || !meta.has("object_id")) {
                    continue;
                }
                String id = meta.get("object_id").getAsString();
                for (var seat : started.seats().entrySet()) {
                    if (seat.getValue().getId().toString().equals(id)) {
                        playerChoice = true;
                        offeredProtectors.add(seat.getKey());
                        if (seat.getKey().equals(protectorChoice)) {
                            protectorAction = e.getAsJsonObject();
                        }
                    }
                }
            }
            if (playerChoice) {
                assertNotNull(protectorAction, protectorChoice + " is offered as protector");
                XmageFullGameTaxExecutionTest.submit(session, stepTag, protectorAction);
                return true;
            }
            int minimum = session.pendingDecisionPayload().getAsJsonObject("decision")
                    .get("minimum_selections").getAsInt();
            if (minimum == 0) {
                XmageActualCardCorpusTest.chooseNone(started, stepTag);
            } else {
                XmageActualCardCorpusTest.chooseNamed(started, stepTag, "Mountain", minimum);
            }
            return true;
        }

        /** Passes and answers until {@code done}; {@code attacker} attacks the battle if offered. */
        void driveUntil(BooleanSupplier done, String attacker) {
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
                    case "declare_attacker" -> {
                        JsonObject atBattle = attackAt(legal, battle() == null ? null : battle().getId());
                        if (atBattle != null) {
                            battleOfferedTo.add(actor);
                        }
                        XmageFullGameTaxExecutionTest.submit(session, stepTag,
                                actor.equals(attacker) && atBattle != null ? atBattle
                                        : XmageNativeStateRestorationTest.singleActionOfType(
                                                legal, "declare_attackers", "hold_attacker"));
                    }
                    case "declare_blocker" -> XmageActualCardCorpusTest.chooseNone(started, stepTag);
                    default -> {
                        if (!answer(cls, stepTag, new TreeSet<>())) {
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
            session.submitConcede(proposal);
            assertTrue(!started.seats().get(pid).isInGame(), pid + " left the game");
        }

        private static JsonObject attackAt(JsonObject legal, UUID defender) {
            if (defender == null) {
                return null;
            }
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                        .getAsJsonObject("xmage_option_metadata");
                if (meta != null && meta.has("defender_id")
                        && defender.toString().equals(meta.get("defender_id").getAsString())) {
                    return element.getAsJsonObject();
                }
            }
            return null;
        }
    }
}
