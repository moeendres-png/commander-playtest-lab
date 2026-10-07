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

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Adversarial principal-scoping evidence for the mid-game lane.
 *
 * <p><b>What is under attack.</b> {@code XmageNativeStateRestoration.readback}
 * is an engine-direct construction readback that carries every seat's full
 * hand identity and is documented as test-only. If the lane returned it, a
 * pilot acting for one principal could read another principal's hand. These
 * tests plant distinct honeycards in P2's, P3's and P4's hands and then prove
 * that the acting principal cannot recover any of them from any lane
 * observation, verification or error payload.</p>
 *
 * <p>The honeycards are real, importable cards whose names are unique in the
 * scenario, so a single plain-text scan of the whole response line is a valid
 * leak detector: if the name appears anywhere in the JSON the secret crossed
 * the boundary, regardless of which field carried it.</p>
 */
class XmageMidgamePrivacyTest {

    private static final long SEED = 424242L;

    /** Distinct honeycard names, one per opposing principal. */
    private static final String P2_HONEYCARD = "Runeclaw Bear";
    private static final String P3_HONEYCARD = "Serra Angel";
    private static final String P4_HONEYCARD = "Sol Ring";

    private record Lane(XmageMidgameJsonlBridge bridge, List<String> responses) {

        String raw(String messageType, JsonObject payload) {
            JsonObject request = new JsonObject();
            request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
            request.addProperty("request_id", messageType + "-" + responses.size());
            request.addProperty("message_type", messageType);
            if (payload != null) {
                request.add("payload", payload);
                request.add("params", payload);
            }
            String json = bridge.handle(request.toString()).json();
            responses.add(json);
            return json;
        }

        JsonObject ok(String messageType, JsonObject payload) {
            JsonObject response = JsonParser.parseString(raw(messageType, payload))
                    .getAsJsonObject();
            if (!response.get("success").getAsBoolean()) {
                fail(messageType + " must succeed: " + response.getAsJsonArray("errors"));
            }
            return response.getAsJsonObject("payload");
        }

        JsonObject rejected(String messageType, JsonObject payload) {
            JsonObject response = JsonParser.parseString(raw(messageType, payload))
                    .getAsJsonObject();
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

    /** Adds a hidden hand object for one principal to a record copy. */
    private static void addHoneycard(
            JsonObject record, String semanticId, String card, String owner) {
        JsonObject object = new JsonObject();
        object.addProperty("semantic_id", semanticId);
        object.addProperty("card_identity", card);
        object.addProperty("owner", owner);
        object.addProperty("controller", owner);
        object.addProperty("zone", "hand");
        object.addProperty("tapped", false);
        object.add("counters", new JsonObject());
        record.getAsJsonArray("semantic_objects").add(object);
    }

    private static JsonObject createRequest(
            String gameId, JsonObject record, String entryMode, JsonArray fuel) {
        JsonObject request = new JsonObject();
        request.addProperty("game_id", gameId);
        request.addProperty("plan_id", gameId);
        request.addProperty("seed", SEED);
        if (entryMode != null) {
            request.addProperty("entry_mode", entryMode);
        }
        request.add("requested_starting_state", record);
        request.addProperty("starting_player_seat",
                startingSeatFor(request.getAsJsonObject("requested_starting_state")));
        if (fuel != null) {
            request.add("fuel", fuel);
        }
        return request;
    }

    /** Advances arrival transport until the engine parks on a precombat priority. */
    private static void driveArrival(Lane lane, String activeLabel) {
        for (int step = 0; step < 60; step++) {
            JsonObject decision = pendingDecision(lane);
            if (decision == null) {
                break;
            }
            String decisionClass = decision.get("decision_class").getAsString();
            if ("mulligan".equals(decisionClass)) {
                submitOption(lane, decision, optionOfType(decision, "keep"));
                continue;
            }
            if ("choice".equals(decisionClass) || "choose_object".equals(decisionClass)) {
                submitOption(lane, decision, optionByLabelSuffix(decision, activeLabel));
                continue;
            }
            if ("priority".equals(decisionClass)) {
                JsonObject observation = lane.ok("complete_midgame_arrival", new JsonObject())
                        .getAsJsonObject("observation");
                if ("PRECOMBAT_MAIN".equals(observation.get("phase").getAsString())) {
                    return;
                }
                submitOption(lane, decision, optionOfType(decision, "pass_priority"));
                continue;
            }
            break;
        }
    }

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

    private static void submitOption(Lane lane, JsonObject decision, String optionId) {
        assertNotNull(optionId, "no engine-offered option matched the pilot intent");
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", decision.get("decision_id").getAsString());
        response.addProperty("actor_id", decision.get("actor_id").getAsString());
        JsonArray selected = new JsonArray();
        selected.add(optionId);
        response.add("selected_option_ids", selected);
        response.add("ordering", new JsonArray());
        JsonObject request = new JsonObject();
        request.add("response", response);
        lane.ok("submit_midgame_decision", request);
    }

    private static String optionOfType(JsonObject decision, String optionType) {
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (optionType.equals(option.get("option_type").getAsString())) {
                return option.get("option_id").getAsString();
            }
        }
        fail("the engine offered no " + optionType + ": " + decision);
        return null;
    }

