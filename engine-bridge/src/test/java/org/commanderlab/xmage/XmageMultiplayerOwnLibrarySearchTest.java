package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.Zone;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Two players search their own libraries at 4P and 5P: each search frame is
 * addressed to the searcher, offers only that searcher's library, and no other
 * principal's view carries the searched library's identities.
 *
 * <p>Scheming Symmetry (Oracle): "Choose two target players. Each of them
 * searches their library for a card, then shuffles and puts that card on top."
 * A library is hidden (CR 401.2); searching lets only the searcher look at it
 * (701.19a). P2's and P3's libraries each hold three marker artifacts that
 * exist nowhere else, so a leak of one searcher's library into another
 * principal's frame or view is visible by name.</p>
 */
class XmageMultiplayerOwnLibrarySearchTest {

    private static final List<String> P2_MARKERS = List.of("Sol Ring", "Mind Stone", "Fellwar Stone");
    private static final List<String> P3_MARKERS = List.of("Arcane Signet", "Thought Vessel", "Wayfarer's Bauble");

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void eachSearcherSeesOnlyItsOwnLibraryAndNobodyElseSeesIt(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Scheming Symmetry", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Swamp", 1, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("symmetry-" + playerCount + "p",
                playerCount, "P1", objects, Map.of("P2", P2_MARKERS, "P3", P3_MARKERS));
        Game game = s.session.restorationGame();

        s.submit(s.action("activate_ability", "Cast Scheming Symmetry"));
        List<String> targetsChosen = new ArrayList<>();
        List<String> searchers = new ArrayList<>();
        java.util.Map<String, String> chosen = new java.util.HashMap<>();
        boolean cast = false;
        for (int i = 0; i < 120; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            String cls = s.decisionClass();
            String actor = s.actor();
            if ("priority".equals(cls) && game.getStack().isEmpty() && cast) {
                break;
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("Swamp");
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "target", "choose_object" -> {
                    if ("P1".equals(actor) && targetsChosen.isEmpty()) {
                        cast = true;
                        targetsChosen.add(actor);
                        selectLabels(s, "targets", List.of("Seat 2", "Seat 3"));
                        continue;
                    }
                    searchers.add(actor);
                    List<String> own = "P2".equals(actor) ? P2_MARKERS : P3_MARKERS;
                    List<String> foreign = "P2".equals(actor) ? P3_MARKERS : P2_MARKERS;
                    Set<String> offered = offeredNames(s);
                    Set<String> library = libraryNames(game, s.seats.get(actor));
                    assertTrue(library.containsAll(offered),
                            "701.19a: " + actor + " is offered only cards of its own library: " + offered);
                    for (String name : foreign) {
                        assertFalse(offered.contains(name), actor + " is offered the other searcher's " + name);
                    }
                    for (String pid : s.seats.keySet()) {
                        if (pid.equals(actor)) {
                            continue;
                        }
                        String view = XmageFullGameStateRedactor.actorView(game, s.seats.get(pid)).toString();
                        for (String name : own) {
                            if (library.contains(name)) {
                                assertFalse(view.contains(name), "401.2: " + pid + "'s view names " + name
                                        + " from " + actor + "'s library during its search");
                            }
                        }
                    }
                    String take = own.stream().filter(library::contains).findFirst().orElse(null);
                    if (take == null) {
                        fail("control: every marker of " + actor + " was drawn; offered " + offered);
                    }
                    chosen.put(actor, take);
                    selectLabels(s, "search-" + actor, List.of(take));
                }
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels() + " " + s.prompt());
            }
        }
        assertEquals(Set.of("P2", "P3"), new HashSet<>(searchers), "each target searches, and only they do");
        for (Map.Entry<String, String> e : chosen.entrySet()) {
            Player searcher = s.seats.get(e.getKey());
            assertEquals(e.getValue(), searcher.getLibrary().getFromTop(game).getName(),
                    e.getKey() + " put the card it found on top");
            for (String pid : s.seats.keySet()) {
                if (pid.equals(e.getKey())) {
                    continue;
                }
                String view = XmageFullGameStateRedactor.actorView(game, s.seats.get(pid)).toString();
                assertFalse(view.contains(e.getValue()),
                        "401.2: " + pid + " does not learn the card " + e.getKey() + " put on top");
            }
        }
    }

    private static Set<String> libraryNames(Game game, Player player) {
        Set<String> names = new HashSet<>();
        for (Card card : player.getLibrary().getCards(game)) {
            names.add(card.getName());
        }
        return names;
    }

    private static Set<String> offeredNames(XmageMultiplayerScenario s) {
        Set<String> names = new HashSet<>();
        for (JsonElement element : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
            JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
            names.add(engine != null && engine.has("name") ? engine.get("name").getAsString()
                    : meta.get("label").getAsString());
        }
        return names;
    }

    /** Selects, for each wanted name or seat label, the single offered option carrying it. */
    private static void selectLabels(XmageMultiplayerScenario s, String tag, List<String> wanted) {
        JsonObject pending = s.session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = s.session.legalActionsPayload();
        JsonArray selected = new JsonArray();
        for (String name : wanted) {
            List<String> matching = new ArrayList<>();
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
                JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
                String optionName = engine != null && engine.has("name") ? engine.get("name").getAsString()
                        : meta.get("label").getAsString();
                if (name.equals(optionName) || meta.get("label").getAsString().contains(name)) {
                    matching.add(meta.get("option_id").getAsString());
                }
            }
            assertEquals(1, matching.size(), "exactly one " + name + " offered: " + s.labels());
            selected.add(matching.get(0));
        }
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", decisionId + ":" + selected.get(0).getAsString());
        proposal.addProperty("action_type", "choose_targets");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", selected);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = s.session.submitAction(proposal);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());
    }

    private static JsonObject pick(XmageMultiplayerScenario s, String labelPart) {
        for (JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            String label = e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString();
            if (label.equals(labelPart) || label.contains(labelPart)) {
                return e.getAsJsonObject();
            }
        }
        fail("no option " + labelPart + " in " + s.labels());
        return null;
    }
}
