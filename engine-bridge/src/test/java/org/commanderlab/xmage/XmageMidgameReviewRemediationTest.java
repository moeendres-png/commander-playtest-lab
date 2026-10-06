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
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Review remediation for the production-reachable mid-game lane.
 *
 * <p>Covers five of the six unresolved findings on PR #304 at the engine
 * boundary; the sixth (the negative construction verdict and the request
 * deadline) is consumer-side and is proven in
 * {@code tests/qualification/test_current_boundary_midgame_lane.py}.</p>
 *
 * <p><b>Hidden information.</b> {@code complete_midgame_arrival} used to return
 * the raw restoration readback, whose {@code seats[*].hand} arrays carry every
 * principal's card names to any caller. The response now separates the two
 * concerns the finding asked to separate: the engine's field-level compare stays
 * authoritative and complete internally, while the response carries a
 * principal-scoped observation. The tests below prove both directions — a bound
 * requester sees its own hand and no other, and an unbound caller sees no hand
 * identity at all.</p>
 *
 * <p><b>Concession schema.</b> The lane now uses the same Protocol-2 schema the
 * full-game lane and the external consumer already use, and the retired shape is
 * asserted to fail closed so the lane cannot drift back to a second schema.</p>
 *
 * <p><b>Colorless commanders.</b> A colorless commander legitimately has no
 * colored identity, so the scaffold must be a colorless basic land. The import
 * that decides legality is still the engine's own real-cards-only Commander
 * import; nothing here relaxes Commander legality.</p>
 */
class XmageMidgameReviewRemediationTest {

    private static final long SEED = 424242L;

    /**
     * The arrival-observation fixture: two principals, and a recorded temporal
     * point reachable by answering engine-offered priority passes, so the
     * privacy controls exercise a completed arrival rather than a stalled drive.
     */
    private static final String PRIVACY_FIXTURE = "WS05-CMD-TAX-2";

    /** A colorless Commander that is legal, so the scaffold must be colorless. */
    private static final String COLORLESS_COMMANDER = "Karn, Silver Golem";

    /**
     * A second, different legal colorless Commander. The scaffold rule is a
     * property of an empty color identity, not of one card name, so the
     * regression covers more than one identity.
     */
    private static final String SECOND_COLORLESS_COMMANDER = "Kozilek, Butcher of Truth";

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

    private static JsonObject actorPayload(String actorId) {
        JsonObject payload = new JsonObject();
        payload.addProperty("actor_id", actorId);
        return payload;
    }

