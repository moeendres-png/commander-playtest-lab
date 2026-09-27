package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * WS204 B4-D generic decision projection for the dedicated full-game lane.
 *
 * <p>Representational boundary only. Legality originates exclusively in native
 * XMage callbacks parked in {@link XmageFullGameDecisionController}. This class
 * never enumerates playable abilities, never computes targets, costs, mana,
 * modes, or combat domains. It projects each exact pending
 * {@code legal_options} entry into a generic {@code LegalAction}-shaped object
 * and validates that a generic {@code ActionProposal}-shaped submission selects
 * only offered options for the exact current actor/decision/revision.</p>
 *
 * <p>Field convention (Option A, no schema migration):</p>
 * <ul>
 *   <li>{@code action_id} is opaque and decision-bound:
 *       {@code decision_id + ":" + option_id} for option-bearing decisions, or
 *       {@code decision_id + ":numeric"} for numeric-only decisions with zero
 *       options. Pilots must treat it as opaque; the bridge parses the prefix
 *       to bind revision.</li>
 *   <li>{@code metadata} carries the exact immutable decision identity
 *       ({@code decision_id}, {@code decision_offset}, {@code decision_class},
 *       {@code prompt}) plus the originating {@code option_id}/{@code option_type}.</li>
 *   <li>{@code choices_schema} describes the allowed response structure
 *       ({@code numeric_min/max}, {@code minimum/maximum_selections},
 *       {@code available_option_ids}).</li>
 *   <li>{@code ActionProposal.choices} may carry only
 *       {@code decision_id}, {@code decision_offset},
 *       {@code selected_option_ids}, {@code ordering}, {@code numeric_choice},
 *       {@code numeric_choices} (joint vector lane only).
 *       Any other key is rejected. {@code target_ids} and
 *       {@code selected_modes} must remain empty: mode/target selection travels
 *       exclusively through the decision-bound {@code legal_action_id} plus
 *       {@code choices} membership, never as caller-declared results.</li>
 * </ul>
 *
 * <p>{@code action_type} is a representational classification only. When no
 * existing type is semantically exact, {@code structural_decision} is used with
 * explicit safe metadata rather than a lie. No new {@code ActionType} is
 * introduced: the missing categories are decision-scoped, not genuinely
 * generic transport gaps.</p>
 */
final class XmageFullGameActionProjection {

    static final String NUMERIC_SUFFIX = "numeric";

    private static final Set<String> ALLOWED_PROPOSAL_CHOICE_KEYS = Set.of(
            "decision_id",
            "decision_offset",
            "selected_option_ids",
            "ordering",
            "numeric_choice",
            "numeric_choices"
    );

    private XmageFullGameActionProjection() {
    }

    static final class ProjectionException extends RuntimeException {
        ProjectionException(String message) {
            super(message);
        }
    }

