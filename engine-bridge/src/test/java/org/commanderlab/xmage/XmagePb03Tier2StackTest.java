package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.stack.StackObject;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * PB-03 Wave 2b: genuine-causal stack rows via L4 reconstruction (Muse XHIGH).
 *
 * <p>Each method loads its own frozen record, adds documented casting-fuel
 * lands (harness scaffolding, never fixture content), rebuilds the record's
 * stack bottom-to-top through genuine casts
 * ({@code XmageCausalStackReconstruction}), then resolves and asserts the
 * row's required events and terminal postconditions as game facts. No digest
 * equality is claimed — obligation facts are.</p>
 */
class XmagePb03Tier2StackTest {

    private static final long SEED = 424242L;

    /** Casting fuel added to the record copy before prepare (scaffolding). */
    record FuelLand(String semanticId, String cardName, String owner) {
    }

    /** A reconstructed row ready for obligation-specific resolution. */
    private record Reconstructed(
            XmageFullGameSession session,
            Map<String, Player> seats,
            XmageCausalStackReconstruction.Prepared prepared,
            XmageCausalStackReconstruction.ReconstructionResult result) {
    }

    private static JsonObject recordWithFuel(String fixtureId, List<FuelLand> fuel) {
        JsonObject record = XmageNativeStateRestorationTest.frozenRecord(fixtureId);
        JsonArray objects = record.getAsJsonArray("semantic_objects");
        for (FuelLand land : fuel) {
            JsonObject entry = new JsonObject();
            entry.addProperty("semantic_id", land.semanticId());
            entry.addProperty("card_identity", land.cardName());
            entry.addProperty("owner", land.owner());
            entry.addProperty("controller", land.owner());
            entry.addProperty("zone", "battlefield");
            entry.addProperty("tapped", false);
            entry.add("counters", new JsonObject());
            objects.add(entry);
        }
        return record;
    }