    private static String optionByLabelSuffix(JsonObject decision, String suffix) {
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (option.get("label").getAsString().endsWith(suffix)) {
                return option.get("option_id").getAsString();
            }
        }
        fail("the engine offered no option ending " + suffix + ": " + decision);
        return null;
    }

    /**
     * The real principal id of the seat that must act, learned from the
     * engine's own decision frame. Seat index is public information; the id is
     * what the lane's principal-scoped messages address.
     */
    private static String principalIdAtSeat(Lane lane, int seatIndex) {
        for (int step = 0; step < 20; step++) {
            JsonObject decision = pendingDecision(lane);
            assertNotNull(decision, "the engine must offer a decision to address a principal");
            if (decision.get("seat").getAsInt() == seatIndex) {
                return decision.get("actor_id").getAsString();
            }
            // Keep the engine moving until the wanted seat holds a decision.
            String decisionClass = decision.get("decision_class").getAsString();
            if ("mulligan".equals(decisionClass)) {
                submitOption(lane, decision, optionOfType(decision, "keep"));
                continue;
            }
            fail("could not reach seat " + seatIndex + " without consuming an unknown decision: "
                    + decisionClass);
        }
        fail("seat never held a decision");
        return null;
    }

    private static void assertNoHoneycard(String context, String json) {
        for (String honeycard : List.of(P2_HONEYCARD, P3_HONEYCARD, P4_HONEYCARD)) {
            assertFalse(json.contains(honeycard),
                    context + " leaked an opposing principal's hand identity (" + honeycard
                            + "): " + json);
        }
    }

