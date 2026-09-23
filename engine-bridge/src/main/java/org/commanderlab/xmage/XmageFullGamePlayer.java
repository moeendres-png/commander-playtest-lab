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
import mage.abilities.PlayLandAbility;
import mage.abilities.SpellAbility;
import mage.abilities.TriggeredAbility;
import mage.abilities.costs.Cost;
import mage.abilities.costs.common.SacrificeSourceCost;
import mage.abilities.costs.common.TapSourceCost;
import mage.abilities.costs.common.UntapSourceCost;
import mage.abilities.costs.mana.ManaCost;
import mage.cards.Card;
import mage.cards.Cards;
import mage.cards.decks.Deck;
import mage.choices.Choice;
import mage.constants.ManaType;
import mage.constants.MultiAmountType;
import mage.constants.Outcome;
import mage.constants.RangeOfInfluence;
import mage.constants.Zone;
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
import java.util.concurrent.ConcurrentHashMap;

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

    /**
     * Set when the external pilot selects Cancel inside a mana-payment
     * decision. The engine then aborts the in-progress activation/cast.
     * That abort is graceful (the pilot declined to fund the action), so
     * {@link #priority} maps it to passing priority instead of failing the
     * game. Any activation/cast failure WITHOUT a preceding cancel stays
     * fatal. Reset on every priority entry; single-threaded game loop.
     */
    private boolean paymentCancelled;

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
    public SpellAbility chooseAbilityForCast(Card card, Game game, boolean noMana) {
        if (card == null || game == null) {
            fail("BRIDGE_PROTOCOL_ERROR", "cast ability choice requires card and game");
            return null;
        }
        Zone zone = game.getState().getZone(card.getMainCard().getId());
        Map<UUID, SpellAbility> castable = PlayerImpl.getCastableSpellAbilities(
                game,
                getId(),
                card,
                zone,
                noMana
        );
        if (castable.isEmpty()) {
            fail("NO_LEGAL_ACTION", "XMage supplied no castable spell ability for " + card.getIdName());
            return null;
        }
        List<SpellAbility> legal = castable.values().stream()
                .sorted(Comparator.comparing(this::abilitySortKey))
                .toList();
        if (legal.size() == 1) {
            // WS229 F-RULES-03 disposition: no discretion exists with one
            // lawful ability, so the forced move auto-submits with a logged
            // forced-move record instead of bypassing pilot+transcript silently.
            SpellAbility only = legal.get(0);
            decisionController.recordForcedMove(
                    "choice",
                    "Choose how to cast " + card.getName(),
                    "single castable ability: " + abilityLabel(only, game)
            );
            return only;
        }

        JsonArray options = new JsonArray();
        Map<String, SpellAbility> byOption = new LinkedHashMap<>();
        for (SpellAbility ability : legal) {
            String optionId = abilityOptionId("cast-choice", ability);
            JsonObject metadata = abilityMetadata(ability, game);
            metadata.addProperty("card_id", card.getId().toString());
            metadata.addProperty("card_name", card.getName());
            metadata.addProperty("zone", zone == null ? "unknown" : zone.name().toLowerCase());
            metadata.addProperty("no_mana", noMana);
            options.add(XmageFullGameDecisionController.option(
                    optionId,
                    abilityLabel(ability, game),
                    "cast_ability",
                    metadata
            ));
            byOption.put(optionId, ability);
        }
        JsonObject context = new JsonObject();
        context.addProperty("choice_domain", "cast_ability");
        context.addProperty("card_id", card.getId().toString());
        context.addProperty("card_name", card.getName());
        context.addProperty("zone", zone == null ? "unknown" : zone.name().toLowerCase());
        context.addProperty("no_mana", noMana);
        String selected = requireSingle(request(
                game,
                "choice",
                "Choose how to cast " + card.getName(),
                1,
                1,
                options,
                context,
                null
        ));
        SpellAbility chosen = byOption.get(selected);
        if (chosen == null) {
            fail("ILLEGAL_ACTION", "cast ability option disappeared: " + selected);
        }
        return chosen;
    }

    @Override
    public ActivatedAbility chooseLandOrSpellAbility(Card card, Game game, boolean noMana) {
        if (card == null || game == null) {
            fail("BRIDGE_PROTOCOL_ERROR", "land-or-spell choice requires card and game");
            return null;
        }
        Zone zone = game.getState().getZone(card.getMainCard().getId());
        Map<UUID, ActivatedAbility> legalById = new LinkedHashMap<>();
        PlayerImpl.getCastableSpellAbilities(game, getId(), card, zone, noMana)
                .forEach(legalById::putIfAbsent);
        getPlayableActivatedAbilities(card, zone, game).forEach((abilityId, ability) -> {
            if (ability instanceof PlayLandAbility) {
                legalById.putIfAbsent(abilityId, ability);
            }
        });
        if (legalById.isEmpty()) {
            fail("NO_LEGAL_ACTION", "XMage supplied no legal land-or-spell ability for " + card.getIdName());
            return null;
        }
        List<ActivatedAbility> legal = legalById.values().stream()
                .sorted(Comparator.comparing(this::abilitySortKey))
                .toList();
        if (legal.size() == 1) {
            // WS229 F-RULES-03 disposition: single lawful ability, logged
            // forced move (see chooseAbilityForCast).
            ActivatedAbility only = legal.get(0);
            decisionController.recordForcedMove(
                    "choice",
                    "Choose land or spell ability for " + card.getName(),
                    "single legal ability: " + abilityLabel(only, game)
            );
            return only;
        }

        JsonArray options = new JsonArray();
        Map<String, ActivatedAbility> byOption = new LinkedHashMap<>();
        for (ActivatedAbility ability : legal) {
            String optionId = abilityOptionId("land-or-spell-choice", ability);
            JsonObject metadata = abilityMetadata(ability, game);
            metadata.addProperty("card_id", card.getId().toString());
            metadata.addProperty("card_name", card.getName());
            metadata.addProperty("zone", zone == null ? "unknown" : zone.name().toLowerCase());
            metadata.addProperty("no_mana", noMana);
            options.add(XmageFullGameDecisionController.option(
                    optionId,
                    abilityLabel(ability, game),
                    ability instanceof PlayLandAbility ? "play_land_ability" : "cast_ability",
                    metadata
            ));
            byOption.put(optionId, ability);
        }
        JsonObject context = new JsonObject();
        context.addProperty("choice_domain", "land_or_spell_ability");
        context.addProperty("card_id", card.getId().toString());
        context.addProperty("card_name", card.getName());
        context.addProperty("zone", zone == null ? "unknown" : zone.name().toLowerCase());
        context.addProperty("no_mana", noMana);
        String selected = requireSingle(request(
                game,
                "choice",
                "Choose land or spell ability for " + card.getName(),
                1,
                1,
                options,
                context,
                null
        ));
        ActivatedAbility chosen = byOption.get(selected);
        if (chosen == null) {
            fail("ILLEGAL_ACTION", "land-or-spell option disappeared: " + selected);
        }
        return chosen;
    }

    @Override
    public boolean priority(Game game) {
        paymentCancelled = false;
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
        // Spell abilities enumerated by getPlayable are cast, never
        // "activated": the engine owns timing, costs (incl. commander tax),
        // payment (pool auto-spend, bookmark rollback on failure), targets,
        // and resolution. Anything the harness cannot operate (targets,
        // modes, choices, shortfall payments) surfaces as further engine
        // decisions, which the caller must handle or fail closed on.
        if (ability instanceof SpellAbility) {
            boolean cast = cast(
                    (SpellAbility) ability, game, false,
                    new mage.ApprovingObject(ability, game));
            if (!cast) {
                if (paymentCancelled) {
                    // Pilot cancelled funding mid-payment: abort gracefully
                    // by passing priority. Partial payments (tapped sources,
                    // floated pool mana) are real game state and persist.
                    pass(game);
                    return false;
                }
                fail("XMAGE_ACTION_EXECUTION_FAILED", "priority cast failed: " + selected);
            }
            return true;
        }
        boolean activated = activateAbility(ability, game);
        if (!activated) {
            if (paymentCancelled) {
                // Pilot cancelled funding mid-payment: abort gracefully
                // by passing priority. Partial payments (tapped sources,
                // floated pool mana) are real game state and persist.
                pass(game);
                return false;
            }
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
        JsonObject supplied = null;
        // WS229 F-RULES-03 disposition: bottom-of-library selection is
        // identified by the native putCardsOnBottomOfLibrary path (callback
        // identity), never by prompt-text heuristics in the Lab.
        if (BOTTOM_SELECTION.get()) {
            supplied = new JsonObject();
            supplied.addProperty("bottom_of_library_selection", true);
        }
        return chooseTargetInternal(outcome, false, target, source, game, cards, supplied);
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
        int amount = requireNumericChoice(response, "target_amount");
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
        // WS92-D4 key-mode Choice projection (systemic reacquisition).
        // Alternative-cost and modal menus carry items in keyChoices while the
        // plain choice set stays empty; projecting zero options would silently
        // cancel the cast. Project key -> engine text and record the pick by
        // key. The engine alone supplies the eligible set; the adapter never
        // computes legality.
        if (choice.isKeyChoice() && !choice.getKeyChoices().isEmpty()) {
            List<String> keys = new ArrayList<>(choice.getKeyChoices().keySet());
            keys.sort(String::compareTo);
            JsonArray options = new JsonArray();
            Map<String, String> byOption = new HashMap<>();
            for (String key : keys) {
                String text = choiceText(choice.getKeyChoices().get(key));
                String optionId = optionId("choice-key", key);
                JsonObject metadata = new JsonObject();
                metadata.addProperty("choice_key", key);
                metadata.addProperty("choice", text == null ? key : text);
                options.add(XmageFullGameDecisionController.option(
                        optionId, text == null ? key : text, "choice", metadata));
                byOption.put(optionId, key);
            }
            String selected = requireSingle(request(
                    game,
                    "choice",
                    choicePrompt(choice),
                    1,
                    1,
                    options,
                    outcomeContext(outcome),
                    null
            ));
            String key = byOption.get(selected);
            if (key == null) {
                fail("ILLEGAL_ACTION", "choice option disappeared: " + selected);
            }
            choice.setChoiceByKey(key, false);
            return true;
        }
        List<String> values = new ArrayList<>(choice.getChoices());
        values.sort(String::compareTo);
        JsonArray options = new JsonArray();
        Map<String, String> choices = new HashMap<>();
        for (String raw : values) {
            String value = choiceText(raw);
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
                choicePrompt(choice),
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

    private static final java.util.regex.Pattern CHOICE_SHORT_ID =
            java.util.regex.Pattern.compile(" \\[[0-9a-z]{1,8}\\]");

    /**
     * WS92-D4 twin-stable choice text (systemic reacquisition). Strips
     * per-game identity from engine choice text (UUIDs plus GameLog short-id
     * suffixes like "Force of Will [bd5]"); Rules content untouched.
     */
    private static String choiceText(String text) {
        if (text == null) {
            return null;
        }
        String redacted = XmageFullGameDecisionController.redactObjectIds(text);
        return CHOICE_SHORT_ID.matcher(redacted).replaceAll(" [#]");
    }

    /** Engine choice message (with sub-message) or the legacy generic prompt. */
    private static String choicePrompt(Choice choice) {
        try {
            String message = choice.getMessage();
            String sub = choice.getSubMessage();
            String combined = ((message == null ? "" : message)
                    + " " + (sub == null ? "" : sub)).trim();
            if (!combined.isEmpty()) {
                return choiceText(combined);
            }
        } catch (RuntimeException ignored) {
            // Fall through to the legacy prompt.
        }
        return "Choose option";
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
        Map<String, ManaType> poolManaById = new LinkedHashMap<>();
        String cancel = optionId("mana", "cancel");
        options.add(XmageFullGameDecisionController.option(
                cancel,
                "Cancel mana payment",
                "cancel_mana_payment",
                new JsonObject()
        ));
        ManaType.getTrueManaTypes().stream()
                .filter(manaType -> getManaPool().get(manaType) > 0)
                .sorted(Comparator.comparing(Enum::name))
                .forEach(manaType -> {
                    String optionId = optionId("mana-pool", manaType.name());
                    JsonObject metadata = new JsonObject();
                    metadata.addProperty("mana_type", manaType.toString());
                    metadata.addProperty("mana_available", getManaPool().get(manaType));
                    options.add(XmageFullGameDecisionController.option(
                            optionId,
                            "Spend " + manaType.toString() + " mana from pool",
                            "mana_pool",
                            metadata
                    ));
                    poolManaById.put(optionId, manaType);
                });
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
            paymentCancelled = true;
            return false;
        }
        ManaType poolManaType = poolManaById.get(selected);
        if (poolManaType != null) {
            getManaPool().unlockManaType(poolManaType);
            return true;
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
        // WS92-D5 twin-stable frame sequence (systemic reacquisition): native
        // UUIDs are random per game, so declaration order follows Rules-visible
        // content (name, entry order, characteristics), never native identity.
        attackers.sort(stablePermanentOrder(game));
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
        // WS92-D5 twin-stable frame sequence (see selectAttackers):
        // declaration order among co-blockers carries no Rules content itself.
        blockers.sort(stablePermanentOrder(game));
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

    /**
     * WS92-D5 twin-stable permanent order over Rules-visible content
     * (systemic reacquisition). Native UUIDs (and their string forms) are
     * random per game and must never sequence decision frames; names, entry
     * order (zone-change counter), and characteristics reproduce identically
     * on twin re-execution. No Rules content: co-declaration order is a
     * replay framing choice, never legality.
     */
    private static Comparator<Permanent> stablePermanentOrder(Game game) {
        return Comparator
                .comparing(
                        (Permanent permanent) -> permanent.getName(),
                        Comparator.nullsFirst(String::compareTo))
                .thenComparingInt(permanent -> permanent.getZoneChangeCounter(game))
                .thenComparingInt(permanent -> permanent.getPower().getValue())
                .thenComparingInt(permanent -> permanent.getToughness().getValue())
                .thenComparing(permanent -> permanent.isTapped())
                .thenComparingInt(Permanent::getDamage);
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
        // WS229 joint restoration (F-RULES-02b closed): ONE joint frame with
        // the full legs+totals domain. The pilot makes a single strategic
        // vector choice; per-leg sequential frames never reappear as pilot
        // decisions. Validation is the exact isGoodValues projection.
        if (messages == null || messages.isEmpty()) {
            return List.of();
        }
        if (totalMax < totalMin) {
            fail("BRIDGE_PROTOCOL_ERROR",
                    "multi amount total band reversed: " + totalMin + ".." + totalMax);
        }
        long minSum = 0L;
        long maxSum = 0L;
        JsonArray legs = new JsonArray();
        for (MultiAmountMessage message : messages) {
            if (message == null) {
                fail("BRIDGE_PROTOCOL_ERROR", "multi amount leg is missing");
            }
            if (message.max < message.min) {
                fail("BRIDGE_PROTOCOL_ERROR", "multi amount leg has reversed bounds");
            }
            minSum += message.min;
            maxSum += message.max;
            JsonObject leg = new JsonObject();
            leg.addProperty("min", message.min);
            leg.addProperty("max", message.max);
            leg.addProperty("prompt", message.message == null ? "" : message.message);
            legs.add(leg);
        }
        if (minSum > totalMax || maxSum < totalMin) {
            fail("PILOT_RESPONSE_INVALID",
                    "multi amount domain infeasible: legs admit " + minSum + ".." + maxSum
                            + " but total requires " + totalMin + ".." + totalMax);
        }
        JsonObject context = new JsonObject();
        context.add("numeric_legs", legs);
        context.addProperty("numeric_total_min", totalMin);
        context.addProperty("numeric_total_max", totalMax);
        context.addProperty("outcome", outcome == null ? "neutral" : outcome.name().toLowerCase());
        XmageFullGameDecisionController.DecisionResponse response = request(
                game,
                "multi_amount",
                "Assign amounts (" + messages.size() + " legs)",
                0,
                0,
                new JsonArray(),
                context,
                null
        );
        List<Integer> chosen = requireJointChoices(response, context, "multi_amount");
        // Native authority gate: the engine's own isGoodValues predicate
        // over the original messages must accept the projected vector.
        // Any divergence between the Lab/controller projection and native
        // semantics fails closed here, never silently.
        if (!MultiAmountType.isGoodValues(chosen, messages, totalMin, totalMax)) {
            fail("PILOT_RESPONSE_INVALID",
                    "multi amount vector rejected by native isGoodValues gate");
        }
        return chosen;
    }

    /**
     * WS229 joint isGoodValues projection: exact vector length, strict
     * integer elements, per-leg inclusive membership, total band. Any
     * violation fails closed; there is no clamp, default, or fallback.
     */
    List<Integer> requireJointChoices(
            XmageFullGameDecisionController.DecisionResponse response,
            JsonObject context,
            String decisionClass
    ) {
        if (response == null || response.numericChoices() == null) {
            fail("PILOT_RESPONSE_INVALID", "joint numeric choice required for " + decisionClass);
        }
        try {
            XmageFullGameDecisionController.requireJointVector(response.numericChoices(), context);
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            fail("PILOT_RESPONSE_INVALID", stripCode(exc.getMessage()));
        }
        return List.copyOf(response.numericChoices());
    }

    private static String stripCode(String message) {
        if (message == null) {
            return "joint numeric choice rejected";
        }
        int colon = message.indexOf(':');
        return colon < 0 ? message : message.substring(colon + 1).trim();
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

    /**
     * WS213 one-shot principal-bound concession authorizations. The set holds
     * the exact native player UUIDs whose next synchronous {@code concede}
     * call was authorized by {@link XmageFullGameSession#submitConcede} after
     * a live {@code Game.canConcede} check. It is an authorization token, not
     * a decision: availability and selection stay engine/pilot-owned.
     */
    private final Set<UUID> concessionArmed = ConcurrentHashMap.newKeySet();

    void armConcession(UUID principal) {
        if (principal == null || !principal.equals(getId())) {
            fail("PILOT_RESPONSE_INVALID", "concession arming requires the exact principal");
        }
        concessionArmed.add(principal);
    }

    void disarmConcession(UUID principal) {
        concessionArmed.remove(principal);
    }

    @Override
    public void concede(Game game) {
        // WS213: unattributed engine calls (idle timeout, inherited defaults)
        // still fail closed. Only a submitConcede-authorized synchronous call
        // for the exact principal reaches the native PlayerImpl path.
        if (game != null && concessionArmed.remove(getId())) {
            super.concede(game);
            return;
        }
        fail("OUT_OF_SCOPE_DECISION", "concession is not part of Commander full-game conformance");
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

        // WS92-D2 Rules-entitled hidden-zone look window (systemic
        // reacquisition). The engine alone selected the eligible set; the
        // adapter only projects identities the deciding principal is entitled
        // to see while choosing (paper search/scry is a look), then closes
        // the window. Creates no Rules semantics: no legality, target, cost,
        // or outcome is computed or altered here.
        Player lookOwner = lookOwnerFor(restrictedCards, game);
        boolean lookGranted = false;
        if (lookOwner != null) {
            XmageFullGameStateRedactor.beginZoneFullLook(this, lookOwner, game);
            lookGranted = true;
        }
        try {
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
        } finally {
            if (lookGranted) {
                XmageFullGameStateRedactor.endZoneFullLook(this, lookOwner);
            }
        }
    }

    /**
     * Owner of the first library-zone card in a restricted decision set, or
     * null when the set involves no hidden library identities (hand,
     * battlefield, graveyard, stack and exile projections need no grant).
     */
    private Player lookOwnerFor(Cards restrictedCards, Game game) {
        if (restrictedCards == null || game == null) {
            return null;
        }
        try {
            for (Card card : restrictedCards.getCards(game)) {
                if (card == null) {
                    continue;
                }
                Card main = card.getMainCard();
                Zone zone = game.getState().getZone(main.getId());
                if (zone == null) {
                    zone = game.getState().getZone(card.getId());
                }
                if (zone == Zone.LIBRARY && card.getOwnerId() != null) {
                    Player owner = game.getPlayer(card.getOwnerId());
                    if (owner != null) {
                        return owner;
                    }
                }
            }
        } catch (RuntimeException ignored) {
            return null;
        }
        return null;
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
        return requireNumericChoice(response, decisionClass);
    }

    int requireNumericChoice(
            XmageFullGameDecisionController.DecisionResponse response,
            String decisionClass
    ) {
        if (response == null || response.numericChoice() == null) {
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
        enrichAbilityCostFacts(metadata, ability, game);
        return metadata;
    }

    /**
     * Attaches engine-factual activation-cost summary to ability metadata.
     *
     * <p>These are translated representations of engine cost objects, not
     * legality judgments: mana-amount breakdown, whether activation taps,
     * untaps, or sacrifices the source, and whether the source permanent is
     * currently tapped. External pilots use them for affordability-aware
     * discretionary choice among engine-authorized options. All enrichment is
     * defensive: any introspection failure leaves the fields absent and the
     * pilot treats them as unknown.</p>
     */
    private void enrichAbilityCostFacts(JsonObject metadata, Ability ability, Game game) {
        mage.Mana costMana = null;
        try {
            costMana = ability.getManaCostsToPay().getMana();
            if (costMana != null) {
                metadata.addProperty("mana_cost_white", costMana.getWhite());
                metadata.addProperty("mana_cost_blue", costMana.getBlue());
                metadata.addProperty("mana_cost_black", costMana.getBlack());
                metadata.addProperty("mana_cost_red", costMana.getRed());
                metadata.addProperty("mana_cost_green", costMana.getGreen());
                metadata.addProperty("mana_cost_generic", costMana.getGeneric());
                metadata.addProperty("mana_cost_colorless", costMana.getColorless());
            }
        } catch (RuntimeException ignored) {
            // Leave mana-cost fields absent; pilot treats them as unknown.
        }
        try {
            // Lossless projection of the engine-native payability fact:
            // can the deciding player's CURRENT pool fund the mana costs
            // (Mana.enough carries native color/generic/colorless semantics)?
            // Tappable permanents are deliberately excluded: pool-only
            // coverage is the conservative discretionary signal.
            if (costMana != null) {
                metadata.addProperty(
                        "pool_covers_mana_cost",
                        costMana.enough(getManaPool().getMana())
                );
            }
        } catch (RuntimeException ignored) {
            // Leave the coverage flag absent; pilot treats it as unknown.
        }
        try {
            boolean requiresTap = false;
            boolean requiresUntap = false;
            boolean requiresSacrifice = false;
            for (Cost cost : ability.getCosts()) {
                if (cost instanceof TapSourceCost) {
                    requiresTap = true;
                } else if (cost instanceof UntapSourceCost) {
                    requiresUntap = true;
                } else if (cost instanceof SacrificeSourceCost) {
                    requiresSacrifice = true;
                }
            }
            metadata.addProperty("requires_tap_source", requiresTap);
            metadata.addProperty("requires_untap_source", requiresUntap);
            metadata.addProperty("requires_sacrifice_source", requiresSacrifice);
        } catch (RuntimeException ignored) {
            // Leave cost-kind fields absent; pilot treats them as unknown.
        }
        try {
            if (ability.getSourceId() != null && game != null) {
                Permanent source = game.getPermanent(ability.getSourceId());
                if (source != null) {
                    metadata.addProperty("source_tapped", source.isTapped());
                }
            }
        } catch (RuntimeException ignored) {
            // Leave source-tapped field absent; pilot treats it as unknown.
        }
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

    /**
     * WS229 F-RULES-03 disposition: marks the native
     * putCardsOnBottomOfLibrary selection path (London mulligan bottom and
     * other bottom-of-library orderings) so the Lab routes by structured
     * context instead of prompt-text sniffing. Proven path: PlayerImpl
     * funnels bottom selection through
     * {@code choose(Outcome, Cards, TargetCard, Ability, Game)} (pinned
     * 1.4.61 bytecode). Thread-local because the engine drives each player
     * on its game thread; always cleared in {@code finally}.
     */
    private static final ThreadLocal<Boolean> BOTTOM_SELECTION =
            ThreadLocal.withInitial(() -> Boolean.FALSE);

    @Override
    public boolean putCardsOnBottomOfLibrary(Cards cards, Game game, Ability source, boolean anyOrder) {
        BOTTOM_SELECTION.set(Boolean.TRUE);
        try {
            return super.putCardsOnBottomOfLibrary(cards, game, source, anyOrder);
        } finally {
            BOTTOM_SELECTION.set(Boolean.FALSE);
        }
    }
}
