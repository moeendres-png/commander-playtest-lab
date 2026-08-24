package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.MageItem;
import mage.MageObject;
import mage.abilities.Ability;
import mage.abilities.ActivatedAbility;
import mage.abilities.Mode;
import mage.abilities.Modes;
import mage.abilities.TriggeredAbility;
import mage.abilities.costs.mana.ManaCost;
import mage.cards.Card;
import mage.cards.Cards;
import mage.cards.decks.Deck;
import mage.choices.Choice;
import mage.constants.MultiAmountType;
import mage.constants.Outcome;
import mage.constants.RangeOfInfluence;
import mage.game.Game;
import mage.game.draft.Draft;
import mage.game.match.Match;
import mage.game.permanent.Permanent;
import mage.game.tournament.Tournament;
import mage.players.Player;
import mage.players.PlayerImpl;
import mage.players.net.UserData;
import mage.target.Target;
import mage.target.TargetAmount;
import mage.target.TargetCard;
import mage.util.MultiAmountMessage;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Headless XMage player whose discretionary decisions are supplied externally.
 *
 * <p>This class intentionally models itself as a human XMage player. That keeps
 * card implementations on XMage's human/rules path instead of activating
 * {@code isComputer()} branches. Every Player decision callback is either
 * handed to {@link XmageFullGameDecisionController} or fails closed. Rules
 * randomness (shuffle, coin flips, dice, random modes) remains XMage-owned.</p>
 */
final class XmageFullGamePlayer extends PlayerImpl {

    private final XmageFullGameDecisionController decisionController;

    XmageFullGamePlayer(
            String name,
            RangeOfInfluence range,
            XmageFullGameDecisionController decisionController
    ) {
        super(name, range);
        if (decisionController == null) {
            throw new IllegalArgumentException("decisionController must not be null");
        }
        this.decisionController = decisionController;
        this.human = true;

        UserData userData = UserData.getDefaultUserDataView();
        userData.setManaPoolAutomatic(false);
        userData.setManaPoolAutomaticRestricted(false);
        userData.setPassPriorityCast(false);
        userData.setPassPriorityActivation(false);
        userData.setAutoOrderTrigger(false);
        userData.setAutoTargetLevel(0);
        userData.setUseFirstManaAbility(false);
        setUserData(userData);
    }

    private XmageFullGamePlayer(XmageFullGamePlayer player) {
        super(player);
        this.decisionController = player.decisionController;
        this.human = true;
    }

    @Override
    public XmageFullGamePlayer copy() {
        return new XmageFullGamePlayer(this);
    }

    @Override
    public boolean priority(Game game) {
        JsonArray options = new JsonArray();
        Map<String, ActivatedAbility> abilities = new LinkedHashMap<>();

        String passId = optionId("priority-pass", getId().toString());
        options.add(XmageFullGameDecisionController.option(
                passId,
                "Pass priority",
                "pass_priority",
                new JsonObject()
        ));

        List<ActivatedAbility> playable = new ArrayList<>(getPlayable(game, false));
        playable.sort(Comparator.comparing(this::abilitySortKey));
        for (ActivatedAbility ability : playable) {
            String optionId = abilityOptionId("priority", ability);
            JsonObject metadata = abilityMetadata(ability, game);
            options.add(XmageFullGameDecisionController.option(
                    optionId,
                    abilityLabel(ability, game),
                    ability.isManaAbility() ? "mana_ability" : "activated_ability",
                    metadata
            ));
            abilities.put(optionId, ability);
        }

        String selected = requireSingle(
                request(game, "priority", "Choose priority action", 1, 1, options, new JsonObject(), null)
        );
        if (passId.equals(selected)) {
            pass(game);
            return false;
        }
        ActivatedAbility ability = abilities.get(selected);
        if (ability == null) {
            fail("ILLEGAL_ACTION", "priority option disappeared: " + selected);
        }
        boolean activated = activateAbility(ability, game);
        if (!activated) {
            fail("XMAGE_ACTION_EXECUTION_FAILED", "priority activation failed: " + selected);
        }
        return true;
    }

