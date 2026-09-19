package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.cards.Card;
import mage.game.CommanderFreeForAll;
import mage.game.permanent.Permanent;
import mage.game.stack.StackObject;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * WS224 hidden-information NAME canary (F-HIDE-02 / S7 successor).
 *
 * <p>Supplements — never replaces — the UUID oracle in
 * {@link XmageFullGameHiddenInformationTest}. A pure card-name leak carries no
 * engine object UUID and would evade a UUID-only scan, so this test builds the
 * second independent negative dimension from unmistakable per-frame
 * hidden-EXCLUSIVE card names: opponent hand/library names that appear in NO
 * public zone, NOT in the actor's own hand, and NOT inside a live D2 grant
 * window. Test-only reflection peeking only; never pilot input; neutral
 * answers only; no Rules outcome altered; no fake production cards.</p>
 *
 * <p>Each of 2P/3P/4P/5P runs a live game and asserts, every frame, that no
 * hidden-exclusive name (AND no hidden UUID) appears in the actor's
 * observation JSON, legal-action labels/metadata, target projection, pending
 * decision, legal-actions payload, transcript slice, or whole-payload
 * serialization. Attacker-inducible error paths (wrong actor, stale decision,
 * unknown/illegal action) must reject without advancing and must not echo any
 * opponent-private name. Grant windows stay bounded. Every ordered
 * actor-&gt;other pair must earn at least one non-vacuous canary pass.</p>
 */
class XmageFullGameNameCanaryTest {

    @Test
    void nameCanaryTwoPlayers() throws Exception {
        runNameCanary(2);
    }

    @Test
    void nameCanaryThreePlayers() throws Exception {
        runNameCanary(3);
    }

    @Test
    void nameCanaryFourPlayers() throws Exception {
        runNameCanary(4);
    }

    @Test
    void nameCanaryFivePlayers() throws Exception {
        runNameCanary(5);
    }

