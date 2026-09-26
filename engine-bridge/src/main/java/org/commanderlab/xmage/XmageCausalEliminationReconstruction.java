package org.commanderlab.xmage;

import mage.players.Player;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * RG-05 causal elimination reconstruction.
 *
 * <p>This class never sets lost/left/eliminated flags and never injects a
 * terminal outcome. It causes a requested native spell transaction through the
 * already-qualified decision/action boundary, then observes XMage's own loss
 * and multiplayer cleanup result. All discretionary target/payment choices
 * remain externally supplied.</p>
 */
final class XmageCausalEliminationReconstruction {

    static final class EliminationException extends RuntimeException {
        EliminationException(String code, String detail) {
            super(code + ": " + detail);
        }
    }

    record Result(
            String eliminatedPlayer,
            Set<String> survivingPlayers,
            int submittedDecisions,
            List<String> decisionClasses
    ) {
    }

    private XmageCausalEliminationReconstruction() {
    }

    static Result castNativeCauseAndRequireElimination(
            XmageFullGameSession session,
            Map<String, Player> seats,
            String actorPid,
            String victimPid,
            UUID sourceCardId,
            XmageControlDivergenceReconstruction.DecisionSource decisionSource,
            int maxDecisions
    ) {
        if (session == null || seats == null || actorPid == null || victimPid == null
                || sourceCardId == null || decisionSource == null) {
            throw new EliminationException("INVALID_ELIMINATION_INPUT", "null input");
        }
        if (!seats.containsKey(actorPid)) {
            throw new EliminationException("UNKNOWN_ACTOR", actorPid);
        }
        if (!seats.containsKey(victimPid)) {
            throw new EliminationException("UNKNOWN_VICTIM", victimPid);
        }
        Player victim = seats.get(victimPid);
        if (victim.hasLost() || victim.hasLeft()) {
            throw new EliminationException(
                    "VICTIM_ALREADY_ELIMINATED", victimPid);
        }

        XmageControlDivergenceReconstruction.Result cause =
                XmageControlDivergenceReconstruction.castAndResolve(
                        session, seats, actorPid, sourceCardId, decisionSource, maxDecisions);

        XmageNativeStateRestoration.revalidate(session.restorationGame());
        if (!(victim.hasLost() || victim.hasLeft())) {
            throw new EliminationException(
                    "NATIVE_CAUSE_DID_NOT_ELIMINATE",
                    victimPid + " life=" + victim.getLife());
        }

        Set<String> survivors = new LinkedHashSet<>();
        for (Map.Entry<String, Player> entry : seats.entrySet()) {
            Player player = entry.getValue();
            if (!player.hasLost() && !player.hasLeft()) {
                survivors.add(entry.getKey());
            }
        }
        if (survivors.contains(victimPid)) {
            throw new EliminationException(
                    "ELIMINATED_PLAYER_RETAINED", victimPid);
        }
        if (survivors.isEmpty()) {
            throw new EliminationException(
                    "NO_SURVIVORS", "bounded multiplayer elimination expected survivors");
        }
        return new Result(
                victimPid,
                Set.copyOf(survivors),
                cause.submittedDecisions(),
                cause.decisionClasses());
    }
}
