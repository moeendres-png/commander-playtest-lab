package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.constants.TurnPhase;
import mage.constants.Zone;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * RG-03 advanced causal temporal qualification: skips, extra turns/combats,
 * stack/trigger blocking, multiplayer priority and fresh-session replay.
 *
 * <p>Every transition is provider-native. The test script chooses only exact
 * offered actions and never edits turn/phase/step fields.</p>
 */
class XmageTemporalAdvancedProgressionTest {

    private static final long SEED = 424242L;

    private static XmageNativeStateRestoration.Plan basePlan(
            String id,
            int playerCount,
            List<XmageNativeStateRestoration.RequestedObject> objects
    ) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", "Rograkh, Son of Rohgahh", pid, 0));
        }
        return new XmageNativeStateRestoration.Plan(
                id, playerCount, SEED, players, commanders, List.of(), objects,
                1, TurnPhase.PRECOMBAT_MAIN, PhaseStep.PRECOMBAT_MAIN,
                "P1", "P1");
    }

    private static XmageNativeStateRestoration.RequestedObject object(
            String id, String name, String owner, Zone zone
    ) {
        return new XmageNativeStateRestoration.RequestedObject(
                id, name, owner, owner, zone, false);
    }

    private static Arrived arrive(
            XmageNativeStateRestoration.Plan plan,
            String tag
    ) {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, tag);
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new Arrived(session, restoration, seats);
    }

    @Test
    void momentOfSilenceSkipsTheNativeCombatPhase() {
        XmageNativeStateRestoration.Plan plan = basePlan(
                "rg03-skip-combat", 3,
                List.of(
                        object("obj:silence", "Moment of Silence", "P1", Zone.HAND),
                        object("obj:plains", "Plains", "P1", Zone.BATTLEFIELD),
                        object("obj:bears", "Grizzly Bears", "P1", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, "rg03-skip-combat");

        castTargetPlayerAndResolve(
                arrived, "Moment of Silence", "P1",
                "Plains \u2014 {T}: Add {W}.", "rg03-skip");

        XmageTemporalProgressionDriver.ProgressionResult result =
                XmageTemporalProgressionDriver.driveUntil(
                        arrived.session(), arrived.seats(),
                        (session, seats, observed) ->
                                observed.get("turn_number").getAsInt() == 1
                                        && "POSTCOMBAT_MAIN".equals(
                                                observed.get("phase").getAsString())
                                        && "POSTCOMBAT_MAIN".equals(
                                                observed.get("step").getAsString()),
                        neutralScript(arrived.seats(), null),
                        120);

        assertTrue(result.temporalTrace().stream()
                        .anyMatch(sample -> sample.contains("/PRECOMBAT_MAIN/")));
        assertTrue(result.temporalTrace().stream()
                        .anyMatch(sample -> sample.contains("/POSTCOMBAT_MAIN/")));
        assertFalse(result.temporalTrace().stream()
                        .anyMatch(sample -> sample.contains("/COMBAT/")),
                "Moment of Silence must skip the entire combat phase natively");
    }

    @Test
    void timeWarpCreatesARealExtraTurnBeforeTheNextPlayer() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(object("obj:warp", "Time Warp", "P1", Zone.HAND));
        for (int i = 0; i < 5; i++) {
            objects.add(object("obj:island-" + i, "Island", "P1", Zone.BATTLEFIELD));
        }
        XmageNativeStateRestoration.Plan plan =
                basePlan("rg03-extra-turn", 3, objects);
        Arrived arrived = arrive(plan, "rg03-extra-turn");

        castTargetPlayerAndResolve(
                arrived, "Time Warp", "P1",
                "Island \u2014 {T}: Add {U}.", "rg03-warp");

        XmageTemporalProgressionDriver.ProgressionResult result =
                XmageTemporalProgressionDriver.driveUntil(
                        arrived.session(), arrived.seats(),
                        (session, seats, observed) ->
                                observed.get("turn_number").getAsInt() == 2
                                        && "P1".equals(
                                                observed.get("active_player").getAsString())
                                        && "PRECOMBAT_MAIN".equals(
                                                observed.get("phase").getAsString()),
                        cleanupAwareScript(arrived.seats(), "Island"),
                        260);

        assertEquals(2, result.observed().get("turn_number").getAsInt());
        assertEquals("P1", result.observed().get("active_player").getAsString(),
                "Time Warp extra turn must precede P2's normal turn");
    }

    @Test
    void relentlessAssaultCreatesASecondCombatInTheSameTurn() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(object("obj:assault", "Relentless Assault", "P1", Zone.HAND));
        objects.add(object("obj:bears", "Grizzly Bears", "P1", Zone.BATTLEFIELD));
        for (int i = 0; i < 4; i++) {
            objects.add(object("obj:mountain-" + i, "Mountain", "P1", Zone.BATTLEFIELD));
        }
        XmageNativeStateRestoration.Plan plan =
                basePlan("rg03-extra-combat", 4, objects);
        Arrived arrived = arrive(plan, "rg03-extra-combat");

        // Complete the ordinary first combat without attacking.
        XmageTemporalProgressionDriver.ProgressionResult firstCombat =
                XmageTemporalProgressionDriver.driveUntil(
                        arrived.session(), arrived.seats(),
                        (session, seats, observed) ->
                                observed.get("turn_number").getAsInt() == 1
                                        && "POSTCOMBAT_MAIN".equals(
                                                observed.get("phase").getAsString())
                                        && "P1".equals(
                                                observed.get("priority_player").getAsString()),
                        neutralScript(arrived.seats(), null),
                        140);
        assertTrue(firstCombat.temporalTrace().stream()
                .anyMatch(sample -> sample.contains("/COMBAT/")));

        XmageExternalRiskSignalTest.passToActor(
                arrived.session(), "rg03-assault", arrived.seats(), "P1");
        XmageFullGameTaxExecutionTest.submit(
                arrived.session(), "rg03-assault-cast",
                XmageExternalRiskSignalTest.spellOffer(
                        arrived.session().legalActionsPayload(), "Relentless Assault"));
        XmageExternalRiskSignalTest.payHomogeneous(
                arrived.session(), "rg03-assault-pay",
                "Mountain \u2014 {T}: Add {R}.", 12);
        XmageExternalRiskSignalTest.resolveStackEmpty(
                arrived.session(), "rg03-assault-resolve");

        XmageTemporalProgressionDriver.ProgressionResult extraCombat =
                XmageTemporalProgressionDriver.driveUntil(
                        arrived.session(), arrived.seats(),
                        (session, seats, observed) ->
                                observed.get("turn_number").getAsInt() == 1
                                        && "COMBAT".equals(observed.get("phase").getAsString())
                                        && "DECLARE_ATTACKERS".equals(
                                                observed.get("step").getAsString()),
                        neutralScript(arrived.seats(), null),
                        80);

        assertEquals(1, extraCombat.observed().get("turn_number").getAsInt());
        assertEquals("DECLARE_ATTACKERS",
                extraCombat.observed().get("step").getAsString(),
                "additional combat must occur in the same turn");
    }

    @Test
    void unresolvedSpellAndTriggerBlockTemporalAdvanceUntilNativeSettlement() {
        ScenarioResult first = stackBlockingScenario("rg03-stack-a");
        ScenarioResult second = stackBlockingScenario("rg03-stack-b");

        assertEquals(41, first.lifeP2());
        assertEquals(41, second.lifeP2());
        assertTrue(first.stackWasNonEmptyBeforeDrive());
        assertTrue(first.stackEmptyAtTarget());
        assertTrue(first.progression().decisionClasses().stream()
                .filter("priority"::equals).count() >= 3,
                "real spell plus Soul Warden trigger must require native priority progression");

        // Fresh-session semantic replay: no process-local UUIDs are compared.
        assertEquals(first.progression().temporalTrace(),
                second.progression().temporalTrace());
        assertEquals(first.progression().decisionClasses(),
                second.progression().decisionClasses());
        assertEquals(first.progression().observed().toString(),
                second.progression().observed().toString());
    }

    @Test
    void threeAndFivePlayerPriorityRoundsVisitEverySeatBeforePhaseAdvance() {
        for (int count : List.of(3, 5)) {
            XmageNativeStateRestoration.Plan plan =
                    basePlan("rg03-priority-" + count, count, List.of());
            Arrived arrived = arrive(plan, "rg03-priority-" + count);
            List<String> actors = new ArrayList<>();

            XmageTemporalProgressionDriver.ProgressionResult result =
                    XmageTemporalProgressionDriver.driveUntil(
                            arrived.session(), arrived.seats(),
                            (session, seats, observed) ->
                                    "COMBAT".equals(observed.get("phase").getAsString()),
                            capturingNeutralScript(arrived.seats(), actors),
                            40);

            assertEquals(count, actors.size(),
                    "one complete main-phase priority round before combat");
            Set<String> expected = new LinkedHashSet<>();
            for (int seat = 1; seat <= count; seat++) {
                expected.add("P" + seat);
            }
            assertEquals(expected, new LinkedHashSet<>(actors),
                    "every live principal must receive priority");
            assertEquals("COMBAT", result.observed().get("phase").getAsString());
        }
    }

    private static ScenarioResult stackBlockingScenario(String tag) {
        XmageNativeStateRestoration.Plan plan = basePlan(
                tag, 3,
                List.of(
                        object("obj:bears", "Grizzly Bears", "P1", Zone.HAND),
                        object("obj:forest-a", "Forest", "P1", Zone.BATTLEFIELD),
                        object("obj:forest-b", "Forest", "P1", Zone.BATTLEFIELD),
                        object("obj:warden", "Soul Warden", "P2", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, tag);

        XmageFullGameTaxExecutionTest.submit(
                arrived.session(), tag + "-cast",
                XmageExternalRiskSignalTest.spellOffer(
                        arrived.session().legalActionsPayload(), "Grizzly Bears"));
        XmageExternalRiskSignalTest.payHomogeneous(
                arrived.session(), tag + "-pay",
                "Forest \u2014 {T}: Add {G}.", 8);

        boolean nonEmpty = !arrived.session().restorationGame().getStack().isEmpty();
        XmageTemporalProgressionDriver.ProgressionResult progression =
                XmageTemporalProgressionDriver.driveUntil(
                        arrived.session(), arrived.seats(),
                        (session, seats, observed) ->
                                "COMBAT".equals(observed.get("phase").getAsString())
                                        && "DECLARE_ATTACKERS".equals(
                                                observed.get("step").getAsString()),
                        neutralScript(arrived.seats(), null),
                        120);

        return new ScenarioResult(
                progression,
                nonEmpty,
                arrived.session().restorationGame().getStack().isEmpty(),
                arrived.seats().get("P2").getLife());
    }

    private static void castTargetPlayerAndResolve(
            Arrived arrived,
            String spellName,
            String targetPid,
            String manaLabel,
            String tag
    ) {
        XmageFullGameTaxExecutionTest.submit(
                arrived.session(), tag + "-cast",
                XmageExternalRiskSignalTest.spellOffer(
                        arrived.session().legalActionsPayload(), spellName));

        JsonObject targetLegal = arrived.session().legalActionsPayload();
        assertEquals("target", targetLegal.get("decision_class").getAsString());
        String targetUuid = arrived.seats().get(targetPid).getId().toString();
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : targetLegal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (metadata.has("object_id")
                    && targetUuid.equals(metadata.get("object_id").getAsString())) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "exact target player must be provider-offered");
        XmageFullGameTaxExecutionTest.submit(
                arrived.session(), tag + "-target", matches.get(0));
        XmageExternalRiskSignalTest.payHomogeneous(
                arrived.session(), tag + "-pay", manaLabel, 16);
        XmageExternalRiskSignalTest.resolveStackEmpty(
                arrived.session(), tag + "-resolve");
    }

    /**
     * Extra-turn progression crosses cleanup. The injected Time Warp plus the
     * natural draw can leave P1 above maximum hand size, so the external test
     * pilot explicitly discards one provider-offered scaffolding basic. The
     * selector is semantic (name + greatest stable hand zone_index), never
     * first/random/default, and it is enabled only for a native discard frame.
     */
    private static XmageTemporalProgressionDriver.DecisionSource cleanupAwareScript(
            Map<String, Player> seats,
            String discardCardName
    ) {
        return (pending, legal, index) -> {
            String dc = pending.get("decision_class").getAsString();
            if ("choose_object".equals(dc)) {
                JsonObject context = pending.has("context")
                        && pending.get("context").isJsonObject()
                        ? pending.getAsJsonObject("context") : new JsonObject();
                String targetName = context.has("target_name")
                        && !context.get("target_name").isJsonNull()
                        ? context.get("target_name").getAsString() : "";
                if (!targetName.endsWith("to discard")) {
                    return null;
                }
                JsonObject chosen = null;
                int chosenIndex = Integer.MIN_VALUE;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    JsonObject metadata = action.getAsJsonObject("metadata");
                    JsonObject nativeMeta = metadata.has("xmage_option_metadata")
                            && metadata.get("xmage_option_metadata").isJsonObject()
                            ? metadata.getAsJsonObject("xmage_option_metadata")
                            : new JsonObject();
                    String name = nativeMeta.has("name")
                            ? nativeMeta.get("name").getAsString() : "";
                    if (!discardCardName.equals(name) || !nativeMeta.has("zone_index")) {
                        continue;
                    }
                    int zoneIndex = nativeMeta.get("zone_index").getAsInt();
                    if (zoneIndex > chosenIndex) {
                        chosen = action;
                        chosenIndex = zoneIndex;
                    } else if (zoneIndex == chosenIndex) {
                        throw new AssertionError(
                                "discard semantic zone_index is ambiguous: " + zoneIndex);
                    }
                }
                if (chosen == null) {
                    throw new AssertionError(
                            "required scripted cleanup discard not provider-offered: "
                                    + discardCardName);
                }
                return proposal("rg03-cleanup-discard-" + index,
                        legal.get("actor_id").getAsString(), chosen);
            }
            return neutralProposal(pending, legal, index);
        };
    }

    private static XmageTemporalProgressionDriver.DecisionSource capturingNeutralScript(
            Map<String, Player> seats,
            List<String> priorityActors
    ) {
        return (pending, legal, index) -> {
            String dc = pending.get("decision_class").getAsString();
            String actorUuid = legal.get("actor_id").getAsString();
            if ("priority".equals(dc) && priorityActors != null) {
                priorityActors.add(pidFor(seats, actorUuid));
            }
            return neutralProposal(pending, legal, index);
        };
    }

    private static XmageTemporalProgressionDriver.DecisionSource neutralScript(
            Map<String, Player> seats,
            List<String> priorityActors
    ) {
        return capturingNeutralScript(seats, priorityActors);
    }

    private static JsonObject neutralProposal(
            JsonObject pending,
            JsonObject legal,
            int index
    ) {
        String dc = pending.get("decision_class").getAsString();
        String actor = legal.get("actor_id").getAsString();
        if ("priority".equals(dc)) {
            return proposal("rg03-adv-pass-" + index, actor,
                    exactByType(legal, "pass_priority", null));
        }
        if ("declare_attacker".equals(dc)) {
            return proposal("rg03-adv-hold-" + index, actor,
                    exactByType(legal, "declare_attackers", "hold_attacker"));
        }
        if ("declare_blocker".equals(dc)) {
            return emptySelectionProposal(
                    "rg03-adv-no-block-" + index, actor);
        }
        return null;
    }

    private static JsonObject exactByType(
            JsonObject legal,
            String actionType,
            String optionType
    ) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!actionType.equals(action.get("action_type").getAsString())) {
                continue;
            }
            if (optionType != null
                    && !optionType.equals(action.getAsJsonObject("metadata")
                            .get("option_type").getAsString())) {
                continue;
            }
            matches.add(action);
        }
        if (matches.size() != 1) {
            throw new AssertionError("expected exact one " + actionType + "/"
                    + optionType + ", got " + matches.size());
        }
        return matches.get(0);
    }

    private static JsonObject proposal(
            String id, String actor, JsonObject action
    ) {
        return XmageFullGameTaxExecutionTest.genericProposal(
                id, actor,
                action.get("action_id").getAsString(),
                action.get("action_type").getAsString());
    }

    private static JsonObject emptySelectionProposal(String id, String actor) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", id);
        proposal.addProperty("actor_id", actor);
        proposal.add("legal_action_id", JsonNull.INSTANCE);
        proposal.addProperty("action_type", "structural_decision");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("selected_option_ids", new JsonArray());
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "rg03-explicit-advanced-temporal-script");
        return proposal;
    }

    private static String pidFor(Map<String, Player> seats, String uuid) {
        for (Map.Entry<String, Player> entry : seats.entrySet()) {
            if (entry.getValue().getId().toString().equals(uuid)) {
                return entry.getKey();
            }
        }
        throw new AssertionError("unknown decision actor " + uuid);
    }

    private record Arrived(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats
    ) {
    }

    private record ScenarioResult(
            XmageTemporalProgressionDriver.ProgressionResult progression,
            boolean stackWasNonEmptyBeforeDrive,
            boolean stackEmptyAtTarget,
            int lifeP2
    ) {
    }
}
