package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.cards.Card;
import mage.game.Game;
import mage.game.combat.CombatGroup;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * #1584: a block controller other than the defender (CR 509.1a; XMage's
 * ChooseBlockersEffect family: Brutal Hordechief, Master Warcraft, Odric,
 * Invasion Plans) declares the <em>defender's</em> blockers.
 *
 * <p>Invasion Plans ("All creatures block each combat if able. The attacking
 * player chooses how each creature blocks each combat.") costs no mana and
 * needs no activation, so the attacker P1 is the block controller as soon as
 * it attacks. P1 attacks P2 and P3 with one Raging Goblin each; XMage then
 * calls {@code selectBlockers} on P1 once per defender (APNAP: P2, then P3),
 * each time with that defender's id.</p>
 *
 * <p>Before the fix the bridge took P1's own untapped creatures, which can
 * never block here: no frame was raised, the unmet "blocks if able" was
 * re-checked, and XMage re-asked without end (the loop has no bound for a
 * human-type player) until the session's settle timeout. In real games that
 * was the {@code ENGINE_FAILURE} of seeds 1024/1029/1033; where no block was
 * required, the defender's blocks were silently skipped.</p>
 *
 * <p>Hidden information (AGENTS.md §5): the block controller now receives
 * frames about an opponent's creatures. They are public battlefield objects;
 * the frames must still carry no opponent hand or library identity, and the
 * oracle must turn red on a leaking frame.</p>
 */
class XmageBlockControllerTest {

    private static final String PLANS = "Invasion Plans";
    private static final String GOBLIN = "Raging Goblin";
    private static final String BEARS = "Grizzly Bears";
    private static final String GIANT = "Hill Giant";
    private static final String P2_HIDDEN = "Lightning Bolt";
    private static final String P3_HIDDEN = "Counterspell";

    private static XmageNativeStateRestoration.RequestedObject object(
            String pid, String name, int index, mage.constants.Zone zone) {
        String zoneTag = zone == mage.constants.Zone.HAND ? "hand" : "bf";
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, zone, false);
    }

    private static List<XmageNativeStateRestoration.RequestedObject> board() {
        mage.constants.Zone bf = mage.constants.Zone.BATTLEFIELD;
        mage.constants.Zone hand = mage.constants.Zone.HAND;
        return List.of(
                object("P1", PLANS, 0, bf),
                object("P1", GOBLIN, 0, bf),
                object("P1", GOBLIN, 1, bf),
                object("P2", BEARS, 0, bf),
                object("P2", P2_HIDDEN, 0, hand),
                object("P3", GIANT, 0, bf),
                object("P3", P3_HIDDEN, 0, hand));
    }

    /** A restored game at the first block frame of P1, the block controller. */
    private record AtBlocks(
            XmageFullGameSession session,
            Map<String, Player> seats,
            Game game,
            Map<UUID, UUID> attackerAt,
            JsonObject firstBlockFrame) {

        UUID id(String pid) {
            return seats.get(pid).getId();
        }
    }

    /** P1 attacks P2 with its first Raging Goblin and P3 with its second. */
    private static AtBlocks attackBothOpponents(String tag) {
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, 3, board());
        XmageFullGameSession session = started.session();
        Map<String, Player> seats = started.seats();
        List<UUID> defendersInOrder = List.of(seats.get("P2").getId(), seats.get("P3").getId());
        Map<UUID, UUID> attackerAt = new HashMap<>();
        int attacks = 0;
        for (int step = 0; step < 80; step++) {
            JsonObject pending = pendingOrFail(session);
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actor = XmageNativeStateRestorationTest.pidOf(
                    seats, legal.get("actor_id").getAsString());
            switch (decisionClass) {
                case "priority" -> passOrFail(session, tag + "-pass-" + step, legal);
                case "declare_attacker" -> {
                    assertEquals("P1", actor, "only P1 attacks");
                    assertTrue(attacks < 2, "P1 has two attackers");
                    UUID defender = defendersInOrder.get(attacks);
                    JsonObject attack = attackAt(legal, defender);
                    attackerAt.put(defender, UUID.fromString(attack.getAsJsonObject("metadata")
                            .getAsJsonObject("xmage_option_metadata")
                            .get("object_id").getAsString()));
                    XmageFullGameTaxExecutionTest.submit(session, tag + "-attack-" + step, attack);
                    attacks++;
                }
                case "declare_blocker" -> {
                    assertEquals(2, attacks, "P1 attacked both opponents");
                    return new AtBlocks(session, seats, session.restorationGame(),
                            attackerAt, pending);
                }
                default -> fail("unexpected decision before blocks: " + decisionClass);
            }
        }
        fail("no block frame within 80 decisions");
        return null;
    }

    @Test
    void blockControllerDeclaresEachDefendersBlockers() {
        String tag = "block-controller-1584";
        AtBlocks at = attackBothOpponents(tag);
        UUID p1 = at.id("P1");
        UUID p2 = at.id("P2");
        UUID p3 = at.id("P3");
        Permanent bears = only(at.game(), p2, BEARS);
        Permanent giant = only(at.game(), p3, GIANT);
        UUID goblinAtP2 = at.attackerAt().get(p2);
        UUID goblinAtP3 = at.attackerAt().get(p3);

        // Frame 1 (APNAP: P2 first): P1 decides, the blocker is P2's, and the
        // only option is the Goblin that attacks P2.
        JsonObject first = at.firstBlockFrame();
        assertBlockFrame(at, first, p1, p2, bears, goblinAtP2);
        declare(at.session(), tag + "-block-p2", first, List.of(goblinAtP2.toString()));

        // Frame 2: P3's Hill Giant. An empty declaration leaves "blocks if
        // able" unmet, so the engine (not the bridge) re-asks the same frame.
        JsonObject second = pendingOrFail(at.session());
        assertBlockFrame(at, second, p1, p3, giant, goblinAtP3);
        declare(at.session(), tag + "-block-p3-none", second, List.of());
        JsonObject reasked = pendingOrFail(at.session());
        assertBlockFrame(at, reasked, p1, p3, giant, goblinAtP3);
        declare(at.session(), tag + "-block-p3", reasked, List.of(goblinAtP3.toString()));

        // The blocks stand in the engine's combat, each blocker on the
        // attacker of its own defender.
        pendingOrFail(at.session());
        assertEquals(Set.of(bears.getId()), blockersOf(at.game(), goblinAtP2),
                "P2's Grizzly Bears blocks the Goblin attacking P2");
        assertEquals(Set.of(giant.getId()), blockersOf(at.game(), goblinAtP3),
                "P3's Hill Giant blocks the Goblin attacking P3");
    }

    @Test
    void blockControllerFramesCarryNoOpponentHiddenCards() {
        String tag = "block-controller-1584-hidden";
        AtBlocks at = attackBothOpponents(tag);
        UUID p1 = at.id("P1");
        JsonObject first = at.firstBlockFrame();
        assertHiddenInformationHolds(at.session(), at.game(), first, p1);
        assertOracleCatchesALeak(at.game(), first, p1, at.seats().get("P2"));
        declare(at.session(), tag + "-block-p2", first, List.of());
        JsonObject second = pendingOrFail(at.session());
        assertEquals("declare_blocker", second.get("decision_class").getAsString());
        assertEquals(p1.toString(), second.get("actor_id").getAsString());
        assertHiddenInformationHolds(at.session(), at.game(), second, p1);
    }

    // ------------------------------------------------------------- assertions

    private static void assertBlockFrame(
            AtBlocks at, JsonObject pending, UUID decider, UUID defender,
            Permanent blocker, UUID attackerOfDefender) {
        XmageFullGameSession session = at.session();
        Map<String, Player> seats = at.seats();
        assertEquals("declare_blocker", pending.get("decision_class").getAsString());
        assertEquals(decider.toString(), pending.get("actor_id").getAsString(),
                "the block controller decides, not the defender");
        assertEquals(0, pending.get("minimum_selections").getAsInt());
        assertEquals(1, pending.get("maximum_selections").getAsInt());
        JsonObject legal = session.legalActionsPayload();
        assertEquals(decider.toString(), legal.get("actor_id").getAsString());
        List<String> blockerIds = new ArrayList<>();
        List<String> attackerIds = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject metadata = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            blockerIds.add(metadata.get("blocker_id").getAsString());
            attackerIds.add(metadata.get("attacker_id").getAsString());
        }
        assertEquals(List.of(blocker.getId().toString()), blockerIds,
                "the offered blocker is the defender's creature ("
                        + XmageNativeStateRestorationTest.pidOf(seats, defender.toString()) + ")");
        assertEquals(List.of(attackerOfDefender.toString()), attackerIds,
                "only the attacker of this defender's combat group is offered");
        // The frame says whose creature it is: the blocker sits on the
        // defender's public battlefield in the actor's pilot_state, and the
        // defender's entry is not the actor's.
        boolean found = false;
        for (JsonElement element : pending.getAsJsonObject("pilot_state").getAsJsonArray("players")) {
            JsonObject entry = element.getAsJsonObject();
            boolean isActor = entry.get("is_actor").getAsBoolean();
            for (JsonElement item : entry.getAsJsonArray("battlefield")) {
                JsonObject permanent = item.getAsJsonObject();
                if (blocker.getId().toString().equals(permanent.get("object_id").getAsString())) {
                    // Actor-safe identity: an opponent appears as its seat token.
                    assertEquals(ActorSafeIdentity.forSeat(decider, defender,
                                    XmageSeating.seat(session.restorationGame(), defender)),
                            entry.get("player_id").getAsString(),
                            "the blocker is listed under its controller, the defender");
                    assertFalse(isActor, "the defender is not the deciding actor");
                    found = true;
                }
            }
        }
        assertTrue(found, "the blocker is on the defender's public battlefield in pilot_state");
    }

    private static void assertHiddenInformationHolds(
            XmageFullGameSession session, Game game, JsonObject pending, UUID actor) {
        for (JsonElement element : pending.getAsJsonObject("pilot_state").getAsJsonArray("players")) {
            JsonObject entry = element.getAsJsonObject();
            if (entry.get("is_actor").getAsBoolean()) {
                assertEquals(actor.toString(), entry.get("player_id").getAsString());
                assertTrue(entry.has("hand"), "the actor sees its own hand");
            } else {
                assertFalse(entry.has("hand"), "an opponent's hand array must be absent");
                assertFalse(entry.has("mana_pool"), "an opponent's mana pool must be absent");
            }
        }
        Set<String> hidden = hiddenCardIds(game, actor);
        assertFalse(hidden.isEmpty(), "the oracle needs opponent-private cards");
        assertNoHiddenCardIdentities(pending, hidden);
        JsonObject legal = session.legalActionsPayload();
        legal.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        legal.addProperty("decision_class", pending.get("decision_class").getAsString());
        assertNoHiddenCardIdentities(legal, hidden);
        assertNoHiddenNames(pending);
        assertNoHiddenNames(legal);
    }

    /**
     * Fail-closed oracle, the same check as XmageFullGameHiddenInformationTest's
     * (kept separate because that file is a pinned meta-verification input):
     * no opponent hand or library card id anywhere in the serialized view.
     */
    private static void assertNoHiddenCardIdentities(JsonObject view, Set<String> hiddenIds) {
        String serialized = view.toString();
        for (String hidden : hiddenIds) {
            assertTrue(!serialized.contains(hidden),
                    "hidden card identity leaked at offset "
                            + view.get("decision_offset").getAsLong()
                            + " class=" + view.get("decision_class").getAsString());
        }
    }

    /**
     * The oracle is not vacuous: the same block controller frame with the
     * defender's hand card injected (as a leaking frame would carry it, by id
     * or by name) turns it red.
     */
    private static void assertOracleCatchesALeak(
            Game game, JsonObject pending, UUID actor, Player defender) {
        Set<String> hidden = hiddenCardIds(game, actor);
        String handCard = handCardId(game, defender, P2_HIDDEN);
        assertTrue(hidden.contains(handCard), "the oracle covers the defender's hand");
        JsonObject byId = JsonParser.parseString(pending.toString()).getAsJsonObject();
        JsonObject leakedOption = new JsonObject();
        leakedOption.addProperty("blocker_id", handCard);
        byId.getAsJsonObject("context").add("leaked_block_option", leakedOption);
        AssertionError detected = assertThrows(AssertionError.class,
                () -> assertNoHiddenCardIdentities(byId, hidden));
        assertTrue(detected.getMessage().contains("hidden card identity leaked"));
        JsonObject byName = JsonParser.parseString(pending.toString()).getAsJsonObject();
        byName.getAsJsonObject("context").addProperty("leaked_name", P2_HIDDEN);
        assertThrows(AssertionError.class, () -> assertNoHiddenNames(byName));
    }

    /** The opponents' hand cards are names that appear nowhere else on this board. */
    private static void assertNoHiddenNames(JsonObject view) {
        String serialized = view.toString();
        for (String name : List.of(P2_HIDDEN, P3_HIDDEN)) {
            assertTrue(!serialized.contains(name), "opponent hand card named in a frame: " + name);
        }
    }

    // ---------------------------------------------------------------- helpers

    private static JsonObject pendingOrFail(XmageFullGameSession session) {
        JsonObject payload;
        try {
            payload = session.pendingDecisionPayload();
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            throw new AssertionError("#1584: the engine raised no frame (the block controller "
                    + "was offered no defender's creature and XMage re-asked without end): "
                    + exc.getMessage(), exc);
        }
        if (payload.get("decision").isJsonNull()) {
            fail("engine terminal before the blocks were declared");
        }
        return payload.getAsJsonObject("decision");
    }

    private static void passOrFail(XmageFullGameSession session, String tag, JsonObject legal) {
        try {
            XmageFullGameTaxExecutionTest.submit(session, tag,
                    XmageFullGameTaxExecutionTest.singleActionOfType(legal, "pass_priority", null));
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            throw new AssertionError("#1584: no frame after passing priority (the block "
                    + "controller was offered no defender's creature and XMage re-asked "
                    + "without end): " + exc.getMessage(), exc);
        }
    }

    private static void declare(
            XmageFullGameSession session, String proposalId, JsonObject pending,
            List<String> attackerOptionIds) {
        JsonObject legal = session.legalActionsPayload();
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        if (attackerOptionIds.isEmpty()) {
            proposal.add("legal_action_id", JsonNull.INSTANCE);
            proposal.addProperty("action_type", "structural_decision");
        } else {
            proposal.addProperty("legal_action_id", decisionId + ":" + attackerOptionIds.get(0));
            proposal.addProperty("action_type", "declare_blockers");
        }
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        JsonArray selected = new JsonArray();
        attackerOptionIds.forEach(selected::add);
        choices.add("selected_option_ids", selected);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        session.submitAction(proposal);
    }

    private static JsonObject attackAt(JsonObject legal, UUID defender) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if ("declare_attackers".equals(action.get("action_type").getAsString())
                    && metadata != null && metadata.has("defender_id")
                    && defender.toString().equals(metadata.get("defender_id").getAsString())) {
                return action;
            }
        }
        fail("no attack at " + defender + " offered: " + legal);
        return null;
    }

    private static Permanent only(Game game, UUID controller, String name) {
        Permanent found = null;
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(controller)) {
            if (name.equals(permanent.getName())) {
                assertTrue(found == null, "unique " + name);
                found = permanent;
            }
        }
        assertNotNull(found, name + " on the battlefield");
        return found;
    }

    private static Set<UUID> blockersOf(Game game, UUID attackerId) {
        CombatGroup group = game.getCombat().findGroup(attackerId);
        assertNotNull(group, "the attacker is in combat");
        return new HashSet<>(group.getBlockers());
    }

    /** Test-only oracle: every opponent hand and library card id (never pilot input). */
    private static Set<String> hiddenCardIds(Game game, UUID actor) {
        Set<String> hidden = new HashSet<>();
        for (Player player : game.getPlayers().values()) {
            if (player.getId().equals(actor)) {
                continue;
            }
            for (Card card : player.getHand().getCards(game)) {
                hidden.add(card.getId().toString());
            }
            for (Card card : player.getLibrary().getCards(game)) {
                hidden.add(card.getId().toString());
            }
        }
        return hidden;
    }

    private static String handCardId(Game game, Player player, String name) {
        for (Card card : player.getHand().getCards(game)) {
            if (name.equals(card.getName())) {
                return card.getId().toString();
            }
        }
        fail(name + " is not in " + player.getName() + "'s hand");
        return null;
    }
}
