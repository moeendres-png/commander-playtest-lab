package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.CommanderCardType;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.players.Player;
import mage.watchers.common.CommanderInfoWatcher;
import mage.watchers.common.CommanderPlaysCountWatcher;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Commander ninjutsu from the command zone at 4P and 5P on the full-game lane.
 *
 * <p>Yuriko, the Tiger's Shadow (Oracle): "Commander ninjutsu {U}{B} ({U}{B},
 * Return an unblocked attacker you control to hand: Put this card onto the
 * battlefield from your hand or the command zone tapped and attacking.)
 * Whenever a Ninja you control deals combat damage to a player, reveal the top
 * card of your library and put that card into your hand. Each opponent loses
 * life equal to that card's mana value."</p>
 *
 * <ul>
 *   <li>Yuriko enters from the command zone tapped and attacking the player the
 *       returned creature was attacking (702.49c), P3.</li>
 *   <li>It was put onto the battlefield, not cast: the commander tax counts
 *       only casts from the command zone (903.8), so the cast count stays 0.</li>
 *   <li>Its 1 combat damage to P3 is commander damage (903.10a); the revealed
 *       Island has mana value 0, so no opponent loses life to the trigger.</li>
 * </ul>
 */
class XmageMultiplayerCommanderNinjutsuTest {

    private static final String YURIKO = "Yuriko, the Tiger's Shadow";
    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";
    private static final String BEARS = "Grizzly Bears";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void commanderNinjutsuFromTheCommandZoneIsNotACast(int playerCount) {
        String tag = "cmd-ninjutsu-" + playerCount + "p";
        XmageActualCardCorpusTest.Started started = start(tag, playerCount);
        Game game = started.session().restorationGame();
        Player p1 = started.seats().get("P1");
        UUID p3 = started.seats().get("P3").getId();
        UUID yurikoId = commanderId(game, p1);
        CommanderPlaysCountWatcher plays = game.getState().getWatcher(CommanderPlaysCountWatcher.class);
        assertNotNull(plays, "native commander cast-count watcher");
        assertEquals(0, plays.getPlaysCount(yurikoId), "control: Yuriko not cast yet");

        List<String> askedToBlock = new ArrayList<>();
        boolean activated = false;
        boolean snapshot = false;
        for (int step = 0; step < 200 && game.getStep().getType() != PhaseStep.END_COMBAT; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = started.session().legalActionsPayload();
            PhaseStep phaseStep = game.getStep().getType();
            switch (cls) {
                case "priority" -> {
                    JsonObject ninjutsu = labelContaining(legal, YURIKO, "injutsu");
                    if (!activated && "P1".equals(actor) && phaseStep == PhaseStep.DECLARE_BLOCKERS) {
                        assertNotNull(ninjutsu, "commander ninjutsu offered from the command zone: " + labels(legal));
                        activated = true;
                        XmageActualCardCorpusTest.submit(started, tag + "-ninjutsu", ninjutsu);
                    } else {
                        XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                    }
                }
                case "declare_attacker" -> XmageActualCardCorpusTest.submit(started, tag + "-attack",
                        attackOption(legal, p3));
                case "declare_blocker" -> {
                    askedToBlock.add(actor);
                    XmageActualCardCorpusTest.chooseNone(started, tag + "-noblock-" + actor);
                }
                case "target", "choose_object" -> {
                    assertEquals("P1", actor);
                    XmageActualCardCorpusTest.chooseByExactName(started, tag + "-return", BEARS, 1);
                }
                case "mana_payment" -> XmageActualCardCorpusTest.payOneFromRestoredMana(started,
                        tag + "-pay-" + step, List.of("Island", "Swamp"),
                        Set.of("Island — {T}: Add {U}.", "Swamp — {T}: Add {B}."));
                default -> fail("[" + tag + "] unexpected " + cls + " for " + actor + " at " + phaseStep
                        + " " + labels(legal));
            }
            Permanent yuriko = game.getPermanent(yurikoId);
            if (!snapshot && activated && yuriko != null && phaseStep == PhaseStep.DECLARE_BLOCKERS
                    && game.getStack().isEmpty()) {
                snapshot = true;
                assertTrue(yuriko.isAttacking() && yuriko.isTapped(), "Yuriko enters tapped and attacking");
                assertEquals(p3, game.getCombat().getDefenderId(yuriko.getId()),
                        "702.49c: Yuriko attacks the player the returned Bears was attacking");
                assertFalse(game.getCombat().findGroup(yuriko.getId()).getBlocked(), "Yuriko is unblocked");
            }
        }
        assertTrue(activated, "control: commander ninjutsu was activated");
        assertTrue(snapshot, "control: Yuriko was on the battlefield attacking before damage");
        assertEquals(List.of("P3"), askedToBlock, "only the attacked player is asked to block");
        assertEquals(1, p1.getHand().getCards(game).stream().filter(c -> BEARS.equals(c.getName())).count(),
                "the Bears returned to hand as the cost");
        assertEquals(0, plays.getPlaysCount(yurikoId),
                "903.8: commander ninjutsu is not a cast; the command-zone cast count stays 0");
        CommanderInfoWatcher damage = game.getState().getWatcher(CommanderInfoWatcher.class, yurikoId);
        assertNotNull(damage, "native commander damage watcher for Yuriko");
        assertEquals(1, damage.getDamageToPlayer().getOrDefault(p3, 0), "903.10a: 1 commander damage to P3");
        assertEquals(39, started.seats().get("P3").getLife(), "P3 took Yuriko's 1 combat damage");
        for (int seat = 2; seat <= playerCount; seat++) {
            if (seat != 3) {
                assertEquals(40, started.seats().get("P" + seat).getLife(),
                        "the revealed Island has mana value 0: P" + seat + " loses nothing");
            }
        }
    }

