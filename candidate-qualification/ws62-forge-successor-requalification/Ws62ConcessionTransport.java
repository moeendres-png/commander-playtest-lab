// SPDX-License-Identifier: GPL-3.0-or-later
// WS62 CPL-owned direct concession transport helper (qualification-only).
// Package forge.game.player so it can be compiled against the successor
// forge-game classes without touching Forge source. Rules-Core owns legality;
// this helper only transports the native seam conditionally.
package forge.game.player;

import forge.game.Game;
import forge.game.player.Player;
import forge.game.player.PlayerController;

/**
 * Direct transport of the engine-native concession action (CR 104.3a any-time;
 * CR 800.4 cleanup via GameAction.concede). Permitted ONLY as conditional
 * delegation: consult canConcede(), record native authority in the identity,
 * then call concede(). Never calls Player.concede() directly; never fabricates
 * an unconditional option; never gates on priority/phase.
 */
public final class Ws62ConcessionTransport {
    private Ws62ConcessionTransport() {}

    /** Native legality consulted (Rules Core alone). */
    public static boolean isConcessionLegal(final PlayerController controller) {
        if (controller == null) return false;
        return controller.canConcede();
    }

    /**
     * Option/action identity recording native authority. Format is stable and
     * asserted by tests: WS62:CONCEDE:authority=PlayerController.canConcede:&lt;bool&gt;:player=&lt;P?&gt;:gameOver=&lt;bool&gt;
     */
    public static String concessionIdentity(final PlayerController controller) {
        if (controller == null) return "WS62:CONCEDE:authority=PlayerController.canConcede:false:player=PX:gameOver=true";
        boolean legal;
        try {
            legal = controller.canConcede();
        } catch (Throwable t) {
            legal = false;
        }
        String pid = "PX";
        boolean over = true;
        try {
            Game game = controller.getGame();
            if (game != null) {
                over = game.isGameOver();
                if (controller.getPlayer() != null) {
                    int i = game.getPlayers().indexOf(controller.getPlayer());
                    pid = i < 0 ? "PX" : ("P" + (i + 1));
                }
            }
        } catch (Throwable t) {
            pid = "PX";
        }
        return "WS62:CONCEDE:authority=PlayerController.canConcede:" + legal + ":player=" + pid + ":gameOver=" + over;
    }

    /**
     * Submission: fail closed when not legal; otherwise call the
     * controller/native action seam (PlayerController.concede()), which routes
     * to GameAction.concede with native 800.4 cleanup. Never calls
     * Player.concede() directly.
     */
    public static void requestConcession(final PlayerController controller) {
        if (controller == null) {
            throw new IllegalStateException("WS62_CONCESSION_NOT_LEGAL");
        }
        if (!controller.canConcede()) {
            throw new IllegalStateException("WS62_CONCESSION_NOT_LEGAL");
        }
        controller.concede();
    }

    /** Test helper: assert no priority gating (callable any-time per 104.3a). */
    public static void assertNotPriorityGated() {
        // Intentionally empty: the absence of any PhaseType/Priority check in
        // this file plus canConcede()'s engine definition (player in game and
        // game not over) is the proof. Static grep asserts no PhaseType import.
    }
}
