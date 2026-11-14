package org.commanderlab.xmage;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Ties {@code XmageFullGamePlayer.manaAvailableInPlayableCalcCopy} to the engine commit whose
 * {@code PlayerImpl.getManaAvailable} it mirrors. The engine jar is not byte-reproducible, so
 * the class bytes cannot be pinned; the commit can. The commit is kept as its SHA-256 on
 * purpose: a repin replaces every literal copy of the old pin, and a literal here would move
 * along silently. With the digest, a repin trips this test, which is the cue to re-compare
 * the mirror with the engine method and then set the digest of the new commit.
 * {@code XmageNestedCopySkipDifferentialTest} checks the behaviour against the engine method.
 */
class XmageMirroredEngineMethodPinTest {

    /** SHA-256 of the engine commit id at which the mirror was last compared. */
    static final String MIRROR_COMPARED_AT_SHA256 =
            "b9ea558dbe5ae149d4cfa214e974d126fa2ca4cfc668b0e366a93ca8f9d9e8e5";

    @Test
    void mirrorWasComparedAtThePinnedEngineCommit() throws Exception {
        String actual = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                .digest(XmageProvider.ENGINE_COMMIT.getBytes(StandardCharsets.US_ASCII)));
        assertEquals(MIRROR_COMPARED_AT_SHA256, actual,
                "The engine pin moved. Re-compare "
                        + "XmageFullGamePlayer.manaAvailableInPlayableCalcCopy with "
                        + "PlayerImpl.getManaAvailable at the new commit "
                        + "(docs/claude/REPIN_RUNBOOK.md), then set MIRROR_COMPARED_AT_SHA256 "
                        + "to the SHA-256 of the new commit id.");
    }
}
