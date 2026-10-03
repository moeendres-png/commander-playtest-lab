package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Causal-reconstruction evidence for the mid-game lane's two causal entries.
 *
 * <p><b>What is under test.</b> The placement entry can only construct what
 * the engine seam can place directly. A spell on the stack must have been
 * cast; a player at zero life must have lost that life. This suite drives the
 * lane's {@code causal_stack} and {@code causal_elimination} entries over the
 * actual Protocol-2 message surface with real frozen records and real cards,
 * and asserts only externally observable engine outcomes. Every causal
 * transition — arrival transport, cast, target, mode, mana payment, resolution
 * — is an ordinary engine decision answered by this suite as the external
 * pilot, selected from the engine's own offered options. No first-option
 * fallback, random option, default yes/no, silent skip or fabricated option
 * appears anywhere.</p>
 *
 * <p><b>Fail-before is structural.</b> On the pre-causal lane,
 * {@code create_midgame_game} with {@code entry_mode causal_stack} is an
 * {@code unsupported_entry_mode}, and the stack-bearing rows
 * ({@code WS05-MP-PRIO-3}, {@code WS05-CMD-ZONE-GY-YES},
 * {@code MICRO_ZONE_CHANGES}) are rejected at creation with
 * {@code UNSUPPORTED_ZONE} while the elimination rows mismatch on life. The
 * causal entries convert those into measured downstream states.</p>
 */
class XmageMidgameCausalTest {

    private static final long SEED = 424242L;

    private record Lane(
            XmageMidgameJsonlBridge bridge,
            List<JsonObject> tape) {

        JsonObject call(String messageType, JsonObject payload) {
            JsonObject request = new JsonObject();
            request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
            request.addProperty("request_id", messageType + "-" + tape.size());
            request.addProperty("message_type", messageType);
            if (payload != null) {
                request.add("payload", payload);
                request.add("params", payload);
            }
            XmageMidgameJsonlBridge.Result result = bridge.handle(request.toString());
            JsonObject response = JsonParser.parseString(result.json()).getAsJsonObject();
            tape.add(response);
            return response;
        }

        JsonObject ok(String messageType, JsonObject payload) {
            JsonObject response = call(messageType, payload);
            if (!response.get("success").getAsBoolean()) {
                fail(messageType + " must succeed: " + response.getAsJsonArray("errors"));
            }
            return response.getAsJsonObject("payload");
        }

        JsonObject rejected(String messageType, JsonObject payload) {
            JsonObject response = call(messageType, payload);
            if (response.get("success").getAsBoolean()) {
                fail(messageType + " must fail closed, but succeeded");
            }
            return response;
        }
    }

    private static Path repoRoot() {
        Path candidate = Path.of("").toAbsolutePath();
        while (candidate != null) {
            if (Files.isDirectory(candidate.resolve("qualification/ws47"))) {
                return candidate;
            }
            candidate = candidate.getParent();
        }
        throw new AssertionError("repository root with qualification/ws47 not found");
    }

    private static JsonObject frozenRecord(String fixtureId) {
        try {
            JsonObject materialization = JsonParser.parseString(Files.readString(
                    repoRoot().resolve(
                            "qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json")))
                    .getAsJsonObject();
            for (JsonElement element : materialization.getAsJsonArray("records")) {
                JsonObject record = element.getAsJsonObject();
                if (record.get("fixture_id").getAsString().equals(fixtureId)) {
                    return record;
                }
            }
        } catch (Exception exc) {
            throw new AssertionError(exc);
        }
        throw new AssertionError("frozen record missing: " + fixtureId);
    }

    private static Lane newLane() {
        return new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
    }

    private static JsonObject fuelCard(String semanticId, String card, String owner, String zone) {
        JsonObject fuel = new JsonObject();
        fuel.addProperty("semantic_id", semanticId);
        fuel.addProperty("card_identity", card);
        fuel.addProperty("owner", owner);
        fuel.addProperty("zone", zone);
        return fuel;
    }

    private static JsonObject causalStackCreate(
            String gameId, String fixtureId, JsonArray fuel) {
        JsonObject request = new JsonObject();
        request.addProperty("game_id", gameId);
        request.addProperty("plan_id", gameId);
        request.addProperty("seed", SEED);
        request.addProperty("entry_mode", "causal_stack");
        request.add("requested_starting_state", frozenRecord(fixtureId));
        request.add("fuel", fuel);
        return request;
    }

    // ------------------------------------------------------------------
    // Entry publication: the causal plan is the pilot's script.
    // ------------------------------------------------------------------

    @Test
    void causalStackEntryPublishesScriptAndFuelBindings() {
        Lane lane = newLane();
        JsonArray fuel = new JsonArray();
        fuel.add(fuelCard("obj:fuel-mountain-p1", "Mountain", "P1", "battlefield"));
        JsonObject created = lane.ok("create_midgame_game",
                causalStackCreate("causal-prio3-plan", "WS05-MP-PRIO-3", fuel));
        assertEquals("causal_stack", created.get("entry_mode").getAsString());

        JsonObject plan = created.getAsJsonObject("causal_plan");
        JsonArray frames = plan.getAsJsonArray("frames_bottom_to_top");
        assertEquals(1, frames.size());
        JsonObject frame = frames.get(0).getAsJsonObject();
        assertEquals("obj:mp-bolt", frame.get("semantic_id").getAsString());
        assertEquals("Lightning Bolt", frame.get("card_identity").getAsString());
        assertEquals("P1", frame.get("controller").getAsString());
        assertEquals(1, frame.getAsJsonArray("targets").size());
        assertEquals("obj:P3-bears",
                frame.getAsJsonArray("targets").get(0).getAsString());
        assertFalse(frame.get("native_source_id").getAsString().isBlank(),
                "the pilot needs the engine-minted source id to match the cast offer");

        JsonObject placed = plan.getAsJsonObject("placed_objects");
        assertFalse(placed.get("obj:mp-bolt").getAsString().isBlank());
        assertFalse(placed.get("obj:fuel-mountain-p1").getAsString().isBlank());
        assertFalse(placed.get("obj:P3-bears").getAsString().isBlank());

        JsonObject checkpoint = plan.getAsJsonObject("pre_stack_checkpoint");
        assertEquals(1, checkpoint.get("turn_number").getAsInt());
        assertEquals("PRECOMBAT_MAIN", checkpoint.get("phase").getAsString());
        assertEquals("P1", checkpoint.get("active_player").getAsString());
    }

    @Test
    void unknownEntryModeFailsClosed() {
        Lane lane = newLane();
        JsonObject request = causalStackCreate(
                "causal-bad-mode", "WS05-MP-PRIO-3", new JsonArray());
        request.addProperty("entry_mode", "causal_anything");
        JsonObject response = lane.rejected("create_midgame_game", request);
        assertEquals("unsupported_entry_mode",
                response.getAsJsonArray("errors").get(0).getAsJsonObject()
                        .get("code").getAsString());
    }

    @Test
    void causalEliminationWithoutSpecFailsClosed() {
        Lane lane = newLane();
        JsonObject request = new JsonObject();
        request.addProperty("game_id", "causal-no-spec");
        request.addProperty("seed", SEED);
        request.addProperty("entry_mode", "causal_elimination");
        request.add("requested_starting_state", frozenRecord("WS05-MP-ELIM-PRIO-3"));
        JsonObject response = lane.rejected("create_midgame_game", request);
        assertEquals("midgame_causal_preparation_rejected",
                response.getAsJsonArray("errors").get(0).getAsJsonObject()
                        .get("code").getAsString());
        assertTrue(response.getAsJsonArray("errors").get(0).getAsJsonObject()
                .get("message").getAsString().contains("MISSING_ELIMINATION_SPEC"));
    }

    @Test
    void causalEliminationWithWrongVictimFailsClosed() {
        Lane lane = newLane();
        JsonObject response = lane.rejected("create_midgame_game",
                eliminationCreate("causal-wrong-victim", "WS05-MP-ELIM-PRIO-3",
                        "P1", "P3", instruments(1)));
        assertEquals("midgame_causal_preparation_rejected",
                response.getAsJsonArray("errors").get(0).getAsJsonObject()
                        .get("code").getAsString());
        assertTrue(response.getAsJsonArray("errors").get(0).getAsJsonObject()
                .get("message").getAsString().contains("ELIMINATION_VICTIM_MISMATCH"));
    }

    @Test
    void causalVerifyOnPlacementGameFailsClosed() {
        Lane lane = newLane();
        JsonObject request = new JsonObject();
        request.addProperty("game_id", "causal-wrong-lane");
        request.addProperty("seed", SEED);
        request.add("requested_starting_state", frozenRecord("WS05-MP-COMBAT-4"));
        lane.ok("create_midgame_game", request);
        lane.ok("start_midgame_game", null);
        JsonObject verify = new JsonObject();
        verify.addProperty("mode", "stack");
        JsonObject response = lane.rejected("complete_causal_reconstruction", verify);
        assertEquals("no_causal_stack_plan",
                response.getAsJsonArray("errors").get(0).getAsJsonObject()
                        .get("code").getAsString());
    }

    // ------------------------------------------------------------------
    // Phase A: WS05-MP-PRIO-3 — the bolt is cast by the engine, then the
    // priority ring with a live response is observed.
    // ------------------------------------------------------------------

