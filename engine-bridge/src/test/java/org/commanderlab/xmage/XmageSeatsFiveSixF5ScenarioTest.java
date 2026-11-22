package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.CommanderCardType;
import mage.constants.PhaseStep;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.GameCommanderImpl;
import mage.game.permanent.Permanent;
import mage.players.Player;
import mage.watchers.common.CommanderInfoWatcher;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * F5 of #1661 (gate (b) of the 5/6-seat release path, #1715): the eight rule
 * points of {@code docs/research/SEATS_5_6_QUALIFICATION_PLAN.md} §2 as named
 * real-engine scenarios at five and six seats, on the full-game lane.
 *
 * <p>XMage decides every rule. Each scenario puts the seats a four-seat table
 * does not have (P5, P6) into the role that matters: the last seat acts,
 * leaves or defends; the turn and APNAP order wraps from the last seat to P1;
 * the commander-damage matrix has 20 or 30 ordered pairs. Expected results
 * come from the cited Comprehensive Rules and from the same scenario shape
 * that existing bridge tests already pin at 3–6 seats (named per method). This
 * class changes no bridge code and no release lock
 * ({@code launch.MAX_RELEASED_SEATS = 4} stays).</p>
 *
 * <p>Where an existing test already covers a point at five or six seats it is
 * not repeated here; three methods call an existing scenario body with a seat
 * count or active seat that body has not run with before (points 1, 6 and
 * 8).</p>
 *
 * <p>Not covered here, by design: the replay tape (point 8) is Python-side
 * ({@code semantic_replay/tape.py}); the five-seat tape MATCH is a separate
 * run and stays NOT_RUN until it has run. Cross-JVM identity is #1715.</p>
 */
class XmageSeatsFiveSixF5ScenarioTest {

    private static final String BOLT = "Lightning Bolt";
    private static final String MOUNTAIN = "Mountain";
    private static final String GOBLIN = "Raging Goblin";
    private static final String HELLRIDER = "Hellrider";
    private static final String BEARS = "Grizzly Bears";
    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    /** One distinct hand card per non-acting seat (P1 .. P5), all in the bridge test corpus. */
    private static final List<String> HIDDEN_HAND = List.of(
            "Shock", "Giant Growth", "Counterspell", "Grizzly Bears", "Hill Giant");

    // ------------------------------------------------------------- point 1

    /**
     * F5-1 APNAP (CR 603.3b, 101.4) at six seats with the last seat active, so
     * the next upkeep is P1's and all six Sulfuric Vortex triggers stack from
     * P1 (bottom) to P6 (top). Same scenario body as
     * {@link XmageMultiplayerApnapTriggerTest}, which runs 5/P3, 5/P5 and 6/P4
     * but not the six-seat wrap.
     */
    @ParameterizedTest(name = "F5-1 APNAP: {0} players, restored active {1}")
    @CsvSource({"6, P6"})
    void point1ApnapTriggersWrapFromTheLastSeatToP1(int playerCount, String restoredActive) {
        new XmageMultiplayerApnapTriggerTest()
                .eachUpkeepTriggersAreStackedInApnapOrder(playerCount, restoredActive);
    }

    // ------------------------------------------------------------- point 2

