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
    // commander-status duality is measured, not papered over.
    // ------------------------------------------------------------------

    /**
     * Commander-status duality, measured on the production lane. The record's
     * battlefield commander is a setup copy without commander status, so a
     * genuine Doom Blade destroys it but the engine never offers the zone
     * choice. This test proves the causal stack reachable and the choice
     * absent — a measured BLOCKED with a decision-class trace, not a pass.
     */
    @Test
    void cmdZoneGyYesReachesCausalStackButChoiceStaysAbsent() {
        Lane lane = newLane();
        JsonArray fuel = new JsonArray();
        fuel.add(fuelCard("obj:fuel-swamp-a", "Swamp", "P2", "battlefield"));
        fuel.add(fuelCard("obj:fuel-swamp-b", "Swamp", "P2", "battlefield"));
        JsonObject created = lane.ok("create_midgame_game",
                causalStackCreate("causal-gy-yes", "WS05-CMD-ZONE-GY-YES", fuel));
        JsonObject causalPlan = created.getAsJsonObject("causal_plan");
        JsonObject frame = causalPlan.getAsJsonArray("frames_bottom_to_top")
                .get(0).getAsJsonObject();
        assertEquals("obj:cmd-zone-source", frame.get("semantic_id").getAsString());
        assertEquals("Doom Blade", frame.get("card_identity").getAsString());
        assertEquals("P2", frame.get("controller").getAsString());
        JsonObject placed = causalPlan.getAsJsonObject("placed_objects");
        String sourceId = frame.get("native_source_id").getAsString();
        String commanderCopyId = placed.get("obj:cmd-zone-test").getAsString();
        List<String> swampIds = List.of(
                placed.get("obj:fuel-swamp-a").getAsString(),
                placed.get("obj:fuel-swamp-b").getAsString());
        lane.ok("start_midgame_game", null);

        driveArrival(lane, "P1");
        castFrameSource(lane, "causal-gy-cast", sourceId);
        answerTarget(lane, "causal-gy-target", commanderCopyId);
        answerManaFromPool(lane, "causal-gy-mana", swampIds);

        JsonObject verify = new JsonObject();
        verify.addProperty("mode", "stack");
        JsonObject arrival = lane.ok("complete_causal_reconstruction", verify);
        assertEquals(true, arrival.getAsJsonObject("verdict")
                .get("causal_match").getAsBoolean(),
                "Doom Blade must be genuinely on the stack: "
                        + arrival.getAsJsonObject("verdict").getAsJsonArray("mismatches"));

        // Resolve fully, recording every decision class. The zone choice must
        // never appear for the setup copy; the game must reach cleanup,
        // proving normal progress without the choice rather than a stall.
        List<String> trace = new ArrayList<>();
        boolean reachedCleanupDiscard = false;
        for (int step = 0; step < 120; step++) {
            JsonObject pending = pendingDecision(lane, 5);
            if (pending == null) {
                break;
            }
            String decisionClass = pending.get("decision_class").getAsString();
            trace.add(decisionClass);
            if ("choose_object".equals(decisionClass)) {
                JsonObject decision = pending;
                if (decision.has("prompt") && !decision.get("prompt").isJsonNull()
                        && decision.get("prompt").getAsString().contains("discard")) {
                    reachedCleanupDiscard = true;
                    break;
                }
                fail("unexpected non-discard choose_object: " + pending);
            }
            if ("declare_attacker".equals(decisionClass)) {
                submitAction(lane, "causal-gy-hold-" + step,
                        singleActionOfType(legalActions(lane),
                                "declare_attackers", "hold_attacker"));
                continue;
            }
            if ("declare_blocker".equals(decisionClass)) {
                submitProposal(lane, "causal-gy-noblock-" + step,
                        emptyBlockProposal("causal-gy-noblock-" + step, legalActions(lane)));
                continue;
            }
            if (!"priority".equals(decisionClass)) {
                fail("unexpected " + decisionClass + " during resolution; trace=" + trace);
            }
            submitOption(lane, pending, optionWithType(pending, "pass_priority"));
        }
        assertTrue(reachedCleanupDiscard,
                "the game must progress to cleanup without any zone choice; trace=" + trace);
        assertTrue(trace.stream().noneMatch(c ->
                        "choice".equals(c) || "choose_use".equals(c)
                                || "replacement_effect".equals(c)),
                "no zone-choice decision may appear for the setup copy; trace=" + trace);
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
                        .getAsJsonObject("readback");
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
        for (int step = 0; step < 20; step++) {
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
            List<JsonObject> pool = new ArrayList<>();
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                if ("mana_pool".equals(action.getAsJsonObject("metadata")
                        .get("option_type").getAsString())) {
                    pool.add(action);
                }
            }
            assertEquals(1, pool.size(),
                    tag + ": expected exactly one engine-offered pool spend; offered: "
                            + legal.getAsJsonArray("actions"));
            submitAction(lane, tag + "-spend", pool.get(0));
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
     * Pays a multi-mana cost from declared fuel lands in order, then spends
     * each resulting pool mana. Returns only after the engine stops asking.
     */
    private static void answerManaFromPool(
            Lane lane, String tag, List<String> fuelNativeIds) {
        int fuelCursor = 0;
        for (int step = 0; step < 40; step++) {
            JsonObject pending = pendingDecision(lane);
            assertNotNull(pending, tag + ": the engine must ask for mana");
            if (!"mana_payment".equals(pending.get("decision_class").getAsString())) {
                return;
            }
            JsonObject legal = legalActions(lane);
            if (fuelCursor < fuelNativeIds.size()) {
                JsonObject ability =
                        findFuelAbility(legal, fuelNativeIds.get(fuelCursor));
                if (ability != null) {
                    submitAction(lane, tag + "-tap-" + fuelCursor, ability);
                    fuelCursor++;
                    continue;
                }
            }
            List<JsonObject> pool = new ArrayList<>();
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                if ("mana_pool".equals(action.getAsJsonObject("metadata")
                        .get("option_type").getAsString())) {
                    pool.add(action);
                }
            }
            assertEquals(1, pool.size(),
                    tag + ": expected exactly one engine-offered pool spend; offered: "
                            + legal.getAsJsonArray("actions"));
            submitAction(lane, tag + "-spend-" + step, pool.get(0));
        }
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
        for (int step = 0; step < 30; step++) {
            JsonObject query = new JsonObject();
            query.addProperty("mode", "elimination");
            JsonObject verdict = lane.ok("complete_causal_reconstruction", query)
                    .getAsJsonObject("verdict");
            int observed = verdict.getAsJsonObject("life_totals").get("P2").getAsInt();
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
        proposal.addProperty("legal_action_id", "empty-block");
        proposal.addProperty("action_type", "declare_blockers");
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