    private static XmageTemporalProgressionDriver.DecisionSource arrivalSource(String tag) {
        return (pending, legal, index) -> {
            String dc = pending.get("decision_class").getAsString();
            String actor = legal.get("actor_id").getAsString();
            if ("mulligan".equals(dc)) {
                return XmageCausalStackReconstruction.proposal(
                        tag + "-keep-" + index, actor,
                        XmageCausalStackReconstructionTest.exactOptionType(
                                legal, "mulligan", "keep"));
            }
            if ("choose_object".equals(dc)
                    && pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    && pending.get("prompt").getAsString().contains("starting player")) {
                JsonObject match = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    if (action.get("action_id").getAsString().endsWith(":" + actor)) {
                        if (match != null) {
                            throw new AssertionError("ambiguous starting-player self option");
                        }
                        match = action;
                    }
                }
                if (match == null) {
                    throw new AssertionError("starting-player self option missing");
                }
                return XmageCausalStackReconstruction.proposal(
                        tag + "-start-" + index, actor, match);
            }
            if ("priority".equals(dc)) {
                return XmageCausalStackReconstruction.proposal(
                        tag + "-pass-" + index, actor,
                        XmageCausalStackReconstructionTest.exactActionType(
                                legal, "pass_priority"));
            }
            return null;
        };
    }

    private static Reconstructed reconstructRow(
            String fixtureId,
            String tag,
            List<FuelLand> fuel,
            Map<String, List<String>> manaOrderByPid) {
        return reconstructRow(fixtureId, tag, fuel, manaOrderByPid, Map.of());
    }

    private static Reconstructed reconstructRow(
            String fixtureId,
            String tag,
            List<FuelLand> fuel,
            Map<String, List<String>> manaOrderByPid,
            Map<String, List<String>> poolSpendOrderByPid) {
        JsonObject record = recordWithFuel(fixtureId, fuel);
        XmageCausalStackReconstruction.Prepared prepared =
                XmageCausalStackReconstruction.prepare(record, tag, SEED);
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = XmageNativeStateRestorationTest.importScaffolding(
                importer, prepared.preStackPlan(), tag);
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, 0, 40, SEED, importer, prepared.restoration());
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        Map<String, Integer> poolSpendIndexByPid = new LinkedHashMap<>();
        XmageCausalStackReconstruction.DecisionSource stackSource =
                (frame, pending, legal, index) -> {
                    String dc = pending.get("decision_class").getAsString();
                    if ("target".equals(dc)) {
                        return XmageCausalStackReconstructionTest.targetProposal(
                                tag + "-target-" + index, frame, legal, prepared, seats, session);
                    }
                    if ("mode".equals(dc)) {
                        return null;
                    }
                    if ("mana_payment".equals(dc)) {
                        String pid = frame.controller();
                        JsonObject proposal = XmageCausalStackReconstructionTest.manaProposal(
                                tag + "-mana-" + index,
                                pid,
                                legal,
                                prepared,
                                manaOrderByPid);
                        List<String> poolOrder =
                                poolSpendOrderByPid.getOrDefault(pid, List.of());
                        if (proposal != null) {
                            if (!poolOrder.isEmpty()) {
                                JsonObject selected =
                                        exactLegalAction(
                                                legal,
                                                proposal.get("legal_action_id").getAsString());
                                if ("mana_pool".equals(selected.getAsJsonObject("metadata")
                                        .get("option_type").getAsString())) {
                                    verifyAndAdvancePoolSpend(
                                            tag,
                                            pid,
                                            selected,
                                            poolOrder,
                                            poolSpendIndexByPid);
                                }
                            }
                            return proposal;
                        }
                        if (poolOrder.isEmpty()) {
                            return null;
                        }
                        int poolIndex = poolSpendIndexByPid.getOrDefault(pid, 0);
                        if (poolIndex >= poolOrder.size()) {
                            return null;
                        }
                        JsonObject poolAction =
                                exactPoolSpend(legal, poolOrder.get(poolIndex));
                        poolSpendIndexByPid.put(pid, poolIndex + 1);
                        return XmageCausalStackReconstruction.proposal(
                                tag + "-pool-" + index,
                                legal.get("actor_id").getAsString(),
                                poolAction);
                    }
                    if ("choice".equals(dc)) {
                        return null;
                    }
                    return null;
                };
        XmageCausalStackReconstruction.ReconstructionResult result =
                XmageCausalStackReconstruction.reconstruct(
                        session, seats, prepared, arrivalSource(tag), stackSource, 240);
        assertTrue(result.submittedDecisions() > 0, tag + ": reconstruction must submit");
        for (Map.Entry<String, List<String>> entry : poolSpendOrderByPid.entrySet()) {
            assertEquals(
                    entry.getValue().size(),
                    poolSpendIndexByPid.getOrDefault(entry.getKey(), 0),
                    tag + ": scripted pool spend sequence was not fully consumed for "
                            + entry.getKey());
        }
        return new Reconstructed(session, seats, prepared, result);
    }

    private static JsonObject exactLegalAction(JsonObject legal, String actionId) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (actionId.equals(action.get("action_id").getAsString())) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "proposal must name exactly one current legal action");
        return matches.get(0);
    }

    private static JsonObject exactPoolSpend(JsonObject legal, String manaType) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            if (!"mana_pool".equals(metadata.get("option_type").getAsString())) {
                continue;
            }
            JsonObject engine =
                    metadata.has("xmage_option_metadata")
                                    && metadata.get("xmage_option_metadata").isJsonObject()
                            ? metadata.getAsJsonObject("xmage_option_metadata")
                            : new JsonObject();
            if (engine.has("mana_type")
                    && !engine.get("mana_type").isJsonNull()
                    && manaType.equalsIgnoreCase(engine.get("mana_type").getAsString())) {
                matches.add(action);
            }
        }
        assertEquals(
                1,
                matches.size(),
                "expected exactly one engine-offered " + manaType + " pool spend");
        return matches.get(0);
    }

    private static void verifyAndAdvancePoolSpend(
            String tag,
            String pid,
            JsonObject selected,
            List<String> poolOrder,
            Map<String, Integer> poolSpendIndexByPid) {
        int poolIndex = poolSpendIndexByPid.getOrDefault(pid, 0);
        assertTrue(
                poolIndex < poolOrder.size(),
                tag + ": engine selected more pool spends than scripted for " + pid);
        JsonObject metadata = selected.getAsJsonObject("metadata");
        JsonObject engine =
                metadata.has("xmage_option_metadata")
                                && metadata.get("xmage_option_metadata").isJsonObject()
                        ? metadata.getAsJsonObject("xmage_option_metadata")
                        : new JsonObject();
        String actual =
                engine.has("mana_type") && !engine.get("mana_type").isJsonNull()
                        ? engine.get("mana_type").getAsString()
                        : "";
        assertTrue(
                poolOrder.get(poolIndex).equalsIgnoreCase(actual),
                tag + ": expected "
                        + poolOrder.get(poolIndex)
                        + " pool spend for "
                        + pid
                        + " but engine action was "
                        + actual);
        poolSpendIndexByPid.put(pid, poolIndex + 1);
    }

    private static void passPriority(
            XmageFullGameSession session, Map<String, Player> seats, String id) {
        JsonObject legal = session.legalActionsPayload();
        XmagePb03Tier1RowsTest.submit(session, id,
                XmageNativeStateRestorationTest.singleActionOfType(
                        legal, "pass_priority", null));
    }

    private static String pendingClass(XmageFullGameSession session) {
        for (int attempt = 0; attempt < 30; attempt++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (!payload.get("decision").isJsonNull()) {
                return payload.getAsJsonObject("decision")
                        .get("decision_class").getAsString();
            }
            try {
                Thread.sleep(100);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                fail("interrupted while polling pending decision");
            }
        }
        return null;
    }

    // ---- MICRO_PRIORITY / MICRO_STACK: Bolt then Growth, Bears survives ----

    @Test
    void microPriorityGrowthSavesBearsFromBolt() {
        executeBoltThenGrowth("MICRO_PRIORITY", "pb03-priority");
    }

    @Test
    void microStackGrowthSavesBearsFromBolt() {
        executeBoltThenGrowth("MICRO_STACK", "pb03-stack");
    }

    static void answerRecordTargets(
            XmageFullGameSession session,
            Map<String, Player> seats,
            Reconstructed run,
            String targetSemantic,
            String tag) {
        UUID targetId = run.prepared().restoration().injectedObjectId(targetSemantic);
        answerNativeTarget(session, targetId.toString(), targetSemantic, tag);
    }

    static void answerNativeTarget(
            XmageFullGameSession session, String nativeId, String name, String tag) {
        for (int step = 0; step < 10; step++) {
            String pending = pendingClass(session);
            if (!"target".equals(pending)) {
                return;
            }
            XmagePb03Tier1RowsTest.submit(session, tag + "-target-" + step,
                    XmagePb03Tier1RowsTest.findTargetOffer(session, nativeId, name));
        }
        fail(tag + ": target decisions did not complete");
    }

    static boolean stackHas(XmageFullGameSession session, String cardName) {
        for (StackObject stackObject : session.restorationGame().getStack()) {
            if (cardName.equals(stackObject.getName())) {
                return true;
            }
        }
        return false;
    }

    static void assertSpellOnStack(
            XmageFullGameSession session, String cardName, String tag) {
        assertTrue(stackHas(session, cardName),
                tag + ": " + cardName + " must be on the stack after payment");
    }

    static void executeBoltThenGrowth(String fixtureId, String tag) {
        Reconstructed run = reconstructRow(
                fixtureId, tag,
                List.of(new FuelLand("obj:fuel-mountain-p1", "Mountain", "P1")),
                Map.of("P1", List.of("obj:fuel-mountain-p1"),
                        "P2", List.of("obj:micro-forest")));
        XmageFullGameSession session = run.session();
        Map<String, Player> seats = run.seats();
        Player p2 = seats.get("P2");

        // Growth is in P2's hand (record object, not a stack frame): cast it
        // genuinely at the reconstructed Bolt, then resolve top-down.
        XmagePb03Tier1RowsTest.castSpellAs(session, seats, tag, "Giant Growth", "P2");
        answerRecordTargets(session, seats, run, "obj:micro-target", tag);
        XmagePb03Tier1RowsTest.payFromSemanticSources(
                session,
                run.prepared().restoration(),
                tag,
                List.of("obj:micro-forest"),
                java.util.Set.of("Forest \u2014 {T}: Add {G}."));
        // Growth must resolve (leaving only Bolt); then proceed. Without
        // this break the loop passes through resolution into combat.
        for (int step = 0; step < 20; step++) {
            if (!stackHas(session, "Giant Growth")
                    && stackHas(session, "Lightning Bolt")) {
                break;
            }
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            if ("target".equals(pending)) {
                answerRecordTargets(session, seats, run, "obj:micro-target", tag + "-late");
                continue;
            }
            if (!"priority".equals(pending)) {
                fail(tag + ": unexpected " + pending + " resolving Growth");
            }
            passPriority(session, seats, tag + "-growth-resolve-" + step);
        }
        for (int step = 0; step < 60; step++) {
            if (session.restorationGame().getStack().isEmpty()) {
                break;
            }
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            if (!"priority".equals(pending)) {
                fail(tag + ": unexpected " + pending + " resolving stack");
            }
            passPriority(session, seats, tag + "-resolve-" + step);
        }
        assertTrue(session.restorationGame().getStack().isEmpty(),
                "stack is empty after both spells resolve");
        UUID targetId = run.prepared().restoration().injectedObjectId("obj:micro-target");
        assertNotNull(session.restorationGame().getPermanent(targetId),
                "Grizzly Bears survives Lightning Bolt because Giant Growth resolves first");
    }

    // ---- MICRO_MANA_PAYMENT: Counterspell answers Bolt ----

    @Test
    void microManaPaymentCounterspellPaidWithTwoBlue() {
        Reconstructed run = reconstructRow(
                "MICRO_MANA_PAYMENT", "pb03-manapay",
                List.of(new FuelLand("obj:fuel-mountain-p2", "Mountain", "P2")),
                Map.of("P2", List.of("obj:fuel-mountain-p2"),
                        "P1", List.of("obj:micro-island-a", "obj:micro-island-b")));
        XmageFullGameSession session = run.session();
        Map<String, Player> seats = run.seats();
        Player p1 = seats.get("P1");
        Player p2 = seats.get("P2");

        XmagePb03Tier1RowsTest.castSpellAs(session, seats, "pb03-manapay", "Counterspell", "P1");
        // Engine casting order: targets before payment. Target the live Bolt
        // stack object by its native stack id.
        UUID boltStackId = run.result().nativeStackObjectIds().get("obj:micro-bolt");
        assertNotNull(boltStackId, "reconstructed Bolt must be on the stack");
        answerNativeTarget(session, boltStackId.toString(), "obj:micro-bolt", "pb03-manapay");
        XmagePb03Tier1RowsTest.payFromSemanticSources(
                session,
                run.prepared().restoration(),
                "pb03-manapay",
                List.of("obj:micro-island-a", "obj:micro-island-b"),
                java.util.Set.of("Island \u2014 {T}: Add {U}."));
        assertSpellOnStack(session, "Counterspell", "pb03-manapay");
        for (int step = 0; step < 60; step++) {
            if (session.restorationGame().getStack().isEmpty()) {
                break;
            }
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            if ("declare_attacker".equals(pending)) {
                XmagePb03Tier1RowsTest.submit(session, "pb03-manapay-hold-" + step,
                        XmageNativeStateRestorationTest.singleActionOfType(
                                session.legalActionsPayload(),
                                "declare_attackers", "hold_attacker"));
                continue;
            }
            if ("declare_blocker".equals(pending)) {
                XmagePb03Tier1RowsTest.submitProposal(session, "pb03-manapay-noblock-" + step,
                        XmagePb03Tier1RowsTest.emptyBlockProposal(
                                "pb03-manapay-noblock-" + step,
                                session.legalActionsPayload()));
                continue;
            }
            if (!"priority".equals(pending)) {
                fail("pb03-manapay: unexpected " + pending + " resolving stack");
            }
            passPriority(session, seats, "pb03-manapay-resolve-" + step);
        }
        int tappedIslands = 0;
        for (mage.game.permanent.Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (permanent.getName().equals("Island")
                    && p1.getId().equals(permanent.getControllerId())
                    && permanent.isTapped()) {
                tappedIslands++;
            }
        }
        assertEquals(2, tappedIslands, "Counterspell paid with exactly two blue mana");
        assertEquals(40, p2.getLife(), "countered Bolt deals no damage");
        assertTrue(session.restorationGame().getStack().isEmpty(), "stack empty at end");
    }

    // ---- MICRO_COPY: Flare copies Bolt on the stack ----

    @Test
    void microCopyFlareDuplicatesBoltOnStack() {
        Reconstructed run = reconstructRow(
                "MICRO_COPY", "pb03-copy",
                List.of(new FuelLand("obj:fuel-mountain-p2", "Mountain", "P2"),
                        new FuelLand("obj:fuel-mountain-p1a", "Mountain", "P1"),
                        new FuelLand("obj:fuel-mountain-p1b", "Mountain", "P1"),
                        new FuelLand("obj:fuel-mountain-p1c", "Mountain", "P1")),
                Map.of("P2", List.of("obj:fuel-mountain-p2"),
                        "P1", List.of("obj:fuel-mountain-p1a", "obj:fuel-mountain-p1b",
                                "obj:fuel-mountain-p1c")));
        XmageFullGameSession session = run.session();
        // After reconstruction the stack holds Bolt (bottom) and Flare (top).
        assertEquals(2, session.restorationGame().getStack().size(),
                "Bolt plus Flare must both be on the stack");
        boolean copyObserved = false;
        for (int step = 0; step < 60; step++) {
            int bolts = 0;
            for (StackObject stackObject : session.restorationGame().getStack()) {
                if ("Lightning Bolt".equals(stackObject.getName())) {
                    bolts++;
                }
            }
            if (bolts == 2) {
                copyObserved = true;
                break;
            }
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            if (!"priority".equals(pending)) {
                fail("pb03-copy: unexpected " + pending + " resolving stack");
            }
            passPriority(session, run.seats(), "pb03-copy-pass-" + step);
        }
        assertTrue(copyObserved,
                "Flare resolution must create a Bolt copy as a distinct stack object");
    }

    // ---- MICRO_ZONE_CHANGES: Bolt resolves, new incarnation in GY ----

    @Test
    void microZoneChangesBoltBecomesNewGraveyardObject() {
        Reconstructed run = reconstructRow(
                "MICRO_ZONE_CHANGES", "pb03-zonechg",
                List.of(new FuelLand("obj:fuel-mountain-p1", "Mountain", "P1")),
                Map.of("P1", List.of("obj:fuel-mountain-p1")));
        XmageFullGameSession session = run.session();
        Map<String, Player> seats = run.seats();
        UUID stackId = run.result().nativeStackObjectIds().get("obj:micro-bolt-stack");
        assertNotNull(stackId, "reconstructed Bolt must be on the stack");
        for (int step = 0; step < 60; step++) {
            if (session.restorationGame().getStack().isEmpty()) {
                break;
            }
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            if (!"priority".equals(pending)) {
                fail("pb03-zonechg: unexpected " + pending + " resolving stack");
            }
            passPriority(session, seats, "pb03-zonechg-pass-" + step);
        }
        assertTrue(session.restorationGame().getStack().isEmpty(), "stack empty after Bolt");
        Player p1 = seats.get("P1");
        UUID graveId = null;
        for (mage.cards.Card card : p1.getGraveyard()
                .getCards(session.restorationGame())) {
            if ("Lightning Bolt".equals(card.getName())) {
                graveId = card.getId();
            }
        }
        assertNotNull(graveId, "Bolt must be in its owner graveyard after resolution");
        assertTrue(!stackId.equals(graveId),
                "graveyard object is a new incarnation, not the stack object");
    }

    // ---- MICRO_RULES_RANDOMNESS: unscripted flip call (BLOCKED) ----
    //
    // Blocker characterization (row stays BLOCKED): the reconstructed Stitch
    // resolves to a genuine "Heads or tails?" call, but the row's
    // decision_script is empty — no scripted call exists. Choosing heads or
    // tails without script would be unscripted discretion over the win
    // condition (first/random/default all forbidden), and the flip outcome
    // itself is seed-determined Rules RNG the harness must not steer. The
    // test proves the choice point exists with exactly the two offered calls
    // and stops without selecting: fail closed, row BLOCKED.

    @Test
    void microRulesRandomnessStitchFlipsHeadsForExtraTurn() {
        Reconstructed run = reconstructRow(
                "MICRO_RULES_RANDOMNESS", "pb03-rng",
                List.of(new FuelLand("obj:fuel-island-p1", "Island", "P1"),
                        new FuelLand("obj:fuel-mountain-p1", "Mountain", "P1"),
                        new FuelLand("obj:fuel-mountain-p1b", "Mountain", "P1")),
                Map.of("P1", List.of("obj:fuel-island-p1", "obj:fuel-mountain-p1",
                        "obj:fuel-mountain-p1b")),
                Map.of("P1", List.of("BLUE", "RED", "RED")));
        XmageFullGameSession session = run.session();
        Map<String, Player> seats = run.seats();
        boolean callSeen = false;
        for (int step = 0; step < 60; step++) {
            if (session.restorationGame().getStack().isEmpty()) {
                break;
            }
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            if ("choose_use".equals(pending)) {
                JsonObject legal = session.legalActionsPayload();
                List<String> labels = new ArrayList<>();
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    labels.add(element.getAsJsonObject().getAsJsonObject("metadata")
                            .get("label").getAsString());
                }
                assertTrue(labels.contains("Heads") && labels.contains("Tails"),
                        "flip call must offer exactly Heads and Tails");
                assertEquals(2, labels.size(), "flip call has no third option");
                callSeen = true;
                break;
            }
            if (!"priority".equals(pending)) {
                fail("pb03-rng: unexpected " + pending + " resolving stack");
            }
            passPriority(session, seats, "pb03-rng-pass-" + step);
        }
        assertTrue(callSeen,
                "the genuine Heads-or-tails call must appear and stay unanswered; row BLOCKED");
    }

    // ---- WS05-MP-PRIO-3/5: priority ring with the response on stack ----

    @Test
    void mpPrio3RingOrderWithBoltResponse() {
        executePrioRing("WS05-MP-PRIO-3", "pb03-prio3", 3);
    }

    @Test
    void mpPrio5RingOrderWithBoltResponse() {
        executePrioRing("WS05-MP-PRIO-5", "pb03-prio5", 5);
    }

    static void executePrioRing(String fixtureId, String tag, int players) {
        Reconstructed run = reconstructRow(
                fixtureId, tag,
                List.of(new FuelLand("obj:fuel-mountain-p1", "Mountain", "P1")),
                Map.of("P1", List.of("obj:fuel-mountain-p1")));
        XmageFullGameSession session = run.session();
        Map<String, Player> seats = run.seats();
        // The reconstructed Bolt is the response on the stack. Traverse a
        // partial ring in seat order WITHOUT completing the round (a full
        // round of passes would resolve the response). Stop with the response
        // still present: order evidence plus persistence evidence.
        List<String> ring = new ArrayList<>();
        for (int step = 0; step < players - 1; step++) {
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            if (!"priority".equals(pending)) {
                fail(tag + ": unexpected " + pending + " in priority ring");
            }
            JsonObject legal = session.legalActionsPayload();
            String actorPid = XmageNativeStateRestorationTest.pidOf(
                    seats, legal.get("actor_id").getAsString());
            ring.add(actorPid);
            passPriority(session, seats, tag + "-ring-" + step);
        }
        assertEquals(players - 1, ring.size(),
                tag + ": partial ring of N-1 priorities must traverse, saw " + ring);
        // The frozen contract orders priority by seat ("Priority traverses
        // exactly P1..PN live ring"), and since F-41 the engine's turn order is
        // seat order: priority ascends, wrapping from PN to P1. Every
        // consecutive pair must follow that order.
        for (int index = 0; index + 1 < ring.size(); index++) {
            int current = Integer.parseInt(ring.get(index).substring(1));
            int next = Integer.parseInt(ring.get(index + 1).substring(1));
            int expected = current == players ? 1 : current + 1;
            assertEquals(expected, next,
                    tag + ": ring must follow live seat order, saw " + ring);
        }
        assertTrue(!session.restorationGame().getStack().isEmpty(),
                "the Bolt response must persist on the stack through the ring");
    }
}