    /**
     * Project one exact pending full-game decision into generic actions.
     * One action per offered native option; exactly one numeric action when the
     * pending decision carries zero options plus numeric bounds.
     */
    static JsonArray project(JsonObject pending) {
        if (pending == null) {
            throw new ProjectionException("STALE_DECISION: no pending decision");
        }
        String decisionId = requiredText(pending, "decision_id");
        String actorId = requiredText(pending, "actor_id");
        String decisionClass = requiredText(pending, "decision_class");
        int min = pending.has("minimum_selections") && !pending.get("minimum_selections").isJsonNull()
                ? pending.get("minimum_selections").getAsInt() : 0;
        int max = pending.has("maximum_selections") && !pending.get("maximum_selections").isJsonNull()
                ? pending.get("maximum_selections").getAsInt() : 0;
        String prompt = pending.has("prompt") && !pending.get("prompt").isJsonNull()
                ? pending.get("prompt").getAsString() : "";
        long offset = pending.has("decision_offset") && !pending.get("decision_offset").isJsonNull()
                ? pending.get("decision_offset").getAsLong() : -1L;
        JsonArray legalOptions = pending.has("legal_options") && pending.get("legal_options").isJsonArray()
                ? pending.getAsJsonArray("legal_options") : new JsonArray();
        JsonObject context = pending.has("context") && pending.get("context").isJsonObject()
                ? pending.getAsJsonObject("context") : new JsonObject();
        JsonObject sourceObject = pending.has("source_object") && pending.get("source_object").isJsonObject()
                ? pending.getAsJsonObject("source_object") : null;

        String sourceObjectId = extractSourceObjectId(sourceObject);

        JsonArray actions = new JsonArray();
        if (legalOptions.size() == 0) {
            if ((!context.has("numeric_min") || !context.has("numeric_max"))
                    && !hasJointLegs(context)) {
                return actions;
            }
            actions.add(numericAction(
                    pending, decisionId, actorId, decisionClass, prompt, min, max, offset,
                    context, sourceObject, sourceObjectId
            ));
            return actions;
        }

        List<String> availableIds = new ArrayList<>(legalOptions.size());
        for (JsonElement element : legalOptions) {
            JsonObject option = element.getAsJsonObject();
            String optionId = option.has("option_id") && !option.get("option_id").isJsonNull()
                    ? option.get("option_id").getAsString() : "";
            if (!optionId.isBlank()) {
                availableIds.add(optionId);
            }
        }

        for (JsonElement element : legalOptions) {
            JsonObject option = element.getAsJsonObject();
            String optionId = option.has("option_id") && !option.get("option_id").isJsonNull()
                    ? option.get("option_id").getAsString() : "";
            String optionType = option.has("option_type") && !option.get("option_type").isJsonNull()
                    ? option.get("option_type").getAsString() : "generic";
            String label = option.has("label") && !option.get("label").isJsonNull()
                    ? option.get("label").getAsString() : optionId;
            JsonObject optionMetadata = option.has("metadata") && option.get("metadata").isJsonObject()
                    ? option.getAsJsonObject("metadata").deepCopy() : new JsonObject();

            String actionType = actionTypeFor(decisionClass, optionType, optionMetadata);
            String actionId = decisionId + ":" + optionId;

            JsonObject action = new JsonObject();
            action.addProperty("action_id", actionId);
            action.addProperty("actor_id", actorId);
            action.addProperty("action_type", actionType);
            if (sourceObjectId == null) {
                action.add("source_object_id", JsonNull.INSTANCE);
            } else {
                action.addProperty("source_object_id", sourceObjectId);
            }
            action.add("target_ids", new JsonArray());

            JsonArray allowedTargets = new JsonArray();
            if (isUuid(optionId) && isTargetLike(decisionClass)) {
                allowedTargets.add(optionId);
            }
            action.add("allowed_target_ids", allowedTargets);

            JsonArray modes = new JsonArray();
            if ("mode".equals(decisionClass)) {
                modes.add(optionId);
            }
            action.add("modes", modes);
            action.add("choices_schema", choicesSchema(
                    decisionId, offset, decisionClass, min, max, context, availableIds,
                    "options"
            ));
            action.add("cost", costFor(decisionClass, context, optionMetadata));

            JsonObject metadata = new JsonObject();
            metadata.addProperty("decision_id", decisionId);
            metadata.addProperty("decision_offset", offset);
            metadata.addProperty("decision_class", decisionClass);
            metadata.addProperty("prompt", prompt);
            if (pending.has("seat") && !pending.get("seat").isJsonNull()) {
                try {
                    metadata.addProperty("seat", pending.get("seat").getAsInt());
                } catch (RuntimeException ignored) {
                    // Seat is informational; never a second authority.
                }
            }
            metadata.addProperty("minimum_selections", min);
            metadata.addProperty("maximum_selections", max);
            metadata.addProperty("option_id", optionId);
            metadata.addProperty("option_type", optionType);
            metadata.addProperty("label", label);
            metadata.add("xmage_option_metadata", optionMetadata);
            if (sourceObject != null) {
                metadata.add("source_object", sourceObject.deepCopy());
            }
            action.add("metadata", metadata);
            actions.add(action);
        }
        return actions;
    }