    @Override
    public boolean choose(Outcome outcome, Target target, Ability source, Game game) {
        return chooseTargetInternal(outcome, false, target, source, game, null, null);
    }

    @Override
    public boolean choose(
            Outcome outcome,
            Target target,
            Ability source,
            Game game,
            Map<String, Serializable> options
    ) {
        JsonObject context = new JsonObject();
        if (options != null && !options.isEmpty()) {
            JsonObject supplied = new JsonObject();
            options.entrySet().stream()
                    .sorted(Map.Entry.comparingByKey())
                    .forEach(entry -> supplied.addProperty(
                            entry.getKey(),
                            String.valueOf(entry.getValue())
                    ));
            context.add("xmage_options", supplied);
        }
        context.addProperty("outcome", outcome == null ? "neutral" : outcome.name().toLowerCase());
        return chooseTargetInternal(outcome, false, target, source, game, null, context);
    }

    @Override
    public boolean choose(
            Outcome outcome,
            Cards cards,
            TargetCard target,
            Ability source,
            Game game
    ) {
        return chooseTargetInternal(outcome, false, target, source, game, cards, null);
    }

    @Override
    public boolean chooseTarget(Outcome outcome, Target target, Ability source, Game game) {
        return chooseTargetInternal(outcome, true, target, source, game, null, null);
    }

    @Override
    public boolean chooseTarget(
            Outcome outcome,
            Cards cards,
            TargetCard target,
            Ability source,
            Game game
    ) {
        return chooseTargetInternal(outcome, true, target, source, game, cards, null);
    }

    @Override
    public boolean chooseTargetAmount(
            Outcome outcome,
            TargetAmount target,
            Ability source,
            Game game
    ) {
        target.prepareAmount(source, game);
        Set<UUID> possible = target.possibleTargets(getId(), source, game);
        List<UUID> sorted = possible.stream()
                .sorted(Comparator.comparing(UUID::toString))
                .toList();
        if (sorted.isEmpty()) {
            return false;
        }

        JsonArray options = objectOptions(sorted, game, "target_amount");
        int remaining = target.getAmountRemaining();
        JsonObject context = new JsonObject();
        context.addProperty("numeric_min", 1);
        context.addProperty("numeric_max", Math.max(1, remaining));
        context.addProperty("amount_remaining", remaining);
        context.addProperty("outcome", outcome == null ? "neutral" : outcome.name().toLowerCase());

        XmageFullGameDecisionController.DecisionResponse response = request(
                game,
                "target_amount",
                target.getMessage(game),
                1,
                1,
                options,
                context,
                source
        );
        String selected = requireSingle(response);
        int amount = response.numericChoice() == null ? 1 : response.numericChoice();
        UUID targetId = UUID.fromString(selected);
        target.addTarget(targetId, amount, source, game);
        return true;
    }

    @Override
    public boolean chooseMulligan(Game game) {
        JsonArray options = new JsonArray();
        String keep = optionId("mulligan", "keep");
        String mulligan = optionId("mulligan", "mulligan");
        options.add(XmageFullGameDecisionController.option(
                keep, "Keep opening hand", "keep", new JsonObject()
        ));
        options.add(XmageFullGameDecisionController.option(
                mulligan, "Take mulligan", "mulligan", new JsonObject()
        ));
        String selected = requireSingle(request(
                game,
                "mulligan",
                "Keep or mulligan",
                1,
                1,
                options,
                new JsonObject(),
                null
        ));
        return mulligan.equals(selected);
    }

    @Override
    public boolean chooseUse(
            Outcome outcome,
            String message,
            Ability source,
            Game game
    ) {
        JsonObject context = new JsonObject();
        context.addProperty("outcome", outcome == null ? "neutral" : outcome.name().toLowerCase());
        return chooseBoolean(message, "choose_use", "Yes", "No", source, game, context);
    }

