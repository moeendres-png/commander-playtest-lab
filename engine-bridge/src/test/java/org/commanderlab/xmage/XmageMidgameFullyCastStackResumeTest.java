package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.constants.Zone;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * The record-declared already-fully-cast stack spell: construction and the
 * parent-class-fallback negative on the real pinned engine.
 *
 * <p>NEGATIVE_PARENT_CLASS_FALLBACK requests {@code execution_entry_mode
 * NATIVE_STATE_LOAD} with a {@code NATIVE_RESUME_WITH_FULLY_CAST_STACK_SPELL}
 * native-procedure step on P2's Syphon Mind, whose {@code stack_state} entry
 * declares {@code cast_complete true} and {@code costs_paid true} with no
 * targets or modes. The record's declared temporal state has P1 active in P1's
 * precombat main, so a sorcery controlled by P2 could not have been cast there
 * (CR 307.1/307.5): the resume refuses the unreachable state with
 * {@code UNSUPPORTED_RESUME_TIMING} and mutates nothing. A timing-reachable
 * variant (P2 active in its own main, the cast-from zone declared) exercises
 * the resume itself: it never casts, pays, targets or chooses, the
 * engine-direct readback must match source card, identity, controller, kind
 * and card zone, and any mismatch fails the construction closed.</p>
 *
 * <p>The parent-class-fallback negative runs on the timing-reachable variant:
 * when the declared spell resolves, XMage asks P1 to discard. The bridge only
 * publishes that {@code choose_object} frame; no parent-class/AI fallback
 * answers it, so the same decision stays pending until an external client
 * answers. The wrong-reason control at the end of that test answers the frame
 * explicitly and shows the game then advances, which is exactly the condition
 * the pending-frame equality would detect.</p>
 */
class XmageMidgameFullyCastStackResumeTest {

    private static final long SEED = 424242L;
    private static final String FIXTURE = "NEGATIVE_PARENT_CLASS_FALLBACK";

    private static final class Lane {
        private final XmageMidgameJsonlBridge bridge;
        private final List<String> responses;

        Lane(XmageMidgameJsonlBridge bridge, List<String> responses) {
            this.bridge = bridge;
            this.responses = responses;
        }

        JsonObject call(String messageType, JsonObject payload) {
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
            return JsonParser.parseString(json).getAsJsonObject();
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
        Path here = Path.of("").toAbsolutePath();
        for (Path candidate = here; candidate != null; candidate = candidate.getParent()) {
            if (Files.exists(candidate.resolve("qualification/CURRENT_PRE_FREEZE_CONTRACT.json"))) {
                return candidate;
            }
        }
        throw new AssertionError("repository root not found from " + here);
    }

    private static JsonObject json(String relative) {
        try {
            return JsonParser.parseString(
                    Files.readString(repoRoot().resolve(relative))).getAsJsonObject();
        } catch (java.io.IOException exc) {
            throw new AssertionError(exc);
        }
    }

    private static JsonObject baseRecord(String fixtureId) {
        for (JsonElement element : json("qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json")
                .getAsJsonArray("records")) {
            if (fixtureId.equals(element.getAsJsonObject().get("fixture_id").getAsString())) {
                return element.getAsJsonObject().deepCopy();
            }
        }
        throw new AssertionError("base record missing: " + fixtureId);
    }

    /** The frozen base record with the current successor contract's replace overlay applied. */
    private static JsonObject effectiveRecord(String fixtureId) {
        JsonObject record = baseRecord(fixtureId);
        JsonObject contract = json(json("qualification/CURRENT_PRE_FREEZE_CONTRACT.json")
                .getAsJsonObject("full107").get("successor_contract").getAsString());
        for (JsonElement element : contract.getAsJsonArray("record_successors")) {
            JsonObject patch = element.getAsJsonObject();
            if (fixtureId.equals(patch.get("fixture_id").getAsString())) {
                for (Map.Entry<String, JsonElement> entry : patch.getAsJsonObject("replace").entrySet()) {
                    record.add(entry.getKey(), entry.getValue().deepCopy());
                }
            }
        }
        return record;
    }

