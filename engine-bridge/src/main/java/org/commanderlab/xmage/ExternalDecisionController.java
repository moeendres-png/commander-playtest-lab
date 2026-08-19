package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.abilities.ActivatedAbility;
import mage.constants.AbilityType;
import mage.game.Game;
import mage.players.Player;
import mage.target.Target;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * Process-local, fail-closed handoff state for externally controlled XMage decisions.
 *
 * <p>B4-B exposes only real priority decisions. It intentionally does not execute
 * actions and does not claim complete coverage of combat/choice dialogs yet.</p>
 */
final class ExternalDecisionController {

    record Decision(
            String gameId,
            String engineGameId,
            long decisionOffset,
            String decisionId,
            String actorId,
            String decisionKind,
            boolean complete,
            List<JsonObject> actions
    ) {
    }

    private Decision currentDecision;
    private long decisionOffset = 0L;

    synchronized Decision capturePriority(
            Player player,
            Game game
    ) {
        decisionOffset++;

        String gameId = game.getId().toString();
        String actorId = player.getId().toString();
        String decisionId = stableId(
                gameId,
                Long.toString(decisionOffset),
                actorId,
                "priority"
        );

        List<JsonObject> actions = new ArrayList<>();
        actions.add(
                legalAction(
                        decisionId,
                        0,
                        actorId,
                        "pass_priority",
                        null,
                        null,
                        true,
                        List.of(),
                        new JsonObject(),
                        new JsonObject()
                )
        );

        boolean complete = true;
        int ordinal = 1;

        List<ActivatedAbility> playable = new ArrayList<>(
                player.getPlayable(game, false)
        );
        playable.sort(
                Comparator
                        .comparing((ActivatedAbility ability) -> ability.getSourceId().toString())
                        .thenComparing(ability -> ability.getOriginalId().toString())
        );

        Set<UUID> commanderIds = game.getCommandersIds(player);

        for (ActivatedAbility ability : playable) {
            String actionType = actionType(ability, commanderIds);
            if (actionType == null) {
                complete = false;
                continue;
            }

            JsonArray allowedTargetIds = new JsonArray();
            JsonArray targetGroups = new JsonArray();
            boolean targetEnumerationComplete = true;

            for (Target target : ability.getTargets()) {
                JsonObject group = new JsonObject();
                group.addProperty("description", target.getDescription());
                group.addProperty("min", target.getMinNumberOfTargets());
                group.addProperty("max", target.getMaxNumberOfTargets());

                JsonArray possible = new JsonArray();
                try {
                    List<String> targetIds = target.possibleTargets(
                                    player.getId(),
                                    ability,
                                    game
                            )
                            .stream()
                            .map(UUID::toString)
                            .sorted()
                            .toList();
                    for (String id : targetIds) {
                        possible.add(id);
                        allowedTargetIds.add(id);
                    }
                } catch (RuntimeException exc) {
                    targetEnumerationComplete = false;
                    group.addProperty(
                            "enumeration_error",
                            exc.getClass().getSimpleName()
                    );
                }
                group.add("allowed_target_ids", possible);
                targetGroups.add(group);
            }

            JsonObject choicesSchema = new JsonObject();
            choicesSchema.add("target_groups", targetGroups);
            choicesSchema.addProperty(
                    "modal",
                    ability.isModal()
            );
            if (ability.isModal()) {
                JsonArray modes = new JsonArray();
                ability.getModes().forEach((id, mode) -> modes.add(id.toString()));
                choicesSchema.add("available_mode_ids", modes);
            } else {
                choicesSchema.add("available_mode_ids", new JsonArray());
            }

            JsonObject cost = new JsonObject();
            JsonArray mana = new JsonArray();
            ability.getManaCostSymbols().forEach(mana::add);
            cost.add("mana_symbols", mana);
            cost.addProperty("rule", ability.getRule(true));

            boolean submissionReady =
                    targetEnumerationComplete
                            && ability.getTargets().isEmpty()
                            && !ability.isModal();

            JsonObject metadata = new JsonObject();
            metadata.addProperty("decision_id", decisionId);
            metadata.addProperty("decision_offset", decisionOffset);
            metadata.addProperty(
                    "ability_original_id",
                    ability.getOriginalId().toString()
            );
            metadata.addProperty(
                    "ability_type",
                    ability.getAbilityType().name()
            );
            metadata.addProperty(
                    "submission_ready",
                    submissionReady
            );
            metadata.addProperty(
                    "target_enumeration_complete",
                    targetEnumerationComplete
            );
            metadata.addProperty(
                    "choice_control_required",
                    !ability.getTargets().isEmpty() || ability.isModal()
            );

            actions.add(
                    legalAction(
                            decisionId,
                            ordinal,
                            actorId,
                            actionType,
                            ability.getSourceId().toString(),
                            ability,
                            submissionReady,
                            jsonStrings(allowedTargetIds),
                            choicesSchema,
                            cost,
                            metadata
                    )
            );
            ordinal++;

            if (!targetEnumerationComplete) {
                complete = false;
            }
        }

        currentDecision = new Decision(
                gameId,
                gameId,
                decisionOffset,
                decisionId,
                actorId,
                "priority",
                complete,
                List.copyOf(actions)
        );

        return currentDecision;
    }

