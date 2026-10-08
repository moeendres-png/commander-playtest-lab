package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
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
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (option.get("label").getAsString().endsWith(label)) {
                return option.get("option_id").getAsString();
            }
        }
        fail("no option labelled " + label);
        return null;
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

    private static JsonObject createRequest(String gameId, JsonObject record) {
        JsonObject create = new JsonObject();
        create.addProperty("game_id", gameId);
        create.addProperty("plan_id", gameId);
        create.addProperty("seed", SEED);
        create.add("requested_starting_state", record);
        create.addProperty("starting_player_seat", startingSeatFor(record));
        return create;
    }

    /** The engine's choice frames during arrival are answered for the declared starting seat. */
    private static String startingSeatLabel(JsonObject record) {
        String seat = record.getAsJsonObject("temporal_state").get("active_player").getAsString();
        return "Full Game Seat " + seat.substring(1);
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
                submit(lane, decision, labelled(decision, startingSeatLabel(record)));
            } else if ("priority".equals(decisionClass)) {
                JsonObject arrival = lane.ok("complete_midgame_arrival", new JsonObject());
                if ("PRECOMBAT_MAIN".equals(
                        arrival.getAsJsonObject("observation").get("phase").getAsString())) {
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
        // The shipped record declares no cast-from zone; the resume refuses
        // it (UNDECLARED_RESUME_CAST_ZONE) rather than defaulting to HAND.
        assertNull(declared.fromZone());
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
    void theUnreachableTimingResumeIsRefusedAndNothingIsMutated() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject create = createRequest(FIXTURE, effectiveRecord(FIXTURE));
        lane.ok("create_midgame_game", create);
        lane.ok("start_midgame_game", null);

        List<String> handBeforeRefusal = new ArrayList<>();
        int offsetBeforeRefusal = -1;
        String decisionBeforeRefusal = null;
        JsonObject refusal = null;
        for (int step = 0; step < 80; step++) {
            JsonObject decision = pendingDecision(lane);
            assertNotNull(decision, "the engine stopped offering decisions before the checkpoint");
            String decisionClass = decision.get("decision_class").getAsString();
            if ("mulligan".equals(decisionClass)) {
                submit(lane, decision, option(decision, "keep"));
                continue;
            }
            if (!"priority".equals(decisionClass)) {
                submit(lane, decision, labelled(decision, startingSeatLabel(effectiveRecord(FIXTURE))));
                continue;
            }
            // Baselines immediately before the completion attempt: P1's own
            // hand, the public tape offset and the pending priority frame.
            handBeforeRefusal.clear();
            handBeforeRefusal.addAll(
                    actorHandNames(lane.ok("get_midgame_projection", actorRequest("P1"))));
            offsetBeforeRefusal = lane.ok("get_midgame_events", new JsonObject())
                    .get("latest_offset").getAsInt();
            decisionBeforeRefusal = decision.get("decision_id").getAsString();
            JsonObject response = lane.call("complete_midgame_arrival", new JsonObject());
            if (!response.get("success").getAsBoolean()) {
                refusal = response;
                break;
            }
            submit(lane, decision, option(decision, "pass_priority"));
        }
        assertNotNull(refusal, "the unreachable resume must be refused at the checkpoint");
        String errors = refusal.getAsJsonArray("errors").toString();
        assertTrue(errors.contains("UNSUPPORTED_RESUME_TIMING"), errors);

        // Nothing was cast, resolved or chosen: the tape did not move, P1's
        // hand is untouched, and the engine still stands on the same frame.
        JsonObject events = lane.ok("get_midgame_events", actorRequest("P1"));
        assertEquals(offsetBeforeRefusal, events.get("latest_offset").getAsInt(),
                "the refused resume must not emit any event");
        JsonObject afterEvents = new JsonObject();
        afterEvents.addProperty("after_offset", offsetBeforeRefusal);
        assertEquals(0, lane.ok("get_midgame_events", afterEvents)
                .getAsJsonArray("events").size(), "no event may follow the refusal");
        assertEquals(handBeforeRefusal,
                actorHandNames(lane.ok("get_midgame_projection", actorRequest("P1"))),
                "P1's hand must be unchanged by the refused resume");
        JsonObject pending = pendingDecision(lane);
        assertNotNull(pending, "the engine must stay parked after the refusal");
        assertEquals(decisionBeforeRefusal, pending.get("decision_id").getAsString(),
                "the refused resume must not advance the engine");

        // A second completion attempt refuses identically: no partial resume.
        JsonObject again = lane.call("complete_midgame_arrival", new JsonObject());
        assertTrue(again.getAsJsonArray("errors").toString().contains("UNSUPPORTED_RESUME_TIMING"),
                again.toString());
        assertEquals(offsetBeforeRefusal, lane.ok("get_midgame_events", new JsonObject())
                .get("latest_offset").getAsInt());
    }

    @Test
    void anUndeclaredCastZoneIsRefusedOnTheRealEngine() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject record = reachableTimingVariant(false);
        JsonObject create = createRequest(FIXTURE, record);
        lane.ok("create_midgame_game", create);
        lane.ok("start_midgame_game", null);
        JsonObject refusal = null;
        for (int step = 0; step < 80; step++) {
            JsonObject decision = pendingDecision(lane);
            assertNotNull(decision, "the engine stopped offering decisions before the checkpoint");
            String decisionClass = decision.get("decision_class").getAsString();
            if ("mulligan".equals(decisionClass)) {
                submit(lane, decision, option(decision, "keep"));
                continue;
            }
            if (!"priority".equals(decisionClass)) {
                submit(lane, decision, labelled(decision, startingSeatLabel(record)));
                continue;
            }
            JsonObject response = lane.call("complete_midgame_arrival", new JsonObject());
            if (!response.get("success").getAsBoolean()) {
                refusal = response;
                break;
            }
            submit(lane, decision, option(decision, "pass_priority"));
        }
        assertNotNull(refusal, "the undeclared cast-from zone must be refused at the checkpoint");
        assertTrue(refusal.getAsJsonArray("errors").toString()
                        .contains("UNDECLARED_RESUME_CAST_ZONE"), refusal.toString());
    }

    // ------------------------------------------------------------------
    // Real engine: resume + engine-direct readback on a reachable variant.
    // ------------------------------------------------------------------

    @Test
    void aReachableVariantResumesAndReadsBackOnTheRealEngine() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject arrival = arriveOn(lane, "reachable-resume", reachableTimingVariant(true));
        assertTrue(arrival.get("construction_match").getAsBoolean(),
                "the checkpoint must construct exactly: " + arrival.get("mismatches"));
        JsonObject resume = arrival.getAsJsonObject("resume_stack_spell");
        assertNotNull(resume, "the arrival must report the resumed declared stack spell");
        assertTrue(resume.get("verified").getAsBoolean(), resume.toString());
        assertEquals(1, resume.get("stack_size").getAsInt());
        JsonObject observed = resume.getAsJsonArray("observed").get(0).getAsJsonObject();
        assertEquals("Syphon Mind", observed.get("card_identity").getAsString());
        assertEquals("P2", observed.get("controller").getAsString());
        assertTrue(observed.get("source_bound").getAsBoolean(),
                "the stack object must be the record's own materialized source card");
        assertTrue(observed.get("is_spell").getAsBoolean(),
                "the resumed stack object must be a real Spell");
        assertTrue(observed.get("bound_card").getAsBoolean(),
                "the Spell must be the bound engine card");
        assertEquals("STACK", observed.get("card_zone").getAsString(),
                "the bound card's engine zone must be STACK");
        assertEquals("HAND", observed.get("from_zone").getAsString(),
                "the declared cast-from zone must be the Spell's from-zone");
        // The resumed spell is part of the constructed-state observation (and
        // therefore of the digest), not only of its own readback.
        JsonArray stack = arrival.getAsJsonObject("observation").getAsJsonArray("stack");
        assertNotNull(stack, "the observation must carry the public stack");
        assertEquals(1, stack.size());
        assertEquals("Syphon Mind",
                stack.get(0).getAsJsonObject().get("card_identity").getAsString());
    }

    @Test
    void theParentClassFallbackNegativeIsTheEngineOwnUnansweredFrame() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject arrival = arriveOn(lane, "parent-fallback", reachableTimingVariant(true));
        assertTrue(arrival.getAsJsonObject("resume_stack_spell").get("verified").getAsBoolean());

        // Pass the checkpoint priority; the declared spell then resolves and
        // XMage asks P1 to discard. The bridge publishes the frame and answers
        // nothing: no parent-class fallback chooses a card. Every priority
        // frame before the resolution is passed explicitly, never skipped.
        JsonObject checkpoint = pendingDecision(lane);
        assertEquals("priority", checkpoint.get("decision_class").getAsString());
        submit(lane, checkpoint, option(checkpoint, "pass_priority"));

        JsonObject discard = null;
        for (int passes = 0; passes < 12; passes++) {
            JsonObject next = pendingDecision(lane);
            assertNotNull(next, "the resolving spell must ask its discard decision");
            if ("choose_object".equals(next.get("decision_class").getAsString())) {
                discard = next;
                break;
            }
            assertEquals("priority", next.get("decision_class").getAsString(),
                    "only priority passes may precede the resolution: " + next);
            submit(lane, next, option(next, "pass_priority"));
        }
        assertNotNull(discard, "the resolving spell must ask its discard decision");
        assertEquals("choose_object", discard.get("decision_class").getAsString());
        String discardId = discard.get("decision_id").getAsString();

        // No handler answers it: the same decision is still the pending one.
        // A fallback that had let the engine's own/AI choice answer it would
        // have advanced the game and this read would return another frame.
        JsonObject again = pendingDecision(lane);
        assertNotNull(again, "the frame must stay pending until an external client answers");
        assertEquals(discardId, again.get("decision_id").getAsString(),
                "the parent-class fallback must not have answered the discard frame");

        // Wrong-reason control: an answer to this frame (exactly what a
        // parent-class fallback would have applied) does move the game on —
        // the pending frame changes — so the equality assertion above cannot
        // hold for the wrong reason.
        submit(lane, discard, labelled(discard, "Mountain"));
        JsonObject afterAnswer = pendingDecision(lane);
        assertNotNull(afterAnswer, "the game must continue after a real answer");
        assertNotEquals(discardId, afterAnswer.get("decision_id").getAsString(),
                "an answered frame must not still be the pending frame");
    }

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
