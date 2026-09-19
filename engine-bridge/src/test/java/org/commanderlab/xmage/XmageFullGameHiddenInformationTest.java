package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.cards.Card;
import mage.game.CommanderFreeForAll;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS213 principal-scoped observation (hidden information) on the repinned
 * engine: no pilot may observe private zones of another principal unless the
 * Rules make them public. Structural negatives (no opponent hand/mana keys)
 * plus a test-oracle UUID scan (no opponent hand/library card identity
 * anywhere in the actor's view, labels and metadata included) across a live
 * game. The oracle is test-only peeking, never pilot input.
 */
class XmageFullGameHiddenInformationTest {

    @Test
    void actorViewsNeverExposeOtherPrincipalsPrivateZones() throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, loadRogShaiRuntimeDeck(), 4);
        XmageFullGameSession session = new XmageFullGameSession(
                "ws213-hidden-info", handles, 0, 40, 10704L, importer
        );
        session.start();

        int scanned = 0;
        int oracleHands = 0;
        List<String> grantObservations = new ArrayList<>();
        for (int step = 0; step < 120 && scanned < 60; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String actorId = pending.get("actor_id").getAsString();
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject pilotState = pending.getAsJsonObject("pilot_state");

            // Structural negative: only the actor entry carries private zones.
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
                            "opponent hand array must be absent at offset "
                                    + pending.get("decision_offset").getAsLong());
                    assertTrue(!entry.has("mana_pool"),
                            "opponent mana pool must be absent at offset "
                                    + pending.get("decision_offset").getAsLong());
                }
                JsonArray granted = entry.has("granted_library")
                        && entry.get("granted_library").isJsonArray()
                        ? entry.getAsJsonArray("granted_library") : new JsonArray();
                if (granted.size() > 0) {
                    grantObservations.add(decisionClass + ":" + granted.size());
                }
            }
            assertTrue(actorSawOwnHand);

            // Oracle negative: opponent hand/library card UUIDs must appear
            // nowhere in the actor's serialized view.
            Set<String> hiddenIds = hiddenCardIds(session, actorId);
            if (!hiddenIds.isEmpty()) {
                oracleHands++;
                String serialized = pilotState.toString();
                for (String hidden : hiddenIds) {
                    assertTrue(!serialized.contains(hidden),
                            "hidden card identity leaked at offset "
                                    + pending.get("decision_offset").getAsLong()
                                    + " class=" + decisionClass);
                }
            }

            answerNeutrally(session, pending);
            scanned++;
        }
        assertTrue(scanned >= 30, "must scan a substantive decision run, scanned=" + scanned);
        assertTrue(oracleHands >= 30, "oracle must cover the run, covered=" + oracleHands);
        // D2 grant windows are entitlement-scoped; record-only here. Outside a
        // library-zone decision no grant may appear.
        for (String observation : grantObservations) {
            assertTrue(observation.startsWith("choose_object:"),
                    "library grant outside library-zone decision: " + observation);
        }
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

    private static void answerNeutrally(XmageFullGameSession session, JsonObject pending) {
        String decisionClass = pending.get("decision_class").getAsString();
        JsonObject legal = session.legalActionsPayload();
        String actor = legal.get("actor_id").getAsString();
        JsonArray actions = legal.getAsJsonArray("actions");
        if ("declare_blocker".equals(decisionClass)) {
            JsonObject emptyProposal = new JsonObject();
            emptyProposal.addProperty("proposal_id", "ws213-hidden-block");
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
        proposal.addProperty("proposal_id", "ws213-hidden");
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