    /**
     * A placement game whose opposing hands hold distinct honeycards. Every
     * lane surface addressed to P1 must be honeycard-free, while the engine's
     * internal construction verdict must still be exact.
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
    void opposingHandIdentitiesNeverCrossTheBoundary() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        // DMG-SPLIT's requested checkpoint is turn-1 precombat main in a
        // four-player Commander game, which the arrival transport reaches
        // exactly, so the engine's construction verdict is provably exact
        // while the honeycards sit in opponents' hands and never appear in
        // any scoped observation.
        JsonObject record = frozenRecord("WS05-CMD-DMG-SPLIT").deepCopy();
        addHoneycard(record, "obj:honey-p2", P2_HONEYCARD, "P2");
        addHoneycard(record, "obj:honey-p3", P3_HONEYCARD, "P3");
        addHoneycard(record, "obj:honey-p4", P4_HONEYCARD, "P4");

        JsonObject created = lane.ok("create_midgame_game",
                createRequest("privacy-honeycards", record, null, null));
        assertFalse(created.toString().contains(P2_HONEYCARD),
                "game creation must not echo an opposing hand identity");
        lane.ok("start_midgame_game", null);

        String p1Id = principalIdAtSeat(lane, 0);
        driveArrival(lane, "Full Game Seat 1");

        // 1. Arrival with no requester: the public view.
        String arrivalRaw = lane.raw("complete_midgame_arrival", new JsonObject());
        assertNoHoneycard("public arrival", arrivalRaw);
        JsonObject publicArrival = JsonParser.parseString(arrivalRaw).getAsJsonObject()
                .getAsJsonObject("payload");
        assertEquals("principal_neutral_opponent_hands_counts_only",
                publicArrival.get("observation_scope").getAsString());
        assertTrue(publicArrival.get("construction_match").getAsBoolean(),
                "the engine's exact construction verdict must be preserved: "
                        + publicArrival.getAsJsonArray("mismatches"));
        for (JsonElement element
                : publicArrival.getAsJsonObject("observation").getAsJsonArray("seats")) {
            assertFalse(element.getAsJsonObject().has("hand"),
                    "an unbound observation must carry no hand identity for any seat");
        }

        // 2. Arrival scoped to P1: own hand allowed, opponents counts only.
        JsonObject scopedRequest = new JsonObject();
        scopedRequest.addProperty("actor_id", p1Id);
        String scopedRaw = lane.raw("complete_midgame_arrival", scopedRequest);
        assertNoHoneycard("principal-scoped arrival", scopedRaw);
        JsonObject scopedArrival = JsonParser.parseString(scopedRaw).getAsJsonObject()
                .getAsJsonObject("payload");
        assertEquals("principal_scoped", scopedArrival.get("observation_scope").getAsString());
        assertTrue(scopedArrival.get("construction_match").getAsBoolean(),
                "the engine's exact construction verdict must survive redaction: "
                        + scopedArrival.getAsJsonArray("mismatches"));
        int ownHandArrays = 0;
        for (JsonElement element
                : scopedArrival.getAsJsonObject("observation").getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            if (seat.has("hand")) {
                ownHandArrays++;
                assertEquals("P1", seat.get("player_id").getAsString(),
                        "only the requesting principal may receive a hand array");
            }
        }
        assertEquals(1, ownHandArrays,
                "exactly one hand array, and only for the requesting principal");

        // The requester binding also accepts the requested-state principal
        // label directly; both bindings must resolve to the same scoped view.
        JsonObject labelRequest = new JsonObject();
        labelRequest.addProperty("actor_id", "P1");
        JsonObject labelArrival = lane.ok("complete_midgame_arrival", labelRequest);
        assertEquals("principal_scoped",
                labelArrival.get("observation_scope").getAsString());
        int labelHandArrays = 0;
        for (JsonElement element
                : labelArrival.getAsJsonObject("observation").getAsJsonArray("seats")) {
            if (element.getAsJsonObject().has("hand")) {
                labelHandArrays++;
            }
        }
        assertEquals(1, labelHandArrays,
                "the label binding must produce the same one-hand scoped view");

        // 3. Normal mid-game state observation.
        JsonObject stateRequest = new JsonObject();
        stateRequest.addProperty("actor_id", p1Id);
        String stateRaw = lane.raw("get_midgame_state", stateRequest);
        assertNoHoneycard("midgame state", stateRaw);

        // 4. Error payloads from causal verification on a placement game.
        JsonObject causalRequest = new JsonObject();
        causalRequest.addProperty("mode", "stack");
        String causalErrorRaw = lane.raw("complete_causal_reconstruction", causalRequest);
        assertFalse(JsonParser.parseString(causalErrorRaw).getAsJsonObject()
                .get("success").getAsBoolean());
        assertNoHoneycard("causal verification error", causalErrorRaw);

        // 5. The pending decision surface currently addressed to P1. A
        // decision frame is addressed to the acting principal and shows that
        // principal its own hand by design; the acting seat here is P1, so no
        // opposing hand identity may appear.
        String decisionRaw = lane.raw("get_midgame_decision", null);
        assertNoHoneycard("pending decision frame", decisionRaw);
    }

    /**
     * A causal game whose third principal holds a honeycard in hand: the stack
     * verification payload must not expose it.
     */
    @Test
    void causalVerificationNeverExposesABystanderHand() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject record = frozenRecord("MICRO_ZONE_CHANGES").deepCopy();
        addHoneycard(record, "obj:honey-p4", P4_HONEYCARD, "P4");
        JsonArray fuel = new JsonArray();
        JsonObject mountain = new JsonObject();
        mountain.addProperty("semantic_id", "obj:fuel-mountain-p1");
        mountain.addProperty("card_identity", "Mountain");
        mountain.addProperty("owner", "P1");
        mountain.addProperty("zone", "battlefield");
        fuel.add(mountain);

