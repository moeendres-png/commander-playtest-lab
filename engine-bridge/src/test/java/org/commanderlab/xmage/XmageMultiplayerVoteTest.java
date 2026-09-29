package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.permanent.Permanent;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Will of the council (Council's Judgment) on the XMage full-game lane with
 * actual cards: "Starting with you, each player votes for a nonland permanent
 * you don't control. Exile each permanent with the most votes or tied for
 * most votes." Votes follow the engine's turn order (the engine seats
 * counterclockwise: P1 → P4 → P3 → P2 in 4P) starting with the caster,
 * including when the caster is not P1, and a tie exiles every tied permanent.
 */
class XmageMultiplayerVoteTest {

    /**
     * Casts Council's Judgment for {@code caster}; each voter's choice comes
     * from {@code votes} (pid → permanent name). Returns the voters in order.
     */
    private static List<String> judge(XmageMultiplayerScenario s, String caster,
            Map<String, String> votes) {
        JsonObject cast = s.action("activate_ability", "Cast Council's Judgment");
        assertNotNull(cast, "no cast offer: " + s.actor() + " " + s.decisionClass() + " "
                + s.labels());
        s.submit(cast);
        s.payWith("Plains");
        List<String> voters = new ArrayList<>();
        StringBuilder trace = new StringBuilder();
        for (int i = 0; i < 60; i++) {
            String cls = s.decisionClass();
            if (cls == null) {
                fail("terminal; trace " + trace);
            }
            String actor = s.actor();
            if ("priority".equals(cls) && voters.size() == votes.size()
                    && s.session.restorationGame().getStack().isEmpty()) {
                return voters;
            }
            trace.append(actor).append(':').append(cls).append(' ').append(s.labels()).append('\n');
            JsonObject next;
            if ("priority".equals(cls)) {
                next = s.action("pass_priority", "Pass");
            } else if ("mana_payment".equals(cls)) {
                s.payWith("Plains");
                continue;
            } else {
                voters.add(actor);
                String choice = votes.get(actor);
                assertNotNull(choice, actor + " was not expected to vote; trace\n" + trace);
                next = s.action("choose_targets", choice);
            }
            assertNotNull(next, "no action; trace\n" + trace);
            s.submit(next);
        }
        fail("Council's Judgment did not resolve; trace\n" + trace);
        return voters;
    }

    private static boolean onBattlefield(XmageMultiplayerScenario s, String name) {
        for (Permanent p : s.session.restorationGame().getBattlefield().getAllActivePermanents()) {
            if (p.getName().equals(name)) {
                return true;
            }
        }
        return false;
    }

    private static List<XmageNativeStateRestoration.RequestedObject> board(String caster,
            List<String> others) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj(caster, "Council's Judgment", 0, Zone.HAND));
        for (int i = 0; i < 3; i++) {
            objects.add(XmageMultiplayerScenario.obj(caster, "Plains", i, Zone.BATTLEFIELD));
        }
        String[] creatures = {"Grizzly Bears", "Craw Wurm", "Runeclaw Bear", "Raging Goblin"};
        for (int i = 0; i < others.size(); i++) {
            objects.add(XmageMultiplayerScenario.obj(others.get(i), creatures[i], 0,
                    Zone.BATTLEFIELD));
        }
        return objects;
    }

    @Test
    void fourPlayerVotesRunFromTheCasterInTurnOrderAndATieExilesBoth() {
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("mp-vote-4", 4, "P1",
                board("P1", List.of("P2", "P3", "P4")));
        // P2 Grizzly Bears, P3 Craw Wurm, P4 Runeclaw Bear.
        List<String> voters = judge(s, "P1", Map.of(
                "P1", "Craw Wurm", "P4", "Grizzly Bears",
                "P3", "Craw Wurm", "P2", "Grizzly Bears"));
        assertEquals(List.of("P1", "P4", "P3", "P2"), voters,
                "starting with the caster, then the engine's turn order");
        assertEquals(false, onBattlefield(s, "Craw Wurm"), "tied 2-2: Craw Wurm exiled");
        assertEquals(false, onBattlefield(s, "Grizzly Bears"), "tied 2-2: Grizzly Bears exiled");
        assertEquals(true, onBattlefield(s, "Runeclaw Bear"), "no votes: Runeclaw Bear stays");
    }

    @Test
    void fivePlayerVotesStartWithANonFirstSeatCaster() {
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("mp-vote-5", 5, "P3",
                board("P3", List.of("P1", "P2", "P4", "P5")));
        // P1 Grizzly Bears, P2 Craw Wurm, P4 Runeclaw Bear, P5 Raging Goblin.
        List<String> voters = judge(s, "P3", Map.of(
                "P3", "Raging Goblin", "P2", "Raging Goblin", "P1", "Craw Wurm",
                "P5", "Raging Goblin", "P4", "Craw Wurm"));
        assertEquals(List.of("P3", "P2", "P1", "P5", "P4"), voters,
                "starting with the caster P3, then the engine's turn order");
        assertEquals(false, onBattlefield(s, "Raging Goblin"), "3 votes: exiled");
        assertEquals(true, onBattlefield(s, "Craw Wurm"), "2 votes: stays");
        assertEquals(true, onBattlefield(s, "Grizzly Bears"));
    }
}
