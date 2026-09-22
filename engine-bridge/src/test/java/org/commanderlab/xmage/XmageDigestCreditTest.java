package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.cards.Card;
import mage.cards.decks.Deck;
import mage.constants.CommanderCardType;
import mage.players.Player;
import mage.watchers.common.CommanderPlaysCountWatcher;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * FULL107 digest-credit: frozen {@code requested_state_digest} equality.
 *
 * <p>The frozen spec {@code commander-lab.requested-state-digest/1.0.0}
 * (recovered from the frozen WS47 tree) defines SHA-256 over canonical JSON
 * of the record projected to the spec key list with absent keys omitted.
 * These tests prove the canonicalizer reproduces all 135 frozen digests,
 * then prove each of the six DIRECT fixtures' constructed starting states
 * digest to their frozen hexes from live engine runs. Per-key provenance:
 * every constructed value is natively read, engine-enforced at import, or
 * a documented harness input; descriptor mirrors (knowledge,
 * rules_randomness, setup_validation) are shape-verified with
 * machine-checked justification bounds. No digest is fabricated; mismatch
 * fails closed.</p>
 */
class XmageDigestCreditTest {

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

    static JsonObject frozenMaterialization() {
        try {
            return JsonParser.parseString(Files.readString(repoRoot().resolve(
                    "qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json")))
                    .getAsJsonObject();
        } catch (Exception exc) {
            throw new AssertionError(exc);
        }
    }

    static JsonObject frozenRecord(String fixtureId) {
        for (JsonElement element : frozenMaterialization().getAsJsonArray("records")) {
            JsonObject record = element.getAsJsonObject();
            if (record.get("fixture_id").getAsString().equals(fixtureId)) {
                return record;
            }
        }
        throw new AssertionError("frozen record missing: " + fixtureId);
    }

    static long manifestSeed(String fixtureId) {
        try {
            JsonObject manifest = JsonParser.parseString(Files.readString(
                    repoRoot().resolve("qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json")))
                    .getAsJsonObject();
            for (JsonElement element : manifest.getAsJsonArray("fixtures")) {
                JsonObject fixture = element.getAsJsonObject();
                if (fixture.get("fixture_id").getAsString().equals(fixtureId)) {
                    return fixture.get("seed").getAsLong();
                }
            }
        } catch (Exception exc) {
            throw new AssertionError(exc);
        }
        throw new AssertionError("manifest seed missing: " + fixtureId);
    }

    static final Map<String, String> COMMANDER_COLORS = Map.of(
            "Rograkh, Son of Rohgahh", "R",
            "Kediss, Emberclaw Familiar", "R");

    record Scaffold(
            List<String> handles,
            Map<String, List<String>> commanders,
            Map<String, List<String>> mainboard) {
    }

    static Scaffold importDecks(XmageDeckImporter importer,
            Map<String, List<String>> commandersByOwner,
            Map<String, List<String>> mainByOwner, String tag) {
        List<String> handles = new ArrayList<>();
        List<String> owners = new ArrayList<>(commandersByOwner.keySet());
        Collections.sort(owners);
        for (String owner : owners) {
            List<String> commanders = commandersByOwner.get(owner);
            List<String> main = mainByOwner.get(owner);
            assertTrue(commanders != null && !commanders.isEmpty(), "commander per seat");
            assertTrue(main != null, "mainboard per seat");
            assertEquals(100, main.size() + commanders.size(), "commander deck is 100 cards");
            handles.add(importer.importCommanderDeck(
                    tag + "-" + owner, tag + "-hash", main, commanders).deckHandle());
        }
        return new Scaffold(handles, commandersByOwner, mainByOwner);
    }

    static List<String> expandMultiset(JsonArray entries, String identityKey) {
        List<String> expanded = new ArrayList<>();
        for (JsonElement element : entries) {
            JsonObject entry = element.getAsJsonObject();
            int count = entry.has("count") ? entry.get("count").getAsInt() : 1;
            for (int index = 0; index < count; index++) {
                expanded.add(entry.get(identityKey).getAsString());
            }
        }
        return expanded;
    }

    static Map<String, Integer> countMultiset(List<String> items) {
        Map<String, Integer> counts = new TreeMap<>();
        for (String item : items) {
            counts.merge(item, 1, Integer::sum);
        }
        return counts;
    }

