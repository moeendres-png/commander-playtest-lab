package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * FULL107 Phase C execution: WS05-CMD-MULL-2 / WS05-CMD-MULL-4 fixture runs.
 *
 * <p>Fixture-faithful execution (no deviation): Rograkh, Son of Rohgahh +
 * 99 Mountain per seat (exact fixture decks, real cards), natural game
 * start, P1 takes exactly one mulligan ({@code mulligan_once} semantic:
 * select the mulligan action, never keep, exactly-once matched) while all
 * other seats keep, then P1 keeps. Required events asserted from the
 * executor observation log: {@code mulligan_once:P1} plus the London
 * bottom count (2P: bottom 1, not free; 4P multiplayer: bottom 0, free).
 * Zero/multiple matches fail closed; forbidden fallbacks prohibited.</p>
 */
class XmageFullGameWs05MulliganTest {

    @Test
    void ws05CmdMull2BottomsOneCard() throws Exception {
        FixtureLog log = driveMulliganOnce(2, "WS05-CMD-MULL-2");
        assertTrue(log.events.contains("mulligan_once:P1"), "log=" + log.events);
        // London arithmetic on 99 Mountains: open 7 (92 left), take returns 7
        // (99) and redraws 7 (92), bottom 1 -> library 93, hand 6. 2P grants
        // no free mulligan, so exactly one card is bottomed.
        assertEquals(93, log.p1Library, "2P P1 library must show one bottomed card; post=" + log.postInfo + " events=" + log.events);
        assertEquals(6, log.p1Hand, "2P P1 hand must be six after bottoming one");
    }

    @Test
    void ws05CmdMull4BottomsZeroCards() throws Exception {
        FixtureLog log = driveMulliganOnce(4, "WS05-CMD-MULL-4");
        assertTrue(log.events.contains("mulligan_once:P1"), "log=" + log.events);
        // Free multiplayer mulligan: 99 - 7 - 0 = 92; hand seven.
        assertEquals(92, log.p1Library, "4P P1 library must show zero bottomed cards");
        assertEquals(7, log.p1Hand, "4P P1 hand must be seven");
    }

    private static final class FixtureLog {
        final List<String> events = new ArrayList<>();
        int bottomCount = -1;
        int p1Library = -1;
        int p1Hand = -1;
        String postInfo = "?";
    }

