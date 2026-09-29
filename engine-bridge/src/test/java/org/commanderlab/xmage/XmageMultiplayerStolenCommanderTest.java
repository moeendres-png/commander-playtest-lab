package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * CR 903.10a: combat damage dealt by a commander counts as that commander's
 * damage whoever controls it, with actual cards at 4P through 6P on the
 * full-game lane.
 *
 * <p>P1 casts its commander Rograkh, Son of Rohgahh. On turn 2 (PN's turn) PN
 * casts Act of Treason ("Gain control of target creature until end of turn.
 * Untap that creature. It gains haste until end of turn.") on it, then Brute
 * Force (+3/+3), and attacks P3. P3 takes 3 damage, and every principal and the
 * public view record it as 3 commander damage from P1's commander, not from
 * PN's. Coverage: correct on pin {@code f79e4168}.</p>
 */
class XmageMultiplayerStolenCommanderTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5, 6})
    void aStolenCommandersDamageStaysItsOwnersCommanderDamage(int playerCount) {
        String thief = "P" + playerCount;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj(thief, "Act of Treason", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj(thief, "Brute Force", 1, Zone.HAND));
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj(thief, "Mountain", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("stolen-cmd-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        boolean castCommander = false;
        boolean treason = false;
        boolean force = false;
        for (int i = 0; i < 300 && !(game.getTurnNum() == 2 && game.getStep().getType() == PhaseStep.END_COMBAT); i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            boolean thiefMain = game.getTurnNum() == 2 && thief.equals(actor)
                    && game.getStep().getType() == PhaseStep.PRECOMBAT_MAIN && game.getStack().isEmpty();
            JsonObject decision = s.session.pendingDecisionPayload().getAsJsonObject("decision");
            switch (cls) {
                case "priority" -> {
                    if (!castCommander && "P1".equals(actor)) {
                        s.submit(s.action("activate_ability", "Cast Rograkh"));
                        castCommander = true;
                    } else if (thiefMain && !treason) {
                        s.submit(s.action("activate_ability", "Cast Act of Treason"));
                        treason = true;
                    } else if (thiefMain && !force) {
                        s.submit(s.action("activate_ability", "Cast Brute Force"));
                        force = true;
                    } else {
                        s.submit(s.action("pass_priority", "Pass"));
                    }
                }
                case "mana_payment" -> s.payWith("Mountain");
                case "target" -> s.submit(s.action("choose_targets", "Rograkh"));
                case "declare_attacker" -> s.submit(game.getTurnNum() == 1
                        ? labelled(s, "Do not attack") : attackAt(s, "P3"));
                case "declare_blocker" -> s.submit(labelled(s, "No"));
                case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "d" + i, "Mountain",
                        decision.get("minimum_selections").getAsInt());
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        assertEquals(PhaseStep.END_COMBAT, game.getStep().getType(), "reached end of PN's combat");
        Permanent rograkh = game.getBattlefield().getAllActivePermanents().stream()
                .filter(p -> p.getName().startsWith("Rograkh")).findFirst().orElseThrow();
        assertEquals(s.seats.get(thief).getId(), rograkh.getControllerId(), "control: PN controls it");
        assertEquals(s.seats.get("P1").getId(), rograkh.getOwnerId(), "control: P1 owns it");

        Map<String, Integer> life = new TreeMap<>();
        s.seats.forEach((pid, player) -> life.put(pid, player.getLife()));
        Map<String, Integer> expected = new TreeMap<>();
        s.seats.keySet().forEach(pid -> expected.put(pid, "P3".equals(pid) ? 37 : 40));
        assertEquals(expected, life, "only P3 was dealt the 3 combat damage");

        int p1Seat = XmageFullGameStateRedactor.seat(game, s.seats.get("P1").getId());
        int thiefSeat = XmageFullGameStateRedactor.seat(game, s.seats.get(thief).getId());
        List<JsonObject> views = new ArrayList<>();
        s.seats.values().forEach(player -> views.add(XmageFullGameStateRedactor.actorView(game, player)));
        views.add(XmageFullGameStateRedactor.publicView(game));
        for (JsonObject view : views) {
            JsonObject p1 = commanderOf(view, p1Seat);
            assertEquals(1, p1.getAsJsonArray("commander_damage_to_player").size(), view.get("commander_status").toString());
            assertEquals(3, p1.getAsJsonArray("commander_damage_to_player").get(0).getAsJsonObject()
                    .get("total").getAsInt(), "3 commander damage from P1's commander");
            assertTrue(commanderOf(view, thiefSeat).getAsJsonArray("commander_damage_to_player").isEmpty(),
                    "none from the controller's own commander");
        }
    }

    /** The commander_status entry of the given seat; entries are in seat order and owner ids are redacted per viewer. */
    private static JsonObject commanderOf(JsonObject view, int seat) {
        return view.getAsJsonArray("commander_status").get(seat).getAsJsonObject();
    }

    private static JsonObject attackAt(XmageMultiplayerScenario s, String pid) {
        for (JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject meta = e.getAsJsonObject().getAsJsonObject("metadata").getAsJsonObject("xmage_option_metadata");
            if (meta != null && meta.has("defender_id")
                    && s.seats.get(pid).getId().toString().equals(meta.get("defender_id").getAsString())) {
                return e.getAsJsonObject();
            }
        }
        fail("no attack at " + pid + ": " + s.labels());
        return null;
    }

    private static JsonObject labelled(XmageMultiplayerScenario s, String part) {
        for (JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            if (e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString().contains(part)) {
                return e.getAsJsonObject();
            }
        }
        fail("no " + part + " in " + s.labels());
        return null;
    }
}
