package org.commanderlab.xmage;

import mage.game.Game;
import mage.players.Player;

import java.util.UUID;

/**
 * Actor-safe principal identity for observations.
 *
 * <p>A principal-scoped observation must not disclose another principal's real
 * identity. The projections in this package previously emitted
 * {@code player.getId().toString()} for <em>every</em> seat, along with
 * {@code active_player_id} and {@code priority_player_id}, so a single
 * {@code get_game_state} handed every viewer the real UUIDs of every opponent.
 *
 * <p>The viewing principal sees its own real id, because a principal must be able
 * to recognise itself. Every other principal is replaced by an opaque token
 * derived from its <em>seat</em>.
 *
 * <p>Seat, rather than a salted hash of the id, is deliberate. Seat is already
 * public in these payloads, so a seat-derived token discloses nothing further,
 * and it stays identical across fresh replay sessions of the same game. A random
 * per-game salt would have been stronger against an attacker who already knows
 * the seat, but it would have made every projection differ between two
 * semantically identical replays, which is exactly what semantic replay must
 * rule out.
 */
final class ActorSafeIdentity {

    private ActorSafeIdentity() {
    }

    /** The id {@code viewer} may legitimately see for the principal at {@code seat}. */
    static String forSeat(UUID viewerId, UUID subjectId, int seat) {
        if (viewerId == null || subjectId == null || seat < 0) {
            return null;
        }
        if (viewerId.equals(subjectId)) {
            return subjectId.toString();
        }
        return "op-" + seat;
    }

    /** Seat-based form for callers that hold a {@code Player}. */
    static String forSeat(Game game, Player viewer, Player subject) {
        if (game == null || subject == null) {
            return null;
        }
        return forSeat(
                viewer == null ? null : viewer.getId(),
                subject.getId(),
                seatOf(game, subject.getId()));
    }

    /** Seat-based form for callers that hold a raw id, such as the active player. */
    static String optionalForSeat(Game game, Player viewer, UUID subjectId) {
        if (game == null || subjectId == null) {
            return null;
        }
        return forSeat(
                viewer == null ? null : viewer.getId(),
                subjectId,
                seatOf(game, subjectId));
    }

    private static int seatOf(Game game, UUID playerId) {
        if (game == null || playerId == null) {
            return -1;
        }
        return XmageSeating.seat(game, playerId);
    }
}
