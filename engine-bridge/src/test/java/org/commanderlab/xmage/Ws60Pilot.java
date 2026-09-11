package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * WS60 principal-disciplined scenario pilot.
 *
 * <p>The pilot answers engine-authoritative decision frames using only the
 * frame itself plus its embedded entitled {@code pilot_state} (exactly what
 * the deciding principal may see). It never reads live engine objects, never
 * synthesizes legality, and never selects options outside the offered set.
 * Any choice-class decision without an explicit scenario mapping fails the
 * run closed via {@link PilotGapException} (no silent yes/no defaults).</p>
 */
final class Ws60Pilot {

    /** Fail-closed pilot gap: a choice the scenario left unmapped. */
    static final class PilotGapException extends RuntimeException {
        PilotGapException(String message) {
            super(message);
        }
    }

    /** Engine fault surfacing (terminal controller failure, timeouts). */
    static final class EngineFaultException extends RuntimeException {
        EngineFaultException(String message) {
            super(message);
        }

        EngineFaultException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    /** What to do with a priority frame. */
    enum PriorityIntent {
        PLAY_LAND,
        CAST,
        ACTIVATE,
        PASS
    }

    record PriorityPlan(PriorityIntent intent, String cardOrLabelFragment) {
    }

    record TargetRule(String descriptionFragment, String nameMatch, Integer ownerRqSeat) {
    }

    private final String scenarioId;
    /** RQ seat -> ordered setup card names to cast when offered. */
    private final Map<Integer, List<String>> setupCasts = new LinkedHashMap<>();
    /** RQ seat -> commander cast allowed (default false). */
    private final Map<Integer, Boolean> commanderCastAllowed = new LinkedHashMap<>();
    /** RQ seat -> ordered ability label fragments to activate when offered. */
    private final Map<Integer, List<String>> setupActivates = new LinkedHashMap<>();
    /** RQ seats allowed to activate Thrasios-style assembly filtering. */
    private final Map<Integer, Boolean> assemblyFiltering = new LinkedHashMap<>();
    /** RQ seats that never attack (default: all hold unless mapped). */
    private final Map<String, Integer> attackers = new LinkedHashMap<>();
    /** blocker name -> attacker names to block. */
    private final Map<String, List<String>> blockers = new LinkedHashMap<>();
    private final List<TargetRule> targetRules = new ArrayList<>();
    /** Ordered mode keywords to pick, then stop. */
    private final List<String> modeKeywords = new ArrayList<>();
    /** Ordered replacement source-name preference. */
    private final List<String> replacementPreference = new ArrayList<>();
    /** message fragment -> yes/no. */
    private final Map<String, Boolean> booleans = new LinkedHashMap<>();
    /** source-name fragment -> announced number. */
    private final Map<String, Integer> numerics = new LinkedHashMap<>();
    /** multi-amount message fragment -> single amount for that message. */
    private final Map<String, Integer> multiAmounts = new LinkedHashMap<>();
    /** card name to find in searches (per description fragment, "" = any). */
    private final Map<String, String> searchPicks = new LinkedHashMap<>();
    /** hand-selection mapping (description fragment -> card name), e.g. pitch costs. */
    private final Map<String, String> handPicks = new LinkedHashMap<>();
    /** "choice"-class prompt fragment -> label fragment to pick. */
    private final Map<String, String> choicePicks = new LinkedHashMap<>();
    /** mulligan seek: seat -> card names that justify a keep. */
    private final Map<Integer, SeekRule> seekRules = new LinkedHashMap<>();
    /** preferred land play order (names); others after. */
    private final List<String> landPreference = new ArrayList<>();
    /** RQ seat -> known land names for land-play recognition. */
    private final Map<Integer, List<String>> seatLands = new LinkedHashMap<>();
    /** RQ seat -> land play preference order (overrides global). */
    private final Map<Integer, List<String>> seatLandOrder = new LinkedHashMap<>();
    /** frame predicates marking acceptance-critical frames. */
    private final List<String> criticalMarks = new ArrayList<>();
    /** RQ seat -> card -> required battlefield fragments (any seat, public). */
    private final Map<Integer, Map<String, List<String>>> castGates = new LinkedHashMap<>();
    /** RQ seat -> card -> required stack fragments. */
    private final Map<Integer, Map<String, List<String>>> stackGates = new LinkedHashMap<>();
    /** RQ seat -> card -> full turns to wait after first observation. */
    private final Map<Integer, Map<String, Integer>> delayGates = new LinkedHashMap<>();
    /** RQ seat -> card -> battlefield trigger fragment to wait for. */
    private final Map<Integer, Map<String, String>> delayTriggers = new LinkedHashMap<>();
    /** RQ seat -> card -> minimum turn number for the cast. */
    private final Map<Integer, Map<String, Integer>> turnGates = new LinkedHashMap<>();
    /** RQ seat -> card -> (battlefield fragment, minimum count). */
    private final Map<Integer, Map<String, Map.Entry<String, Integer>>> countGates = new LinkedHashMap<>();
    /** RQ seat -> hand-land threshold for gas-seeking scry (bottom lands). */
    private final Map<Integer, Integer> scryGas = new LinkedHashMap<>();

    Ws60Pilot scryGas(int rqSeat, int handLandsThreshold) {
        scryGas.put(rqSeat, handLandsThreshold);
        return this;
    }

    /** RQ seat -> hand fragments that trigger answer-holding (skip all casts). */
    private final Map<Integer, List<String>> holdForAnswer = new LinkedHashMap<>();

    Ws60Pilot holdForAnswer(int rqSeat, String... handFragments) {
        holdForAnswer.computeIfAbsent(rqSeat, ignored -> new ArrayList<>())
                .addAll(List.of(handFragments));
        return this;
    }

    /** RQ seat -> land names to preserve untapped for generic payments. */
    private final Map<Integer, List<String>> reserveTaps = new LinkedHashMap<>();

    Ws60Pilot reserveTaps(int rqSeat, String... landNames) {
        reserveTaps.computeIfAbsent(rqSeat, ignored -> new ArrayList<>())
                .addAll(List.of(landNames));
        return this;
    }

    /** RQ seat -> max assembly-filter activations per turn (default unlimited). */
    private final Map<Integer, Integer> filterCaps = new LinkedHashMap<>();
    /** RQ seat -> turn -> filter activations used. */
    private final Map<Integer, Map<Integer, Integer>> filterUsed = new LinkedHashMap<>();
    /** RQ seat -> minimum untapped permanents required to filter (answer buffer). */
    private final Map<Integer, Integer> filterUntappedMin = new LinkedHashMap<>();

    Ws60Pilot filterMaxPerTurn(int rqSeat, int max) {
        filterCaps.put(rqSeat, max);
        return this;
    }

    Ws60Pilot filterMinUntapped(int rqSeat, int min) {
        filterUntappedMin.put(rqSeat, min);
        return this;
    }

    private boolean filterBudgetLeft(int seat, JsonObject view) {
        Integer cap = filterCaps.get(seat);
        if (cap == null) {
            return true;
        }
        int turn = viewTurn(view);
        int used = filterUsed.getOrDefault(seat, Map.of()).getOrDefault(turn, 0);
        if (System.getenv("WS60_DEBUG_FILTER") != null) {
            System.err.println("WS60DBG budget seat=" + seat + " turn=" + turn + " used=" + used
                    + " cap=" + cap + " caps=" + filterCaps);
        }
        return used < cap;
    }

    private boolean filterUntappedOk(int seat, JsonObject view) {
        Integer min = filterUntappedMin.get(seat);
        if (min == null) {
            return true;
        }
        List<String> reserved = reserveTaps.getOrDefault(seat, List.of());
        long untapped = Ws60Views.battlefield(view, seat).stream()
                .filter(entry -> !entry.tapped()
                        && reserved.stream().noneMatch(entry.name()::contains))
                .count();
        return untapped >= min;
    }

    private void spendFilterBudget(int seat, JsonObject view) {
        if (!filterCaps.containsKey(seat)) {
            return;
        }
        int turn = viewTurn(view);
        Map<Integer, Integer> used = filterUsed.computeIfAbsent(seat,
                ignored -> new LinkedHashMap<>());
        used.put(turn, used.getOrDefault(turn, 0) + 1);
        if (System.getenv("WS60_DEBUG_FILTER") != null) {
            System.err.println("WS60DBG spend seat=" + seat + " turn=" + turn + " used-now="
                    + used.get(turn));
        }
    }

