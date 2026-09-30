package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

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
}
