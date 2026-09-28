package org.commanderlab.xmage;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

import java.util.UUID;

/**
 * Gate 9: a principal-scoped observation must not disclose another principal's
 * real identity.
 *
 * <p>Before this change every projection emitted {@code player.getId()} for all
 * seats, so one {@code get_game_state} handed the viewer the real UUIDs of every
 * opponent, while the payload's own docstring claimed hidden information was
 * preserved.
 */
class ActorSafeIdentityTest {

    private static final UUID GAME = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final UUID ACTOR = UUID.fromString("22222222-2222-2222-2222-222222222222");
    private static final UUID OPPONENT = UUID.fromString("33333333-3333-3333-3333-333333333333");

    private static String safe(UUID viewer, UUID subject, int seat) {
        return ActorSafeIdentity.forSeat(viewer, subject, seat);
    }

    @Test
    void viewerSeesItsOwnRealId() {
        assertEquals(ACTOR.toString(), safe(ACTOR, ACTOR, 0));
    }

    @Test
    void viewerNeverSeesAnOpponentsRealId() {
        String token = safe(ACTOR, OPPONENT, 2);
        assertNotEquals(OPPONENT.toString(), token);
        assertEquals("op-2", token);
    }

    @Test
    void opponentTokenIsStable() {
        assertEquals(safe(ACTOR, OPPONENT, 2), safe(ACTOR, OPPONENT, 2));
    }

    @Test
    void differentSeatsGetDifferentTokens() {
        assertNotEquals(safe(ACTOR, OPPONENT, 1), safe(ACTOR, OPPONENT, 2));
    }

    @Test
    void tokensAreReplayStableForTheSameSeat() {
        // Two semantically identical replays must project identical semantics.
        // A per-session salt would break this, which is why the token is derived
        // from the public seat rather than from a random salt.
        assertEquals(safe(ACTOR, OPPONENT, 2), safe(ACTOR, OPPONENT, 2));
    }

    @Test
    void tokenDisclosesNothingBeyondThePublicSeat() {
        // Seat is already present in the payload, so op-N carries no new
        // information about the principal behind it.
        assertEquals("op-" + 3, safe(ACTOR, OPPONENT, 3));
    }

    @Test
    void differentViewersAgreeOnTheSameOpponent() {
        UUID other = UUID.fromString("44444444-4444-4444-4444-444444444444");
        assertEquals(safe(ACTOR, OPPONENT, 2), safe(other, OPPONENT, 2));
    }

    @Test
    void eachViewerStillSeesItself() {
        UUID other = UUID.fromString("44444444-4444-4444-4444-444444444444");
        assertEquals(ACTOR.toString(), safe(ACTOR, ACTOR, 0));
        assertEquals(other.toString(), safe(other, other, 0));
    }

    @Test
    void nullsAndUnknownSeatsAreHandledWithoutDisclosingAnything() {
        assertNull(safe(null, OPPONENT, 2));
        assertNull(safe(ACTOR, null, 2));
        assertNull(safe(ACTOR, OPPONENT, -1));
        assertNull(ActorSafeIdentity.forSeat(null, null, null));
        assertNull(ActorSafeIdentity.optionalForSeat(null, null, OPPONENT));
    }
}
