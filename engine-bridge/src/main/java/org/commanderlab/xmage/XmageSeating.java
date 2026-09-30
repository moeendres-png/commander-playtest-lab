package org.commanderlab.xmage;

import mage.game.Game;
import mage.players.Player;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;

/**
 * F-41: seats are turn order.
 *
 * <p>The frozen contract orders a table by seat number: priority traverses
 * P1..PN, and APNAP groups run P1, P2, ... XMage's {@code CircularList.add}
 * inserts each player at the current position, so the engine's turn order is
 * the reverse of the order players are added (P1, PN, ..., P2 when added
 * P1..PN). Every bridge lane therefore adds its players in
 * {@link #additionOrder}: P1 first, then PN down to P2, which makes the
 * engine's own turn order P1, P2, ..., PN.</p>
 *
 * <p>{@link #seat} reads a seat from the engine's own turn-order ring,
 * counted from the table's first player, so a seat always names a player's
 * position in the engine's turn order. The ring keeps players who left, so
 * seats are stable for the whole game.</p>
 */
final class XmageSeating {

    private XmageSeating() {
    }

    /** The engine addition order that makes turn order equal seat order. */
    static <T> List<T> additionOrder(List<T> seatOrder) {
        List<T> order = new ArrayList<>(seatOrder.size());
        if (seatOrder.isEmpty()) {
            return order;
        }
        order.add(seatOrder.get(0));
        for (int index = seatOrder.size() - 1; index >= 1; index--) {
            order.add(seatOrder.get(index));
        }
        return order;
    }

    /** The player's 0-based position in the engine's turn order from the first seat, or -1. */
    static int seat(Game game, UUID playerId) {
        if (game == null || playerId == null || game.getPlayers().isEmpty()) {
            return -1;
        }
        List<UUID> ring = game.getState().getPlayerList();
        UUID first = game.getPlayers().keySet().iterator().next();
        int firstIndex = ring.indexOf(first);
        int index = ring.indexOf(playerId);
        if (firstIndex < 0 || index < 0) {
            return -1;
        }
        return Math.floorMod(index - firstIndex, ring.size());
    }

    /** The game's players in seat order. */
    static List<Player> playersInSeatOrder(Game game) {
        List<Player> players = new ArrayList<>(game.getPlayers().values());
        players.sort(Comparator.comparingInt(player -> seat(game, player.getId())));
        return players;
    }
}