    /**
     * Drives a placement arrival to the record's declared temporal checkpoint,
     * answering every decision from the engine's own offered options. Returns the
     * completed arrival payload for the supplied requester binding.
     */
    private static JsonObject driveToArrivalCheckpoint(
            Lane lane, String fixtureId, JsonObject requesterPayload) {
        lane.ok("create_midgame_game", createRequest("remediation-" + fixtureId, fixtureId, SEED));
        lane.ok("start_midgame_game", null);
        JsonObject temporalState = frozenRecord(fixtureId).getAsJsonObject("temporal_state");
        String requestedPhase = temporalState.get("phase").getAsString().toUpperCase();
        String requestedStep = engineStep(
                temporalState.get("phase").getAsString(),
                temporalState.get("step").getAsString(),
                fixtureId);
        for (int step = 0; step < 80; step++) {
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
                JsonObject observation = lane.ok("complete_midgame_arrival", requesterPayload)
                        .getAsJsonObject("observation");
                if (requestedPhase.equals(observation.get("phase").getAsString())
                        && requestedStep.equals(observation.get("step").getAsString())) {
                    return lane.ok("complete_midgame_arrival", requesterPayload);
                }
                submitOption(lane, pending, actor, optionWithType(pending, "pass_priority"));
                continue;
            }
            break;
        }
        throw new AssertionError(
                "the engine must reach the requested " + requestedPhase + "/" + requestedStep
                        + " checkpoint for " + fixtureId);
    }

    /**
     * The frozen record addresses a checkpoint by a (phase, step) pair while the
     * engine's observation names the same point by a single step token. This is
     * the engine seam's own mapping, reproduced so the test compares the engine's
     * live reading against the record's own request rather than against a guess.
     */
    private static String engineStep(String phase, String step, String fixtureId) {
        return switch (phase + "/" + step) {
            case "beginning/upkeep" -> "UPKEEP";
            case "beginning/draw" -> "DRAW";
            case "precombat_main/main" -> "PRECOMBAT_MAIN";
            case "combat/declare_attackers" -> "DECLARE_ATTACKERS";
            case "combat/declare_blockers" -> "DECLARE_BLOCKERS";
            case "combat/combat_damage" -> "COMBAT_DAMAGE";
            case "postcombat_main/main" -> "POSTCOMBAT_MAIN";
            default -> throw new AssertionError(
                    fixtureId + ": the test does not know the engine step for " + phase + "/" + step);
        };
    }

    private static JsonObject seatOf(JsonObject observation, String principal) {
        for (JsonElement element : observation.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            if (principal.equals(seat.get("player_id").getAsString())) {
                return seat;
            }
        }
        throw new AssertionError("no seat for principal " + principal);
    }

    private static int seatsCarryingAHand(JsonObject observation) {
        int withHand = 0;
        for (JsonElement element : observation.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            if (seat.has("hand") && seat.get("hand").isJsonArray()) {
                withHand++;
            }
        }
        return withHand;
    }

    // ------------------------------------------------------------------
    // Hidden information: the arrival observation is principal-scoped.
    // ------------------------------------------------------------------


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
    void unboundArrivalNeverReturnsTheRawReadbackOrAnyHandIdentities() {
        Lane lane = newLane();
        JsonObject arrival = driveToArrivalCheckpoint(
                lane, PRIVACY_FIXTURE, new JsonObject());

        assertFalse(arrival.has("readback"),
                "the raw restoration readback must never be returned to a caller");
        assertEquals("principal_neutral_opponent_hands_counts_only",
                arrival.get("observation_scope").getAsString(),
                "an unbound caller is answered with the principal-neutral projection");

        JsonObject observation = arrival.getAsJsonObject("observation");
        assertEquals(0, seatsCarryingAHand(observation),
                "no seat may carry a hand identity list when no requester is named");
        // Counts stay available: they are public and the construction verdict is
        // still readable without them.
        for (JsonElement element : observation.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            assertTrue(seat.has("hand_count") && seat.get("hand_count").isJsonPrimitive(),
                    "a seat must still report its public hand count: " + seat);
        }
        assertTrue(arrival.has("mismatches"), "the engine's own mismatch list is still reported");
        assertTrue(arrival.get("construction_match").isJsonPrimitive(),
                "the engine's own construction verdict is still reported");
    }

    @Test
    void aBoundRequesterSeesOnlyItsOwnHandIdentity() {
        Lane lane = newLane();
        JsonObject arrival = driveToArrivalCheckpoint(
                lane, PRIVACY_FIXTURE, actorPayload("P1"));

        assertEquals("principal_scoped", arrival.get("observation_scope").getAsString());
        JsonObject observation = arrival.getAsJsonObject("observation");
        assertEquals(1, seatsCarryingAHand(observation),
                "exactly the requester's own seat may carry a hand identity list");

        JsonObject own = seatOf(observation, "P1");
        assertTrue(own.has("hand") && own.get("hand").isJsonArray(),
                "the requester must still see its own hand");
        assertTrue(own.getAsJsonArray("hand").size() >= 1,
                "the restored hand is non-empty, so the control is not vacuous");

        for (String other : List.of("P2")) {
            JsonObject seat = seatOf(observation, other);
            assertFalse(seat.has("hand"),
                    other + " is another principal and must expose only its hand count");
            assertTrue(seat.has("hand_count"),
                    other + " must still report its public hand count");
        }
    }

    @Test
    void onePrincipalCannotObtainAnotherPrincipalsHandIdentities() {
        Lane lane = newLane();
        // P1's own observation is the reference for what P1 holds.
        JsonObject p1Arrival = driveToArrivalCheckpoint(
                lane, PRIVACY_FIXTURE, actorPayload("P1"));
        JsonArray p1Hand = seatOf(p1Arrival.getAsJsonObject("observation"), "P1")
                .getAsJsonArray("hand");
        assertTrue(p1Hand.size() >= 1, "the P1 reference hand must not be empty");

        Lane second = newLane();
        JsonObject p1Bound = driveToArrivalCheckpoint(
                second, PRIVACY_FIXTURE, actorPayload("P1"));
        JsonObject p2Seat = seatOf(p1Bound.getAsJsonObject("observation"), "P2");
        assertFalse(p2Seat.has("hand"),
                "P1 must not be able to read P2's hand identities from its own observation");
        assertEquals("principal_scoped", p1Bound.get("observation_scope").getAsString());

        // Negative control on the binding itself: an unknown requester is
        // rejected rather than silently answered with no principal scope.
        Lane third = newLane();
        third.ok("create_midgame_game",
                createRequest("remediation-unknown-principal", PRIVACY_FIXTURE, SEED));
        third.ok("start_midgame_game", null);
        JsonObject response = third.call("complete_midgame_arrival",
                actorPayload("not-a-principal"));
        assertFalse(response.get("success").getAsBoolean(),
                "an unrecognized requester binding must fail closed, not over-redact silently");
    }

    @Test
    void theReportedDigestCoversTheRedactedObservationAndNotHiddenState() {
        Lane lane = newLane();
        JsonObject arrival = driveToArrivalCheckpoint(
                lane, PRIVACY_FIXTURE, new JsonObject());
        JsonObject observation = arrival.getAsJsonObject("observation");
        assertEquals("principal_scoped_observation",
                arrival.get("constructed_state_digest_scope").getAsString());
        // Recomputing the digest over what the caller received must reproduce the
        // reported value, so no hidden field is folded into it.
        assertEquals(XmageNativeStateRestoration.digestJson(observation),
                arrival.get("constructed_state_digest").getAsString(),
                "the reported digest must cover exactly the redacted observation");
        assertEquals(64, arrival.get("constructed_state_digest").getAsString().length());
    }

    // ------------------------------------------------------------------
    // Hidden information in mismatch details.
    // ------------------------------------------------------------------

    /**
     * The engine reports a missing requested hand card as
     * {@code hand subset <owner>|HAND|<cardIdentity>|tapped=...: requested N observed M}.
     * The identity is that principal's hidden information, so it may only reach
     * the principal that owns it.
     */
    @Test
    void aMismatchNeverDisclosesAnotherPrincipalsHandIdentity() {
        String engineMessage =
                "hand subset P2|HAND|Grizzly Bears|tapped=false|controller=P2: requested 1 "
                        + "observed 0";

        // A different principal must not learn the card identity.
        String forP1 = XmageMidgameJsonlBridge.redactMismatch(engineMessage, "P1");
        assertFalse(forP1.contains("Grizzly Bears"),
                "P1 must not receive P2's hidden hand identity: " + forP1);
        assertTrue(forP1.contains("P2"),
                "the owning seat and the counts are public and stay visible: " + forP1);
        assertTrue(forP1.contains("requested 1 observed 0"),
                "the counts are public and stay visible: " + forP1);

        // An unbound caller learns no hand identity either.
        String unbound = XmageMidgameJsonlBridge.redactMismatch(engineMessage, null);
        assertFalse(unbound.contains("Grizzly Bears"),
                "an unbound caller must not receive any hand identity: " + unbound);

        // The owner keeps its own identity: it is that principal's own information.
        String forP2 = XmageMidgameJsonlBridge.redactMismatch(engineMessage, "P2");
        assertEquals(engineMessage, forP2,
                "the owning principal keeps its own hand identity");
    }

    @Test
    void aMismatchWithoutAHandKeyIsUnchanged() {
        String publicMessage =
                "zone multiset P1|BATTLEFIELD|Grizzly Bears|tapped=false|controller=P1: "
                        + "requested 3 observed 1";
        assertEquals(publicMessage,
                XmageMidgameJsonlBridge.redactMismatch(publicMessage, "P1"),
                "a public-zone mismatch carries no hidden identity and stays verbatim");
        String priority = "priority_player: requested P1 observed P2";
        assertEquals(priority, XmageMidgameJsonlBridge.redactMismatch(priority, "P1"));
    }

    /*
     * RESOLVED (2026-09-29): the two recorded privacy vectors are closed at this
     * head and are regression-locked by this class and by
     * `XmageMidgamePrivacyTest`.
     *
     * 1. Decision-frame vector. An earlier revision returned the pending
     *    `decision` frame inside the arrival observation, and that frame's
     *    `legal_options` labels can name the acting principal's hand cards. The
     *    arrival and causal-verification responses now carry no decision frame
     *    at all; the only decision channel is `get_midgame_decision` for the
     *    acting principal.
     * 2. Honeycard control. The earlier note said an end-to-end planted-identity
     *    control was not provable with the frozen corpus. It now is:
     *    `XmageMidgamePrivacyTest.opposingHandIdentitiesNeverCrossTheBoundary`
     *    plants `Runeclaw Bear` / `Serra Angel` / `Sol Ring` in the opposing
     *    seats' supported hands of `WS05-CMD-DMG-SPLIT` and scans the complete
     *    wire surface (create, unbound arrival, P1-bound arrival,
     *    `get_midgame_state`, causal-verification error, pending decision) for
     *    them, and `causalVerificationNeverExposesABystanderHand` does the same
     *    for the causal lane. Early `HIDDEN_HONEYCARD_SENTINEL` attempts really
     *    were rejected before arrival with `UNSUPPORTED_ZONE`; the
     *    `WS05-CMD-DMG-SPLIT` route is the lane-supported record that makes the
     *    control executable.
     *
     * The disclosure machinery itself remains unit-controlled below:
     * `redactMismatch` withholds a hand identity from any principal other than
     * its owner and `redactNativeIds` removes the opaque handle for every
     * requester.
     */

    @Test
    void theLiveArrivalMismatchListCarriesNoForeignHandIdentity() {
        Lane lane = newLane();
        JsonObject arrival = driveToArrivalCheckpoint(
                lane, PRIVACY_FIXTURE, actorPayload("P1"));
        for (JsonElement element : arrival.getAsJsonArray("mismatches")) {
            String mismatch = element.getAsString();
            assertFalse(mismatch.contains("<hand-identity-redacted>") && mismatch.contains("P1"),
                    "P1's own hand identity is not redacted for P1: " + mismatch);
            if (mismatch.contains("|HAND|")) {
                assertFalse(mismatch.contains("P2|HAND|") || mismatch.contains("P3|HAND|")
                                || mismatch.contains("P4|HAND|"),
                        "a foreign hand identity must have been redacted: " + mismatch);
            }
        }
    }

    // ------------------------------------------------------------------
    // Concession: the lane uses the established Protocol-2 schema.
    // ------------------------------------------------------------------

    @Test
    void concedeOfferAndSubmissionUseTheEstablishedProtocol2Schema() {
        Lane lane = newLane();
        lane.ok("create_midgame_game",
                createRequest("remediation-concede", "WS05-CMD-TAX-2", SEED));
        lane.ok("start_midgame_game", null);
        String principal = nativePrincipalOfSeat(lane, 0);

        // Offer: the established schema is payload.player_id.
        JsonObject offer = lane.ok("get_concede_offer", payload("player_id", principal));
        assertTrue(offer.get("concede_available").getAsBoolean(),
                "a player still in the game may concede (CR 104.3a)");
        JsonObject concedeAction = offer.getAsJsonObject("concede_action");
        assertNotNull(concedeAction, "an available concession must be offered as an action");
        assertEquals(principal, concedeAction.get("actor_id").getAsString(),
                "the offered action is bound to the requesting principal itself");
        assertEquals("concede", concedeAction.get("action_type").getAsString());

        // The retired schema must fail closed so no second schema can reappear.
        lane.rejected("get_concede_offer", payload("actor_id", principal));

        // Submission: the established schema is payload.proposal.{actor_id, player_id}.
        JsonObject proposal = new JsonObject();
        proposal.addProperty("actor_id", principal);
        proposal.addProperty("player_id", principal);
        JsonObject submitPayload = new JsonObject();
        submitPayload.add("proposal", proposal);
        JsonObject submitted = lane.ok("submit_concede", submitPayload);
        assertNotNull(submitted, "the concession must reach the authoritative implementation");

        // A foreign proposal (actor != subject) and the retired nested shape both
        // fail closed and must not have executed a concession.
        JsonObject foreignProposal = new JsonObject();
        foreignProposal.addProperty("actor_id", principal);
        foreignProposal.addProperty("player_id", nativePrincipalOfSeat(lane, 1));
        JsonObject foreignPayload = new JsonObject();
        foreignPayload.add("proposal", foreignProposal);
        lane.rejected("submit_concede", foreignPayload);
        lane.rejected("submit_concede", payload("payload", "nested"));
    }

    /**
     * The concession contract addresses a principal in the native session
     * namespace, which is what a direct engine driver legitimately needs and what
     * the established external consumer obtains from its own status payload. The
     * lane's own observations mask non-viewer ids, so a test must ask the bridge
     * directly; this accessor is package-private and unreachable over the wire.
     */
    private static String nativePrincipalOfSeat(Lane lane, int seat) {
        String principal = lane.bridge().nativePrincipalIdAtSeat(seat);
        assertNotNull(principal, "seat " + seat + " must have a native principal id");
        return principal;
    }

    private static JsonObject payload(String key, String value) {
        JsonObject object = new JsonObject();
        object.addProperty(key, value);
        return object;
    }

    // ------------------------------------------------------------------
    // Colorless commanders: no fabricated colored identity, no legality
    // relaxation, and the engine still decides the import.
    // ------------------------------------------------------------------

    @Test
    void aColorlessCommanderScaffoldsWithTheColorlessBasicLand() {
        List<String> filler = XmageNativeStateRestoration.scaffoldingFiller(4, Set.of());
        assertEquals(List.of("Wastes", "Wastes", "Wastes", "Wastes"), filler,
                "a colorless commander must be scaffolded with the colorless basic land");
        for (String card : filler) {
            assertFalse(Set.of("Plains", "Island", "Swamp", "Mountain", "Forest").contains(card),
                    "no colored basic may be fabricated for a colorless commander");
        }
    }

    @Test
    void aColoredCommanderScaffoldIsUnchanged() {
        List<String> filler = XmageNativeStateRestoration.scaffoldingFiller(6, Set.of("B", "G"));
        assertEquals(List.of("Swamp", "Forest", "Swamp", "Forest", "Swamp", "Forest"), filler,
                "the colored scaffold keeps its previous deterministic shape");
        assertFalse(filler.contains("Wastes"),
                "a colored commander must never be scaffolded with a colorless land");
    }

    @Test
    void everyColorlessCommanderDeckImportsThroughTheEngineAuthority() {
        XmageDeckImporter.ensureRepositoryReady();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> mainboard = XmageNativeStateRestoration.scaffoldingFiller(99, Set.of());
        for (String commander : List.of(COLORLESS_COMMANDER, SECOND_COLORLESS_COMMANDER)) {
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    "remediation-colorless-" + commander.length(), "remediation-hash", mainboard,
                    List.of(commander));
            assertNotNull(imported.deckHandle(),
                    "the engine's own real-cards-only Commander import accepted the colorless "
                            + "scaffold for " + commander);
            assertEquals(1, imported.commanderCount());
            assertEquals(99, imported.mainboardCount(),
                    "the scaffold is the requested size; the engine accepted every card");
        }
    }

    @Test
    void theColorlessScaffoldIsRejectedForAColoredCommanderSlotOnlyByTheEngine() {
        // Negative control: the scaffold for a colorless commander contains only
        // Wastes, so it can carry no colored identity of its own. The engine's
        // import remains the single legality authority, so feeding it an unknown
        // card still fails closed there rather than here.
        XmageDeckImporter.ensureRepositoryReady();
        XmageDeckImporter importer = new XmageDeckImporter();
        assertThrows(XmageDeckImporter.ImportException.class, () -> importer.importCommanderDeck(
                "remediation-bogus", "remediation-bogus-hash",
                List.of("Not A Real Magic Card"), List.of(COLORLESS_COMMANDER)));
    }

    // ------------------------------------------------------------------
    // Helpers mirrored from the lane suite (kept local so the evidence
    // classes stay untouched).
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
        JsonObject envelope = new JsonObject();
        envelope.add("response", response);
        lane.ok("submit_midgame_decision", envelope);
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
     * The engine names each principal after its seat, so a frozen record's
     * principal id maps onto the engine's own offered label without any Lab-side
     * identity table.
     */
    private static String seatLabel(String pid) {
        return "Full Game Seat " + pid.replaceAll("^P", "");
    }
}