    @Override
    public boolean chooseUse(
            Outcome outcome,
            String message,
            String secondMessage,
            String trueText,
            String falseText,
            Ability source,
            Game game
    ) {
        JsonObject context = new JsonObject();
        context.addProperty("outcome", outcome == null ? "neutral" : outcome.name().toLowerCase());
        if (secondMessage != null) {
            context.addProperty("secondary_prompt", secondMessage);
        }
        return chooseBoolean(
                message,
                "choose_use",
                trueText == null ? "Yes" : trueText,
                falseText == null ? "No" : falseText,
                source,
                game,
                context
        );
    }

    @Override
    public boolean choose(Outcome outcome, Choice choice, Game game) {
        List<String> values = new ArrayList<>(choice.getChoices());
        values.sort(String::compareTo);
        JsonArray options = new JsonArray();
        Map<String, String> choices = new HashMap<>();
        for (String value : values) {
            String optionId = optionId("choice", value);
            JsonObject metadata = new JsonObject();
            metadata.addProperty("choice", value);
            options.add(XmageFullGameDecisionController.option(
                    optionId, value, "choice", metadata
            ));
            choices.put(optionId, value);
        }
        if (options.isEmpty()) {
            return false;
        }
        String selected = requireSingle(request(
                game,
                "choice",
                "Choose option",
                1,
                1,
                options,
                outcomeContext(outcome),
                null
        ));
        String value = choices.get(selected);
        if (value == null) {
            fail("ILLEGAL_ACTION", "choice option disappeared: " + selected);
        }
        choice.setChoice(value);
        return true;
    }

    @Override
    public boolean choosePile(
            Outcome outcome,
            String message,
            List<? extends Card> pile1,
            List<? extends Card> pile2,
            Game game
    ) {
        JsonArray options = new JsonArray();
        String first = optionId("pile", "1");
        String second = optionId("pile", "2");
        options.add(XmageFullGameDecisionController.option(
                first, "Pile 1", "pile", pileMetadata(pile1)
        ));
        options.add(XmageFullGameDecisionController.option(
                second, "Pile 2", "pile", pileMetadata(pile2)
        ));
        String selected = requireSingle(request(
                game,
                "pile",
                message,
                1,
                1,
                options,
                outcomeContext(outcome),
                null
        ));
        return first.equals(selected);
    }

    @Override
    public boolean playMana(
            Ability ability,
            ManaCost unpaid,
            String promptText,
            Game game
    ) {
        List<ActivatedAbility> manaAbilities = getPlayable(game, false).stream()
                .filter(Ability::isManaAbility)
                .sorted(Comparator.comparing(this::abilitySortKey))
                .toList();

        JsonArray options = new JsonArray();
        Map<String, ActivatedAbility> byId = new LinkedHashMap<>();
        String cancel = optionId("mana", "cancel");
        options.add(XmageFullGameDecisionController.option(
                cancel,
                "Cancel mana payment",
                "cancel_mana_payment",
                new JsonObject()
        ));
        for (ActivatedAbility manaAbility : manaAbilities) {
            String optionId = abilityOptionId("mana", manaAbility);
            options.add(XmageFullGameDecisionController.option(
                    optionId,
                    abilityLabel(manaAbility, game),
                    "mana_ability",
                    abilityMetadata(manaAbility, game)
            ));
            byId.put(optionId, manaAbility);
        }
        JsonObject context = new JsonObject();
        context.addProperty("unpaid_mana", unpaid == null ? "" : unpaid.getText());
        String selected = requireSingle(request(
                game,
                "mana_payment",
                promptText,
                1,
                1,
                options,
                context,
                ability
        ));
        if (cancel.equals(selected)) {
            return false;
        }
        ActivatedAbility manaAbility = byId.get(selected);
        if (manaAbility == null) {
            fail("ILLEGAL_ACTION", "mana option disappeared: " + selected);
        }
        boolean activated = activateAbility(manaAbility, game);
        if (!activated) {
            fail("XMAGE_ACTION_EXECUTION_FAILED", "mana activation failed: " + selected);
        }
        return true;
    }

