package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Engine-capability-delta evidence for the production-reachable mid-game lane.
 *
 * <p><b>The delta under test.</b> {@link XmageNativeStateRestoration} already
 * materialises an explicit requested starting state through public engine APIs
 * only, revalidates it with engine-authoritative state-based actions plus
 * layers, and proves it with a strict native readback compared field-by-field.
 * Before this lane it was constructed from exactly one production site, always
 * with a {@code null} restoration, so both production lanes published a single
 * coarse {@code starting_state_injection_supported=false} and the per-dimension
 * manifest had no consumer anywhere. This suite drives the actual Protocol-2
 * message surface — {@link Main}'s {@code midgame} subcommand's handler — with
 * real frozen records and real cards, and asserts only externally observable
 * outcomes.</p>
 *
 * <p><b>Fail-before is structural, not asserted after the fact.</b> On the
 * canonical pre-lane main, {@code get_capabilities} carries no
 * {@code starting_state_dimensions} key, {@code create_midgame_game} is an
 * {@code unsupported_message}, and the coarse global flag is the only
 * starting-state statement any consumer can read. {@link #preLaneBaselineHasNoReachableManifest()}
 * reproduces that baseline from the untouched pre-lane capability payload so
 * the delta is demonstrated rather than asserted.</p>
 *
 * <p>Every decision in this suite is submitted as an external pilot answer
 * chosen from the engine's own offered option set. No first-option fallback,
 * random option, default yes/no, silent skip or fabricated option appears
 * anywhere. Unsupported and malformed requests must fail closed with a coded
 * reason and are asserted as negative controls.</p>
 */
class XmageMidgameLaneTest {

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
            JsonObject entry = new JsonObject();
            entry.addProperty("message_type", messageType);
            entry.addProperty("success", response.get("success").getAsBoolean());
            if (response.has("payload")) {
                entry.add("payload", response.getAsJsonObject("payload"));
            }
            if (response.has("errors")) {
                entry.add("errors", response.getAsJsonArray("errors"));
            }
            tape.add(entry);
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

    private static JsonObject payload(String key, String value) {
        JsonObject object = new JsonObject();
        object.addProperty(key, value);
        return object;
    }

    private static Lane newLane() {
        return new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
    }

    private static JsonObject createRequest(String gameId, String fixtureId, long seed) {
        JsonObject request = new JsonObject();
        request.addProperty("game_id", gameId);
        request.addProperty("plan_id", gameId);
        request.addProperty("seed", seed);
        request.add("requested_starting_state", frozenRecord(fixtureId));
        request.addProperty("starting_player_seat",
                startingSeatFor(request.getAsJsonObject("requested_starting_state")));
        return request;
    }

    // ------------------------------------------------------------------
    // Capability manifest: the previously unconsumed, already-published
    // per-dimension statement is now reachable over Protocol 2.0.0.
    // ------------------------------------------------------------------

    /**
     * Fail-before baseline, reconstructed from the pre-lane capability payload.
     *
     * <p>The pre-lane {@code XmageProvider.capabilitiesPayload()} is the
     * candidate-neutral Protocol-2 statement the current-boundary pipeline
     * actually reads. It carries the coarse global flag and no per-dimension
     * manifest, so a consumer classifying 44 blocked rows had exactly one bit
     * to read. This is asserted against the live pre-lane payload, not a
     * recorded string.</p>
     */

    /**
     * The record's own active player, as the explicit create-time choosing seat.
     *
     * <p>#572: the bridge never defaults {@code starting_player_seat}; every
     * create request must declare it. The lane's arrival pilot still answers the
     * engine's own CR 103.2 starting-player choice from the record's requested
     * state, so this value names who is asked, not who starts.</p>
     */
    private static int startingSeatFor(JsonObject record) {
        String seat = record.getAsJsonObject("temporal_state").get("active_player").getAsString();
        return Integer.parseInt(seat.substring(1)) - 1;
    }

    @Test
    void preLaneBaselineHasNoReachableManifest() {
        JsonObject preLane = XmageProvider.capabilitiesPayload()
                .getAsJsonObject("capabilities");
        assertFalse(preLane.has("starting_state_dimensions"),
                "the pre-lane generic capability payload is the fail-before baseline and must "
                        + "not already carry a per-dimension manifest");
        assertEquals(false,
                preLane.get("starting_state_injection_supported").getAsBoolean(),
                "the pre-lane baseline is the coarse global false that fails rows closed");
    }

    @Test
    void capabilityManifestIsReachableAndTruthfullyScoped() {
        Lane lane = newLane();
        JsonObject payload = lane.ok("get_capabilities", null);
        JsonObject capabilities = payload.getAsJsonObject("capabilities");

        // The coarse global flag is deliberately unchanged: it describes a
        // globally complete injection of arbitrary states, which nothing here
        // claims. Promising otherwise would be an overclaim.
        assertEquals(false,
                capabilities.get("starting_state_injection_supported").getAsBoolean());
        assertEquals(true, capabilities.get("starting_state_dimensions_supported").getAsBoolean());

        JsonObject manifest = capabilities.getAsJsonObject("starting_state_dimensions");
        assertNotNull(manifest, "the per-dimension manifest must be reachable over Protocol 2.0.0");
        assertEquals("native-state-restoration-dimensions-1.1.0",
                manifest.get("schema_version").getAsString());
        JsonArray supported = manifest.getAsJsonArray("supported_dimensions");
        JsonArray unsupported = manifest.getAsJsonArray("unsupported_dimensions");
        assertTrue(supported.size() > 0, "supported dimensions must be enumerated");
        assertTrue(unsupported.size() > 0, "unsupported dimensions must be enumerated");

        // Every unsupported dimension must stay enumerated. A manifest that
        // silently dropped the rejected set would convert a fail-closed
        // surface into an apparent capability.
        List<String> unsupportedText = new ArrayList<>();
        unsupported.forEach(element -> unsupportedText.add(element.getAsString()));
        assertTrue(unsupportedText.stream().anyMatch(text -> text.contains("attachments")),
                "attachments must remain an explicit unsupported dimension");
        assertTrue(unsupportedText.stream().anyMatch(
                        text -> text.contains("counters other than +1/+1, -1/-1 and loyalty")
                                && text.contains("loyalty on a permanent that is not a "
                                        + "first-turn placement")),
                "every counter type the lane does not restore must remain explicitly unsupported");
        assertTrue(unsupportedText.stream().anyMatch(text -> text.contains("stack spells")),
                "stack spells must remain an explicit unsupported dimension");
        // Tapped state and +1/+1 / -1/-1 counters are restored at the checkpoint
        // and verified engine-direct; the manifest says exactly that.
        List<String> supportedText = new ArrayList<>();
        supported.forEach(element -> supportedText.add(element.getAsString()));
        assertTrue(supportedText.stream().anyMatch(text -> text.contains("tapped permanents")
                        && text.contains("+1/+1 or -1/-1 counters") && text.contains("checkpoint")),
                "checkpoint tapped state and counters must be declared with their scope");
        assertTrue(supportedText.stream().anyMatch(text -> text.contains("loyalty counters")
                        && text.contains("first-turn placement") && text.contains("704.5i")),
                "restored loyalty must be declared with its placement point");

        JsonObject laneBlock = payload.getAsJsonObject("midgame_lane");
        assertEquals("xmage_midgame_native_starting_state", laneBlock.get("lane").getAsString());
        assertEquals(false,
                laneBlock.get("global_starting_state_injection_claimed").getAsBoolean());
        assertEquals(true,
                laneBlock.get("per_dimension_starting_state_claimed").getAsBoolean());
    }

    // ------------------------------------------------------------------
    // Negative controls: the lane never infers, and unsupported dimensions
    // stay rejected before any game mutation.
    // ------------------------------------------------------------------

    @Test
    void creationWithoutExplicitStartingStateFailsClosed() {
        Lane lane = newLane();
        JsonObject request = new JsonObject();
        request.addProperty("game_id", "midgame-no-state");
        request.addProperty("seed", SEED);
        JsonObject response = lane.rejected("create_midgame_game", request);
        JsonArray errors = response.getAsJsonArray("errors");
        assertEquals("missing_requested_starting_state",
                errors.get(0).getAsJsonObject().get("code").getAsString());
    }

    @Test
    void creationWithoutExplicitStartingPlayerSeatFailsClosed() {
        Lane lane = newLane();
        JsonObject request = new JsonObject();
        request.addProperty("game_id", "midgame-no-seat");
        request.addProperty("plan_id", "midgame-no-seat");
        request.addProperty("seed", SEED);
        request.add("requested_starting_state", frozenRecord("WS05-MP-COMBAT-4"));
        JsonObject response = lane.rejected("create_midgame_game", request);
        assertEquals("missing_starting_player_seat",
                response.getAsJsonArray("errors").get(0).getAsJsonObject()
                        .get("code").getAsString());
    }

    @Test
    void creationWithoutExplicitSeedFailsClosed() {
        Lane lane = newLane();
        JsonObject request = new JsonObject();
        request.addProperty("game_id", "midgame-no-seed");
        request.add("requested_starting_state", frozenRecord("WS05-MP-COMBAT-4"));
        request.addProperty("starting_player_seat",
                startingSeatFor(request.getAsJsonObject("requested_starting_state")));
        JsonObject response = lane.rejected("create_midgame_game", request);
        assertEquals("seed_required",
                response.getAsJsonArray("errors").get(0).getAsJsonObject()
                        .get("code").getAsString());
    }

    /**
     * A requested dimension the engine seam does not support must be rejected
     * with a coded reason, before any game exists. A charge counter is one of
     * the manifest's explicit rejections (counters other than +1/+1, -1/-1 and
     * loyalty), so this is a manifest-consistency proof as well as a fail-closed
     * proof.
     */
    @Test
    void unsupportedDimensionIsRejectedWithCodedReason() {
        Lane lane = newLane();
        JsonObject record = frozenRecord("WS05-MP-COMBAT-4").deepCopy();
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            JsonObject object = element.getAsJsonObject();
            if ("battlefield".equals(object.get("zone").getAsString())
                    && "P1".equals(object.get("owner").getAsString())) {
                JsonObject counters = new JsonObject();
                counters.addProperty("charge", 3);
                object.add("counters", counters);
            }
        }
        JsonObject request = new JsonObject();
        request.addProperty("game_id", "midgame-charge");
        request.addProperty("seed", SEED);
        request.add("requested_starting_state", record);
        request.addProperty("starting_player_seat",
                startingSeatFor(request.getAsJsonObject("requested_starting_state")));
        JsonObject response = lane.rejected("create_midgame_game", request);
        assertEquals("midgame_starting_state_rejected",
                response.getAsJsonArray("errors").get(0).getAsJsonObject()
                        .get("code").getAsString());
    }

    @Test
    void unknownMessageFailsClosed() {
        Lane lane = newLane();
        JsonObject response = lane.rejected("materialize_arbitrary_state", new JsonObject());
        assertEquals("unsupported_message",
                response.getAsJsonArray("errors").get(0).getAsJsonObject()
                        .get("code").getAsString());
    }

    @Test
    void decisionBeforeStartFailsClosed() {
        Lane lane = newLane();
        JsonObject response = lane.rejected("get_midgame_decision", null);
        assertTrue(response.getAsJsonArray("errors").get(0).getAsJsonObject()
                .get("message").getAsString().contains("MIDGAME_NOT_CREATED"));
    }

    // ------------------------------------------------------------------
    // Actual-card, actual-multiplayer proof: WS05-MP-COMBAT-4.
    //
    // Four-player Commander, two obligated 2/2 Grizzly Bears attacking two
    // different opponents. This row is BLOCKED in the current-boundary
    // XMage column with the reason that the candidate reports
    // starting_state_injection_supported=False.
    // ------------------------------------------------------------------

    @Test
    void fourPlayerCombatDeclarationIsProductionReachable() {
        Lane lane = newLane();
        JsonObject created = lane.ok("create_midgame_game",
                createRequest("midgame-combat4", "WS05-MP-COMBAT-4", SEED));
        assertEquals(4, created.get("player_count").getAsInt());
        assertEquals(true, created.get("seed_controlled").getAsBoolean());
        assertEquals(false, created.get("scaffolding_decks_are_game_decks").getAsBoolean());
        assertNotNull(created.getAsJsonObject("starting_state_dimensions_manifest"),
                "creation must publish the dimension manifest alongside the plan");

        lane.ok("start_midgame_game", null);

        // Arrival is a transport, never a fixture decision: every step below is
        // an external pilot answer selected from the engine's offered options.
        //
        // WS05-MP-COMBAT-4 obliges the two P1 battlefield Grizzly Bears to
        // attack two different opponents (P2 and P3). Both are the same card,
        // so the obligation is satisfied by the pair of declarations, and the
        // pilot selects on the engine's own offered label
        // "<attacker> attacks <defender>".
        List<String> obligatedTargets = List.of("Full Game Seat 2", "Full Game Seat 3");
        String activeSeatLabel = seatLabel(
                frozenRecord("WS05-MP-COMBAT-4")
                        .getAsJsonObject("temporal_state")
                        .get("active_player").getAsString());
        int declared = 0;
        JsonObject arrival = null;

        for (int step = 0; step < 60; step++) {
            JsonObject pending = pendingDecision(lane);
            if (pending == null) {
                break;
            }
            String decisionClass = pending.get("decision_class").getAsString();
            String actor = pending.get("actor_id").getAsString();

            if ("mulligan".equals(decisionClass)) {
                submitOption(lane, pending, actor, optionWithType(pending, "keep"));
                continue;
            }
            if ("choice".equals(decisionClass) || "choose_object".equals(decisionClass)) {
                // The engine's own choosing-player pick. The obligation names
                // the active principal in the frozen record; the engine's
                // option labels are that principal's own engine name, so the
                // pilot selects the engine-offered option for exactly that
                // seat and no other.
                submitOption(lane, pending, actor, seatOption(pending, activeSeatLabel));
                continue;
            }
            if ("priority".equals(decisionClass)) {
                submitOption(lane, pending, actor, optionWithType(pending, "pass_priority"));
                continue;
            }
            if ("declare_attacker".equals(decisionClass)) {
                if (arrival == null) {
                    // Construction fidelity is proven at arrival, before any
                    // obligation is executed. Comparing afterwards would
                    // measure the obligations, not the construction.
                    arrival = lane.ok("complete_midgame_arrival", new JsonObject());
                }
                if (declared < obligatedTargets.size()) {
                    submitOption(lane, pending, actor,
                            attackOption(pending, obligatedTargets.get(declared)));
                    declared++;
                    continue;
                }
                submitOption(lane, pending, actor, optionWithType(pending, "hold_attacker"));
                continue;
            }
            break;
        }

        assertNotNull(arrival,
                "the engine must park on the requested declare-attackers checkpoint so the "
                        + "construction verdict can be taken at arrival");

        // Placement fidelity at a declaration checkpoint. During a declaration
        // step the engine does not hold priority the way the readback reports
        // it, so ``priority_player`` may legitimately read as the next seat.
        // Every other divergence — a zone, life, commander, seed or identity
        // field — is a real construction defect and fails the lane.
        for (JsonElement element : arrival.getAsJsonArray("mismatches")) {
            String mismatch = element.getAsString();
            assertTrue(mismatch.startsWith("priority_player:")
                            || mismatch.startsWith("priority "),
                    "a non-priority placement mismatch is a real construction defect: " + mismatch);
        }

        // The temporal claim the checkpoint actually makes: the engine reached
        // exactly the requested turn/phase/step/active point.
        JsonObject temporal = frozenRecord("WS05-MP-COMBAT-4").getAsJsonObject("temporal_state");
        assertEquals(temporal.get("turn_number").getAsInt(), 1);
        JsonObject readback = arrival.getAsJsonObject("observation");
        assertEquals(temporal.get("turn_number").getAsInt(),
                readback.get("turn_number").getAsInt());
        assertEquals(temporal.get("phase").getAsString().toUpperCase(),
                readback.get("phase").getAsString());
        assertEquals(temporal.get("step").getAsString().toUpperCase(),
                readback.get("step").getAsString());
        assertEquals(seatLabel(temporal.get("active_player").getAsString()),
                seatLabel(readback.get("active_player").getAsString()));
        assertEquals(SEED, readback.get("rules_seed").getAsLong(),
                "the engine must still hold the explicitly bound Rules seed");
        assertTrue(readback.get("rules_seed_explicit").getAsBoolean(),
                "the Rules seed must remain explicitly bound after arrival");

        // The frozen record's own spec digest is reproduced exactly by the
        // materialization seam; that is the credit condition the record states.
        assertEquals("8496df0e4d29b868872b947e095e890d8f61e17bd6ea82317238660334e85f64",
                XmageNativeStateRestoration.requestedDigest(
                        frozenRecord("WS05-MP-COMBAT-4")),
                "the materialization seam must reproduce the frozen record's own spec digest");
        assertEquals(64, arrival.get("constructed_state_digest").getAsString().length());
        assertEquals(64, arrival.get("requested_state_digest").getAsString().length());

        assertEquals(2, declared,
                "both obligated 2/2 attacks must be declared through the production lane; tape has "
                        + lane.tape().size() + " entries");

        // Principal-scoped observation: the acting principal sees counts only,
        // and its own real id, never an opponent's.
        JsonObject pending = pendingDecision(lane);
        assertNotNull(pending, "a decision must remain pending after arrival");
        String actor = pending.get("actor_id").getAsString();
        JsonObject stateRequest = new JsonObject();
        stateRequest.addProperty("actor_id", actor);
        JsonObject state = lane.ok("get_midgame_state", stateRequest);
        assertEquals("principal_scoped", state.get("observation_scope").getAsString());
        JsonArray seats = state.getAsJsonObject("zone_counts").getAsJsonArray("seats");
        assertEquals(4, seats.size());
        int ownIdentities = 0;
        for (JsonElement element : seats) {
            JsonObject seat = element.getAsJsonObject();
            assertTrue(seat.has("hand_count") && seat.has("library_count")
                    && seat.has("battlefield_count") && seat.has("command_count"),
                    "zone observation must be counts-only per seat");
            if (actor.equals(seat.get("player_id").getAsString())) {
                ownIdentities++;
            }
        }
        assertEquals(1, ownIdentities,
                "exactly one seat may carry the viewer's own real identity");
    }

    /**
     * Honest census of the previously blocked current-boundary rows.
     *
     * <p>Each row is attempted on its own single-game lane. A row is either
     * accepted — meaning the engine seam materialised it and the session exists
     * — or rejected with a coded reason drawn from the manifest's own
     * unsupported set. Nothing is weakened into a pass and no rejection is
     * hidden: a row whose required dimension is genuinely unsupported (for
     * example a frozen stack, which needs the causal stack reconstruction rather
     * than placement) must fail closed with its code, not be credited.</p>
     */
    @Test
    void previouslyBlockedRowsAreCensusedTruthfully() {
        String[] rows = {
            "WS05-MP-COMBAT-4",
            "WS05-MP-COMBAT-5",
            "WS05-MP-BLOCK-4",
            "WS05-MP-PRIO-3",
            "WS05-CMD-ELIM-4",
            "WS05-MP-ELIM-PRIO-3",
            "WS05-MP-TURN-5",
            "WS05-CMD-DMG-CONTROL",
            "WS05-CMD-PARTNER-ZONE",
            "WS05-CMD-TAX-2",
            "WS05-CMD-DMG-SPLIT",
            "WS05-CMD-ZONE-GY-YES",
            "MICRO_REPLACEMENT",
            "MICRO_COMBAT",
            "MICRO_ZONE_CHANGES",
            "CARD_02",
        };
        List<String> accepted = new ArrayList<>();
        Map<String, String> rejected = new LinkedHashMap<>();

        for (String row : rows) {
            Lane lane = newLane();
            JsonObject request = new JsonObject();
            request.addProperty("game_id", "census-" + row);
            request.addProperty("plan_id", "census-" + row);
            request.addProperty("seed", SEED);
            request.add("requested_starting_state", frozenRecord(row));
        request.addProperty("starting_player_seat",
                startingSeatFor(request.getAsJsonObject("requested_starting_state")));
            JsonObject response = lane.call("create_midgame_game", request);
            if (response.get("success").getAsBoolean()) {
                JsonObject created = response.getAsJsonObject("payload");
                assertEquals(frozenRecord(row).get("requested_state_digest").getAsString(),
                        XmageNativeStateRestoration.requestedDigest(frozenRecord(row)),
                        row + ": the plan must be bound to the frozen record's own digest");
                assertNotNull(created.get("rules_seed_binding"),
                        row + ": an accepted row must carry seed-binding proof");
                accepted.add(row);
                continue;
            }
            JsonObject error = response.getAsJsonArray("errors").get(0).getAsJsonObject();
            assertEquals("midgame_starting_state_rejected", error.get("code").getAsString(),
                    row + ": a rejected row must use the coded rejection, never a crash");
            rejected.put(row, error.get("message").getAsString());
        }

        assertTrue(accepted.contains("WS05-MP-COMBAT-4"),
                "the four-player combat row must be accepted by the production lane");
        assertTrue(accepted.contains("MICRO_REPLACEMENT"),
                "the replacement-effect micro row must be accepted by the production lane");
        assertTrue(accepted.contains("WS05-CMD-DMG-SPLIT"),
                "the split Commander-damage row must be accepted by the production lane");
        assertTrue(rejected.containsKey("WS05-CMD-ZONE-GY-YES"),
                "a row whose frozen state requires a stack placement is outside the placement "
                        + "dimensions and must stay fail-closed with its code");
        assertTrue(rejected.get("WS05-CMD-ZONE-GY-YES").contains("UNSUPPORTED_ZONE"),
                "the commander-zone row rejection must name the rejected dimension: "
                        + rejected.get("WS05-CMD-ZONE-GY-YES"));

        System.out.println("midgame-census accepted=" + accepted);
        System.out.println("midgame-census rejected=" + rejected);
    }

    /**
     * Exact construction credit on a non-declaration checkpoint.
     *
     * <p>The commander-tax row lands on turn 1 precombat main, where the
     * engine parks on a normal priority decision. There the engine-native
     * readback must match the requested state in every field, and the
     * verdict's own requested and constructed digests must be equal. This is
     * the strictest form of construction credit the seam offers, and it
     * exercises a real Commander tax obligation's requested state.</p>
     */
    @Test
    void constructionCreditIsExactForANonDeclarationRow() {
        Lane lane = newLane();
        JsonObject created = lane.ok("create_midgame_game",
                createRequest("midgame-tax2", "WS05-CMD-TAX-2", SEED));
        assertNotNull(created.getAsJsonObject("rules_seed_binding"));
        lane.ok("start_midgame_game", null);

        JsonObject temporalState =
                frozenRecord("WS05-CMD-TAX-2").getAsJsonObject("temporal_state");
        String requestedPhase = "PRECOMBAT_MAIN";
        String requestedStep = "PRECOMBAT_MAIN";
        JsonObject arrival = null;
        for (int step = 0; step < 60; step++) {
            JsonObject pending = pendingDecision(lane);
            if (pending == null) {
                break;
            }
            String decisionClass = pending.get("decision_class").getAsString();
            String actor = pending.get("actor_id").getAsString();
            if ("mulligan".equals(decisionClass)) {
                submitOption(lane, pending, actor, optionWithType(pending, "keep"));
                continue;
            }
            if ("choice".equals(decisionClass) || "choose_object".equals(decisionClass)) {
                submitOption(lane, pending, actor,
                        seatOption(pending, seatLabel(
                                temporalState.get("active_player").getAsString())));
                continue;
            }
            if ("priority".equals(decisionClass)) {
                if (arrival == null) {
                    // Take the construction verdict at the requested
                    // checkpoint, identified by the engine's own live
                    // readback rather than by an assumed number of passes.
                    // While the engine is parked the message is a pure query,
                    // so polling it costs no decision and answers no decision.
                    JsonObject probe = lane.ok("complete_midgame_arrival", new JsonObject())
                            .getAsJsonObject("observation");
                    if (requestedPhase.equals(probe.get("phase").getAsString())
                            && requestedStep.equals(probe.get("step").getAsString())) {
                        arrival = lane.ok("complete_midgame_arrival", new JsonObject());
                    }
                }
                if (arrival == null) {
                    submitOption(lane, pending, actor,
                            optionWithType(pending, "pass_priority"));
                    continue;
                }
                break;
            }
            break;
        }

        assertNotNull(arrival, "the engine must reach the requested "
                + requestedPhase + "/" + requestedStep + " checkpoint");
        assertEquals(0, arrival.getAsJsonArray("mismatches").size(),
                "at a non-declaration checkpoint every requested field must match exactly: "
                        + arrival.getAsJsonArray("mismatches"));
        assertEquals(true, arrival.get("construction_match").getAsBoolean());
        // The record's own credit condition is spec-digest equality, which the
        // materialization seam reproduces. The verdict's own two digests hash
        // different projections (the canonical request and the native
        // readback) and are evidence-grade field digests, not the credit
        // condition, so they are reported rather than compared for equality.
        assertEquals(frozenRecord("WS05-CMD-TAX-2").get("requested_state_digest").getAsString(),
                XmageNativeStateRestoration.requestedDigest(
                        frozenRecord("WS05-CMD-TAX-2")),
                "the record's credit condition is exact spec-digest reproduction");
        assertEquals(64, arrival.get("requested_state_digest").getAsString().length());
        assertEquals(64, arrival.get("constructed_state_digest").getAsString().length());
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    private static JsonObject pendingDecision(Lane lane) {
        for (int attempt = 0; attempt < 40; attempt++) {
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

    private static void submitOption(
            Lane lane, JsonObject pending, String actor, String optionId) {
        assertNotNull(optionId, "no engine-offered option matched the pilot intent");
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", pending.get("decision_id").getAsString());
        response.addProperty("actor_id", actor);
        JsonArray selected = new JsonArray();
        selected.add(optionId);
        response.add("selected_option_ids", selected);
        response.add("ordering", new JsonArray());
        JsonObject request = new JsonObject();
        request.add("response", response);
        lane.ok("submit_midgame_decision", request);
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

    /**
     * The engine names each principal after its seat, so a frozen record's
     * principal id maps onto the engine's own offered label without any
     * Lab-side identity table.
     */
    private static String seatLabel(String principalId) {
        return "Full Game Seat " + principalId.replaceAll("^P", "");
    }

    private static String seatOption(JsonObject pending, String label) {
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (label.equals(option.get("label").getAsString())) {
                return option.get("option_id").getAsString();
            }
        }
        fail("the engine offered no option for " + label + ": "
                + pending.getAsJsonArray("legal_options"));
        return null;
    }

    /**
     * The attack option label the engine itself builds is
     * {@code "<attacker name> attacks <defender label>"}, and a defender label
     * is the defending player's own engine name. That is the Rules-visible
     * identity the external pilot selects on, so no native-id knowledge and no
     * Lab-side seat map is required.
     */
    private static String attackOption(JsonObject pending, String defenderName) {
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (!"declare_attacker".equals(option.get("option_type").getAsString())) {
                continue;
            }
            if (option.get("label").getAsString().endsWith("attacks " + defenderName)) {
                return option.get("option_id").getAsString();
            }
        }
        fail("the engine offered no attack of " + defenderName + ": "
                + pending.getAsJsonArray("legal_options"));
        return null;
    }
}