    /**
     * Translate a generic proposal into the exact controller response for the
     * current pending decision. Validates actor, revision, membership, types,
     * bounds, ordering, and forbids undeclared target/mode/choice smuggling.
     */
    static JsonObject toDecisionResponse(JsonObject pending, JsonObject proposal) {
        if (pending == null) {
            throw new ProjectionException("STALE_DECISION: no pending decision");
        }
        if (proposal == null) {
            throw new ProjectionException("PILOT_RESPONSE_INVALID: proposal is null");
        }
        String decisionId = requiredText(pending, "decision_id");
        String actorId = requiredText(pending, "actor_id");
        String decisionClass = requiredText(pending, "decision_class");
        int min = pending.has("minimum_selections") && !pending.get("minimum_selections").isJsonNull()
                ? pending.get("minimum_selections").getAsInt() : 0;
        int max = pending.has("maximum_selections") && !pending.get("maximum_selections").isJsonNull()
                ? pending.get("maximum_selections").getAsInt() : 0;
        long offset = pending.has("decision_offset") && !pending.get("decision_offset").isJsonNull()
                ? pending.get("decision_offset").getAsLong() : -1L;
        JsonArray legalOptions = pending.has("legal_options") && pending.get("legal_options").isJsonArray()
                ? pending.getAsJsonArray("legal_options") : new JsonArray();
        JsonObject context = pending.has("context") && pending.get("context").isJsonObject()
                ? pending.getAsJsonObject("context") : new JsonObject();

        Map<String, JsonObject> offeredById = new LinkedHashMap<>();
        for (JsonElement element : legalOptions) {
            JsonObject option = element.getAsJsonObject();
            if (option.has("option_id") && !option.get("option_id").isJsonNull()) {
                offeredById.put(option.get("option_id").getAsString(), option);
            }
        }
        boolean numericOnly = offeredById.isEmpty()
                && context.has("numeric_min") && context.has("numeric_max");
        boolean jointOnly = offeredById.isEmpty() && hasJointLegs(context);

        String legalActionId = proposal.has("legal_action_id") && !proposal.get("legal_action_id").isJsonNull()
                ? proposal.get("legal_action_id").getAsString().trim() : "";

        JsonObject choices = proposal.has("choices") && !proposal.get("choices").isJsonNull()
                ? proposal.getAsJsonObject("choices") : new JsonObject();
        if (!choices.isJsonObject()) {
            throw new ProjectionException("PILOT_RESPONSE_INVALID: choices must be an object");
        }
        for (Map.Entry<String, JsonElement> entry : choices.entrySet()) {
            if (!ALLOWED_PROPOSAL_CHOICE_KEYS.contains(entry.getKey())) {
                throw new ProjectionException(
                        "PILOT_RESPONSE_INVALID: forbidden choice field: " + entry.getKey()
                );
            }
        }
        if (choices.has("decision_id") && !choices.get("decision_id").isJsonNull()) {
            String choicesDecision = choices.get("decision_id").getAsString().trim();
            if (!decisionId.equals(choicesDecision)) {
                throw new ProjectionException("STALE_DECISION: expected " + decisionId);
            }
        }
        if (choices.has("decision_offset") && !choices.get("decision_offset").isJsonNull()) {
            try {
                long choicesOffset = choices.get("decision_offset").getAsLong();
                if (choicesOffset != offset) {
                    throw new ProjectionException("STALE_DECISION: expected offset " + offset);
                }
            } catch (ProjectionException exc) {
                throw exc;
            } catch (RuntimeException exc) {
                throw new ProjectionException("PILOT_RESPONSE_INVALID: decision_offset must be integer");
            }
        }

        // Revision binding precedes actor binding so a replayed prior decision
        // is unambiguously STALE even when the next pending actor differs.
        // This mirrors XmageFullGameDecisionController.submit() order.
        if (!legalActionId.isBlank()) {
            String[] prefix = splitActionIdLenient(legalActionId);
            if (prefix != null && !decisionId.equals(prefix[0])) {
                throw new ProjectionException("STALE_DECISION: expected " + decisionId);
            }
        }

        String proposalActor = requiredText(proposal, "actor_id");
        if (!actorId.equals(proposalActor)) {
            throw new ProjectionException("PILOT_RESPONSE_INVALID: wrong actor");
        }

        requireEmptyArray(proposal, "target_ids");
        requireEmptyArray(proposal, "selected_modes");

        if (proposal.has("source_object_id") && !proposal.get("source_object_id").isJsonNull()) {
            String proposalSource = proposal.get("source_object_id").getAsString().trim();
            String expectedSource = extractSourceObjectId(
                    pending.has("source_object") && pending.get("source_object").isJsonObject()
                            ? pending.getAsJsonObject("source_object") : null
            );
            if (expectedSource == null) {
                if (!proposalSource.isBlank()) {
                    throw new ProjectionException("PILOT_RESPONSE_INVALID: unexpected source_object_id");
                }
            } else if (!expectedSource.equals(proposalSource)) {
                throw new ProjectionException("PILOT_RESPONSE_INVALID: source_object_id mismatch");
            }
        }

        List<String> ordering = stringArray(choices, "ordering");
        for (String orderedId : ordering) {
            if (!offeredById.containsKey(orderedId)) {
                throw new ProjectionException(
                        "PILOT_RESPONSE_INVALID: ordering contains unknown option"
                );
            }
        }

        boolean hasNumericBounds = context.has("numeric_min") && context.has("numeric_max");
        Integer numericChoice = null;
        if (choices.has("numeric_choice") && !choices.get("numeric_choice").isJsonNull()) {
            try {
                numericChoice = strictInt(choices.get("numeric_choice"));
            } catch (RuntimeException exc) {
                throw new ProjectionException("PILOT_RESPONSE_INVALID: numeric_choice must be integer");
            }
        }
        List<Integer> numericChoices = optionalIntegerArray(choices);
        if (numericChoice != null && numericChoices != null) {
            throw new ProjectionException(
                    "PILOT_RESPONSE_INVALID: numeric_choice and numeric_choices are mutually exclusive"
            );
        }
        if (hasNumericBounds) {
            int numericMin = context.get("numeric_min").getAsInt();
            int numericMax = context.get("numeric_max").getAsInt();
            if (numericOnly || requiresNumeric(decisionClass)) {
                if (numericChoice == null) {
                    throw new ProjectionException(
                            "PILOT_RESPONSE_INVALID: numeric choice required for " + decisionClass
                    );
                }
                if (numericChoice < numericMin || numericChoice > numericMax) {
                    throw new ProjectionException(
                            "PILOT_RESPONSE_INVALID: numeric choice out of range"
                    );
                }
            } else if (numericChoice != null) {
                if (numericChoice < numericMin || numericChoice > numericMax) {
                    throw new ProjectionException(
                            "PILOT_RESPONSE_INVALID: numeric choice out of range"
                    );
                }
            }
            if (numericChoices != null) {
                throw new ProjectionException(
                        "PILOT_RESPONSE_INVALID: numeric_choices not authorized by decision schema"
                );
            }
        } else if (numericChoice != null) {
            throw new ProjectionException(
                    "PILOT_RESPONSE_INVALID: numeric_choice not authorized by decision schema"
            );
        }
        // WS229 joint vector lane: the joint frame authorizes numeric_choices
        // only. A scalar numeric_choice on a joint frame is schema confusion.
        if (hasJointLegs(context)) {
            if (numericChoices == null) {
                throw new ProjectionException(
                        "PILOT_RESPONSE_INVALID: joint numeric choices required for "
                                + decisionClass
                );
            }
            validateJointVector(numericChoices, context);
        } else if (numericChoices != null) {
            throw new ProjectionException(
                    "PILOT_RESPONSE_INVALID: numeric_choices not authorized by decision schema"
            );
        }

        if (jointOnly) {
            if (legalActionId.isBlank()) {
                throw new ProjectionException("PILOT_RESPONSE_INVALID: legal_action_id is required");
            }
            String[] parts = splitActionId(legalActionId);
            if (!decisionId.equals(parts[0])) {
                throw new ProjectionException("STALE_DECISION: expected " + decisionId);
            }
            if (!NUMERIC_SUFFIX.equals(parts[1])) {
                throw new ProjectionException("ILLEGAL_ACTION: option not offered by XMage: " + parts[1]);
            }
            String proposalType = proposal.has("action_type") && !proposal.get("action_type").isJsonNull()
                    ? proposal.get("action_type").getAsString().trim() : "";
            if (!"structural_decision".equals(proposalType)) {
                throw new ProjectionException("ACTION_TYPE_MISMATCH: numeric decision requires structural_decision");
            }
            if (!ordering.isEmpty()) {
                throw new ProjectionException("PILOT_RESPONSE_INVALID: ordering not authorized here");
            }
            JsonObject response = new JsonObject();
            response.addProperty("decision_id", decisionId);
            response.addProperty("actor_id", actorId);
            response.add("selected_option_ids", new JsonArray());
            response.add("ordering", new JsonArray());
            response.add("numeric_choice", JsonNull.INSTANCE);
            JsonArray vector = new JsonArray();
            numericChoices.forEach(vector::add);
            response.add("numeric_choices", vector);
            return response;
        }

        if (numericOnly) {
            if (legalActionId.isBlank()) {
                throw new ProjectionException("PILOT_RESPONSE_INVALID: legal_action_id is required");
            }
            String[] parts = splitActionId(legalActionId);
            if (!decisionId.equals(parts[0])) {
                throw new ProjectionException("STALE_DECISION: expected " + decisionId);
            }
            if (!NUMERIC_SUFFIX.equals(parts[1])) {
                throw new ProjectionException("ILLEGAL_ACTION: option not offered by XMage: " + parts[1]);
            }
            String proposalType = proposal.has("action_type") && !proposal.get("action_type").isJsonNull()
                    ? proposal.get("action_type").getAsString().trim() : "";
            if (!"structural_decision".equals(proposalType)) {
                throw new ProjectionException("ACTION_TYPE_MISMATCH: numeric decision requires structural_decision");
            }
            if (!ordering.isEmpty()) {
                throw new ProjectionException("PILOT_RESPONSE_INVALID: ordering not authorized here");
            }
            JsonObject response = new JsonObject();
            response.addProperty("decision_id", decisionId);
            response.addProperty("actor_id", actorId);
            response.add("selected_option_ids", new JsonArray());
            response.add("ordering", new JsonArray());
            response.addProperty("numeric_choice", numericChoice);
            return response;
        }

        List<String> selected;
        if (choices.has("selected_option_ids") && !choices.get("selected_option_ids").isJsonNull()) {
            if (!choices.get("selected_option_ids").isJsonArray()) {
                throw new ProjectionException("PILOT_RESPONSE_INVALID: selected_option_ids must be an array");
            }
            selected = new ArrayList<>();
            for (JsonElement element : choices.getAsJsonArray("selected_option_ids")) {
                if (!element.isJsonPrimitive() || !element.getAsJsonPrimitive().isString()) {
                    throw new ProjectionException("PILOT_RESPONSE_INVALID: non-string in selected_option_ids");
                }
                selected.add(element.getAsString());
            }
            if (legalActionId.isBlank()) {
                if (!(selected.isEmpty() && min == 0)) {
                    throw new ProjectionException("PILOT_RESPONSE_INVALID: legal_action_id is required");
                }
            } else {
                String[] parts = splitActionId(legalActionId);
                if (!decisionId.equals(parts[0])) {
                    throw new ProjectionException("STALE_DECISION: expected " + decisionId);
                }
                if (!offeredById.containsKey(parts[1])) {
                    throw new ProjectionException(
                            "ILLEGAL_ACTION: option not offered by XMage: " + parts[1]
                    );
                }
                if (!selected.contains(parts[1])) {
                    throw new ProjectionException(
                            "PILOT_RESPONSE_INVALID: legal_action_id is not in selected_option_ids"
                    );
                }
            }
        } else {
            if (legalActionId.isBlank()) {
                if (min == 0) {
                    selected = List.of();
                } else {
                    throw new ProjectionException("PILOT_RESPONSE_INVALID: legal_action_id is required");
                }
            } else {
                String[] parts = splitActionId(legalActionId);
                if (!decisionId.equals(parts[0])) {
                    throw new ProjectionException("STALE_DECISION: expected " + decisionId);
                }
                if (!offeredById.containsKey(parts[1])) {
                    throw new ProjectionException(
                            "ILLEGAL_ACTION: option not offered by XMage: " + parts[1]
                    );
                }
                selected = List.of(parts[1]);
            }
        }

        if (selected.size() < min || selected.size() > max) {
            throw new ProjectionException(
                    "PILOT_RESPONSE_INVALID: selected " + selected.size()
                            + " options, expected " + min + ".." + max
            );
        }
        if (new HashSet<>(selected).size() != selected.size()) {
            throw new ProjectionException("PILOT_RESPONSE_INVALID: duplicate option id");
        }
        for (String optionId : selected) {
            if (!offeredById.containsKey(optionId)) {
                throw new ProjectionException(
                        "ILLEGAL_ACTION: option not offered by XMage: " + optionId
                );
            }
        }

        if (!legalActionId.isBlank()) {
            String[] parts = splitActionId(legalActionId);
            if (offeredById.containsKey(parts[1])) {
                JsonObject option = offeredById.get(parts[1]);
                String optionType = option.has("option_type") && !option.get("option_type").isJsonNull()
                        ? option.get("option_type").getAsString() : "generic";
                JsonObject optionMetadata = option.has("metadata") && option.get("metadata").isJsonObject()
                        ? option.getAsJsonObject("metadata") : new JsonObject();
                String expectedType = actionTypeFor(decisionClass, optionType, optionMetadata);
                String proposalType = proposal.has("action_type") && !proposal.get("action_type").isJsonNull()
                        ? proposal.get("action_type").getAsString().trim() : "";
                if (!expectedType.equals(proposalType)) {
                    throw new ProjectionException(
                            "ACTION_TYPE_MISMATCH: expected " + expectedType + " for " + optionType
                    );
                }
            }
        } else if (proposal.has("action_type") && !proposal.get("action_type").isJsonNull()) {
            String proposalType = proposal.get("action_type").getAsString().trim();
            if (!proposalType.isBlank() && !"structural_decision".equals(proposalType)) {
                throw new ProjectionException(
                        "ACTION_TYPE_MISMATCH: empty selection requires structural_decision"
                );
            }
        }

        JsonObject response = new JsonObject();
        response.addProperty("decision_id", decisionId);
        response.addProperty("actor_id", actorId);
        JsonArray selectedJson = new JsonArray();
        selected.forEach(selectedJson::add);
        response.add("selected_option_ids", selectedJson);
        JsonArray orderingJson = new JsonArray();
        ordering.forEach(orderingJson::add);
        response.add("ordering", orderingJson);
        if (numericChoice == null) {
            response.add("numeric_choice", JsonNull.INSTANCE);
        } else {
            response.addProperty("numeric_choice", numericChoice);
        }
        return response;
    }

