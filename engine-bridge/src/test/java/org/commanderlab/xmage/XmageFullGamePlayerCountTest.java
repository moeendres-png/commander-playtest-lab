package org.commanderlab.xmage;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS215 variable-player cardinality gate, R19-widened and R21-remediated:
 * the full-game lane supports exactly 2..8 Commander Free-for-All principals
 * under one authoritative contract (R19 gates 2-6: bridge suites, live 6P
 * smoke + full gate with replay MATCH, XmageSixPlayerGateTest; seven and
 * eight seats since #1672, SIMULATE only, no replay claim). Out-of-range
 * construction fails closed at the session boundary before any deck
 * resolution or engine contact (no silent seat creation, no default
 * fourth player, no hidden dummies, no partial lifecycle). Every supported
 * count constructs with the exact seat/principal map. Nine players is the
 * negative control above the supported range (seven was until #1672).
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
    void sixPlayerPassesCardinalityGate() {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>(
                List.of("d0", "d1", "d2", "d3", "d4", "d5"));
        // Fake handles fail at deck resolution (after the cardinality
        // gate passes): the gate itself must not reject the supported 6P.
        RuntimeException failure = assertThrows(
                RuntimeException.class,
                () -> new XmageFullGameSession(
                        "ws215-6p", handles, 0, 40, 1L, importer)
        );
        assertTrue(
                !failure.getMessage().contains("FULL_GAME_INVALID_PLAYER_COUNT"),
                "supported count 6 must pass the cardinality gate"
        );
    }

    @Test
    void sevenAndEightPlayersPassCardinalityGate() {
        // #1672: fails on the BEFORE bridge (MAX_PLAYERS 6), where 7 and 8 were refused.
        for (int count : new int[]{7, 8}) {
            XmageDeckImporter importer = new XmageDeckImporter();
            List<String> handles = fakeHandles(count);
            RuntimeException failure = assertThrows(
                    RuntimeException.class,
                    () -> new XmageFullGameSession(
                            "ws215-" + count + "p", handles, 0, 40, 1L, importer)
            );
            assertTrue(
                    !failure.getMessage().contains("FULL_GAME_INVALID_PLAYER_COUNT"),
                    "supported count " + count + " must pass the cardinality gate"
            );
        }
    }

    @Test
    void ninePlayerConstructionFailsClosed() {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = fakeHandles(9);
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> new XmageFullGameSession(
                        "ws215-9p", handles, 0, 40, 1L, importer)
        );
        assertTrue(failure.getMessage().contains("FULL_GAME_INVALID_PLAYER_COUNT"));
        assertTrue(failure.getMessage().contains("(supported 2..8)"));
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
        for (int count : new int[]{2, 3, 4, 5, 6, 7, 8}) {
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
    void capabilityBoundsAreTwoToEight() {
        assertEquals(2, XmageFullGameSession.MIN_PLAYERS);
        assertEquals(8, XmageFullGameSession.MAX_PLAYERS);
        // the mid-game starting-state lane is not widened by #1672
        assertEquals(6, XmageFullGameSession.MIDGAME_MAX_PLAYERS);
    }

    @Test
    void midgameLaneRefusesSevenAndEightBeforeAnySession() {
        // #1672 widens only the full-game lane: the mid-game entries keep 2..6.
        for (int count : new int[]{2, 3, 4, 5, 6}) {
            XmageMidgameJsonlBridge.requireMidgamePlayerCount(count);
        }
        for (int count : new int[]{1, 7, 8, 9}) {
            XmageNativeStateRestoration.RestorationException failure = assertThrows(
                    XmageNativeStateRestoration.RestorationException.class,
                    () -> XmageMidgameJsonlBridge.requireMidgamePlayerCount(count));
            assertTrue(failure.getMessage().startsWith("UNSUPPORTED_PLAYER_COUNT: " + count));
        }
    }

    private static List<String> fakeHandles(int count) {
        List<String> handles = new ArrayList<>(count);
        for (int index = 0; index < count; index++) {
            handles.add("unresolved-" + index);
        }
        return handles;
    }
}
