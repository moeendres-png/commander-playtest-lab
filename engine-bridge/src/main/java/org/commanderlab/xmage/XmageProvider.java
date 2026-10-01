package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.game.Game;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

final class XmageProvider {

    static final String ENGINE = "xmage";
    static final String ENGINE_VERSION = "1.4.61";
    static final String ENGINE_COMMIT =
            "4e59e8b9087878816b37728055eb61757a2fbf07";
    static final String PROTOCOL_VERSION = "2.0.0";

    private XmageProvider() {
    }

    static void verifyRuntimeLoaded() {
        if (Game.class.getProtectionDomain() == null
                || Game.class.getProtectionDomain().getCodeSource() == null) {
            throw new IllegalStateException(
                    "Unable to identify loaded XMage runtime"
            );
        }
    }

    /**
     * The cryptographic identity of the engine artifact the bridge actually
     * loaded, computed from the loaded {@code Game} class's own code source.
     *
     * <p>{@link #ENGINE_COMMIT} is a declared constant; this record is the
     * observed counterpart. Consumers that require exact engine identity (the
     * runtime fingerprint test, the PB-03 admission/runtime evidence and the
     * midgame probe receipt) fail closed when the kind is not {@code file} or
     * the digest is absent, so a directory, an unreadable artifact or a
     * hand-written claim can never satisfy them.</p>
     */
    record EngineArtifact(String kind, String path, String sha256, long size) {

        static final String KIND_FILE = "file";
        static final String KIND_DIRECTORY = "directory";
        static final String KIND_UNAVAILABLE = "unavailable";

        boolean digestPresent() {
            return sha256 != null && sha256.matches("[0-9a-f]{64}");
        }
    }

    static EngineArtifact engineArtifactIdentity() {
        verifyRuntimeLoaded();
        String location = Game.class.getProtectionDomain()
                .getCodeSource()
                .getLocation()
                .toString();
        Path path;
        try {
            path = Path.of(new URI(location));
        } catch (URISyntaxException | IllegalArgumentException exc) {
            return new EngineArtifact(EngineArtifact.KIND_UNAVAILABLE, location, null, 0L);
        }
        try {
            if (!Files.isRegularFile(path)) {
                String kind = Files.isDirectory(path)
                        ? EngineArtifact.KIND_DIRECTORY
                        : EngineArtifact.KIND_UNAVAILABLE;
                return new EngineArtifact(kind, location, null, 0L);
            }
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream stream = Files.newInputStream(path);
                 DigestInputStream digestStream = new DigestInputStream(stream, digest)) {
                byte[] buffer = new byte[8192];
                while (digestStream.read(buffer) != -1) {
                    // The digest is the product; the bytes are not retained.
                }
            }
            return new EngineArtifact(
                    EngineArtifact.KIND_FILE,
                    location,
                    HexFormat.of().formatHex(digest.digest()),
                    Files.size(path)
            );
        } catch (IOException | NoSuchAlgorithmException | RuntimeException exc) {
            return new EngineArtifact(EngineArtifact.KIND_UNAVAILABLE, location, null, 0L);
        }
    }

    static JsonObject providerVersion() {
        verifyRuntimeLoaded();

        JsonObject payload = new JsonObject();
        payload.addProperty("engine", ENGINE);
        payload.addProperty("engine_version", ENGINE_VERSION);
        payload.addProperty("engine_commit", ENGINE_COMMIT);
        payload.addProperty("protocol_version", PROTOCOL_VERSION);
        EngineArtifact artifact = engineArtifactIdentity();
        payload.addProperty("xmage_code_source", artifact.path());
        payload.addProperty("engine_artifact_kind", artifact.kind());
        payload.addProperty("engine_artifact_path", artifact.path());
        if (artifact.sha256() == null) {
            payload.add("engine_artifact_sha256", JsonNull.INSTANCE);
        } else {
            payload.addProperty("engine_artifact_sha256", artifact.sha256());
        }
        payload.addProperty("engine_artifact_size", artifact.size());
        return payload;
    }

    static JsonObject capabilitiesPayload() {
        JsonObject capabilities = new JsonObject();

        /*
         * B4-D retains the real B4-A/B4-B/B4-C state and action surfaces and
         * adds an externally exportable, monotonic audit event stream plus
         * explicit per-game XMage end/cleanup. The event stream records real
         * bridge/XMage lifecycle and externally controlled action boundaries;
         * it is deliberately not described as an exhaustive internal
         * mage.game.events.GameEvent tap.
         *
         * Global legal-actions/action-submission flags remain false because
         * target, mode, choice and combat classes are not yet complete.
         */
        capabilities.addProperty("commander_supported", true);
        capabilities.addProperty("partner_supported", true);
        capabilities.addProperty("multiplayer_supported", true);
        capabilities.addProperty("max_players", 5);
        capabilities.addProperty("headless_supported", true);
        /*
         * seed_supported: an explicit create-game seed is bound to XMage's
         * authoritative per-game Rules RNG before start (XmageRulesSeedBinding)
         * and acknowledged from engine readback. A game created without a seed
         * runs on the engine's non-credited default and reports
         * seed_controlled=false; it is never described as controlled.
         */
        capabilities.addProperty("seed_supported", true);
        capabilities.addProperty("deck_import_supported", true);
        capabilities.addProperty("legal_actions_supported", false);
        capabilities.addProperty("action_submission_supported", false);
        capabilities.addProperty("event_log_supported", true);
        capabilities.addProperty("replay_supported", false);
        capabilities.addProperty("stack_visible", true);
        capabilities.addProperty("priority_visible", true);
        capabilities.addProperty("commander_damage_visible", false);
        capabilities.addProperty("commander_tax_visible", false);
        capabilities.addProperty("starting_state_injection_supported", false);
        capabilities.addProperty("scenario_injection_supported", false);
        capabilities.addProperty("healthcheck_supported", true);
        capabilities.addProperty("target_selection_supported", false);
        capabilities.addProperty("mode_selection_supported", false);
        capabilities.addProperty("trigger_order_supported", false);
        capabilities.addProperty("mulligan_supported", false);
        capabilities.addProperty("concede_supported", false);
        capabilities.addProperty("game_shutdown_supported", true);
        capabilities.addProperty("engine_shutdown_supported", true);
        capabilities.addProperty("runtime_kind", "external_rules_engine");

        JsonArray notes = new JsonArray();
        notes.add(
                "B4-D real XMage bridge audit event log is externally exportable with monotonic sequence, action/decision identity and pre/post state hashes; it covers bridge lifecycle and externally controlled action boundaries and is not an exhaustive raw internal XMage GameEvent tap"
        );
        notes.add(
                "B4-D explicit per-game XMage end/cleanup and deck-handle release are implemented for repeated games in one bridge process"
        );
        notes.add(
                "B4-C bounded current-priority action control remains validated; global legal-action and action-submission completeness remain unavailable"
        );
        notes.add(
                "An explicit create-game seed is bound to the native per-game Rules RNG (setRulesSeed + requireExplicitSeed before start) and acknowledged from engine readback; unseeded games report seed_controlled=false and the seed value never appears in principal-scoped state"
        );
        notes.add("NO_PROVIDER_READY remains in force");
        capabilities.add("notes", notes);

        JsonObject result = new JsonObject();
        result.add("capabilities", capabilities);
        return result;
    }
}