    @Override
    public int announceX(
            int min,
            int max,
            String message,
            Game game,
            Ability source,
            boolean isManaPay
    ) {
        return chooseNumber("announce_x", message, min, max, source, game);
    }

    @Override
    public int chooseReplacementEffect(
            Map<String, String> effectsMap,
            Map<String, MageObject> objectsMap,
            Game game
    ) {
        if (effectsMap == null || effectsMap.isEmpty()) {
            fail("BRIDGE_PROTOCOL_ERROR", "replacement effect choice had no options");
        }
        JsonArray options = new JsonArray();
        Map<String, Integer> indexByOption = new LinkedHashMap<>();
        int index = 0;
        for (Map.Entry<String, String> entry : effectsMap.entrySet()) {
            String optionId = optionId("replacement", Integer.toString(index), entry.getKey());
            JsonObject metadata = new JsonObject();
            metadata.addProperty("xmage_key", entry.getKey());
            metadata.addProperty("index", index);
            if (objectsMap != null && objectsMap.get(entry.getKey()) != null) {
                metadata.addProperty("source_name", objectsMap.get(entry.getKey()).getName());
            }
            options.add(XmageFullGameDecisionController.option(
                    optionId,
                    entry.getValue(),
                    "replacement_effect",
                    metadata
            ));
            indexByOption.put(optionId, index);
            index++;
        }
        String selected = requireSingle(request(
                game,
                "replacement_effect",
                "Choose replacement effect",
                1,
                1,
                options,
                new JsonObject(),
                null
        ));
        Integer selectedIndex = indexByOption.get(selected);
        if (selectedIndex == null) {
            fail("ILLEGAL_ACTION", "replacement option disappeared: " + selected);
        }
        return selectedIndex;
    }

    @Override
    public TriggeredAbility chooseTriggeredAbility(
            List<TriggeredAbility> abilities,
            Game game
    ) {
        if (abilities == null || abilities.isEmpty()) {
            return null;
        }
        JsonArray options = new JsonArray();
        Map<String, TriggeredAbility> byId = new LinkedHashMap<>();
        List<TriggeredAbility> sorted = new ArrayList<>(abilities);
        sorted.sort(Comparator.comparing(this::abilitySortKey));
        for (TriggeredAbility ability : sorted) {
            String optionId = abilityOptionId("trigger", ability);
            options.add(XmageFullGameDecisionController.option(
                    optionId,
                    abilityLabel(ability, game),
                    "triggered_ability",
                    abilityMetadata(ability, game)
            ));
            byId.put(optionId, ability);
        }
        String selected = requireSingle(request(
                game,
                "trigger_order",
                "Choose next triggered ability",
                1,
                1,
                options,
                new JsonObject(),
                null
        ));
        TriggeredAbility result = byId.get(selected);
        if (result == null) {
            fail("ILLEGAL_ACTION", "trigger option disappeared: " + selected);
        }
        return result;
    }