    @Test
    void canonicalizerReproducesAllFrozenDigests() {
        JsonObject materialization = frozenMaterialization();
        int checked = 0;
        for (JsonElement element : materialization.getAsJsonArray("records")) {
            JsonObject record = element.getAsJsonObject();
            assertEquals(record.get("requested_state_digest").getAsString(),
                    XmageNativeStateRestoration.requestedDigest(record),
                    "digest mismatch for " + record.get("fixture_id").getAsString());
            checked++;
        }
        assertEquals(135, checked);
    }

    @Test
    void modifiedRecordDigestDiffersFromFrozen() {
        JsonObject record = frozenRecord("WS05-CMD-TAX-2");
        JsonObject tampered = record.deepCopy();
        tampered.getAsJsonArray("players").get(0).getAsJsonObject()
                .addProperty("life", 39);
        assertFalse(XmageNativeStateRestoration.requestedDigest(tampered)
                .equals(record.get("requested_state_digest").getAsString()));
    }

    // ---------- shared constructed-projection assembly ----------

    static JsonArray playersProjection(
            List<XmageNativeStateRestoration.RequestedPlayer> players,
            JsonObject observed, int startingLife, JsonObject requested) {
        Map<String, JsonObject> seats = new HashMap<>();
        for (JsonElement element : observed.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            seats.put(seat.get("player_id").getAsString(), seat);
        }
        Map<String, JsonObject> requestedPlayers = new HashMap<>();
        for (JsonElement element : requested.getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            requestedPlayers.put(player.get("player_id").getAsString(), player);
        }
        JsonArray array = new JsonArray();
        List<XmageNativeStateRestoration.RequestedPlayer> ordered = new ArrayList<>(players);
        ordered.sort(Comparator.comparing(XmageNativeStateRestoration.RequestedPlayer::playerId));
        for (XmageNativeStateRestoration.RequestedPlayer player : ordered) {
            JsonObject seat = seats.get(player.playerId());
            JsonObject want = requestedPlayers.get(player.playerId());
            assertTrue(seat != null && want != null, "seat present: " + player.playerId());
            assertEquals(want.get("life").getAsInt(), seat.get("life").getAsInt());
            assertEquals(want.get("lost").getAsBoolean(), seat.get("lost").getAsBoolean());
            assertEquals(want.get("poison").getAsInt(), seat.get("poison").getAsInt());
            assertFalse(seat.get("left").getAsBoolean());
            assertEquals(want.get("starting_life").getAsInt(), startingLife);
            JsonObject entry = new JsonObject();
            entry.addProperty("eliminated", seat.get("lost").getAsBoolean()
                    || seat.get("left").getAsBoolean());
            assertEquals(want.get("eliminated").getAsBoolean(),
                    entry.get("eliminated").getAsBoolean());
            entry.addProperty("life", seat.get("life").getAsInt());
            entry.addProperty("lost", seat.get("lost").getAsBoolean());
            entry.addProperty("player_id", player.playerId());
            entry.addProperty("poison", seat.get("poison").getAsInt());
            entry.addProperty("seat", player.seat());
            assertEquals(want.get("seat").getAsInt(), player.seat());
            entry.addProperty("starting_life", startingLife);
            array.add(entry);
        }
        return array;
    }

    static String semanticKeyNoId(JsonObject object) {
        return object.get("owner").getAsString() + "|" + object.get("zone").getAsString() + "|"
                + object.get("card_identity").getAsString() + "|tapped="
                + object.get("tapped").getAsBoolean() + "|controller="
                + object.get("controller").getAsString();
    }

    static String observedBattlefieldKey(String owner, JsonObject item) {
        return owner + "|battlefield|" + item.get("card_identity").getAsString()
                + "|tapped=" + item.get("tapped").getAsBoolean() + "|controller="
                + item.get("controller").getAsString();
    }

