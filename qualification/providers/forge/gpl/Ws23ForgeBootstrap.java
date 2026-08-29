// SPDX-License-Identifier: GPL-3.0-or-later
package forge.game.player;

import forge.util.Localizer;

/** GPL-side headless bootstrap. This class is compiled only into the separate Forge provider JVM. */
public final class Ws23ForgeBootstrap {
    private Ws23ForgeBootstrap() {}

    public static void main(String[] args) throws Exception {
        String languagesDirectory = System.getenv("COMMANDER_LAB_FORGE_LANG_DIR");
        if (languagesDirectory == null || languagesDirectory.isBlank()) {
            throw new IllegalStateException("COMMANDER_LAB_FORGE_LANG_DIR is required");
        }
        Localizer.getInstance().initialize("en-US", languagesDirectory);
        Ws23ForgeVerticalProvider.main(args);
    }
}
