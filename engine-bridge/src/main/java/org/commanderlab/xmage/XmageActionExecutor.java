package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.ActivatedAbility;
import mage.cards.Card;
import mage.game.Game;
import mage.players.Player;

import java.util.List;
import java.util.UUID;

/**
 * Bounded B4-C executor for the live externally controlled XMage priority decision.
 *
 * <p>The executor never trusts a cached bridge proposal. Every mutation is checked
 * against the current live {@link XmageGameManager.LegalActionsSnapshot}, the live
 * XMage priority player and the current {@code Player.getPlayable(...)} set. Only
 * already-enumerated, submission-ready actions without unresolved target/mode
 * choices are executable in this slice.</p>
 */
final class XmageActionExecutor {

    record ExecutionResult(
            String decisionId,
            String actionId,
            String actionType,
            String actorId,
            String sourceObjectId,
            String sourceName
    ) {
    }

    static final class ActionException extends RuntimeException {
        ActionException(String message) {
            super(message);
        }
    }

    private XmageActionExecutor() {
    }

    static ExecutionResult passPriority(
            Game game,
            XmageGameManager.LegalActionsSnapshot current,
            String expectedDecisionId,
            String actorId,
            String actionId
    ) {
        Player player = requireCurrentPriority(
                game,
                current,
                expectedDecisionId,
                actorId
        );
        JsonObject action = requireAction(current, actionId);
        if (!"pass_priority".equals(stringValue(action, "action_type"))) {
            throw new ActionException(
                    "ACTION_TYPE_MISMATCH: PASS_PRIORITY requires the current pass_priority action"
            );
        }
        if (!actorId.equals(stringValue(action, "actor_id"))) {
            throw new ActionException("ACTION_ACTOR_MISMATCH");
        }

        player.pass(game);
        game.resume();

        return new ExecutionResult(
                current.decisionId(),
                actionId,
                "pass_priority",
                actorId,
                null,
                null
        );
    }

    static ExecutionResult submitAction(
            Game game,
            XmageGameManager.LegalActionsSnapshot current,
            String expectedDecisionId,
            JsonObject proposal
    ) {
        String actorId = requiredText(proposal, "actor_id");
        String actionId = requiredText(proposal, "legal_action_id");
        String proposalActionType = requiredText(proposal, "action_type");

        Player player = requireCurrentPriority(
                game,
                current,
                expectedDecisionId,
                actorId
        );
        JsonObject action = requireAction(current, actionId);
        String actionType = requiredText(action, "action_type");
        if ("pass_priority".equals(actionType)) {
            throw new ActionException(
                    "ACTION_TYPE_MISMATCH: use PASS_PRIORITY for the pass action"
            );
        }
        if (!actionType.equals(proposalActionType)) {
            throw new ActionException("ACTION_TYPE_MISMATCH");
        }
        if (!actorId.equals(requiredText(action, "actor_id"))) {
            throw new ActionException("ACTION_ACTOR_MISMATCH");
        }

        requireEmptyArray(proposal, "target_ids");
        requireEmptyArray(proposal, "selected_modes");
        requireEmptyObject(proposal, "choices");

        if (!action.has("metadata") || !action.get("metadata").isJsonObject()) {
            throw new ActionException("ACTION_METADATA_MISSING");
        }
        JsonObject metadata = action.getAsJsonObject("metadata");
        if (!booleanValue(metadata, "submission_ready")) {
            throw new ActionException(
                    "ACTION_NOT_SUBMISSION_READY: unresolved target/mode/choice control remains"
            );
        }
        if (booleanValue(metadata, "choice_control_required")) {
            throw new ActionException("ACTION_CHOICE_CONTROL_REQUIRED");
        }

        String sourceObjectId = requiredText(action, "source_object_id");
        String proposalSource = requiredText(proposal, "source_object_id");
        if (!sourceObjectId.equals(proposalSource)) {
            throw new ActionException("ACTION_SOURCE_MISMATCH");
        }
        String abilityOriginalId = requiredText(metadata, "ability_original_id");

        ActivatedAbility executable = null;
        for (ActivatedAbility ability : player.getPlayable(game, false)) {
            if (sourceObjectId.equals(ability.getSourceId().toString())
                    && abilityOriginalId.equals(ability.getOriginalId().toString())) {
                if (executable != null) {
                    throw new ActionException("AMBIGUOUS_EXECUTABLE_ACTION");
                }
                executable = ability;
            }
        }
        if (executable == null) {
            throw new ActionException(
                    "STALE_OR_UNPLAYABLE_EXTERNAL_ACTION: action is no longer in XMage getPlayable"
            );
        }

        Card sourceCard = game.getCard(executable.getSourceId());
        String sourceName = sourceCard == null ? null : sourceCard.getName();

        if (!player.activateAbility(executable, game)) {
            throw new ActionException("XMAGE_ACTION_EXECUTION_FAILED");
        }
        game.resume();

        return new ExecutionResult(
                current.decisionId(),
                actionId,
                actionType,
                actorId,
                sourceObjectId,
                sourceName
        );
    }