    private boolean holdingForAnswer(int seat, JsonObject view) {
        List<String> fragments = holdForAnswer.getOrDefault(seat, List.of());
        if (fragments.isEmpty()) {
            return false;
        }
        List<String> hand = Ws60Views.handNames(view, seat);
        return fragments.stream().allMatch(
                fragment -> hand.stream().anyMatch(card -> card.contains(fragment)));
    }

    /** RQ seat -> fragments that halt all card-draw once secured (hand/battlefield/graveyard). */
    private final Map<Integer, List<String>> secureWhen = new LinkedHashMap<>();

    Ws60Pilot secureWhen(int rqSeat, String... fragments) {
        secureWhen.computeIfAbsent(rqSeat, ignored -> new ArrayList<>())
                .addAll(List.of(fragments));
        return this;
    }

    private boolean secured(int seat, JsonObject view) {
        List<String> fragments = secureWhen.getOrDefault(seat, List.of());
        if (fragments.isEmpty()) {
            return false;
        }
        List<String> hand = Ws60Views.handNames(view, seat);
        List<String> battlefield = viewOwnBattlefieldNames(view, seat);
        List<String> graveyard = viewOwnGraveyardNames(view, seat);
        List<String> stack = viewStackNames(view);
        return fragments.stream().allMatch(fragment ->
                hand.stream().anyMatch(card -> card.contains(fragment))
                        || battlefield.stream().anyMatch(card -> card.contains(fragment))
                        || graveyard.stream().anyMatch(card -> card.contains(fragment))
                        || stack.stream().anyMatch(card -> card.contains(fragment)));
    }

    static List<String> viewOwnGraveyardNames(JsonObject view, int seat) {
        List<String> out = new ArrayList<>();
        if (!view.has("players") || !view.get("players").isJsonArray()) {
            return out;
        }
        for (JsonElement player : view.getAsJsonArray("players")) {
            JsonObject row = player.getAsJsonObject();
            if (row.get("seat").getAsInt() != seat || !row.has("graveyard")
                    || !row.get("graveyard").isJsonArray()) {
                continue;
            }
            for (JsonElement card : row.getAsJsonArray("graveyard")) {
                out.add(card.getAsJsonObject().get("name").getAsString());
            }
        }
        return out;
    }
    /** Sequential multi-target script: description fragment -> names in pick order. */
    private final Map<String, List<String>> sequentialTargets = new LinkedHashMap<>();
    /** Sequential names already picked this run. */
    private final List<String> sequentialPicked = new ArrayList<>();
    /** RQ seat -> activation fragment -> required stack fragments. */
    private final Map<Integer, Map<String, List<String>>> activateGates = new LinkedHashMap<>();
    /** Activation fragments allowed only once per run. */
    private final List<String> activateOnceFragments = new ArrayList<>();
    /** Activation fragments already used this run. */
    private final List<String> activateOnceUsed = new ArrayList<>();

    Ws60Pilot activateOnce(String activationFragment) {
        activateOnceFragments.add(activationFragment);
        return this;
    }

    Ws60Pilot sequentialTargets(String descriptionFragment, List<String> namesInOrder) {
        sequentialTargets.put(descriptionFragment, List.copyOf(namesInOrder));
        return this;
    }
    /** attacker name -> minimum own-battlefield count to attack. */
    private final Map<String, Integer> attackCountGates = new LinkedHashMap<>();
    /** attacker name -> ordered defender seats (per-occurrence). */
    private final Map<String, List<Integer>> attackSequences = new LinkedHashMap<>();

    Ws60Pilot attackCountGate(String attackerName, int minCount) {
        attackCountGates.put(attackerName, minCount);
        return this;
    }

    private boolean attackCountOpen(String attacker, JsonObject frame) {
        Integer min = attackCountGates.get(attacker);
        if (min == null) {
            return true;
        }
        int seat = actorSeat(frame);
        long count = viewOwnBattlefieldNames(pilotState(frame), seat).stream()
                .filter(name -> name.contains(attacker)).count();
        return count >= min;
    }
    /** attacker name -> occurrences consumed. */
    private final Map<String, Integer> attackSequenceUsed = new LinkedHashMap<>();
    /** replacement source names already picked this run. */
    private final List<String> replacementPicked = new ArrayList<>();
    /** RQ seat -> fragments that trigger mana conservation (skip casts). */
    private final Map<Integer, List<String>> conserveTriggers = new LinkedHashMap<>();
    /** BATTLEFIELD fragment -> turns first observed, per seat (delay gates). */
    private final Map<Integer, Map<String, Integer>> firstSeenTurn = new LinkedHashMap<>();
    /** commander names by seat (to recognize commander cast options). */
    private final Map<Integer, List<String>> commanderNames = new LinkedHashMap<>();

    record SeekRule(List<String> names, int maxTries) {
    }

    Ws60Pilot(String scenarioId) {
        this.scenarioId = scenarioId;
    }

    String scenarioId() {
        return scenarioId;
    }

    Ws60Pilot setupCast(int rqSeat, String... cardNames) {
        setupCasts.computeIfAbsent(rqSeat, ignored -> new ArrayList<>()).addAll(List.of(cardNames));
        return this;
    }

    Ws60Pilot allowCommanderCast(int rqSeat) {
        commanderCastAllowed.put(rqSeat, true);
        return this;
    }

    Ws60Pilot commanders(int rqSeat, List<String> names) {
        commanderNames.put(rqSeat, List.copyOf(names));
        return this;
    }

    Ws60Pilot setupActivate(int rqSeat, String... labelFragments) {
        setupActivates.computeIfAbsent(rqSeat, ignored -> new ArrayList<>()).addAll(List.of(labelFragments));
        return this;
    }

    Ws60Pilot assemblyFiltering(int rqSeat) {
        assemblyFiltering.put(rqSeat, true);
        return this;
    }

    Ws60Pilot castGate(int rqSeat, String card, String... requiredBattlefieldFragments) {
        castGates.computeIfAbsent(rqSeat, ignored -> new LinkedHashMap<>())
                .computeIfAbsent(card, ignored -> new ArrayList<>())
                .addAll(List.of(requiredBattlefieldFragments));
        return this;
    }

    Ws60Pilot stackGate(int rqSeat, String card, String... requiredStackFragments) {
        stackGates.computeIfAbsent(rqSeat, ignored -> new LinkedHashMap<>())
                .computeIfAbsent(card, ignored -> new ArrayList<>())
                .addAll(List.of(requiredStackFragments));
        return this;
    }

    Ws60Pilot delayGate(int rqSeat, String card, int fullTurnsAfterSeen) {
        return delayGate(rqSeat, card, card, fullTurnsAfterSeen);
    }

    Ws60Pilot delayGate(int rqSeat, String waiterCard, String triggerFragment,
            int fullTurnsAfterSeen) {
        delayGates.computeIfAbsent(rqSeat, ignored -> new LinkedHashMap<>())
                .put(waiterCard, fullTurnsAfterSeen);
        delayTriggers.computeIfAbsent(rqSeat, ignored -> new LinkedHashMap<>())
                .put(waiterCard, triggerFragment);
        return this;
    }

    /** RQ seat -> card -> (own-battlefield fragment, minimum count). */
    private final Map<Integer, Map<String, Map.Entry<String, Integer>>> ownCountGates =
            new LinkedHashMap<>();

    Ws60Pilot turnGate(int rqSeat, String card, int minTurn) {
        turnGates.computeIfAbsent(rqSeat, ignored -> new LinkedHashMap<>())
                .put(card, minTurn);
        return this;
    }

    Ws60Pilot countGate(int rqSeat, String card, String fragment, int minCount) {
        countGates.computeIfAbsent(rqSeat, ignored -> new LinkedHashMap<>())
                .put(card, Map.entry(fragment, minCount));
        return this;
    }

    Ws60Pilot ownCountGate(int rqSeat, String card, String fragment, int minCount) {
        ownCountGates.computeIfAbsent(rqSeat, ignored -> new LinkedHashMap<>())
                .put(card, Map.entry(fragment, minCount));
        return this;
    }

    Ws60Pilot activateGate(int rqSeat, String activationFragment,
            String... requiredStackFragments) {
        activateGates.computeIfAbsent(rqSeat, ignored -> new LinkedHashMap<>())
                .computeIfAbsent(activationFragment, ignored -> new ArrayList<>())
                .addAll(List.of(requiredStackFragments));
        return this;
    }

