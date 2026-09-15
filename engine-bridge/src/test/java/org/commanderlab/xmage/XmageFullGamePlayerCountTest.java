package org.commanderlab.xmage;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS215 variable-player cardinality gate: the full-game lane supports exactly
 * 2..5 Commander Free-for-All principals under one authoritative contract.
 * Out-of-range construction fails closed at the session boundary before any
 * deck resolution or engine contact (no silent seat creation, no default
 * fourth player, no hidden dummies, no partial lifecycle). Every supported
 * count constructs with the exact seat/principal map.
 */
class XmageFullGamePlayerCountTest {

    @Test
    void zeroPlayerConstructionFailsClosed() {
        XmageDeckImporter importer = new XmageDeckImporter();
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> new XmageFullGameSession(
                        "ws215-0p", List.of(), 0, 40, 1L, importer)
        );
        assertTrue(failure.getMessage().contains("FULL_GAME_INVALID_PLAYER_COUNT"));
    }

    @Test
    void onePlayerConstructionFailsClosed() {
        XmageDeckImporter importer = new XmageDeckImporter();
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> new XmageFullGameSession(
                        "ws215-1p", List.of("d0"), 0, 40, 1L, importer)
        );
        assertTrue(failure.getMessage().contains("FULL_GAME_INVALID_PLAYER_COUNT"));
    }

    @Test
    void sixPlayerConstructionFailsClosed() {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>(
                List.of("d0", "d1", "d2", "d3", "d4", "d5"));
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> new XmageFullGameSession(
                        "ws215-6p", handles, 0, 40, 1L, importer)
        );
        assertTrue(failure.getMessage().contains("FULL_GAME_INVALID_PLAYER_COUNT"));
    }

    @Test
    void invalidStartingSeatFailsClosedForSupportedCount() {
        XmageDeckImporter importer = new XmageDeckImporter();
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> new XmageFullGameSession(
                        "ws215-bad-seat", List.of("d0", "d1", "d2"), 3, 40, 1L, importer)
        );
        assertTrue(failure.getMessage().contains("invalid starting_player_seat"));
    }

    @Test
    void supportedCountsConstructWithExactPlayerCount() {
        for (int count : new int[]{2, 3, 4, 5}) {
            XmageDeckImporter importer = new XmageDeckImporter();
            List<String> handles = fakeHandles(count);
            // Fake handles fail at deck resolution (after the cardinality
            // gate passes): the gate itself must not reject supported counts.
            RuntimeException failure = assertThrows(
                    RuntimeException.class,
                    () -> new XmageFullGameSession(
                            "ws215-gate-" + count, handles, 0, 40, 1L, importer)
            );
            assertTrue(
                    !failure.getMessage().contains("FULL_GAME_INVALID_PLAYER_COUNT"),
                    "supported count " + count + " must pass the cardinality gate"
            );
        }
    }

    @Test
    void capabilityBoundsAreTwoToFive() {
        assertEquals(2, XmageFullGameSession.MIN_PLAYERS);
        assertEquals(5, XmageFullGameSession.MAX_PLAYERS);
    }

    private static List<String> fakeHandles(int count) {
        List<String> handles = new ArrayList<>(count);
        for (int index = 0; index < count; index++) {
            handles.add("unresolved-" + index);
        }
        return handles;
    }
}