    /**
     * F5-2 a player leaves with its spell on the stack (CR 800.4a), with the
     * last seat as caster and leaver. On P1's turn PN casts Lightning Bolt at
     * P(N-1), keeps priority with a second Bolt castable, and concedes. PN's
     * Bolt ceases to exist, P(N-1) takes no damage, PN's re-issued frame offers
     * only the pass, PN is never asked again and the other N-1 players play
     * on. Same shape as {@link XmageMultiplayerLeaverStackTest} (P2 leaves,
     * 4 and 5 seats); leaving mid-combat at 3–6 seats is
     * {@link XmageMultiplayerLeaveDuringCombatTest}.
     */
    @ParameterizedTest(name = "F5-2 leaver with a spell on the stack: {0} players")
    @ValueSource(ints = {5, 6})
    void point2LastSeatLeavesWhileItsSpellIsOnTheStack(int playerCount) {
        String leaver = "P" + playerCount;
        String victim = "P" + (playerCount - 1);
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj(leaver, BOLT, 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj(leaver, BOLT, 1, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj(leaver, MOUNTAIN, 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj(leaver, MOUNTAIN, 3, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "f5-2-leaver-" + playerCount + "p", playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        String leaverId = s.seats.get(leaver).getId().toString();
        UUID victimId = s.seats.get(victim).getId();
        boolean cast = false;
        for (int i = 0; i < 80; i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            if (cast && leaver.equals(actor) && "priority".equals(cls)) {
                assertEquals(1, game.getStack().size(), "control: " + leaver + "'s Bolt is on the stack");
                assertTrue(s.labels().contains("Lightning Bolt — Cast Lightning Bolt"),
                        "control: " + leaver + " could cast its second Bolt");
                concedeHoldingPriority(s, game, leaver, victim, leaverId);
                return;
            }
            switch (cls) {
                case "priority" -> s.submit(!cast && leaver.equals(actor)
                        ? s.action("activate_ability", "Cast Lightning Bolt")
                        : s.action("pass_priority", "Pass"));
                case "target" -> {
                    assertEquals(leaver, actor, "only the leaver casts a spell");
                    s.submit(playerTargetAction(s.session.legalActionsPayload(), victimId));
                    cast = true;
                }
                case "mana_payment" -> s.payWith(MOUNTAIN);
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        fail(leaver + " never held priority over its Bolt");
    }

    private static void concedeHoldingPriority(XmageMultiplayerScenario s, Game game,
            String leaver, String victim, String leaverId) {
        JsonObject concede = new JsonObject();
        concede.addProperty("proposal_id", leaver + "-concede");
        concede.addProperty("actor_id", leaverId);
        concede.addProperty("player_id", leaverId);
        JsonObject result = s.session.submitConcede(concede);
        assertFalse(s.seats.get(leaver).isInGame(), leaver + " left the game");
        assertTrue(game.getStack().isEmpty(),
                leaver + "'s Bolt, a card it owns, left the game with it (800.4a)");
        assertTrue(result.get("failure").isJsonNull(), "the lane goes on: " + result.get("failure"));

        JsonObject frame = result.getAsJsonObject("decision");
        assertEquals(leaverId, frame.get("actor_id").getAsString(),
                leaver + " still answers its own open frame");
        assertEquals("priority", frame.get("decision_class").getAsString());
        JsonArray options = frame.getAsJsonArray("legal_options");
        assertEquals(1, options.size(), "only the pass option remains: " + options);
        for (JsonElement option : options) {
            assertEquals("pass_priority", option.getAsJsonObject().get("option_type").getAsString());
        }
        assertTrue(frame.getAsJsonObject("context").get("actor_left_game").getAsBoolean());

        s.submit(s.action("pass_priority", "Pass"));
        for (int i = 0; i < 2 * s.seats.size(); i++) {
            JsonObject next = s.session.pendingDecisionPayload().getAsJsonObject("decision");
            assertNotNull(next, "the game goes on for the remaining players");
            assertFalse(leaverId.equals(next.get("actor_id").getAsString()),
                    leaver + " is never asked again");
            s.submit(s.action("pass_priority", "Pass"));
        }
        assertEquals(40, s.seats.get(victim).getLife(),
                victim + " took no damage from the departed Bolt");
        for (Map.Entry<String, Player> seat : s.seats.entrySet()) {
            if (!seat.getKey().equals(leaver)) {
                assertTrue(seat.getValue().isInGame(), seat.getKey() + " still plays");
                assertEquals(40, seat.getValue().getLife(), seat.getKey() + " untouched");
            }
        }
        assertFalse(game.hasEnded(), "N-1 players remain, the game goes on");
    }

    // ------------------------------------------------------------- point 3

    /**
     * F5-3 commander damage per ordered pair (CR 903.10a, 704.6c) at 20 and 30
     * restored pairs. Every commander has dealt 20 combat damage to every
     * other player, except PN's commander, which has dealt 21 to P(N-1). The
     * matrix is restored input through the native CARD-scope
     * {@code CommanderInfoWatcher}; what the engine decides is the state-based
     * action, as in {@link XmageCommanderDamageRestorationTest} (three seats).
     * Only P(N-1) loses. PN, restored with 20 from each of the other N-1
     * commanders (100 at six seats) at that same check, does not: damage is
     * never added across commanders. Afterwards the ledger is read back for
     * the (N-1)^2 pairs whose commander is still in the game (16 / 25),
     * including PN -> P(N-1) = 21. Not covered: accumulation through live
     * combat at 5/6 seats (no hasty commander with power in the scaffold
     * corpus).
     */
    @ParameterizedTest(name = "F5-3 commander damage per pair: {0} players")
    @ValueSource(ints = {5, 6})
    void point3CommanderDamageCountsPerOrderedPairAndNeverAcrossCommanders(int playerCount) {
        String last = "P" + playerCount;
        String loser = "P" + (playerCount - 1);
        String tag = "f5-3-cmd-damage-" + playerCount + "p";
        Map<String, Integer> expected = new LinkedHashMap<>();
        List<XmageNativeStateRestoration.RequestedCommanderDamage> damage = new ArrayList<>();
        for (int attacker = 1; attacker <= playerCount; attacker++) {
            for (int defender = 1; defender <= playerCount; defender++) {
                if (attacker == defender) {
                    continue;
                }
                String from = "P" + attacker;
                String to = "P" + defender;
                int amount = from.equals(last) && to.equals(loser) ? 21 : 20;
                expected.put(from + "->" + to, amount);
                damage.add(new XmageNativeStateRestoration.RequestedCommanderDamage(
                        "cmd:" + from + "-A", to, amount));
            }
        }
        assertEquals(playerCount * (playerCount - 1), damage.size(), "every ordered pair");

        XmageFullGameSession session = arriveWithCommanderDamage(tag, playerCount, damage);
        Map<String, Player> seats = session.restorationSeats();
        GameCommanderImpl game = session.restorationGame();

        for (Map.Entry<String, Player> seat : seats.entrySet()) {
            Player player = seat.getValue();
            if (seat.getKey().equals(loser)) {
                assertTrue(player.hasLost() || player.hasLeft(),
                        "704.6c: 21 from " + last + "'s commander makes " + loser + " lose");
            } else {
                assertFalse(player.hasLost(), seat.getKey()
                        + " holds at most 20 from any one commander and does not lose");
            }
        }
        // Read back the native ledger of every commander, for every defender,
        // the loser included (PN -> P(N-1) must read 21). Only the loser's own
        // commander is skipped as attacker: it left the game with its owner
        // (CR 800.4a), so the engine no longer lists it for that owner.
        int pairsRead = 0;
        for (int attacker = 1; attacker <= playerCount; attacker++) {
            String from = "P" + attacker;
            if (from.equals(loser)) {
                continue;
            }
            CommanderInfoWatcher watcher = game.getState().getWatcher(
                    CommanderInfoWatcher.class, commanderId(game, seats.get(from)));
            assertNotNull(watcher, "native CommanderInfoWatcher for " + from);
            for (int defender = 1; defender <= playerCount; defender++) {
                String to = "P" + defender;
                if (attacker == defender) {
                    continue;
                }
                assertEquals(expected.get(from + "->" + to),
                        watcher.getDamageToPlayer().get(seats.get(to).getId()),
                        "native ledger " + from + " -> " + to);
                pairsRead++;
            }
        }
        assertEquals((playerCount - 1) * (playerCount - 1), pairsRead,
                "ledger read back for every pair whose commander is still in the game");
        assertFalse(game.hasEnded(), "N-1 players remain");
        // One priority round after the state-based action: the N-1 survivors,
        // and only they, are asked.
        Set<String> survivors = new LinkedHashSet<>(seats.keySet());
        survivors.remove(loser);
        Set<String> asked = new LinkedHashSet<>();
        for (int i = 0; i < playerCount - 1; i++) {
            JsonObject pending = session.pendingDecisionPayload();
            assertFalse(pending.get("decision").isJsonNull(), "the survivors get the next decision");
            assertEquals("priority",
                    pending.getAsJsonObject("decision").get("decision_class").getAsString());
            String actor = XmageNativeStateRestorationTest.pidOf(seats,
                    session.legalActionsPayload().get("actor_id").getAsString());
            assertFalse(loser.equals(actor), loser + " is never asked again");
            asked.add(actor);
            XmageFullGameTaxExecutionTest.submit(session, tag + "-pass-" + i,
                    XmageNativeStateRestorationTest.singleActionOfType(
                            session.legalActionsPayload(), "pass_priority", null));
        }
        assertEquals(survivors, asked, "one priority round reaches every survivor");
    }

    /**
     * Known engine deviation (documentation test, not a rule claim of ours).
     * Two chained 21-damage pairs restored for the same state-based-action
     * check: by CR 704.3 with 704.6c both damaged players should lose at once.
     * The engine at the tested build lets only one of them lose:
     * {@code GameCommanderImpl.checkStateBasedActions} walks the players one
     * after another and skips the commanders of owners that are no longer in
     * the game, so the commander of the player who just lost no longer counts
     * (reviewer finding on #1750 from the bytecode, LOCAL_OBSERVED on the
     * local 1.4.62 build; restored input, no live combat). XMage is the rules
     * authority: the bridge mirrors it, the deviation is only reported, no
     * fork change. This test stays green while the engine behaves so; when it
     * fails, the deviation is gone and this test and F5-3's PARTIAL rating are
     * to be revisited. The control row with two separate pairs shows both
     * players losing.
     */
    @ParameterizedTest(name = "known engine deviation, {0} players: {1} -> lost {2}, still in {3}")
    @CsvSource({
            "6, P1>P6 P6>P5, P6, P5",
            "5, P1>P5 P5>P4, P5, P4",
            "6, P6>P5 P5>P1, P5, P1",
            "6, P1>P2 P5>P4, P2 P4, -"})
    void knownEngineDeviationChainedTwentyOnePairsInOneCheckEliminateOnlyOnePlayer(
            int playerCount, String pairs, String lost, String stillIn) {
        String tag = "f5-3-chained-" + playerCount + "p-" + pairs.replaceAll("[^A-Za-z0-9]", "");
        List<XmageNativeStateRestoration.RequestedCommanderDamage> damage = new ArrayList<>();
        for (String pair : pairs.split(" ")) {
            String[] ends = pair.split(">");
            damage.add(new XmageNativeStateRestoration.RequestedCommanderDamage(
                    "cmd:" + ends[0] + "-A", ends[1], 21));
        }
        XmageFullGameSession session = arriveWithCommanderDamage(tag, playerCount, damage);
        Map<String, Player> seats = session.restorationSeats();
        Set<String> lostSet = Set.of(lost.split(" "));
        for (Map.Entry<String, Player> seat : seats.entrySet()) {
            Player player = seat.getValue();
            if (lostSet.contains(seat.getKey())) {
                assertTrue(player.hasLost() || player.hasLeft(), seat.getKey() + " lost");
            } else {
                assertFalse(player.hasLost(), seat.getKey() + " is still in the game"
                        + (seat.getKey().equals(stillIn)
                                ? " (known deviation: CR 704.3/704.6c would make it lose too)"
                                : ""));
            }
        }
    }

    /** Arrival at P1's precombat main with the given restored commander-damage matrix. */
    private static XmageFullGameSession arriveWithCommanderDamage(String tag, int playerCount,
            List<XmageNativeStateRestoration.RequestedCommanderDamage> damage) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            players.add(new XmageNativeStateRestoration.RequestedPlayer("P" + seat, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:P" + seat + "-A", ROGRAKH, "P" + seat, 0));
        }
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                tag, playerCount, 424242L, players, commanders, damage, List.of(),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, tag);
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        XmageNativeStateRestorationTest.completeArrival(
                session, restoration, session.restorationSeats());
        return session;
    }

    private static UUID commanderId(GameCommanderImpl game, Player owner) {
        List<UUID> matches = new ArrayList<>();
        for (UUID id : game.getCommandersIds(owner, CommanderCardType.ANY, false)) {
            Card card = game.getCard(id);
            if (card != null && ROGRAKH.equals(card.getName())) {
                matches.add(id);
            }
        }
        assertEquals(1, matches.size(), "exactly one genuine commander for " + owner.getName());
        return matches.get(0);
    }

    // ------------------------------------------------------------- point 4

    /**
     * F5-4 range of influence {@code ALL} (the bridge's fixed setting,
     * {@code XmageCommanderGames}) at 5/6 seats, plus hidden information per
     * seat ({@code AGENTS.md} §5). On P1's turn PN casts Lightning Bolt ("any
     * target"): with no creature or planeswalker in play the engine offers
     * exactly the N players, P1 and PN included. Every frame of every seat on
     * the way (all N seats get priority) is scanned: it carries no card id of
     * another seat's hand or library and no name of another seat's hand card
     * (each seat holds one distinct named card). Discarding at 3–6 seats is
     * {@link XmageMultiplayerHiddenDiscardTest}.
     */
    @ParameterizedTest(name = "F5-4 range ALL and hidden information: {0} players")
    @ValueSource(ints = {5, 6})
    void point4LastSeatMayTargetEveryPlayerAndNoFrameShowsAnotherSeatsHiddenCards(int playerCount) {
        String last = "P" + playerCount;
        Map<String, String> handName = new LinkedHashMap<>();
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        for (int seat = 1; seat < playerCount; seat++) {
            String pid = "P" + seat;
            handName.put(pid, HIDDEN_HAND.get(seat - 1));
            objects.add(XmageMultiplayerScenario.obj(pid, HIDDEN_HAND.get(seat - 1), 0, Zone.HAND));
        }
        handName.put(last, BOLT);
        objects.add(XmageMultiplayerScenario.obj(last, BOLT, 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj(last, MOUNTAIN, 1, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "f5-4-range-" + playerCount + "p", playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        Set<String> allPlayers = new HashSet<>();
        s.seats.values().forEach(player -> allPlayers.add(player.getId().toString()));

        Set<String> scannedActors = new LinkedHashSet<>();
        boolean cast = false;
        boolean targeted = false;
        for (int i = 0; i < 120; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertFalse(payload.get("decision").isJsonNull(), "engine terminal mid-scenario");
            String cls = s.decisionClass();
            String actor = s.actor();
            JsonObject legal = s.session.legalActionsPayload();
            // The pilot's view: the decision frame plus its legal actions (the
            // same scope as XmageMultiplayerHiddenDiscardTest), not the
            // session status around it.
            assertNoHiddenCardOfAnotherSeat(game, s.seats, handName, actor,
                    payload.getAsJsonObject("decision"), legal);
            scannedActors.add(actor);
            if (targeted && "priority".equals(cls) && game.getStack().isEmpty()) {
                break;
            }
            switch (cls) {
                case "priority" -> {
                    boolean castNow = !cast && last.equals(actor);
                    s.submit(castNow ? s.action("activate_ability", "Cast Lightning Bolt")
                            : s.action("pass_priority", "Pass"));
                    cast = cast || castNow;
                }
                case "target" -> {
                    assertEquals(last, actor);
                    assertEquals(allPlayers, playerTargetIds(legal),
                            "range ALL: the engine offers every one of the " + playerCount
                                    + " players as a Bolt target");
                    s.submit(playerTargetAction(legal, s.seats.get("P1").getId()));
                    targeted = true;
                }
                case "mana_payment" -> s.payWith(MOUNTAIN);
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        assertTrue(targeted, "control: " + last + " reached its target choice");
        assertEquals(37, s.seats.get("P1").getLife(), "the Bolt resolved at P1");
        assertEquals(s.seats.keySet(), scannedActors, "a frame of every seat was scanned");
    }

    /** Test oracle: no other seat's hand/library id, and no other seat's hand-card name. */
    private static void assertNoHiddenCardOfAnotherSeat(Game game, Map<String, Player> seats,
            Map<String, String> handName, String actor, JsonObject pending, JsonObject legal) {
        String view = pending.toString() + legal.toString();
        int hidden = 0;
        for (Map.Entry<String, Player> seat : seats.entrySet()) {
            if (seat.getKey().equals(actor)) {
                continue;
            }
            List<Card> cards = new ArrayList<>(seat.getValue().getHand().getCards(game));
            cards.addAll(seat.getValue().getLibrary().getCards(game));
            for (Card card : cards) {
                hidden++;
                assertFalse(view.contains(card.getId().toString()),
                        actor + "'s frame leaks a card id of " + seat.getKey()
                                + " (" + card.getName() + ")");
            }
            String name = handName.get(seat.getKey());
            boolean stillHidden = false;
            for (Card card : seat.getValue().getHand().getCards(game)) {
                stillHidden = stillHidden || card.getName().equals(name);
            }
            if (stillHidden && !name.equals(handName.get(actor))) {
                assertFalse(view.contains(name),
                        actor + "'s frame names " + seat.getKey() + "'s hand card " + name);
            }
        }
        assertTrue(hidden > 0, "the oracle must scan real hidden cards");
    }

    private static Set<String> playerTargetIds(JsonObject legal) {
        Set<String> out = new HashSet<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta != null && meta.has("object_id")) {
                out.add(meta.get("object_id").getAsString());
            }
        }
        return out;
    }

    private static JsonObject playerTargetAction(JsonObject legal, UUID player) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta != null && meta.has("object_id")
                    && player.toString().equals(meta.get("object_id").getAsString())) {
                return element.getAsJsonObject();
            }
        }
        fail("player " + player + " not offered as a target: " + legal);
        return null;
    }

    // ------------------------------------------------------------- point 5

    /**
     * F5-5 attacks on several defenders, at the two far seats. P1 attacks
     * P(N-1) with Raging Goblin and PN with Hellrider (Oracle: "Haste. Whenever
     * a creature you control attacks, this creature deals 1 damage to the
     * player or planeswalker it's attacking."); every opponent controls a
     * Grizzly Bears.
     * <ul>
     *   <li>Every attack decision offers every opponent P2..PN as defender
     *       (range {@code ALL}, attack option {@code MULTIPLE}; the same holds
     *       in {@link XmageMultiplayerAttackLimitTest} at 3–6 seats).</li>
     *   <li>CR 802.4a: P(N-1)'s Bears is offered exactly the Goblin, PN's Bears
     *       exactly Hellrider; P2..P(N-2) are never asked to block.</li>
     *   <li>P(N-1) blocks: 39 (Hellrider trigger), the Goblin dies; PN 36
     *       (trigger plus 3 combat damage); everyone else 40.</li>
     * </ul>
     * The near-seat version (P2, P3) at 3–6 seats is
     * {@link XmageMultiplayerSplitCombatTest}.
     */
    @ParameterizedTest(name = "F5-5 two far defenders: {0} players")
    @ValueSource(ints = {5, 6})
    void point5EachFarDefenderMayBlockOnlyTheCreatureAttackingThem(int playerCount) {
        String last = "P" + playerCount;
        String prev = "P" + (playerCount - 1);
        String tag = "f5-5-far-defenders-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(bf("P1", GOBLIN));
        objects.add(bf("P1", HELLRIDER));
        for (int seat = 2; seat <= playerCount; seat++) {
            objects.add(bf("P" + seat, BEARS));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();
        Map<String, UUID> ids = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> ids.put(pid, player.getId()));
        Set<String> opponents = new HashSet<>();
        for (int seat = 2; seat <= playerCount; seat++) {
            opponents.add(ids.get("P" + seat).toString());
        }
        Map<String, String> attackAt = Map.of(GOBLIN, prev, HELLRIDER, last);

        Map<String, List<String>> blockOffers = new LinkedHashMap<>();
        int attackDecisions = 0;
        boolean combatOver = false;
        for (int step = 0; step < 240 && !combatOver; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = session.legalActionsPayload();
            switch (cls) {
                case "priority" -> {
                    if (game.getStep().getType() == PhaseStep.END_COMBAT) {
                        combatOver = true;
                        break;
                    }
                    XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                }
                case "declare_attacker" -> {
                    assertEquals("P1", actor);
                    assertEquals(opponents, defenderIds(legal),
                            "every opponent P2.." + last + " is offered as defender");
                    attackDecisions++;
                    String attacker = attackerName(legal);
                    XmageFullGameTaxExecutionTest.submit(session, tag + "-attack-" + step,
                            attackOption(legal, ids.get(attackAt.get(attacker))));
                }
                case "trigger_order" -> XmageFullGameTaxExecutionTest.submit(session,
                        tag + "-order-" + step, equivalentHellriderTrigger(legal));
                case "declare_blocker" -> {
                    List<String> offered = new ArrayList<>();
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                                .getAsJsonObject("xmage_option_metadata");
                        Permanent attacker = game.getPermanent(
                                UUID.fromString(meta.get("attacker_id").getAsString()));
                        offered.add(attacker.getName());
                    }
                    assertTrue(blockOffers.put(actor, offered) == null,
                            actor + " is asked once for its one Bears");
                    if (prev.equals(actor)) {
                        blockWithEveryOffer(session, tag + "-block-" + step);
                    } else {
                        XmageActualCardCorpusTest.chooseNone(started, tag + "-noblock-" + step);
                    }
                }
                default -> fail("unexpected decision " + cls + " for " + actor);
            }
        }
        assertTrue(combatOver, "combat reached its end step");
        assertEquals(2, attackDecisions, "one attack decision per creature");
        assertEquals(Map.of(prev, List.of(GOBLIN), last, List.of(HELLRIDER)), blockOffers,
                "CR 802.4a: each far defender is offered only its own attacker; "
                        + "unattacked players are not asked");
        assertEquals(39, started.seats().get(prev).getLife(),
                prev + ": 1 from Hellrider's trigger for the Goblin; the Goblin was blocked");
        assertEquals(36, started.seats().get(last).getLife(),
                last + ": 1 from Hellrider's own trigger plus 3 unblocked combat damage");
        for (int seat = 1; seat <= playerCount - 2; seat++) {
            assertEquals(40, started.seats().get("P" + seat).getLife(),
                    "P" + seat + " was not attacked");
        }
        assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, "P1", GOBLIN),
                "the Goblin died to " + prev + "'s blocking Bears");
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, prev, BEARS));
    }

