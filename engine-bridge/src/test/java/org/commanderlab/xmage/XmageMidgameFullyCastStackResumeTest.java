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
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

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
 * declares {@code cast_complete true}, {@code costs_paid true} and the
 * cast-from zone, with no targets or modes. Contract 1.0.25 also declares the
 * record's turn-2 temporal state (P2 active in P2's own precombat main after
 * the engine's own turn 1) and P1's scripted turn-1 cleanup discard (one
 * Mountain, CR 514.1), so the checkpoint is reachable through the engine's
 * own turn structure. The cleanup {@code choose_object} frame is answered
 * from the record's own card-name multiset -- by name, never first or
 * positionally, least option id among same-name copies -- and a red control
 * shows an answer naming a card outside the script is rejected. The resume
 * itself never casts, pays, targets or chooses; the engine-direct readback
 * must match source card, identity, controller, kind and card zone, and any
 * mismatch fails the construction closed. An undeclared cast-from zone is
 * refused with its named code rather than defaulting to HAND.</p>
 *
 * <p>The parent-class-fallback negative runs on the corrected record: when the
 * declared spell resolves, XMage asks P1 to discard. The bridge only publishes
 * that {@code choose_object} frame; no parent-class/AI fallback answers it, so
 * the same decision stays pending until an external client answers. The
 * wrong-reason control at the end of that test answers the frame explicitly
 * and shows the game then advances, which is exactly the condition the
 * pending-frame equality would detect.</p>
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
     * The record's own card-name multiset for its scripted cleanup discard
     * (CR 514.1; contract 1.0.25 declares exactly one Mountain for P1's turn-1
     * cleanup). The frame is answered from this multiset only.
     */
    private static Map<String, Integer> scriptedCleanupDiscard(JsonObject record) {
        for (JsonElement element : record.getAsJsonArray("decision_script")) {
            JsonObject step = element.getAsJsonObject();
            if (!"cleanup_discard".equals(step.get("decision_family").getAsString())) {
                continue;
            }
            JsonObject selection = step.getAsJsonObject("selection");
            if (!"card_identity_multiset".equals(selection.get("selector_kind").getAsString())) {
                fail("the cleanup_discard script is not a card-identity multiset: " + step);
            }
            Map<String, Integer> multiset = new TreeMap<>();
            for (Map.Entry<String, JsonElement> entry
                    : selection.getAsJsonObject("semantic_value").entrySet()) {
                multiset.put(entry.getKey(), entry.getValue().getAsInt());
            }
            return multiset;
        }
        fail("the record declares no cleanup_discard script");
        return null;
    }

    /**
     * The option ids the record's cleanup-discard multiset selects from the
     * engine's own offer: candidates are matched by card name only, never by
     * position, and among same-name copies the least option id is taken (the
     * copies share one identity, so their relative order is not a choice the
     * record could make). The selection is re-validated against the record by
     * {@link #requireScriptedCleanupSelection} before it is returned, and the
     * frame's own selection bounds must authorize the multiset's total.
     */
    private static List<String> scriptedCleanupSelection(JsonObject record, JsonObject decision) {
        Map<String, Integer> multiset = scriptedCleanupDiscard(record);
        List<JsonObject> offers = new ArrayList<>();
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            offers.add(element.getAsJsonObject());
        }
        List<String> selected = new ArrayList<>();
        for (Map.Entry<String, Integer> entry : multiset.entrySet()) {
            List<JsonObject> named = new ArrayList<>();
            for (JsonObject offer : offers) {
                if (entry.getKey().equals(offer.get("label").getAsString())) {
                    named.add(offer);
                }
            }
            if (named.size() < entry.getValue()) {
                fail("the record scripts " + entry.getValue() + " " + entry.getKey()
                        + " but the engine offers " + named.size());
            }
            named.sort(Comparator.comparing(offer -> offer.get("option_id").getAsString()));
            for (JsonObject offer : named.subList(0, entry.getValue())) {
                selected.add(offer.get("option_id").getAsString());
            }
        }
        requireScriptedCleanupSelection(decision, selected, multiset);
        int min = decision.get("minimum_selections").getAsInt();
        int max = decision.get("maximum_selections").getAsInt();
        if (selected.size() < min || selected.size() > max) {
            fail("the record scripts " + selected.size() + " discards, the engine asks "
                    + min + ".." + max);
        }
        return selected;
    }

    /**
     * Rejects a cleanup-discard answer that is not exactly the record's own
     * multiset: every selected option must be offered and carry a scripted
     * card name, and no name may be picked more often than the record scripts
     * it. This is the gate the transport runs before submitting, so a lenient
     * picker (first option, least option id, any positional rule) cannot pass:
     * an answer that picks a card the script never names is rejected.
     */
    private static void requireScriptedCleanupSelection(
            JsonObject decision, List<String> selectedOptionIds, Map<String, Integer> multiset) {
        Map<String, JsonObject> offered = new HashMap<>();
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            offered.put(option.get("option_id").getAsString(), option);
        }
        Map<String, Integer> counted = new TreeMap<>();
        for (String optionId : selectedOptionIds) {
            JsonObject option = offered.get(optionId);
            if (option == null) {
                fail("the cleanup answer names an option the engine never offered: " + optionId);
            }
            String name = option.get("label").getAsString();
            if (!multiset.containsKey(name)) {
                fail("the cleanup answer picks " + name
                        + ", which the record's cleanup_discard script never names");
            }
            counted.merge(name, 1, Integer::sum);
        }
        for (Map.Entry<String, Integer> entry : counted.entrySet()) {
            if (entry.getValue() > multiset.get(entry.getKey())) {
                fail("the cleanup answer picks " + entry.getValue() + " " + entry.getKey()
                        + ", the record scripts " + multiset.get(entry.getKey()));
            }
        }
    }

    /** A crafted option in the engine's own frame shape, for control tests. */
    private static JsonObject offeredOption(String optionId, String label) {
        JsonObject option = new JsonObject();
        option.addProperty("option_id", optionId);
        option.addProperty("label", label);
        return option;
    }

    private static void submit(Lane lane, JsonObject decision, List<String> optionIds) {
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", decision.get("decision_id").getAsString());
        response.addProperty("actor_id", decision.get("actor_id").getAsString());
        JsonArray selected = new JsonArray();
        optionIds.forEach(selected::add);
        response.add("selected_option_ids", selected);
        response.add("ordering", new JsonArray());
        JsonObject request = new JsonObject();
        request.add("response", response);
        lane.ok("submit_midgame_decision", request);
    }

    private static void submit(Lane lane, JsonObject decision, String optionId) {
        submit(lane, decision, List.of(optionId));
    }

    /**
     * The seat the record itself declares as the starting player: the
     * {@code starting_player} decision-script step's seat (CR 103.1). The
     * turn-2 checkpoint's active player is never turned into a starter by
     * seat arithmetic; an absent or ambiguous declaration fails closed.
     */
    private static int startingPlayerSeatFor(JsonObject record) {
        String seat = null;
        for (JsonElement element : record.getAsJsonArray("decision_script")) {
            JsonObject step = element.getAsJsonObject();
            if (!"starting_player".equals(step.get("decision_family").getAsString())) {
                continue;
            }
            JsonObject selection = step.getAsJsonObject("selection");
            if (!"seat".equals(selection.get("selector_kind").getAsString())) {
                fail("the starting_player script is not a seat selector: " + step);
            }
            String declared = selection.get("semantic_value").getAsString();
            if (seat != null && !seat.equals(declared)) {
                fail("the record declares two different starting seats: " + seat
                        + " and " + declared);
            }
            seat = declared;
        }
        if (seat == null) {
            fail("the record declares no starting_player script step");
        }
        return Integer.parseInt(seat.substring(1)) - 1;
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
        create.addProperty("starting_player_seat", startingPlayerSeatFor(record));
        return create;
    }

    /** The engine's choice frames during arrival are answered for the declared starting seat. */
    private static String startingSeatLabel(JsonObject record) {
        return startingPlayerLabel(record);
    }

    /**
     * One arrival frame that is not a {@code priority} frame, answered for the
     * record's own declarations: mulligans keep, a seat choice is answered at
     * the record's declared starting seat, the cleanup discard comes from the
     * record's scripted card-name multiset, and turn-1 combat (which the record
     * declares none of) holds every legal attacker. Anything else fails closed.
     */
    private static void answerArrivalFrame(Lane lane, JsonObject record, JsonObject decision) {
        String decisionClass = decision.get("decision_class").getAsString();
        if ("mulligan".equals(decisionClass)) {
            submit(lane, decision, option(decision, "keep"));
        } else if ("choice".equals(decisionClass) || "choose_object".equals(decisionClass)) {
            String bySeat = firstOptionLabelled(decision, startingSeatLabel(record));
            if (bySeat != null) {
                submit(lane, decision, bySeat);
            } else {
                submit(lane, decision, scriptedCleanupSelection(record, decision));
            }
        } else if ("declare_attacker".equals(decisionClass)) {
            // The record declares no turn-1 combat. Holding every legal
            // attacker is the engine's own no-attack outcome (the only
            // declaration consistent with the record); no attack is chosen.
            submit(lane, decision, option(decision, "hold_attacker"));
        } else {
            fail("unexpected decision during arrival: " + decisionClass);
        }
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
            if ("priority".equals(decisionClass)) {
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
                answerArrivalFrame(lane, record, decision);
            }
        }
        fail("the checkpoint was never reached");
        return null;
    }

    /**
     * Drives the record to its checkpoint and returns the first refused
     * completion (a checkpoint whose construction is refused fails closed at
     * the same place the production driver would refuse it).
     */
    private static JsonObject arriveExpectingRefusal(Lane lane, String gameId, JsonObject record) {
        lane.ok("create_midgame_game", createRequest(gameId, record));
        lane.ok("start_midgame_game", null);
        for (int step = 0; step < 80; step++) {
            JsonObject decision = pendingDecision(lane);
            assertNotNull(decision, "the engine stopped offering decisions before the checkpoint");
            if ("priority".equals(decision.get("decision_class").getAsString())) {
                JsonObject response = lane.call("complete_midgame_arrival", new JsonObject());
                if (!response.get("success").getAsBoolean()) {
                    return response;
                }
                submit(lane, decision, option(decision, "pass_priority"));
            } else {
                answerArrivalFrame(lane, record, decision);
            }
        }
        fail("the checkpoint was never reached");
        return null;
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
    // Real engine: the corrected record reaches its turn-2 checkpoint, the
    // scripted cleanup discard is transported, and the resume runs.
    // ------------------------------------------------------------------

    @Test
    void aReachableVariantResumesAndReadsBackOnTheRealEngine() {
        // The engine's own turn 1 is performed: P1 is the record's declared
        // starting player, draws in the turn-1 draw step (CR 103.8c
        // multiplayer: the first player draws), and at cleanup (CR 514.1) has
        // 8 cards and discards the one Mountain the record scripts. That
        // discard is answered from the record's own card-name multiset, never
        // picked by the transport.
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject arrival = arriveOn(lane, "reachable-resume", effectiveRecord(FIXTURE));
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
        // The scripted cleanup discard makes the construction exact: the
        // record's graveyard Mountain is present and nothing mismatches.
        assertTrue(arrival.get("construction_match").getAsBoolean(),
                "the checkpoint must construct exactly: " + arrival.get("mismatches"));
        assertEquals(0, arrival.getAsJsonArray("mismatches").size(),
                "the scripted cleanup discard leaves no mismatch: " + arrival);
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
        JsonArray stack = observation.getAsJsonArray("stack");
        assertNotNull(stack, "the observation must carry the public stack");
        assertEquals(1, stack.size());
        assertEquals("Syphon Mind",
                stack.get(0).getAsJsonObject().get("card_identity").getAsString());
    }

    // ------------------------------------------------------------------
    // Real engine: an undeclared cast-from zone is refused, and the route
    // declares no default (a missing zone is never HAND).
    // ------------------------------------------------------------------

    @Test
    void anUndeclaredCastZoneIsRefusedOnTheRealEngine() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject record = effectiveRecord(FIXTURE);
        record.getAsJsonArray("stack_state").get(0).getAsJsonObject().remove("from_zone");
        JsonObject refusal = arriveExpectingRefusal(lane, "undeclared-zone", record);
        assertTrue(refusal.getAsJsonArray("errors").toString()
                        .contains("UNDECLARED_RESUME_CAST_ZONE"), refusal.toString());
    }

    // ------------------------------------------------------------------
    // Real engine: the parent-class-fallback negative. The bridge publishes
    // the resolving spell's discard frame and no handler answers it.
    // ------------------------------------------------------------------

    @Test
    void theParentClassFallbackNegativeIsTheEngineOwnUnansweredFrame() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject arrival = arriveOn(lane, "parent-fallback", effectiveRecord(FIXTURE));
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
        // parent-class fallback would have applied) does move the game on --
        // the pending frame changes -- so the equality assertion above cannot
        // hold for the wrong reason. The control names the card explicitly and
        // among same-name copies takes the least option id, never a position.
        submit(lane, discard, leastOptionIdLabelled(discard, "Mountain"));
        JsonObject afterAnswer = pendingDecision(lane);
        assertNotNull(afterAnswer, "the game must continue after a real answer");
        assertNotEquals(discardId, afterAnswer.get("decision_id").getAsString(),
                "an answered frame must not still be the pending frame");
    }

    /** The least option id among the options that carry the given card name. */
    private static String leastOptionIdLabelled(JsonObject decision, String label) {
        String least = null;
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (label.equals(option.get("label").getAsString())) {
                String id = option.get("option_id").getAsString();
                if (least == null || id.compareTo(least) < 0) {
                    least = id;
                }
            }
        }
        if (least == null) {
            fail("no option labelled " + label + " in " + decision);
        }
        return least;
    }

    // ------------------------------------------------------------------
    // Red control: a cleanup answer that picks a card the record's script
    // never names is rejected by the transport gate, even when it is the
    // least/positionally-first offered option.
    // ------------------------------------------------------------------

    @Test
    void aCleanupAnswerPickingACardOutsideTheScriptIsRejected() {
        JsonObject record = effectiveRecord(FIXTURE);
        Map<String, Integer> multiset = scriptedCleanupDiscard(record);
        assertEquals(Map.of("Mountain", 1), multiset);

        // The engine's frame offers the record's Mountain plus an Island the
        // record never scripts; the Island's option id sorts first.
        JsonObject frame = new JsonObject();
        frame.addProperty("decision_id", "cleanup-red-control");
        frame.addProperty("actor_id", "P1");
        frame.addProperty("decision_class", "choose_object");
        frame.addProperty("minimum_selections", 1);
        frame.addProperty("maximum_selections", 1);
        JsonArray options = new JsonArray();
        options.add(offeredOption("a-island", "Island"));
        options.add(offeredOption("z-mountain", "Mountain"));
        frame.add("legal_options", options);

        // The transport picks by card name, never by position: the Island is
        // not chosen even though its option id is the least offered one.
        assertEquals(List.of("z-mountain"), scriptedCleanupSelection(record, frame));
        // A lenient answer that picks that least/first option anyway is
        // rejected by the same gate every submitted answer passes.
        AssertionError rejection = assertThrows(AssertionError.class,
                () -> requireScriptedCleanupSelection(frame, List.of("a-island"), multiset));
        assertTrue(rejection.getMessage().contains("never names"), rejection.getMessage());

        // Among same-name copies the deterministic least option id is chosen,
        // independent of the engine's offer order.
        JsonObject tied = new JsonObject();
        tied.add("legal_options", new JsonArray());
        tied.getAsJsonArray("legal_options").add(offeredOption("z-mountain", "Mountain"));
        tied.getAsJsonArray("legal_options").add(offeredOption("a-mountain", "Mountain"));
        tied.addProperty("minimum_selections", 1);
        tied.addProperty("maximum_selections", 1);
        assertEquals(List.of("a-mountain"), scriptedCleanupSelection(record, tied));
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
    // The resume declaration is refused at creation when the record cannot
    // honor it (an unpaid declaration never becomes a resume).
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