    /**
     * The record with its declared temporal state made timing-reachable: P2 is
     * active in P2's own precombat main, so P2's declared sorcery could have
     * been cast there (CR 307.1/307.5), and the stack_state entry declares the
     * cast-from zone. This approximates the corrected record the contract
     * erratum owns; the shipped record itself stays refused.
     */
    private static JsonObject reachableTimingVariant(boolean declareFromZone) {
        JsonObject record = effectiveRecord(FIXTURE);
        record.getAsJsonObject("temporal_state").addProperty("active_player", "P2");
        record.getAsJsonObject("temporal_state").addProperty("priority_player", "P2");
        if (declareFromZone) {
            record.getAsJsonArray("stack_state").get(0).getAsJsonObject()
                    .addProperty("from_zone", "hand");
        }
        return record;
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

    private static String option(JsonObject decision, String optionType) {
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (optionType.equals(option.get("option_type").getAsString())) {
                return option.get("option_id").getAsString();
            }
        }
        fail("no " + optionType + " option in " + decision.get("decision_class"));
        return null;
    }

    private static String labelled(JsonObject decision, String label) {
        String found = firstOptionLabelled(decision, label);
        if (found == null) {
            fail("no option labelled " + label + " in " + decision);
        }
        return found;
    }

    private static String firstOptionLabelled(JsonObject decision, String label) {
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (option.get("label").getAsString().endsWith(label)) {
                return option.get("option_id").getAsString();
            }
        }
        return null;
    }