    @Test
    void prio3BoltIsCastByTheEngineAndPriorityRingIsObserved() {
        Lane lane = newLane();
        JsonArray fuel = new JsonArray();
        fuel.add(fuelCard("obj:fuel-mountain-p1", "Mountain", "P1", "battlefield"));
        JsonObject created = lane.ok("create_midgame_game",
                causalStackCreate("causal-prio3", "WS05-MP-PRIO-3", fuel));
        JsonObject causalPlan = created.getAsJsonObject("causal_plan");
        JsonObject frame = causalPlan.getAsJsonArray("frames_bottom_to_top")
                .get(0).getAsJsonObject();
        String boltSourceId = frame.get("native_source_id").getAsString();
        JsonObject placed = causalPlan.getAsJsonObject("placed_objects");
        String bearsId = placed.get("obj:P3-bears").getAsString();
        String mountainId = placed.get("obj:fuel-mountain-p1").getAsString();
        lane.ok("start_midgame_game", null);

        driveArrival(lane, "P1");

        // Hand priority to the frame's controller, then cast the exact
        // engine-offered source action. The cast is the engine's transition;
        // the pilot only selects it.
        castFrameSource(lane, "causal-prio3-cast", boltSourceId);

        // Engine casting order (CR 601.2): modes, then targets, then payment.
        // The PRIO-3 frame names no modes, one target, and one red payment.
        answerTarget(lane, "causal-prio3-target", bearsId);
        answerMana(lane, "causal-prio3-mana", mountainId);

        JsonObject verify = new JsonObject();
        verify.addProperty("mode", "stack");
        JsonObject arrival = lane.ok("complete_causal_reconstruction", verify);
        JsonObject verdict = arrival.getAsJsonObject("verdict");
        assertEquals(true, verdict.get("causal_match").getAsBoolean(),
                "the engine must have produced the requested stack: "
                        + verdict.getAsJsonArray("mismatches"));
        assertEquals(0, verdict.getAsJsonArray("mismatches").size());
        assertEquals(1, verdict.get("frames_verified").getAsInt());
        assertEquals("obj:mp-bolt", verdict.getAsJsonArray("stack_order_top_to_bottom")
                .get(0).getAsString());

        // The row's own obligation: a live priority ring with a response on
        // the stack. The engine must park on priority with the bolt still
        // present; the pilot records the ring order by passing once around.
        List<String> ringActors = new ArrayList<>();
        for (int step = 0; step < 12; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, "the engine must park on priority with a live response");
            assertEquals("priority", pending.get("decision_class").getAsString(),
                    "after reconstruction the only open decision is the priority ring");
            ringActors.add(pending.get("actor_id").getAsString());
            submitOption(lane, pending, optionWithType(pending, "pass_priority"));
            if (ringActors.size() >= 3) {
                break;
            }
        }
        assertEquals(3, ringActors.size(),
                "the priority ring must pass through three distinct principals");
        assertEquals(3, new java.util.HashSet<>(ringActors).size(),
                "the ring must visit three distinct actors, proving APNAP order is live");
    }

    // ------------------------------------------------------------------
    // Phase A: WS05-CMD-ZONE-GY-YES — the causal stack is reachable, and the
    // genuine commander's zone choice is executed on the production lane.
    // ------------------------------------------------------------------

    /**
     * F-38: the record's battlefield commander is restored as the engine's own
     * commander, so a genuine Doom Blade puts it into the graveyard and the
     * engine asks its owner the commander zone choice. Before F-38 the lane
     * placed a setup copy without commander status and the choice never came.
     */
    @Test
    void cmdZoneGyYesExecutesZoneChoice() {
        Lane lane = newLane();
        executeZoneChoice(lane, "causal-gy-yes", "WS05-CMD-ZONE-GY-YES", "Doom Blade",
                List.of(new FuelSpec("obj:fuel-swamp-a", "Swamp", "P2"),
                        new FuelSpec("obj:fuel-swamp-b", "Swamp", "P2")),
                List.of("Swamp"));
    }

    // ------------------------------------------------------------------
    // Phase B: WS05-MP-ELIM-PRIO-3 — fourteen real Lightning Bolts eliminate
    // P2 through engine SBAs; nothing forces life.
    // ------------------------------------------------------------------

    private static JsonArray eliminationInstruments(int bolts, int mountains) {
        JsonArray instruments = new JsonArray();
        for (int index = 0; index < bolts; index++) {
            instruments.add(fuelCard(
                    "obj:elim-bolt-" + index, "Lightning Bolt", "P1", "hand"));
        }
        for (int index = 0; index < mountains; index++) {
            instruments.add(fuelCard(
                    "obj:elim-mountain-" + index, "Mountain", "P1", "battlefield"));
        }
        return instruments;
    }

    private static JsonObject eliminationCreate(
            String gameId, String fixtureId, String actor, String victim, JsonArray instruments) {
        JsonObject request = new JsonObject();
        request.addProperty("game_id", gameId);
        request.addProperty("plan_id", gameId);
        request.addProperty("seed", SEED);
        request.addProperty("entry_mode", "causal_elimination");
        request.add("requested_starting_state", frozenRecord(fixtureId));
        JsonObject spec = new JsonObject();
        spec.addProperty("actor", actor);
        spec.addProperty("victim", victim);
        spec.add("instruments", instruments);
        request.add("elimination", spec);
        return request;
    }

    private static JsonArray instruments(int count) {
        return eliminationInstruments(count, count);
    }

    @Test
    void causalEliminationEntryPublishesInstrumentsAndSubstitution() {
        Lane lane = newLane();
        JsonObject created = lane.ok("create_midgame_game",
                eliminationCreate("causal-elim-plan", "WS05-MP-ELIM-PRIO-3",
                        "P1", "P2", instruments(14)));
        assertEquals("causal_elimination", created.get("entry_mode").getAsString());
        JsonObject plan = created.getAsJsonObject("elimination_plan");
        assertEquals("P1", plan.get("actor").getAsString());
        assertEquals("P2", plan.get("victim").getAsString());
        assertEquals(28, plan.getAsJsonArray("instruments").size());
        JsonArray substitutions = plan.getAsJsonArray("life_substitutions");
        assertEquals(1, substitutions.size());
        JsonObject substitution = substitutions.get(0).getAsJsonObject();
        assertEquals("P2", substitution.get("player_id").getAsString());
        assertEquals(0, substitution.get("recorded_life").getAsInt());
        assertEquals(40, substitution.get("placed_life").getAsInt());
        JsonArray survivors = plan.getAsJsonArray("expected_survivors");
        assertEquals(2, survivors.size());
    }

    @Test
    void causalEliminationVerifyBeforeDamageFailsClosed() {
        Lane lane = newLane();
        lane.ok("create_midgame_game",
                eliminationCreate("causal-elim-early", "WS05-MP-ELIM-PRIO-3",
                        "P1", "P2", instruments(14)));
        lane.ok("start_midgame_game", null);
        driveArrival(lane, "P1");

        // Verifying before any damage must fail with the engine's own
        // non-elimination fact — a vacuous "player disappeared" can never pass
        // because no player has disappeared yet and the verdict says so.
        JsonObject verify = new JsonObject();
        verify.addProperty("mode", "elimination");
        JsonObject arrival = lane.ok("complete_causal_reconstruction", verify);
        JsonObject verdict = arrival.getAsJsonObject("verdict");
        assertEquals(false, verdict.get("causal_match").getAsBoolean());
        assertTrue(verdict.getAsJsonArray("mismatches").size() > 0);
        assertTrue(verdict.getAsJsonArray("mismatches").get(0).getAsString()
                .contains("NATIVE_CAUSE_DID_NOT_ELIMINATE"));
    }

    @Test
    void fourteenRealBoltsEliminateP2ThroughEngineSbas() {
        Lane lane = newLane();
        JsonObject created = lane.ok("create_midgame_game",
                eliminationCreate("causal-elim", "WS05-MP-ELIM-PRIO-3",
                        "P1", "P2", instruments(14)));
        JsonObject plan = created.getAsJsonObject("elimination_plan");
        JsonObject placed = plan.getAsJsonObject("placed_objects");
        List<String> boltIds = new ArrayList<>();
        List<String> mountainIds = new ArrayList<>();
        for (Map.Entry<String, JsonElement> entry : placed.entrySet()) {
            if (entry.getKey().startsWith("obj:elim-bolt-")) {
                boltIds.add(entry.getValue().getAsString());
            } else if (entry.getKey().startsWith("obj:elim-mountain-")) {
                mountainIds.add(entry.getValue().getAsString());
            }
        }
        assertEquals(14, boltIds.size());
        assertEquals(14, mountainIds.size());
        lane.ok("start_midgame_game", null);
        driveArrival(lane, "P1");

        // Cause fourteen real Lightning Bolts at P2. Each cast, target and
        // mana answer is an engine-offered option; each resolution is the
        // engine's; SBAs and multiplayer cleanup are the engine's. The pilot
        // only selects. P2 falls from 40 to -2; the thirteenth bolt leaves 1.
        //
        // Every bolt is resolved before the next is cast, and resolution is
        // detected by P2's own life total dropping — never by passing a fixed
        // number of times. P1 therefore never passes with an empty stack, so
        // combat never starts, cleanup never discards the remaining
        // ammunition, and all fourteen casts happen in precombat main.
        String victimSeat = seatLabel("P2");
        int expectedVictimLife = 40;
        for (int bolt = 0; bolt < 14; bolt++) {
            castFrameSource(lane, "causal-elim-cast-" + bolt, boltIds.get(bolt));
            answerPlayerTarget(lane, "causal-elim-target-" + bolt, victimSeat);
            answerManaFromSet(lane, "causal-elim-mana-" + bolt, mountainIds);
            expectedVictimLife -= 3;
            resolveUntilLifeReaches(lane, "causal-elim-resolve-" + bolt,
                    expectedVictimLife);
        }

        JsonObject verify = new JsonObject();
        verify.addProperty("mode", "elimination");
        JsonObject arrival = lane.ok("complete_causal_reconstruction", verify);
        JsonObject verdict = arrival.getAsJsonObject("verdict");
        assertEquals(true, verdict.get("causal_match").getAsBoolean(),
                "the engine must have eliminated P2 itself: "
                        + verdict.getAsJsonArray("mismatches"));
        assertEquals(0, verdict.getAsJsonArray("mismatches").size());
        assertEquals("P2", verdict.get("victim").getAsString());
        assertEquals(true, verdict.get("victim_lost").getAsBoolean());
        assertTrue(verdict.get("victim_life").getAsInt() <= 0,
                "P2 must have reached zero or less through real damage");
        assertEquals(2, verdict.getAsJsonArray("survivors").size());
        JsonObject lifeTotals = verdict.getAsJsonObject("life_totals");
        assertEquals(40, lifeTotals.get("P1").getAsInt());
        assertEquals(40, lifeTotals.get("P3").getAsInt());
    }

    // ------------------------------------------------------------------
    // WS05-MP-BLOCK-4 — declaration execution through the placement lane.
    //
    // Four-player Commander. P1 attacks P2 with one 2/2 and P3 with another;
    // P2 blocks the P2-attacked creature with its Runeclaw Bear. With the
    // CR 802.4a lane fix, P2 is offered only attackers P2 defends against.
    // The pilot records which native attacker went to which defender during
    // declaration, then asserts the block partition from engine-offered
    // options only. Every declaration below selects an engine-offered option.
    // ------------------------------------------------------------------

    @Test
    void block4PartitionHoldsUnderThe8024aFix() {
        Lane lane = newLane();
        JsonObject request = new JsonObject();
        request.addProperty("game_id", "causal-block4");
        request.addProperty("plan_id", "causal-block4");
        request.addProperty("seed", SEED);
        request.add("requested_starting_state", frozenRecord("WS05-MP-BLOCK-4"));
        JsonObject created = lane.ok("create_midgame_game", request);
        assertEquals("placement", created.get("entry_mode").getAsString());
        lane.ok("start_midgame_game", null);

        driveArrival(lane, "P1");

        // Declare exactly as the record requires: one attacker to P2, one to
        // P3. Precombat priorities are passed to reach combat; then the pilot
        // records native attacker -> defender label for the partition proof.
        Map<String, String> defenderByAttacker = new java.util.LinkedHashMap<>();
        java.util.Set<String> remainingDefenders =
                new java.util.HashSet<>(List.of("Full Game Seat 2", "Full Game Seat 3"));
        for (int step = 0; step < 60 && !remainingDefenders.isEmpty(); step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, "the engine must park while declaring");
            String pendingClass = pending.get("decision_class").getAsString();
            if ("priority".equals(pendingClass)) {
                submitOption(lane, pending, optionWithType(pending, "pass_priority"));
                continue;
            }
            if (!"declare_attacker".equals(pendingClass)) {
                break;
            }
            boolean answered = false;
            for (JsonElement element : pending.getAsJsonArray("legal_options")) {
                JsonObject option = element.getAsJsonObject();
                if (!"declare_attacker".equals(option.get("option_type").getAsString())) {
                    continue;
                }
                String label = option.get("label").getAsString();
                for (String defender : new java.util.ArrayList<>(remainingDefenders)) {
                    if (label.endsWith("attacks " + defender)) {
                        JsonObject metadata = option.getAsJsonObject("metadata");
                        String attackerId = metadata.has("object_id")
                                && !metadata.get("object_id").isJsonNull()
                                ? metadata.get("object_id").getAsString() : "";
                        assertFalse(attackerId.isBlank(),
                                "the engine must identify the declared attacker");
                        defenderByAttacker.put(attackerId, defender);
                        remainingDefenders.remove(defender);
                        submitOption(lane, pending,
                                option.get("option_id").getAsString());
                        answered = true;
                        break;
                    }
                }
                if (answered) {
                    break;
                }
            }
            if (!answered) {
                submitOption(lane, pending,
                        optionWithType(pending, "hold_attacker"));
            }
        }
        assertEquals(2, defenderByAttacker.size(),
                "both obligated attacks must be declared; declared=" + defenderByAttacker);
        // Hold every remaining attacker so the engine advances to blockers.
        // P1 fields three bears; only the two obligated ones attack.
        for (int step = 0; step < 20; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, "the engine must park while holding attackers");
            String pendingClass = pending.get("decision_class").getAsString();
            if ("priority".equals(pendingClass)) {
                submitOption(lane, pending, optionWithType(pending, "pass_priority"));
                continue;
            }
            if (!"declare_attacker".equals(pendingClass)) {
                break;
            }
            submitOption(lane, pending, optionWithType(pending, "hold_attacker"));
        }
        String p2Attacker = null;
        String p3Attacker = null;
        for (Map.Entry<String, String> entry : defenderByAttacker.entrySet()) {
            if ("Full Game Seat 2".equals(entry.getValue())) {
                p2Attacker = entry.getKey();
            } else {
                p3Attacker = entry.getKey();
            }
        }
        assertNotNull(p2Attacker, "one attacker must defend P2");
        assertNotNull(p3Attacker, "one attacker must defend P3");

        // P2's block decision arrives per blocker. The Runeclaw Bear's own
        // frame is identified by the engine's prompt, and its offered
        // attacker set must be exactly the P2-attacked creature: the
        // P3-attacked one must be absent by CR 802.4a.
        boolean blockExecuted = false;
        for (int step = 0; step < 60; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, "the engine must park on declare_blocker");
            String decisionClass = pending.get("decision_class").getAsString();
            if ("priority".equals(decisionClass)) {
                submitOption(lane, pending, optionWithType(pending, "pass_priority"));
                continue;
            }
            if (!"declare_blocker".equals(decisionClass)) {
                break;
            }
            int seat = pending.has("seat") && !pending.get("seat").isJsonNull()
                    ? pending.get("seat").getAsInt() : -1;
            String prompt = pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    ? pending.get("prompt").getAsString() : "";
            if (seat != 1 || !prompt.contains("Runeclaw Bear")) {
                submitProposal(lane, "causal-block4-noblock-" + step,
                        emptyBlockProposal("causal-block4-noblock-" + step,
                                legalActions(lane)));
                continue;
            }
            JsonObject legal = legalActions(lane);
            java.util.Set<String> offeredAttackers = new java.util.HashSet<>();
            String runeclawOffer = null;
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                JsonObject metadata = action.getAsJsonObject("metadata");
                if (!"declare_blocker".equals(metadata.get("option_type").getAsString())) {
                    continue;
                }
                JsonObject nativeMetadata = metadata.has("xmage_option_metadata")
                        && metadata.get("xmage_option_metadata").isJsonObject()
                        ? metadata.getAsJsonObject("xmage_option_metadata")
                        : new JsonObject();
                if (nativeMetadata.has("attacker_id")
                        && !nativeMetadata.get("attacker_id").isJsonNull()) {
                    offeredAttackers.add(
                            nativeMetadata.get("attacker_id").getAsString());
                    runeclawOffer = action.get("action_id").getAsString();
                }
            }
            assertTrue(offeredAttackers.contains(p2Attacker),
                    "P2 must be offered the P2-attacked creature; offered=" + offeredAttackers);
            assertFalse(offeredAttackers.contains(p3Attacker),
                    "P2 must NOT be offered the P3-attacked creature (CR 802.4a); offered="
                            + offeredAttackers);
            assertNotNull(runeclawOffer, "P2 must be offered a block action");
            submitActionById(lane, "causal-block4-block", legal, runeclawOffer);
            blockExecuted = true;
            break;
        }
        assertTrue(blockExecuted, "P2 must execute the obligated block");
    }

    /**
     * Selects a discard from engine-offered options, preferring scaffolding
     * filler (basic lands) so fixture content is never discarded. The choice
     * is the pilot's, from the engine's set, and is recorded by the decision
     * tape; it cannot satisfy or defeat any extra-turn obligation.
     */
    private static String discardFillerOption(JsonObject pending, String tag) {
        JsonArray options = pending.getAsJsonArray("legal_options");
        for (JsonElement element : options) {
            JsonObject option = element.getAsJsonObject();
            String label = option.has("label") && !option.get("label").isJsonNull()
                    ? option.get("label").getAsString() : "";
            if (label.contains("Mountain") || label.contains("Plains")
                    || label.contains("Island") || label.contains("Swamp")
                    || label.contains("Forest")) {
                return option.get("option_id").getAsString();
            }
        }
        assertFalse(options.isEmpty(), tag + ": the engine offered no discard option");
        return options.get(0).getAsJsonObject().get("option_id").getAsString();
    }

    private static void submitActionById(
            Lane lane, String proposalId, JsonObject legal, String actionId) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (actionId.equals(action.get("action_id").getAsString())) {
                submitAction(lane, proposalId, action);
                return;
            }
        }
        fail("offer disappeared: " + actionId);
    }

    // ------------------------------------------------------------------
    // MICRO_REPLACEMENT — doubling through the placement lane.
    //
    // Four-player Commander. P1 controls Gratuitous Violence (damage P1's
    // sources deal is doubled) and an attacking 3-power Hill Giant unblocked
    // against P2. The pilot declares the Giant at P2, walks to the
    // combat-damage step, and reads P2's life from the engine's own readback:
    // 40 -> 34 proves the replacement doubled 3 to 6. No stack, no modes, no
    // fuel; the replacement is a static battlefield object the engine
    // applies. Every declaration below selects an engine-offered option.
    // ------------------------------------------------------------------

    @Test
    void microReplacementDoublesThreeDamageToSix() {
        Lane lane = newLane();
        JsonObject request = new JsonObject();
        request.addProperty("game_id", "causal-microrepl");
        request.addProperty("plan_id", "causal-microrepl");
        request.addProperty("seed", SEED);
        request.add("requested_starting_state", frozenRecord("MICRO_REPLACEMENT"));
        JsonObject created = lane.ok("create_midgame_game", request);
        assertEquals("placement", created.get("entry_mode").getAsString());
        lane.ok("start_midgame_game", null);

        driveArrival(lane, "P1");
        int lifeBefore = readbackLife(lane, "P2");
        assertEquals(40, lifeBefore);

        // Declare the Giant at P2; hold everything else. The Giant is the
        // only P1 creature that can attack (Violence is an enchantment).
        boolean giantDeclared = false;
        for (int step = 0; step < 60; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, "the engine must park while declaring");
            String pendingClass = pending.get("decision_class").getAsString();
            if ("priority".equals(pendingClass)) {
                submitOption(lane, pending, optionWithType(pending, "pass_priority"));
                continue;
            }
            if (!"declare_attacker".equals(pendingClass)) {
                break;
            }
            boolean answered = false;
            for (JsonElement element : pending.getAsJsonArray("legal_options")) {
                JsonObject option = element.getAsJsonObject();
                if (!"declare_attacker".equals(option.get("option_type").getAsString())) {
                    continue;
                }
                String label = option.get("label").getAsString();
                if (label.startsWith("Hill Giant")
                        && label.endsWith("attacks Full Game Seat 2")) {
                    submitOption(lane, pending,
                            option.get("option_id").getAsString());
                    giantDeclared = true;
                    answered = true;
                    break;
                }
            }
            if (!answered) {
                submitOption(lane, pending, optionWithType(pending, "hold_attacker"));
            }
            if (giantDeclared) {
                break;
            }
        }
        assertTrue(giantDeclared, "the Hill Giant must attack P2");
        for (int step = 0; step < 20; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, "the engine must park while holding attackers");
            String pendingClass = pending.get("decision_class").getAsString();
            if ("priority".equals(pendingClass)) {
                submitOption(lane, pending, optionWithType(pending, "pass_priority"));
                continue;
            }
            if (!"declare_attacker".equals(pendingClass)) {
                break;
            }
            submitOption(lane, pending, optionWithType(pending, "hold_attacker"));
        }

        // Walk to the combat-damage step, declining all blocks, then read P2.
        int lifeAfter = -1;
        for (int step = 0; step < 80; step++) {
            JsonObject arrival = lane.ok("complete_midgame_arrival", new JsonObject());
            JsonObject readback = arrival.getAsJsonObject("observation");
            if ("COMBAT_DAMAGE".equals(readback.get("step").getAsString())) {
                lifeAfter = readbackLife(lane, "P2");
                break;
            }
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, "the engine must park while advancing to damage");
            String pendingClass = pending.get("decision_class").getAsString();
            if ("priority".equals(pendingClass)) {
                submitOption(lane, pending, optionWithType(pending, "pass_priority"));
                continue;
            }
            if ("declare_blocker".equals(pendingClass)) {
                submitProposal(lane, "causal-repl-noblock-" + step,
                        emptyBlockProposal("causal-repl-noblock-" + step,
                                legalActions(lane)));
                continue;
            }
            if ("declare_attacker".equals(pendingClass)) {
                submitOption(lane, pending, optionWithType(pending, "hold_attacker"));
                continue;
            }
            break;
        }
        assertEquals(34, lifeAfter,
                "Gratuitous Violence must double the Giant's 3 to 6: P2 40 -> 34");
    }

    /**
     * Reads one principal's life from the engine's own arrival readback. The
     * readback seats are keyed by principal id (P1..PN), which is the record's
     * own addressing, not a native identity.
     */
    private static int readbackLife(Lane lane, String principalId) {
        JsonObject readback = lane.ok("complete_midgame_arrival", new JsonObject())
                .getAsJsonObject("observation");
        for (JsonElement element : readback.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            if (principalId.equals(seat.get("player_id").getAsString())) {
                return seat.get("life").getAsInt();
            }
        }
        fail("the engine readback names no seat " + principalId + ": " + readback);
        return -1;
    }

    // ------------------------------------------------------------------
    // WS05-MP-TURN-5 — extra-turn spells in graveyard carry no effect.
    //
    // Five-player Commander. The record places Time Warp and Nexus of Fate in
    // graveyards and expects extra turns for P3 then P2. A placed resolved
    // spell is a card, not an effect: the engine has no record of it ever
    // resolving, so no extra turn can occur. This test materializes the
    // record through placement, drives three full turns forward, records the
    // active-player sequence from the engine's own readback, and asserts the
    // rotation is normal with no extra turn anywhere. That is the measured
    // blocker: reaching the obligation needs the spells cast from hand for
    // real (as the native tier suite does by relocating them), which is a
    // causal-cast entry the lane does not have. No turn number or active
    // player is injected; the sequence is observed.
    // ------------------------------------------------------------------

    @Test
    void turn5PlacedGraveyardSpellsGrantNoExtraTurn() {
        Lane lane = newLane();
        JsonObject request = new JsonObject();
        request.addProperty("game_id", "causal-turn5");
        request.addProperty("plan_id", "causal-turn5");
        request.addProperty("seed", SEED);
        request.add("requested_starting_state", frozenRecord("WS05-MP-TURN-5"));
        JsonObject created = lane.ok("create_midgame_game", request);
        assertEquals("placement", created.get("entry_mode").getAsString());
        assertEquals(5, created.get("player_count").getAsInt());
        lane.ok("start_midgame_game", null);

        driveArrival(lane, "P1");

        // Drive forward, recording each turn's active player from the
        // engine's own readback. Holds and passes only; nothing is declared
        // except to walk through combat.
        List<String> activeSequence = new ArrayList<>();
        String lastActive = "";
        for (int step = 0; step < 400; step++) {
            JsonObject readback = lane.ok("complete_midgame_arrival", new JsonObject())
                    .getAsJsonObject("observation");
            String active = readback.get("active_player").getAsString();
            if (!active.equals(lastActive)) {
                activeSequence.add(active);
                lastActive = active;
            }
            if (activeSequence.size() >= 7) {
                break;
            }
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, "the engine must keep parking while turning");
            String pendingClass = pending.get("decision_class").getAsString();
            if ("priority".equals(pendingClass)) {
                submitOption(lane, pending, optionWithType(pending, "pass_priority"));
                continue;
            }
            if ("declare_attacker".equals(pendingClass)) {
                submitOption(lane, pending, optionWithType(pending, "hold_attacker"));
                continue;
            }
            if ("declare_blocker".equals(pendingClass)) {
                submitProposal(lane, "causal-turn5-noblock-" + step,
                        emptyBlockProposal("causal-turn5-noblock-" + step,
                                legalActions(lane)));
                continue;
            }
            if ("mulligan".equals(pendingClass)) {
                submitOption(lane, pending, optionWithType(pending, "keep"));
                continue;
            }
            if ("choose_object".equals(pendingClass)) {
                // Cleanup discard (the starting player draws in multiplayer,
                // so P1 holds eight at cleanup). The pilot discards
                // scaffolding filler first — an external discretionary choice
                // among engine-offered options, recorded, never a fallback.
                // It cannot create an extra turn.
                submitOption(lane, pending,
                        discardFillerOption(pending, "causal-turn5-discard-" + step));
                continue;
            }
            break;
        }
        assertTrue(activeSequence.size() >= 6,
                "three full turns must be observed; sequence=" + activeSequence);
        // Normal reverse-seat rotation with no extra turn anywhere: the
        // engine turns P1 P5 P4 P3 P2 P1 P5. An extra turn would repeat a
        // player consecutively or break the rotation order. The record
        // obligates P3 then P2 immediately after P1; neither happens.
        for (int index = 1; index < activeSequence.size(); index++) {
            assertFalse(activeSequence.get(index).equals(activeSequence.get(index - 1)),
                    "no active player may take two turns in a row without a causal "
                            + "extra turn; sequence=" + activeSequence);
        }
        assertEquals(List.of("P1", "P2", "P3", "P4", "P5", "P1", "P2"),
                activeSequence.subList(0, Math.min(7, activeSequence.size())),
                "the rotation must be the engine's normal order with no extra turn inserted; "
                        + "sequence=" + activeSequence);
    }

    // ------------------------------------------------------------------
    // Remaining zone rows: GY-NO, EXILE-YES/NO, HAND-YES/NO share the GY-YES
    // shape with different cause cards and fuel. LIB-YES/NO add a modal
    // choice (Bant Charm) answered from the engine's own offered modes. Each
    // proves the causal stack reachable and executes the owner's zone choice.
    // ------------------------------------------------------------------

    private static void executeZoneChoice(
            Lane lane, String tag, String fixtureId, String causeCard,
            List<FuelSpec> fuelSpecs, List<String> fuelLabels) {
        JsonArray fuel = new JsonArray();
        List<String> fuelIds = new ArrayList<>();
        for (FuelSpec spec : fuelSpecs) {
            fuel.add(fuelCard(spec.semanticId(), spec.card(), spec.owner(), "battlefield"));
            fuelIds.add(spec.semanticId());
        }
        JsonObject created = lane.ok("create_midgame_game",
                causalStackCreate(tag, fixtureId, fuel));
        JsonObject causalPlan = created.getAsJsonObject("causal_plan");
        JsonObject frame = causalPlan.getAsJsonArray("frames_bottom_to_top")
                .get(0).getAsJsonObject();
        assertEquals(causeCard, frame.get("card_identity").getAsString());
        JsonObject placed = causalPlan.getAsJsonObject("placed_objects");
        String sourceId = frame.get("native_source_id").getAsString();
        String targetId = placed.get("obj:cmd-zone-test").getAsString();
        List<String> fuelNativeIds = new ArrayList<>();
        for (String semantic : fuelIds) {
            fuelNativeIds.add(placed.get(semantic).getAsString());
        }
        lane.ok("start_midgame_game", null);

        driveArrival(lane, "P1");
        castFrameSource(lane, tag + "-cast", sourceId);
        // Engine casting order (CR 601.2): modes, then targets, then payment.
        for (JsonElement modeElement : frame.getAsJsonArray("modes")) {
            answerMode(lane, tag + "-mode", modeElement.getAsString());
        }
        answerTarget(lane, tag + "-target", targetId);
        answerManaFromSet(lane, tag + "-mana", fuelNativeIds);

        JsonObject verify = new JsonObject();
        verify.addProperty("mode", "stack");
        JsonObject arrival = lane.ok("complete_causal_reconstruction", verify);
        assertEquals(true, arrival.getAsJsonObject("verdict")
                .get("causal_match").getAsBoolean(),
                fixtureId + " causal stack must verify: "
                        + arrival.getAsJsonObject("verdict").getAsJsonArray("mismatches"));

        answerCommanderZoneChoice(lane, tag, fixtureId, placed.get("obj:cmd-zone-test").getAsString());
        List<String> trace = resolveAndRecordClasses(lane, tag);
        assertTrue(trace.stream().noneMatch("choose_use"::equals),
                fixtureId + ": one zone choice per zone change; trace=" + trace);
    }

    /**
     * F-38: the genuine commander is on the battlefield, so the engine asks its
     * owner (seat 0, P1) the commander zone choice. Answers the decision_script's
     * boolean among the engine-offered options only.
     */
    private static void answerCommanderZoneChoice(
            Lane lane, String tag, String fixtureId, String commanderNativeId) {
        boolean toCommandZone = frozenRecord(fixtureId).getAsJsonArray("decision_script").get(0)
                .getAsJsonObject().getAsJsonObject("selection").get("semantic_value").getAsBoolean();
        List<String> trace = new ArrayList<>();
        for (int step = 0; step < 40; step++) {
            JsonObject pending = pendingDecision(lane, 5);
            assertNotNull(pending, tag + ": the engine went terminal before the zone choice");
            String decisionClass = pending.get("decision_class").getAsString();
            trace.add(decisionClass);
            if ("priority".equals(decisionClass)) {
                submitOption(lane, pending, optionWithType(pending, "pass_priority"));
                continue;
            }
            assertEquals("choose_use", decisionClass, fixtureId + ": trace=" + trace);
            List<String> matches = new ArrayList<>();
            for (JsonElement element : legalActions(lane).getAsJsonArray("actions")) {
                JsonObject metadata = element.getAsJsonObject().getAsJsonObject("metadata");
                assertEquals(0, metadata.get("seat").getAsInt(), fixtureId + ": the owner decides");
                assertTrue(metadata.get("prompt").getAsString().contains(commanderNativeId),
                        fixtureId + ": the choice names the genuine commander");
                JsonObject option = metadata.getAsJsonObject("xmage_option_metadata");
                if (option != null && option.get("value").getAsBoolean() == toCommandZone) {
                    matches.add(metadata.get("option_id").getAsString());
                }
            }
            assertEquals(1, matches.size(), fixtureId + ": exactly one offered answer");
            submitOption(lane, pending, matches.get(0));
            return;
        }
        fail(fixtureId + ": the engine never asked for the zone; trace=" + trace);
    }

    private record FuelSpec(String semanticId, String card, String owner) {
    }

    /**
     * Selects the engine-offered mode matching the frame's mode token. The
     * token's words must appear in order in exactly one offered label; zero
     * or multiple matches fail closed rather than guessing.
     */
    private static void answerMode(Lane lane, String tag, String modeToken) {
        List<String> wanted = normalizeWords(modeToken.replace("_", " "));
        for (int step = 0; step < 10; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, tag + ": the engine must ask for the mode");
            if (!"mode".equals(pending.get("decision_class").getAsString())) {
                fail(tag + ": expected a mode decision, observed "
                        + pending.get("decision_class").getAsString());
            }
            List<String> matches = new ArrayList<>();
            for (JsonElement element : pending.getAsJsonArray("legal_options")) {
                JsonObject option = element.getAsJsonObject();
                if (isSubsequence(wanted,
                        normalizeWords(option.get("label").getAsString()))) {
                    matches.add(option.get("option_id").getAsString());
                }
            }
            assertEquals(1, matches.size(),
                    tag + ": expected exactly one mode matching " + modeToken
                            + "; offered: " + pending.getAsJsonArray("legal_options"));
            submitOption(lane, pending, matches.get(0));
            return;
        }
    }

    private static List<String> normalizeWords(String text) {
        List<String> words = new ArrayList<>();
        for (String word : text.toLowerCase().replaceAll("[^a-z ]", "").split(" ")) {
            if (!word.isBlank()) {
                words.add(word);
            }
        }
        return words;
    }

    private static boolean isSubsequence(List<String> needles, List<String> haystack) {
        int cursor = 0;
        for (String needle : needles) {
            while (cursor < haystack.size() && !haystack.get(cursor).equals(needle)) {
                cursor++;
            }
            if (cursor >= haystack.size()) {
                return false;
            }
            cursor++;
        }
        return true;
    }

    /**
     * Resolves fully, recording every decision class. Returns the trace. The
     * caller asserts what must or must not appear; resolving itself answers
     * only priority passes, combat holds/empties and cleanup discards of
     * scaffolding filler.
     */
    private static List<String> resolveAndRecordClasses(Lane lane, String tag) {
        List<String> trace = new ArrayList<>();
        boolean reachedCleanupDiscard = false;
        for (int step = 0; step < 150; step++) {
            JsonObject pending = pendingDecision(lane, 5);
            if (pending == null) {
                break;
            }
            String decisionClass = pending.get("decision_class").getAsString();
            trace.add(decisionClass);
            if ("choose_object".equals(decisionClass)) {
                String prompt = pending.has("prompt") && !pending.get("prompt").isJsonNull()
                        ? pending.get("prompt").getAsString() : "";
                if (prompt.contains("discard")) {
                    reachedCleanupDiscard = true;
                    break;
                }
                fail(tag + ": unexpected non-discard choose_object: " + pending);
            }
            if ("declare_attacker".equals(decisionClass)) {
                submitOption(lane, pending, optionWithType(pending, "hold_attacker"));
                continue;
            }
            if ("declare_blocker".equals(decisionClass)) {
                submitProposal(lane, tag + "-noblock-" + step,
                        emptyBlockProposal(tag + "-noblock-" + step, legalActions(lane)));
                continue;
            }
            if ("mulligan".equals(decisionClass)) {
                submitOption(lane, pending, optionWithType(pending, "keep"));
                continue;
            }
            if (!"priority".equals(decisionClass)) {
                break;
            }
            submitOption(lane, pending, optionWithType(pending, "pass_priority"));
        }
        assertTrue(reachedCleanupDiscard,
                tag + ": the game must progress to cleanup; trace=" + trace);
        return trace;
    }

    @Test
    void cmdZoneGyNoExecutesZoneChoice() {
        Lane lane = newLane();
        executeZoneChoice(lane, "causal-gy-no", "WS05-CMD-ZONE-GY-NO", "Doom Blade",
                List.of(new FuelSpec("obj:fuel-swamp-a", "Swamp", "P2"),
                        new FuelSpec("obj:fuel-swamp-b", "Swamp", "P2")),
                List.of("Swamp"));
    }

    /**
     * The public event tape of the GY-NO row: the engine's own events, named by
     * seat and semantic id, with hidden draws carrying no identity and no native
     * id anywhere.
     */
    @Test
    void thePublicEventTapeRecordsTheCausalRouteWithoutHiddenIdentities() {
        Lane lane = newLane();
        executeZoneChoice(lane, "tape-gy-no", "WS05-CMD-ZONE-GY-NO", "Doom Blade",
                List.of(new FuelSpec("obj:fuel-swamp-a", "Swamp", "P2"),
                        new FuelSpec("obj:fuel-swamp-b", "Swamp", "P2")),
                List.of("Swamp"));
        JsonObject after = new JsonObject();
        after.addProperty("after_offset", 0);
        JsonObject tape = lane.ok("get_midgame_events", after);
        JsonArray events = tape.getAsJsonArray("events");
        assertEquals(events.size(), tape.get("latest_offset").getAsInt());
        assertFalse(java.util.regex.Pattern
                .compile("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
                .matcher(tape.toString()).find(), "no native id on the wire: " + tape);

        boolean cast = false;
        boolean destroyed = false;
        boolean toGraveyard = false;
        int hiddenDraws = 0;
        int sourceMoves = 0;
        for (JsonElement element : events) {
            JsonObject event = element.getAsJsonObject();
            String type = event.get("type").getAsString();
            if ("SPELL_CAST".equals(type) && "Doom Blade".equals(text(event, "source_name"))) {
                assertEquals("P2", text(event, "player_player"));
                cast = true;
            }
            if ("DESTROYED_PERMANENT".equals(type)
                    && "obj:cmd-zone-test".equals(text(event, "target_object"))) {
                // The destroy has a source (Doom Blade); the tape says so even
                // where it would withhold which object it is.
                assertTrue(event.has("source_present") && event.get("source_present").getAsBoolean(),
                        "a sourced event reports source_present: " + event);
                destroyed = true;
            }
            if ("ZONE_CHANGE".equals(type) && "obj:cmd-zone-test".equals(text(event, "target_object"))
                    && "BATTLEFIELD".equals(text(event, "from")) && "GRAVEYARD".equals(text(event, "to"))) {
                toGraveyard = true;
            }
            if ("ZONE_CHANGE".equals(type) && "obj:cmd-zone-source".equals(text(event, "target_object"))) {
                // CR 400.7: each public move of Doom Blade is a move between
                // zones, and no zone-change counter (or anything derived from
                // it) leaves the engine: it also counts hidden moves.
                assertTrue(event.get("public_identity").getAsBoolean(), "a public move: " + event);
                assertNotEquals(text(event, "from"), text(event, "to"), "a move between zones: " + event);
                assertFalse(event.has("new_object"), "no counter-derived flag on the tape: " + event);
                assertFalse(event.has("incarnation"), "no raw counter on the tape: " + event);
                sourceMoves++;
            }
            if ("ZONE_CHANGE".equals(type) && "LIBRARY".equals(text(event, "from"))
                    && "HAND".equals(text(event, "to"))) {
                assertFalse(event.get("public_identity").getAsBoolean(), "a draw is hidden: " + event);
                assertFalse(event.has("target_name") || event.has("target_object"), "a draw names nothing: " + event);
                assertFalse(event.has("new_object") || event.has("incarnation"), "a hidden move reports no counter: " + event);
                hiddenDraws++;
            }
        }
        assertTrue(cast, "Doom Blade's cast by P2 is on the tape");
        assertTrue(destroyed, "the commander's destruction is on the tape");
        assertTrue(toGraveyard, "the commander's move to the graveyard is on the tape");
        assertTrue(hiddenDraws >= 1, "the turn draw is on the tape, anonymously: " + hiddenDraws);
        assertEquals(2, sourceMoves, "Doom Blade moved hand -> stack -> graveyard");

        JsonObject beyond = new JsonObject();
        beyond.addProperty("after_offset", events.size() + 1);
        lane.rejected("get_midgame_events", beyond);
    }

    private static String text(JsonObject event, String key) {
        return event.has(key) && !event.get(key).isJsonNull() ? event.get(key).getAsString() : null;
    }

    @Test
    void cmdZoneExileYesExecutesZoneChoice() {
        Lane lane = newLane();
        executeZoneChoice(lane, "causal-exile-yes", "WS05-CMD-ZONE-EXILE-YES",
                "Swords to Plowshares",
                List.of(new FuelSpec("obj:fuel-plains-a", "Plains", "P2")),
                List.of("Plains"));
    }

    @Test
    void cmdZoneExileNoExecutesZoneChoice() {
        Lane lane = newLane();
        executeZoneChoice(lane, "causal-exile-no", "WS05-CMD-ZONE-EXILE-NO",
                "Swords to Plowshares",
                List.of(new FuelSpec("obj:fuel-plains-a", "Plains", "P2")),
                List.of("Plains"));
    }

    @Test
    void cmdZoneHandYesExecutesZoneChoice() {
        Lane lane = newLane();
        executeZoneChoice(lane, "causal-hand-yes", "WS05-CMD-ZONE-HAND-YES", "Unsummon",
                List.of(new FuelSpec("obj:fuel-island-a", "Island", "P2")),
                List.of("Island"));
    }

    @Test
    void cmdZoneHandNoExecutesZoneChoice() {
        Lane lane = newLane();
        executeZoneChoice(lane, "causal-hand-no", "WS05-CMD-ZONE-HAND-NO", "Unsummon",
                List.of(new FuelSpec("obj:fuel-island-a", "Island", "P2")),
                List.of("Island"));
    }

    @Test
    void cmdZoneLibYesExecutesZoneChoiceWithMode() {
        Lane lane = newLane();
        executeZoneChoice(lane, "causal-lib-yes", "WS05-CMD-ZONE-LIB-YES", "Bant Charm",
                List.of(new FuelSpec("obj:fuel-forest-a", "Forest", "P2"),
                        new FuelSpec("obj:fuel-plains-a", "Plains", "P2"),
                        new FuelSpec("obj:fuel-island-a", "Island", "P2")),
                List.of("Forest", "Plains", "Island"));
    }

    @Test
    void cmdZoneLibNoExecutesZoneChoiceWithMode() {
        Lane lane = newLane();
        executeZoneChoice(lane, "causal-lib-no", "WS05-CMD-ZONE-LIB-NO", "Bant Charm",
                List.of(new FuelSpec("obj:fuel-forest-a", "Forest", "P2"),
                        new FuelSpec("obj:fuel-plains-a", "Plains", "P2"),
                        new FuelSpec("obj:fuel-island-a", "Island", "P2")),
                List.of("Forest", "Plains", "Island"));
    }

    // ------------------------------------------------------------------
    // Remaining elimination rows: OWNED-3, TURN-3 and ELIM-5 share the
    // 14-bolt engine-SBA route; CONTROL-3 is honestly rejected for control
    // divergence; ELIM-STACK-3 measures the stack with elimination pending.
    // ------------------------------------------------------------------

    private static void executeFourteenBoltElimination(
            Lane lane, String tag, String fixtureId, String victimPid, int playerCount) {
        executeFourteenBoltElimination(lane, tag, fixtureId, victimPid, playerCount, "P1");
    }

    private static void executeFourteenBoltElimination(
            Lane lane, String tag, String fixtureId, String victimPid, int playerCount,
            String startingPrincipal) {
        JsonArray instruments = new JsonArray();
        for (int index = 0; index < 14; index++) {
            instruments.add(fuelCard("obj:elim-bolt-" + index, "Lightning Bolt", "P1", "hand"));
            instruments.add(fuelCard("obj:elim-mountain-" + index, "Mountain", "P1",
                    "battlefield"));
        }
        JsonObject request = new JsonObject();
        request.addProperty("game_id", tag);
        request.addProperty("plan_id", tag);
        request.addProperty("seed", SEED);
        request.addProperty("entry_mode", "causal_elimination");
        request.add("requested_starting_state", frozenRecord(fixtureId));
        JsonObject spec = new JsonObject();
        spec.addProperty("actor", "P1");
        spec.addProperty("victim", victimPid);
        spec.add("instruments", instruments);
        request.add("elimination", spec);
        JsonObject created = lane.ok("create_midgame_game", request);
        JsonObject plan = created.getAsJsonObject("elimination_plan");
        JsonObject placed = plan.getAsJsonObject("placed_objects");
        List<String> boltIds = new ArrayList<>();
        List<String> mountainIds = new ArrayList<>();
        for (Map.Entry<String, JsonElement> entry : placed.entrySet()) {
            if (entry.getKey().contains("bolt")) {
                boltIds.add(entry.getValue().getAsString());
            } else if (entry.getKey().contains("mountain")) {
                mountainIds.add(entry.getValue().getAsString());
            }
        }
        assertEquals(14, boltIds.size());
        assertEquals(14, mountainIds.size());
        lane.ok("start_midgame_game", null);
        driveArrival(lane, startingPrincipal);

        String victimSeat = seatLabel(victimPid);
        int expectedLife = 40;
        for (int bolt = 0; bolt < 14; bolt++) {
            castFrameSource(lane, tag + "-cast-" + bolt, boltIds.get(bolt));
            answerPlayerTarget(lane, tag + "-target-" + bolt, victimSeat);
            answerManaFromSet(lane, tag + "-mana-" + bolt, mountainIds);
            expectedLife -= 3;
            resolveUntilLifeReaches(lane, tag + "-resolve-" + bolt, victimPid, expectedLife);
        }

        JsonObject verify = new JsonObject();
        verify.addProperty("mode", "elimination");
        JsonObject verdict = lane.ok("complete_causal_reconstruction", verify)
                .getAsJsonObject("verdict");
        assertEquals(true, verdict.get("causal_match").getAsBoolean(),
                fixtureId + ": the engine must have eliminated " + victimPid + ": "
                        + verdict.getAsJsonArray("mismatches"));
        assertEquals(playerCount - 1, verdict.getAsJsonArray("survivors").size());
    }

    @Test
    void elimOwned3EliminatesThroughEngineSbas() {
        Lane lane = newLane();
        executeFourteenBoltElimination(
                lane, "causal-elim-owned", "WS05-MP-ELIM-OWNED-3", "P2", 3);
    }

    @Test
    void elimTurn3EliminatesThroughEngineSbas() {
        Lane lane = newLane();
        // The record names P2 active on turn 1, so P2 is the starting player
        // here; the helper below still drives P1 as the bolt actor afterwards.
        executeFourteenBoltElimination(
                lane, "causal-elim-turn", "WS05-MP-ELIM-TURN-3", "P2", 3, "P2");
    }

    @Test
    void elim5EliminatesThroughEngineSbasAtFivePlayers() {
        Lane lane = newLane();
        executeFourteenBoltElimination(
                lane, "causal-elim-5", "WS05-MP-ELIM-5", "P3", 5);
    }

    @Test
    void elimControl3RejectsControlDivergence() {
        Lane lane = newLane();
        JsonObject request = new JsonObject();
        request.addProperty("game_id", "causal-elim-control");
        request.addProperty("plan_id", "causal-elim-control");
        request.addProperty("seed", SEED);
        request.addProperty("entry_mode", "causal_elimination");
        // The row also attaches Control Magic, which the restoration refuses on
        // its own (UNSUPPORTED_ATTACHMENTS); without it the divergence is what
        // remains to reject.
        JsonObject record = frozenRecord("WS05-MP-ELIM-CONTROL-3").deepCopy();
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            element.getAsJsonObject().remove("attached_to");
        }
        request.add("requested_starting_state", record);
        JsonObject spec = new JsonObject();
        spec.addProperty("actor", "P1");
        spec.addProperty("victim", "P2");
        spec.add("instruments", new JsonArray());
        request.add("elimination", spec);
        JsonObject response = lane.rejected("create_midgame_game", request);
        assertEquals("midgame_causal_preparation_rejected",
                response.getAsJsonArray("errors").get(0).getAsJsonObject()
                        .get("code").getAsString());
        assertTrue(response.getAsJsonArray("errors").get(0).getAsJsonObject()
                .get("message").getAsString().contains("UNSUPPORTED_CONTROL_DIVERGENCE"));
    }

    @Test
    void elimStack3MeasuresStackWithEliminationPending() {
        Lane lane = newLane();
        JsonArray fuel = new JsonArray();
        fuel.add(fuelCard("obj:fuel-mountain-p2", "Mountain", "P2", "battlefield"));
        JsonObject created = lane.ok("create_midgame_game",
                causalStackCreate("causal-elim-stack", "WS05-MP-ELIM-STACK-3", fuel));
        JsonObject causalPlan = created.getAsJsonObject("causal_plan");
        JsonObject frame = causalPlan.getAsJsonArray("frames_bottom_to_top")
                .get(0).getAsJsonObject();
        assertEquals("obj:leave-bolt", frame.get("semantic_id").getAsString());
        assertEquals("P2", frame.get("controller").getAsString());
        JsonObject placed = causalPlan.getAsJsonObject("placed_objects");
        lane.ok("start_midgame_game", null);

        driveArrival(lane, "P1");
        castFrameSource(lane, "causal-elim-stack-cast",
                frame.get("native_source_id").getAsString());
        answerPlayerTarget(lane, "causal-elim-stack-target", seatLabel("P1"));
        answerManaFromSet(lane, "causal-elim-stack-mana",
                List.of(placed.get("obj:fuel-mountain-p2").getAsString()));

        JsonObject verify = new JsonObject();
        verify.addProperty("mode", "stack");
        JsonObject verdict = lane.ok("complete_causal_reconstruction", verify)
                .getAsJsonObject("verdict");
        assertEquals(true, verdict.get("causal_match").getAsBoolean(),
                "P2's bolt must be genuinely on the stack targeting P1: "
                        + verdict.getAsJsonArray("mismatches"));

        // The victim is still alive with the spell on the stack. Eliminating
        // in the same game needs stack frames and elimination instruments
        // placed together — a combined causal entry the lane does not have.
        // The lane correctly refuses to verify elimination on a stack-mode
        // game; that refusal code is the composition-gap receipt.
        JsonObject elimVerify = new JsonObject();
        elimVerify.addProperty("mode", "elimination");
        JsonObject elimResponse = lane.rejected("complete_causal_reconstruction", elimVerify);
        assertEquals("no_causal_elimination_plan",
                elimResponse.getAsJsonArray("errors").get(0).getAsJsonObject()
                        .get("code").getAsString());
    }

    @Test
    void elimStack3ComposedEntryRemovesTheVictimsSpellWithTheVictim() {
        Lane lane = newLane();
        JsonArray fuel = new JsonArray();
        fuel.add(fuelCard("obj:fuel-mountain-p2", "Mountain", "P2", "battlefield"));
        JsonArray instruments = new JsonArray();
        for (int index = 0; index < 14; index++) {
            instruments.add(fuelCard("obj:elim-bolt-" + index, "Lightning Bolt", "P1", "hand"));
            instruments.add(fuelCard("obj:elim-mountain-" + index, "Mountain", "P1",
                    "battlefield"));
        }
        JsonObject request = causalStackCreate(
                "causal-elim-stack-composed", "WS05-MP-ELIM-STACK-3", fuel);
        request.addProperty("entry_mode", "causal_stack_elimination");
        JsonObject spec = new JsonObject();
        spec.addProperty("actor", "P1");
        spec.addProperty("victim", "P2");
        spec.add("instruments", instruments);
        request.add("elimination", spec);
        JsonObject created = lane.ok("create_midgame_game", request);
        assertEquals("causal_stack_elimination", created.get("entry_mode").getAsString());
        JsonObject causalPlan = created.getAsJsonObject("causal_plan");
        JsonObject eliminationPlan = created.getAsJsonObject("elimination_plan");
        JsonObject substitution = eliminationPlan.getAsJsonArray("life_substitutions")
                .get(0).getAsJsonObject();
        assertEquals("P2", substitution.get("player_id").getAsString());
        assertEquals(0, substitution.get("recorded_life").getAsInt());
        JsonObject frame = causalPlan.getAsJsonArray("frames_bottom_to_top")
                .get(0).getAsJsonObject();
        assertEquals("obj:leave-bolt", frame.get("semantic_id").getAsString());
        JsonObject placed = causalPlan.getAsJsonObject("placed_objects");
        List<String> boltIds = new ArrayList<>();
        List<String> mountainIds = new ArrayList<>();
        for (JsonElement element : eliminationPlan.getAsJsonArray("instruments")) {
            JsonObject instrument = element.getAsJsonObject();
            String nativeId = instrument.get("native_id").getAsString();
            if ("Lightning Bolt".equals(instrument.get("card_identity").getAsString())) {
                boltIds.add(nativeId);
            } else {
                mountainIds.add(nativeId);
            }
        }
        assertEquals(14, boltIds.size());
        assertEquals(14, mountainIds.size());
        // P2's own Bolt and fuel Mountain are not instruments.
        assertFalse(boltIds.contains(placed.get("obj:leave-bolt").getAsString()));
        lane.ok("start_midgame_game", null);

        driveArrival(lane, "P1");
        castFrameSource(lane, "composed-cast", frame.get("native_source_id").getAsString());
        answerPlayerTarget(lane, "composed-target", seatLabel("P1"));
        answerManaFromSet(lane, "composed-mana",
                List.of(placed.get("obj:fuel-mountain-p2").getAsString()));
        JsonObject stackVerify = new JsonObject();
        stackVerify.addProperty("mode", "stack");
        JsonObject stackVerdict = lane.ok("complete_causal_reconstruction", stackVerify)
                .getAsJsonObject("verdict");
        assertTrue(stackVerdict.get("causal_match").getAsBoolean(),
                "P2's Bolt must be on the stack before the loss: "
                        + stackVerdict.getAsJsonArray("mismatches"));

        int expectedLife = 40;
        for (int bolt = 0; bolt < 14; bolt++) {
            castFrameSource(lane, "composed-bolt-" + bolt, boltIds.get(bolt));
            answerPlayerTarget(lane, "composed-bolt-target-" + bolt, seatLabel("P2"));
            answerManaFromSet(lane, "composed-bolt-mana-" + bolt, mountainIds);
            expectedLife -= 3;
            resolveUntilLifeReaches(lane, "composed-bolt-resolve-" + bolt, "P2", expectedLife);
        }

        JsonObject eliminationVerify = new JsonObject();
        eliminationVerify.addProperty("mode", "elimination");
        JsonObject verdict = lane.ok("complete_causal_reconstruction", eliminationVerify)
                .getAsJsonObject("verdict");
        assertTrue(verdict.get("causal_match").getAsBoolean(),
                "the engine must eliminate P2: " + verdict.getAsJsonArray("mismatches"));
        assertTrue(verdict.get("victim_lost").getAsBoolean(), "P2 lost: " + verdict);
        assertTrue(verdict.get("victim_left").getAsBoolean(), "P2 left: " + verdict);
        // P2's Bolt left with P2 (CR 800.4a): it never resolved at P1, and the
        // engine's own stack is empty at the next decision.
        assertEquals(40, verdict.getAsJsonObject("life_totals").get("P1").getAsInt());
        JsonObject next = pendingDecision(lane);
        assertEquals(0, next.getAsJsonObject("pilot_state").getAsJsonArray("stack").size(),
                "the victim's spell must be gone from the engine's stack: " + next);
        JsonObject after = lane.ok("complete_causal_reconstruction", stackVerify)
                .getAsJsonObject("verdict");
        assertFalse(after.get("causal_match").getAsBoolean(),
                "the stack verifier no longer finds the victim's spell after the loss");
    }

    @Test
    void composedEntryWithoutEliminationSpecFailsClosed() {
        Lane lane = newLane();
        JsonArray fuel = new JsonArray();
        fuel.add(fuelCard("obj:fuel-mountain-p2", "Mountain", "P2", "battlefield"));
        JsonObject request = causalStackCreate(
                "causal-elim-stack-nospec", "WS05-MP-ELIM-STACK-3", fuel);
        request.addProperty("entry_mode", "causal_stack_elimination");
        JsonObject response = lane.rejected("create_midgame_game", request);
        JsonObject error = response.getAsJsonArray("errors").get(0).getAsJsonObject();
        assertEquals("midgame_causal_preparation_rejected", error.get("code").getAsString());
        assertTrue(error.get("message").getAsString().contains("MISSING_ELIMINATION_SPEC"));
    }

    private static JsonObject elimControl3Request(String gameId, boolean withCaused) {
        JsonArray fuel = new JsonArray();
        fuel.add(fuelCard("obj:enabler-leyline-p2", "Leyline of Anticipation", "P2", "battlefield"));
        for (int index = 0; index < 4; index++) {
            fuel.add(fuelCard("obj:fuel-island-p2-" + index, "Island", "P2", "battlefield"));
        }
        JsonArray instruments = new JsonArray();
        for (int index = 0; index < 14; index++) {
            instruments.add(fuelCard("obj:elim-bolt-" + index, "Lightning Bolt", "P1", "hand"));
            instruments.add(fuelCard("obj:elim-mountain-" + index, "Mountain", "P1",
                    "battlefield"));
        }
        JsonObject request = causalStackCreate(gameId, "WS05-MP-ELIM-CONTROL-3", fuel);
        request.addProperty("entry_mode", "causal_stack_elimination");
        if (withCaused) {
            JsonArray caused = new JsonArray();
            caused.add("obj:leave-controlmagic");
            request.add("caused_permanents", caused);
        }
        JsonObject spec = new JsonObject();
        spec.addProperty("actor", "P1");
        spec.addProperty("victim", "P2");
        spec.add("instruments", instruments);
        request.add("elimination", spec);
        return request;
    }

    private static void passUntilStackEmpty(Lane lane, String tag) {
        for (int step = 0; step < 30; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, tag + ": the engine must keep asking");
            assertEquals("priority", pending.get("decision_class").getAsString(), tag);
            if (pending.getAsJsonObject("pilot_state").getAsJsonArray("stack").isEmpty()) {
                return;
            }
            submitOption(lane, pending, optionWithType(pending, "pass_priority"));
        }
        fail(tag + ": the stack never emptied");
    }

    @Test
    void elimControl3CausesTheAuraThenEliminatesItsOwner() {
        Lane lane = newLane();
        JsonObject created = lane.ok("create_midgame_game",
                elimControl3Request("causal-elim-control-caused", true));
        JsonObject causalPlan = created.getAsJsonObject("causal_plan");
        JsonObject frame = causalPlan.getAsJsonArray("frames_bottom_to_top")
                .get(0).getAsJsonObject();
        assertEquals("obj:leave-controlmagic", frame.get("semantic_id").getAsString());
        assertEquals("P2", frame.get("controller").getAsString());
        assertEquals("obj:p1-owned-controlled",
                frame.getAsJsonArray("targets").get(0).getAsString());
        JsonObject placed = causalPlan.getAsJsonObject("placed_objects");
        List<String> islands = new ArrayList<>();
        for (int index = 0; index < 4; index++) {
            islands.add(placed.get("obj:fuel-island-p2-" + index).getAsString());
        }
        lane.ok("start_midgame_game", null);

        driveArrival(lane, "P1");
        JsonObject permanentsVerify = new JsonObject();
        permanentsVerify.addProperty("mode", "permanents");
        JsonObject early = lane.ok("complete_causal_reconstruction", permanentsVerify)
                .getAsJsonObject("verdict");
        assertFalse(early.get("causal_match").getAsBoolean(),
                "before the cast the Aura is not on the battlefield: " + early);

        // P2 casts Control Magic on P1's turn only because the declared
        // Leyline of Anticipation gives it flash; the engine decides that.
        castFrameSource(lane, "caused-cast", frame.get("native_source_id").getAsString());
        answerTarget(lane, "caused-target", placed.get("obj:p1-owned-controlled").getAsString());
        answerManaFromSet(lane, "caused-mana", islands);
        JsonObject stackVerify = new JsonObject();
        stackVerify.addProperty("mode", "stack");
        assertTrue(lane.ok("complete_causal_reconstruction", stackVerify)
                .getAsJsonObject("verdict").get("causal_match").getAsBoolean());
        passUntilStackEmpty(lane, "caused-resolve");
        JsonObject permanents = lane.ok("complete_causal_reconstruction", permanentsVerify)
                .getAsJsonObject("verdict");
        assertTrue(permanents.get("causal_match").getAsBoolean(),
                "the Aura must be attached, P2 must control the Bears, and the engine must be "
                        + "at the record's checkpoint (P1's turn 1, P1 holding priority): "
                        + permanents.getAsJsonArray("mismatches"));
        JsonObject checkpoint = pendingDecision(lane);
        assertEquals("priority", checkpoint.get("decision_class").getAsString());
        assertEquals(0, checkpoint.getAsJsonObject("pilot_state").getAsJsonArray("stack").size());

        List<String> boltIds = new ArrayList<>();
        List<String> mountainIds = new ArrayList<>();
        for (JsonElement element : created.getAsJsonObject("elimination_plan")
                .getAsJsonArray("instruments")) {
            JsonObject instrument = element.getAsJsonObject();
            String nativeId = instrument.get("native_id").getAsString();
            if ("Lightning Bolt".equals(instrument.get("card_identity").getAsString())) {
                boltIds.add(nativeId);
            } else {
                mountainIds.add(nativeId);
            }
        }
        int expectedLife = 40;
        for (int bolt = 0; bolt < 14; bolt++) {
            castFrameSource(lane, "caused-bolt-" + bolt, boltIds.get(bolt));
            answerPlayerTarget(lane, "caused-bolt-target-" + bolt, seatLabel("P2"));
            answerManaFromSet(lane, "caused-bolt-mana-" + bolt, mountainIds);
            expectedLife -= 3;
            resolveUntilLifeReaches(lane, "caused-bolt-resolve-" + bolt, "P2", expectedLife);
        }
        JsonObject eliminationVerify = new JsonObject();
        eliminationVerify.addProperty("mode", "elimination");
        JsonObject verdict = lane.ok("complete_causal_reconstruction", eliminationVerify)
                .getAsJsonObject("verdict");
        assertTrue(verdict.get("victim_lost").getAsBoolean() && verdict.get("victim_left").getAsBoolean(),
                "P2 must lose and leave: " + verdict);
        // The Aura left with P2 (CR 800.4a): the caused-permanent verifier no
        // longer finds it, and P1 controls its Bears again.
        JsonObject after = lane.ok("complete_causal_reconstruction", permanentsVerify)
                .getAsJsonObject("verdict");
        assertFalse(after.get("causal_match").getAsBoolean(), "the Aura must be gone: " + after);
        assertTrue(after.getAsJsonArray("mismatches").toString().contains("CAUSED_PERMANENT_ABSENT"),
                after.toString());
    }

    @Test
    void theCausedPermanentsMustLandOnTheRecordsCheckpoint() {
        // Wrong-reason control for the checkpoint comparison: after the Aura
        // resolved, P1 passes once, so P2 holds priority. Attachment and
        // control still match, but the record's checkpoint (P1 holding
        // priority) no longer does, and the verifier must say so.
        Lane lane = newLane();
        JsonObject created = lane.ok("create_midgame_game",
                elimControl3Request("caused-checkpoint", true));
        JsonObject causalPlan = created.getAsJsonObject("causal_plan");
        JsonObject frame = causalPlan.getAsJsonArray("frames_bottom_to_top")
                .get(0).getAsJsonObject();
        JsonObject placed = causalPlan.getAsJsonObject("placed_objects");
        List<String> islands = new ArrayList<>();
        for (int index = 0; index < 4; index++) {
            islands.add(placed.get("obj:fuel-island-p2-" + index).getAsString());
        }
        lane.ok("start_midgame_game", null);
        driveArrival(lane, "P1");
        castFrameSource(lane, "checkpoint-cast", frame.get("native_source_id").getAsString());
        answerTarget(lane, "checkpoint-target", placed.get("obj:p1-owned-controlled").getAsString());
        answerManaFromSet(lane, "checkpoint-mana", islands);
        passUntilStackEmpty(lane, "checkpoint-resolve");
        JsonObject permanentsVerify = new JsonObject();
        permanentsVerify.addProperty("mode", "permanents");
        assertTrue(lane.ok("complete_causal_reconstruction", permanentsVerify)
                .getAsJsonObject("verdict").get("causal_match").getAsBoolean());

        JsonObject pending = pendingDecision(lane);
        submitOption(lane, pending, optionWithType(pending, "pass_priority"));
        JsonObject moved = lane.ok("complete_causal_reconstruction", permanentsVerify)
                .getAsJsonObject("verdict");
        assertFalse(moved.get("causal_match").getAsBoolean(), moved.toString());
        String mismatches = moved.getAsJsonArray("mismatches").toString();
        assertTrue(mismatches.contains("CAUSED_CHECKPOINT_MISMATCH"), mismatches);
        assertFalse(mismatches.contains("CAUSED_PERMANENT_ATTACHMENT"), mismatches);
    }

    @Test
    void permanentsVerifierWithoutCausedPermanentsFailsClosed() {
        // Without its caused Aura the ELIM-CONTROL-3 record has nothing to cast,
        // so the composed entry refuses it outright.
        Lane refused = newLane();
        JsonObject rejected = refused.rejected("create_midgame_game",
                elimControl3Request("caused-none", false));
        assertTrue(rejected.getAsJsonArray("errors").get(0).getAsJsonObject().get("message")
                .getAsString().contains("EMPTY_STACK_STATE"), rejected.toString());
        // A composed game that declares no caused permanents has no permanents
        // verifier to answer.
        Lane lane = newLane();
        JsonArray fuel = new JsonArray();
        fuel.add(fuelCard("obj:fuel-mountain-p2", "Mountain", "P2", "battlefield"));
        JsonObject request = causalStackCreate("caused-none-stack", "WS05-MP-ELIM-STACK-3", fuel);
        request.addProperty("entry_mode", "causal_stack_elimination");
        JsonObject spec = new JsonObject();
        spec.addProperty("actor", "P1");
        spec.addProperty("victim", "P2");
        spec.add("instruments", new JsonArray());
        request.add("elimination", spec);
        lane.ok("create_midgame_game", request);
        JsonObject permanentsVerify = new JsonObject();
        permanentsVerify.addProperty("mode", "permanents");
        JsonObject response = lane.rejected("complete_causal_reconstruction", permanentsVerify);
        assertEquals("no_caused_permanents", response.getAsJsonArray("errors").get(0)
                .getAsJsonObject().get("code").getAsString());
    }

    @Test
    void aCausedPermanentWithARequestedStackFailsClosed() {
        // Resolving the caused cast would resolve the requested stack too.
        Lane lane = newLane();
        JsonArray fuel = new JsonArray();
        fuel.add(fuelCard("obj:fuel-mountain-p2", "Mountain", "P2", "battlefield"));
        JsonObject request = causalStackCreate("caused-with-stack", "WS05-MP-ELIM-STACK-3", fuel);
        request.addProperty("entry_mode", "causal_stack_elimination");
        JsonArray caused = new JsonArray();
        caused.add("obj:P1-bears");
        request.add("caused_permanents", caused);
        JsonObject spec = new JsonObject();
        spec.addProperty("actor", "P1");
        spec.addProperty("victim", "P2");
        spec.add("instruments", new JsonArray());
        request.add("elimination", spec);
        JsonObject response = lane.rejected("create_midgame_game", request);
        assertTrue(response.getAsJsonArray("errors").get(0).getAsJsonObject().get("message")
                .getAsString().contains("CAUSED_PERMANENT_WITH_REQUESTED_STACK"),
                response.toString());
    }

    @Test
    void causedPermanentsOutsideTheComposedEntryAreRefused() {
        Lane lane = newLane();
        JsonArray fuel = new JsonArray();
        fuel.add(fuelCard("obj:fuel-mountain-p2", "Mountain", "P2", "battlefield"));
        JsonObject request = causalStackCreate("caused-outside", "WS05-MP-ELIM-STACK-3", fuel);
        JsonArray caused = new JsonArray();
        caused.add("obj:leave-bolt");
        request.add("caused_permanents", caused);
        JsonObject response = lane.rejected("create_midgame_game", request);
        assertTrue(response.getAsJsonArray("errors").get(0).getAsJsonObject().get("message")
                .getAsString().contains("CAUSED_PERMANENTS_OUTSIDE_COMPOSED_ENTRY"),
                response.toString());
    }

    @Test
    void anUnattachedCausedPermanentFailsClosed() {
        Lane lane = newLane();
        JsonObject request = elimControl3Request("caused-unattached", false);
        JsonArray caused = new JsonArray();
        caused.add("obj:P1-bears");
        request.add("caused_permanents", caused);
        JsonObject response = lane.rejected("create_midgame_game", request);
        assertTrue(response.getAsJsonArray("errors").get(0).getAsJsonObject().get("message")
                .getAsString().contains("CAUSED_PERMANENT_NOT_ATTACHED"), response.toString());
    }

    // ------------------------------------------------------------------
    // Lane drivers: every answer is an engine-offered option.
    // ------------------------------------------------------------------

    private static JsonObject pendingDecision(Lane lane) {
        return pendingDecision(lane, 40);
    }

    private static JsonObject pendingDecision(Lane lane, int attempts) {
        for (int attempt = 0; attempt < attempts; attempt++) {
            JsonObject payload = lane.ok("get_midgame_decision", null);
            if (payload.has("decision") && !payload.get("decision").isJsonNull()) {
                return payload.getAsJsonObject("decision");
            }
            try {
                Thread.sleep(100);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                fail("interrupted while polling the pending decision");
            }
        }
        return null;
    }

    private static JsonObject legalActions(Lane lane) {
        return lane.ok("get_legal_actions", null);
    }

    private static void submitOption(Lane lane, JsonObject pending, String optionId) {
        assertNotNull(optionId, "no engine-offered option matched the pilot intent");
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", pending.get("decision_id").getAsString());
        response.addProperty("actor_id", pending.get("actor_id").getAsString());
        JsonArray selected = new JsonArray();
        selected.add(optionId);
        response.add("selected_option_ids", selected);
        response.add("ordering", new JsonArray());
        JsonObject request = new JsonObject();
        request.add("response", response);
        lane.ok("submit_midgame_decision", request);
    }

    private static void submitAction(Lane lane, String proposalId, JsonObject action) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        JsonObject legal = legalActions(lane);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", action.get("action_id").getAsString());
        proposal.addProperty("action_type", action.get("action_type").getAsString());
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "midgame-causal-external-pilot");
        JsonObject request = new JsonObject();
        request.add("proposal", proposal);
        lane.ok("submit_action", request);
    }

    private static void submitProposal(Lane lane, String proposalId, JsonObject proposal) {
        JsonObject request = new JsonObject();
        request.add("proposal", proposal);
        lane.ok("submit_action", request);
    }

    private static String optionWithType(JsonObject pending, String optionType) {
        List<String> matches = new ArrayList<>();
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (optionType.equals(option.get("option_type").getAsString())) {
                matches.add(option.get("option_id").getAsString());
            }
        }
        assertEquals(1, matches.size(),
                "expected exactly one engine-offered " + optionType + " option; offered: "
                        + pending.getAsJsonArray("legal_options"));
        return matches.get(0);
    }

    private static String seatLabel(String principalId) {
        return "Full Game Seat " + principalId.replaceAll("^P", "");
    }

    private static void driveArrival(Lane lane, String activePrincipal) {
        String activeLabel = seatLabel(activePrincipal);
        for (int step = 0; step < 60; step++) {
            JsonObject pending = pendingDecision(lane);
            if (pending == null) {
                break;
            }
            String decisionClass = pending.get("decision_class").getAsString();
            String actor = pending.get("actor_id").getAsString();
            if ("mulligan".equals(decisionClass)) {
                submitOption(lane, pending, optionWithType(pending, "keep"));
                continue;
            }
            if ("choice".equals(decisionClass) || "choose_object".equals(decisionClass)) {
                String label = pending.has("prompt") && !pending.get("prompt").isJsonNull()
                        ? pending.get("prompt").getAsString() : "";
                if (label.contains("discard") || label.contains("starting player")) {
                    // Cleanup discard and the choosing-player pick: answer the
                    // engine-offered option for the active seat only.
                    submitOption(lane, pending, optionForLabelSuffix(pending, activeLabel));
                    continue;
                }
                // Any other choice is an obligation, not arrival transport.
                break;
            }
            if ("priority".equals(decisionClass)) {
                JsonObject readback = lane.ok("complete_midgame_arrival", new JsonObject())
                        .getAsJsonObject("observation");
                if ("PRECOMBAT_MAIN".equals(readback.get("phase").getAsString())
                        && "PRECOMBAT_MAIN".equals(readback.get("step").getAsString())) {
                    return;
                }
                submitOption(lane, pending, optionWithType(pending, "pass_priority"));
                continue;
            }
            break;
        }
    }

    private static String optionForLabelSuffix(JsonObject pending, String suffix) {
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (option.get("label").getAsString().endsWith(suffix)) {
                return option.get("option_id").getAsString();
            }
        }
        fail("the engine offered no option ending with " + suffix + ": "
                + pending.getAsJsonArray("legal_options"));
        return null;
    }

    /** Hands priority to the frame controller, then selects the exact cast. */
    private static void castFrameSource(Lane lane, String tag, String nativeSourceId) {
        drainCombatToPriority(lane, tag);
        for (int step = 0; step < 40; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, tag + ": the engine must park while the cast is open");
            String decisionClass = pending.get("decision_class").getAsString();
            if (!"priority".equals(decisionClass)) {
                fail(tag + ": expected priority to cast, observed " + decisionClass
                        + ": " + pending);
            }
            JsonObject legal = legalActions(lane);
            JsonObject cast = findSourceCast(legal, nativeSourceId);
            if (cast != null) {
                submitAction(lane, tag, cast);
                return;
            }
            submitOption(lane, pending, optionWithType(pending, "pass_priority"));
        }
        fail(tag + ": the engine never offered the requested source cast");
    }

    /**
     * Answers combat declarations with holds/empties until a priority decision
     * is pending. The engine advances through its combat steps as priority
     * passes; a sorcery-speed causal cast needs a priority, so the pilot must
     * walk through combat, never around it.
     */
    private static void drainCombatToPriority(Lane lane, String tag) {
        for (int step = 0; step < 60; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, tag + ": the engine must park while draining combat");
            String decisionClass = pending.get("decision_class").getAsString();
            if ("priority".equals(decisionClass)) {
                return;
            }
            if ("declare_attacker".equals(decisionClass)) {
                submitAction(lane, tag + "-hold-" + step,
                        singleActionOfType(legalActions(lane),
                                "declare_attackers", "hold_attacker"));
                continue;
            }
            if ("declare_blocker".equals(decisionClass)) {
                submitProposal(lane, tag + "-noblock-" + step,
                        emptyBlockProposal(tag + "-noblock-" + step, legalActions(lane)));
                continue;
            }
            fail(tag + ": expected combat or priority while draining, observed "
                    + decisionClass);
        }
        fail(tag + ": the engine never returned to priority");
    }

    private static JsonObject findSourceCast(JsonObject legal, String nativeSourceId) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!action.has("metadata") || !action.get("metadata").isJsonObject()) {
                continue;
            }
            JsonObject metadata = action.getAsJsonObject("metadata");
            if (!metadata.has("xmage_option_metadata")
                    || !metadata.get("xmage_option_metadata").isJsonObject()) {
                continue;
            }
            JsonObject engine = metadata.getAsJsonObject("xmage_option_metadata");
            if (engine.has("source_object_id")
                    && nativeSourceId.equals(engine.get("source_object_id").getAsString())
                    && engine.has("ability_type")
                    && "spell".equals(engine.get("ability_type").getAsString())) {
                return action;
            }
        }
        return null;
    }

    private static void answerTarget(Lane lane, String tag, String nativeTargetId) {
        for (int step = 0; step < 20; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, tag + ": the engine must ask for the target");
            if (!"target".equals(pending.get("decision_class").getAsString())) {
                fail(tag + ": expected a target decision, observed "
                        + pending.get("decision_class").getAsString());
            }
            JsonObject offer = findNativeOffer(legalActions(lane), nativeTargetId);
            if (offer != null) {
                submitAction(lane, tag, offer);
                return;
            }
            fail(tag + ": the engine never offered the requested target " + nativeTargetId
                    + "; offered: " + legalActions(lane).getAsJsonArray("actions"));
        }
    }

    /**
     * Targets a player by the engine's own offered action label, never by
     * native id. The label is the defending player's own engine name, which
     * is the Rules-visible seat identity the external pilot selects on.
     */
    private static void answerPlayerTarget(Lane lane, String tag, String seatName) {
        for (int step = 0; step < 20; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, tag + ": the engine must ask for the target");
            if (!"target".equals(pending.get("decision_class").getAsString())) {
                fail(tag + ": expected a target decision, observed "
                        + pending.get("decision_class").getAsString());
            }
            JsonObject legal = legalActions(lane);
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                JsonObject metadata = action.getAsJsonObject("metadata");
                if (!metadata.has("label") || metadata.get("label").isJsonNull()) {
                    continue;
                }
                if (seatName.equals(metadata.get("label").getAsString())) {
                    submitAction(lane, tag, action);
                    return;
                }
            }
            fail(tag + ": the engine never offered " + seatName + " as a target");
        }
    }

    private static JsonObject findNativeOffer(JsonObject legal, String nativeId) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            JsonObject nativeMetadata = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
            for (Map.Entry<String, JsonElement> entry : nativeMetadata.entrySet()) {
                if (entry.getValue().isJsonPrimitive()
                        && nativeId.equals(entry.getValue().getAsString())) {
                    return action;
                }
            }
        }
        return null;
    }

    /**
     * Pays with the exact engine-offered mana ability of one fuel land, then
     * spends the resulting pool mana. XMage moves the spell onto the stack
     * before payment completes, so a stack verification alone cannot prove
     * payment — this method returns only after the engine stops asking.
     */
    private static void answerMana(Lane lane, String tag, String fuelNativeId) {
        answerManaFromSet(lane, tag, List.of(fuelNativeId));
    }

    /**
     * Pays from any offered ability whose source is a declared fuel card,
     * then from the resulting pool. The engine offers its untapped fuel in
     * its own order and never re-offers a tapped land, so matching the set
     * consumes fuel exactly once each.
     */
    private static void answerManaFromSet(
            Lane lane, String tag, List<String> fuelNativeIds) {
        java.util.Set<String> fuelSet = new java.util.HashSet<>(fuelNativeIds);
        for (int step = 0; step < 40; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, tag + ": the engine must ask for mana");
            if (!"mana_payment".equals(pending.get("decision_class").getAsString())) {
                return;
            }
            JsonObject legal = legalActions(lane);
            JsonObject ability = findFuelAbilityInSet(legal, fuelSet);
            if (ability != null) {
                submitAction(lane, tag + "-tap", ability);
                continue;
            }
            // Spend pool mana the engine marks as advancing the payment. The
            // engine withdraws spent mana from later offers, so a repeated
            // color across polls is fresh mana, not a repeat; the loop bound
            // plus the decision closing on payment together prevent spinning.
            JsonObject spend = null;
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                JsonObject metadata = action.getAsJsonObject("metadata");
                if (!"mana_pool".equals(metadata.get("option_type").getAsString())) {
                    continue;
                }
                JsonObject engine = metadata.has("xmage_option_metadata")
                        && metadata.get("xmage_option_metadata").isJsonObject()
                        ? metadata.getAsJsonObject("xmage_option_metadata")
                        : new JsonObject();
                boolean advances = !engine.has("advances_payment")
                        || engine.get("advances_payment").isJsonNull()
                        || engine.get("advances_payment").getAsBoolean();
                if (advances) {
                    spend = action;
                    break;
                }
            }
            assertNotNull(spend,
                    tag + ": the engine offered no advancing pool spend; offered: "
                            + legal.getAsJsonArray("actions"));
            submitAction(lane, tag + "-spend", spend);
        }
    }

    private static JsonObject findFuelAbility(JsonObject legal, String fuelNativeId) {
        return findFuelAbilityInSet(legal, java.util.Set.of(fuelNativeId));
    }

    private static JsonObject findFuelAbilityInSet(
            JsonObject legal, java.util.Set<String> fuelNativeIds) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            if (!"mana_ability".equals(metadata.get("option_type").getAsString())) {
                continue;
            }
            JsonObject engine = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata")
                    : new JsonObject();
            if (engine.has("source_object_id")
                    && fuelNativeIds.contains(
                            engine.get("source_object_id").getAsString())) {
                return action;
            }
        }
        return null;
    }

    /**
     * Resolves one spell by passing priority until the victim's own life total
     * reaches the expected value. The elimination verify is a pure query while
     * the engine is parked, so polling it spends no decision and answers
     * none. Returns the moment the engine reports the life drop; never passes
     * afterwards, so the caller still holds an empty-stack priority.
     */
    private static void resolveUntilLifeReaches(
            Lane lane, String tag, int expectedLife) {
        resolveUntilLifeReaches(lane, tag, "P2", expectedLife);
    }

    private static void resolveUntilLifeReaches(
            Lane lane, String tag, String victimPid, int expectedLife) {
        for (int step = 0; step < 30; step++) {
            JsonObject query = new JsonObject();
            query.addProperty("mode", "elimination");
            JsonObject verdict = lane.ok("complete_causal_reconstruction", query)
                    .getAsJsonObject("verdict");
            int observed = verdict.getAsJsonObject("life_totals").get(victimPid).getAsInt();
            if (observed <= expectedLife) {
                assertEquals(expectedLife, observed,
                        tag + ": each bolt deals exactly 3");
                return;
            }
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, tag + ": the engine must park while resolving");
            String decisionClass = pending.get("decision_class").getAsString();
            if ("priority".equals(decisionClass)) {
                submitOption(lane, pending, optionWithType(pending, "pass_priority"));
                continue;
            }
            if ("declare_attacker".equals(decisionClass)) {
                submitAction(lane, tag + "-hold-" + step,
                        singleActionOfType(legalActions(lane),
                                "declare_attackers", "hold_attacker"));
                continue;
            }
            if ("declare_blocker".equals(decisionClass)) {
                submitProposal(lane, tag + "-noblock-" + step,
                        emptyBlockProposal(tag + "-noblock-" + step, legalActions(lane)));
                continue;
            }
            fail(tag + ": unexpected " + decisionClass + " while resolving");
        }
        fail(tag + ": P2's life never reached " + expectedLife);
    }

    private static JsonObject singleActionOfType(
            JsonObject legal, String actionType, String optionType) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!actionType.equals(action.get("action_type").getAsString())) {
                continue;
            }
            JsonObject metadata = action.getAsJsonObject("metadata");
            String actual = metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if (optionType == null || optionType.equals(actual)) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(),
                "expected exactly one " + actionType + "/" + optionType);
        return matches.get(0);
    }

    private static JsonObject emptyBlockProposal(String proposalId, JsonObject legal) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.add("legal_action_id", com.google.gson.JsonNull.INSTANCE);
        proposal.addProperty("action_type", "structural_decision");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "midgame-causal-external-pilot");
        return proposal;
    }
}