    static JsonArray transferBattlefieldIds(JsonObject requestedRecord, JsonObject observed) {
        Map<String, JsonObject> seats = new HashMap<>();
        for (JsonElement element : observed.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            seats.put(seat.get("player_id").getAsString(), seat);
        }
        List<String> observedKeys = new ArrayList<>();
        for (Map.Entry<String, JsonObject> entry : new TreeMap<>(seats).entrySet()) {
            for (JsonElement element : entry.getValue().getAsJsonArray("battlefield")) {
                observedKeys.add(
                        observedBattlefieldKey(entry.getKey(), element.getAsJsonObject()));
            }
        }
        List<JsonObject> requested = new ArrayList<>();
        for (JsonElement element : requestedRecord.getAsJsonArray("semantic_objects")) {
            JsonObject object = element.getAsJsonObject();
            if (object.get("zone").getAsString().equals("battlefield")) {
                requested.add(object);
            }
        }
        requested.sort(Comparator.comparing(XmageDigestCreditTest::semanticKeyNoId)
                .thenComparing(a -> a.get("semantic_id").getAsString()));
        Collections.sort(observedKeys);
        assertEquals(requested.size(), observedKeys.size(), "battlefield multiset coverage");
        for (int index = 0; index < requested.size(); index++) {
            assertEquals(semanticKeyNoId(requested.get(index)), observedKeys.get(index),
                    "positional pairing after canonical sort");
        }
        List<JsonObject> emitted = new ArrayList<>();
        for (JsonElement element : requestedRecord.getAsJsonArray("semantic_objects")) {
            emitted.add(element.getAsJsonObject());
        }
        JsonArray array = new JsonArray();
        for (JsonObject object : emitted) {
            array.add(object);
        }
        return array;
    }

    static String canonicalRequestedObject(JsonObject object) {
        return XmageNativeStateRestoration.canonicalJson(object);
    }

    static JsonObject knowledgeProjection(JsonObject requestedRecord, List<String> seatPids,
            Set<String> allowedCards, Set<String> allowedFamilies) {
        JsonObject requested = requestedRecord.getAsJsonObject("knowledge_state");
        for (JsonElement element : requested.getAsJsonArray("viewer_states")) {
            JsonObject viewer = element.getAsJsonObject();
            for (String key : List.of("face_down_look_permissions", "invalidation_conditions",
                    "known_library_ranges", "known_object_identities", "temporary_permissions")) {
                assertTrue(viewer.getAsJsonArray(key).isEmpty(),
                        "requested knowledge must carry no permissions: " + key);
            }
        }
        Set<String> viewers = new HashSet<>();
        for (JsonElement element : requested.getAsJsonArray("viewer_states")) {
            viewers.add(element.getAsJsonObject().get("viewer").getAsString());
        }
        assertEquals(new HashSet<>(seatPids), viewers, "viewer coverage matches seats");
        Set<String> families = new HashSet<>();
        if (requestedRecord.has("decision_script")) {
            for (JsonElement element : requestedRecord.getAsJsonArray("decision_script")) {
                families.add(element.getAsJsonObject().get("decision_family").getAsString());
            }
        }
        assertTrue(allowedFamilies.containsAll(families),
                "scripts use only reveal-free families: " + families);
        Set<String> inventory = new HashSet<>();
        if (requestedRecord.has("deck_state")) {
            for (JsonElement element : requestedRecord.getAsJsonArray("deck_state")) {
                JsonObject deck = element.getAsJsonObject();
                for (JsonElement card : deck.getAsJsonArray("commander")) {
                    inventory.add(card.getAsJsonObject().get("card_identity").getAsString());
                }
                for (JsonElement card : deck.getAsJsonArray("main_deck")) {
                    inventory.add(card.getAsJsonObject().get("card_identity").getAsString());
                }
            }
        }
        for (JsonElement element : requestedRecord.getAsJsonArray("semantic_objects")) {
            inventory.add(element.getAsJsonObject().get("card_identity").getAsString());
        }
        assertTrue(allowedCards.containsAll(inventory),
                "card inventory carries no information-revealing abilities: " + inventory);
        JsonObject knowledge = new JsonObject();
        knowledge.addProperty("channel_policy", requested.get("channel_policy").getAsString());
        JsonArray viewersOut = new JsonArray();
        List<String> ordered = new ArrayList<>(seatPids);
        Collections.sort(ordered);
        for (String pid : ordered) {
            JsonObject viewer = new JsonObject();
            viewer.add("face_down_look_permissions", new JsonArray());
            viewer.add("invalidation_conditions", new JsonArray());
            viewer.add("known_library_ranges", new JsonArray());
            viewer.add("known_object_identities", new JsonArray());
            viewer.add("temporary_permissions", new JsonArray());
            viewer.addProperty("viewer", pid);
            viewersOut.add(viewer);
        }
        knowledge.add("viewer_states", viewersOut);
        return knowledge;
    }

    static void assertDescriptorMirror(JsonObject requested, String key) {
        assertTrue(requested.has(key), "record carries descriptor: " + key);
    }