    /**
     * Representational classification only. Never computes legality. Unknown
     * combinations map to {@code structural_decision} with explicit metadata
     * rather than a semantic lie.
     */
    static String actionTypeFor(String decisionClass, String optionType, JsonObject optionMetadata) {
        String dc = decisionClass == null ? "" : decisionClass.trim();
        String ot = optionType == null ? "" : optionType.trim();
        if ("priority".equals(dc) && "pass_priority".equals(ot)) {
            return "pass_priority";
        }
        if ("priority".equals(dc)) {
            String abilityType = optionMetadata != null
                    && optionMetadata.has("ability_type")
                    && !optionMetadata.get("ability_type").isJsonNull()
                    ? optionMetadata.get("ability_type").getAsString().trim().toLowerCase() : "";
            if ("play_land".equals(abilityType)) {
                return "play_land";
            }
            return "activate_ability";
        }
        if ("mulligan".equals(dc)) {
            return "mulligan";
        }
        if ("target".equals(dc) || "choose_object".equals(dc) || "target_amount".equals(dc)) {
            return "choose_targets";
        }
        if ("choose".equals(dc) && "choice".equals(ot)) {
            return "structural_decision";
        }
        if ("choice".equals(dc)) {
            if ("play_land_ability".equals(ot)) {
                return "play_land";
            }
            return "structural_decision";
        }
        if ("mode".equals(dc)) {
            return "choose_mode";
        }
        if ("mana_payment".equals(dc)) {
            return "pay_cost";
        }
        if ("declare_attacker".equals(dc)) {
            return "declare_attackers";
        }
        if ("declare_blocker".equals(dc)) {
            return "declare_blockers";
        }
        if ("choose_use".equals(dc)
                || "pile".equals(dc)
                || "replacement_effect".equals(dc)
                || "trigger_order".equals(dc)
                || "announce_x".equals(dc)
                || "amount".equals(dc)
                || "multi_amount".equals(dc)) {
            return "structural_decision";
        }
        if ("pass_priority".equals(ot)) {
            return "pass_priority";
        }
        if ("play_land_ability".equals(ot)) {
            return "play_land";
        }
        if ("keep".equals(ot) || "mulligan".equals(ot)) {
            return "mulligan";
        }
        if ("mode".equals(ot)) {
            return "choose_mode";
        }
        if ("declare_attacker".equals(ot) || "hold_attacker".equals(ot)) {
            return "declare_attackers";
        }
        if ("declare_blocker".equals(ot)) {
            return "declare_blockers";
        }
        if ("target".equals(ot) || "choice".equals(ot) || "target_amount".equals(ot)) {
            return "choose_targets";
        }
        if ("mana_pool".equals(ot) || "mana_ability".equals(ot) || "cancel_mana_payment".equals(ot)) {
            return "pay_cost";
        }
        return "structural_decision";
    }