    private static XmageActualCardCorpusTest.Started start(String tag, int playerCount) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", seat == 1 ? YURIKO : ROGRAKH, pid, 0));
        }
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>(List.of(
                obj("P1", "Island", 0), obj("P1", "Swamp", 1), obj("P1", BEARS, 2)));
        for (int seat = 2; seat <= playerCount; seat++) {
            // Every opponent could block, so being asked depends only on being attacked.
            objects.add(obj("P" + seat, "Wall of Stone", 0));
        }
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                tag, playerCount, 424242L, List.copyOf(players), List.copyOf(commanders), List.copyOf(objects),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN, PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration = XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            List<String> mainboard = new ArrayList<>();
            for (int index = 0; index < 99; index++) {
                mainboard.add(seat == 1 ? "Island" : "Mountain");
            }
            handles.add(importer.importCommanderDeck(tag + "-P" + seat, tag + "-hash", mainboard,
                    List.of(seat == 1 ? YURIKO : ROGRAKH)).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new XmageActualCardCorpusTest.Started(session, seats, restoration);
    }

    private static XmageNativeStateRestoration.RequestedObject obj(String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, mage.constants.Zone.BATTLEFIELD, false);
    }

    private static UUID commanderId(Game game, Player owner) {
        for (UUID id : game.getCommandersIds(owner, CommanderCardType.COMMANDER_OR_OATHBREAKER, false)) {
            if (YURIKO.equals(game.getCard(id).getName())) {
                return id;
            }
        }
        throw new AssertionError("Yuriko is P1's commander");
    }

    private static JsonObject labelContaining(JsonObject legal, String a, String b) {
        for (JsonElement e : legal.getAsJsonArray("actions")) {
            String label = e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString();
            if (label.contains(a) && label.contains(b)) {
                return e.getAsJsonObject();
            }
        }
        return null;
    }

    private static List<String> labels(JsonObject legal) {
        List<String> out = new ArrayList<>();
        for (JsonElement e : legal.getAsJsonArray("actions")) {
            out.add(e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString());
        }
        return out;
    }

    /** The declare-attacker option whose engine metadata names {@code defender}. */
    private static JsonObject attackOption(JsonObject legal, UUID defender) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta != null && meta.has("defender_id")
                    && defender.toString().equals(meta.get("defender_id").getAsString())) {
                return element.getAsJsonObject();
            }
        }
        fail("attack at " + defender + " not offered: " + labels(legal));
        return null;
    }
}