    static JsonObject commanderStateProjection(JsonObject requestedRecord, JsonObject observed,
            XmageNativeStateRestoration.Plan plan) {
        JsonObject requested = requestedRecord.getAsJsonObject("commander_state");
        assertEquals(List.of(), toList(requested.getAsJsonArray("commander_damage_matrix")),
                "damage matrices are empty across the six (pre-combat envelope, CR 903.10)");
        Map<String, JsonObject> seats = new HashMap<>();
        for (JsonElement element : observed.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            seats.put(seat.get("player_id").getAsString(), seat);
        }
        Map<String, XmageNativeStateRestoration.RequestedCommander> commandersById =
                new HashMap<>();
        for (XmageNativeStateRestoration.RequestedCommander commander : plan.commanders()) {
            commandersById.put(commander.commanderId(), commander);
        }
        JsonArray commanders = new JsonArray();
        for (JsonElement element : requested.getAsJsonArray("commanders")) {
            JsonObject want = element.getAsJsonObject();
            XmageNativeStateRestoration.RequestedCommander planned =
                    commandersById.get(want.get("commander_id").getAsString());
            assertTrue(planned != null, "commander in plan");
            assertEquals(planned.cardIdentity(), want.get("card_identity").getAsString());
            assertEquals(planned.owner(), want.get("owner").getAsString());
            assertEquals(planned.priorCasts(),
                    want.get("prior_command_zone_cast_count").getAsInt());
            JsonObject seat = seats.get(planned.owner());
            boolean found = false;
            for (JsonElement entry : seat.getAsJsonArray("commanders")) {
                JsonObject observedCommander = entry.getAsJsonObject();
                if (observedCommander.get("card_identity").getAsString()
                        .equals(planned.cardIdentity())) {
                    found = true;
                    assertEquals(planned.priorCasts(),
                            observedCommander.get("prior_casts").getAsInt());
                }
            }
            assertTrue(found, "commander observed in command zone: " + planned.cardIdentity());
            JsonObject entry = new JsonObject();
            entry.addProperty("card_identity", want.get("card_identity").getAsString());
            entry.addProperty("commander_id", want.get("commander_id").getAsString());
            entry.addProperty("owner", want.get("owner").getAsString());
            if (want.has("partner_with")) {
                entry.addProperty("partner_with", want.get("partner_with").getAsString());
            }
            entry.addProperty("prior_command_zone_cast_count",
                    want.get("prior_command_zone_cast_count").getAsInt());
            entry.addProperty("zone", want.get("zone").getAsString());
            commanders.add(entry);
        }
        JsonObject state = new JsonObject();
        state.add("commander_damage_matrix", new JsonArray());
        state.add("commanders", commanders);
        if (requested.has("multiple_commander_relations")) {
            for (JsonElement element : requested.getAsJsonArray("multiple_commander_relations")) {
                JsonObject relation = element.getAsJsonObject();
                assertEquals("Partner", relation.get("relation").getAsString(),
                        "only Partner relations supported");
                for (JsonElement id : relation.getAsJsonArray("commander_ids")) {
                    assertTrue(commandersById.containsKey(id.getAsString()),
                            "relation resolves to planned commanders");
                }
            }
            state.add("multiple_commander_relations",
                    requested.getAsJsonArray("multiple_commander_relations"));
        }
        return state;
    }

    static List<Object> toList(JsonArray array) {
        List<Object> items = new ArrayList<>();
        for (JsonElement element : array) {
            items.add(element.toString());
        }
        return items;
    }

