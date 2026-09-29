package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Multiplayer hidden information and Rules RNG with actual cards on the
 * full-game lane.
 *
 * <ul>
 *   <li>Delirium Skeins (Oracle: "Each player discards three cards."), 3–6P:
 *       every player chooses their own discards through the external surface,
 *       in APNAP order (101.4), in the engine's turn order P1, PN, …, P2. Each
 *       discard decision offers only the actor's own hand. No decision's
 *       serialized payload or legal actions carry any card identity from
 *       another player's hand or library (AGENTS.md §5).</li>
 *   <li>Burning Inquiry (Oracle: "Each player draws three cards, then
 *       discards three cards at random."), 4P and 5P: the random discards are
 *       Rules randomness. Two runs with the same explicit seed discard exactly
 *       the same cards for every player, and no pilot decision is invented for
 *       a random discard.</li>
 * </ul>
 */
class XmageMultiplayerHiddenDiscardTest {

    private static final String SKEINS = "Delirium Skeins";
    private static final String INQUIRY = "Burning Inquiry";
    private static final String SWAMP_LABEL = "Swamp — {T}: Add {B}.";
    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";
    /** Distinct names so every hand and every discard is identifiable. */
    private static final List<String> HAND = List.of(
            "Grizzly Bears", "Lightning Bolt", "Shock", "Giant Growth", "Counterspell");

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void eachPlayerChoosesDiscardsFromTheirOwnHandWithoutSeeingOthers(int playerCount) {
        String tag = "skeins-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects =
                handsAndSpell(playerCount, SKEINS, "Swamp", 3);
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();
        Map<String, Integer> handBefore = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> handBefore.put(pid, player.getHand().size()));

        XmageActualCardCorpusTest.cast(started, tag + "-cast", SKEINS);
        List<String> choosers = new ArrayList<>();
        XmageActualCardCorpusTest.resolveAll(started, tag, SWAMP_LABEL, (cls, step) -> {
            if (!"target".equals(cls) && !"choose_object".equals(cls)) {
                return false;
            }
            String actor = XmageActualCardCorpusTest.actorPid(started);
            Player actorPlayer = started.seats().get(actor);
            JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
            JsonObject legal = session.legalActionsPayload();
            assertNoOtherPrincipalsPrivateCards(game, started, actor, pending, legal);

            Set<UUID> ownHand = new HashSet<>();
            for (Card card : actorPlayer.getHand().getCards(game)) {
                ownHand.add(card.getId());
            }
            List<String> options = new ArrayList<>();
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
                JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
                assertNotNull(engine, "discard options carry engine metadata");
                UUID card = UUID.fromString(engine.get("object_id").getAsString());
                assertTrue(ownHand.contains(card), actor + " may discard only from their own hand");
                options.add(meta.get("option_id").getAsString());
            }
            int count = pending.get("minimum_selections").getAsInt();
            assertEquals(3, count, "three discards");
            if (choosers.isEmpty() || !choosers.get(choosers.size() - 1).equals(actor)) {
                choosers.add(actor);
            }
            options.sort(String::compareTo);
            submitSelection(session, tag + "-discard-" + actor + "-" + step,
                    options.subList(0, count));
            return true;
        });

        assertEquals(apnapFromP1(playerCount), choosers,
                "every player chooses their own discards, in APNAP order");
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            int cast = "P1".equals(pid) ? 1 : 0;
            assertEquals(handBefore.get(pid) - cast - 3, started.seats().get(pid).getHand().size(),
                    pid + " discarded exactly three cards");
        }
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void randomDiscardsAreReproducibleFromTheRulesSeed(int playerCount) {
        Map<String, List<String>> first = burningInquiry(playerCount, "a");
        Map<String, List<String>> second = burningInquiry(playerCount, "b");
        assertEquals(first, second,
                "same explicit seed: every player's random discards are identical");
        for (List<String> discarded : first.values()) {
            assertEquals(3, discarded.size(), "three random discards per player");
        }
        Set<String> distinct = new HashSet<>();
        first.values().forEach(discarded -> distinct.add(String.join(",", discarded)));
        assertTrue(distinct.size() > 1 || playerCount < 2,
                "the random discards are not the same for every player (non-vacuous): " + first);
    }

    private static Map<String, List<String>> burningInquiry(int playerCount, String run) {
        String tag = "inquiry-" + playerCount + "p";
        XmageActualCardCorpusTest.Started started = XmageActualCardCorpusTest.start(
                tag, playerCount, handsAndSpell(playerCount, INQUIRY, "Mountain", 1));
        XmageActualCardCorpusTest.cast(started, tag + "-" + run + "-cast", INQUIRY);
        XmageActualCardCorpusTest.resolveAll(started, tag + "-" + run, MOUNTAIN_LABEL,
                XmageActualCardCorpusTest.NONE);
        Game game = started.session().restorationGame();
        Map<String, List<String>> discarded = new LinkedHashMap<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            List<String> names = new ArrayList<>();
            for (Card card : started.seats().get(pid).getGraveyard().getCards(game)) {
                if (!INQUIRY.equals(card.getName())) {
                    names.add(card.getName());
                }
            }
            names.sort(String::compareTo);
            discarded.put(pid, names);
        }
        assertFalse(game.hasEnded());
        return discarded;
    }

    private static List<XmageNativeStateRestoration.RequestedObject> handsAndSpell(
            int playerCount, String spell, String land, int lands) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:hand-P1-9-" + spell.replaceAll("[^A-Za-z]", ""), spell, "P1", "P1",
                mage.constants.Zone.HAND, false));
        for (int index = 0; index < lands; index++) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:bf-P1-" + index + "-" + land, land, "P1", "P1",
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            for (int index = 0; index < HAND.size(); index++) {
                objects.add(new XmageNativeStateRestoration.RequestedObject(
                        "obj:hand-" + pid + "-" + index + "-"
                                + HAND.get(index).replaceAll("[^A-Za-z]", ""),
                        HAND.get(index), pid, pid, mage.constants.Zone.HAND, false));
            }
        }
        return objects;
    }

    private static List<String> apnapFromP1(int playerCount) {
        List<String> order = new ArrayList<>();
        order.add("P1");
        for (int seat = playerCount; seat >= 2; seat--) {
            order.add("P" + seat);
        }
        return order;
    }

    /** Test-oracle scan: no other principal's hand/library identity in the actor's view. */
    private static void assertNoOtherPrincipalsPrivateCards(Game game,
            XmageActualCardCorpusTest.Started started, String actor,
            JsonObject pending, JsonObject legal) {
        String view = pending.toString() + legal.toString();
        int hidden = 0;
        for (Map.Entry<String, Player> seat : started.seats().entrySet()) {
            if (seat.getKey().equals(actor)) {
                continue;
            }
            List<Card> cards = new ArrayList<>(seat.getValue().getHand().getCards(game));
            cards.addAll(seat.getValue().getLibrary().getCards(game));
            for (Card card : cards) {
                hidden++;
                assertFalse(view.contains(card.getId().toString()),
                        actor + "'s discard view leaks a card of " + seat.getKey()
                                + " (" + card.getName() + ")");
            }
        }
        assertTrue(hidden > 0, "the oracle must scan real hidden cards");
    }

    private static void submitSelection(XmageFullGameSession session, String tag,
            List<String> optionIds) {
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", decisionId + ":" + optionIds.get(0));
        proposal.addProperty("action_type", "choose_targets");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        JsonArray selected = new JsonArray();
        optionIds.forEach(selected::add);
        choices.add("selected_option_ids", selected);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = session.submitAction(proposal);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());
    }
}
