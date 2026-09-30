package org.commanderlab.xmage;

import mage.game.Game;
import mage.players.Player;
import mage.util.CircularList;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * F-41: the engine's own turn order is seat order.
 *
 * <p>The frozen contract orders a table by seat number ("Priority traverses
 * exactly P1..P5 live ring"; APNAP groups P1, P2, ...). XMage's
 * {@code CircularList.add} inserts at the current position, so a table added
 * P1..PN turned P1, PN, ..., P2. These tests read the engine's own ring, not
 * the bridge's seat readout.</p>
 */
class XmageSeatingTest {

    @Test
    void theAdditionOrderSeatsTheFirstPlayerThenTheRestReversed() {
        assertEquals(List.of("a", "d", "c", "b"), XmageSeating.additionOrder(List.of("a", "b", "c", "d")));
        assertEquals(List.of("a", "b"), XmageSeating.additionOrder(List.of("a", "b")));
        assertEquals(List.of(), XmageSeating.additionOrder(List.of()));
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {2, 3, 4, 5, 6})
    void theEngineTurnOrderIsSeatOrderOnTheFullGameLane(int playerCount) {
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start("seating-" + playerCount + "p", playerCount, List.of());
        Game game = started.session().restorationGame();
        List<String> expected = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            expected.add("Full Game Seat " + seat);
            Player player = started.seats().get("P" + seat);
            assertEquals(seat - 1, XmageSeating.seat(game, player.getId()), "P" + seat + "'s seat");
        }
        assertEquals(expected, engineTurnOrder(game, started.seats().get("P1").getId()));
        List<String> bySeat = new ArrayList<>();
        XmageSeating.playersInSeatOrder(game).forEach(player -> bySeat.add(player.getName()));
        assertEquals(expected, bySeat);
    }

    /** One round of the engine's own turn-order ring, starting at {@code first}, by player name. */
    static List<String> engineTurnOrder(Game game, UUID first) {
        CircularList<UUID> ring = game.getState().getPlayerList().copy();
        ring.setCurrent(first);
        List<String> names = new ArrayList<>(List.of(game.getPlayer(first).getName()));
        for (int step = 1; step < ring.size(); step++) {
            names.add(game.getPlayer(ring.getNext()).getName());
        }
        return names;
    }
}
