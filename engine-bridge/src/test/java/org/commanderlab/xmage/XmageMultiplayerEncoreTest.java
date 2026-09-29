package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.keyword.HasteAbility;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.game.combat.CombatGroup;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Encore (CR 702.141a) at 3–6 players, with an actual card on the full-game
 * lane.
 *
 * <p>P1 activates the encore ability of Impulsive Pilferer (Oracle: "When
 * Impulsive Pilferer dies, create a Treasure token. Encore {3}{R}") from its
 * graveyard.</p>
 *
 * <ul>
 *   <li>The card is exiled. P1 gets exactly one hasty token copy per opponent.</li>
 *   <li>In combat, the engine declares every token as an attacker. The tokens
 *       attack pairwise-distinct opponents, so every opponent is attacked by
 *       exactly one token, and each opponent takes 1 damage.</li>
 *   <li>At the beginning of the end step, every token is sacrificed. Each
 *       copy's own dies trigger makes a Treasure, so P1 gets N−1 Treasures.</li>
 * </ul>
 */
class XmageMultiplayerEncoreTest {

    private static final String PILFERER = "Impulsive Pilferer";
    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void oneHastyTokenAttacksEachOpponentAndIsSacrificedAtEndStep(int playerCount) {
        String tag = "encore-" + playerCount + "p";
        int opponents = playerCount - 1;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:gy-P1-0-Pilferer", PILFERER, "P1", "P1", mage.constants.Zone.GRAVEYARD, false));
        for (int index = 0; index < 4; index++) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:bf-P1-" + index + "-Mountain", "Mountain", "P1", "P1",
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        Set<UUID> opponentIds = new HashSet<>();
        for (int seat = 2; seat <= playerCount; seat++) {
            opponentIds.add(started.seats().get("P" + seat).getId());
        }

        XmageActualCardCorpusTest.submit(started, tag + "-encore",
                XmageActualCardCorpusTest.labelled(started, PILFERER + " — Encore"));
        XmageActualCardCorpusTest.resolveAll(started, tag + "-activate", MOUNTAIN_LABEL, (cls, step) -> false);

        assertEquals(0, XmageActualCardCorpusTest.inGraveyard(started, "P1", PILFERER));
        assertEquals(1, game.getExile().getCardsOwned(game, started.seats().get("P1").getId()).stream()
                .filter(card -> PILFERER.equals(card.getName())).count(),
                "encore exiles the card as a cost");
        List<Permanent> tokens = tokens(game, started);
        assertEquals(opponents, tokens.size(), "exactly one token copy for each opponent");
        for (Permanent token : tokens) {
            assertTrue(token.hasAbility(HasteAbility.getInstance(), game), "encore tokens gain haste");
        }

        boolean combatChecked = false;
        List<String> trace = new ArrayList<>();
        for (int step = 0; step < 200 && game.getTurnNum() == 1; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            trace.add(step + " " + game.getStep().getType() + " " + actor + " " + cls);
            if (!combatChecked && game.getStep().getType() == PhaseStep.DECLARE_BLOCKERS) {
                combatChecked = true;
                List<CombatGroup> groups = game.getCombat().getGroups();
                assertEquals(opponents, groups.size(), "every token attacks: " + trace);
                Set<UUID> defenders = new HashSet<>();
                for (CombatGroup group : groups) {
                    assertEquals(1, group.getAttackers().size(), "one token per attacked opponent");
                    assertTrue(tokens.stream().anyMatch(token -> token.getId().equals(group.getAttackers().get(0))),
                            "only encore tokens attack");
                    defenders.add(group.getDefenderId());
                }
                assertEquals(opponentIds, defenders,
                        "the tokens attack pairwise-distinct opponents, covering every opponent");
            }
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                case "trigger_order" -> {
                    // N−1 identical dies triggers from identical token copies: an explicit,
                    // id-scripted order (all orders are rules-equivalent here).
                    assertEquals(PhaseStep.END_TURN, game.getStep().getType());
                    JsonObject first = null;
                    String firstSource = null;
                    for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
                        JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
                        assertTrue(meta.get("label").getAsString().startsWith(PILFERER + " — When {this} dies"),
                                meta.get("label").getAsString());
                        String source = meta.getAsJsonObject("xmage_option_metadata")
                                .get("source_object_id").getAsString();
                        if (firstSource == null || source.compareTo(firstSource) < 0) {
                            firstSource = source;
                            first = element.getAsJsonObject();
                        }
                    }
                    XmageActualCardCorpusTest.submit(started, tag + "-order-" + step, first);
                }
                case "choose_object" -> {
                    // Cleanup hand-size discard (opening hand plus the arrival draw).
                    assertEquals(PhaseStep.CLEANUP, game.getStep().getType());
                    XmageActualCardCorpusTest.chooseByExactName(started, tag + "-discard-" + step, "Mountain", 1);
                }
                default -> fail("[" + tag + "] unexpected " + cls + " for " + actor + " at "
                        + game.getStep().getType() + " prompt=" + started.session().pendingDecisionPayload()
                                .getAsJsonObject("decision").get("prompt"));
            }
        }
        assertTrue(combatChecked, "combat reached: " + trace);
        assertEquals(2, game.getTurnNum(), "turn 1 finished: " + trace);
        assertEquals(40, started.seats().get("P1").getLife());
        for (UUID opponent : opponentIds) {
            assertEquals(39, game.getPlayer(opponent).getLife(), "each opponent took exactly 1 combat damage");
        }
        assertEquals(0, tokens(game, started).size(), "every encore token was sacrificed at the end step");
        assertEquals(opponents, XmageActualCardCorpusTest.onBattlefield(started, "P1", "Treasure Token"),
                "each sacrificed copy's own dies trigger made a Treasure");
    }

    private static List<Permanent> tokens(Game game, XmageActualCardCorpusTest.Started started) {
        List<Permanent> tokens = new ArrayList<>();
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(started.seats().get("P1").getId())) {
            if (PILFERER.equals(permanent.getName())) {
                assertTrue(permanent instanceof mage.game.permanent.PermanentToken, "only token copies exist");
                tokens.add(permanent);
            }
        }
        tokens.sort(Comparator.comparing(permanent -> permanent.getId().toString()));
        return tokens;
    }
}
