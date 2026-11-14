package org.commanderlab.xmage;

import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.security.MessageDigest;
import java.util.HexFormat;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

/**
 * Pins the engine class that {@code XmageFullGamePlayer.manaAvailableInPlayableCalcCopy}
 * mirrors. The method source is not available from the jar and no bytecode library is on the
 * test classpath (and none may be added), so the whole {@code mage/players/PlayerImpl.class}
 * resource is hashed with SHA-256. Any repin that changes that class trips this test, which
 * is the cue to re-compare the mirror.
 */
class XmageMirroredEngineMethodPinTest {

    static final String PINNED_SHA256 = "708373ab3b3a5af2d1859db6dd81157bb46220ef35fe7839b670ca0636e82b5d";

    @Test
    void engineMirroredClassIsUnchanged() throws Exception {
        try (InputStream in = mage.players.PlayerImpl.class
                .getResourceAsStream("/mage/players/PlayerImpl.class")) {
            assertNotNull(in, "PlayerImpl.class is on the classpath");
            String actual = HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(in.readAllBytes()));
            assertEquals(PINNED_SHA256, actual,
                    "The engine's PlayerImpl changed. Re-compare "
                            + "XmageFullGamePlayer.manaAvailableInPlayableCalcCopy with "
                            + "PlayerImpl.getManaAvailable (docs/claude/REPIN_RUNBOOK.md), "
                            + "then update this digest.");
        }
    }
}