    Ws60Pilot attackSequence(String attackerName, List<Integer> defendersInOrder) {
        attackSequences.put(attackerName, List.copyOf(defendersInOrder));
        return this;
    }

    /** Round-robin defenders across occurrences (spreads combat damage). */
    Ws60Pilot attackRoundRobin(String attackerName, List<Integer> seats) {
        List<Integer> cycle = new ArrayList<>();
        for (int round = 0; round < 64; round++) {
            cycle.addAll(seats);
        }
        attackSequences.put(attackerName, List.copyOf(cycle));
        return this;
    }

    Ws60Pilot conserveMana(int rqSeat, String... battlefieldFragments) {
        conserveTriggers.computeIfAbsent(rqSeat, ignored -> new ArrayList<>())
                .addAll(List.of(battlefieldFragments));
        return this;
    }

    Ws60Pilot attacker(String attackerName, int defenderRqSeat) {
        attackers.put(attackerName, defenderRqSeat);
        return this;
    }

    /** Assembly attackers fall back to the lowest live defender (else hold). */
    private final Map<String, Integer> fallbackAttackers = new LinkedHashMap<>();
    /** RQ seats never attacked by fallback (life-asserted). */
    private final List<Integer> fallbackExcluded = new ArrayList<>();

    Ws60Pilot attackerFallback(String attackerName, int defenderRqSeat) {
        fallbackAttackers.put(attackerName, defenderRqSeat);
        return this;
    }

    Ws60Pilot fallbackExcludeSeats(Integer... seats) {
        fallbackExcluded.addAll(List.of(seats));
        return this;
    }

    Ws60Pilot blocker(String blockerName, String... attackerNames) {
        blockers.put(blockerName, List.of(attackerNames));
        return this;
    }

    Ws60Pilot target(String descriptionFragment, String nameMatch) {
        targetRules.add(new TargetRule(descriptionFragment, nameMatch, null));
        return this;
    }

    Ws60Pilot targetPlayer(String descriptionFragment, int rqSeat) {
        targetRules.add(new TargetRule(descriptionFragment, "WS52 Seat " + (rqSeat + 1), null));
        return this;
    }

    Ws60Pilot modes(String... keywordsInOrder) {
        modeKeywords.addAll(List.of(keywordsInOrder));
        return this;
    }

    Ws60Pilot replacement(String... sourceNamesInPreferenceOrder) {
        replacementPreference.addAll(List.of(sourceNamesInPreferenceOrder));
        return this;
    }

    Ws60Pilot bool(String messageFragment, boolean yes) {
        booleans.put(messageFragment, yes);
        return this;
    }

    Ws60Pilot numeric(String sourceFragment, int value) {
        numerics.put(sourceFragment, value);
        return this;
    }

    Ws60Pilot multiAmount(String messageFragment, int amount) {
        multiAmounts.put(messageFragment, amount);
        return this;
    }

    Ws60Pilot search(String descriptionFragment, String cardName) {
        searchPicks.put(descriptionFragment, cardName);
        return this;
    }

    Ws60Pilot handPick(String descriptionFragment, String cardName) {
        handPicks.put(descriptionFragment, cardName);
        return this;
    }

    Ws60Pilot choice(String promptFragment, String labelFragment) {
        choicePicks.put(promptFragment, labelFragment);
        return this;
    }

    Ws60Pilot seek(int rqSeat, int maxTries, String... names) {
        seekRules.put(rqSeat, new SeekRule(List.of(names), maxTries));
        return this;
    }

    Ws60Pilot lands(String... namesInOrder) {
        landPreference.addAll(List.of(namesInOrder));
        return this;
    }

    Ws60Pilot seatLands(int rqSeat, String... names) {
        seatLands.computeIfAbsent(rqSeat, ignored -> new ArrayList<>()).addAll(List.of(names));
        return this;
    }

    Ws60Pilot landOrder(int rqSeat, String... namesInOrder) {
        seatLandOrder.put(rqSeat, List.of(namesInOrder));
        return this;
    }

    Ws60Pilot critical(String mark) {
        criticalMarks.add(mark);
        return this;
    }

    // ------------------------------------------------------------------
    // Frame access helpers
    // ------------------------------------------------------------------

    static String frameClass(JsonObject frame) {
        return frame.get("decision_class").getAsString();
    }

    static int actorSeat(JsonObject frame) {
        return frame.get("seat").getAsInt();
    }

    static String prompt(JsonObject frame) {
        return frame.has("prompt") && !frame.get("prompt").isJsonNull()
                ? frame.get("prompt").getAsString() : "";
    }

    static JsonArray options(JsonObject frame) {
        return frame.getAsJsonArray("legal_options");
    }

    static String label(JsonObject option) {
        return option.has("label") && !option.get("label").isJsonNull()
                ? option.get("label").getAsString() : "";
    }

    static String optionType(JsonObject option) {
        return option.has("option_type") && !option.get("option_type").isJsonNull()
                ? option.get("option_type").getAsString() : "";
    }

    static String optionId(JsonObject option) {
        return option.get("option_id").getAsString();
    }

    static JsonObject metadata(JsonObject option) {
        return option.has("metadata") && option.get("metadata").isJsonObject()
                ? option.getAsJsonObject("metadata") : new JsonObject();
    }

    static String meta(JsonObject option, String key) {
        JsonObject meta = metadata(option);
        return meta.has(key) && !meta.get(key).isJsonNull() ? meta.get(key).getAsString() : "";
    }

    static String contextString(JsonObject frame, String key) {
        JsonObject context = frame.has("context") && frame.get("context").isJsonObject()
                ? frame.getAsJsonObject("context") : new JsonObject();
        return context.has(key) && !context.get(key).isJsonNull()
                ? context.get(key).getAsString() : "";
    }

    static String sourceName(JsonObject frame) {
        if (!frame.has("source_object") || !frame.get("source_object").isJsonObject()) {
            return "";
        }
        JsonObject source = frame.getAsJsonObject("source_object");
        return source.has("source_name") && !source.get("source_name").isJsonNull()
                ? source.get("source_name").getAsString() : "";
    }

    static JsonObject pilotState(JsonObject frame) {
        return frame.has("pilot_state") && frame.get("pilot_state").isJsonObject()
                ? frame.getAsJsonObject("pilot_state") : new JsonObject();
    }

    boolean isCritical(JsonObject frame) {
        String haystack = frameClass(frame) + " | " + prompt(frame) + " | " + sourceName(frame);
        for (String mark : criticalMarks) {
            if (haystack.contains(mark)) {
                return true;
            }
        }
        return false;
    }

    // ------------------------------------------------------------------
    // Decisions
    // ------------------------------------------------------------------

    record PilotAction(List<String> optionIds, Integer numeric) {
    }

    PilotAction decide(JsonObject frame) {
        String clazz = frameClass(frame);
        return switch (clazz) {
            case "mulligan" -> decideMulligan(frame);
            case "priority" -> decidePriority(frame);
            case "target", "choose_object" -> decideTarget(frame);
            case "target_amount" -> decideTargetAmount(frame);
            case "mana_payment" -> decideMana(frame);
            case "choose_use" -> decideBoolean(frame);
            case "choice" -> decideChoice(frame);
            case "announce_x", "amount" -> decideNumeric(frame, false);
            case "multi_amount" -> decideNumeric(frame, true);
            case "mode" -> decideMode(frame);
            case "replacement_effect" -> decideReplacement(frame);
            case "trigger_order" -> decideTrigger(frame);
            case "declare_attacker" -> decideAttacker(frame);
            case "declare_blocker" -> decideBlocker(frame);
            case "pile" -> gap("pile decision unmapped: " + prompt(frame));
            default -> gap("unknown decision class: " + clazz + " prompt=" + prompt(frame));
        };
    }

    private PilotAction decideMulligan(JsonObject frame) {
        int seat = actorSeat(frame);
        SeekRule seek = seekRules.get(seat);
        int tries = mulliganTries.getOrDefault(seat, 0);
        if (seek == null) {
            return single(frame, "keep");
        }
        if (tries >= seek.maxTries()) {
            return single(frame, "keep");
        }
        JsonObject view = pilotState(frame);
        List<String> hand = Ws60Views.handNames(view, seat);
        for (String name : seek.names()) {
            if (hand.stream().anyMatch(card -> card.contains(name))) {
                return single(frame, "keep");
            }
        }
        mulliganTries.put(seat, tries + 1);
        return single(frame, "mulligan");
    }