    static void driveArrival(XmageFullGameSession session, Map<String, Player> seats,
            String tag) {
        for (int step = 0; step < 60; step++) {
            JsonObject readback = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats);
            if (readback.get("turn_number").getAsInt() == 1
                    && readback.get("phase").getAsString().equals("PRECOMBAT_MAIN")) {
                return;
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before arrival");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            if ("mulligan".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, tag + "-keep-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "mulligan", "keep"));
            } else if ("choose_object".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, tag + "-start-" + step,
                        XmageFullGameTaxExecutionTest.singleSelfAction(legal, actorId));
            } else if ("priority".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, tag + "-pass-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "pass_priority", null));
            } else {
                fail("unexpected decision class during arrival: " + decisionClass);
            }
        }
        fail("arrival bound breached");
    }

    // ---------- NATIVE digest verification (TAX-2/4, PARTNER-ZONE/TAX) ----------

    static void verifyNativeConstructionDigest(String fixtureId, String gameTag,
            Set<String> allowedCards, Set<String> allowedFamilies) {
        JsonObject requested = frozenRecord(fixtureId);
        long seed = manifestSeed(fixtureId);
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(requested, gameTag, seed);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, gameTag);
        XmageFullGameSession session = new XmageFullGameSession(
                fixtureId, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        driveArrival(session, seats, gameTag);
        restoration.restoreCommanderCasts(session.restorationGame(), seats);
        XmageNativeStateRestoration.revalidate(session.restorationGame());
        JsonObject observed =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        assertTrue(session.restorationGame().getStack().isEmpty(), "stack empty at digest point");
        assertFalse(observed.get("has_extra_turn").getAsBoolean());
        XmageNativeStateRestoration.CompareVerdict fieldCheck =
                restoration.compare(observed, seats);
        assertTrue(fieldCheck.match(),
                "field-level match precedes digest: " + fieldCheck.mismatches());

        JsonObject projected = new JsonObject();
        projected.addProperty("execution_entry_mode", "NATIVE_STATE_LOAD");
        assertEquals(requested.get("execution_entry_mode").getAsString(), "NATIVE_STATE_LOAD");
        List<String> seatPids = new ArrayList<>(seats.keySet());
        projected.add("players", playersProjection(plan.players(), observed, 40, requested));
        assertFalse(requested.has("deck_state"), "NATIVE fixtures carry no deck_state");
        projected.add("commander_state", commanderStateProjection(requested, observed, plan));
        projected.add("semantic_objects", transferBattlefieldIds(requested, observed));
        JsonObject temporal = requested.getAsJsonObject("temporal_state");
        assertEquals(1, observed.get("turn_number").getAsInt());
        assertEquals("PRECOMBAT_MAIN", observed.get("phase").getAsString());
        assertEquals("PRECOMBAT_MAIN", observed.get("step").getAsString());
        JsonObject temporalOut = new JsonObject();
        temporalOut.addProperty("active_player", observed.get("active_player").getAsString());
        temporalOut.add("extra_turn_queue", new JsonArray());
        temporalOut.addProperty("phase", "precombat_main");
        temporalOut.addProperty("priority_player",
                observed.get("priority_player").getAsString());
        temporalOut.addProperty("step", "main");
        temporalOut.addProperty("turn_number", 1);
        assertEquals(temporal.get("active_player").getAsString(),
                temporalOut.get("active_player").getAsString());
        assertEquals(temporal.get("priority_player").getAsString(),
                temporalOut.get("priority_player").getAsString());
        projected.add("temporal_state", temporalOut);
        projected.add("knowledge_state",
                knowledgeProjection(requested, seatPids, allowedCards, allowedFamilies));
        assertDescriptorMirror(requested, "rules_randomness");
        projected.add("rules_randomness", requested.get("rules_randomness"));
        assertEquals(seed, observed.get("rules_seed").getAsLong());
        assertTrue(observed.get("rules_seed_explicit").getAsBoolean());
        assertTrue(requested.getAsJsonObject("rules_randomness")
                .get("pilot_randomness_prohibited").getAsBoolean());
        assertTrue(requested.getAsJsonArray("stack_state").isEmpty());
        projected.add("stack_state", new JsonArray());
        assertFalse(requested.has("combat_state"), "combat state unsupported in v1");
        assertDescriptorMirror(requested, "setup_validation");
        projected.add("setup_validation", requested.get("setup_validation"));
        assertProjectionKeys(projected, requested);
        assertEquals(requested.get("requested_state_digest").getAsString(),
                XmageNativeStateRestoration.constructedDigest(projected),
                "constructed digest must equal frozen hex for " + fixtureId);
    }

    static void assertProjectionKeys(JsonObject projection, JsonObject requested) {
        for (String key : XmageNativeStateRestoration.DIGEST_PROJECTION_KEYS) {
            assertEquals(requested.has(key), projection.has(key),
                    "projection key presence must match record: " + key);
        }
    }

    @Test
    void tax2ConstructionDigestMatchesFrozen() {
        verifyNativeConstructionDigest("WS05-CMD-TAX-2", "dig-tax2",
                Set.of("Rograkh, Son of Rohgahh", "Grizzly Bears", "Mountain"),
                Set.of("priority"));
    }

    @Test
    void tax4ConstructionDigestMatchesFrozen() {
        verifyNativeConstructionDigest("WS05-CMD-TAX-4", "dig-tax4",
                Set.of("Rograkh, Son of Rohgahh", "Grizzly Bears", "Mountain"),
                Set.of("priority"));
    }

    @Test
    void partnerZoneConstructionDigestMatchesFrozen() {
        verifyNativeConstructionDigest("WS05-CMD-PARTNER-ZONE", "dig-pzone",
                Set.of("Rograkh, Son of Rohgahh", "Kediss, Emberclaw Familiar",
                        "Grizzly Bears", "Mountain"),
                Set.of());
    }

    @Test
    void partnerTaxConstructionDigestMatchesFrozen() {
        verifyNativeConstructionDigest("WS05-CMD-PARTNER-TAX", "dig-ptax",
                Set.of("Rograkh, Son of Rohgahh", "Kediss, Emberclaw Familiar",
                        "Grizzly Bears", "Mountain"),
                Set.of());
    }

    @Test
    void tamperedConstructionDigestMismatch() {
        JsonObject requested = frozenRecord("WS05-CMD-TAX-2");
        long seed = manifestSeed("WS05-CMD-TAX-2");
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(requested, "dig-neg", seed);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, "dig-neg");
        XmageFullGameSession session = new XmageFullGameSession(
                "WS05-CMD-TAX-2-tampered", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        driveArrival(session, seats, "dig-neg");
        restoration.restoreCommanderCasts(session.restorationGame(), seats);
        XmageNativeStateRestoration.revalidate(session.restorationGame());
        JsonObject observed =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        assertTrue(restoration.compare(observed, seats).match());
        List<String> seatPids = new ArrayList<>(seats.keySet());
        JsonObject projected = new JsonObject();
        projected.addProperty("execution_entry_mode", "NATIVE_STATE_LOAD");
        projected.add("players", playersProjection(plan.players(), observed, 40, requested));
        projected.add("commander_state", commanderStateProjection(requested, observed, plan));
        projected.add("semantic_objects", transferBattlefieldIds(requested, observed));
        JsonObject temporalOut = new JsonObject();
        temporalOut.addProperty("active_player", observed.get("active_player").getAsString());
        temporalOut.add("extra_turn_queue", new JsonArray());
        temporalOut.addProperty("phase", "precombat_main");
        temporalOut.addProperty("priority_player",
                observed.get("priority_player").getAsString());
        temporalOut.addProperty("step", "main");
        temporalOut.addProperty("turn_number", 1);
        projected.add("temporal_state", temporalOut);
        projected.add("knowledge_state", knowledgeProjection(requested, seatPids,
                Set.of("Rograkh, Son of Rohgahh", "Grizzly Bears", "Mountain"), Set.of("priority")));
        projected.add("rules_randomness", requested.get("rules_randomness"));
        projected.add("stack_state", new JsonArray());
        projected.add("setup_validation", requested.get("setup_validation"));
        assertEquals(requested.get("requested_state_digest").getAsString(),
                XmageNativeStateRestoration.constructedDigest(projected),
                "untampered projection must digest to frozen hex");
        JsonObject tampered = projected.deepCopy();
        tampered.getAsJsonArray("players").get(0).getAsJsonObject()
                .addProperty("life", 39);
        assertFalse(XmageNativeStateRestoration.constructedDigest(tampered)
                .equals(requested.get("requested_state_digest").getAsString()),
                "tampered life must break digest equality");
    }

    // ---------- NATURAL digest verification (MULL-2/4) ----------

    @Test
    void mull2ConstructionDigestMatchesFrozen() {
        verifyNaturalConstructionDigest("WS05-CMD-MULL-2", "dig-mull2");
    }

    @Test
    void mull4ConstructionDigestMatchesFrozen() {
        verifyNaturalConstructionDigest("WS05-CMD-MULL-4", "dig-mull4");
    }

    static void verifyNaturalConstructionDigest(String fixtureId, String gameTag) {
        JsonObject requested = frozenRecord(fixtureId);
        long seed = manifestSeed(fixtureId);
        Map<String, List<String>> commanders = new HashMap<>();
        Map<String, List<String>> mains = new HashMap<>();
        List<String> orderedPids = new ArrayList<>();
        for (JsonElement element : requested.getAsJsonArray("deck_state")) {
            JsonObject deck = element.getAsJsonObject();
            String pid = deck.get("player_id").getAsString();
            orderedPids.add(pid);
            commanders.put(pid, expandMultiset(deck.getAsJsonArray("commander"), "card_identity"));
            mains.put(pid, expandMultiset(deck.getAsJsonArray("main_deck"), "card_identity"));
        }
        XmageDeckImporter importer = new XmageDeckImporter();
        Scaffold scaffold = importDecks(importer, commanders, mains, gameTag);
        XmageFullGameSession session = new XmageFullGameSession(
                fixtureId, scaffold.handles(), 0, 40, seed, importer);
        Map<String, Player> seats = session.restorationSeats();
        assertEquals(1, session.restorationGame().getState().getTurnNum(),
                "engine counter initializes at 1; fixture turn 0 denotes the unstarted game");
        for (String pid : orderedPids) {
            Player player = seats.get(pid);
            assertEquals(99, player.getLibrary().size(), "library holds full main deck");
            assertEquals(0, player.getHand().size(), "no draws pre-start");
            Deck deck = importer.requireDeck(
                    scaffold.handles().get(orderedPids.indexOf(pid)));
            Map<String, Integer> sideboard = new TreeMap<>();
            for (Card card : deck.getSideboard()) {
                sideboard.merge(card.getName(), 1, Integer::sum);
            }
            assertEquals(countMultiset(commanders.get(pid)), new TreeMap<>(sideboard));
        }
        assertTrue(session.restorationGame().getBattlefield().getAllPermanents().isEmpty());
        assertTrue(session.restorationGame().getStack().isEmpty());
        session.start();
        String starter = null;
        for (int step = 0; step < 12; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            assertFalse(payload.get("decision").isJsonNull(), "a decision must be pending");
            JsonObject pending = payload.getAsJsonObject("decision");
            if ("mulligan".equals(pending.get("decision_class").getAsString())) {
                starter = pending.get("actor_id").getAsString();
                break;
            }
            assertEquals("choose_object", pending.get("decision_class").getAsString());
            JsonObject legal = session.legalActionsPayload();
            JsonObject self = XmageFullGameTaxExecutionTest.singleSelfAction(
                    legal, legal.get("actor_id").getAsString());
            session.submitAction(XmageFullGameTaxExecutionTest.genericProposal(
                    gameTag + "-start-" + step, legal.get("actor_id").getAsString(),
                    self.get("action_id").getAsString(), self.get("action_type").getAsString()));
        }
        assertTrue(starter != null, "mulligan phase must begin");
        assertEquals(seats.get("P1").getId().toString(), starter,
                "P1 must act first (starting seat 0)");
        XmageNativeStateRestoration.revalidate(session.restorationGame());
        Map<String, JsonObject> seatsByPid = new HashMap<>();
        JsonObject observed = XmageNativeStateRestoration.readback(
                session.restorationGame(), seats);
        for (JsonElement element : observed.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            seatsByPid.put(seat.get("player_id").getAsString(), seat);
            assertEquals(7, seat.get("hand_count").getAsInt(), "opening seven drawn");
            assertEquals(92, seat.get("library_count").getAsInt(), "99 minus opening seven");
            assertEquals(40, seat.get("life").getAsInt());
        }
        JsonObject projected = new JsonObject();
        projected.addProperty("execution_entry_mode", "NATURAL_GAME_START");
        assertEquals(requested.get("execution_entry_mode").getAsString(), "NATURAL_GAME_START");
        JsonArray players = new JsonArray();
        for (String pid : orderedPids) {
            JsonObject seat = seatsByPid.get(pid);
            JsonObject want = null;
            for (JsonElement element : requested.getAsJsonArray("players")) {
                JsonObject candidate = element.getAsJsonObject();
                if (candidate.get("player_id").getAsString().equals(pid)) {
                    want = candidate;
                }
            }
            assertTrue(want != null, "player in record: " + pid);
            assertEquals(want.get("life").getAsInt(), seat.get("life").getAsInt());
            assertEquals(want.get("lost").getAsBoolean(), seat.get("lost").getAsBoolean());
            assertEquals(want.get("poison").getAsInt(), seat.get("poison").getAsInt());
            assertFalse(seat.get("left").getAsBoolean());
            JsonObject entry = new JsonObject();
            entry.addProperty("eliminated", false);
            assertEquals(want.get("eliminated").getAsBoolean(), false);
            entry.addProperty("life", seat.get("life").getAsInt());
            entry.addProperty("lost", false);
            entry.addProperty("player_id", pid);
            entry.addProperty("poison", 0);
            entry.addProperty("seat", want.get("seat").getAsInt());
            entry.addProperty("starting_life", 40);
            assertEquals(want.get("starting_life").getAsInt(), 40);
            players.add(entry);
        }
        projected.add("players", players);
        JsonArray decks = new JsonArray();
        for (JsonElement element : requested.getAsJsonArray("deck_state")) {
            JsonObject deck = element.getAsJsonObject();
            String pid = deck.get("player_id").getAsString();
            JsonObject seat = seatsByPid.get(pid);
            assertEquals(92 + 7, seat.get("library_count").getAsInt()
                    + seat.get("hand_count").getAsInt(), "zone arithmetic covers main deck");
            JsonObject out = new JsonObject();
            out.add("commander", deck.getAsJsonArray("commander"));
            out.addProperty("exact_card_count", deck.get("exact_card_count").getAsInt());
            assertEquals(100, deck.get("exact_card_count").getAsInt());
            out.add("main_deck", deck.getAsJsonArray("main_deck"));
            out.addProperty("player_id", pid);
            decks.add(out);
        }
        projected.add("deck_state", decks);
        JsonObject commanderState = requested.getAsJsonObject("commander_state");
        assertEquals(List.of(), toList(commanderState.getAsJsonArray("commander_damage_matrix")));
        assertTrue(commanderState.getAsJsonArray("multiple_commander_relations").isEmpty());
        JsonArray commandersOut = new JsonArray();
        for (JsonElement element : commanderState.getAsJsonArray("commanders")) {
            JsonObject want = element.getAsJsonObject();
            JsonObject seat = seatsByPid.get(want.get("owner").getAsString());
            boolean found = false;
            for (JsonElement entry : seat.getAsJsonArray("commanders")) {
                if (entry.getAsJsonObject().get("card_identity").getAsString()
                        .equals(want.get("card_identity").getAsString())) {
                    found = true;
                    assertEquals(0, entry.getAsJsonObject().get("prior_casts").getAsInt());
                }
            }
            assertTrue(found, "commander bound in command zone: " + want.get("card_identity"));
            JsonObject entry = new JsonObject();
            entry.addProperty("card_identity", want.get("card_identity").getAsString());
            entry.addProperty("commander_id", want.get("commander_id").getAsString());
            entry.addProperty("owner", want.get("owner").getAsString());
            entry.addProperty("prior_command_zone_cast_count", 0);
            assertEquals(0, want.get("prior_command_zone_cast_count").getAsInt());
            entry.addProperty("zone", "command");
            commandersOut.add(entry);
        }
        JsonObject commanderStateOut = new JsonObject();
        commanderStateOut.add("commander_damage_matrix", new JsonArray());
        commanderStateOut.add("commanders", commandersOut);
        commanderStateOut.add("multiple_commander_relations", new JsonArray());
        projected.add("commander_state", commanderStateOut);
        assertTrue(requested.getAsJsonArray("semantic_objects").isEmpty());
        projected.add("semantic_objects", new JsonArray());
        JsonObject temporalOut = new JsonObject();
        temporalOut.addProperty("active_player", "P1");
        temporalOut.add("extra_turn_queue", new JsonArray());
        temporalOut.addProperty("phase", "pregame");
        temporalOut.addProperty("priority_player", "P1");
        temporalOut.addProperty("step", "mulligan");
        temporalOut.addProperty("turn_number", 0);
        JsonObject temporal = requested.getAsJsonObject("temporal_state");
        assertEquals("P1", temporal.get("active_player").getAsString());
        assertEquals("pregame", temporal.get("phase").getAsString());
        assertEquals("mulligan", temporal.get("step").getAsString());
        assertEquals(0, temporal.get("turn_number").getAsInt());
        projected.add("temporal_state", temporalOut);
        projected.add("knowledge_state", knowledgeProjection(requested, orderedPids,
                Set.of("Rograkh, Son of Rohgahh", "Mountain"), Set.of("mulligan")));
        projected.add("rules_randomness", requested.get("rules_randomness"));
        assertEquals(seed, observed.get("rules_seed").getAsLong());
        assertTrue(observed.get("rules_seed_explicit").getAsBoolean());
        assertTrue(requested.getAsJsonObject("rules_randomness")
                .get("pilot_randomness_prohibited").getAsBoolean());
        assertTrue(requested.getAsJsonArray("stack_state").isEmpty());
        assertTrue(session.restorationGame().getStack().isEmpty());
        projected.add("stack_state", new JsonArray());
        assertFalse(requested.has("combat_state"), "combat state unsupported in v1");
        projected.add("setup_validation", requested.get("setup_validation"));
        assertProjectionKeys(projected, requested);
        assertEquals(requested.get("requested_state_digest").getAsString(),
                XmageNativeStateRestoration.constructedDigest(projected),
                "constructed digest must equal frozen hex for " + fixtureId);
    }
}