    @Override
    public Mode chooseMode(Modes modes, Ability source, Game game) {
        List<Mode> available = new ArrayList<>(modes.getAvailableModes(source, game));
        available.sort(Comparator.comparing(mode -> mode.getId().toString()));
        if (available.isEmpty()) {
            return null;
        }
        JsonArray options = new JsonArray();
        Map<String, Mode> byId = new LinkedHashMap<>();
        for (Mode mode : available) {
            String optionId = mode.getId().toString();
            JsonObject metadata = new JsonObject();
            metadata.addProperty("mode_id", mode.getId().toString());
            metadata.addProperty("paw_print_value", mode.getPawPrintValue());
            options.add(XmageFullGameDecisionController.option(
                    optionId,
                    mode.toString(),
                    "mode",
                    metadata
            ));
            byId.put(optionId, mode);
        }
        int min = modes.getSelectedModes().size() >= modes.getMinModes() ? 0 : 1;
        XmageFullGameDecisionController.DecisionResponse response = request(
                game,
                "mode",
                modes.getText(),
                min,
                1,
                options,
                new JsonObject(),
                source
        );
        if (response.selectedOptionIds().isEmpty()) {
            return null;
        }
        Mode selected = byId.get(response.selectedOptionIds().get(0));
        if (selected == null) {
            fail("ILLEGAL_ACTION", "mode option disappeared");
        }
        return selected;
    }

    @Override
    public void selectAttackers(Game game, UUID attackingPlayerId) {
        List<Permanent> attackers = new ArrayList<>(getAvailableAttackers(game));
        attackers.sort(Comparator.comparing(permanent -> permanent.getId().toString()));
        List<UUID> defenders = game.getCombat().getDefenders().stream()
                .sorted(Comparator.comparing(UUID::toString))
                .toList();

        for (Permanent attacker : attackers) {
            JsonArray options = new JsonArray();
            String hold = optionId("attack", attacker.getId().toString(), "hold");
            options.add(XmageFullGameDecisionController.option(
                    hold,
                    "Do not attack with " + attacker.getName(),
                    "hold_attacker",
                    objectMetadata(attacker.getId(), attacker.getName())
            ));
            Map<String, UUID> defenderByOption = new LinkedHashMap<>();
            for (UUID defenderId : defenders) {
                if (!attacker.canAttack(defenderId, game)) {
                    continue;
                }
                String optionId = optionId(
                        "attack",
                        attacker.getId().toString(),
                        defenderId.toString()
                );
                JsonObject metadata = objectMetadata(attacker.getId(), attacker.getName());
                metadata.addProperty("defender_id", defenderId.toString());
                options.add(XmageFullGameDecisionController.option(
                        optionId,
                        attacker.getName() + " attacks " + objectLabel(defenderId, game),
                        "declare_attacker",
                        metadata
                ));
                defenderByOption.put(optionId, defenderId);
            }
            String selected = requireSingle(request(
                    game,
                    "declare_attacker",
                    "Choose attack for " + attacker.getName(),
                    1,
                    1,
                    options,
                    new JsonObject(),
                    null
            ));
            if (hold.equals(selected)) {
                continue;
            }
            UUID defenderId = defenderByOption.get(selected);
            if (defenderId == null) {
                fail("ILLEGAL_ACTION", "attack option disappeared: " + selected);
            }
            declareAttacker(attacker.getId(), defenderId, game, false);
        }
    }

    @Override
    public void selectBlockers(
            Ability source,
            Game game,
            UUID defendingPlayerId
    ) {
        List<Permanent> blockers = new ArrayList<>(getAvailableBlockers(game));
        blockers.sort(Comparator.comparing(permanent -> permanent.getId().toString()));
        List<UUID> attackers = game.getCombat().getAttackers().stream()
                .sorted(Comparator.comparing(UUID::toString))
                .toList();

        for (Permanent blocker : blockers) {
            JsonArray options = new JsonArray();
            Map<String, UUID> attackerByOption = new LinkedHashMap<>();
            for (UUID attackerId : attackers) {
                if (!blocker.canBlock(attackerId, game)) {
                    continue;
                }
                String optionId = attackerId.toString();
                JsonObject metadata = new JsonObject();
                metadata.addProperty("blocker_id", blocker.getId().toString());
                metadata.addProperty("attacker_id", attackerId.toString());
                options.add(XmageFullGameDecisionController.option(
                        optionId,
                        blocker.getName() + " blocks " + objectLabel(attackerId, game),
                        "declare_blocker",
                        metadata
                ));
                attackerByOption.put(optionId, attackerId);
            }
            int maxBlocks = Math.min(blocker.getMaxBlocks(), options.size());
            if (maxBlocks <= 0 || options.isEmpty()) {
                continue;
            }
            XmageFullGameDecisionController.DecisionResponse response = request(
                    game,
                    "declare_blocker",
                    "Choose creatures blocked by " + blocker.getName(),
                    0,
                    maxBlocks,
                    options,
                    new JsonObject(),
                    source
            );
            for (String selected : response.selectedOptionIds()) {
                UUID attackerId = attackerByOption.get(selected);
                if (attackerId == null) {
                    fail("ILLEGAL_ACTION", "block option disappeared: " + selected);
                }
                declareBlocker(defendingPlayerId, blocker.getId(), attackerId, game, false);
            }
        }
    }