    private final Map<Integer, Integer> mulliganTries = new LinkedHashMap<>();

    private PilotAction decidePriority(JsonObject frame) {
        int seat = actorSeat(frame);
        JsonObject view = pilotState(frame);
        trackSeen(seat, view);
        List<JsonObject> offered = asList(options(frame));
        boolean conserve = conserving(seat, view) || holdingForAnswer(seat, view);
        // 1. Scenario setup casts/activations in configured order (gated).
        // Reactive answers (casts with stack gates, e.g. counterspells) are
        // exempt from conservation: they must fire when their trigger is
        // present, which is exactly when conservation matters.
        for (String card : setupCasts.getOrDefault(seat, List.of())) {
            boolean reactive = !stackGates.getOrDefault(seat, Map.of())
                    .getOrDefault(card, List.of()).isEmpty();
            if (conserve && !reactive) {
                continue;
            }
            // Reactive gates still apply (trigger must be present).
            if (!castGateOpen(seat, card, view)) {
                continue;
            }
            String match = castOptionFor(offered, card, seat);
            if (match != null) {
                return ids(match);
            }
        }
        for (String fragment : setupActivates.getOrDefault(seat, List.of())) {
            if (!activateGateOpen(seat, fragment, view)) {
                continue;
            }
            if (activateOnceFragments.contains(fragment)
                    && activateOnceUsed.contains(fragment)) {
                continue;
            }
            String match = activateOptionFor(offered, fragment, seat);
            if (match != null) {
                activateOnceUsed.add(fragment);
                return ids(match);
            }
        }
        // 2. Commander cast when explicitly allowed.
        if (!conserve && commanderCastAllowed.getOrDefault(seat, false)) {
            for (String commander : commanderNames.getOrDefault(seat, List.of())) {
                String match = castOptionFor(offered, commander, seat);
                if (match != null) {
                    return ids(match);
                }
            }
        }
        // 3. Assembly filtering (Thrasios-style draw/ramp) while enabled.
        // Secured seats (all sought pieces in hand/battlefield/graveyard)
        // stop drawing to avoid milling away the late game.
        if (!conserve && !secured(seat, view)
                && assemblyFiltering.getOrDefault(seat, false)
                && filterBudgetLeft(seat, view)
                && filterUntappedOk(seat, view)) {
            String match = activateOptionFor(offered, "scry 1", seat);
            if (match != null) {
                spendFilterBudget(seat, view);
                return ids(match);
            }
            match = activateOptionFor(offered, "reveal the top card", seat);
            if (match != null) {
                spendFilterBudget(seat, view);
                return ids(match);
            }
        }
        // 4. Land drop in preference order, else any land play.
        String land = landOption(offered, seat);
        if (land != null) {
            return ids(land);
        }
        // 5. Default: pass (always legal).
        return single(frame, "pass_priority");
    }

    /** Priority cast option for a card name, excluding commander casts unless allowed. */
    private String castOptionFor(List<JsonObject> offered, String cardName, int seat) {
        // (gates are checked by the caller via castGateOpen)
        return castOptionForUngated(offered, cardName, seat);
    }    private boolean castGateOpen(int seat, String card, JsonObject view) {
        List<String> battlefield = viewBattlefieldNames(view);
        for (String required : castGates.getOrDefault(seat, Map.of())
                .getOrDefault(card, List.of())) {
            if (battlefield.stream().noneMatch(name -> name.contains(required))) {
                return false;
            }
        }
        List<String> stack = viewStackNames(view);
        for (String required : stackGates.getOrDefault(seat, Map.of())
                .getOrDefault(card, List.of())) {
            if (stack.stream().noneMatch(name -> name.contains(required))) {
                return false;
            }
        }
        Integer wait = delayGates.getOrDefault(seat, Map.of()).get(card);
        if (wait != null) {
            String trigger = delayTriggers.getOrDefault(seat, Map.of())
                    .getOrDefault(card, card);
            Integer seen = firstSeenTurn.getOrDefault(seat, Map.of()).get(card);
            if (seen == null) {
                if (battlefield.stream().anyMatch(name -> name.contains(trigger))) {
                    // First observation happens now; the wait starts next turn.
                    return false;
                }
                return false;
            }
            if (viewTurn(view) - seen < wait) {
                return false;
            }
        }
        Integer minTurn = turnGates.getOrDefault(seat, Map.of()).get(card);
        if (minTurn != null && viewTurn(view) < minTurn) {
            return false;
        }
        Map.Entry<String, Integer> countGate = countGates.getOrDefault(seat, Map.of()).get(card);
        if (countGate != null) {
            long found = battlefield.stream()
                    .filter(name -> name.contains(countGate.getKey())).count();
            if (found < countGate.getValue()) {
                return false;
            }
        }
        Map.Entry<String, Integer> ownGate = ownCountGates.getOrDefault(seat, Map.of()).get(card);
        if (ownGate != null) {
            long found = viewOwnBattlefieldNames(view, seat).stream()
                    .filter(name -> name.contains(ownGate.getKey())).count();
            if (found < ownGate.getValue()) {
                return false;
            }
        }
        return true;
    }

    private boolean activateGateOpen(int seat, String fragment, JsonObject view) {
        List<String> required = activateGates.getOrDefault(seat, Map.of())
                .getOrDefault(fragment, List.of());
        if (required.isEmpty()) {
            return true;
        }
        List<String> stack = viewStackNames(view);
        return required.stream().allMatch(
                need -> stack.stream().anyMatch(name -> name.contains(need)));
    }

    private boolean conserving(int seat, JsonObject view) {        List<String> triggers = conserveTriggers.getOrDefault(seat, List.of());
        if (triggers.isEmpty()) {
            return false;
        }
        List<String> battlefield = viewBattlefieldNames(view);
        return triggers.stream().anyMatch(
                fragment -> battlefield.stream().anyMatch(name -> name.contains(fragment)));
    }

    private void trackSeen(int seat, JsonObject view) {
        Map<String, Integer> gates = delayGates.getOrDefault(seat, Map.of());
        if (gates.isEmpty()) {
            return;
        }
        int turn = viewTurn(view);
        List<String> battlefield = viewBattlefieldNames(view);
        Map<String, Integer> seen = firstSeenTurn.computeIfAbsent(seat, ignored -> new LinkedHashMap<>());
        Map<String, String> triggers = delayTriggers.getOrDefault(seat, Map.of());
        for (String card : gates.keySet()) {
            String trigger = triggers.getOrDefault(card, card);
            if (!seen.containsKey(card)
                    && battlefield.stream().anyMatch(name -> name.contains(trigger))) {
                seen.put(card, turn);
            }
        }
    }

    static List<String> viewBattlefieldNames(JsonObject view) {
        List<String> out = new ArrayList<>();
        if (!view.has("players") || !view.get("players").isJsonArray()) {
            return out;
        }
        for (JsonElement player : view.getAsJsonArray("players")) {
            JsonObject row = player.getAsJsonObject();
            if (!row.has("battlefield") || !row.get("battlefield").isJsonArray()) {
                continue;
            }
            for (JsonElement permanent : row.getAsJsonArray("battlefield")) {
                out.add(permanent.getAsJsonObject().get("name").getAsString());
            }
        }
        return out;
    }

    static List<String> viewOwnBattlefieldNames(JsonObject view, int seat) {
        List<String> out = new ArrayList<>();
        if (!view.has("players") || !view.get("players").isJsonArray()) {
            return out;
        }
        for (JsonElement player : view.getAsJsonArray("players")) {
            JsonObject row = player.getAsJsonObject();
            if (row.get("seat").getAsInt() != seat || !row.has("battlefield")
                    || !row.get("battlefield").isJsonArray()) {
                continue;
            }
            for (JsonElement permanent : row.getAsJsonArray("battlefield")) {
                out.add(permanent.getAsJsonObject().get("name").getAsString());
            }
        }
        return out;
    }

    static List<String> viewStackNames(JsonObject view) {
        List<String> out = new ArrayList<>();
        if (!view.has("stack") || !view.get("stack").isJsonArray()) {
            return out;
        }
        for (JsonElement element : view.getAsJsonArray("stack")) {
            out.add(element.getAsJsonObject().get("name").getAsString());
        }
        return out;
    }

