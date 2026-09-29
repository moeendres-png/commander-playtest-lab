package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * CR 800.4a with actual cards at 3–6 players on the full-game lane: when a
 * player leaves the game, effects that give that player control of objects end
 * and the objects that player owns leave the game.
 *
 * <p>P1 casts Control Magic (Oracle: "Enchant creature / You control enchanted
 * creature.") on P2's Grizzly Bears, then P1 concedes. The Bears stay on the
 * battlefield under P2's control; P1's Control Magic is gone.</p>
 */
class XmageMultiplayerLeaverControlTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void stolenCreatureReturnsToItsOwnerWhenTheThiefLeaves(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Control Magic", 0, Zone.HAND));
        for (int i = 0; i < 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", i, Zone.BATTLEFIELD));
        }
        objects.add(XmageMultiplayerScenario.obj("P2", "Grizzly Bears", 0, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "leaver-control-" + playerCount + "p", playerCount, "P1", objects);

        s.submit(s.action("activate_ability", "Cast Control Magic"));
        for (int i = 0; i < 40 && !"priority".equals(s.decisionClass())
                || i < 40 && !s.session.restorationGame().getStack().isEmpty(); i++) {
            String cls = s.decisionClass();
            if ("mana_payment".equals(cls)) {
                s.payWith("Island");
            } else if ("target".equals(cls) || "choose_object".equals(cls)) {
                s.submit(s.action("choose_targets", "Grizzly Bears"));
            } else {
                s.submit(s.action("pass_priority", "Pass"));
            }
        }
        Permanent bears = bears(s);
        assertNotNull(bears);
        assertEquals(s.seats.get("P1").getId(), bears.getControllerId(), "Control Magic gave P1 the Bears");

        String p1 = s.seats.get("P1").getId().toString();
        JsonObject concede = new JsonObject();
        concede.addProperty("proposal_id", "leaver-control-concede");
        concede.addProperty("actor_id", p1);
        concede.addProperty("player_id", p1);
        s.session.submitConcede(concede);
        assertTrue(!s.seats.get("P1").isInGame(), "P1 left the game");

        bears = bears(s);
        assertNotNull(bears, "P2's Bears stay on the battlefield");
        assertEquals(s.seats.get("P2").getId(), bears.getControllerId(),
                "800.4a: the leaver's control effect ended");
        assertNull(s.session.restorationGame().getBattlefield().getAllActivePermanents().stream()
                .filter(p -> "Control Magic".equals(p.getName())).findFirst().orElse(null),
                "the leaver's Aura left the game");
    }

    private static Permanent bears(XmageMultiplayerScenario s) {
        return s.session.restorationGame().getBattlefield().getAllActivePermanents().stream()
                .filter(p -> "Grizzly Bears".equals(p.getName())).findFirst().orElse(null);
    }
}