    @Override
    public int getAmount(
            int min,
            int max,
            String message,
            Ability source,
            Game game
    ) {
        return chooseNumber("amount", message, min, max, source, game);
    }

    @Override
    public List<Integer> getMultiAmountWithIndividualConstraints(
            Outcome outcome,
            List<MultiAmountMessage> messages,
            int totalMin,
            int totalMax,
            MultiAmountType type,
            Game game
    ) {
        if (messages == null || messages.isEmpty()) {
            return List.of();
        }
        List<Integer> result = new ArrayList<>(messages.size());
        int allocated = 0;
        for (int index = 0; index < messages.size(); index++) {
            MultiAmountMessage current = messages.get(index);
            int remainingMinAfter = 0;
            int remainingMaxAfter = 0;
            for (int future = index + 1; future < messages.size(); future++) {
                remainingMinAfter += messages.get(future).min;
                remainingMaxAfter += messages.get(future).max;
            }
            int min = Math.max(current.min, totalMin - allocated - remainingMaxAfter);
            int max = Math.min(current.max, totalMax - allocated - remainingMinAfter);
            int chosen = chooseNumber(
                    "multi_amount",
                    current.message,
                    min,
                    max,
                    null,
                    game
            );
            result.add(chosen);
            allocated += chosen;
        }
        if (allocated < totalMin || allocated > totalMax) {
            fail(
                    "PILOT_RESPONSE_INVALID",
                    "multi amount total " + allocated + " outside " + totalMin + ".." + totalMax
            );
        }
        return List.copyOf(result);
    }

    @Override
    public void shuffleLibrary(Ability source, Game game) {
        super.shuffleLibrary(source, game);
    }

    @Override
    public void abort() {
        // Process shutdown interrupts the controller; no hidden/default game decision exists here.
    }

    @Override
    public void skip() {
        // GUI-only skip action. Priority decisions are handled explicitly by priority().
    }

    @Override
    public void sideboard(Match match, Deck deck) {
        fail("OUT_OF_SCOPE_DECISION", "sideboarding is not part of Commander full-game conformance");
    }

    @Override
    public void construct(Tournament tournament, Deck deck) {
        fail("OUT_OF_SCOPE_DECISION", "limited construction is not part of Commander full-game conformance");
    }

    @Override
    public void pickCard(List<Card> cards, Deck deck, Draft draft) {
        fail("OUT_OF_SCOPE_DECISION", "draft is not part of Commander full-game conformance");
    }