    private static Set<String> defenderIds(JsonObject legal) {
        Set<String> out = new HashSet<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta != null && meta.has("defender_id")) {
                out.add(meta.get("defender_id").getAsString());
            }
        }
        return out;
    }

    private static String attackerName(JsonObject legal) {
        String name = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta == null || !meta.has("name")) {
                continue;
            }
            String candidate = meta.get("name").getAsString();
            assertTrue(name == null || name.equals(candidate), "one attacker per decision");
            name = candidate;
        }
        assertNotNull(name);
        return name;
    }

    private static JsonObject attackOption(JsonObject legal, UUID defender) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta != null && meta.has("defender_id")
                    && defender.toString().equals(meta.get("defender_id").getAsString())) {
                return element.getAsJsonObject();
            }
        }
        fail("attack at " + defender + " not offered: " + legal);
        return null;
    }

    /** Both triggers are Hellrider's own and rules-equivalent; take the lowest id. */
    private static JsonObject equivalentHellriderTrigger(JsonObject legal) {
        JsonObject chosen = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata");
            JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
            assertEquals(HELLRIDER, engine.get("source_name").getAsString(),
                    "only Hellrider triggers are ordered");
            if (chosen == null || meta.get("option_id").getAsString().compareTo(
                    chosen.getAsJsonObject("metadata").get("option_id").getAsString()) < 0) {
                chosen = action;
            }
        }
        assertNotNull(chosen);
        return chosen;
    }

    private static void blockWithEveryOffer(XmageFullGameSession session, String tag) {
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        JsonArray selected = new JsonArray();
        String first = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            String optionId = element.getAsJsonObject().getAsJsonObject("metadata")
                    .get("option_id").getAsString();
            selected.add(optionId);
            first = first == null ? optionId : first;
        }
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", decisionId + ":" + first);
        proposal.addProperty("action_type", "declare_blockers");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", selected);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        session.submitAction(proposal);
    }

    // ------------------------------------------------------------- point 6

    /**
     * F5-6 several concedes down to the last player. While P1 holds priority
     * on its turn, PN, P(N-1), ..., P2 concede one after another. After each
     * concede with two or more players left, the conceder is out and the game
     * goes on. After the last one, P1 is the only player left and wins
     * (CR 104.2a). Basis for that expectation: the native sole-survivor win
     * after losses in {@link XmageCausalEliminationReconstructionTest} (four
     * seats); the concede path at 5/6 seats is the assumption under test here.
     * When exactly the engine ends the game (at the concede, or once P1's open
     * priority is answered) is not asserted: the test answers P1's pass for at
     * most a few frames and then requires the terminal state.
     */
    @ParameterizedTest(name = "F5-6 concede chain to the last player: {0} players")
    @ValueSource(ints = {5, 6})
    void point6ConcedesDownToTheLastPlayerLeaveThatPlayerTheWinner(int playerCount) {
        String tag = "f5-6-concede-chain-" + playerCount + "p";
        XmageActualCardCorpusTest.Started started = XmageActualCardCorpusTest.start(
                tag, playerCount, List.of(bf("P1", MOUNTAIN)));
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();
        Set<String> departed = new HashSet<>();
        for (int seat = playerCount; seat >= 3; seat--) {
            String pid = "P" + seat;
            concede(started, pid);
            departed.add(pid);
            assertFalse(started.seats().get(pid).isInGame(), pid + " left the game");
            assertFalse(game.hasEnded(), (seat - 1) + " players remain, the game goes on");
            JsonObject pending = session.pendingDecisionPayload();
            assertTrue(pending.get("failure").isJsonNull(), "the lane goes on");
            assertFalse(pending.get("decision").isJsonNull(), "the remaining players decide on");
            assertFalse(departed.contains(XmageActualCardCorpusTest.actorPid(started)),
                    "no departed seat is asked");
        }
        concede(started, "P2");
        departed.add("P2");
        for (int step = 0; step < 10; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject decision = payload.getAsJsonObject("decision");
            boolean leftFrame = decision.has("context") && decision.get("context").isJsonObject()
                    && decision.getAsJsonObject("context").has("actor_left_game")
                    && decision.getAsJsonObject("context").get("actor_left_game").getAsBoolean();
            assertTrue("P1".equals(actor) || (departed.contains(actor) && leftFrame),
                    "only P1, or a departed seat's re-issued pass frame, may be open: " + actor);
            assertEquals("priority", decision.get("decision_class").getAsString());
            XmageActualCardCorpusTest.pass(started, tag + "-drain-" + step);
        }
        JsonObject terminal = session.pendingDecisionPayload();
        assertTrue(terminal.get("decision").isJsonNull(), "the game is over");
        assertTrue(game.hasEnded(), "the engine ended the game");
        assertTrue(started.seats().get("P1").hasWon(), "104.2a: the last player left wins");
        for (String pid : departed) {
            Player player = started.seats().get(pid);
            assertFalse(player.hasWon(), pid + " did not win");
            assertTrue(player.hasLost() || player.hasLeft(), pid + " lost or left");
        }
        int winners = 0;
        for (JsonElement element : terminal.getAsJsonArray("outcomes")) {
            winners += element.getAsJsonObject().get("won").getAsBoolean() ? 1 : 0;
        }
        assertEquals(1, winners, "exactly one published winner");
    }

    /**
     * F5-6 everyone loses at once at six seats: a draw (CR 104.4a). Same
     * scenario body as {@link XmageMultiplayerSimultaneousLossTest}, which
     * runs 3–5 seats for the draw; its "some lose, the rest play on" case
     * already runs at 4–6.
     */
    @Test
    void point6EveryoneLosingAtOnceAtSixSeatsIsADraw() {
        new XmageMultiplayerSimultaneousLossTest().everyoneLosingAtOnceIsADraw(6);
    }

    // ------------------------------------------------------------- point 7

    /**
     * F5-7 seat and turn order. From P1's turn the turns pass P1, P2, ..., PN
     * and then wrap to P1 (F-41: the engine runs turns in seat order), one turn number
     * each.
     */
    @ParameterizedTest(name = "F5-7 full round: {0} players")
    @ValueSource(ints = {5, 6})
    void point7TurnsPassThroughEverySeatAndWrapFromTheLastSeatToP1(int playerCount) {
        XmageActualCardCorpusTest.Started started = XmageActualCardCorpusTest.start(
                "f5-7-round-" + playerCount + "p", playerCount, List.of(bf("P1", MOUNTAIN)));
        List<String> turns = turnsUntilP1Again(started, Set.of(), "f5-7-round-" + playerCount);
        List<String> expected = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            expected.add("P" + seat);
        }
        expected.add("P1");
        assertEquals(expected, turns, "turns in seat order, wrapping from P" + playerCount);
        assertEquals(playerCount + 1, started.session().restorationGame().getState().getTurnNum(),
                "one turn number per turn taken");
    }

    /**
     * F5-7 a departed seat takes no turn (CR 800.4a; the same skip as in
     * {@link XmageMultiplayerSimultaneousLossTest} at 4–6 seats, there for P2).
     * P(N-1) concedes during P1's turn: the turns are P1, ..., P(N-2), PN and
     * then P1 again, so the wrap from the last seat still happens.
     */
    @ParameterizedTest(name = "F5-7 departed seat skipped: {0} players")
    @ValueSource(ints = {5, 6})
    void point7ADepartedSeatTakesNoTurnAndTheLastSeatStillWrapsToP1(int playerCount) {
        String departed = "P" + (playerCount - 1);
        String tag = "f5-7-skip-" + playerCount + "p";
        XmageActualCardCorpusTest.Started started = XmageActualCardCorpusTest.start(
                tag, playerCount, List.of(bf("P1", MOUNTAIN)));
        concede(started, departed);
        assertFalse(started.seats().get(departed).isInGame(), departed + " left the game");
        List<String> turns = turnsUntilP1Again(started, Set.of(departed), tag);
        List<String> expected = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            if (seat != playerCount - 1) {
                expected.add("P" + seat);
            }
        }
        expected.add("P1");
        assertEquals(expected, turns, departed + " takes no turn; P" + playerCount + " wraps to P1");
        assertEquals(playerCount, started.session().restorationGame().getState().getTurnNum(),
                "a departed seat's turn does not begin, so it uses no turn number");
    }

    /** Passes priority (and discards Mountains at cleanup) until P1 is active again. */
    private static List<String> turnsUntilP1Again(XmageActualCardCorpusTest.Started started,
            Set<String> departed, String tag) {
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();
        List<String> turns = new ArrayList<>();
        for (int step = 0; step < 3000; step++) {
            String active = XmageNativeStateRestorationTest.pidOf(
                    started.seats(), game.getActivePlayerId().toString());
            if (turns.isEmpty() || !turns.get(turns.size() - 1).equals(active)) {
                turns.add(active);
            }
            if (turns.size() > 1 && "P1".equals(active)) {
                return turns;
            }
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            if (departed.contains(actor)) {
                JsonObject decision = session.pendingDecisionPayload().getAsJsonObject("decision");
                boolean leftFrame = decision.has("context") && decision.get("context").isJsonObject()
                        && decision.getAsJsonObject("context").has("actor_left_game")
                        && decision.getAsJsonObject("context").get("actor_left_game").getAsBoolean();
                assertTrue(leftFrame, "a departed seat gets at most its re-issued pass frame");
            }
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                case "choose_object" -> {
                    assertEquals(PhaseStep.CLEANUP, game.getStep().getType(), "only cleanup discards");
                    XmageActualCardCorpusTest.chooseNamed(started, tag + "-discard-" + step,
                            MOUNTAIN, Math.max(1, session.pendingDecisionPayload()
                                    .getAsJsonObject("decision").get("minimum_selections").getAsInt()));
                }
                default -> fail("unexpected decision " + cls + " for " + actor
                        + " at " + game.getStep().getType());
            }
        }
        fail("P1 never became active again; turns so far " + turns);
        return turns;
    }

    // ------------------------------------------------------------- point 8

    /**
     * F5-8 replay, bridge side only: two runs with the same Rules seed at six
     * seats in one JVM give the identical decision transcript and final zones
     * (scenario body of {@link XmageMultiplayerApnapReplayTest}, which runs 4
     * and 5 seats). This is not a replay-tape claim (the tape is Python-side
     * and takes at most five seats) and not a cross-JVM claim (#1715).
     */
    @Test
    void point8TwinRunsAtSixSeatsGiveTheSameTranscriptInOneJvm() {
        new XmageMultiplayerApnapReplayTest().twinRunsProduceTheSameTranscriptAndZones(6);
    }

    // ------------------------------------------------------------- shared

    private static XmageNativeStateRestoration.RequestedObject bf(String pid, String name) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-0-" + name.replaceAll("[^A-Za-z]", ""), name, pid, pid,
                Zone.BATTLEFIELD, false);
    }

    private static void concede(XmageActualCardCorpusTest.Started started, String pid) {
        XmageFullGameSession session = started.session();
        String principal = started.seats().get(pid).getId().toString();
        assertTrue(session.concedeOfferPayload(principal).get("concede_available").getAsBoolean(),
                pid + " may concede");
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "concede-" + pid);
        proposal.addProperty("actor_id", principal);
        proposal.addProperty("player_id", principal);
        assertEquals(principal, session.submitConcede(proposal)
                .get("conceded_actor_id").getAsString());
    }
}
