package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.abilities.ActivatedAbility;
import mage.constants.Zone;
import mage.game.Game;
import mage.players.Player;
import mage.target.Target;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

import static org.commanderlab.xmage.DecisionClassMatrixHarness.Placed;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.Scenario;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.Step;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.actions;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.labels;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.nativeField;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.optionType;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.pass;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.proposal;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.sorted;
import static org.commanderlab.xmage.DecisionClassMatrixHarness.step;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #662 SLOT-06 per-decision-class matrix on the full-game production lane.
 *
 * <p>For each decision class, a native-restored scenario reaches one real pending
 * decision of that class, and the test checks:</p>
 * <ul>
 *   <li>L1: {@code get_legal_actions} is non-empty and set-equal to the engine's
 *       option set. The test computes that set itself from the native callback
 *       arguments ({@link XmageFullGameSession#pendingNativeWitness()}) and the
 *       live game through the engine's own API, never from the bridge's
 *       {@code legal_options}.</li>
 *   <li>S1: every offered action, submitted in a fresh identical session at the
 *       same frame, is accepted, and the pending decision advances.</li>
 *   <li>S2: a stale offset, a stale decision id, a wrong actor, an option that was
 *       not offered and a malformed proposal each fail with a typed error, and the
 *       privileged engine-state digest, decision identity and decision count are
 *       unchanged afterwards.</li>
 * </ul>
 *
 * <p>Every class the lane can emit appears either here or in
 * {@link XmageFullGameDecisionClassInventoryTest} with a code reason.</p>
 */
class XmageFullGameDecisionClassMatrixTest {

    static final Map<String, Scenario> SCENARIOS = new LinkedHashMap<>();

    static {
        SCENARIOS.put("priority", new Scenario("matrix-priority", 66201L,
                List.of(Placed.hand("P1", "Lightning Bolt"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Grizzly Bears")),
                List.of(), "priority", "P1"));
        SCENARIOS.put("target", new Scenario("matrix-target", 66202L,
                List.of(Placed.hand("P1", "Lightning Bolt"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P2", "Grizzly Bears")),
                List.of(step("priority", "P1", "Cast Lightning Bolt")),
                "target", "P1"));
        SCENARIOS.put("mana_payment", new Scenario("matrix-mana-payment", 66203L,
                List.of(Placed.hand("P1", "Lightning Bolt"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Plains")),
                List.of(step("priority", "P1", "Cast Lightning Bolt"),
                        new Step("target", "P1", "target P2",
                                action -> label(action).equals("Full Game Seat 2"))),
                "mana_payment", "P1"));
        SCENARIOS.put("target_amount", new Scenario("matrix-target-amount", 66204L,
                List.of(Placed.hand("P1", "Forked Bolt"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P2", "Grizzly Bears")),
                List.of(step("priority", "P1", "Cast Forked Bolt")),
                "target_amount", "P1"));
        SCENARIOS.put("mode", new Scenario("matrix-mode", 66205L,
                List.of(Placed.hand("P1", "Boros Charm"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Plains"),
                        Placed.battlefield("P1", "Grizzly Bears")),
                List.of(step("priority", "P1", "Cast Boros Charm")),
                "mode", "P1"));
        SCENARIOS.put("announce_x", new Scenario("matrix-announce-x", 66206L,
                List.of(Placed.hand("P1", "Blaze"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Mountain")),
                List.of(step("priority", "P1", "Cast Blaze")),
                "announce_x", "P1"));
        SCENARIOS.put("trigger_order", new Scenario("matrix-trigger-order", 66207L,
                List.of(Placed.hand("P1", "Grizzly Bears"),
                        Placed.battlefield("P1", "Forest"),
                        Placed.battlefield("P1", "Forest"),
                        Placed.battlefield("P1", "Soul Warden"),
                        Placed.battlefield("P1", "Soul Warden")),
                List.of(step("priority", "P1", "Cast Grizzly Bears"),
                        DecisionClassMatrixHarness.passUntil("trigger_order", "P1")),
                "trigger_order", "P1"));
        SCENARIOS.put("choice", new Scenario("matrix-choice", 66208L,
                List.of(Placed.hand("P1", "Painter's Servant"),
                        Placed.battlefield("P1", "Plains"),
                        Placed.battlefield("P1", "Plains")),
                List.of(step("priority", "P1", "Cast Painter's Servant"),
                        DecisionClassMatrixHarness.passUntil("choice", "P1")),
                "choice", "P1"));
        SCENARIOS.put("replacement_effect", new Scenario("matrix-replacement", 66209L,
                List.of(Placed.hand("P1", "Battlegrowth"),
                        Placed.battlefield("P1", "Forest"),
                        Placed.battlefield("P1", "Hardened Scales"),
                        Placed.battlefield("P1", "Corpsejack Menace"),
                        Placed.battlefield("P1", "Grizzly Bears")),
                List.of(step("priority", "P1", "Cast Battlegrowth"),
                        step("target", "P1", "Grizzly Bears"),
                        DecisionClassMatrixHarness.passUntil("replacement_effect", "P1")),
                "replacement_effect", "P1"));
        SCENARIOS.put("choose_object", new Scenario("matrix-choose-object", 66210L,
                List.of(Placed.hand("P1", "Fact or Fiction"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island")),
                List.of(step("priority", "P1", "Cast Fact or Fiction"),
                        DecisionClassMatrixHarness.passUntil("choose_object", "P2")),
                "choose_object", "P2"));
        SCENARIOS.put("pile", new Scenario("matrix-pile", 66210L,
                List.of(Placed.hand("P1", "Fact or Fiction"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island")),
                List.of(step("priority", "P1", "Cast Fact or Fiction"),
                        DecisionClassMatrixHarness.passUntil("choose_object", "P2"),
                        DecisionClassMatrixHarness.selectNone("choose_object", "P2")),
                "pile", "P1"));
        SCENARIOS.put("declare_attacker", new Scenario("matrix-attack", 66211L,
                List.of(Placed.battlefield("P1", "Grizzly Bears")),
                List.of(DecisionClassMatrixHarness.passUntil("declare_attacker", "P1")),
                "declare_attacker", "P1"));
        SCENARIOS.put("declare_blocker", new Scenario("matrix-block", 66214L,
                List.of(Placed.battlefield("P1", "Colossal Dreadmaw"),
                        Placed.battlefield("P2", "Grizzly Bears")),
                List.of(DecisionClassMatrixHarness.passUntil("declare_attacker", "P1"),
                        step("declare_attacker", "P1", "attacks"),
                        DecisionClassMatrixHarness.passUntil("declare_blocker", "P2")),
                "declare_blocker", "P2"));
        SCENARIOS.put("multi_amount_combat", new Scenario("matrix-trample", 66214L,
                List.of(Placed.battlefield("P1", "Colossal Dreadmaw"),
                        Placed.battlefield("P2", "Grizzly Bears")),
                List.of(DecisionClassMatrixHarness.passUntil("declare_attacker", "P1"),
                        step("declare_attacker", "P1", "attacks"),
                        DecisionClassMatrixHarness.passUntil("declare_blocker", "P2"),
                        step("declare_blocker", "P2", "blocks"),
                        DecisionClassMatrixHarness.passUntil("multi_amount", "P1")),
                "multi_amount", "P1"));
        SCENARIOS.put("amount", new Scenario("matrix-amount", 66217L,
                List.of(Placed.hand("P1", "Indentured Djinn"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island"),
                        Placed.battlefield("P1", "Island")),
                List.of(step("priority", "P1", "Cast Indentured Djinn"),
                        DecisionClassMatrixHarness.passUntil("amount", "P2")),
                "amount", "P2"));
        SCENARIOS.put("choose_use", new Scenario("matrix-choose-use", 66212L,
                List.of(Placed.hand("P1", "Ponder"),
                        Placed.battlefield("P1", "Island")),
                List.of(step("priority", "P1", "Cast Ponder"),
                        DecisionClassMatrixHarness.passUntil("choose_object", "P1"),
                        DecisionClassMatrixHarness.chooseFirst("choose_object", "P1"),
                        DecisionClassMatrixHarness.chooseFirst("choose_object", "P1"),
                        DecisionClassMatrixHarness.passUntil("choose_use", "P1")),
                "choose_use", "P1"));
        SCENARIOS.put("multi_amount", new Scenario("matrix-multi-amount", 66215L,
                List.of(Placed.hand("P1", "Manamorphose"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Mountain")),
                List.of(step("priority", "P1", "Cast Manamorphose"),
                        DecisionClassMatrixHarness.passUntil("multi_amount", "P1")),
                "multi_amount", "P1"));
        SCENARIOS.put("ring_bearer", new Scenario("matrix-ring-bearer", 66213L,
                List.of(Placed.hand("P1", "Claim the Precious"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Llanowar Elves"),
                        Placed.battlefield("P1", "Elvish Mystic"),
                        Placed.battlefield("P2", "Grizzly Bears")),
                List.of(step("priority", "P1", "Cast Claim the Precious"),
                        step("target", "P1", "Grizzly Bears"),
                        DecisionClassMatrixHarness.passUntil("choose_object", "P1")),
                "choose_object", "P1"));
        SCENARIOS.put("cast_ability", new Scenario("matrix-cast-ability", 66216L,
                List.of(Placed.hand("P1", "Kari Zev's Expertise"),
                        Placed.hand("P1", "Fire // Ice"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P1", "Mountain"),
                        Placed.battlefield("P2", "Grizzly Bears")),
                List.of(step("priority", "P1", "Cast Kari Zev's Expertise"),
                        step("target", "P1", "Grizzly Bears"),
                        DecisionClassMatrixHarness.passUntil("choose_use", "P1"),
                        step("choose_use", "P1", "Yes")),
                "choice", "P1"));
        SCENARIOS.put("land_or_spell", new Scenario("matrix-land-or-spell", 66219L,
                List.of(Placed.battlefield("P1", "Gix, Yawgmoth Praetor"),
                        Placed.hand("P1", "Grizzly Bears"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        Placed.battlefield("P1", "Swamp"),
                        new Placed("P2", Zone.LIBRARY, "Agadeem's Awakening")),
                List.of(step("priority", "P1", "Exile the top X"),
                        DecisionClassMatrixHarness.numeric("announce_x", "P1", 1),
                        step("target", "P1", "Full Game Seat 2"),
                        DecisionClassMatrixHarness.passUntilAny(),
                        step("choose_object", "P1", "Grizzly Bears"),
                        DecisionClassMatrixHarness.passUntilAny(),
                        step("choose_use", "P1", "Yes")),
                "choice", "P1"));
        // Pregame (no restoration): starting player, mulligan, London bottom.
        SCENARIOS.put("starting_player", new Scenario("matrix-start", 66218L, null,
                List.of(), "choose_object", "P1"));
        SCENARIOS.put("mulligan", new Scenario("matrix-mulligan", 66218L, null,
                List.of(step("choose_object", "P1", "Full Game Seat 1")), "mulligan", "P1"));
        SCENARIOS.put("london_bottom", new Scenario("matrix-london", 66218L, null,
                List.of(step("choose_object", "P1", "Full Game Seat 1"),
                        step("mulligan", "P1", "Take mulligan"),
                        step("mulligan", "P2", "Keep opening hand")),
                "target", "P1"));
    }

    private static String label(JsonObject action) {
        return DecisionClassMatrixHarness.label(action);
    }

    @Test
    void priorityMatrix() {
        runClass("priority");
    }

    @Test
    void targetMatrix() {
        runClass("target");
    }

    @Test
    void manaPaymentMatrix() {
        runClass("mana_payment");
    }

    @Test
    void targetAmountMatrix() {
        runClass("target_amount");
    }

    @Test
    void modeMatrix() {
        runClass("mode");
    }

    @Test
    void announceXMatrix() {
        runClass("announce_x");
    }

    @Test
    void triggerOrderMatrix() {
        runClass("trigger_order");
    }

    @Test
    void choiceMatrix() {
        runClass("choice");
    }

    @Test
    void replacementEffectMatrix() {
        runClass("replacement_effect");
    }

    @Test
    void chooseObjectMatrix() {
        runClass("choose_object");
    }

    @Test
    void pileMatrix() {
        runClass("pile");
    }

    @Test
    void declareAttackerMatrix() {
        runClass("declare_attacker");
    }

    @Test
    void declareBlockerMatrix() {
        runClass("declare_blocker");
    }

    @Test
    void multiAmountCombatMatrix() {
        runClass("multi_amount_combat");
    }

    @Test
    void amountMatrix() {
        runClass("amount");
    }

    @Test
    void chooseUseMatrix() {
        runClass("choose_use");
    }

    @Test
    void multiAmountMatrix() {
        runClass("multi_amount");
    }

    @Test
    void ringBearerMatrix() {
        runClass("ring_bearer");
    }

    @Test
    void castAbilityMatrix() {
        runClass("cast_ability");
    }

    @Test
    void landOrSpellMatrix() {
        runClass("land_or_spell");
    }

    @Test
    void startingPlayerMatrix() {
        runClass("starting_player");
    }

    @Test
    void mulliganMatrix() {
        runClass("mulligan");
    }

    @Test
    void londonBottomMatrix() {
        runClass("london_bottom");
    }


    // ---- matrix core ----------------------------------------------------------

    static void runClass(String key) {
        Scenario scenario = SCENARIOS.get(key);
        String decisionClass = scenario.targetClass();
        DecisionClassMatrixHarness.Live live = DecisionClassMatrixHarness.open(scenario);
        JsonObject frame = DecisionClassMatrixHarness.driveToTarget(live, scenario);

        // L1: non-empty and set-equal to the engine oracle.
        assertFalse(actions(frame).isEmpty(), decisionClass + ": empty projection");
        assertTrue(frame.get("complete").getAsBoolean());
        Object[] witness = live.session().pendingNativeWitness();
        assertTrue(witness.length > 0, key + ": no native witness");
        Oracle oracle = oracleFor(String.valueOf(witness[0]), live, frame, witness);
        assertEquals(oracle.expected(), oracle.projected(),
                decisionClass + ": projection must equal the engine option set; frame " + labels(frame));

        // S2 on this live frame: each malformed submission is rejected with no mutation.
        rejectWithoutMutation(live, frame);

        // S1: every offered action is accepted at the same frame in a fresh session.
        // Option ids are fresh per game, so the same option in a fresh identical
        // session is named by its semantic key: type, label and ordinal among equals.
        cardinalityAccepted(scenario, frame);
        List<String> keys = semanticKeys(frame);
        for (String optionKey : keys) {
            DecisionClassMatrixHarness.Live fresh = DecisionClassMatrixHarness.open(scenario);
            JsonObject same = DecisionClassMatrixHarness.driveToTarget(fresh, scenario);
            List<String> sameKeys = semanticKeys(same);
            assertEquals(new java.util.TreeSet<>(keys), new java.util.TreeSet<>(sameKeys),
                    decisionClass + " S1: identical option set in a fresh session");
            JsonObject action = actions(same).get(sameKeys.indexOf(optionKey));
            List<JsonObject> proposals = acceptedProposals(same, action);
            for (int variant = 0; variant < proposals.size(); variant++) {
                DecisionClassMatrixHarness.Live run = fresh;
                JsonObject proposal = proposals.get(variant);
                if (variant > 0) {
                    run = DecisionClassMatrixHarness.open(scenario);
                    JsonObject again = DecisionClassMatrixHarness.driveToTarget(run, scenario);
                    proposal = rebind(proposal, again, actions(again).get(semanticKeys(again).indexOf(optionKey)));
                }
                String before = proposal.getAsJsonObject("choices").get("decision_id").getAsString();
                JsonObject result = run.session().submitAction(proposal);
                assertEquals(before, result.get("executed_decision_id").getAsString());
                JsonObject after = run.session().pendingDecisionPayload();
                if (!after.get("decision").isJsonNull()) {
                    assertNotEquals(before, after.getAsJsonObject("decision").get("decision_id").getAsString(),
                            decisionClass + " S1: decision must advance after " + optionKey);
                }
            }
        }
    }

    /**
     * The proposals S1 submits for one offered action: the action itself, or for a
     * numeric action its lowest and highest legal value, or for a joint vector the
     * lowest and highest legal totals filled leg by leg.
     */
    static List<JsonObject> acceptedProposals(JsonObject frame, JsonObject action) {
        List<JsonObject> proposals = new ArrayList<>();
        JsonObject context = frame.getAsJsonObject("decision").getAsJsonObject("context");
        boolean numeric = context.has("numeric_legs")
                || context.has("numeric_min") && context.has("numeric_max");
        if (!numeric) {
            proposals.add(proposal(frame, action));
        } else if (context.has("numeric_legs")) {
            for (int total : new int[] {context.get("numeric_total_min").getAsInt(),
                    context.get("numeric_total_max").getAsInt()}) {
                com.google.gson.JsonArray vector = new com.google.gson.JsonArray();
                int remaining = total;
                for (com.google.gson.JsonElement leg : context.getAsJsonArray("numeric_legs")) {
                    int min = leg.getAsJsonObject().get("min").getAsInt();
                    int take = Math.max(min, Math.min(leg.getAsJsonObject().get("max").getAsInt(), remaining));
                    vector.add(take);
                    remaining -= take;
                }
                JsonObject proposal = proposal(frame, action);
                proposal.getAsJsonObject("choices").add("numeric_choices", vector);
                proposals.add(proposal);
            }
        } else {
            for (int value : new int[] {context.get("numeric_min").getAsInt(),
                    context.get("numeric_max").getAsInt()}) {
                JsonObject proposal = proposal(frame, action);
                proposal.getAsJsonObject("choices").addProperty("numeric_choice", value);
                proposals.add(proposal);
            }
        }
        return proposals;
    }

    /** Re-bind a proposal built on one session's frame to an identical frame of another. */
    static JsonObject rebind(JsonObject proposal, JsonObject frame, JsonObject action) {
        JsonObject copy = proposal.deepCopy();
        copy.addProperty("actor_id", action.get("actor_id").getAsString());
        copy.addProperty("legal_action_id", action.get("action_id").getAsString());
        copy.getAsJsonObject("choices").addProperty("decision_id", frame.get("decision_id").getAsString());
        copy.getAsJsonObject("choices").addProperty("decision_offset", frame.get("decision_offset").getAsLong());
        return copy;
    }

    /** S1 for selection cardinality: the empty selection (min 0) and a maximal one. */
    static void cardinalityAccepted(Scenario scenario, JsonObject frame) {
        JsonObject decision = frame.getAsJsonObject("decision");
        int min = decision.get("minimum_selections").getAsInt();
        int max = decision.get("maximum_selections").getAsInt();
        if (min == 0 && max > 0) {
            DecisionClassMatrixHarness.Live fresh = DecisionClassMatrixHarness.open(scenario);
            JsonObject same = DecisionClassMatrixHarness.driveToTarget(fresh, scenario);
            JsonObject result = fresh.session().submitAction(DecisionClassMatrixHarness.emptySelection(same));
            assertEquals(same.get("decision_id").getAsString(), result.get("executed_decision_id").getAsString());
        }
        if (max > 1 && actions(frame).size() > 1) {
            DecisionClassMatrixHarness.Live fresh = DecisionClassMatrixHarness.open(scenario);
            JsonObject same = DecisionClassMatrixHarness.driveToTarget(fresh, scenario);
            List<JsonObject> offered = actions(same);
            int count = Math.min(max, offered.size());
            JsonObject proposal = proposal(same, offered.get(0));
            com.google.gson.JsonArray selected = new com.google.gson.JsonArray();
            for (int index = 0; index < count; index++) {
                selected.add(DecisionClassMatrixHarness.metadata(offered.get(index)).get("option_id").getAsString());
            }
            proposal.getAsJsonObject("choices").add("selected_option_ids", selected);
            JsonObject result = fresh.session().submitAction(proposal);
            assertEquals(same.get("decision_id").getAsString(), result.get("executed_decision_id").getAsString());
        }
    }

    static List<String> semanticKeys(JsonObject frame) {
        List<String> keys = new ArrayList<>();
        Map<String, Integer> seen = new LinkedHashMap<>();
        for (JsonObject action : actions(frame)) {
            // Engine object ids in labels ("[270]") are fresh per game; strip them.
            String base = optionType(action) + "|" + label(action).replaceAll("\\[[0-9a-f]{3}\\]", "[id]");
            int ordinal = seen.merge(base, 1, Integer::sum);
            keys.add(base + "#" + ordinal);
        }
        return keys;
    }

    record Oracle(Set<String> expected, Set<String> projected) {
    }

    static Oracle oracleFor(String kind, DecisionClassMatrixHarness.Live live,
                            JsonObject frame, Object[] witness) {
        Game game = live.session().restorationGame();
        Player actor = game.getPlayer(UUID.fromString(frame.get("actor_id").getAsString()));
        JsonObject decision = frame.getAsJsonObject("decision");
        Set<String> expected = new HashSet<>();
        Set<String> projected = new HashSet<>();
        switch (kind) {
            case "priority" -> {
                // Engine: pass, plus every playable ability (no hash de-duplication). A mana
                // ability with its own mana cost needs the F-35 affordability filter; the
                // scenarios hold none, which the assertion keeps true.
                expected.add("pass_priority");
                for (ActivatedAbility ability
                        : ((mage.players.PlayerImpl) actor).getPlayable(game, false, Zone.ALL, false)) {
                    assertTrue(!ability.isManaAbility() || ability.getManaCostsToPay().isEmpty(),
                            "scenario must not need the F-35 affordability filter: " + ability);
                    expected.add(abilityKey(ability));
                }
                for (JsonObject action : actions(frame)) {
                    projected.add("pass_priority".equals(optionType(action))
                            ? "pass_priority" : actionAbilityKey(action));
                }
            }
            case "target", "target_amount" -> {
                Target target = (Target) witness[1];
                Ability source = (Ability) witness[2];
                mage.cards.Cards cards = witness.length > 3 ? (mage.cards.Cards) witness[3] : null;
                Set<UUID> possible = cards == null
                        ? target.possibleTargets(actor.getId(), source, game)
                        : target.possibleTargets(actor.getId(), source, game,
                        cards.getCards(game).stream().map(mage.MageItem::getId).collect(Collectors.toSet()));
                possible.forEach(id -> expected.add(id.toString()));
                actions(frame).forEach(action -> projected.add(optionId(action)));
                if ("target".equals(kind)) {
                    int min = Math.max(0, target.getMinNumberOfTargets() - target.getSize());
                    int max = Math.min(Math.max(0, target.getMaxNumberOfTargets() - target.getSize()),
                            possible.size());
                    assertEquals(Math.min(min, max), decision.get("minimum_selections").getAsInt(), "min");
                    assertEquals(max, decision.get("maximum_selections").getAsInt(), "max");
                } else {
                    JsonObject context = decision.getAsJsonObject("context");
                    assertEquals(1, context.get("numeric_min").getAsInt());
                    assertEquals(Math.max(1, ((mage.target.TargetAmount) target).getAmountRemaining()),
                            context.get("numeric_max").getAsInt());
                }
            }
            case "mode" -> {
                mage.abilities.Modes modes = (mage.abilities.Modes) witness[1];
                Ability source = (Ability) witness[2];
                List<mage.abilities.Mode> available = new ArrayList<>(modes.getAvailableModes(source, game));
                // CR 700.2a: a mode whose required targets cannot be chosen cannot be chosen,
                // unless no mode can (then the cast rewinds, and all stay listed).
                List<mage.abilities.Mode> choosable = available.stream()
                        .filter(mode -> mode.getTargets().canChoose(actor.getId(), source, game))
                        .toList();
                (choosable.isEmpty() ? available : choosable)
                        .forEach(mode -> expected.add(mode.getId().toString()));
                actions(frame).forEach(action -> projected.add(optionId(action)));
            }
            case "announce_x", "amount" -> {
                JsonObject context = decision.getAsJsonObject("context");
                expected.add(witness[1] + ".." + witness[2]);
                projected.add(context.get("numeric_min").getAsInt() + ".." + context.get("numeric_max").getAsInt());
                assertEquals(1, actions(frame).size(), "one numeric action");
            }
            case "multi_amount" -> {
                @SuppressWarnings("unchecked")
                List<mage.util.MultiAmountMessage> messages = (List<mage.util.MultiAmountMessage>) witness[1];
                JsonObject context = decision.getAsJsonObject("context");
                expected.add("total " + witness[2] + ".." + witness[3]);
                projected.add("total " + context.get("numeric_total_min").getAsInt() + ".."
                        + context.get("numeric_total_max").getAsInt());
                for (int index = 0; index < messages.size(); index++) {
                    expected.add("leg" + index + " " + messages.get(index).min + ".." + messages.get(index).max);
                }
                com.google.gson.JsonArray legs = context.getAsJsonArray("numeric_legs");
                for (int index = 0; index < legs.size(); index++) {
                    JsonObject leg = legs.get(index).getAsJsonObject();
                    projected.add("leg" + index + " " + leg.get("min").getAsInt() + ".." + leg.get("max").getAsInt());
                }
            }
            case "trigger_order" -> {
                @SuppressWarnings("unchecked")
                List<mage.abilities.TriggeredAbility> abilities =
                        (List<mage.abilities.TriggeredAbility>) witness[1];
                abilities.forEach(ability -> expected.add(abilityKey(ability)));
                actions(frame).forEach(action -> projected.add(actionAbilityKey(action)));
            }
            case "choice" -> {
                mage.choices.Choice choice = (mage.choices.Choice) witness[1];
                if (choice.isKeyChoice()) {
                    expected.addAll(choice.getKeyChoices().keySet());
                    actions(frame).forEach(action -> projected.add(nativeField(action, "choice_key")));
                } else {
                    expected.addAll(choice.getChoices());
                    actions(frame).forEach(action -> projected.add(nativeField(action, "choice")));
                }
            }
            case "cast_ability" -> {
                mage.cards.Card card = (mage.cards.Card) witness[1];
                boolean noMana = (Boolean) witness[2];
                Zone zone = game.getState().getZone(card.getMainCard().getId());
                mage.players.PlayerImpl.getCastableSpellAbilities(game, actor.getId(), card, zone, noMana)
                        .values().forEach(ability -> expected.add(abilityKey(ability)));
                actions(frame).forEach(action -> projected.add(actionAbilityKey(action)));
            }
            case "land_or_spell" -> {
                mage.cards.Card card = (mage.cards.Card) witness[1];
                boolean noMana = (Boolean) witness[2];
                Zone zone = game.getState().getZone(card.getMainCard().getId());
                mage.players.PlayerImpl.getCastableSpellAbilities(game, actor.getId(), card, zone, noMana)
                        .values().forEach(ability -> expected.add(abilityKey(ability)));
                for (mage.cards.Card component : mage.util.CardUtil.getCastableComponents(
                        card, null, null, actor, game, null, true)) {
                    if (component.isLand(game)) {
                        component.getAbilities(game).stream()
                                .filter(ability -> ability instanceof mage.abilities.PlayLandAbility)
                                .forEach(ability -> expected.add(abilityKey(ability)));
                    }
                }
                actions(frame).forEach(action -> projected.add(actionAbilityKey(action)));
            }
            case "replacement_effect" -> {
                @SuppressWarnings("unchecked")
                Map<String, String> effects = (Map<String, String>) witness[1];
                expected.addAll(effects.keySet());
                actions(frame).forEach(action -> projected.add(nativeField(action, "xmage_key")));
            }
            case "pile" -> {
                @SuppressWarnings("unchecked")
                List<? extends mage.cards.Card> pile1 = (List<? extends mage.cards.Card>) witness[1];
                @SuppressWarnings("unchecked")
                List<? extends mage.cards.Card> pile2 = (List<? extends mage.cards.Card>) witness[2];
                expected.add("Pile 1:" + pile1.size());
                expected.add("Pile 2:" + pile2.size());
                for (JsonObject action : actions(frame)) {
                    projected.add(DecisionClassMatrixHarness.label(action) + ":"
                            + DecisionClassMatrixHarness.nativeMetadata(action).getAsJsonArray("cards").size());
                }
            }
            case "choose_use" -> {
                expected.add("true");
                expected.add("false");
                actions(frame).forEach(action -> projected.add(nativeField(action, "value")));
            }
            case "mulligan" -> {
                // CR 103.5: keep or take a mulligan.
                expected.add("keep");
                expected.add("mulligan");
                actions(frame).forEach(action -> projected.add(optionType(action)));
            }
            case "declare_attacker" -> {
                // The frame asks about one attacker: hold, or attack each defender it can attack.
                String attackerId = nativeField(actions(frame).get(0), "object_id");
                mage.game.permanent.Permanent attacker = game.getPermanent(UUID.fromString(attackerId));
                assertTrue(actor.getAvailableAttackers(game).contains(attacker), "attacker is available");
                expected.add("hold:" + attackerId);
                for (UUID defender : game.getCombat().getDefenders()) {
                    if (attacker.canAttack(defender, game)) {
                        expected.add("attack:" + defender);
                    }
                }
                for (JsonObject action : actions(frame)) {
                    projected.add("hold_attacker".equals(optionType(action))
                            ? "hold:" + nativeField(action, "object_id")
                            : "attack:" + nativeField(action, "defender_id"));
                }
            }
            case "declare_blocker" -> {
                // The frame asks about one blocker: each attacker it can block (min 0 = no block).
                String blockerId = nativeField(actions(frame).get(0), "blocker_id");
                mage.game.permanent.Permanent blocker = game.getPermanent(UUID.fromString(blockerId));
                for (UUID attackerId : game.getCombat().getAttackers()) {
                    mage.game.permanent.Permanent attacker = game.getPermanent(attackerId);
                    if (attacker != null && blocker.canBlock(attackerId, game)) {
                        expected.add(attackerId.toString());
                    }
                }
                actions(frame).forEach(action -> projected.add(nativeField(action, "attacker_id")));
                assertEquals(0, decision.get("minimum_selections").getAsInt(), "blocking is optional");
            }
            case "mana_payment" -> {
                expected.add("cancel_mana_payment");
                for (mage.constants.ManaType type : mage.constants.ManaType.getTrueManaTypes()) {
                    if (actor.getManaPool().get(type) > 0) {
                        expected.add("pool:" + type);
                    }
                }
                for (mage.game.permanent.Permanent permanent
                        : game.getBattlefield().getAllActivePermanents(actor.getId())) {
                    for (ActivatedAbility ability
                            : permanent.getAbilities().getActivatedManaAbilities(Zone.BATTLEFIELD)) {
                        if (ability.canActivate(actor.getId(), game).canActivate()) {
                            expected.add(abilityKey(ability));
                        }
                    }
                }
                for (mage.abilities.SpecialAction special
                        : game.getState().getSpecialActions().getControlledBy(actor.getId(), true).values()) {
                    expected.add(abilityKey(special));
                }
                for (JsonObject action : actions(frame)) {
                    String type = optionType(action);
                    if ("cancel_mana_payment".equals(type)) {
                        projected.add(type);
                    } else if ("mana_pool".equals(type)) {
                        projected.add("pool:" + nativeField(action, "mana_type"));
                    } else {
                        projected.add(actionAbilityKey(action));
                    }
                }
            }
            default -> throw new AssertionError("no oracle for native callback " + kind);
        }
        return new Oracle(sorted(expected), sorted(projected));
    }

    static String optionId(JsonObject action) {
        return DecisionClassMatrixHarness.metadata(action).get("option_id").getAsString();
    }

    static String abilityKey(Ability ability) {
        return ability.getSourceId() + "/" + ability.getOriginalId();
    }

    static String actionAbilityKey(JsonObject action) {
        return nativeField(action, "source_object_id") + "/" + nativeField(action, "ability_original_id");
    }

    // ---- S2 -------------------------------------------------------------------

    static void rejectWithoutMutation(DecisionClassMatrixHarness.Live live, JsonObject frame) {
        XmageFullGameSession session = live.session();
        JsonObject action = actions(frame).get(0);
        String digest = XmageNativeStateRestoration.readback(session.restorationGame(), live.seats()).toString();
        long count = session.pendingDecisionPayload().get("decision_count").getAsLong();
        String decisionId = frame.get("decision_id").getAsString();

        List<JsonObject> bad = new ArrayList<>();
        JsonObject staleOffset = proposal(frame, action);
        staleOffset.getAsJsonObject("choices").addProperty("decision_offset",
                frame.get("decision_offset").getAsLong() + 1);
        bad.add(staleOffset);
        JsonObject staleId = proposal(frame, action);
        staleId.getAsJsonObject("choices").addProperty("decision_id", "0".repeat(64));
        bad.add(staleId);
        JsonObject wrongActor = proposal(frame, action);
        String other = live.seats().values().stream()
                .map(player -> player.getId().toString())
                .filter(id -> !id.equals(frame.get("actor_id").getAsString()))
                .findFirst().orElseThrow();
        wrongActor.addProperty("actor_id", other);
        bad.add(wrongActor);
        JsonObject unoffered = proposal(frame, action);
        unoffered.addProperty("legal_action_id", decisionId + ":" + "f".repeat(64));
        bad.add(unoffered);
        JsonObject malformed = proposal(frame, action);
        malformed.remove("actor_id");
        bad.add(malformed);

        for (JsonObject proposal : bad) {
            assertThrows(XmageFullGameDecisionController.DecisionException.class,
                    () -> session.submitAction(proposal), "must reject " + proposal);
            JsonObject now = session.pendingDecisionPayload();
            assertEquals(digest, XmageNativeStateRestoration.readback(session.restorationGame(), live.seats()).toString(),
                    "a rejected submission must not mutate the game: " + proposal);
            assertEquals(count, now.get("decision_count").getAsLong());
            assertEquals(decisionId, now.getAsJsonObject("decision").get("decision_id").getAsString());
        }
    }

    static Set<String> keys(Iterable<String> values) {
        return sorted(values);
    }

    static Map<String, Boolean> unused() {
        return Map.of();
    }
}
