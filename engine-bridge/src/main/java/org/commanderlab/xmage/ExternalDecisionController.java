package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.cards.Card;
import mage.abilities.ActivatedAbility;
import mage.constants.AbilityType;
import mage.constants.CommanderCardType;
import mage.game.Game;
import mage.players.Player;
import mage.target.Target;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
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
            List<JsonObject> actions,
            JsonObject context
    ) {
    }

    private static final long RESPONSE_TIMEOUT_MILLIS = Duration.ofMinutes(2).toMillis();

    private Decision currentDecision;
    private String submittedActionId;
    private List<String> submittedSelection;
    private RuntimeException terminalFailure;
    private boolean terminal;
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

        Set<UUID> commanderIds = game.getCommandersIds(
                player,
                CommanderCardType.COMMANDER_OR_OATHBREAKER,
                false
        );

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
                List.copyOf(actions),
                new JsonObject()
        );

        return currentDecision;
    }

    /**
     * Publish the engine-authored keep/mulligan domain and block the XMage
     * engine thread until the JSONL control thread submits one of those exact
     * options. No keep/mulligan default exists on this path.
     */
    synchronized boolean requestMulligan(
            Player player,
            Game game
    ) {
        requireLiveController();
        if (currentDecision != null) {
            throw new IllegalStateException("CONCURRENT_EXTERNAL_DECISION");
        }

        decisionOffset++;
        String gameId = game.getId().toString();
        String actorId = player.getId().toString();
        String decisionId = stableId(
                gameId,
                Long.toString(decisionOffset),
                actorId,
                "mulligan"
        );

        JsonObject keepMetadata = new JsonObject();
        keepMetadata.addProperty("option_type", "keep");
        JsonObject mulliganMetadata = new JsonObject();
        mulliganMetadata.addProperty("option_type", "mulligan");

        List<JsonObject> actions = List.of(
                legalAction(
                        decisionId,
                        0,
                        actorId,
                        "mulligan",
                        null,
                        null,
                        true,
                        List.of(),
                        new JsonObject(),
                        new JsonObject(),
                        keepMetadata
                ),
                legalAction(
                        decisionId,
                        1,
                        actorId,
                        "mulligan",
                        null,
                        null,
                        true,
                        List.of(),
                        new JsonObject(),
                        new JsonObject(),
                        mulliganMetadata
                )
        );

        Decision pending = new Decision(
                gameId,
                gameId,
                decisionOffset,
                decisionId,
                actorId,
                "mulligan",
                true,
                actions,
                new JsonObject()
        );
        currentDecision = pending;
        submittedActionId = null;
        notifyAll();

        long deadlineNanos = System.nanoTime() + RESPONSE_TIMEOUT_MILLIS * 1_000_000L;
        while (submittedActionId == null && terminalFailure == null && !terminal) {
            long remainingNanos = deadlineNanos - System.nanoTime();
            if (remainingNanos <= 0L) {
                RuntimeException failure = new IllegalStateException(
                        "EXTERNAL_DECISION_TIMEOUT: " + decisionId + " kind=mulligan"
                );
                terminalFailure = failure;
                currentDecision = null;
                notifyAll();
                throw failure;
            }
            try {
                wait(Math.max(1L, remainingNanos / 1_000_000L));
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                RuntimeException failure = new IllegalStateException(
                        "EXTERNAL_DECISION_TIMEOUT: interrupted while awaiting " + decisionId,
                        exc
                );
                terminalFailure = failure;
                currentDecision = null;
                notifyAll();
                throw failure;
            }
        }

        if (terminalFailure != null) {
            throw terminalFailure;
        }
        if (submittedActionId == null) {
            throw new IllegalStateException(
                    "EXTERNAL_DECISION_ENDED_WITHOUT_RESPONSE: " + decisionId
            );
        }

        JsonObject selected = pending.actions().stream()
                .filter(action -> submittedActionId.equals(action.get("action_id").getAsString()))
                .findFirst()
                .orElseThrow(() -> new IllegalStateException(
                        "EXTERNAL_DECISION_RESPONSE_NOT_IN_OFFER: " + submittedActionId
                ));
        String optionType = selected.getAsJsonObject("metadata")
                .get("option_type").getAsString();

        submittedActionId = null;
        currentDecision = null;
        notifyAll();
        return "mulligan".equals(optionType);
    }

    /**
     * Publish the engine-authored London-bottoming domain and block the XMage
     * engine thread until the JSONL control thread submits an explicit
     * selection from the offered cards.
     *
     * <p>The offered identities are the acting player's own cards as the engine
     * supplied them, so the projection stays actor-scoped. The cardinality is
     * the engine's own minimum and maximum for this choice; the controller
     * derives no Mulligan rule of its own and applies no default selection.</p>
     */
    synchronized List<String> requestMulliganBottom(
            Player player,
            Game game,
            List<String> offeredIds,
            int minCount,
            int maxCount
    ) {
        requireLiveController();
        if (currentDecision != null) {
            throw new IllegalStateException("CONCURRENT_EXTERNAL_DECISION");
        }
        if (offeredIds == null || offeredIds.isEmpty()) {
            throw new IllegalStateException(
                    "MULLIGAN_BOTTOM_DOMAIN_INVALID: engine offered no card to choose from"
            );
        }
        if (minCount < 0 || maxCount < minCount || maxCount > offeredIds.size()) {
            throw new IllegalStateException(
                    "MULLIGAN_BOTTOM_DOMAIN_INVALID: engine declared min=" + minCount
                            + " max=" + maxCount + " for " + offeredIds.size() + " offered cards"
            );
        }

        decisionOffset++;
        String gameId = game.getId().toString();
        String actorId = player.getId().toString();
        String decisionId = stableId(
                gameId,
                Long.toString(decisionOffset),
                actorId,
                "mulligan_bottom"
        );

        List<JsonObject> actions = new ArrayList<>(offeredIds.size());
        for (int ordinal = 0; ordinal < offeredIds.size(); ordinal++) {
            String cardId = offeredIds.get(ordinal);
            JsonObject metadata = new JsonObject();
            metadata.addProperty("option_type", "mulligan_bottom_card");
            metadata.addProperty("card_id", cardId);
            metadata.addProperty("card_name", cardId);
            actions.add(legalAction(
                    decisionId,
                    ordinal,
                    actorId,
                    "mulligan_bottom",
                    cardId,
                    null,
                    true,
                    List.of(),
                    new JsonObject(),
                    new JsonObject(),
                    metadata
            ));
        }

        JsonObject context = new JsonObject();
        context.addProperty("min_selection", minCount);
        context.addProperty("max_selection", maxCount);

        Decision pending = new Decision(
                gameId,
                gameId,
                decisionOffset,
                decisionId,
                actorId,
                "mulligan_bottom",
                true,
                actions,
                context
        );
        currentDecision = pending;
        submittedActionId = null;
        submittedSelection = null;
        notifyAll();

        long deadlineNanos = System.nanoTime() + RESPONSE_TIMEOUT_MILLIS * 1_000_000L;
        while (submittedSelection == null && terminalFailure == null && !terminal) {
            long remainingNanos = deadlineNanos - System.nanoTime();
            if (remainingNanos <= 0L) {
                RuntimeException failure = new IllegalStateException(
                        "EXTERNAL_DECISION_TIMEOUT: " + decisionId + " kind=mulligan_bottom"
                );
                terminalFailure = failure;
                currentDecision = null;
                notifyAll();
                throw failure;
            }
            try {
                wait(Math.max(1L, remainingNanos / 1_000_000L));
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                RuntimeException failure = new IllegalStateException(
                        "EXTERNAL_DECISION_TIMEOUT: interrupted while awaiting " + decisionId,
                        exc
                );
                terminalFailure = failure;
                currentDecision = null;
                notifyAll();
                throw failure;
            }
        }

        if (terminalFailure != null) {
            throw terminalFailure;
        }
        if (submittedSelection == null) {
            throw new IllegalStateException(
                    "EXTERNAL_DECISION_ENDED_WITHOUT_RESPONSE: " + decisionId
            );
        }

        List<String> selection = List.copyOf(submittedSelection);
        submittedSelection = null;
        currentDecision = null;
        notifyAll();
        return selection;
    }

    /**
     * Resolve the pending London-bottoming decision from an explicit external
     * selection. Validation fails closed and in this order: live controller,
     * decision kind, decision id, actor id, membership of every selected
     * identity in the offered set, then authoritative cardinality.
     */
    synchronized List<String> submitMulliganBottom(
            String engineGameId,
            String decisionId,
            String actorId,
            List<String> selectedCardIds
    ) {
        requireLiveController();
        Decision decision = requireCurrentDecision(engineGameId);
        if (!"mulligan_bottom".equals(decision.decisionKind())) {
            throw new IllegalStateException(
                    "EXTERNAL_DECISION_KIND_MISMATCH: expected mulligan_bottom, observed "
                            + decision.decisionKind()
            );
        }
        if (!decision.decisionId().equals(decisionId)) {
            throw new IllegalStateException("STALE_EXTERNAL_DECISION");
        }
        if (!decision.actorId().equals(actorId)) {
            throw new IllegalStateException("EXTERNAL_DECISION_ACTOR_MISMATCH");
        }
        if (selectedCardIds == null) {
            throw new IllegalStateException("MULLIGAN_BOTTOM_SELECTION_INVALID: null selection");
        }

        List<String> offeredIds = decision.actions().stream()
                .filter(action -> action.has("metadata") && action.get("metadata").isJsonObject())
                .map(action -> action.getAsJsonObject("metadata"))
                .filter(metadata -> metadata.has("card_id"))
                .map(metadata -> metadata.get("card_id").getAsString())
                .toList();
        for (String selected : selectedCardIds) {
            if (selected == null || !offeredIds.contains(selected)) {
                throw new IllegalStateException(
                        "MULLIGAN_BOTTOM_SELECTION_INVALID: identity " + selected
                                + " is not among the offered cards"
                );
            }
        }
        if (new java.util.HashSet<>(selectedCardIds).size() != selectedCardIds.size()) {
            throw new IllegalStateException(
                    "MULLIGAN_BOTTOM_SELECTION_INVALID: the same card may not be selected twice"
            );
        }
        JsonObject domain = decision.context();
        int minSelection = domain.has("min_selection") ? domain.get("min_selection").getAsInt() : 0;
        int maxSelection = domain.has("max_selection") ? domain.get("max_selection").getAsInt() : 0;
        if (selectedCardIds.size() < minSelection || selectedCardIds.size() > maxSelection) {
            throw new IllegalStateException(
                    "MULLIGAN_BOTTOM_SELECTION_INVALID: the engine requires "
                            + minSelection + ".." + maxSelection
                            + " card(s) from the offered domain, got " + selectedCardIds.size()
            );
        }

        submittedSelection = new ArrayList<>(selectedCardIds);
        notifyAll();
        return selectedCardIds;
    }

    /**
     * Resolve the currently pending mulligan decision from an explicit external
     * choice. bottom_card_ids must be empty here: London bottoming is a separate
     * engine callback and remains fail-closed until that callback is projected.
     */
    synchronized String submitMulligan(
            String engineGameId,
            String decisionId,
            String actorId,
            boolean keep,
            List<String> bottomCardIds
    ) {
        requireLiveController();
        Decision decision = requireCurrentDecision(engineGameId);
        if (!"mulligan".equals(decision.decisionKind())) {
            throw new IllegalStateException(
                    "EXTERNAL_DECISION_KIND_MISMATCH: expected mulligan, observed "
                            + decision.decisionKind()
            );
        }
        if (!decision.decisionId().equals(decisionId)) {
            throw new IllegalStateException("STALE_EXTERNAL_DECISION");
        }
        if (!decision.actorId().equals(actorId)) {
            throw new IllegalStateException("EXTERNAL_DECISION_ACTOR_MISMATCH");
        }
        if (bottomCardIds != null && !bottomCardIds.isEmpty()) {
            throw new IllegalStateException(
                    "UNSUPPORTED_COMPATIBILITY_DECISION: London bottom-card selection "
                            + "is a separate engine decision and cannot be injected here"
            );
        }

        String wanted = keep ? "keep" : "mulligan";
        List<JsonObject> matches = decision.actions().stream()
                .filter(action -> action.has("metadata")
                        && action.get("metadata").isJsonObject()
                        && wanted.equals(action.getAsJsonObject("metadata")
                                .get("option_type").getAsString()))
                .toList();
        if (matches.size() != 1) {
            throw new IllegalStateException(
                    "EXTERNAL_DECISION_DOMAIN_INVALID: expected one " + wanted
                            + " option, observed " + matches.size()
            );
        }
        submittedActionId = matches.get(0).get("action_id").getAsString();
        notifyAll();
        return submittedActionId;
    }

    synchronized Decision awaitCurrentDecision(
            String engineGameId,
            Duration timeout
    ) {
        long timeoutMillis = timeout == null ? 20_000L : timeout.toMillis();
        long deadlineNanos = System.nanoTime() + timeoutMillis * 1_000_000L;
        while (currentDecision == null && terminalFailure == null && !terminal) {
            long remainingNanos = deadlineNanos - System.nanoTime();
            if (remainingNanos <= 0L) {
                throw new IllegalStateException("NO_EXTERNAL_DECISION_AVAILABLE");
            }
            try {
                wait(Math.max(1L, remainingNanos / 1_000_000L));
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException(
                        "EXTERNAL_DECISION_WAIT_INTERRUPTED", exc
                );
            }
        }
        return requireCurrentDecision(engineGameId);
    }

    synchronized Decision awaitDecisionAdvance(
            String engineGameId,
            String previousDecisionId,
            Duration timeout
    ) {
        long timeoutMillis = timeout == null ? 20_000L : timeout.toMillis();
        long deadlineNanos = System.nanoTime() + timeoutMillis * 1_000_000L;
        while (terminalFailure == null && !terminal) {
            if (currentDecision != null
                    && !previousDecisionId.equals(currentDecision.decisionId())) {
                return requireCurrentDecision(engineGameId);
            }
            long remainingNanos = deadlineNanos - System.nanoTime();
            if (remainingNanos <= 0L) {
                throw new IllegalStateException(
                        "EXTERNAL_DECISION_ADVANCE_TIMEOUT: " + previousDecisionId
                );
            }
            try {
                wait(Math.max(1L, remainingNanos / 1_000_000L));
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException(
                        "EXTERNAL_DECISION_ADVANCE_INTERRUPTED", exc
                );
            }
        }
        if (terminalFailure != null) {
            throw terminalFailure;
        }
        throw new IllegalStateException(
                "EXTERNAL_DECISION_TERMINAL_WITHOUT_SUCCESSOR: " + previousDecisionId
        );
    }

    synchronized void failClosed(String message, Throwable cause) {
        if (terminalFailure == null) {
            terminalFailure = new IllegalStateException(message, cause);
        }
        notifyAll();
    }

    synchronized void markTerminal() {
        terminal = true;
        notifyAll();
    }

    private void requireLiveController() {
        if (terminalFailure != null) {
            throw terminalFailure;
        }
        if (terminal) {
            throw new IllegalStateException("EXTERNAL_DECISION_CONTROLLER_TERMINAL");
        }
    }

    synchronized Decision requireCurrentDecision(
            String engineGameId
    ) {
        if (terminalFailure != null) {
            throw terminalFailure;
        }
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