    private static void runNameCanary(int playerCount) throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, loadRogShaiRuntimeDeck(), playerCount);
        XmageFullGameSession session = new XmageFullGameSession(
                "ws224-name-canary-" + playerCount + "p", handles, 0, 40, 10704L, importer
        );
        session.start();

        int scanned = 0;
        int oracleHands = 0;
        int canaryFrames = 0;
        int grantFrames = 0;
        Set<String> coveredPairs = new HashSet<>();
        String firstDecisionId = null;

        for (int step = 0; step < 120 && scanned < 60; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String actorId = pending.get("actor_id").getAsString();
            String decisionClass = pending.get("decision_class").getAsString();
            long offset = pending.get("decision_offset").getAsLong();
            if (firstDecisionId == null) {
                firstDecisionId = pending.get("decision_id").getAsString();
            }
            JsonObject pilotState = pending.getAsJsonObject("pilot_state");
            JsonObject legal = session.legalActionsPayload();

            int actorSeat = seatOf(pilotState, actorId);

            // Structural negative (same discipline as the UUID oracle).
            boolean actorSawOwnHand = false;
            for (JsonElement element : pilotState.getAsJsonArray("players")) {
                JsonObject entry = element.getAsJsonObject();
                boolean isActor = entry.get("is_actor").getAsBoolean();
                if (isActor) {
                    assertEquals(actorId, entry.get("player_id").getAsString());
                    assertTrue(entry.has("hand"), "actor must see own hand");
                    assertTrue(entry.has("mana_pool"), "actor must see own mana");
                    actorSawOwnHand = true;
                } else {
                    assertTrue(!entry.has("hand"),
                            "opponent hand array must be absent at offset " + offset);
                    assertTrue(!entry.has("mana_pool"),
                            "opponent mana pool must be absent at offset " + offset);
                }
                JsonArray granted = entry.has("granted_library")
                        && entry.get("granted_library").isJsonArray()
                        ? entry.getAsJsonArray("granted_library") : new JsonArray();
                if (granted.size() > 0) {
                    grantFrames++;
                    assertTrue("choose_object".equals(decisionClass),
                            "library grant outside library-zone decision at offset "
                                    + offset + " class=" + decisionClass);
                }
            }
            assertTrue(actorSawOwnHand);

            // Oracle A: hidden UUIDs AND hidden-exclusive names absent from
            // every pilot-visible serialization of this frame.
            Set<String> hiddenIds = hiddenCardIds(session, actorId);
            Map<String, Set<String>> hiddenNamesByOwner = hiddenCardNamesByOwner(session, actorId);
            Set<String> publicNames = publicNames(session, actorId, pilotState);
            Set<String> canary = new HashSet<>();
            Map<String, Set<String>> canaryByOwner = new HashMap<>();
            for (Map.Entry<String, Set<String>> entry : hiddenNamesByOwner.entrySet()) {
                Set<String> exclusive = new HashSet<>(entry.getValue());
                exclusive.removeAll(publicNames);
                if (!exclusive.isEmpty()) {
                    canary.addAll(exclusive);
                    canaryByOwner.put(entry.getKey(), exclusive);
                }
            }

            String pilotSerialized = pilotState.toString();
            String legalSerialized = legal.toString();
            String pendingSerialized = pending.toString();
            // Transcript causality: only the LATEST event (this decision's own
            // request) belongs to this frame. The cumulative transcript is
            // Lab-owned privileged history mixing every actor's entitled
            // labels (each request's options were engine-selected for THAT
            // actor); scanning history against the current actor's hidden set
            // would flag other actors' entitled choices as leaks. History is
            // classified privileged (see CANARY_CONTRACT historical rule).
            String latestEvent = latestTranscriptEvent(session);

            if (!hiddenIds.isEmpty()) {
                oracleHands++;
                for (String hidden : hiddenIds) {
                    assertTrue(!pilotSerialized.contains(hidden),
                            "hidden UUID in observation at offset " + offset);
                    assertTrue(!legalSerialized.contains(hidden),
                            "hidden UUID in legal actions at offset " + offset);
                    assertTrue(!latestEvent.contains(hidden),
                            "hidden UUID in current transcript event at offset " + offset);
                }
            }
            if (!canary.isEmpty()) {
                canaryFrames++;
                for (String name : canary) {
                    assertTrue(!pilotSerialized.contains(name),
                            "hidden-exclusive name '" + name + "' in observation at offset "
                                    + offset + " class=" + decisionClass);
                    assertTrue(!legalSerialized.contains(name),
                            "hidden-exclusive name '" + name + "' in legal actions at offset "
                                    + offset + " class=" + decisionClass);
                    assertTrue(!pendingSerialized.contains(name),
                            "hidden-exclusive name '" + name + "' in pending decision at offset "
                                    + offset + " class=" + decisionClass);
                    assertTrue(!latestEvent.contains(name),
                            "hidden-exclusive name '" + name + "' in current transcript event "
                                    + "at offset " + offset + " class=" + decisionClass
                                    + " event=" + snippet(latestEvent));
                }
                for (String ownerId : canaryByOwner.keySet()) {
                    coveredPairs.add(actorSeat + "->" + seatOf(pilotState, ownerId));
                }
            }

            answerNeutrally(session, pending);
            // Frame-N completions: every event appended by this submit that
            // closes frame N (decision_accepted, controller_failure) is
            // scanned against frame N's actor-relative canary set. The next
            // frame's request event (if already appended) belongs to the next
            // actor and is scanned at the next iteration.
            scanFrameCompletions(session, transcriptSize(session), actorSeat, canary, offset);
            scanned++;
        }

        assertTrue(scanned >= 30,
                "must scan a substantive decision run, scanned=" + scanned);
        assertTrue(oracleHands >= 30,
                "UUID oracle must cover the run, covered=" + oracleHands);
        assertTrue(canaryFrames >= 15,
                "name canary must have signal, canaryFrames=" + canaryFrames
                        + " scanned=" + scanned);
        int expectedPairs = playerCount * (playerCount - 1);
        assertEquals(expectedPairs, coveredPairs.size(),
                "every ordered actor->other pair needs a non-vacuous canary pass, covered="
                        + coveredPairs);

        // Attacker-inducible error paths: must reject without advancing and
        // must not echo any opponent-private name (full hidden set, not just
        // the exclusive subset — errors have no entitlement at all).
        probeErrorPaths(session, playerCount);

        System.out.printf(
                "WS224_CANARY players=%d scanned=%d uuidFrames=%d canaryFrames=%d pairs=%d/%d grantFrames=%d%n",
                playerCount, scanned, oracleHands, canaryFrames,
                coveredPairs.size(), playerCount * (playerCount - 1), grantFrames);
    }

    private static void probeErrorPaths(XmageFullGameSession session, int playerCount)
            throws Exception {
        JsonObject payload = session.pendingDecisionPayload();
        if (payload.get("decision").isJsonNull()) {
            fail("no live decision left for error probes");
        }
        JsonObject pending = payload.getAsJsonObject("decision");
        String actorId = pending.get("actor_id").getAsString();
        String liveDecisionId = pending.get("decision_id").getAsString();
        Set<String> allHiddenNames = new HashSet<>();
        for (Set<String> names : hiddenCardNamesByOwner(session, actorId).values()) {
            allHiddenNames.addAll(names);
        }
        assertTrue(!allHiddenNames.isEmpty(), "error probes need hidden signal");

        // Wrong actor: valid shape, swapped principal.
        String otherId = otherPlayerId(session, actorId);
        JsonObject wrongActor = new JsonObject();
        wrongActor.addProperty("decision_id", liveDecisionId);
        wrongActor.addProperty("actor_id", otherId);
        wrongActor.add("selected_option_ids", new JsonArray());
        wrongActor.add("ordering", new JsonArray());
        String wrongMessage = expectRejection(session, wrongActor);
        assertTrue(wrongMessage.contains("wrong actor"),
                "wrong-actor probe must identify the cause, got: " + wrongMessage);
        assertNoHiddenNames(wrongMessage, allHiddenNames, "wrong-actor error");

        // Stale decision: replay a superseded decision id for this actor.
        JsonObject stale = new JsonObject();
        stale.addProperty("decision_id", "ws224-stale-decision-id");
        stale.addProperty("actor_id", actorId);
        stale.add("selected_option_ids", new JsonArray());
        stale.add("ordering", new JsonArray());
        String staleMessage = expectRejection(session, stale);
        assertTrue(staleMessage.contains("STALE_DECISION"),
                "stale probe must be stale, got: " + staleMessage);
        assertNoHiddenNames(staleMessage, allHiddenNames, "stale-decision error");

        // Unknown/illegal action: ghost option the engine never offered.
        JsonObject ghost = new JsonObject();
        ghost.addProperty("decision_id", liveDecisionId);
        ghost.addProperty("actor_id", actorId);
        JsonArray ghostSelected = new JsonArray();
        ghostSelected.add("ghost-option-ws224");
        ghost.add("selected_option_ids", ghostSelected);
        ghost.add("ordering", new JsonArray());
        String ghostMessage = expectRejection(session, ghost);
        assertTrue(ghostMessage.contains("ILLEGAL_ACTION") || ghostMessage.contains("PILOT_RESPONSE_INVALID"),
                "ghost probe must be rejected as illegal, got: " + ghostMessage);
        assertNoHiddenNames(ghostMessage, allHiddenNames, "unknown-action error");

        // Illegal target as raw UUID: must echo only the attacker-supplied id.
        JsonObject ghostUuid = new JsonObject();
        ghostUuid.addProperty("decision_id", liveDecisionId);
        ghostUuid.addProperty("actor_id", actorId);
        JsonArray ghostUuidSelected = new JsonArray();
        ghostUuidSelected.add("00000000-0000-0000-0000-000000000000");
        ghostUuid.add("selected_option_ids", ghostUuidSelected);
        ghostUuid.add("ordering", new JsonArray());
        String ghostUuidMessage = expectRejection(session, ghostUuid);
        assertNoHiddenNames(ghostUuidMessage, allHiddenNames, "illegal-target error");

        // None of the probes may have advanced the game.
        JsonObject after = session.pendingDecisionPayload();
        assertTrue(!after.get("decision").isJsonNull(), "probes must not terminate the game");
        assertEquals(liveDecisionId,
                after.getAsJsonObject("decision").get("decision_id").getAsString(),
                "rejected probes must not advance the decision");
    }

    private static String expectRejection(XmageFullGameSession session, JsonObject response) {
        try {
            session.submit(response);
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            return exc.getMessage() == null ? "" : exc.getMessage();
        }
        fail("attacker probe must be rejected: " + response);
        throw new IllegalStateException("unreachable");
    }

    private static void assertNoHiddenNames(String text, Set<String> hidden, String surface) {
        for (String name : hidden) {
            assertTrue(!text.contains(name),
                    surface + " echoes opponent-private name '" + name + "'");
        }
    }

    private static String otherPlayerId(XmageFullGameSession session, String actorId)
            throws Exception {
        CommanderFreeForAll game = field(session, "game", CommanderFreeForAll.class);
        for (Player player : game.getPlayers().values()) {
            if (!player.getId().toString().equals(actorId)) {
                return player.getId().toString();
            }
        }
        throw new IllegalStateException("no other principal for wrong-actor probe");
    }

    private static Set<String> hiddenCardIds(XmageFullGameSession session, String actorId)
            throws Exception {
        CommanderFreeForAll game = field(session, "game", CommanderFreeForAll.class);
        Set<String> hidden = new HashSet<>();
        for (Player player : game.getPlayers().values()) {
            if (player.getId().toString().equals(actorId)) {
                continue;
            }
            for (Card card : player.getHand().getCards(game)) {
                hidden.add(card.getId().toString());
            }
            for (Card card : player.getLibrary().getCards(game)) {
                hidden.add(card.getId().toString());
            }
        }
        return hidden;
    }

    private static Map<String, Set<String>> hiddenCardNamesByOwner(
            XmageFullGameSession session, String actorId) throws Exception {
        CommanderFreeForAll game = field(session, "game", CommanderFreeForAll.class);
        Map<String, Set<String>> byOwner = new HashMap<>();
        for (Player player : game.getPlayers().values()) {
            if (player.getId().toString().equals(actorId)) {
                continue;
            }
            Set<String> names = new HashSet<>();
            for (Card card : player.getHand().getCards(game)) {
                names.add(card.getName());
            }
            for (Card card : player.getLibrary().getCards(game)) {
                names.add(card.getName());
            }
            byOwner.put(player.getId().toString(), names);
        }
        return byOwner;
    }

    private static Set<String> publicNames(
            XmageFullGameSession session, String actorId, JsonObject pilotState) throws Exception {
        CommanderFreeForAll game = field(session, "game", CommanderFreeForAll.class);
        Set<String> names = new HashSet<>();
        for (Player player : game.getPlayers().values()) {
            for (Card card : player.getGraveyard().getCards(game)) {
                names.add(card.getName());
            }
            if (player.getId().toString().equals(actorId)) {
                for (Card card : player.getHand().getCards(game)) {
                    names.add(card.getName());
                }
            }
        }
        for (Permanent permanent : game.getBattlefield().getAllPermanents()) {
            names.add(permanent.getName());
        }
        for (StackObject stackObject : game.getStack()) {
            names.add(stackObject.getName());
        }
        // Command-zone contents are public (commander rows).
        for (JsonElement element : pilotState.getAsJsonArray("players")) {
            JsonObject entry = element.getAsJsonObject();
            if (entry.has("command") && entry.get("command").isJsonArray()) {
                for (JsonElement cmd : entry.getAsJsonArray("command")) {
                    JsonObject row = cmd.getAsJsonObject();
                    if (row.has("name") && !row.get("name").isJsonNull()) {
                        names.add(row.get("name").getAsString());
                    }
                }
            }
            if (entry.has("graveyard") && entry.get("graveyard").isJsonArray()) {
                for (JsonElement grave : entry.getAsJsonArray("graveyard")) {
                    JsonObject row = grave.getAsJsonObject();
                    if (row.has("name") && !row.get("name").isJsonNull()) {
                        names.add(row.get("name").getAsString());
                    }
                }
            }
            // A live D2 grant window entitles THIS frame's viewer only.
            if (entry.has("granted_library") && entry.get("granted_library").isJsonArray()) {
                for (JsonElement granted : entry.getAsJsonArray("granted_library")) {
                    JsonObject row = granted.getAsJsonObject();
                    if (row.has("name") && !row.get("name").isJsonNull()) {
                        names.add(row.get("name").getAsString());
                    }
                }
            }
        }
        return names;
    }

    private static int seatOf(JsonObject pilotState, String playerId) {
        for (JsonElement element : pilotState.getAsJsonArray("players")) {
            JsonObject entry = element.getAsJsonObject();
            if (entry.has("player_id") && playerId.equals(entry.get("player_id").getAsString())) {
                return entry.get("seat").getAsInt();
            }
        }
        return -1;
    }

    private static int transcriptSize(XmageFullGameSession session) throws Exception {
        XmageFullGameDecisionController controller =
                field(session, "controller", XmageFullGameDecisionController.class);
        return controller.transcript().size();
    }

    private static void scanFrameCompletions(
            XmageFullGameSession session, int sizeBefore, int actorSeat,
            Set<String> canary, long offset) throws Exception {
        XmageFullGameDecisionController controller =
                field(session, "controller", XmageFullGameDecisionController.class);
        JsonArray transcript = controller.transcript();
        for (int index = sizeBefore; index < transcript.size(); index++) {
            JsonObject event = transcript.get(index).getAsJsonObject();
            String kind = event.has("kind") && !event.get("kind").isJsonNull()
                    ? event.get("kind").getAsString() : "";
            if ("decision_requested".equals(kind)) {
                // Next frame's request; scanned at the next iteration under
                // the next actor's canary set.
                continue;
            }
            if ("decision_accepted".equals(kind) && event.has("actor_seat")) {
                assertEquals(actorSeat, event.get("actor_seat").getAsInt(),
                        "accepted event must close this frame's actor at offset " + offset);
            }
            String serialized = event.toString();
            for (String name : canary) {
                assertTrue(!serialized.contains(name),
                        "hidden-exclusive name '" + name + "' in frame completion '"
                                + kind + "' at offset " + offset
                                + " event=" + snippet(serialized));
            }
        }
    }
    private static String latestTranscriptEvent(XmageFullGameSession session) throws Exception {
        XmageFullGameDecisionController controller =
                field(session, "controller", XmageFullGameDecisionController.class);
        JsonArray transcript = controller.transcript();
        if (transcript.size() == 0) {
            return "{}";
        }
        return transcript.get(transcript.size() - 1).toString();
    }

    private static String snippet(String text) {
        return text.length() <= 600 ? text : text.substring(0, 600) + "...";
    }

    private static void answerNeutrally(XmageFullGameSession session, JsonObject pending) {
        String decisionClass = pending.get("decision_class").getAsString();
        JsonObject legal = session.legalActionsPayload();
        String actor = legal.get("actor_id").getAsString();
        JsonArray actions = legal.getAsJsonArray("actions");
        if ("declare_blocker".equals(decisionClass)) {
            JsonObject emptyProposal = new JsonObject();
            emptyProposal.addProperty("proposal_id", "ws224-canary-block");
            emptyProposal.addProperty("actor_id", actor);
            emptyProposal.add("legal_action_id", com.google.gson.JsonNull.INSTANCE);
            emptyProposal.addProperty("action_type", "structural_decision");
            emptyProposal.add("target_ids", new JsonArray());
            emptyProposal.add("selected_modes", new JsonArray());
            JsonObject choices = new JsonObject();
            choices.add("selected_option_ids", new JsonArray());
            choices.add("ordering", new JsonArray());
            emptyProposal.add("choices", choices);
            session.submitAction(emptyProposal);
            return;
        }
        JsonObject first = null;
        for (JsonElement element : actions) {
            JsonObject candidate = element.getAsJsonObject();
            if ("mulligan".equals(decisionClass)) {
                if ("keep".equals(candidate.getAsJsonObject("metadata")
                        .get("option_type").getAsString())) {
                    first = candidate;
                    break;
                }
            } else if ("priority".equals(decisionClass)) {
                if ("pass_priority".equals(candidate.get("action_type").getAsString())) {
                    first = candidate;
                    break;
                }
            } else if ("declare_attacker".equals(decisionClass)) {
                if ("hold_attacker".equals(candidate.getAsJsonObject("metadata")
                        .get("option_type").getAsString())) {
                    first = candidate;
                    break;
                }
            } else {
                if (first == null || candidate.get("action_id").getAsString()
                        .compareTo(first.get("action_id").getAsString()) < 0) {
                    first = candidate;
                }
            }
        }
        if (first == null) {
            if (actions.size() == 0) {
                return;
            }
            first = actions.get(0).getAsJsonObject();
        }
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "ws224-canary");
        proposal.addProperty("actor_id", actor);
        proposal.addProperty("legal_action_id", first.get("action_id").getAsString());
        proposal.addProperty("action_type", first.get("action_type").getAsString());
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject context = pending.getAsJsonObject("context");
        if (context.has("numeric_min") && !context.get("numeric_min").isJsonNull()
                && ("announce_x".equals(decisionClass) || "amount".equals(decisionClass)
                        || "multi_amount".equals(decisionClass)
                        || "target_amount".equals(decisionClass))) {
            choices.addProperty("numeric_choice", context.get("numeric_min").getAsInt());
        }
        if ("multi_amount".equals(decisionClass) && context.has("numeric_legs")
                && context.get("numeric_legs").isJsonArray()) {
            // WS229 joint frame: per-leg minimums repaired upward into the
            // total band (deterministic joint-minimum strategy).
            com.google.gson.JsonArray legs = context.getAsJsonArray("numeric_legs");
            int totalMin = context.get("numeric_total_min").getAsInt();
            java.util.List<Integer> values = new java.util.ArrayList<>();
            int total = 0;
            for (int index = 0; index < legs.size(); index++) {
                int legMin = legs.get(index).getAsJsonObject().get("min").getAsInt();
                values.add(legMin);
                total += legMin;
            }
            for (int index = 0; total < totalMin; index++) {
                int leg = index % values.size();
                int legMax = legs.get(leg).getAsJsonObject().get("max").getAsInt();
                if (values.get(leg) >= legMax) {
                    if (index > values.size() * 1000) {
                        throw new IllegalStateException("joint minimums cannot reach total band");
                    }
                    continue;
                }
                values.set(leg, values.get(leg) + 1);
                total += 1;
            }
            com.google.gson.JsonArray vector = new com.google.gson.JsonArray();
            values.forEach(vector::add);
            choices.add("numeric_choices", vector);
        }
        session.submitAction(proposal);
    }

    @SuppressWarnings("unchecked")
    private static <T> T field(Object target, String name, Class<T> type) throws Exception {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        Object value = field.get(target);
        if (!type.isInstance(value)) {
            throw new IllegalStateException("field " + name + " is not a " + type);
        }
        return (T) value;
    }

    private static List<String> importCopies(
            XmageDeckImporter importer, RuntimeDeck deck, int count) {
        List<String> handles = new ArrayList<>(count);
        for (int copy = 0; copy < count; copy++) {
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    deck.deckId(), deck.deckHash(), deck.mainboard(), deck.commanders()
            );
            handles.add(imported.deckHandle());
        }
        return List.copyOf(handles);
    }

    private static RuntimeDeck loadRogShaiRuntimeDeck() throws IOException {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        if (repoRoot == null || repoRoot.isBlank()) {
            throw new IllegalStateException("commanderlab.repoRoot is missing");
        }
        JsonObject root = JsonParser.parseString(
                Files.readString(
                        Path.of(repoRoot, "data", "decks", "rogshai_current.json").normalize(),
                        StandardCharsets.UTF_8
                )
        ).getAsJsonObject();
        List<String> mainboard = new ArrayList<>();
        List<String> commanders = new ArrayList<>();
        root.getAsJsonArray("cards").forEach(element -> {
            JsonObject card = element.getAsJsonObject();
            String name = card.get("oracle_name").getAsString();
            int quantity = card.get("quantity").getAsInt();
            String zone = card.get("zone").getAsString();
            List<String> target;
            if ("main".equals(zone)) {
                target = mainboard;
            } else if ("commander".equals(zone)) {
                target = commanders;
            } else {
                throw new IllegalStateException("Unexpected zone: " + zone);
            }
            for (int copy = 0; copy < quantity; copy++) {
                target.add(name);
            }
        });
        return new RuntimeDeck(
                root.get("deck_id").getAsString(),
                root.get("deck_hash").getAsString(),
                List.copyOf(mainboard),
                List.copyOf(commanders)
        );
    }

    private record RuntimeDeck(
            String deckId,
            String deckHash,
            List<String> mainboard,
            List<String> commanders
    ) {
    }
}