    static int viewTurn(JsonObject view) {
        try {
            return view.has("turn_number") ? view.get("turn_number").getAsInt() : 0;
        } catch (RuntimeException ignored) {
            return 0;
        }
    }

    private String castOptionForUngated(List<JsonObject> offered, String cardName, int seat) {
        for (JsonObject option : offered) {
            String type = optionType(option);
            if (!type.equals("activated_ability") && !type.equals("cast_ability")) {
                continue;
            }
            // Casts render as "<Card> — Cast <Card>...". Activated abilities
            // of the same source (e.g. Thrasios's filter) must not match here;
            // they are handled by the activation/filter steps.
            if (!label(option).contains("Cast ")) {
                continue;
            }
            String source = meta(option, "source_name");
            if (source.isBlank()) {
                source = label(option);
            }
            if (!source.contains(cardName)) {
                continue;
            }
            if (isCommander(source, seat) && !commanderCastAllowed.getOrDefault(seat, false)) {
                continue;
            }
            return optionId(option);
        }
        return null;
    }

    private boolean isCommander(String sourceName, int seat) {
        for (String commander : commanderNames.getOrDefault(seat, List.of())) {
            if (sourceName.contains(commander)) {
                return true;
            }
        }
        return false;
    }

    private String activateOptionFor(List<JsonObject> offered, String fragment, int seat) {
        for (JsonObject option : offered) {
            String type = optionType(option);
            if (!type.equals("activated_ability") && !type.equals("mana_ability")) {
                continue;
            }
            if (isCommander(label(option), seat) && !commanderCastAllowed.getOrDefault(seat, false)
                    && !assemblyFiltering.getOrDefault(seat, false)) {
                continue;
            }
            if (label(option).contains(fragment) || meta(option, "source_name").contains(fragment)) {
                return optionId(option);
            }
        }
        return null;
    }

    private String landOption(List<JsonObject> offered, int seat) {
        List<String> preference = seatLandOrder.getOrDefault(seat, landPreference);
        List<String> known = new ArrayList<>(preference);
        known.addAll(seatLands.getOrDefault(seat, List.of()));
        List<JsonObject> landOptions = new ArrayList<>();
        for (JsonObject option : offered) {
            String type = optionType(option);
            if (type.equals("play_land_ability")) {
                landOptions.add(option);
                continue;
            }
            if (!type.equals("activated_ability") && !type.equals("cast_ability")) {
                continue;
            }
            String source = meta(option, "source_name");
            if (!source.isBlank() && known.stream().anyMatch(source::contains)) {
                landOptions.add(option);
            }
        }
        if (landOptions.isEmpty()) {
            return null;
        }
        for (String preferred : preference) {
            for (JsonObject option : landOptions) {
                if (label(option).contains(preferred) || meta(option, "source_name").contains(preferred)) {
                    return optionId(option);
                }
            }
        }
        landOptions.sort((left, right) -> label(left).compareTo(label(right)));
        return optionId(landOptions.get(0));
    }

    private PilotAction decideTarget(JsonObject frame) {
        String description = contextString(frame, "target_description");
        String message = prompt(frame);
        // Scry/surveil splits first (their messages also mention bottoming,
        // but they are optional top/bottom splits, not London mulligans).
        if (containsIgnoreCase(message, "scry") || containsIgnoreCase(description, "scry")) {
            return scryPick(frame);
        }
        // Bottom-of-library (London) and similar hand-picks: keep seek pieces, bottom the rest.
        if (containsIgnoreCase(message, "bottom of your library")
                || containsIgnoreCase(message, "bottom of their library")) {
            return bottomPick(frame);
        }
        // Cleanup discard to hand size: discard a basic land first, else any
        // non-precious card. Copies are fungible; the engine enforces the count.
        if (description.contains("to discard") || message.toLowerCase().contains("to discard")) {
            return discardPick(frame);
        }
        boolean handFrame = description.toLowerCase().contains("hand")
                || message.toLowerCase().contains("hand");
        // Hand selections (pitch costs and similar hidden-zone decisions).
        if (handFrame) {
            for (Map.Entry<String, String> entry : handPicks.entrySet()) {
                if (!entry.getKey().isEmpty() && !description.contains(entry.getKey())
                        && !message.contains(entry.getKey())) {
                    continue;
                }
                String match = optionByName(frame, entry.getValue());
                if (match != null) {
                    return ids(match);
                }
                return gap("hand pick '" + entry.getValue() + "' not offered: " + message
                        + " options=" + summarizeOptions(frame));
            }
        }
        // Library searches consult only the search mapping (never generic target rules).
        if (!handFrame) {
            for (Map.Entry<String, String> entry : searchPicks.entrySet()) {
                if (!entry.getKey().isEmpty() && !description.contains(entry.getKey())
                        && !message.contains(entry.getKey())) {
                    continue;
                }
                String match = optionByName(frame, entry.getValue());
                if (match != null) {
                    return ids(match);
                }
                return gap("search pick '" + entry.getValue() + "' not offered: " + message
                        + " options=" + summarizeOptions(frame));
            }
        }
        // Battlefield / stack / player targets: sequential scripts first (one
        // pick per frame, stop with an empty selection once complete), then
        // collect picks across ALL matching rules for single-frame multi
        // targets. Single-target frames match exactly one rule.
        for (Map.Entry<String, List<String>> sequence : sequentialTargets.entrySet()) {
            if (!sequence.getKey().isEmpty() && !description.contains(sequence.getKey())
                    && !message.contains(sequence.getKey())) {
                continue;
            }
            for (String want : sequence.getValue()) {
                if (sequentialPicked.contains(want)) {
                    continue;
                }
                String match = optionByName(frame, want);
                if (match != null) {
                    sequentialPicked.add(want);
                    return ids(match);
                }
                return gap("sequential target '" + want + "' not offered: "
                        + summarizeOptions(frame));
            }
            // All scripted targets picked: stop if allowed.
            if (minimum(frame) == 0) {
                return ids();
            }
            return gap("sequential targets cannot stop (min=" + minimum(frame) + ") picked="
                    + sequentialPicked + " offered=" + summarizeOptions(frame));
        }
        List<String> picks = new ArrayList<>();
        for (TargetRule rule : targetRules) {
            if (!rule.descriptionFragment().isEmpty()
                    && !description.contains(rule.descriptionFragment())
                    && !message.contains(rule.descriptionFragment())) {
                continue;
            }
            String match = optionByName(frame, rule.nameMatch());
            if (match == null) {
                return gap("target '" + rule.nameMatch() + "' not offered for '"
                        + rule.descriptionFragment() + "': " + summarizeOptions(frame));
            }
            if (!picks.contains(match)) {
                picks.add(match);
            }
        }
        if (!picks.isEmpty()) {
            return ids(picks.toArray(new String[0]));
        }
        // Label-scoped generic picks (scry top/bottom, graft, ETB zero-select).
        String generic = genericTargetPick(frame);
        if (generic != null) {
            return ids(generic);
        }
        return gap("unmapped target decision: desc='" + description + "' prompt='" + message
                + "' options=" + summarizeOptions(frame));
    }

    private boolean isLibrarySearch(JsonObject frame) {
        String message = prompt(frame).toLowerCase();
        return message.contains("search") || message.contains("library");
    }

    private static final List<String> BASIC_LANDS =
            List.of("Forest", "Island", "Swamp", "Mountain", "Plains", "Wastes");

