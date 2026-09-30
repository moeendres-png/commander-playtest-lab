package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * CR 701.38a with an actual card at 3–6 players on the full-game lane.
 *
 * <p>Council's Judgment (Oracle: "Will of the council — Starting with you, each
 * player votes for a nonland permanent you don't control. Exile each
 * permanent with the most votes or tied for most votes."). P1 casts it.
 * P1 and every opponent control a Grizzly Bears.</p>
 *
 * <ul>
 *   <li>Every player votes through the external decision surface, starting
 *       with P1 and proceeding in the engine's turn order: P1, P2, …, PN.</li>
 *   <li>"You" is P1 for every voter, so no voter is offered P1's Bears.</li>
 *   <li>Every voter except P2 votes for P2's Bears; P2 votes for P3's. So
 *       P2's Bears has N−1 votes, P3's has 1, and only P2's Bears is
 *       exiled.</li>
 * </ul>
 */
class XmageMultiplayerVotingTest {

    private static final String JUDGMENT = "Council's Judgment";
    private static final String BEARS = "Grizzly Bears";
    private static final String PLAINS_LABEL = "Plains — {T}: Add {W}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void everyPlayerVotesInTurnOrderStartingWithTheCaster(int playerCount) {
        String tag = "council-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:hand-P1-0-CouncilsJudgment", JUDGMENT, "P1", "P1",
                mage.constants.Zone.HAND, false));
        for (int index = 0; index < 3; index++) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:bf-P1-" + index + "-Plains", "Plains", "P1", "P1",
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        for (int seat = 1; seat <= playerCount; seat++) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:bf-P" + seat + "-0-Bears", BEARS, "P" + seat, "P" + seat,
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        UUID p2Bears = bearsOf(game, started, "P2").getId();
        UUID p3Bears = bearsOf(game, started, "P3").getId();

        XmageActualCardCorpusTest.cast(started, tag + "-cast", JUDGMENT);
        List<String> voters = new ArrayList<>();
        XmageActualCardCorpusTest.resolveAll(started, tag, PLAINS_LABEL, (cls, step) -> {
            if (!"choose_object".equals(cls) && !"target".equals(cls)) {
                return false;
            }
            String voter = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = started.session().legalActionsPayload();
            List<String> candidates = new ArrayList<>();
            JsonObject vote = null;
            UUID wanted = "P2".equals(voter) ? p3Bears : p2Bears;
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject engine = element.getAsJsonObject().getAsJsonObject("metadata")
                        .getAsJsonObject("xmage_option_metadata");
                assertNotNull(engine, "vote options carry engine metadata");
                Permanent candidate = game.getPermanent(
                        UUID.fromString(engine.get("object_id").getAsString()));
                assertNotNull(candidate, "candidates are permanents");
                candidates.add(XmageNativeStateRestorationTest.pidOf(started.seats(),
                        candidate.getControllerId().toString()));
                if (candidate.getId().equals(wanted)) {
                    vote = element.getAsJsonObject();
                }
            }
            java.util.Collections.sort(candidates);
            List<String> opponents = new ArrayList<>();
            for (int seat = 2; seat <= playerCount; seat++) {
                opponents.add("P" + seat);
            }
            java.util.Collections.sort(opponents);
            assertEquals(opponents, candidates,
                    voter + " may vote only for nonland permanents P1 doesn't control");
            assertNotNull(vote, voter + " must be able to vote as planned");
            voters.add(voter);
            submitSingle(started.session(), tag + "-vote-" + voter, vote);
            return true;
        });

        List<String> expectedOrder = new ArrayList<>();
        expectedOrder.add("P1");
        for (int seat = 2; seat <= playerCount; seat++) {
            expectedOrder.add("P" + seat);
        }
        assertEquals(expectedOrder, voters,
                "CR 701.38a: starting with the caster, then turn order; every player votes");
        assertTrue(game.getPermanent(p2Bears) == null, "P2's Bears had the most votes: exiled");
        assertEquals(1, game.getExile().getAllCards(game).stream()
                .filter(card -> card.getId().equals(p2Bears)
                        || card.getName().equals(BEARS)).count(),
                "exactly one Bears is exiled");
        assertNotNull(game.getPermanent(p3Bears), "P3's Bears had one vote and stays");
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", BEARS));
    }

    private static Permanent bearsOf(Game game, XmageActualCardCorpusTest.Started started,
            String pid) {
        for (Permanent permanent : game.getBattlefield()
                .getAllActivePermanents(started.seats().get(pid).getId())) {
            if (BEARS.equals(permanent.getName())) {
                return permanent;
            }
        }
        throw new AssertionError(pid + " Bears");
    }

    private static void submitSingle(XmageFullGameSession session, String tag, JsonObject action) {
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        String optionId = action.getAsJsonObject("metadata").get("option_id").getAsString();
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", decisionId + ":" + optionId);
        proposal.addProperty("action_type", action.get("action_type").getAsString());
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        JsonArray selected = new JsonArray();
        selected.add(optionId);
        choices.add("selected_option_ids", selected);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = session.submitAction(proposal);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());
    }
}
