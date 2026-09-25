package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.abilities.effects.common.continuous.BecomesFaceDownCreatureEffect;
import mage.cards.decks.Deck;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * WS2 qualification: native-state-restoration capability on real cards.
 *
 * <p>Positive tests construct frozen requested states (parsed from the frozen
 * WS47 materialization, never hand-copied) through public engine APIs, drive
 * natural arrival at turn 1 precombat main with keeps and priority passes
 * only, restore commander cast counts, revalidate through engine
 * state-based actions plus layers, and require an exact native-readback
 * match. Negative tests prove fail-closed rejection and compare sensitivity.
 * No mapping classification is awarded here; the global
 * {@code starting_state_injection_supported} flag must stay false.</p>
 */
class XmageNativeStateRestorationTest {

    private static final Map<String, List<String>> COMMANDER_COLORS = Map.of(
            "Rograkh, Son of Rohgahh", List.of("R"),
            "Kediss, Emberclaw Familiar", List.of("R"),
            "Isamaru, Hound of Konda", List.of("W"));

    static Path repoRoot() {
        Path candidate = Path.of(System.getProperty("user.dir"));
        for (int depth = 0; depth < 4; depth++) {
            if (Files.isDirectory(candidate.resolve("qualification/ws47"))) {
                return candidate;
            }
            candidate = candidate.getParent();
        }
        throw new AssertionError("repository root with qualification/ws47 not found");
    }

    static JsonObject frozenRecord(String fixtureId) {
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

    static List<String> importScaffolding(
            XmageDeckImporter importer, XmageNativeStateRestoration.Plan plan, String deckTag) {
        Map<String, List<String>> commandersByOwner = new HashMap<>();
        for (XmageNativeStateRestoration.RequestedCommander commander : plan.commanders()) {
            commandersByOwner
                    .computeIfAbsent(commander.owner(), owner -> new ArrayList<>())
                    .add(commander.cardIdentity());
        }
        List<String> handles = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedPlayer player : plan.players()) {
            List<String> commanders = commandersByOwner.getOrDefault(
                    player.playerId(), List.of());
            assertFalse(commanders.isEmpty(), "every seat needs a commander: " + player.playerId());
            assertTrue(commanders.size() <= 2, "commander count: " + player.playerId());
            java.util.Set<String> colors = new java.util.HashSet<>();
            for (String commander : commanders) {
                List<String> known = COMMANDER_COLORS.get(commander);
                assertTrue(known != null, "color table missing commander: " + commander);
                colors.addAll(known);
            }
            int fillerCount = 100 - commanders.size();
            List<String> mainboard =
                    XmageNativeStateRestoration.scaffoldingFiller(fillerCount, colors);
            handles.add(importer.importCommanderDeck(
                    deckTag + "-" + player.playerId(), deckTag + "-hash",
                    mainboard, commanders).deckHandle());
        }
        return handles;
    }

