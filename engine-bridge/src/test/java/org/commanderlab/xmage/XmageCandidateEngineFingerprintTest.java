package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.game.Game;
import org.junit.jupiter.api.Test;

import java.io.File;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.net.URI;
import java.nio.file.Files;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Successor-repin identity guard (2026-09-29, successor v2 2026-09-30, v3 2026-10-01): the bridge
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

    static final String CANDIDATE = "37e4df6c914f1e189e24f0ef59fa91734c922436";

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

    /**
     * Successor v3 (2026-10-01): the loaded engine carries F-43's combat-damage
     * source revalidation (mage#29). F-44 (mage#33) changes behaviour inside
     * GameImpl.checkTriggered only and F-45 (mage#35) inside
     * PlayerImpl.moveObjectToLibrary only; neither has a structural signature.
     * Their native regressions TriggerOrderLeaver4PTest and SuddenSetbackCopyTest
     * run in the candidate's Mage.Tests.
     */
    @Test
    void loadedEngineCarriesTheF43Revalidation() throws Exception {
        Class<?> group = mage.game.combat.CombatGroup.class;
        Method revalidate = group.getDeclaredMethod("revalidateCombatDamageSource",
                mage.MageObjectReference.class, UUID.class, Game.class);
        assertEquals(mage.game.permanent.Permanent.class, revalidate.getReturnType(),
                "F-43: loaded engine is not the successor: "
                        + group.getProtectionDomain().getCodeSource().getLocation());
    }

    /**
     * The declared commit is a constant; this proves the artifact that actually
     * loaded has a reported, well-formed, independently reproducible SHA-256.
     *
     * <p>The expected digest is computed here from the loaded code source, not
     * hard-coded, so a rebuild at the same commit stays valid while any other
     * artifact (a stale cache entry, a directory classpath, a different jar)
     * fails. The provider version payload must carry exactly that digest.</p>
     */
    @Test
    void loadedEngineArtifactIdentityIsReportedAndExact() throws Exception {
        URI location = Game.class.getProtectionDomain().getCodeSource().getLocation().toURI();
        File artifact = new File(location);
        assertTrue(artifact.isFile(), "loaded engine artifact is not a file: " + location);

        String expectedDigest;
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream stream = Files.newInputStream(artifact.toPath());
             DigestInputStream digestStream = new DigestInputStream(stream, digest)) {
            byte[] buffer = new byte[8192];
            while (digestStream.read(buffer) != -1) {
                // digest only
            }
        }
        expectedDigest = HexFormat.of().formatHex(digest.digest());

        JsonObject version = XmageProvider.providerVersion();
        assertEquals("file", version.get("engine_artifact_kind").getAsString());
        assertEquals(artifact.getAbsolutePath(),
                new File(URI.create(version.get("engine_artifact_path").getAsString()))
                        .getAbsolutePath());
        String reported = version.get("engine_artifact_sha256").getAsString();
        assertTrue(reported.matches("[0-9a-f]{64}"), reported);
        assertEquals(expectedDigest, reported);
        assertEquals(artifact.length(), version.get("engine_artifact_size").getAsLong());
        assertFalse(XmageProvider.engineArtifactIdentity().sha256().isEmpty());
    }
}