    synchronized Decision requireCurrentDecision(
            String engineGameId
    ) {
        if (currentDecision == null) {
            throw new IllegalStateException(
                    "NO_EXTERNAL_DECISION_AVAILABLE"
            );
        }
        if (!currentDecision.engineGameId().equals(engineGameId)) {
            throw new IllegalStateException(
                    "EXTERNAL_DECISION_GAME_MISMATCH"
            );
        }
        return currentDecision;
    }

    private static String actionType(
            ActivatedAbility ability,
            Set<UUID> commanderIds
    ) {
        AbilityType type = ability.getAbilityType();
        return switch (type) {
            case PLAY_LAND -> "play_land";
            case SPELL -> commanderIds.contains(ability.getSourceId())
                    ? "cast_commander"
                    : "cast_spell";
            case ACTIVATED_NONMANA, ACTIVATED_MANA, SPECIAL_ACTION -> "activate_ability";
            default -> null;
        };
    }

    private static JsonObject legalAction(
            String decisionId,
            int ordinal,
            String actorId,
            String actionType,
            String sourceObjectId,
            Ability ability,
            boolean submissionReady,
            List<String> allowedTargetIds,
            JsonObject choicesSchema,
            JsonObject cost
    ) {
        JsonObject metadata = new JsonObject();
        metadata.addProperty("decision_id", decisionId);
        metadata.addProperty("submission_ready", submissionReady);
        return legalAction(
                decisionId,
                ordinal,
                actorId,
                actionType,
                sourceObjectId,
                ability,
                submissionReady,
                allowedTargetIds,
                choicesSchema,
                cost,
                metadata
        );
    }

    private static JsonObject legalAction(
            String decisionId,
            int ordinal,
            String actorId,
            String actionType,
            String sourceObjectId,
            Ability ability,
            boolean submissionReady,
            List<String> allowedTargetIds,
            JsonObject choicesSchema,
            JsonObject cost,
            JsonObject metadata
    ) {
        String abilityId = ability == null
                ? "none"
                : ability.getOriginalId().toString();
        String sourceId = sourceObjectId == null
                ? "none"
                : sourceObjectId;

        JsonObject action = new JsonObject();
        action.addProperty(
                "action_id",
                stableId(
                        decisionId,
                        Integer.toString(ordinal),
                        actorId,
                        actionType,
                        sourceId,
                        abilityId
                )
        );
        action.addProperty("actor_id", actorId);
        action.addProperty("action_type", actionType);
        if (sourceObjectId == null) {
            action.add("source_object_id", com.google.gson.JsonNull.INSTANCE);
        } else {
            action.addProperty("source_object_id", sourceObjectId);
        }
        action.add("target_ids", new JsonArray());

        JsonArray targets = new JsonArray();
        allowedTargetIds.stream().distinct().sorted().forEach(targets::add);
        action.add("allowed_target_ids", targets);
        action.add("modes", new JsonArray());
        action.add("choices_schema", choicesSchema);
        action.add("cost", cost);
        metadata.addProperty("submission_ready", submissionReady);
        action.add("metadata", metadata);
        return action;
    }

    private static List<String> jsonStrings(JsonArray values) {
        List<String> result = new ArrayList<>();
        values.forEach(value -> result.add(value.getAsString()));
        return result;
    }

    private static String stableId(String... parts) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (String part : parts) {
                digest.update(part.getBytes(StandardCharsets.UTF_8));
                digest.update((byte) 0);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException exc) {
            throw new IllegalStateException("SHA-256 unavailable", exc);
        }
    }
}
