// SPDX-License-Identifier: GPL-3.0-or-later
package forge.game.player;

import forge.CardStorageReader;
import forge.StaticData;
import forge.util.Lang;
import forge.util.Localizer;
import forge.util.MyRandom;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Random;

/** GPL-side headless bootstrap. This class is compiled only into the separate Forge provider JVM. */
public final class Ws23ForgeBootstrap {
    public static final long QUALIFICATION_SEED = 230023L;

    private Ws23ForgeBootstrap() {}

    private static long configuredRulesSeed() {
        String raw = System.getenv("COMMANDER_LAB_FORGE_RULES_SEED");
        if (raw == null || raw.isBlank()) {
            return QUALIFICATION_SEED;
        }
        try {
            return Long.parseLong(raw);
        } catch (NumberFormatException e) {
            throw new IllegalStateException("COMMANDER_LAB_FORGE_RULES_SEED must be an integer", e);
        }
    }

    private static Path forgeRoot(Path languagesDirectory) {
        Path absolute = languagesDirectory.toAbsolutePath().normalize();
        Path res = absolute.getParent();
        Path forgeGui = res == null ? null : res.getParent();
        Path root = forgeGui == null ? null : forgeGui.getParent();
        if (root == null) {
            throw new IllegalStateException("Cannot derive Forge root from language directory: " + absolute);
        }
        return root;
    }

    private static void initializeHeadlessForge(Path languagesDirectory) throws Exception {
        MyRandom.setRandom(new Random(configuredRulesSeed()));
        Lang.createInstance("en-US");
        Localizer.getInstance().initialize("en-US", languagesDirectory.toString());

        Path root = forgeRoot(languagesDirectory);
        Path res = root.resolve("forge-gui/res");
        Path cards = res.resolve("cardsfolder");
        Path editions = res.resolve("editions");
        Path blockData = res.resolve("blockdata");
        if (!Files.isDirectory(cards) || !Files.isDirectory(editions) || !Files.isDirectory(blockData)) {
            throw new IllegalStateException("Pinned Forge runtime data directories are missing under " + res);
        }

        // Keep all Forge card/rules data inside this separate GPL-side process. The default seed preserves
        // WS-23/25 regressions; finalist convergence supplies the exact neutral record seed by environment.
        Path emptyCustomEditions = Files.createTempDirectory("ws23-forge-custom-editions-");
        CardStorageReader reader = new CardStorageReader(cards.toString(), null, true);
        StaticData data = new StaticData(
                reader,
                null,
                editions.toString(),
                emptyCustomEditions.toString(),
                blockData.toString(),
                "latest",
                true,
                true);
        data.setFilteredHandsEnabled(false);
    }

    public static void main(String[] args) throws Exception {
        String languagesDirectory = System.getenv("COMMANDER_LAB_FORGE_LANG_DIR");
        if (languagesDirectory == null || languagesDirectory.isBlank()) {
            throw new IllegalStateException("COMMANDER_LAB_FORGE_LANG_DIR is required");
        }

        // Forge bootstrap code writes informational output to System.out. WS-10R owns stdout,
        // so quarantine all pre-protocol Forge initialization chatter on stderr.
        PrintStream protocolStdout = System.out;
        try {
            System.setOut(System.err);
            initializeHeadlessForge(Path.of(languagesDirectory));
        } finally {
            System.setOut(protocolStdout);
        }

        Ws23ForgeVerticalProvider.main(args);
    }
}