        private static boolean requiresNumeric(String decisionClass) {
        return "announce_x".equals(decisionClass)
                || "amount".equals(decisionClass)
                || "multi_amount".equals(decisionClass);
    }

    /** WS229: a joint frame carries its authoritative legs as a context array. */
    private static boolean hasJointLegs(JsonObject context) {
        return context != null
                && context.has("numeric_legs")
                && context.get("numeric_legs").isJsonArray();
    }

    /** WS229: strict integer — strings, booleans, and fractionals fail closed. */
    private static int strictInt(JsonElement element) {
        if (!element.isJsonPrimitive() || !element.getAsJsonPrimitive().isNumber()) {
            throw new ProjectionException("not an integer");
        }
        double asDouble = element.getAsJsonPrimitive().getAsDouble();
        int asInt = element.getAsJsonPrimitive().getAsInt();
        if (asDouble != (double) asInt) {
            throw new ProjectionException("not an integer");
        }
        return asInt;
    }

    /** WS229: strict integer array for the joint vector lane. */
    private static List<Integer> optionalIntegerArray(JsonObject choices) {
        if (!choices.has("numeric_choices") || choices.get("numeric_choices").isJsonNull()) {
            return null;
        }
        if (!choices.get("numeric_choices").isJsonArray()) {
            throw new ProjectionException("PILOT_RESPONSE_INVALID: numeric_choices must be an array");
        }
        List<Integer> values = new ArrayList<>();
        for (JsonElement element : choices.getAsJsonArray("numeric_choices")) {
            try {
                values.add(strictInt(element));
            } catch (ProjectionException exc) {
                throw new ProjectionException(
                        "PILOT_RESPONSE_INVALID: non-integer element in numeric_choices");
            }
        }
        return values;
    }

