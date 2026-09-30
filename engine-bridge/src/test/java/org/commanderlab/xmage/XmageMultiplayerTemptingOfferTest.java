package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Tempting offer ("each opponent may …") at 3–6 players, with an actual card on
 * the full-game lane.
 *
 * <p>PN, active on the last turn of the first round (turns run in seat
 * order, F-41), casts Tempt with Discovery. Oracle: "Search your library for
 * a land card and put it onto the battlefield. Each opponent may search their
 * library for a land card and put it onto the battlefield. For each opponent who
 * searches a library this way, search your library for a land card and put it
 * onto the battlefield. Then each player who searched a library this way
 * shuffles." Every opponent accepts.</p>
 *
 * <ul>
 *   <li>Now: every opponent is asked exactly once, through the external
 *       surface. Every search is honoured, and the caster searches once more per
 *       opponent who searched.</li>
 *   <li><b>F-21</b> (tracker #328, engine fix moeendres-png/mage#22; pinned and upstream): the opponents should be asked
 *       in APNAP order (101.4), i.e. P(N−1), …, P1 from the active caster.
 *       {@code Game.getOpponents()} iterates the turn-order list from its
 *       <i>current pointer</i>, not from the active player, so at 4P the order
 *       observed is P1, P3, P2. fixed in the XMage multiplayer candidate f79e4168 (moeendres-png/mage#24) and enabled by the 2026-09-29 successor repin.</li>
 * </ul>
 */
class XmageMultiplayerTemptingOfferTest {

    private static final String TEMPT = "Tempt with Discovery";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void everyOpponentIsOfferedOnceAndEverySearchIsHonoured(int playerCount) {
        Run run = run(playerCount);
        List<String> opponents = new ArrayList<>();
        for (int seat = 1; seat < playerCount; seat++) {
            opponents.add("P" + seat);
        }
        assertEquals(new HashSet<>(opponents), new HashSet<>(run.offered),
                "every opponent is offered: " + run.offered);
        assertEquals(opponents.size(), run.offered.size(), "each exactly once: " + run.offered);
        for (String opponent : opponents) {
            assertEquals(1, run.landsOf(opponent), opponent + " searched out one land");
        }
        assertEquals(1 + opponents.size(), run.landsOf("P" + playerCount),
                "the caster searched once, plus once per opponent who searched");
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void opponentsAreOfferedInApnapOrder(int playerCount) {
        List<String> apnap = new ArrayList<>();
        for (int seat = 1; seat <= playerCount - 1; seat++) {
            apnap.add("P" + seat);
        }
        assertEquals(apnap, run(playerCount).offered, "CR 101.4 from the active caster");
    }

    private record Run(List<String> offered, XmageActualCardCorpusTest.Started started) {
        int landsOf(String pid) {
            return XmageActualCardCorpusTest.onBattlefield(started, pid, "Mountain");
        }
    }

    private static Run run(int playerCount) {
        String tag = "tempt-" + playerCount + "p";
        String caster = "P" + playerCount;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:hand-" + caster + "-0-Tempt", TEMPT, caster, caster,
                mage.constants.Zone.HAND, false));
        for (int index = 0; index < 4; index++) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:bf-" + caster + "-" + index + "-Forest", "Forest", caster, caster,
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        UUID casterId = started.seats().get(caster).getId();
        boolean cast = false;
        List<String> offered = new ArrayList<>();
        for (int step = 0; step < 400; step++) {
            JsonObject decision = started.session().pendingDecisionPayload()
                    .getAsJsonObject("decision");
            String cls = decision.get("decision_class").getAsString();
            String actor = XmageActualCardCorpusTest.actorPid(started);
            if ("priority".equals(cls) && !cast && casterId.equals(game.getActivePlayerId())
                    && game.getStep().getType() == PhaseStep.PRECOMBAT_MAIN
                    && caster.equals(actor)) {
                XmageActualCardCorpusTest.cast(started, tag + "-cast", TEMPT);
                cast = true;
                continue;
            }
            if ("priority".equals(cls) && cast && game.getStack().isEmpty()) {
                break;
            }
            String prompt = decision.get("prompt").getAsString().toLowerCase(Locale.ROOT);
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                case "mana_payment" -> XmageActualCardCorpusTest.payOneFromRestoredMana(started,
                        tag + "-pay-" + step, List.of("Forest"), Set.of("Forest — {T}: Add {G}."));
                case "choose_use" -> {
                    if (!prompt.startsWith("search your library for a land")) {
                        fail("unexpected yes/no question: " + prompt);
                    }
                    offered.add(actor);
                    XmageActualCardCorpusTest.submit(started, tag + "-use-" + step,
                            XmageActualCardCorpusTest.labelled(started, "Yes"));
                }
                case "choose_object", "target" -> XmageActualCardCorpusTest.chooseNamed(started,
                        tag + "-pick-" + step, "Mountain",
                        Math.max(1, decision.get("minimum_selections").getAsInt()));
                default -> fail("unexpected decision " + cls + " for " + actor + ": " + prompt);
            }
        }
        if (!cast) {
            fail(caster + " never got to cast " + TEMPT);
        }
        return new Run(offered, started);
    }
}