    private PilotAction discardPick(JsonObject frame) {
        int seat = actorSeat(frame);
        List<String> precious = new ArrayList<>();
        SeekRule seek = seekRules.get(seat);
        if (seek != null) {
            precious.addAll(seek.names());
        }
        precious.addAll(setupCasts.getOrDefault(seat, List.of()));
        precious.addAll(commanderNames.getOrDefault(seat, List.of()));
        precious.addAll(searchPicks.values());
        int need = Math.max(minimum(frame), 1);
        List<JsonObject> offered = asList(options(frame));
        List<JsonObject> basics = new ArrayList<>();
        for (JsonObject option : offered) {
            String name = label(option);
            if (BASIC_LANDS.stream().anyMatch(name::contains)) {
                basics.add(option);
            }
        }
        List<JsonObject> spare = new ArrayList<>();
        for (JsonObject option : offered) {
            String name = label(option);
            if (precious.stream().noneMatch(name::contains)) {
                spare.add(option);
            }
        }
        java.util.Comparator<JsonObject> byRank = (left, right) -> Integer.compare(
                discardRank(label(left)), discardRank(label(right)));
        java.util.Comparator<JsonObject> byLabel = (left, right) ->
                label(left).compareTo(label(right));
        basics.sort(byRank);
        spare.sort(byLabel);
        List<String> picks = new ArrayList<>();
        for (JsonObject option : basics) {
            if (picks.size() >= need) {
                break;
            }
            picks.add(optionId(option));
        }
        for (JsonObject option : spare) {
            if (picks.size() >= need) {
                break;
            }
            if (!picks.contains(optionId(option))) {
                picks.add(optionId(option));
            }
        }
        if (picks.isEmpty()) {
            List<JsonObject> fallback = new ArrayList<>(offered);
            fallback.sort(byLabel);
            picks.add(optionId(fallback.get(0)));
        }
        return ids(picks.toArray(new String[0]));
    }

    private PilotAction bottomPick(JsonObject frame) {
        int seat = actorSeat(frame);
        SeekRule seek = seekRules.get(seat);
        List<String> keep = seek == null ? List.of() : seek.names();
        List<String> setup = setupCasts.getOrDefault(seat, List.of());
        int need = Math.max(minimum(frame), 1);
        List<JsonObject> candidates = new ArrayList<>();
        List<JsonObject> fallback = new ArrayList<>();
        for (JsonObject option : asList(options(frame))) {
            String name = label(option);
            boolean precious = keep.stream().anyMatch(name::contains)
                    || setup.stream().anyMatch(name::contains)
                    || commanderNames.getOrDefault(seat, List.of()).stream().anyMatch(name::contains);
            (precious ? fallback : candidates).add(option);
        }
        // Deterministic across twin runs: fixed name order, then first label.
        java.util.Comparator<JsonObject> byRank = (left, right) -> {
            int rank = Integer.compare(
                    discardRank(label(left)), discardRank(label(right)));
            return rank != 0 ? rank : label(left).compareTo(label(right));
        };
        candidates.sort(byRank);
        fallback.sort(byRank);
        List<String> picks = new ArrayList<>();
        for (JsonObject option : candidates) {
            if (picks.size() >= need) {
                break;
            }
            picks.add(optionId(option));
        }
        // Mandatory bottoms (London, min>0) fill from precious options if
        // forced; optional splits (min 0) may return fewer (possibly empty).
        if (minimum(frame) > 0) {
            for (JsonObject option : fallback) {
                if (picks.size() >= need) {
                    break;
                }
                if (!picks.contains(optionId(option))) {
                    picks.add(optionId(option));
                }
            }
        }
        if (picks.isEmpty() && minimum(frame) > 0) {
            return gap("bottom pick without options");
        }
        return ids(picks.toArray(new String[0]));
    }

    /**
     * Fixed discard/bottom priority (twin-stable): abundant basics first in a
     * fixed color rotation, scarce fixing lands last. Names decide; copies are
     * fungible so which copy is irrelevant to game evolution.
     */
    private static int discardRank(String name) {
        List<String> order = List.of("Plains", "Island", "Swamp", "Mountain", "Forest",
                "Wastes", "Command Tower", "Exotic Orchard", "Reflecting Pool",
                "Gemstone Mine", "Tendo Ice Bridge", "Sol Ring");
        for (int index = 0; index < order.size(); index++) {
            if (name.contains(order.get(index))) {
                return index;
            }
        }
        return order.size();
    }

    private static boolean containsIgnoreCase(String haystack, String needle) {
        return haystack != null && haystack.toLowerCase().contains(needle.toLowerCase());
    }

    private PilotAction scryPick(JsonObject frame) {
        int seat = actorSeat(frame);
        Integer threshold = scryGas.get(seat);
        if (threshold == null) {
            return ids();
        }
        JsonObject view = pilotState(frame);
        long handLands = Ws60Views.handNames(view, seat).stream()
                .filter(name -> BASIC_LANDS.stream().anyMatch(name::contains)
                        || seatLands.getOrDefault(seat, List.of()).stream()
                                .anyMatch(name::contains))
                .count();
        if (handLands < threshold) {
            return ids();
        }
        // Bottom basic lands to dig for spells; keep everything else on top.
        List<String> bottom = new ArrayList<>();
        for (JsonObject option : asList(options(frame))) {
            String name = label(option);
            if (BASIC_LANDS.stream().anyMatch(name::contains)) {
                bottom.add(optionId(option));
            }
        }
        return ids(bottom.toArray(new String[0]));
    }

    private String genericTargetPick(JsonObject frame) {
        String message = prompt(frame);
        // Scry: always keep on top (productive: lands ramp via Thrasios, non-lands draw).
        if (message.toLowerCase().contains("scry")) {
            String match = optionByFragment(frame, "top");
            if (match != null) {
                return match;
            }
        }
        return null;
    }

    private PilotAction decideTargetAmount(JsonObject frame) {
        return gap("target_amount unmapped: " + prompt(frame));
    }

    private PilotAction decideMana(JsonObject frame) {
        int seat = actorSeat(frame);
        String unpaid = contextString(frame, "unpaid_mana");
        if (!unpaid.isBlank()) {
            lastUnpaid.put(seat, unpaid);
        }
        String repeatKey = seat + "|" + unpaid;
        int repeats = manaRepeats.getOrDefault(repeatKey, 0) + 1;
        manaRepeats.put(repeatKey, repeats);
        // Forget other bills for this seat (a new bill resets the stall count).
        manaRepeats.keySet().removeIf(key -> key.startsWith(seat + "|") && !key.equals(repeatKey));

        // Progress discipline: the prompt's existence proves a remainder is
        // owed. Spending a bill-needed color, or any mana toward a generic
        // remainder, is monotone progress (the engine tracks the true
        // remainder and stops prompting when paid). Tapping the last source
        // of a still-needed color for generic is avoided by preferring
        // non-bill-colored taps for generic remainders.
        List<String> needs = billColors(unpaid);
        boolean generic = hasGeneric(unpaid);
        List<JsonObject> offered = asList(options(frame));
        List<JsonObject> poolOptions = new ArrayList<>();
        List<JsonObject> abilities = new ArrayList<>();
        boolean cancelOffered = false;
        for (JsonObject option : offered) {
            String type = optionType(option);
            if (type.equals("mana_pool")) {
                poolOptions.add(option);
            } else if (type.equals("mana_ability")) {
                abilities.add(option);
            } else if (type.equals("cancel_mana_payment")) {
                cancelOffered = true;
            }
        }
        poolOptions.sort((left, right) -> label(left).compareTo(label(right)));
        abilities.sort((left, right) -> label(left).compareTo(label(right)));

        // A. Colored needs: matching pool first, then producing taps.
        for (String color : needs) {
            for (JsonObject option : poolOptions) {
                if (color.equals(poolColor(meta(option, "mana_type")))) {
                    return ids(optionId(option));
                }
            }
        }
        for (String color : needs) {
            String symbol = COLOR_SYMBOLS.get(color);
            for (JsonObject ability : abilities) {
                if (label(ability).contains("{" + symbol + "}")) {
                    return ids(optionId(ability));
                }
            }
            for (JsonObject ability : abilities) {
                String abilityLabel = label(ability);
                if (abilityLabel.contains("any color") || abilityLabel.contains("any type")) {
                    return ids(optionId(ability));
                }
            }
        }
        // B. Generic remainder: spare pool first, then taps that do not
        // consume bill-needed colors (nor reserved answer mana), then any tap.
        if (generic) {
            if (!poolOptions.isEmpty()) {
                return ids(optionId(poolOptions.get(0)));
            }
            List<String> reserved = reserveTaps.getOrDefault(seat, List.of());
            for (JsonObject ability : abilities) {
                if (!producesBillColor(label(ability), needs)
                        && reserved.stream().noneMatch(label(ability)::contains)) {
                    return ids(optionId(ability));
                }
            }
            for (JsonObject ability : abilities) {
                if (!producesBillColor(label(ability), needs)) {
                    return ids(optionId(ability));
                }
            }
            if (!abilities.isEmpty()) {
                return ids(optionId(abilities.get(0)));
            }
        }
        // C. Nothing usable: cancel a genuinely unpayable bill now; cancel a
        // merely stalled one after repeats (the cast can be retried later).
        if (cancelOffered && (poolOptions.isEmpty() && abilities.isEmpty() || repeats >= 6)) {
            for (JsonObject option : offered) {
                if (optionType(option).equals("cancel_mana_payment")) {
                    return ids(optionId(option));
                }
            }
        }
        return gap("mana payment without progressing route (repeats=" + repeats + "): "
                + prompt(frame) + " unpaid=" + unpaid);
    }