    private boolean chooseTargetInternal(
            Outcome outcome,
            boolean targeted,
            Target target,
            Ability source,
            Game game,
            Cards restrictedCards,
            JsonObject suppliedContext
    ) {
        Set<UUID> possible;
        if (restrictedCards == null) {
            possible = target.possibleTargets(getId(), source, game);
        } else {
            Set<UUID> cardIds = restrictedCards.getCards(game).stream()
                    .map(MageItem::getId)
                    .collect(java.util.stream.Collectors.toSet());
            possible = target.possibleTargets(getId(), source, game, cardIds);
        }
        List<UUID> sorted = possible.stream()
                .sorted(Comparator.comparing(UUID::toString))
                .toList();

        int alreadySelected = target.getSize();
        int min = Math.max(0, target.getMinNumberOfTargets() - alreadySelected);
        int max = Math.max(0, target.getMaxNumberOfTargets() - alreadySelected);
        max = Math.min(max, sorted.size());
        min = Math.min(min, max);

        if (sorted.isEmpty()) {
            return false;
        }
        JsonObject context = suppliedContext == null ? new JsonObject() : suppliedContext.deepCopy();
        context.addProperty("targeted", targeted);
        context.addProperty("outcome", outcome == null ? "neutral" : outcome.name().toLowerCase());
        context.addProperty("target_description", target.getDescription());
        context.addProperty("target_name", target.getTargetName());
        context.addProperty("required", target.isRequired());

        XmageFullGameDecisionController.DecisionResponse response = request(
                game,
                targeted ? "target" : "choose_object",
                target.getMessage(game),
                min,
                max,
                objectOptions(sorted, game, targeted ? "target" : "choice"),
                context,
                source
        );
        for (String selected : response.selectedOptionIds()) {
            UUID id = UUID.fromString(selected);
            if (targeted) {
                target.addTarget(id, source, game);
            } else {
                target.add(id, game);
            }
        }
        return !response.selectedOptionIds().isEmpty();
    }

    private static JsonObject outcomeContext(Outcome outcome) {
        JsonObject context = new JsonObject();
        context.addProperty(
                "outcome",
                outcome == null ? "neutral" : outcome.name().toLowerCase()
        );
        return context;
    }

    private boolean chooseBoolean(
            String message,
            String decisionClass,
            String trueText,
            String falseText,
            Ability source,
            Game game
    ) {
        return chooseBoolean(
                message,
                decisionClass,
                trueText,
                falseText,
                source,
                game,
                new JsonObject()
        );
    }

    private boolean chooseBoolean(
            String message,
            String decisionClass,
            String trueText,
            String falseText,
            Ability source,
            Game game,
            JsonObject context
    ) {
        JsonArray options = new JsonArray();
        String yes = optionId(decisionClass, "true");
        String no = optionId(decisionClass, "false");
        JsonObject yesMeta = new JsonObject();
        yesMeta.addProperty("value", true);
        JsonObject noMeta = new JsonObject();
        noMeta.addProperty("value", false);
        options.add(XmageFullGameDecisionController.option(yes, trueText, "boolean", yesMeta));
        options.add(XmageFullGameDecisionController.option(no, falseText, "boolean", noMeta));
        String selected = requireSingle(request(
                game,
                decisionClass,
                message,
                1,
                1,
                options,
                context,
                source
        ));
        return yes.equals(selected);
    }

    private int chooseNumber(
            String decisionClass,
            String message,
            int min,
            int max,
            Ability source,
            Game game
    ) {
        if (max < min) {
            fail("BRIDGE_PROTOCOL_ERROR", "numeric bounds reversed: " + min + ".." + max);
        }
        JsonObject context = new JsonObject();
        context.addProperty("numeric_min", min);
        context.addProperty("numeric_max", max);
        XmageFullGameDecisionController.DecisionResponse response = request(
                game,
                decisionClass,
                message,
                0,
                0,
                new JsonArray(),
                context,
                source
        );
        if (response.numericChoice() == null) {
            fail("PILOT_RESPONSE_INVALID", "numeric choice required for " + decisionClass);
        }
        return response.numericChoice();
    }

    private XmageFullGameDecisionController.DecisionResponse request(
            Game game,
            String decisionClass,
            String prompt,
            int min,
            int max,
            JsonArray options,
            JsonObject context,
            Ability source
    ) {
        return decisionController.request(
                game,
                this,
                decisionClass,
                prompt,
                min,
                max,
                options,
                context,
                sourceMetadata(source, game)
        );
    }