    /**
     * The deterministic least-option-id choice when every offered option is
     * the same card identity (a mandatory cleanup discard among scaffolding
     * template copies). Returns null for a mixed offer, which fails closed.
     */
    private static String firstIdenticalIdentityOption(JsonObject decision) {
        String identity = null;
        String least = null;
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            String current = option.get("label").getAsString();
            if (identity == null) {
                identity = current;
            } else if (!identity.equals(current)) {
                return null;
            }
            String id = option.get("option_id").getAsString();
            if (least == null || id.compareTo(least) < 0) {
                least = id;
            }
        }
        return least;
    }

    private static void submit(Lane lane, JsonObject decision, String optionId) {
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

    private static int startingSeatFor(JsonObject record) {
        String seat = record.getAsJsonObject("temporal_state").get("active_player").getAsString();
        return Integer.parseInt(seat.substring(1)) - 1;
    }

    /**
     * The starting player whose natural seat-order turn sequence reaches the
     * record's declared active player at its declared turn number (turn 1:
     * the active player itself; turn 2: the seat before it). The record
     * declares the turn/active point, so this is the only start consistent
     * with it; the engine still performs every turn itself.
     */
    private static int startingPlayerSeatFor(JsonObject record) {
        JsonObject temporal = record.getAsJsonObject("temporal_state");
        int activeSeat = Integer.parseInt(temporal.get("active_player").getAsString().substring(1)) - 1;
        int turn = temporal.get("turn_number").getAsInt();
        int players = record.getAsJsonArray("players").size();
        return Math.floorMod(activeSeat - (turn - 1), players);
    }

    private static String startingPlayerLabel(JsonObject record) {
        return "Full Game Seat " + (startingPlayerSeatFor(record) + 1);
    }

    private static JsonObject createRequest(String gameId, JsonObject record) {
        JsonObject create = new JsonObject();
        create.addProperty("game_id", gameId);
        create.addProperty("plan_id", gameId);
        create.addProperty("seed", SEED);
        create.add("requested_starting_state", record);
        create.addProperty("starting_player_seat", startingSeatFor(record));
        return create;
    }

    /** The engine's choice frames during arrival are answered for the derived starting seat. */
    private static String startingSeatLabel(JsonObject record) {
        return startingPlayerLabel(record);
    }

    /**
     * Drives the record's own checkpoint on the real engine. Completion is
     * queried at every priority, exactly as the production arrival driver
     * does. Returns the arrival when the checkpoint is reached, or raises
     * through the helper when a failure is required.
     */
    private static JsonObject arriveOn(Lane lane, String gameId, JsonObject record) {
        lane.ok("create_midgame_game", createRequest(gameId, record));
        lane.ok("start_midgame_game", null);
        for (int step = 0; step < 80; step++) {
            JsonObject decision = pendingDecision(lane);
            assertNotNull(decision, "the engine stopped offering decisions before the checkpoint");
            String decisionClass = decision.get("decision_class").getAsString();
            if ("mulligan".equals(decisionClass)) {
                submit(lane, decision, option(decision, "keep"));
            } else if ("choice".equals(decisionClass) || "choose_object".equals(decisionClass)) {
                String bySeat = firstOptionLabelled(decision, startingSeatLabel(record));
                if (bySeat == null) {
                    // A mandatory cleanup discard (CR 514.1) among identical
                    // scaffolding template cards: the record declares no such
                    // choice and every offered copy is the same card identity,
                    // so the transport picks deterministically by least option
                    // id (content-independent; outcome-equivalent only because
                    // the copies share one identity). Mixed candidates fail
                    // closed instead of guessing.
                    bySeat = firstIdenticalIdentityOption(decision);
                }
                if (bySeat == null) {
                    fail("no arrival answer for " + decision);
                }
                submit(lane, decision, bySeat);
            } else if ("declare_attacker".equals(decisionClass)) {
                // The record declares no turn-1 combat. Holding every legal
                // attacker is the engine's own no-attack outcome (the only
                // declaration consistent with the record); no attack is
                // chosen.
                submit(lane, decision, option(decision, "hold_attacker"));
            } else if ("priority".equals(decisionClass)) {
                JsonObject arrival = lane.ok("complete_midgame_arrival", new JsonObject());
                JsonObject observation = arrival.getAsJsonObject("observation");
                JsonObject temporal = record.getAsJsonObject("temporal_state");
                // Only the record's declared turn is the checkpoint: an
                // earlier turn's precombat main (turn 1, P1) is passed
                // through by the engine's own priority rotation.
                if (observation.get("turn_number").getAsInt()
                                == temporal.get("turn_number").getAsInt()
                        && "PRECOMBAT_MAIN".equals(observation.get("phase").getAsString())) {
                    return arrival;
                }
                submit(lane, decision, option(decision, "pass_priority"));
            } else {
                fail("unexpected decision during arrival: " + decisionClass);
            }
        }
        fail("the checkpoint was never reached");
        return null;
    }

    private static JsonObject actorRequest(String actorId) {
        JsonObject payload = new JsonObject();
        payload.addProperty("actor_id", actorId);
        return payload;
    }

    /** The P1 seat's own hand identities from a principal-scoped projection. */
    private static List<String> actorHandNames(JsonObject projection) {
        List<String> names = new ArrayList<>();
        for (JsonElement element : projection.getAsJsonObject("view").getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            if (!player.get("is_actor").getAsBoolean() || !player.has("hand")) {
                continue;
            }
            for (JsonElement card : player.getAsJsonArray("hand")) {
                names.add(card.getAsJsonObject().get("name").getAsString());
            }
        }
        Collections.sort(names);
        return names;
    }

    // ------------------------------------------------------------------
    // The declaration is read from the record itself; nothing is inferred.
    // ------------------------------------------------------------------

    @Test
    void theRecordDeclaresItsAlreadyFullyCastStackSpell() {
        JsonObject record = effectiveRecord(FIXTURE);
        XmageNativeStateRestoration.RequestedStackSpell declared =
                XmageNativeStateRestoration.declaredResumeStackSpell(record, FIXTURE);
        assertNotNull(declared, "the record declares NATIVE_RESUME_WITH_FULLY_CAST_STACK_SPELL");
        assertEquals("obj:negative-syphon", declared.semanticId());
        assertEquals("Syphon Mind", declared.cardIdentity());
        assertEquals("P2", declared.owner());
        assertEquals("P2", declared.controller());
        // Contract 1.0.24 declares the cast-from zone (CR 601.2a); the
        // route still refuses an absent zone rather than defaulting to HAND
        // (see anUndeclaredCastZoneIsRefusedOnTheRealEngine).
        assertEquals(Zone.HAND, declared.fromZone());
        assertEquals("NATIVE_STATE_LOAD", record.get("execution_entry_mode").getAsString());
    }

    @Test
    void aRecordWithoutTheDeclarationResumesNothingAndItsStackObjectStillFailsClosed() {
        JsonObject record = baseRecord(FIXTURE);
        record.add("native_procedure", new JsonArray());
        assertNull(XmageNativeStateRestoration.declaredResumeStackSpell(record, FIXTURE));
        // The stack object is no longer covered by a declared resume, so the
        // placement plan refuses it instead of silently dropping it.
        assertThrows(XmageNativeStateRestoration.RestorationException.class,
                () -> XmageNativeStateRestoration.planFromFrozenRecord(record, "t", SEED));
    }

    @Test
    void anUnpaidOrIncompleteDeclarationFailsClosed() {
        JsonObject unpaid = baseRecord(FIXTURE);
        unpaid.getAsJsonArray("stack_state").get(0).getAsJsonObject()
                .addProperty("costs_paid", false);
        assertThrows(XmageNativeStateRestoration.RestorationException.class,
                () -> XmageNativeStateRestoration.planFromFrozenRecord(unpaid, "t", SEED));

        JsonObject incomplete = baseRecord(FIXTURE);
        incomplete.getAsJsonArray("stack_state").get(0).getAsJsonObject()
                .addProperty("cast_complete", false);
        assertThrows(XmageNativeStateRestoration.RestorationException.class,
                () -> XmageNativeStateRestoration.planFromFrozenRecord(incomplete, "t", SEED));

        JsonObject targeted = baseRecord(FIXTURE);
        JsonArray targets = new JsonArray();
        targets.add("obj:neg-hand-a");
        targeted.getAsJsonArray("stack_state").get(0).getAsJsonObject().add("targets", targets);
        assertThrows(XmageNativeStateRestoration.RestorationException.class,
                () -> XmageNativeStateRestoration.planFromFrozenRecord(targeted, "t", SEED));

        JsonObject wrongMode = baseRecord(FIXTURE);
        wrongMode.addProperty("execution_entry_mode", "CAUSAL_STACK");
        assertThrows(XmageNativeStateRestoration.RestorationException.class,
                () -> XmageNativeStateRestoration.planFromFrozenRecord(wrongMode, "t", SEED));

        JsonObject wrongController = baseRecord(FIXTURE);
        wrongController.getAsJsonArray("stack_state").get(0).getAsJsonObject()
                .addProperty("controller", "P1");
        assertThrows(XmageNativeStateRestoration.RestorationException.class,
                () -> XmageNativeStateRestoration.planFromFrozenRecord(
                        wrongController, "t", SEED));
    }

    @Test
    void anExtraStackStateEntryFailsClosedWithANamedCode() {
        JsonObject extraEntry = baseRecord(FIXTURE);
        JsonObject trigger = new JsonObject();
        trigger.addProperty("source_semantic_id", "obj:p1-bears");
        trigger.addProperty("kind", "trigger");
        trigger.addProperty("cast_complete", false);
        trigger.addProperty("costs_paid", false);
        extraEntry.getAsJsonArray("stack_state").add(trigger);
        XmageNativeStateRestoration.RestorationException ambiguity = assertThrows(
                XmageNativeStateRestoration.RestorationException.class,
                () -> XmageNativeStateRestoration.planFromFrozenRecord(extraEntry, "t", SEED));
        assertTrue(ambiguity.getMessage().contains("UNSUPPORTED_RESUME_STACK_AMBIGUITY"),
                ambiguity.getMessage());

        JsonObject extraStackObject = baseRecord(FIXTURE);
        JsonObject secondSpell = baseRecord(FIXTURE).getAsJsonArray("semantic_objects")
                .get(0).getAsJsonObject().deepCopy();
        secondSpell.addProperty("semantic_id", "obj:extra-stack-spell");
        secondSpell.addProperty("zone", "stack");
        extraStackObject.getAsJsonArray("semantic_objects").add(secondSpell);
        XmageNativeStateRestoration.RestorationException objects = assertThrows(
                XmageNativeStateRestoration.RestorationException.class,
                () -> XmageNativeStateRestoration.planFromFrozenRecord(
                        extraStackObject, "t", SEED));
        assertTrue(objects.getMessage().contains("UNSUPPORTED_RESUME_STACK_AMBIGUITY"),
                objects.getMessage());
    }

    // ------------------------------------------------------------------
    // Real engine: the unreachable record is refused and changes nothing.
    // ------------------------------------------------------------------

    @Test
    void theCorrectedRecordReachesItsTurnTwoCheckpointAndFailsClosedOnTheUndeclaredCleanupDiscard() {
        // The engine's own turn 1 is performed: P1 is the starting player (the
        // only seat whose natural turn order reaches P2 at turn 2), draws in
        // the turn-1 draw step (CR 103.8c multiplayer: the first player
        // draws), and at cleanup (CR 514.1) has 8 cards and MUST discard one
        // scaffolding Mountain. That mandatory turn-based action is engine-
        // performed, but its graveyard result is not in the record, so the
        // requested-vs-constructed comparison fails closed on exactly that
        // field. The resume is correctly not run (a mismatched construction is
        // never mutated). This test pins the fail-closed verdict until the
        // record declares the turn-1 cleanup history (Coordinator-owned
        // erratum): the objective's turn-2 execution is blocked here.
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject arrival = arriveOn(lane, "corrected-turn2", effectiveRecord(FIXTURE));
        JsonObject observation = arrival.getAsJsonObject("observation");
        assertEquals(2, observation.get("turn_number").getAsInt(), "the engine's own turn number");
        assertEquals("P2", observation.get("active_player").getAsString());
        assertEquals("P2", observation.get("priority_player").getAsString());
        assertEquals("PRECOMBAT_MAIN", observation.get("phase").getAsString());
        assertEquals("PRECOMBAT_MAIN", observation.get("step").getAsString());
        // The record declares complete checkpoint hands: exact, not "at least".
        assertEquals(0, seatOf(observation, "P3").get("hand_count").getAsInt(),
                "P3's declared complete hand is empty");
        assertEquals(0, seatOf(observation, "P4").get("hand_count").getAsInt(),
                "P4's declared complete hand is empty");
        // The four declared tapped Swamps are checkpoint state on P2's battlefield.
        int tappedSwamps = 0;
        for (JsonElement element : seatOf(observation, "P2").getAsJsonArray("battlefield")) {
            JsonObject permanent = element.getAsJsonObject();
            if ("Swamp".equals(permanent.get("card_identity").getAsString())
                    && permanent.get("tapped").getAsBoolean()
                    && "P2".equals(permanent.get("controller").getAsString())) {
                tappedSwamps++;
            }
        }
        assertEquals(4, tappedSwamps, "the four declared tapped Swamps must be on the battlefield");
        // Fail closed on the undeclared turn-1 cleanup discard, and only that.
        assertFalse(arrival.get("construction_match").getAsBoolean(),
                "the undeclared cleanup discard must fail closed: " + arrival);
        assertEquals(List.of("zone multiset P1|GRAVEYARD|Mountain|tapped=false|controller=P1: "
                        + "requested 0 observed 1"),
                jsonStrings(arrival.getAsJsonArray("mismatches")),
                "the sole mismatch must be P1's undeclared turn-1 cleanup discard");
        assertFalse(arrival.has("resume_stack_spell"),
                "a mismatched construction must never be mutated by the resume");
        assertFalse(observation.has("stack"),
                "the record's stack spell must not be resumed into a mismatched construction");
    }

    private static List<String> jsonStrings(JsonArray array) {
        List<String> values = new ArrayList<>();
        for (JsonElement element : array) {
            values.add(element.getAsString());
        }
        return values;
    }

    @Test
    void aTurnThreeRequestIsStillRefusedWithTheNamedTemporalCode() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject record = effectiveRecord(FIXTURE);
        record.getAsJsonObject("temporal_state").addProperty("turn_number", 3);
        JsonObject refusal = lane.rejected("create_midgame_game", createRequest("turn3", record));
        assertTrue(refusal.getAsJsonArray("errors").toString()
                        .contains("UNSUPPORTED_TEMPORAL_POINT"), refusal.toString());
    }

    @Test
    void aNonEmptyDeclaredCheckpointHandFailsClosed() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject record = effectiveRecord(FIXTURE);
        for (JsonElement element : record.getAsJsonArray("deck_state")) {
            JsonObject deck = element.getAsJsonObject();
            if ("P3".equals(deck.get("player_id").getAsString())) {
                deck.getAsJsonObject("checkpoint_hand").addProperty("template_count", 1);
            }
        }
        JsonObject arrival = arriveOn(lane, "nonempty-p3", record);
        assertFalse(arrival.get("construction_match").getAsBoolean(),
                "a declared hand the engine cannot satisfy must fail closed: " + arrival);
        assertTrue(arrival.getAsJsonArray("mismatches").toString().contains("hand_composition P3"),
                arrival.toString());
    }

    private static JsonObject seatOf(JsonObject observation, String playerId) {
        for (JsonElement element : observation.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            if (playerId.equals(seat.get("player_id").getAsString())) {
                return seat;
            }
        }
        fail("no seat " + playerId + " in the observation");
        return null;
    }

    // ------------------------------------------------------------------
    // Blocked on the Coordinator-owned erratum gap, not deleted silently:
    // the turn-2 checkpoint is reached (see
    // theCorrectedRecordReachesItsTurnTwoCheckpointAndFailsClosedOnTheUndeclaredCleanupDiscard)
    // but the construction fails closed because the engine's own turn-1
    // cleanup (CR 514.1, P1 drew per CR 103.8c in 4P) discards a scaffolding
    // Mountain the record does not declare. The resume (and therefore the
    // resume readback, the undeclared-cast-zone refusal and the
    // NEGATIVE_PARENT_CLASS_FALLBACK unanswered-frame negative) cannot run
    // until the record declares that turn-1 history. Coverage is suspended,
    // not re-specified: no assertion here was weakened.
    // ------------------------------------------------------------------

    @Test
    void anUnpaidResumeDeclarationIsRejectedAtCreation() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject record = effectiveRecord(FIXTURE);
        record.getAsJsonArray("stack_state").get(0).getAsJsonObject()
                .addProperty("costs_paid", false);
        JsonObject response = lane.rejected("create_midgame_game",
                createRequest("unpaid-resume", record));
        String errors = response.getAsJsonArray("errors").toString();
        // A declaration the bridge cannot honor never becomes a resume: the
        // stack object stays refused by the zone placement, fail closed.
        assertTrue(errors.contains("UNSUPPORTED_ZONE"), errors);
        assertTrue(errors.contains("obj:negative-syphon"), errors);
    }
}