    private final Map<String, Integer> manaRepeats = new LinkedHashMap<>();

    private static String poolColor(String manaType) {
        if (manaType == null) {
            return null;
        }
        String upper = manaType.toUpperCase();
        if (upper.contains("WHITE") || upper.equals("{W}")) {
            return "White";
        }
        if (upper.contains("BLUE") || upper.equals("{U}")) {
            return "Blue";
        }
        if (upper.contains("BLACK") || upper.equals("{B}")) {
            return "Black";
        }
        if (upper.contains("RED") || upper.equals("{R}")) {
            return "Red";
        }
        if (upper.contains("GREEN") || upper.equals("{G}")) {
            return "Green";
        }
        if (upper.contains("COLORLESS") || upper.equals("{C}")) {
            return "Colorless";
        }
        return null;
    }

    private static boolean producesBillColor(String label, List<String> needs) {
        for (String color : needs) {
            if (label.contains("{" + COLOR_SYMBOLS.get(color) + "}")) {
                return true;
            }
        }
        return false;
    }

    private static boolean hasGeneric(String bill) {
        if (bill == null) {
            return false;
        }
        java.util.regex.Matcher matcher =
                java.util.regex.Pattern.compile("\\{(\\d+)\\}").matcher(bill);
        int generic = 0;
        while (matcher.find()) {
            try {
                generic += Integer.parseInt(matcher.group(1));
            } catch (NumberFormatException ignored) {
                // Non-numeric braces (e.g. {T}, {W}) are not generic mana.
            }
        }
        if (generic <= 0) {
            return false;
        }
        return true;
    }

    private PilotAction decideBoolean(JsonObject frame) {
        String message = prompt(frame);
        int seat = actorSeat(frame);
        // Secured seats decline further card-draw (mill guard); other
        // yes/no prompts use the scenario mapping.
        if (message.contains("pay X life") && secured(seat, pilotState(frame))) {
            return single(frame, "false");
        }
        for (Map.Entry<String, Boolean> entry : booleans.entrySet()) {
            if (message.contains(entry.getKey())) {
                return single(frame, entry.getValue() ? "true" : "false");
            }
        }
        return gap("unmapped yes/no: '" + message + "' source=" + sourceName(frame));
    }

    private static final List<String> MANA_COLORS =
            List.of("White", "Blue", "Black", "Red", "Green", "Colorless");

    private static final Map<String, String> COLOR_SYMBOLS = Map.of(
            "White", "W", "Blue", "U", "Black", "B", "Red", "R", "Green", "G",
            "Colorless", "C");

    private static boolean isColorChoice(JsonObject frame) {
        List<JsonObject> offered = asList(options(frame));
        if (offered.isEmpty()) {
            return false;
        }
        for (JsonObject option : offered) {
            if (!optionType(option).equals("choice")
                    || !MANA_COLORS.contains(label(option))) {
                return false;
            }
        }
        return true;
    }

    /** Last unpaid_mana bill text per seat (for color-choice payment). */
    private final Map<Integer, String> lastUnpaid = new LinkedHashMap<>();

    private PilotAction colorChoice(JsonObject frame) {
        int seat = actorSeat(frame);
        String bill = lastUnpaid.getOrDefault(seat, "");
        // The bill prompt is static; any bill-needed color offered here is
        // monotone progress toward the engine-tracked remainder.
        for (String color : billColors(bill)) {
            String match = optionByFragment(frame, color);
            if (match != null) {
                return ids(match);
            }
        }
        // Generic remainder (or unknown bill): first offered color, deterministic.
        List<JsonObject> offered = asList(options(frame));
        offered.sort((left, right) -> label(left).compareTo(label(right)));
        return ids(optionId(offered.get(0)));
    }

    private static List<String> billColors(String bill) {
        List<String> out = new ArrayList<>();
        for (String color : MANA_COLORS) {
            if (bill.contains("{" + COLOR_SYMBOLS.get(color) + "}")) {
                out.add(color);
            }
        }
        return out;
    }

    private static int colorNeed(String bill, String color) {
        String token = "{" + COLOR_SYMBOLS.get(color) + "}";
        int count = 0;
        int index = 0;
        while ((index = bill.indexOf(token, index)) >= 0) {
            count++;
            index += token.length();
        }
        return count;
    }

    static Map<String, Integer> viewManaPool(JsonObject view, int seat) {
        Map<String, Integer> out = new LinkedHashMap<>();
        if (!view.has("players") || !view.get("players").isJsonArray()) {
            return out;
        }
        for (JsonElement player : view.getAsJsonArray("players")) {
            JsonObject row = player.getAsJsonObject();
            if (row.get("seat").getAsInt() != seat || !row.has("mana_pool")) {
                continue;
            }
            JsonObject pool = row.getAsJsonObject("mana_pool");
            Map<String, String> names = Map.of("white", "White", "blue", "Blue",
                    "black", "Black", "red", "Red", "green", "Green", "colorless", "Colorless");
            for (Map.Entry<String, String> entry : names.entrySet()) {
                if (pool.has(entry.getKey())) {
                    out.put(entry.getValue(), pool.get(entry.getKey()).getAsInt());
                }
            }
        }
        return out;
    }
    private PilotAction decideChoice(JsonObject frame) {
        String message = prompt(frame);
        // Mana-color choices (rainbow-land and similar "any color" abilities):
        // pay the outstanding bill. The bill's remaining colors are the last
        // unpaid_mana minus the actor's current pool (both pilot-visible).
        if (isColorChoice(frame)) {
            return colorChoice(frame);
        }
        // Cast-ability alternatives (e.g., normal vs alternative cost): scenario mapping first.
        for (Map.Entry<String, String> entry : choicePicks.entrySet()) {
            if (message.contains(entry.getKey()) || sourceName(frame).contains(entry.getKey())) {
                String match = optionByFragment(frame, entry.getValue());
                if (match == null) {
                    return gap("choice '" + entry.getValue() + "' not offered: " + message
                            + " options=" + summarizeOptions(frame));
                }
                return ids(match);
            }
        }
        // Land-or-spell duals: default to the configured setup card when present.
        int seat = actorSeat(frame);
        for (String card : setupCasts.getOrDefault(seat, List.of())) {
            String match = optionByFragment(frame, card);
            if (match != null) {
                return ids(match);
            }
        }
        return gap("unmapped choice: '" + message + "' source=" + sourceName(frame)
                + " options=" + summarizeOptions(frame));
    }

    private PilotAction decideNumeric(JsonObject frame, boolean multi) {
        String source = sourceName(frame);
        String message = prompt(frame);
        if (multi) {
            // The adapter issues one multi_amount frame per distribution
            // message with an empty option set and expects a numeric choice.
            for (Map.Entry<String, Integer> entry : multiAmounts.entrySet()) {
                if (message.contains(entry.getKey()) || source.contains(entry.getKey())) {
                    return numeric(entry.getValue());
                }
            }
            return gap("unmapped multi amount: '" + message + "' source=" + source
                    + " bounds=" + contextString(frame, "numeric_min")
                    + ".." + contextString(frame, "numeric_max"));
        }
        for (Map.Entry<String, Integer> entry : numerics.entrySet()) {
            if (source.contains(entry.getKey()) || message.contains(entry.getKey())) {
                return numeric(entry.getValue());
            }
        }
        return gap("unmapped numeric (" + frameClass(frame) + "): '" + message + "' source=" + source);
    }

    private PilotAction decideMode(JsonObject frame) {
        List<String> picked = modePicks.computeIfAbsent(frameKey(frame), ignored -> new ArrayList<>());
        List<JsonObject> offered = asList(options(frame));
        for (String keyword : modeKeywords) {
            if (picked.contains(keyword)) {
                continue;
            }
            for (JsonObject option : offered) {
                if (label(option).toLowerCase().contains(keyword.toLowerCase())) {
                    picked.add(keyword);
                    return ids(optionId(option));
                }
            }
        }
        // All scripted modes picked (or none match): stop if the frame allows it.
        int min = minimum(frame);
        if (min == 0) {
            return ids();
        }
        return gap("mode stop not allowed (min=" + min + ") picked=" + picked
                + " offered=" + summarizeOptions(frame));
    }

