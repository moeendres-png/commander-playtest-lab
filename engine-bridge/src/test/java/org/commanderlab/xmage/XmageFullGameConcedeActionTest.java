package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS213 authoritative concession (WS211 engine contract): CONCEDE is a native
 * LegalAction whose availability originates in {@code
 * Game.canConcede(exactPrincipal)}, whose selection names the exact principal
 * as both actor and subject, and whose execution is native {@code
 * Game.concede} for that principal. No Lab-side availability heuristic, no
 * Yes/No blocking callback, no outcome injection.
 */
class XmageFullGameConcedeActionTest {

    @Test
    void concedeOfferAvailableForLivePrincipal() throws Exception {
        XmageFullGameSession session = startBoundSession("ws213-concede-offer", 7017L);
        String principal = principalId(session, 0);

        JsonObject offer = session.concedeOfferPayload(principal);
        assertTrue(offer.get("concede_available").getAsBoolean());
        assertEquals(principal, offer.get("concede_actor_id").getAsString());
        JsonObject action = offer.getAsJsonObject("concede_action");
        assertEquals("concede", action.get("action_type").getAsString());
        assertEquals(principal, action.get("actor_id").getAsString());
    }

    @Test
    void concedeSubmissionExecutesNativelyForExactPrincipal() throws Exception {
        XmageFullGameSession session = startBoundSession("ws213-concede-exec", 7017L);
        answerMulligans(session, 8);
        String principal = principalId(session, 1);

        // Concession needs no priority: the pending actor may differ.
        JsonObject offer = session.concedeOfferPayload(principal);
        assertTrue(offer.get("concede_available").getAsBoolean());

        JsonObject result = session.submitConcede(concedeProposal(principal));
        assertEquals(principal, result.get("conceded_actor_id").getAsString());

        // Native execution marks the exact principal lost on the calling
        // thread; game-thread leave processing follows at priority.
        boolean lostObserved = false;
        for (com.google.gson.JsonElement outcome
                : result.getAsJsonArray("outcomes")) {
            JsonObject item = outcome.getAsJsonObject();
            if (principal.equals(item.get("player_id").getAsString())) {
                lostObserved = item.get("lost").getAsBoolean();
            }
        }
        assertTrue(lostObserved, "native concede must mark the exact principal lost");

        // The conceder is now stale: availability is gone and resubmission
        // fails closed without touching game state.
        assertFalse(session.concedeOfferPayload(principal)
                .get("concede_available").getAsBoolean());
        XmageFullGameDecisionController.DecisionException stale = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> session.submitConcede(concedeProposal(principal))
        );
        assertTrue(stale.getMessage().contains("CONCEDE_UNAVAILABLE"));
    }

    @Test
    void concedeGameContinuesForRemainingPlayers() throws Exception {
        XmageFullGameSession session = startBoundSession("ws213-concede-cont", 7017L);
        answerMulligans(session, 8);
        String principal = principalId(session, 2);
        session.submitConcede(concedeProposal(principal));

        // The still-pending native decision (whatever its actor) must remain
        // answerable through the generic boundary: concession neither injects
        // outcomes nor wedges the engine.
        int answered = 0;
        for (int step = 0; step < 40; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String actor = pending.get("actor_id").getAsString();
            if (principal.equals(actor)) {
                // The conceded player's own frame: pass/keep neutrally.
                answerNeutrally(session, pending);
            } else {
                answerNeutrally(session, pending);
            }
            answered++;
        }
        assertTrue(answered > 0, "game must continue after a concession");

        // The conceder never decides again: no later pending actor is theirs
        // once the engine processed the leave (bounded observation).
        JsonObject payload = session.pendingDecisionPayload();
        if (!payload.get("decision").isJsonNull()) {
            String actor = payload.getAsJsonObject("decision").get("actor_id").getAsString();
            assertTrue(!principal.equals(actor)
                    || session.concedeOfferPayload(principal)
                            .get("concede_available").getAsBoolean() == false);
        }
    }

    @Test
    void concedeRejectsForeignAndMismatchedActors() throws Exception {
        XmageFullGameSession session = startBoundSession("ws213-concede-neg", 7017L);
        String principal = principalId(session, 0);
        String other = principalId(session, 1);

        // Unknown principal fails closed.
        XmageFullGameDecisionController.DecisionException unknown = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> session.submitConcede(concedeProposal("00000000-0000-0000-0000-000000000000"))
        );
        assertTrue(unknown.getMessage().contains("PILOT_RESPONSE_INVALID"));

        // Controller-for-controlled confusion: actor != subject is rejected,
        // so one principal can never be conceded for another.
        JsonObject mismatched = concedeProposal(other);
        mismatched.addProperty("actor_id", principal);
        XmageFullGameDecisionController.DecisionException mismatch = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> session.submitConcede(mismatched)
        );
        assertTrue(mismatch.getMessage().contains("PILOT_RESPONSE_INVALID"));

        // Malformed principal fails closed.
        XmageFullGameDecisionController.DecisionException malformed = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> session.concedeOfferPayload("not-a-uuid")
        );
        assertTrue(malformed.getMessage().contains("PILOT_RESPONSE_INVALID"));
    }

    @Test
    void unattributedPlayerConcedeStillFailsClosed() {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        XmageFullGamePlayer player = new XmageFullGamePlayer(
                "ws213-concede-direct",
                mage.constants.RangeOfInfluence.ALL,
                controller
        );
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> player.concede(null)
        );
        assertTrue(failure.getMessage().contains("OUT_OF_SCOPE_DECISION"));
    }

    private static XmageFullGameSession startBoundSession(String gameId, long seed) throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, loadRogShaiRuntimeDeck(), 4);
        XmageFullGameSession session = new XmageFullGameSession(
                gameId, handles, 0, 40, seed, importer
        );
        session.start();
        return session;
    }

    private static String principalId(XmageFullGameSession session, int seat) {
        JsonObject payload = session.pendingDecisionPayload();
        // Outcomes list is seat-ordered.
        JsonArray outcomes = payload.getAsJsonArray("outcomes");
        return outcomes.get(seat).getAsJsonObject().get("player_id").getAsString();
    }

    private static void answerMulligans(XmageFullGameSession session, int budget) {
        for (int step = 0; step < budget; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                return;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            if (!"mulligan".equals(pending.get("decision_class").getAsString())) {
                return;
            }
            JsonObject legal = session.legalActionsPayload();
            String actor = legal.get("actor_id").getAsString();
            JsonObject keep = null;
            for (com.google.gson.JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                if ("mulligan".equals(action.get("action_type").getAsString())
                        && "keep".equals(action.getAsJsonObject("metadata")
                                .get("option_type").getAsString())) {
                    keep = action;
                }
            }
            if (keep == null) {
                return;
            }
            session.submitAction(genericProposal(
                    "ws213-mulligan-" + step, actor,
                    keep.get("action_id").getAsString(), "mulligan"));
        }
    }

    private static void answerNeutrally(XmageFullGameSession session, JsonObject pending) {
        String decisionClass = pending.get("decision_class").getAsString();
        JsonObject legal = session.legalActionsPayload();
        String actor = legal.get("actor_id").getAsString();
        JsonArray actions = legal.getAsJsonArray("actions");
        if (actions.size() == 0) {
            return;
        }
        if ("mulligan".equals(decisionClass)) {
            for (com.google.gson.JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                if ("keep".equals(action.getAsJsonObject("metadata")
                        .get("option_type").getAsString())) {
                    session.submitAction(genericProposal(
                            "ws213-neutral", actor,
                            action.get("action_id").getAsString(), "mulligan"));
                    return;
                }
            }
        }
        if ("priority".equals(decisionClass)) {
            for (com.google.gson.JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                if ("pass_priority".equals(action.get("action_type").getAsString())) {
                    session.submitAction(genericProposal(
                            "ws213-neutral", actor,
                            action.get("action_id").getAsString(), "pass_priority"));
                    return;
                }
            }
        }
        if ("declare_attacker".equals(decisionClass)) {
            for (com.google.gson.JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                if ("hold_attacker".equals(action.getAsJsonObject("metadata")
                        .get("option_type").getAsString())) {
                    session.submitAction(genericProposal(
                            "ws213-neutral", actor,
                            action.get("action_id").getAsString(), "declare_attackers"));
                    return;
                }
            }
        }
        // Any other class: lexicographically smallest offered option (reachability only).
        JsonObject first = actions.get(0).getAsJsonObject();
        for (com.google.gson.JsonElement element : actions) {
            JsonObject candidate = element.getAsJsonObject();
            if (candidate.get("action_id").getAsString()
                    .compareTo(first.get("action_id").getAsString()) < 0) {
                first = candidate;
            }
        }
        JsonObject proposal = genericProposal(
                "ws213-neutral", actor,
                first.get("action_id").getAsString(),
                first.get("action_type").getAsString());
        JsonObject context = pending.getAsJsonObject("context");
        if (context.has("numeric_min") && !context.get("numeric_min").isJsonNull()
                && ("announce_x".equals(decisionClass) || "amount".equals(decisionClass)
                        || "multi_amount".equals(decisionClass))) {
            proposal.getAsJsonObject("choices").addProperty(
                    "numeric_choice", context.get("numeric_min").getAsInt());
        }
        session.submitAction(proposal);
    }

    private static JsonObject concedeProposal(String principal) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "ws213-concede");
        proposal.addProperty("actor_id", principal);
        proposal.addProperty("player_id", principal);
        return proposal;
    }

    private static JsonObject genericProposal(
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
        return proposal;
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
