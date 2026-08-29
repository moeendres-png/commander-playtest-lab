// SPDX-License-Identifier: GPL-3.0-or-later
package forge.game.player;

import forge.CardStorageReader;
import forge.StaticData;
import forge.util.Localizer;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Path;

/** GPL-side headless bootstrap. This class is compiled only into the separate Forge provider JVM. */
public final class Ws23ForgeBootstrap {
    private Ws23ForgeBootstrap() {}

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
        Localizer.getInstance().initialize("en-US", languagesDirectory.toString());

        Path root = forgeRoot(languagesDirectory);
        Path res = root.resolve("forge-gui/res");
        Path cards = res.resolve("cardsfolder");
        Path editions = res.resolve("editions");
        Path blockData = res.resolve("blockdata");
        if (!Files.isDirectory(cards) || !Files.isDirectory(editions) || !Files.isDirectory(blockData)) {
            throw new IllegalStateException("Pinned Forge runtime data directories are missing under " + res);
        }

        // Gate-A uses synthetic FAKE_CARD decks. Build the genuine Forge StaticData singleton lazily,
        // so normal game initialization has its required invariants without parsing/copying card scripts
        // into the proprietary process. All resources remain filesystem inputs to this GPL-side JVM.
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
