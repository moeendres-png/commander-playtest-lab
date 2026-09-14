package org.commanderlab.xmage;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS213 player-count impact gate: the full-game lane is operationally scoped
 * to exactly four players. Non-4P construction fails closed at the session
 * boundary (no silent 2P/3P/5P game, no fallback). 4P lifecycle is proven by
 * the requalification matrix; 2P/3P/5P remain NOT_SUPPORTED with a bounded
 * successor (variable-player session), never silently attempted.
 */
class XmageFullGamePlayerCountTest {

    @Test
    void twoPlayerConstructionFailsClosed() {
        XmageDeckImporter importer = new XmageDeckImporter();
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> new XmageFullGameSession(
                        "ws213-2p", List.of("d0", "d1"), 0, 40, 1L, importer)
        );
        assertTrue(failure.getMessage().contains("FULL_GAME_REQUIRES_EXACTLY_FOUR_PLAYERS"));
    }

    @Test
    void threePlayerConstructionFailsClosed() {
        XmageDeckImporter importer = new XmageDeckImporter();
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> new XmageFullGameSession(
                        "ws213-3p", List.of("d0", "d1", "d2"), 0, 40, 1L, importer)
        );
        assertTrue(failure.getMessage().contains("FULL_GAME_REQUIRES_EXACTLY_FOUR_PLAYERS"));
    }

    @Test
    void fivePlayerConstructionFailsClosed() {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>(List.of("d0", "d1", "d2", "d3", "d4"));
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> new XmageFullGameSession(
                        "ws213-5p", handles, 0, 40, 1L, importer)
        );
        assertTrue(failure.getMessage().contains("FULL_GAME_REQUIRES_EXACTLY_FOUR_PLAYERS"));
    }
}