    /**
     * WS229 joint isGoodValues projection for the generic-submission lane.
     * Mirrors the controller transport check: exact length, per-leg
     * membership, total band. Bounds come verbatim from the pending frame.
     */
    private static void validateJointVector(List<Integer> vector, JsonObject context) {
        JsonArray legs = context.getAsJsonArray("numeric_legs");
        if (!context.has("numeric_total_min") || !context.has("numeric_total_max")) {
            throw new ProjectionException(
                    "BRIDGE_PROTOCOL_ERROR: joint frame is missing its total band");
        }
        int totalMin;
        int totalMax;
        try {
            totalMin = strictInt(context.get("numeric_total_min"));
            totalMax = strictInt(context.get("numeric_total_max"));
        } catch (ProjectionException exc) {
            throw new ProjectionException(
                    "BRIDGE_PROTOCOL_ERROR: joint frame total band is malformed");
        }
        if (vector.size() != legs.size()) {
            throw new ProjectionException(
                    "PILOT_RESPONSE_INVALID: joint vector length " + vector.size()
                            + " differs from legs " + legs.size());
        }
        int total = 0;
        for (int index = 0; index < legs.size(); index++) {
            JsonElement legElement = legs.get(index);
            if (!legElement.isJsonObject()) {
                throw new ProjectionException(
                        "BRIDGE_PROTOCOL_ERROR: joint frame leg " + index + " is malformed");
            }
            JsonObject leg = legElement.getAsJsonObject();
            int legMin;
            int legMax;
            try {
                legMin = strictInt(leg.get("min"));
                legMax = strictInt(leg.get("max"));
            } catch (RuntimeException exc) {
                throw new ProjectionException(
                        "BRIDGE_PROTOCOL_ERROR: joint frame leg " + index + " is malformed");
            }
            int value = vector.get(index);
            if (value < legMin || value > legMax) {
                throw new ProjectionException(
                        "PILOT_RESPONSE_INVALID: joint leg " + index + " value " + value
                                + " out of range " + legMin + ".." + legMax);
            }
            total += value;
        }
        if (total < totalMin || total > totalMax) {
            throw new ProjectionException(
                    "PILOT_RESPONSE_INVALID: joint total " + total
                            + " outside " + totalMin + ".." + totalMax);
        }
    }    private static boolean isTargetLike(String decisionClass) {
        return "target".equals(decisionClass)
                || "choose_object".equals(decisionClass)
                || "target_amount".equals(decisionClass)
                || "declare_attacker".equals(decisionClass)
                || "declare_blocker".equals(decisionClass);
    }