    private JsonArray objectOptions(List<UUID> ids, Game game, String optionType) {
        JsonArray options = new JsonArray();
        for (UUID id : ids) {
            options.add(XmageFullGameDecisionController.option(
                    id.toString(),
                    objectLabel(id, game),
                    optionType,
                    objectMetadata(id, objectLabel(id, game))
            ));
        }
        return options;
    }

    private JsonObject sourceMetadata(Ability source, Game game) {
        if (source == null) {
            return null;
        }
        JsonObject metadata = new JsonObject();
        if (source.getSourceId() == null) {
            metadata.add("source_object_id", JsonNull.INSTANCE);
        } else {
            metadata.addProperty("source_object_id", source.getSourceId().toString());
        }
        metadata.addProperty("ability_original_id", source.getOriginalId().toString());
        metadata.addProperty("ability_type", source.getAbilityType().name().toLowerCase());
        MageObject object = game.getObject(source);
        if (object != null) {
            metadata.addProperty("source_name", object.getName());
        }
        return metadata;
    }

    private JsonObject abilityMetadata(Ability ability, Game game) {
        JsonObject metadata = new JsonObject();
        metadata.addProperty("ability_original_id", ability.getOriginalId().toString());
        metadata.addProperty("ability_type", ability.getAbilityType().name().toLowerCase());
        if (ability.getSourceId() != null) {
            metadata.addProperty("source_object_id", ability.getSourceId().toString());
            metadata.addProperty("source_name", objectLabel(ability.getSourceId(), game));
        }
        metadata.addProperty("mana_ability", ability.isManaAbility());
        return metadata;
    }

    private String abilityLabel(Ability ability, Game game) {
        String sourceName = ability.getSourceId() == null
                ? "unknown source"
                : objectLabel(ability.getSourceId(), game);
        return sourceName + " — " + ability.toString();
    }

    private String abilityOptionId(String prefix, Ability ability) {
        return optionId(
                prefix,
                ability.getSourceId() == null ? "<none>" : ability.getSourceId().toString(),
                ability.getOriginalId().toString()
        );
    }

    private String abilitySortKey(Ability ability) {
        return (ability.getSourceId() == null ? "" : ability.getSourceId().toString())
                + ":" + ability.getOriginalId();
    }

    private String objectLabel(UUID id, Game game) {
        Player player = game.getPlayer(id);
        if (player != null) {
            return player.getName();
        }
        Permanent permanent = game.getPermanent(id);
        if (permanent != null) {
            return permanent.getName();
        }
        Card card = game.getCard(id);
        if (card != null) {
            return card.getName();
        }
        MageObject object = game.getObject(id);
        if (object != null) {
            return object.getName();
        }
        return id.toString();
    }

    private static JsonObject objectMetadata(UUID id, String label) {
        JsonObject metadata = new JsonObject();
        metadata.addProperty("object_id", id.toString());
        metadata.addProperty("name", label);
        return metadata;
    }

    private static JsonObject pileMetadata(List<? extends Card> pile) {
        JsonObject metadata = new JsonObject();
        JsonArray cards = new JsonArray();
        if (pile != null) {
            for (Card card : pile) {
                JsonObject item = new JsonObject();
                item.addProperty("object_id", card.getId().toString());
                item.addProperty("name", card.getName());
                cards.add(item);
            }
        }
        metadata.add("cards", cards);
        return metadata;
    }

    private static String optionId(String... parts) {
        return XmageFullGameDecisionController.stableId(parts);
    }

    private static String requireSingle(
            XmageFullGameDecisionController.DecisionResponse response
    ) {
        if (response.selectedOptionIds().size() != 1) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "PILOT_RESPONSE_INVALID: exactly one option required"
            );
        }
        return response.selectedOptionIds().get(0);
    }

    private void fail(String code, String detail) {
        decisionController.failClosed(code, detail);
        throw new XmageFullGameDecisionController.DecisionException(code + ": " + detail);
    }
}
