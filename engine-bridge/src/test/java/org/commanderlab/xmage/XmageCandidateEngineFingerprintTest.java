package org.commanderlab.xmage;

import mage.game.Game;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Successor-repin identity guard (2026-09-29, successor v2 2026-09-30): the bridge
 * declares the XMage multiplayer candidate as its engine commit, and the engine
 * classes actually loaded at runtime are that candidate's.
 *
 * <p>XmageProvider.ENGINE_COMMIT is a declared constant. This test adds a
 * runtime fingerprint: the candidate's bounded F-21 APNAP primitives must be
 * present on the loaded mage.game.Game. A build against a stale engine
 * artifact (for example the prior pin in a shared Maven cache) fails here, so it
 * can never be credited as the new pin.</p>
 */
class XmageCandidateEngineFingerprintTest {

    static final String CANDIDATE = "9375f35ac7c9a540ebcb8b262b8645b8c6b1b326";

    @Test
    void declaredEngineCommitIsTheCandidate() {
        assertEquals(CANDIDATE, XmageProvider.ENGINE_COMMIT);
    }

    @Test
    void loadedEngineCarriesTheCandidatesApnapPrimitives() throws Exception {
        Method players = Game.class.getMethod("getPlayerIdsInApnapOrder");
        Method opponents = Game.class.getMethod("getOpponentsInApnapOrder", UUID.class);
        assertEquals(List.class, players.getReturnType(),
                "loaded engine is not the candidate: " + Game.class.getProtectionDomain()
                        .getCodeSource().getLocation());
        assertEquals(List.class, opponents.getReturnType());
    }

    /**
     * Successor v2 (2026-09-30): the loaded engine also carries F-23's explicit
     * current-opponent query and the F-28/F-29 combat fixes.
     */
    @Test
    void loadedEngineCarriesTheSuccessorFixes() throws Exception {
        Method inGame = Game.class.getMethod("getOpponentsInGame", UUID.class);
        assertEquals(java.util.Set.class, inGame.getReturnType(), "F-23");
        Class<?> combat = mage.game.combat.Combat.class;
        Method forcedBlock = combat.getDeclaredMethod("canBlockInThisCombat",
                mage.game.permanent.Permanent.class, UUID.class, Game.class);
        assertEquals(boolean.class, forcedBlock.getReturnType(), "F-28");
        Method blockOrder = combat.getDeclaredMethod("getPlayerDefendersInApnapOrder", Game.class);
        assertEquals(List.class, blockOrder.getReturnType(), "F-29: loaded engine is not the successor: "
                + combat.getProtectionDomain().getCodeSource().getLocation());
    }
}
