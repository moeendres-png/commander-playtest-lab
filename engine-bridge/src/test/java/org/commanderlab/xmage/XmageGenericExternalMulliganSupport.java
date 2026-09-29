package org.commanderlab.xmage;

import com.google.gson.JsonObject;

import java.util.List;

/**
 * Test-only driver for the generic Protocol-2 external mulligan boundary.
 *
 * <p>Every choice is matched semantically against an option authored by the
 * live XMage decision controller. There is no first-option, ordering, random
 * or default keep policy hidden in this helper.</p>
 */
final class XmageGenericExternalMulliganSupport {

    private XmageGenericExternalMulliganSupport() {
    }

    static void keepAllToPriority(
            XmageGameManager manager,
            String gameHandle,
            int playerCount
    ) {
        for (int seat = 0; seat < playerCount; seat++) {
            XmageGameManager.LegalActionsSnapshot decision =
                    manager.legalActions(gameHandle);
            if (!"mulligan".equals(decision.decisionKind())) {
                throw new AssertionError(
                        "expected engine-authored mulligan decision for seat "
                                + seat + ", observed " + decision.decisionKind()
                );
            }
            requireDomain(decision);
            manager.resolveMulligan(
                    gameHandle,
                    decision.decisionId(),
                    decision.actorId(),
                    true,
                    List.of()
            );
        }

        XmageGameManager.LegalActionsSnapshot priority =
                manager.legalActions(gameHandle);
        if (!"priority".equals(priority.decisionKind())) {
            throw new AssertionError(
                    "expected priority after explicit keeps, observed "
                            + priority.decisionKind()
            );
        }
    }

    static void requireDomain(XmageGameManager.LegalActionsSnapshot decision) {
        List<JsonObject> mulliganActions = decision.actions().stream()
                .filter(action -> "mulligan".equals(
                        action.get("action_type").getAsString()))
                .toList();
        if (mulliganActions.size() != 2) {
            throw new AssertionError(
                    "expected exactly keep+mulligan, observed "
                            + mulliganActions.size()
            );
        }
        long keeps = mulliganActions.stream()
                .filter(action -> "keep".equals(optionType(action)))
                .count();
        long mulligans = mulliganActions.stream()
                .filter(action -> "mulligan".equals(optionType(action)))
                .count();
        if (keeps != 1L || mulligans != 1L) {
            throw new AssertionError(
                    "engine mulligan domain must contain exactly one keep and "
                            + "one mulligan; keep=" + keeps + " mulligan=" + mulligans
            );
        }
    }

    private static String optionType(JsonObject action) {
        if (!action.has("metadata") || !action.get("metadata").isJsonObject()) {
            return "";
        }
        JsonObject metadata = action.getAsJsonObject("metadata");
        return metadata.has("option_type")
                && !metadata.get("option_type").isJsonNull()
                ? metadata.get("option_type").getAsString()
                : "";
    }
}