    private static FixtureLog driveMulliganOnce(int playerCount, String gameId) {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> mainboard = new ArrayList<>();
        for (int i = 0; i < 99; i++) {
            mainboard.add("Mountain");
        }
        List<String> handles = new ArrayList<>(playerCount);
        for (int seat = 1; seat <= playerCount; seat++) {
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    "ws05-rograkh-mountain-p" + seat,
                    "ws05-rograkh-mountain-hash",
                    mainboard,
                    List.of("Rograkh, Son of Rohgahh"));
            handles.add(imported.deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                gameId, handles, 0, 40, 424242L, importer);
        session.start();

        FixtureLog log = new FixtureLog();
        boolean p1Mulliganed = false;
        // seat index of P1 (seat 1) among actors is unknown upfront; track by
        // resolving exactly one mulligan-take across the whole round-1 phase.
        for (int step = 0; step < 24; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            if ("choose_object".equals(decisionClass)
                    && pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    && pending.get("prompt").getAsString().contains("starting player")) {
                JsonObject self = singleSelfAction(legal, actorId);
                session.submitAction(genericProposal(
                        gameId + "-start-" + step, actorId,
                        self.get("action_id").getAsString(),
                        self.get("action_type").getAsString()));
                continue;
            }
            if ("target".equals(decisionClass)
                    && pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    && pending.get("prompt").getAsString().toLowerCase().contains("bottom")) {
                // London bottom selection. Homogeneity proof: the fixture deck
                // is 99x Mountain with the commander outside the library, so
                // every offered hand card is a Mountain and all single-card
                // selections are outcome-equivalent. Deterministic rule: least
                // option UUID (content-independent, never positional); fail
                // closed unless exactly the full 7-card hand is offered.
                JsonObject bottom = singleBottomTarget(legal);
                JsonObject bottomed = session.submitAction(genericProposal(
                        gameId + "-bottom-" + step, actorId,
                        bottom.get("action_id").getAsString(),
                        bottom.get("action_type").getAsString()));
                assertEquals(pending.get("decision_id").getAsString(),
                        bottomed.get("executed_decision_id").getAsString());
                log.events.add("bottom:P1:1");
                continue;
            }
            if (!"mulligan".equals(decisionClass)) {
                break;
            }
            boolean take = !p1Mulliganed && isP1Turn(pending, 0);
            JsonObject action = take
                    ? singleActionOfType(legal, "mulligan", "mulligan")
                    : singleActionOfType(legal, "mulligan", "keep");
            JsonObject after = session.submitAction(genericProposal(
                    gameId + "-" + step, actorId,
                    action.get("action_id").getAsString(),
                    action.get("action_type").getAsString()));
            assertEquals(pending.get("decision_id").getAsString(),
                    after.get("executed_decision_id").getAsString());
            if (take) {
                p1Mulliganed = true;
                log.events.add("mulligan_once:P1");
            } else {
                log.events.add("keep:" + actorId.substring(0, 8));
            }
            log.events.add("zones:" + zoneSummary(session));
        }
        assertTrue(p1Mulliganed, "P1 must take exactly one mulligan, log=" + log.events);
        JsonObject zones = session.zoneCountsPayload();
        JsonObject post = session.pendingDecisionPayload();
        if (!post.get("decision").isJsonNull()) {
            JsonObject pd = post.getAsJsonObject("decision");
            JsonObject pl = session.legalActionsPayload();
            log.postInfo = pd.get("decision_class").getAsString() + "|"
                    + (pd.has("prompt") && !pd.get("prompt").isJsonNull()
                            ? pd.get("prompt").getAsString() : "?") + "|nactions="
                    + pl.getAsJsonArray("actions").size() + "|first="
                    + pl.getAsJsonArray("actions").get(0).toString();
        } else {
            log.postInfo = "terminal";
        }
        for (JsonElement element : zones.getAsJsonArray("seats")) {
            JsonObject item = element.getAsJsonObject();
            if (item.get("seat").getAsInt() == 0) {
                log.p1Library = item.get("library_count").getAsInt();
                log.p1Hand = item.get("hand_count").getAsInt();
            }
        }
        return log;
    }

    private static boolean isP1Turn(JsonObject pending, int seat) {
        if (pending.has("seat") && !pending.get("seat").isJsonNull()) {
            try {
                return pending.get("seat").getAsInt() == seat;
            } catch (RuntimeException ignored) {
                return false;
            }
        }
        return false;
    }

    private static JsonObject singleBottomTarget(JsonObject legal) {
        List<String> optionIds = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!"choose_targets".equals(action.get("action_type").getAsString())) {
                continue;
            }
            JsonArray allowed = action.getAsJsonArray("allowed_target_ids");
            assertEquals(1, allowed.size(), "each bottom action targets exactly one card");
            optionIds.add(allowed.get(0).getAsString());
        }
        assertEquals(7, optionIds.size(), "full seven-card hand must be offered (fail closed)");
        java.util.Collections.sort(optionIds);
        String chosen = optionIds.get(0);
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (action.get("action_id").getAsString().endsWith(":" + chosen)) {
                return action;
            }
        }
        throw new AssertionError("chosen bottom target not offered");
    }

    private static String zoneSummary(XmageFullGameSession session) {
        JsonObject zones = session.zoneCountsPayload();
        StringBuilder sb = new StringBuilder();
        for (JsonElement element : zones.getAsJsonArray("seats")) {
            JsonObject item = element.getAsJsonObject();
            sb.append(item.get("seat").getAsInt()).append("=h")
                    .append(item.get("hand_count").getAsInt()).append("/l")
                    .append(item.get("library_count").getAsInt()).append(" ");
        }
        return sb.toString().trim();
    }

    private static JsonObject singleSelfAction(JsonObject legal, String actorId) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (action.get("action_id").getAsString().endsWith(":" + actorId)) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "expected exactly one self action (fail closed)");
        return matches.get(0);
    }

    private static JsonObject singleActionOfType(
            JsonObject legal, String actionType, String optionType) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!actionType.equals(action.get("action_type").getAsString())) {
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
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "full107-ws05-mulligan");
        return proposal;
    }
}
