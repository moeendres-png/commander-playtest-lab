package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * The full-game lane states its player range once: the session's own
 * constants. Machine-readable fields and human-readable notes must agree with
 * them (the notes used to say 2..5 while the lane accepted 2..6).
 */
class XmageFullGameContractTruthTest {

    private static final Pattern RANGE = Pattern.compile("(\\d+)\\.\\.(\\d+)-player");

    @Test
    void everyPlayerRangeTheLaneStatesIsTheSessionRange() {
        JsonObject payload = XmageFullGameJsonlBridge.capabilitiesPayload();
        JsonObject capabilities = payload.getAsJsonObject("capabilities");
        JsonObject lane = payload.getAsJsonObject("full_game_lane");
        assertEquals(XmageFullGameSession.MIN_PLAYERS, capabilities.get("min_players").getAsInt());
        assertEquals(XmageFullGameSession.MAX_PLAYERS, capabilities.get("max_players").getAsInt());
        assertEquals(XmageFullGameSession.MIN_PLAYERS, lane.get("min_players").getAsInt());
        assertEquals(XmageFullGameSession.MAX_PLAYERS, lane.get("max_players").getAsInt());
        int ranges = 0;
        for (JsonElement note : capabilities.getAsJsonArray("notes")) {
            Matcher matcher = RANGE.matcher(note.getAsString());
            while (matcher.find()) {
                ranges++;
                assertEquals(XmageFullGameSession.MIN_PLAYERS, Integer.parseInt(matcher.group(1)), note.getAsString());
                assertEquals(XmageFullGameSession.MAX_PLAYERS, Integer.parseInt(matcher.group(2)), note.getAsString());
            }
        }
        assertTrue(ranges > 0, "the lane states its operational range in a note");
    }

    /**
     * #662 SLOT-06: a required capability may be reported {@code true} only while the
     * test classes that prove its surface exist (the freeze record additionally needs
     * their executed in-epoch receipts). Mirrors freeze_record.CAPABILITY_PROOF; the
     * headless flag is proven by the production-lane AF01 run itself, engine shutdown
     * by that run plus the shutdown test.
     */
    static final Map<String, List<String>> CAPABILITY_PROOF = Map.of(
            "legal_actions_supported", List.of(
                    "XmageFullGameDecisionClassMatrixTest", "XmageFullGameDecisionClassInventoryTest",
                    "XmageFullGameUnprojectableDecisionTest", "XmageFullGameCancelRewindTest"),
            "action_submission_supported", List.of(
                    "XmageFullGameDecisionClassMatrixTest", "XmageFullGameDecisionClassInventoryTest",
                    "XmageFullGameCancelRewindTest"),
            "event_log_supported", List.of("XmageFullGameEventLogTest"),
            "game_shutdown_supported", List.of("XmageFullGameShutdownGameTest"),
            "engine_shutdown_supported", List.of("XmageFullGameShutdownGameTest"),
            "replay_supported", List.of("XmageFullGameReplayExportTest"),
            "seed_supported", List.of("XmageFullGameRulesSeedBindingTest"),
            "multiplayer_supported", List.of("XmageFullGamePlayerCountTest"),
            "deck_import_supported", List.of("XmageFullGamePlayerCountTest"),
            "commander_supported", List.of(
                    "XmageFullGameTaxExecutionTest", "XmageFullGamePartnerExecutionTest"));

    @Test
    void everyTrueRequiredCapabilityHasItsProofClass() {
        JsonObject capabilities = XmageFullGameJsonlBridge.capabilitiesPayload().getAsJsonObject("capabilities");
        CAPABILITY_PROOF.forEach((flag, classes) -> {
            if (!capabilities.get(flag).getAsBoolean()) {
                return;
            }
            for (String name : classes) {
                try {
                    Class.forName("org.commanderlab.xmage." + name);
                } catch (ClassNotFoundException missing) {
                    fail(flag + " is reported true without its proof class " + name);
                }
            }
        });
    }
}