        lane.ok("create_midgame_game",
                createRequest("privacy-causal", record, "causal_stack", fuel));
        lane.ok("start_midgame_game", null);
        String p1Id = principalIdAtSeat(lane, 0);
        driveArrival(lane, "Full Game Seat 1");

        // Cast P1's bolt through the engine, then verify the stack.
        JsonObject decision = pendingDecision(lane);
        assertNotNull(decision, "the engine must park for the cast");
        JsonObject legal = lane.ok("get_legal_actions", null);
        JsonObject cast = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            JsonObject engine = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
            if (engine.has("ability_type")
                    && "spell".equals(engine.get("ability_type").getAsString())) {
                cast = action;
                break;
            }
        }
        assertNotNull(cast, "the engine must offer the causal cast");
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "privacy-causal-cast");
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", cast.get("action_id").getAsString());
        proposal.addProperty("action_type", cast.get("action_type").getAsString());
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "privacy-adversarial");
        JsonObject proposalRequest = new JsonObject();
        proposalRequest.add("proposal", proposal);
        lane.ok("submit_action", proposalRequest);

        // Answer target and mana until the stack verify succeeds is not the
        // point here: what matters is that no verification or error payload
        // carries the bystander's hidden identity. Scan every response of this
        // scenario, including the pending decision frames served per seat.
        for (int step = 0; step < 6; step++) {
            JsonObject pending = pendingDecision(lane);
            if (pending == null) {
                break;
            }
            String decisionClass = pending.get("decision_class").getAsString();
            if ("target".equals(decisionClass)) {
                JsonObject legalTargets = lane.ok("get_legal_actions", null);
                for (JsonElement element : legalTargets.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    if ("target".equals(action.getAsJsonObject("metadata")
                            .get("option_type").getAsString())) {
                        JsonObject targetProposal = new JsonObject();
                        targetProposal.addProperty("proposal_id", "privacy-target-" + step);
                        targetProposal.addProperty("actor_id",
                                legalTargets.get("actor_id").getAsString());
                        targetProposal.addProperty("legal_action_id",
                                action.get("action_id").getAsString());
                        targetProposal.addProperty("action_type",
                                action.get("action_type").getAsString());
                        targetProposal.add("target_ids", new JsonArray());
                        targetProposal.add("selected_modes", new JsonArray());
                        JsonObject targetChoices = new JsonObject();
                        targetChoices.add("ordering", new JsonArray());
                        targetProposal.add("choices", targetChoices);
                        targetProposal.addProperty("decision_tier", 1);
                        targetProposal.addProperty("policy_name", "privacy-adversarial");
                        JsonObject targetRequest = new JsonObject();
                        targetRequest.add("proposal", targetProposal);
                        lane.ok("submit_action", targetRequest);
                        break;
                    }
                }
                continue;
            }
            if ("mana_payment".equals(decisionClass)) {
                String passed = optionOfType(pending, "cancel_mana_payment");
                submitOption(lane, pending, passed);
                continue;
            }
            break;
        }
        JsonObject verifyRequest = new JsonObject();
        verifyRequest.addProperty("mode", "stack");
        String verifyRaw = lane.raw("complete_causal_reconstruction", verifyRequest);
        assertNoHoneycard("causal verification payload", verifyRaw);
        assertFalse(JsonParser.parseString(verifyRaw).getAsJsonObject()
                        .getAsJsonObject("payload").has("pending_decision"),
                "a verification payload must not embed a decision frame");

        // The surfaces the requirement names, each addressed without a
        // principal or to P1.
        String publicArrivalRaw = lane.raw("complete_midgame_arrival", new JsonObject());
        assertNoHoneycard("public arrival", publicArrivalRaw);
        JsonObject scoped = new JsonObject();
        scoped.addProperty("actor_id", p1Id);
        assertNoHoneycard("principal-scoped arrival",
                lane.raw("complete_midgame_arrival", scoped));
        JsonObject stateRequest = new JsonObject();
        stateRequest.addProperty("actor_id", p1Id);
        assertNoHoneycard("midgame state", lane.raw("get_midgame_state", stateRequest));
    }

    /**
     * The mismatch redactor itself. The engine's hand-subset message names the
     * owning seat (public) and the card identity (hidden): a wrong principal or
     * an unbound caller must receive the identity-free placeholder while the
     * owner and the public counts survive. The opaque native id is removed for
     * every requester. Public-zone, temporal and count mismatches pass through.
     */
    @Test
    void hiddenMismatchIdentitiesAreRedactedForTheWrongPrincipal() {
        String handSubset = "hand subset P2|HAND|" + P2_HONEYCARD
                + "|tapped=false|controller=P2: requested 1 observed 0";

        String unbound = XmageMidgameJsonlBridge.redactMismatch(handSubset, null);
        assertFalse(unbound.contains(P2_HONEYCARD),
                "an unbound caller must not receive a hand identity: " + unbound);
        assertTrue(unbound.startsWith("hand subset P2"),
                "the owning seat is public and must survive: " + unbound);
        assertTrue(unbound.contains("requested 1 observed 0"),
                "the public counts must survive: " + unbound);

        String wrongPrincipal = XmageMidgameJsonlBridge.redactMismatch(handSubset, "P3");
        assertFalse(wrongPrincipal.contains(P2_HONEYCARD),
                "a non-owner must not receive the identity: " + wrongPrincipal);

        assertEquals(handSubset, XmageMidgameJsonlBridge.redactMismatch(handSubset, "P2"),
                "the owner's own hand identity is legitimately observable to the owner");

        String injectedMissing = "hand injected object missing: P2 "
                + "native_id=11111111-2222-3333-4444-555555555555";
        String redactedId = XmageMidgameJsonlBridge.redactNativeIds(injectedMissing);
        assertFalse(redactedId.contains("11111111-2222-3333-4444-555555555555"),
                "a hidden card's native id must not survive redaction: " + redactedId);
        assertTrue(redactedId.contains("P2"),
                "the owning seat is public and must survive: " + redactedId);

        String temporal = "priority_player: requested P1 observed P2";
        assertEquals(temporal, XmageMidgameJsonlBridge.redactMismatch(temporal, "P1"),
                "public temporal facts pass through unchanged");
        String life = "life P2: requested 0 observed 40";
        assertEquals(life, XmageMidgameJsonlBridge.redactMismatch(life, null),
                "public life facts pass through unchanged");
        String battlefield = "zone multiset P2|BATTLEFIELD|Grizzly Bears"
                + "|tapped=false|controller=P2: requested 1 observed 0";
        assertEquals(battlefield, XmageMidgameJsonlBridge.redactMismatch(battlefield, null),
                "public-zone facts pass through unchanged");
    }

    /**
     * An unidentified requester must not silently receive the public view when
     * it asked for a principal-scoped one: the request fails closed.
     */
    @Test
    void unknownRequesterFailsClosed() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        lane.ok("create_midgame_game",
                createRequest("privacy-unknown-actor",
                        frozenRecord("MICRO_REPLACEMENT"), null, null));
        lane.ok("start_midgame_game", null);
        JsonObject request = new JsonObject();
        request.addProperty("actor_id", "not-a-principal");
        JsonObject response = lane.rejected("complete_midgame_arrival", request);
        assertTrue(response.getAsJsonArray("errors").get(0).getAsJsonObject()
                        .get("message").getAsString().contains("unknown requester principal"),
                "an unknown requester must fail closed: " + response);
    }
}