    static XmageNativeStateRestoration restorationFor(
            XmageNativeStateRestoration.Plan plan) {
        List<String> identities = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedObject object : plan.objects()) {
            identities.add(object.cardIdentity());
        }
        return new XmageNativeStateRestoration(plan,
                XmageNativeStateRestoration.materializeCards(identities));
    }

    static String pidOf(Map<String, Player> seats, String actorUuid) {
        for (Map.Entry<String, Player> entry : seats.entrySet()) {
            if (entry.getValue().getId().toString().equals(actorUuid)) {
                return entry.getKey();
            }
        }
        fail("unknown actor UUID: " + actorUuid);
        return "?";
    }

    static JsonObject singleActionOfType(
            JsonObject legal, String actionType, String optionType) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!actionType.equals(action.get("action_type").getAsString())) {
                continue;
            }
            if (optionType == null) {
                matches.add(action);
                continue;
            }
            JsonObject metadata = action.getAsJsonObject("metadata");
            String actual = metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if (optionType.equals(actual)) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(),
                "expected exactly one " + actionType + "/" + optionType);
        return matches.get(0);
    }

    static JsonObject singleSelfAction(JsonObject legal, String actorId) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (action.get("action_id").getAsString().endsWith(":" + actorId)) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "expected exactly one self action");
        return matches.get(0);
    }

    static JsonObject genericProposal(
            String proposalId, String actorId, String actionId, String actionType) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        proposal.addProperty("actor_id", actorId);
        proposal.addProperty("legal_action_id", actionId);
        proposal.addProperty("action_type", actionType);
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "native-state-arrival");
        return proposal;
    }

    /**
     * Drives keeps and priority passes (harness transport only, never fixture
     * decisions) until the native readback shows the requested temporal
     * point. Fails closed on any unexpected decision class or bound breach.
     */
    static void driveArrival(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats) {
        for (int step = 0; step < 80; step++) {
            JsonObject readback = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats);
            if (readback.get("turn_number").getAsInt() == 1
                    && readback.get("phase").getAsString().equals("PRECOMBAT_MAIN")
                    && readback.get("step").getAsString().equals("PRECOMBAT_MAIN")) {
                return;
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before arrival at step " + step);
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            JsonObject action;
            String proposalId = "arrival-" + step;
            if ("mulligan".equals(decisionClass)) {
                action = singleActionOfType(legal, "mulligan", "keep");
            } else if ("choose_object".equals(decisionClass)
                    && pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    && pending.get("prompt").getAsString().contains("starting player")) {
                action = singleSelfAction(legal, actorId);
            } else if ("priority".equals(decisionClass)) {
                action = singleActionOfType(legal, "pass_priority", null);
            } else {
                fail("unexpected decision class during arrival: " + decisionClass
                        + " at step " + step);
                return;
            }
            JsonObject after = session.submitAction(genericProposal(
                    proposalId, actorId,
                    action.get("action_id").getAsString(),
                    action.get("action_type").getAsString()));
            assertEquals(pending.get("decision_id").getAsString(),
                    after.get("executed_decision_id").getAsString());
        }
        fail("arrival bound breached without reaching turn 1 precombat main");
    }

    static XmageNativeStateRestoration.CompareVerdict restoreAndCompare(
            String gameId,
            XmageNativeStateRestoration.Plan plan,
            XmageDeckImporter importer) {
        XmageNativeStateRestoration restoration = restorationFor(plan);
        List<String> handles = importScaffolding(importer, plan, gameId);
        XmageFullGameSession session = new XmageFullGameSession(
                gameId, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        completeArrival(session, restoration, seats);
        JsonObject observed =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        return restoration.compare(observed, seats);
    }

    /**
     * Post-arrival completion while the engine is parked: controller
     * attribution, commander cast-count restore, engine revalidation.
     */
    static void completeArrival(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats) {
        driveArrival(session, restoration, seats);
        restoration.restoreCommanderCasts(session.restorationGame(), seats);
        XmageNativeStateRestoration.revalidate(session.restorationGame());
    }

    @Test
    void tax2RequestedStateMatchesNativeReadback() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        frozenRecord("WS05-CMD-TAX-2"), "ws2-tax2", 424242L);
        XmageNativeStateRestoration.CompareVerdict verdict =
                restoreAndCompare("ws2-tax2", plan, new XmageDeckImporter());
        assertTrue(verdict.mismatches().isEmpty(),
                "TAX-2 readback mismatches: " + verdict.mismatches());
        assertTrue(verdict.match());
        assertEquals(64, verdict.requestedDigest().length());
        assertEquals(64, verdict.constructedDigest().length());
    }

    @Test
    void card02CommandZoneMatchesNativeReadback() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        frozenRecord("CARD_02"), "ws2-card02", 424242L);
        XmageNativeStateRestoration.CompareVerdict verdict =
                restoreAndCompare("ws2-card02", plan, new XmageDeckImporter());
        assertTrue(verdict.mismatches().isEmpty(),
                "CARD_02 readback mismatches: " + verdict.mismatches());
        assertTrue(verdict.match());
    }

    @Test
    void layersAuthorityObservedOnRestoredBoard() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        frozenRecord("MICRO_LAYERS"), "ws2-layers", 424242L);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration = restorationFor(plan);
        List<String> handles = importScaffolding(importer, plan, "ws2-layers");
        XmageFullGameSession session = new XmageFullGameSession(
                "ws2-layers", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        completeArrival(session, restoration, seats);
        JsonObject observed =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        XmageNativeStateRestoration.CompareVerdict verdict = restoration.compare(observed, seats);
        assertTrue(verdict.mismatches().isEmpty(),
                "MICRO_LAYERS mismatches: " + verdict.mismatches());
        for (JsonElement seatElement : observed.getAsJsonArray("seats")) {
            JsonObject seat = seatElement.getAsJsonObject();
            String pid = seat.get("player_id").getAsString();
            for (JsonElement entryElement : seat.getAsJsonArray("battlefield")) {
                JsonObject entry = entryElement.getAsJsonObject();
                if (entry.get("card_identity").getAsString().equals("Grizzly Bears")) {
                    // Humility is global (all creatures 1/1 base); Anthem pumps
                    // P1's creatures only: P1 Bears 2/2, all other Bears 1/1.
                    int expected = pid.equals("P1") ? 2 : 1;
                    assertEquals(expected, entry.get("power").getAsInt(),
                            "layer 7b/7c authority for " + pid);
                    assertEquals(expected, entry.get("toughness").getAsInt(),
                            "layer 7b/7c authority for " + pid);
                }
            }
        }
    }

    @Test
    void restoredStateIsDeterministicAcrossRuns() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        frozenRecord("WS05-CMD-TAX-2"), "ws2-determinism", 424242L);
        XmageNativeStateRestoration.CompareVerdict first =
                restoreAndCompare("ws2-det-a", plan, new XmageDeckImporter());
        XmageNativeStateRestoration.CompareVerdict second =
                restoreAndCompare("ws2-det-b", plan, new XmageDeckImporter());
        assertTrue(first.match() && second.match());
        assertEquals(first.constructedDigest(), second.constructedDigest(),
                "same seed must reproduce the same constructed state");
    }

    @Test
    void elimLifeZeroIsNotCredited() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        frozenRecord("WS05-MP-ELIM-OWNED-3"), "ws2-elim", 424242L);
        XmageNativeStateRestoration.CompareVerdict verdict =
                restoreAndCompare("ws2-elim", plan, new XmageDeckImporter());
        assertFalse(verdict.match(),
                "life-0 state cannot survive authoritative state-based actions");
        assertFalse(verdict.mismatches().isEmpty());
    }

    @Test
    void mulliganConstructionValidation() {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> mainboard = new ArrayList<>();
        for (int index = 0; index < 99; index++) {
            mainboard.add("Mountain");
        }
        List<String> handles = new ArrayList<>();
        for (int seat = 1; seat <= 2; seat++) {
            handles.add(importer.importCommanderDeck(
                    "ws2-mullval-" + seat, "ws2-mullval-hash", mainboard,
                    List.of("Rograkh, Son of Rohgahh")).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                "WS05-CMD-MULL-2-validation", handles, 0, 40, 424242L, importer);
        session.start();
        for (int step = 0; step < 12; step++) {
            JsonObject pending = session.pendingDecisionPayload();
            assertFalse(pending.get("decision").isJsonNull(), "a decision must be pending");
            JsonObject decision = pending.getAsJsonObject("decision");
            if ("mulligan".equals(decision.get("decision_class").getAsString())) {
                break;
            }
            assertEquals("choose_object", decision.get("decision_class").getAsString());
            JsonObject legal = session.legalActionsPayload();
            JsonObject self = singleSelfAction(
                    legal, legal.get("actor_id").getAsString());
            JsonObject after = session.submitAction(genericProposal(
                    "ws2-mullval-" + step, legal.get("actor_id").getAsString(),
                    self.get("action_id").getAsString(), self.get("action_type").getAsString()));
            assertEquals(decision.get("decision_id").getAsString(),
                    after.get("executed_decision_id").getAsString());
            if (step == 11) {
                fail("mulligan phase never began");
            }
        }
        Map<String, Player> seats = session.restorationSeats();
        JsonObject observed = XmageNativeStateRestoration.readback(
                session.restorationGame(), seats);
        assertEquals(424242L, observed.get("rules_seed").getAsLong());
        assertTrue(observed.get("rules_seed_explicit").getAsBoolean());
        for (JsonElement seatElement : observed.getAsJsonArray("seats")) {
            JsonObject seat = seatElement.getAsJsonObject();
            assertEquals(92, seat.get("library_count").getAsInt(), "99 minus opening seven");
            assertEquals(7, seat.get("hand_count").getAsInt(), "opening seven");
            JsonArray commanders = seat.getAsJsonArray("commanders");
            assertEquals(1, commanders.size());
            assertEquals("Rograkh, Son of Rohgahh",
                    commanders.get(0).getAsJsonObject().get("card_identity").getAsString());
            assertEquals(0, commanders.get(0).getAsJsonObject().get("prior_casts").getAsInt());
        }
    }

    /**
     * DR-CLOSURE-01 Phase 1 (v2 hand dimension): the frozen TRIG-3 record
     * parses, restores P1's hand Grizzly Bears through the engine's typed
     * setup primitive, and matches the native readback (subset + count
     * pinned). Genuine Rules transition: a real priority pass advances the
     * game and the restored hand card is offered through the engine's own
     * cast-legality pipeline with its real cost.
     */
    @Test
    void trig3HandIdentityMatchesNativeReadback() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        frozenRecord("WS05-MP-TRIG-3"), "ws2-trig3-hand", 424242L);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration = restorationFor(plan);
        List<String> handles = importScaffolding(importer, plan, "ws2-trig3-hand");
        XmageFullGameSession session = new XmageFullGameSession(
                "ws2-trig3-hand", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        completeArrival(session, restoration, seats);
        JsonObject observed =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        XmageNativeStateRestoration.CompareVerdict verdict =
                restoration.compare(observed, seats);
        assertTrue(verdict.mismatches().isEmpty(),
                "TRIG-3 hand readback mismatches: " + verdict.mismatches());
        assertTrue(verdict.match());
        boolean bearsInP1Hand = false;
        for (JsonElement seatElement : observed.getAsJsonArray("seats")) {
            JsonObject seat = seatElement.getAsJsonObject();
            if (!seat.get("player_id").getAsString().equals("P1")) {
                continue;
            }
            assertTrue(seat.get("hand_count").getAsInt() >= 8,
                    "opening seven plus the restored Grizzly Bears (plus any natural draws)");
            for (JsonElement card : seat.getAsJsonArray("hand")) {
                if (card.getAsString().equals("Grizzly Bears")) {
                    bearsInP1Hand = true;
                }
            }
        }
        assertTrue(bearsInP1Hand, "restored Grizzly Bears must sit in P1's hand");
        // Genuine Rules transition: pass priority with the restored state and
        // prove the engine still advances and still offers the restored card
        // through its own legality pipeline (P1 holds 2 Forests: {1}{G} payable).
        JsonObject legal = session.legalActionsPayload();
        assertEquals(pidOf(seats, legal.get("actor_id").getAsString()), "P1");
        boolean bearsOffered = false;
        List<String> offeredTypes = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            offeredTypes.add(action.get("action_type").getAsString());
            // Cast-from-hand projects as a priority ability option carrying
            // the source card identity in its metadata (engine-computed).
            if (action.toString().contains("Grizzly Bears")) {
                bearsOffered = true;
            }
        }
        assertTrue(bearsOffered,
                "engine must offer the restored hand card through its own legality; "
                        + "offered=" + offeredTypes);
        JsonObject passAction = singleActionOfType(legal, "pass_priority", null);
        JsonObject after = session.submitAction(genericProposal(
                "ws2-trig3-hand-pass", legal.get("actor_id").getAsString(),
                passAction.get("action_id").getAsString(),
                passAction.get("action_type").getAsString()));
        assertTrue(after.has("executed_decision_id"));
        JsonObject reread =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        // The pass legitimately advances priority away from the plan pin, so
        // assert transition invariants rather than a stale full match: the
        // restored hand card survives, life totals hold, and priority really
        // moved (proving a genuine engine transition, not a no-op).
        assertTrue(!reread.get("priority_player").getAsString().equals("P1"),
                "priority must advance after a real pass");
        boolean bearsSurvives = false;
        for (JsonElement seatElement : reread.getAsJsonArray("seats")) {
            JsonObject seat = seatElement.getAsJsonObject();
            assertEquals(40, seat.get("life").getAsInt());
            if (!seat.get("player_id").getAsString().equals("P1")) {
                continue;
            }
            for (JsonElement card : seat.getAsJsonArray("hand")) {
                if (card.getAsString().equals("Grizzly Bears")) {
                    bearsSurvives = true;
                }
            }
        }
        assertTrue(bearsSurvives, "restored hand card must survive the transition");
    }

    /**
     * DR-CLOSURE-01 Phase 1 honeycard: a distinctive restored hand card for a
     * non-actor principal ("Shivan Dragon" in P2's hand, nowhere else) must
     * never appear in the actor's pilot-facing observation, while the
     * engine-direct oracle still proves the restore. Pilot-facing hand arrays
     * stay actor-only (structural negative).
     */
    @Test
    void restoredHandHoneycardNeverLeaksToWrongPrincipal() {
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "ws2-hand-honey", 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Rograkh, Son of Rohgahh", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0)),
                List.of(
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:forest", "Forest", "P1", "P1",
                                mage.constants.Zone.BATTLEFIELD, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:honey", "Shivan Dragon", "P2", "P2",
                                mage.constants.Zone.HAND, false)),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration = restorationFor(plan);
        List<String> handles = importScaffolding(importer, plan, "ws2-hand-honey");
        XmageFullGameSession session = new XmageFullGameSession(
                "ws2-hand-honey", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        completeArrival(session, restoration, seats);
        XmageNativeStateRestoration.CompareVerdict verdict =
                restoration.compare(
                        XmageNativeStateRestoration.readback(
                                session.restorationGame(), seats), seats);
        assertTrue(verdict.match(),
                "honeycard restore must match engine-direct: " + verdict.mismatches());
        // Oracle (test-only peeking): the honeycard sits in P2's engine hand.
        boolean oracleSeesHoney = false;
        for (mage.cards.Card card
                : seats.get("P2").getHand().getCards(session.restorationGame())) {
            if (card.getName().equals("Shivan Dragon")) {
                oracleSeesHoney = true;
            }
        }
        assertTrue(oracleSeesHoney, "oracle must see the honeycard restore");
        // Pilot-facing: no pending view may carry the honeycard identity.
        for (int step = 0; step < 6; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String actorId = pending.get("actor_id").getAsString();
            String actorPid = pidOf(seats, actorId);
            JsonObject pilotState = pending.getAsJsonObject("pilot_state");
            if (!actorPid.equals("P2")) {
                assertTrue(!pilotState.toString().contains("Shivan Dragon"),
                        "honeycard identity leaked to " + actorPid + " at step " + step);
            }
            for (JsonElement element : pilotState.getAsJsonArray("players")) {
                JsonObject entry = element.getAsJsonObject();
                if (!entry.get("player_id").getAsString().equals(actorId)) {
                    assertTrue(!entry.has("hand"),
                            "opponent hand array must be absent for "
                                    + entry.get("player_id").getAsString());
                }
            }
            JsonObject legal = session.legalActionsPayload();
            JsonObject action = singleActionOfType(legal,
                    pending.get("decision_class").getAsString().equals("mulligan")
                            ? "mulligan" : "pass_priority",
                    pending.get("decision_class").getAsString().equals("mulligan")
                            ? "keep" : null);
            session.submitAction(genericProposal(
                    "ws2-hand-honey-" + step, actorId,
                    action.get("action_id").getAsString(),
                    action.get("action_type").getAsString()));
        }
    }

    @Test
    void naturalSameNameCannotMaskMissingInjectedHandObject() {
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "ws2-hand-provenance", 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Rograkh, Son of Rohgahh", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0)),
                List.of(new XmageNativeStateRestoration.RequestedObject(
                        "obj:injected-mountain", "Mountain", "P1", "P1",
                        mage.constants.Zone.HAND, false)),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration = restorationFor(plan);
        List<String> handles = importScaffolding(importer, plan, "ws2-hand-provenance");
        XmageFullGameSession session = new XmageFullGameSession(
                "ws2-hand-provenance", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        completeArrival(session, restoration, seats);

        JsonObject observed =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        assertTrue(restoration.compare(observed, seats).match(),
                "exact injected Mountain must initially earn credit");

        java.util.Set<java.util.UUID> injected =
                restoration.injectedHandIdsForTests("P1");
        assertEquals(1, injected.size(), "one requested hand object has one native identity");
        java.util.UUID injectedId = injected.iterator().next();
        assertTrue(seats.get("P1").getHand().contains(injectedId),
                "injected native object is actually in P1 hand");

        int mountainsBefore = 0;
        for (mage.cards.Card card
                : seats.get("P1").getHand().getCards(session.restorationGame())) {
            if (card.getName().equals("Mountain")) {
                mountainsBefore++;
            }
        }
        assertTrue(mountainsBefore >= 2,
                "natural scaffolding draws must provide same-name decoys for this regression");

        // Adversarial test-only tamper: remove exactly the injected UUID while
        // leaving natural same-name Mountains in hand. The old name-subset
        // comparison would still pass; provenance-bound comparison must fail.
        assertTrue(seats.get("P1").getHand().remove(injectedId));
        JsonObject tampered =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        XmageNativeStateRestoration.CompareVerdict verdict =
                restoration.compare(tampered, seats);
        assertFalse(verdict.match(),
                "natural same-name draws must never mask a missing injected object");
        assertTrue(verdict.mismatches().stream()
                        .anyMatch(message -> message.startsWith("hand injected object missing:")),
                "failure must be attributed to injected-object provenance: "
                        + verdict.mismatches());
    }

    @Test
    void rejectsLibraryIdentityBeforeMutation() {
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "ws2-neg-library", 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(),
                List.of(new XmageNativeStateRestoration.RequestedObject(
                        "obj:library", "Mountain", "P1", "P1", mage.constants.Zone.LIBRARY, false)),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        try {
            restorationFor(plan);
            fail("library identity must fail closed");
        } catch (XmageNativeStateRestoration.RestorationException exc) {
            assertTrue(exc.getMessage().startsWith("UNSUPPORTED_ZONE"), exc.getMessage());
        }
    }

    @Test
    void rejectsNonMainTemporalPoint() {
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "ws2-neg-temporal", 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(), List.of(), 1, mage.constants.TurnPhase.COMBAT,
                mage.constants.PhaseStep.DECLARE_ATTACKERS, "P1", "P1");
        try {
            restorationFor(plan);
            fail("combat temporal point must fail closed in v1");
        } catch (XmageNativeStateRestoration.RestorationException exc) {
            assertTrue(exc.getMessage().startsWith("UNSUPPORTED_TEMPORAL_POINT"), exc.getMessage());
        }
    }

    @Test
    void rejectsUnknownCardName() {
        try {
            XmageNativeStateRestoration.materializeCards(List.of("Mock Card XYZ"));
            fail("mock card must fail closed");
        } catch (XmageNativeStateRestoration.RestorationException exc) {
            assertTrue(exc.getMessage().startsWith("UNKNOWN_CARD_NAME"), exc.getMessage());
        }
    }

    @Test
    void rejectsFrozenStackSpell() {
        try {
            XmageNativeStateRestoration.planFromFrozenRecord(
                    frozenRecord("WS05-CMD-ZONE-LIB-YES"), "ws2-neg-stack", 424242L);
            fail("stack-bearing frozen record must fail closed");
        } catch (XmageNativeStateRestoration.RestorationException exc) {
            assertTrue(exc.getMessage().startsWith("UNSUPPORTED_ZONE"), exc.getMessage());
        }
    }

    @Test
    void tamperedRequestDoesNotMatch() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        frozenRecord("WS05-CMD-TAX-2"), "ws2-tamper", 424242L);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration = restorationFor(plan);
        List<String> handles = importScaffolding(importer, plan, "ws2-tamper");
        XmageFullGameSession session = new XmageFullGameSession(
                "ws2-tamper", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        completeArrival(session, restoration, seats);
        JsonObject observed =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        assertTrue(restoration.compare(observed, seats).match());
        List<XmageNativeStateRestoration.RequestedPlayer> tamperedPlayers = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedPlayer player : plan.players()) {
            tamperedPlayers.add(new XmageNativeStateRestoration.RequestedPlayer(
                    player.playerId(), player.seat(),
                    player.playerId().equals("P1") ? 39 : player.life()));
        }
        XmageNativeStateRestoration.Plan tampered = new XmageNativeStateRestoration.Plan(
                plan.planId(), plan.playerCount(), plan.seed(), List.copyOf(tamperedPlayers),
                plan.commanders(), plan.objects(), plan.turnNumber(), plan.phase(), plan.step(),
                plan.activePlayer(), plan.priorityPlayer());
        XmageNativeStateRestoration.CompareVerdict verdict =
                new XmageNativeStateRestoration(tampered, restorationFor(plan)
                        .materializationVehicleForTests())
                        .compare(observed, seats);
        assertFalse(verdict.match(), "altered request must not match the readback");
        assertFalse(verdict.mismatches().isEmpty());
    }

    @Test
    void partnerCommandersMatch() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        frozenRecord("WS05-CMD-PARTNER-TAX"), "ws2-partner", 424242L);
        XmageNativeStateRestoration.CompareVerdict verdict =
                restoreAndCompare("ws2-partner", plan, new XmageDeckImporter());
        assertTrue(verdict.mismatches().isEmpty(),
                "PARTNER-TAX readback mismatches: " + verdict.mismatches());
        assertTrue(verdict.match());
    }

    @Test
    void graveyardExilePlacementMatches() {
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "ws2-grave-exile", 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Rograkh, Son of Rohgahh", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0)),
                List.of(
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:ring", "Sol Ring", "P1", "P1",
                                mage.constants.Zone.GRAVEYARD, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:mountain", "Mountain", "P1", "P1",
                                mage.constants.Zone.EXILED, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:mountain2", "Mountain", "P2", "P2",
                                mage.constants.Zone.GRAVEYARD, false)),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageNativeStateRestoration.CompareVerdict verdict =
                restoreAndCompare("ws2-grave-exile", plan, new XmageDeckImporter());
        assertTrue(verdict.mismatches().isEmpty(),
                "graveyard/exile mismatches: " + verdict.mismatches());
        assertTrue(verdict.match());
    }

    @Test
    void rejectsControlDivergence() {
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "ws2-neg-control", 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Rograkh, Son of Rohgahh", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0)),
                List.of(new XmageNativeStateRestoration.RequestedObject(
                        "obj:bears", "Grizzly Bears", "P1", "P2",
                        mage.constants.Zone.BATTLEFIELD, false)),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        try {
            restorationFor(plan);
            fail("control divergence must fail closed: engine layers re-derive control");
        } catch (XmageNativeStateRestoration.RestorationException exc) {
            assertTrue(exc.getMessage().startsWith("UNSUPPORTED_CONTROL_DIVERGENCE"),
                    exc.getMessage());
        }
    }

    @Test
    void globalCapabilityFlagStaysFalse() {
        JsonObject capabilities = XmageProvider.capabilitiesPayload()
                .getAsJsonObject("capabilities");
        assertFalse(capabilities.get("starting_state_injection_supported").getAsBoolean());
        JsonObject dimensions = XmageNativeStateRestoration.dimensionsPayload();
        assertFalse(dimensions.get("starting_state_injection_supported").getAsBoolean());
        assertTrue(!dimensions.getAsJsonArray("supported_dimensions").isEmpty());
        assertTrue(!dimensions.getAsJsonArray("unsupported_dimensions").isEmpty());
    }

    @Test
    void residualCandidateOrderedLibraryRestorePrimitiveIsRuntimeReachable() {
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "residual-library-api", 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Rograkh, Son of Rohgahh", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0)),
                List.of(), 1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration = restorationFor(plan);
        List<String> handles = importScaffolding(importer, plan, "residual-library-api");
        XmageFullGameSession session = new XmageFullGameSession(
                "residual-library-api", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        completeArrival(session, restoration, seats);

        Player p1 = seats.get("P1");
        List<UUID> original = new ArrayList<>(p1.getLibrary().getCardList());
        assertTrue(original.size() > 1, "scaffolding library must contain multiple cards");
        List<UUID> requested = new ArrayList<>(original);
        Collections.reverse(requested);
        p1.getLibrary().restoreOrderForGameLoad(requested, session.restorationGame());
        assertEquals(requested, p1.getLibrary().getCardList(),
                "bridge runtime must execute the residual candidate's exact ordered-library API");
    }

    @Test
    void residualCandidateFaceDownRestorePrimitiveIsRuntimeReachable() {
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "residual-facedown-api", 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Rograkh, Son of Rohgahh", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0)),
                List.of(new XmageNativeStateRestoration.RequestedObject(
                        "obj:P1-bears", "Grizzly Bears", "P1", "P1",
                        mage.constants.Zone.BATTLEFIELD, false)),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration = restorationFor(plan);
        List<String> handles = importScaffolding(importer, plan, "residual-facedown-api");
        XmageFullGameSession session = new XmageFullGameSession(
                "residual-facedown-api", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        completeArrival(session, restoration, seats);

        Permanent bears = session.restorationGame().getBattlefield().getAllActivePermanents().stream()
                .filter(p -> p.getOwnerId().equals(seats.get("P1").getId()))
                .filter(p -> "Grizzly Bears".equals(p.getName()))
                .findFirst()
                .orElseThrow(() -> new AssertionError("restored Grizzly Bears missing"));
        BecomesFaceDownCreatureEffect.restoreFaceDownStateForGameLoad(
                bears.getId(),
                BecomesFaceDownCreatureEffect.FaceDownType.MANIFESTED,
                session.restorationGame());
        XmageNativeStateRestoration.revalidate(session.restorationGame());

        assertTrue(bears.isFaceDown(session.restorationGame()));
        assertTrue(bears.isManifested());
        assertFalse(bears.isCloaked());
        assertFalse(XmageProvider.capabilitiesPayload().getAsJsonObject("capabilities")
                .get("starting_state_injection_supported").getAsBoolean(),
                "bounded native primitive reachability must not inflate the global capability");
    }

}