    private static JsonObject numericAction(
            JsonObject pending,
            String decisionId,
            String actorId,
            String decisionClass,
            String prompt,
            int min,
            int max,
            long offset,
            JsonObject context,
            JsonObject sourceObject,
            String sourceObjectId
    ) {
        JsonObject action = new JsonObject();
        action.addProperty("action_id", decisionId + ":" + NUMERIC_SUFFIX);
        action.addProperty("actor_id", actorId);
        action.addProperty("action_type", "structural_decision");
        if (sourceObjectId == null) {
            action.add("source_object_id", JsonNull.INSTANCE);
        } else {
            action.addProperty("source_object_id", sourceObjectId);
        }
        action.add("target_ids", new JsonArray());
        action.add("allowed_target_ids", new JsonArray());
        action.add("modes", new JsonArray());
        action.add("choices_schema", choicesSchema(
                decisionId, offset, decisionClass, min, max, context, List.of(), "numeric"
        ));
        action.add("cost", costFor(decisionClass, context, new JsonObject()));
        JsonObject metadata = new JsonObject();
        metadata.addProperty("decision_id", decisionId);
        metadata.addProperty("decision_offset", offset);
        metadata.addProperty("decision_class", decisionClass);
        metadata.addProperty("prompt", prompt);
        if (pending.has("seat") && !pending.get("seat").isJsonNull()) {
            try {
                metadata.addProperty("seat", pending.get("seat").getAsInt());
            } catch (RuntimeException ignored) {
                // Informational only.
            }
        }
        metadata.addProperty("minimum_selections", min);
        metadata.addProperty("maximum_selections", max);
        metadata.addProperty("option_id", NUMERIC_SUFFIX);
        metadata.addProperty("option_type", "numeric_choice");
        metadata.addProperty("label", "Provide numeric choice");
        if (sourceObject != null) {
            metadata.add("source_object", sourceObject.deepCopy());
        }
        action.add("metadata", metadata);
        return action;
    }

