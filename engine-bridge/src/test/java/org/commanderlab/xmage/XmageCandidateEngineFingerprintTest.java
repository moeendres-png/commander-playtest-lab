package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.game.Game;
import org.junit.jupiter.api.Test;

import java.io.File;
import java.io.InputStream;
import java.lang.reflect.Field;
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
 * Successor-repin identity guard (2026-09-29, successor v2 2026-09-30, v3 2026-10-01,
 * v4 2026-10-03, v5 2026-10-11, v6 2026-10-13, v7 2026-10-16, v8 2026-10-17, v9 2026-10-20): the bridge
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

    static final String CANDIDATE = "043579bb7829fa866ade893909c9ba4825a18b23";

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
     *
     * <p>Successor v4 (2026-10-03): the CR 117.5 / 800.4a priority repair after
     * state-based player elimination (mage#41, a patch-identical port of master
     * mage#40) is a guard inside GameImpl.playPriority only, with no structural
     * signature. Its native regression PriorityEliminationTest runs in the
     * candidate's Mage.Tests; the declared commit and the artifact digest below
     * bind the loaded engine.</p>
     *
     * <p>Successor v5 (2026-10-11): the deterministic commander-zone ask order
     * (mage#57) replaces the identity-hash Set with a LinkedHashSet and sorts the
     * exile path by card name inside GameImpl.checkStateBasedActions only, so it
     * has no structural signature either. Its native regressions are the partner
     * ask-order scenarios CommanderZoneApnap3PTest, CommanderZoneApnap4PTest,
     * CommanderZoneApnap5PTest and CommanderZoneApnap6PTest in the candidate's
     * Mage.Tests, which ran on this exact commit (maven.yml run 38136235677); with
     * the declared commit and the artifact digest below they are the identity claim.</p>
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
     * Successor v6 (2026-10-13): the loaded engine carries the hooks of the precon
     * card coverage (mage#59): RequirementEffect.mustAttackDefenders and the
     * CONNIVED game event, plus the bulk set-card lookup of the card scanner
     * (mage#58). The precon cards themselves live in mage-sets; one of them must
     * load from the same classpath.
     */
    @Test
    void loadedEngineCarriesThePreconCoverageHooks() throws Exception {
        Method defenders = mage.abilities.effects.RequirementEffect.class.getMethod(
                "mustAttackDefenders", mage.abilities.Ability.class, Game.class);
        assertEquals(java.util.Set.class, defenders.getReturnType(),
                "mage#59: loaded engine is not the successor: "
                        + Game.class.getProtectionDomain().getCodeSource().getLocation());
        assertEquals("CONNIVED",
                mage.game.events.GameEvent.EventType.valueOf("CONNIVED").name());
        Method keys = mage.cards.repository.CardRepository.class
                .getMethod("findAllSetCodeAndCardNumberKeys");
        assertEquals(java.util.Set.class, keys.getReturnType(), "mage#58");
        Class<?> shuri = Class.forName("mage.cards.s.ShuriTheBlackPanther");
        assertTrue(mage.cards.Card.class.isAssignableFrom(shuri),
                "mage#59: loaded card set is not the successor's");
    }

    /**
     * Successor v7 (2026-10-16): the loaded engine carries the lazy card copy of the
     * playable calculation (mage#60): GameImpl keeps the ids of cards a playable
     * calculation copy still shares with its parent and copies a card on first read.
     */
    @Test
    void loadedEngineCarriesTheLazyPlayableCopy() throws Exception {
        Field shared = mage.game.GameImpl.class.getDeclaredField("sharedGameCards");
        assertEquals(java.util.Set.class, shared.getType(),
                "mage#60: loaded engine is not the successor: "
                        + Game.class.getProtectionDomain().getCodeSource().getLocation());
        Method lazy = mage.game.GameImpl.class.getDeclaredMethod(
                "copyCardsLazily", mage.game.GameImpl.class);
        assertEquals(void.class, lazy.getReturnType(), "mage#60");
        Method own = mage.game.GameImpl.class.getDeclaredMethod("ownGameCard", java.util.UUID.class);
        assertEquals(mage.cards.Card.class, own.getReturnType(), "mage#60");
    }

    /**
     * Successor v8 (2026-10-17): the loaded card set carries the seven enabled Strixhaven
     * prepare creatures (mage#61) and still hides the cards that are unfinished. Successor v9
     * (2026-10-20) keeps both checks against the updated unfinished list.
     */
    @Test
    void loadedCardSetCarriesTheEnabledPrepareCreatures() {
        java.util.Set<String> names = new java.util.HashSet<>();
        for (mage.cards.ExpansionSet.SetCardInfo info
                : mage.sets.SecretsOfStrixhaven.getInstance().getSetCardInfo()) {
            names.add(info.getName());
        }
        for (String enabled : new String[]{"Spellbook Seeker", "Sanar, Unfinished Genius",
                "Blazing Firesinger", "Cheerful Osteomancer", "Goblin Glasswright",
                "Studious First-Year", "Tam, Observant Sequencer"}) {
            assertTrue(names.contains(enabled),
                    "mage#61: loaded card set is not the successor's: " + enabled);
        }
        // Upstream finished Adventurous Eater after v8 (magefree/mage 8b3512e4), so the v9
        // update carries it. The cards that are still on the set's unfinished list stay hidden.
        assertTrue(names.contains("Adventurous Eater"), "v9: finished upstream card is missing");
        for (String unfinished : new String[]{"Decorum Dissertation", "Echocasting Symposium",
                "Germination Practicum", "Improvisation Capstone", "Restoration Seminar"}) {
            assertFalse(names.contains(unfinished), "v9: unfinished card is playable: " + unfinished);
        }
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
