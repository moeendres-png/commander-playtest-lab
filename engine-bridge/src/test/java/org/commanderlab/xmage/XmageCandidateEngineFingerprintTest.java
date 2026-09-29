package org.commanderlab.xmage;

import mage.game.Game;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Successor-repin identity guard (2026-09-29): the bridge declares the XMage
 * multiplayer candidate as its engine commit, and the engine classes actually
 * loaded at runtime are that candidate's.
 *
 * <p>XmageProvider.ENGINE_COMMIT is a declared constant. This test adds a
 * runtime fingerprint: the candidate's bounded F-21 APNAP primitives must be
 * present on the loaded mage.game.Game. A build against a stale engine
 * artifact (for example the prior pin in a shared Maven cache) fails here, so it
 * can never be credited as the new pin.</p>
 */
class XmageCandidateEngineFingerprintTest {

    static final String CANDIDATE = "fcfde9dad30fa56e60d5f5bc40ddce6ecd68019c";

    @Test
    void declaredEngineCommitIsTheCandidate() {
        assertEquals(CANDIDATE, XmageProvider.ENGINE_COMMIT);
    }

    @Test
    void loadedEngineCarriesTheCandidatesApnapPrimitives() throws Exception {
        Method players = Game.class.getMethod("getPlayerIdsInApnapOrder");
        Method opponents = Game.class.getMethod("getOpponentsInApnapOrder", UUID.class);
        Method inGameOpponents = Game.class.getMethod("getOpponentsInGame", UUID.class);
        assertEquals(List.class, players.getReturnType(),
                "loaded engine is not the candidate: " + Game.class.getProtectionDomain()
                        .getCodeSource().getLocation());
        assertEquals(List.class, opponents.getReturnType());
        assertEquals(Set.class, inGameOpponents.getReturnType(),
                "loaded engine predates the F-22/F-23 successor");
    }
}
