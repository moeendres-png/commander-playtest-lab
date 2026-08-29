// SPDX-License-Identifier: GPL-3.0-or-later
package forge.game.player;

import forge.util.Localizer;
import java.io.PrintStream;

/** GPL-side headless bootstrap. This class is compiled only into the separate Forge provider JVM. */
public final class Ws23ForgeBootstrap {
    private Ws23ForgeBootstrap() {}

    public static void main(String[] args) throws Exception {
        String languagesDirectory = System.getenv("COMMANDER_LAB_FORGE_LANG_DIR");
        if (languagesDirectory == null || languagesDirectory.isBlank()) {
            throw new IllegalStateException("COMMANDER_LAB_FORGE_LANG_DIR is required");
        }

        // Forge Localizer writes a bootstrap success message to System.out. WS-10R owns stdout,
        // so quarantine Forge bootstrap chatter on stderr and restore protocol stdout afterwards.
        PrintStream protocolStdout = System.out;
        try {
            System.setOut(System.err);
            Localizer.getInstance().initialize("en-US", languagesDirectory);
        } finally {
            System.setOut(protocolStdout);
        }

        Ws23ForgeVerticalProvider.main(args);
    }
}
