package org.commanderlab.xmage;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Ties {@code XmageFullGamePlayer.manaAvailableInPlayableCalcCopy} to the engine commit whose
 * {@code PlayerImpl.getManaAvailable} it mirrors. The engine jar is not byte-reproducible, so
 * the class bytes cannot be pinned; the commit can. A repin changes
 * {@code XmageProvider.ENGINE_COMMIT} and trips this test, which is the cue to re-compare the
 * mirror with the engine method and then move this constant.
 * {@code XmageNestedCopySkipDifferentialTest} checks the behaviour against the engine method.
 */
class XmageMirroredEngineMethodPinTest {

    /** The engine commit at which the mirror was last compared with the engine method. */
    static final String MIRROR_COMPARED_AT = "f4d12f6e8066203fba7aa38bd35ea3358117393d";

    @Test
    void mirrorWasComparedAtThePinnedEngineCommit() {
        assertEquals(MIRROR_COMPARED_AT, XmageProvider.ENGINE_COMMIT,
                "The engine pin moved. Re-compare "
                        + "XmageFullGamePlayer.manaAvailableInPlayableCalcCopy with "
                        + "PlayerImpl.getManaAvailable at the new commit "
                        + "(docs/claude/REPIN_RUNBOOK.md), then set MIRROR_COMPARED_AT to it.");
    }
}
