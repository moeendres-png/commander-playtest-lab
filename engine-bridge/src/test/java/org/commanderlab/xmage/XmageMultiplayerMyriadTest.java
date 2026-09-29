package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.game.combat.CombatGroup;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Myriad, a multiplayer-only keyword (CR 702.116a), with an actual card on the
 * full-game lane at 3–6 players.
 *
 * <p>P1's Warchief Giant (Oracle: "Haste. Myriad …", 5/3) attacks P2.</p>
 *
 * <ul>
 *   <li>For each opponent other than the defending player, P1 alone is asked
 *       whether to create a token copy attacking that opponent: once per
 *       opponent, never for P2 or P1.</li>
 *   <li>P1 declines for P3 (at 4P and more) and accepts for the rest. The
 *       tokens attack exactly the accepted opponents.</li>
 *   <li>Unblocked, each attacked opponent takes 5.</li>
 *   <li>The tokens are exiled at end of combat.</li>
 * </ul>
 */
class XmageMultiplayerMyriadTest {

    private static final String GIANT = "Warchief Giant";
    private static final Pattern SEAT = Pattern.compile("Full Game Seat (\\d+)");

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void myriadCopiesAttackEachOtherOpponentAsChosen(int playerCount) {
        String tag = "myriad-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-P1-0-WarchiefGiant", GIANT, "P1", "P1", mage.constants.Zone.BATTLEFIELD, false));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        UUID p2 = started.seats().get("P2").getId();
        boolean declineP3 = playerCount >= 4;

        List<String> offeredFor = new ArrayList<>();
        Map<String, Integer> attackersByDefender = null;
        boolean combatEnded = false;
        for (int step = 0; step < 80 && !combatEnded; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = started.session().legalActionsPayload();
            switch (cls) {
                case "priority" -> {
                    PhaseStep now = game.getStep().getType();
                    if (now == PhaseStep.DECLARE_BLOCKERS && attackersByDefender == null) {
                        attackersByDefender = attackers(game, started);
                    }
                    if (now == PhaseStep.END_TURN || now == PhaseStep.POSTCOMBAT_MAIN) {
                        combatEnded = true;
                        break;
                    }
                    XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                }
                case "declare_attacker" -> {
                    JsonObject atP2 = null;
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                                .getAsJsonObject("xmage_option_metadata");
                        if (meta != null && meta.has("defender_id")
                                && p2.toString().equals(meta.get("defender_id").getAsString())) {
                            atP2 = element.getAsJsonObject();
                        }
                    }
                    XmageFullGameTaxExecutionTest.submit(started.session(), tag + "-attack", atP2);
                }
                case "choose_use" -> {
                    assertEquals("P1", actor, "only the myriad controller decides");
                    String prompt = started.session().pendingDecisionPayload().getAsJsonObject("decision")
                            .get("prompt").getAsString();
                    Matcher matcher = SEAT.matcher(prompt);
                    if (!matcher.find()) {
                        fail("myriad prompt names no player: " + prompt);
                    }
                    String opponent = "P" + matcher.group(1);
                    offeredFor.add(opponent);
                    boolean accept = !(declineP3 && "P3".equals(opponent));
                    XmageActualCardCorpusTest.submit(started, tag + "-myriad-" + opponent,
                            XmageActualCardCorpusTest.labelled(started, accept ? "Yes" : "No"));
                }
                case "declare_blocker" -> XmageActualCardCorpusTest.chooseNone(started, tag + "-nb-" + step);
                default -> fail("unexpected decision " + cls + " for " + actor);
            }
        }
        assertTrue(combatEnded, "combat finished");

        List<String> expectedOffers = new ArrayList<>();
        for (int seat = playerCount; seat >= 3; seat--) {
            expectedOffers.add("P" + seat);
        }
        assertEquals(expectedOffers, offeredFor,
                "one offer per opponent other than the defending player, in turn order");
        Map<String, Integer> expectedAttacks = new TreeMap<>();
        expectedAttacks.put("P2", 1);
        for (int seat = 3; seat <= playerCount; seat++) {
            if (!(declineP3 && seat == 3)) {
                expectedAttacks.put("P" + seat, 1);
            }
        }
        assertEquals(expectedAttacks, attackersByDefender, "a token attacks each accepted opponent");
        for (int seat = 2; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            assertEquals(expectedAttacks.containsKey(pid) ? 35 : 40,
                    started.seats().get(pid).getLife(), pid);
        }
        assertEquals(40, started.seats().get("P1").getLife());
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", GIANT),
                "the tokens were exiled at end of combat; only the original remains");
    }

    private static Map<String, Integer> attackers(Game game, XmageActualCardCorpusTest.Started started) {
        Map<String, Integer> byDefender = new TreeMap<>();
        for (CombatGroup group : game.getCombat().getGroups()) {
            for (UUID attacker : group.getAttackers()) {
                Permanent permanent = game.getPermanent(attacker);
                assertEquals(GIANT, permanent.getName());
                byDefender.merge(XmageNativeStateRestorationTest.pidOf(started.seats(),
                        group.getDefenderId().toString()), 1, Integer::sum);
            }
        }
        return byDefender;
    }
}