    private static JsonObject choicesSchema(
            String decisionId,
            long offset,
            String decisionClass,
            int min,
            int max,
            JsonObject context,
            List<String> availableIds,
            String responseKind
    ) {
        JsonObject schema = new JsonObject();
        schema.addProperty("decision_id", decisionId);
        schema.addProperty("decision_offset", offset);
        schema.addProperty("decision_class", decisionClass);
        schema.addProperty("minimum_selections", min);
        schema.addProperty("maximum_selections", max);
        schema.addProperty("response_kind", responseKind);
        if (context.has("numeric_min") && !context.get("numeric_min").isJsonNull()) {
            try {
                schema.addProperty("numeric_min", context.get("numeric_min").getAsInt());
            } catch (RuntimeException ignored) {
                // Bounds are descriptive; range validation reads the pending context.
            }
        }
        if (context.has("numeric_max") && !context.get("numeric_max").isJsonNull()) {
            try {
                schema.addProperty("numeric_max", context.get("numeric_max").getAsInt());
            } catch (RuntimeException ignored) {
                // Descriptive only.
            }
        }
        // WS229: joint domain described verbatim (descriptive only; range
        // validation reads the pending context).
        if (hasJointLegs(context)) {
            schema.add("numeric_legs", context.getAsJsonArray("numeric_legs").deepCopy());
        }
        if (context.has("numeric_total_min") && !context.get("numeric_total_min").isJsonNull()) {
            try {
                schema.addProperty("numeric_total_min", context.get("numeric_total_min").getAsInt());
            } catch (RuntimeException ignored) {
                // Descriptive only.
            }
        }
        if (context.has("numeric_total_max") && !context.get("numeric_total_max").isJsonNull()) {
            try {
                schema.addProperty("numeric_total_max", context.get("numeric_total_max").getAsInt());
            } catch (RuntimeException ignored) {
                // Descriptive only.
            }
        }
        JsonArray available = new JsonArray();
        availableIds.forEach(available::add);
        schema.add("available_option_ids", available);
        return schema;
    }

    private static JsonObject costFor(
            String decisionClass,
            JsonObject context,
            JsonObject optionMetadata
    ) {
        JsonObject cost = new JsonObject();
        if (!"mana_payment".equals(decisionClass)) {
            return cost;
        }
        if (context.has("unpaid_mana") && !context.get("unpaid_mana").isJsonNull()) {
            cost.addProperty("unpaid_mana", context.get("unpaid_mana").getAsString());
        }
        if (optionMetadata.has("mana_type") && !optionMetadata.get("mana_type").isJsonNull()) {
            cost.addProperty("mana_type", optionMetadata.get("mana_type").getAsString());
        }
        if (optionMetadata.has("mana_available") && !optionMetadata.get("mana_available").isJsonNull()) {
            try {
                cost.addProperty("mana_available", optionMetadata.get("mana_available").getAsInt());
            } catch (RuntimeException ignored) {
                // Descriptive only; affordability stays XMage-owned.
            }
        }
        cost.addProperty("descriptive_only", true);
        return cost;
    }

    private static String extractSourceObjectId(JsonObject sourceObject) {
        if (sourceObject == null) {
            return null;
        }
        if (sourceObject.has("source_object_id") && !sourceObject.get("source_object_id").isJsonNull()) {
            String value = sourceObject.get("source_object_id").getAsString().trim();
            return value.isBlank() ? null : value;
        }
        return null;
    }

    private static boolean isUuid(String value) {
        if (value == null || value.isBlank()) {
            return false;
        }
        try {
            UUID.fromString(value.trim());
            return true;
        } catch (IllegalArgumentException exc) {
            return false;
        }
    }

    private static String[] splitActionId(String actionId) {
        int index = actionId.indexOf(':');
        if (index <= 0 || index == actionId.length() - 1) {
            throw new ProjectionException("PILOT_RESPONSE_INVALID: malformed legal_action_id");
        }
        return new String[]{actionId.substring(0, index), actionId.substring(index + 1)};
    }

    private static String[] splitActionIdLenient(String actionId) {
        int index = actionId.indexOf(':');
        if (index <= 0 || index == actionId.length() - 1) {
            return null;
        }
        return new String[]{actionId.substring(0, index), actionId.substring(index + 1)};
    }

    private static String requiredText(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            throw new ProjectionException("PILOT_RESPONSE_INVALID: missing " + property);
        }
        String value = object.get(property).getAsString().trim();
        if (value.isBlank()) {
            throw new ProjectionException("PILOT_RESPONSE_INVALID: blank " + property);
        }
        return value;
    }

    private static List<String> stringArray(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return List.of();
        }
        if (!object.get(property).isJsonArray()) {
            throw new ProjectionException("PILOT_RESPONSE_INVALID: " + property + " must be an array");
        }
        List<String> values = new ArrayList<>();
        for (JsonElement element : object.getAsJsonArray(property)) {
            if (!element.isJsonPrimitive() || !element.getAsJsonPrimitive().isString()) {
                throw new ProjectionException("PILOT_RESPONSE_INVALID: non-string in " + property);
            }
            values.add(element.getAsString());
        }
        return values;
    }

    private static void requireEmptyArray(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return;
        }
        if (!object.get(property).isJsonArray()) {
            throw new ProjectionException("PILOT_RESPONSE_INVALID: " + property + " must be an array");
        }
        if (object.getAsJsonArray(property).size() != 0) {
            throw new ProjectionException(
                    "PILOT_RESPONSE_INVALID: " + property + " not authorized by decision schema"
            );
        }
    }
}