    private final Map<String, List<String>> modePicks = new LinkedHashMap<>();

    private static String frameKey(JsonObject frame) {
        return frame.has("decision_id") ? frame.get("decision_id").getAsString() : "mode";
    }

    private PilotAction decideReplacement(JsonObject frame) {
        for (String preferred : replacementPreference) {
            if (replacementPicked.contains(preferred)) {
                continue;
            }
            for (JsonObject option : asList(options(frame))) {
                if (label(option).contains(preferred) || meta(option, "source_name").contains(preferred)) {
                    replacementPicked.add(preferred);
                    return ids(optionId(option));
                }
            }
        }
        return gap("unmapped replacement choice: " + summarizeOptions(frame));
    }

    private PilotAction decideTrigger(JsonObject frame) {
        List<JsonObject> offered = asList(options(frame));
        if (offered.isEmpty()) {
            return gap("trigger ordering with no options");
        }
        // Deterministic: first offered (labels recorded verbatim in evidence).
        return ids(optionId(offered.get(0)));
    }

    private PilotAction decideAttacker(JsonObject frame) {
        String message = prompt(frame);
        for (Map.Entry<String, List<Integer>> sequence : attackSequences.entrySet()) {
            if (!message.contains(sequence.getKey())) {
                continue;
            }
            if (!attackCountOpen(sequence.getKey(), frame)) {
                return single(frame, "hold_attacker");
            }
            int used = attackSequenceUsed.getOrDefault(sequence.getKey(), 0);
            List<Integer> defenders = sequence.getValue();
            if (used >= defenders.size()) {
                // Choreography complete: hold further attacks.
                return single(frame, "hold_attacker");
            }
            int defender = defenders.get(used);
            attackSequenceUsed.put(sequence.getKey(), used + 1);
            String wantSeat = "defender-seat-" + (defender + 1);
            for (JsonObject option : asList(options(frame))) {
                if (optionId(option).equals(wantSeat)
                        || (optionType(option).equals("declare_attacker")
                                && meta(option, "defender_seat").equals(String.valueOf(defender + 1)))) {
                    return ids(optionId(option));
                }
            }
            // Scripted defender gone: fall back to preserve draw triggers.
            return fallbackLiveDefender(frame, sequence.getKey(), wantSeat);
        }
        for (Map.Entry<String, Integer> entry : attackers.entrySet()) {
            if (!message.contains(entry.getKey())) {
                continue;
            }
            if (!attackCountOpen(entry.getKey(), frame)) {
                return single(frame, "hold_attacker");
            }
            String wantSeat = "defender-seat-" + (entry.getValue() + 1);
            for (JsonObject option : asList(options(frame))) {
                if (optionId(option).equals(wantSeat)
                        || (optionType(option).equals("declare_attacker")
                                && meta(option, "defender_seat").equals(String.valueOf(entry.getValue() + 1)))) {
                    return ids(optionId(option));
                }
            }
            return gap("defender seat option missing for " + entry.getKey()
                    + " want=" + wantSeat + " options=" + summarizeOptions(frame));
        }
        for (Map.Entry<String, Integer> entry : fallbackAttackers.entrySet()) {
            if (!message.contains(entry.getKey())) {
                continue;
            }
            if (!attackCountOpen(entry.getKey(), frame)) {
                return single(frame, "hold_attacker");
            }
            String wantSeat = "defender-seat-" + (entry.getValue() + 1);
            for (JsonObject option : asList(options(frame))) {
                if (optionId(option).equals(wantSeat)
                        || (optionType(option).equals("declare_attacker")
                                && meta(option, "defender_seat").equals(String.valueOf(entry.getValue() + 1)))) {
                    return ids(optionId(option));
                }
            }
            // Scripted defender gone (left the game): attack the lowest live
            // defender to preserve draw triggers, else hold. Deterministic.
            return fallbackLiveDefender(frame, entry.getKey(), wantSeat);
        }
        return single(frame, "hold_attacker");
    }

    private PilotAction fallbackLiveDefender(JsonObject frame, String attacker, String wantSeat) {
        List<String> live = new ArrayList<>();
        for (JsonObject option : asList(options(frame))) {
            if (optionType(option).equals("declare_attacker")
                    && !meta(option, "defender_seat").isBlank()) {
                int seat;
                try {
                    seat = Integer.parseInt(meta(option, "defender_seat")) - 1;
                } catch (NumberFormatException ignored) {
                    continue;
                }
                if (fallbackExcluded.contains(seat)) {
                    continue;
                }
                live.add(optionId(option) + "|" + meta(option, "defender_seat"));
            }
        }
        live.sort(String::compareTo);
        if (!live.isEmpty()) {
            return ids(live.get(0).split("\\|")[0]);
        }
        return single(frame, "hold_attacker");
    }

    private PilotAction decideBlocker(JsonObject frame) {
        String message = prompt(frame);
        String blocker = blockerForPrompt(message);
        List<String> wanted = blocker == null ? null : blockers.get(blocker);
        if (wanted == null) {
            return ids();
        }
        List<String> picked = new ArrayList<>();
        for (JsonObject option : asList(options(frame))) {
            if (!optionType(option).equals("declare_blocker")) {
                continue;
            }
            for (String attacker : wanted) {
                if (label(option).contains(attacker)) {
                    picked.add(optionId(option));
                }
            }
        }
        if (picked.size() != wanted.size()) {
            return gap("blocker " + blocker + " wanted " + wanted + " picked " + picked.size()
                    + " options=" + summarizeOptions(frame));
        }
        return ids(picked.toArray(new String[0]));
    }

    private String blockerForPrompt(String message) {
        for (String blocker : blockers.keySet()) {
            if (message.contains(blocker)) {
                return blocker;
            }
        }
        return null;
    }

    // ------------------------------------------------------------------
    // Small builders
    // ------------------------------------------------------------------

    private static PilotAction ids(String... ids) {
        return new PilotAction(List.of(ids), null);
    }

    private static PilotAction numeric(int value) {
        return new PilotAction(List.of(), value);
    }

    private PilotAction single(JsonObject frame, String typeOrValue) {
        for (JsonObject option : asList(options(frame))) {
            if (optionType(option).equals(typeOrValue)) {
                return ids(optionId(option));
            }
            if (optionType(option).equals("boolean") && meta(option, "value").equals(typeOrValue)) {
                return ids(optionId(option));
            }
            if ((typeOrValue.equals("keep") || typeOrValue.equals("mulligan"))
                    && optionType(option).equals(typeOrValue)) {
                return ids(optionId(option));
            }
            if (typeOrValue.equals("hold_attacker") && optionId(option).equals("hold_attacker")) {
                return ids(optionId(option));
            }
        }
        return gap("no option of kind '" + typeOrValue + "' in " + frameClass(frame)
                + ": " + summarizeOptions(frame));
    }

    private String optionByName(JsonObject frame, String name) {
        for (JsonObject option : asList(options(frame))) {
            if (label(option).equals(name) || label(option).contains(name)
                    || meta(option, "name").equals(name) || meta(option, "name").contains(name)) {
                return optionId(option);
            }
        }
        return null;
    }

    private String optionByFragment(JsonObject frame, String fragment) {
        String lowered = fragment.toLowerCase();
        for (JsonObject option : asList(options(frame))) {
            if (label(option).toLowerCase().contains(lowered)) {
                return optionId(option);
            }
        }
        return null;
    }

    private static int minimum(JsonObject frame) {
        return frame.has("minimum_selections") ? frame.get("minimum_selections").getAsInt() : 1;
    }

    private static List<JsonObject> asList(JsonArray array) {
        List<JsonObject> out = new ArrayList<>(array.size());
        for (JsonElement element : array) {
            out.add(element.getAsJsonObject());
        }
        return out;
    }

    static String summarizeOptions(JsonObject frame) {
        StringBuilder out = new StringBuilder("[");
        for (JsonObject option : asList(options(frame))) {
            out.append("{").append(optionType(option)).append(":").append(label(option)).append("}");
        }
        return out.append("]").toString();
    }

    private PilotAction gap(String message) {
        throw new PilotGapException(scenarioId + ": " + message);
    }
}