    private static Player requireCurrentPriority(
            Game game,
            XmageGameManager.LegalActionsSnapshot current,
            String expectedDecisionId,
            String actorId
    ) {
        if (!game.isPaused()) {
            throw new ActionException("EXTERNAL_ACTION_UNAVAILABLE: game is not paused");
        }
        if (!current.decisionId().equals(expectedDecisionId)) {
            throw new ActionException(
                    "STALE_EXTERNAL_DECISION: expected current decision " + current.decisionId()
            );
        }
        if (!current.actorId().equals(actorId)) {
            throw new ActionException("ACTION_ACTOR_MISMATCH");
        }
        if (game.getPriorityPlayerId() == null
                || !current.actorId().equals(game.getPriorityPlayerId().toString())) {
            throw new ActionException("XMAGE_PRIORITY_ACTOR_MISMATCH");
        }
        Player player = game.getPlayers().get(UUID.fromString(actorId));
        if (player == null) {
            throw new ActionException("UNKNOWN_ACTION_ACTOR");
        }
        return player;
    }

    private static JsonObject requireAction(
            XmageGameManager.LegalActionsSnapshot current,
            String actionId
    ) {
        List<JsonObject> matches = current.actions().stream()
                .filter(action -> actionId.equals(stringValue(action, "action_id")))
                .toList();
        if (matches.isEmpty()) {
            throw new ActionException(
                    "STALE_OR_UNKNOWN_EXTERNAL_ACTION: action is not in the current decision"
            );
        }
        if (matches.size() != 1) {
            throw new ActionException("AMBIGUOUS_EXTERNAL_ACTION_ID");
        }
        return matches.getFirst();
    }

    private static void requireEmptyArray(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return;
        }
        JsonElement value = object.get(property);
        if (!value.isJsonArray()) {
            throw new ActionException(property + " must be an array");
        }
        JsonArray array = value.getAsJsonArray();
        if (!array.isEmpty()) {
            throw new ActionException(
                    "ACTION_CHOICE_CONTROL_REQUIRED: " + property + " is not supported in B4-C"
            );
        }
    }

    private static void requireEmptyObject(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return;
        }
        JsonElement value = object.get(property);
        if (!value.isJsonObject()) {
            throw new ActionException(property + " must be an object");
        }
        if (!value.getAsJsonObject().isEmpty()) {
            throw new ActionException(
                    "ACTION_CHOICE_CONTROL_REQUIRED: " + property + " is not supported in B4-C"
            );
        }
    }

    private static String requiredText(JsonObject object, String property) {
        String value = stringValue(object, property).trim();
        if (value.isBlank()) {
            throw new ActionException("INVALID_ACTION_FIELD: " + property + " must be nonblank");
        }
        return value;
    }

    private static String stringValue(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return "";
        }
        return object.get(property).getAsString();
    }

    private static boolean booleanValue(JsonObject object, String property) {
        return object.has(property)
                && !object.get(property).isJsonNull()
                && object.get(property).getAsBoolean();
    }
}
