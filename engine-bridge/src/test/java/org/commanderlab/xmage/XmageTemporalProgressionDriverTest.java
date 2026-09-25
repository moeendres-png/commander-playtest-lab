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
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * RG-03 qualification: later temporal checkpoints are reached by ordinary
 * engine progression only. The driver never edits GameState clock fields.
 */
class XmageTemporalProgressionDriverTest {

    private static final long SEED = 424242L;

    private static XmageNativeStateRestoration.Plan plan(
            String id,
            int players,
            TurnPhase phase,
            PhaseStep step,
            String priority,
            boolean p2Blocker
    ) {
        List<XmageNativeStateRestoration.RequestedPlayer> seats = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int seat = 1; seat <= players; seat++) {
            String pid = "P" + seat;
            seats.add(new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", "Rograkh, Son of Rohgahh", pid, 0));
        }
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:p1-attacker", "Grizzly Bears", "P1", "P1",
                Zone.BATTLEFIELD, false));
        if (p2Blocker) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:p2-blocker", "Runeclaw Bear", "P2", "P2",
                    Zone.BATTLEFIELD, false));
        }
        return new XmageNativeStateRestoration.Plan(
                id, players, SEED, seats, commanders, List.of(), objects,
                1, phase, step, "P1", priority);
    }

    private static Arrived sessionFor(
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
        return new Arrived(session, restoration, session.restorationSeats());
    }

    @Test
    void parserAcceptsOnlyQualifiedFrozenTemporalTargets() {
        for (String fixture : List.of(
                "PILOT_TRIGGER_ORDER",
                "PILOT_DECLARE_ATTACKER",
                "PILOT_DECLARE_BLOCKER",
                "MICRO_REPLACEMENT",
                "WS05-MP-TURN-3",
                "WS05-CMD-START-2")) {
            XmageNativeStateRestoration.Plan parsed =
                    XmageNativeStateRestoration.planFromFrozenRecord(
                            XmageNativeStateRestorationTest.frozenRecord(fixture),
                            "rg03-" + fixture, SEED);
            assertTrue(XmageNativeStateRestoration.isSupportedTemporalPoint(parsed), fixture);
        }
    }

    @Test
    void reachesUpkeepDrawAndDeclareAttackersWithoutClockMutation() {
        for (TargetCase target : List.of(
                new TargetCase(TurnPhase.BEGINNING, PhaseStep.UPKEEP, "P1"),
                new TargetCase(TurnPhase.BEGINNING, PhaseStep.DRAW, "P1"),
                new TargetCase(TurnPhase.COMBAT, PhaseStep.DECLARE_ATTACKERS, "P1"))) {
            XmageNativeStateRestoration.Plan p = plan(
                    "rg03-" + target.step(), 3,
                    target.phase(), target.step(), target.priority(), false);
            Arrived arrived = sessionFor(p, "rg03-" + target.step());
            XmageTemporalProgressionDriver.ProgressionResult result =
                    XmageTemporalProgressionDriver.driveToPlanTarget(
                            arrived.session(), arrived.seats(), p,
                            transport(arrived.seats(), false, false),
                            80);
            assertEquals(1, result.observed().get("turn_number").getAsInt());
            assertEquals(target.phase().name(), result.observed().get("phase").getAsString());
            assertEquals(target.step().name(), result.observed().get("step").getAsString());
            assertEquals("P1", result.observed().get("active_player").getAsString());
            assertEquals(target.priority(), result.observed().get("priority_player").getAsString());
            assertTrue(result.submittedDecisions() > 0);
        }
    }

    @Test
    void reachesDeclareBlockersViaOneExplicitNativeAttack() {
        XmageNativeStateRestoration.Plan p = plan(
                "rg03-blockers", 4, TurnPhase.COMBAT, PhaseStep.DECLARE_BLOCKERS,
                "P2", true);
        Arrived arrived = sessionFor(p, "rg03-blockers");
        XmageTemporalProgressionDriver.ProgressionResult result =
                XmageTemporalProgressionDriver.driveToPlanTarget(
                        arrived.session(), arrived.seats(), p,
                        transport(arrived.seats(), true, false),
                        120);
        assertEquals("DECLARE_BLOCKERS", result.observed().get("step").getAsString());
        assertEquals("P2", result.observed().get("priority_player").getAsString());
        assertTrue(result.decisionClasses().contains("declare_attacker"));
    }

    @Test
    void reachesCombatDamageWithExplicitAttackAndNoBlockChoice() {
        XmageNativeStateRestoration.Plan p = plan(
                "rg03-damage", 4, TurnPhase.COMBAT, PhaseStep.COMBAT_DAMAGE,
                "P1", true);
        Arrived arrived = sessionFor(p, "rg03-damage");
        XmageTemporalProgressionDriver.ProgressionResult result =
                XmageTemporalProgressionDriver.driveToPlanTarget(
                        arrived.session(), arrived.seats(), p,
                        transport(arrived.seats(), true, true),
                        140);
        assertEquals("COMBAT_DAMAGE", result.observed().get("step").getAsString());
        assertTrue(result.decisionClasses().contains("declare_attacker"));
        assertTrue(result.decisionClasses().contains("declare_blocker"));
    }

    @Test
    void reachesPostcombatMainAtTwoThroughFivePlayers() {
        for (int players = 2; players <= 5; players++) {
            XmageNativeStateRestoration.Plan p = plan(
                    "rg03-post-" + players, players,
                    TurnPhase.POSTCOMBAT_MAIN, PhaseStep.POSTCOMBAT_MAIN,
                    "P1", false);
            Arrived arrived = sessionFor(p, "rg03-post-" + players);
            XmageTemporalProgressionDriver.ProgressionResult result =
                    XmageTemporalProgressionDriver.driveToPlanTarget(
                            arrived.session(), arrived.seats(), p,
                            transport(arrived.seats(), false, false),
                            180);
            assertEquals("POSTCOMBAT_MAIN", result.observed().get("phase").getAsString());
            assertEquals("POSTCOMBAT_MAIN", result.observed().get("step").getAsString());
            assertEquals(players, arrived.seats().size());
        }
    }

    @Test
    void unscriptedDecisionFailsClosedWithoutAdvancingIt() {
        XmageNativeStateRestoration.Plan p = plan(
                "rg03-unscripted", 3, TurnPhase.COMBAT, PhaseStep.DECLARE_ATTACKERS,
                "P1", false);
        Arrived arrived = sessionFor(p, "rg03-unscripted");
        JsonObject before = arrived.session().pendingDecisionPayload()
                .getAsJsonObject("decision").deepCopy();
        XmageTemporalProgressionDriver.ProgressionException failure = assertThrows(
                XmageTemporalProgressionDriver.ProgressionException.class,
                () -> XmageTemporalProgressionDriver.driveToPlanTarget(
                        arrived.session(), arrived.seats(), p,
                        (pending, legal, index) -> null,
                        80));
        assertTrue(failure.getMessage().startsWith("UNSCRIPTED_DECISION"));
        JsonObject after = arrived.session().pendingDecisionPayload()
                .getAsJsonObject("decision");
        assertEquals(before.get("decision_id").getAsString(),
                after.get("decision_id").getAsString());
    }

    @Test
    void laterTurnAndUnqualifiedStepsRemainFailClosed() {
        XmageNativeStateRestoration.Plan later = new XmageNativeStateRestoration.Plan(
                "rg03-turn2", 2, SEED,
                List.of(
                        new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Rograkh, Son of Rohgahh", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0)),
                List.of(), List.of(),
                2, TurnPhase.PRECOMBAT_MAIN, PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageNativeStateRestoration.RestorationException failure = assertThrows(
                XmageNativeStateRestoration.RestorationException.class,
                () -> XmageNativeStateRestorationTest.restorationFor(later));
        assertTrue(failure.getMessage().startsWith("UNSUPPORTED_TEMPORAL_POINT"));
    }

    /**
     * Explicit test script. It selects only semantically named offered options:
     * keep, starting-player self, pass, a named attack to P2, hold, and an
     * explicitly empty blocker selection. There is no first/random/default.
     */
    private static XmageTemporalProgressionDriver.DecisionSource transport(
            Map<String, Player> seats,
            boolean attackP2,
            boolean declineBlocks
    ) {
        AtomicBoolean attacked = new AtomicBoolean(false);
        return (pending, legal, decisionIndex) -> {
            String decisionClass = pending.get("decision_class").getAsString();
            String actor = legal.get("actor_id").getAsString();
            if ("mulligan".equals(decisionClass)) {
                return proposal("rg03-keep-" + decisionIndex, actor,
                        exactOption(legal, "mulligan", "keep", null, null));
            }
            if ("choose_object".equals(decisionClass)
                    && pending.has("prompt")
                    && pending.get("prompt").getAsString().contains("starting player")) {
                JsonObject self = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    if (action.get("action_id").getAsString().endsWith(":" + actor)) {
                        if (self != null) {
                            throw new AssertionError("multiple starting-player self options");
                        }
                        self = action;
                    }
                }
                if (self == null) {
                    throw new AssertionError("starting-player self option missing");
                }
                return proposal("rg03-start-" + decisionIndex, actor, self);
            }
            if ("priority".equals(decisionClass)) {
                return proposal("rg03-pass-" + decisionIndex, actor,
                        exactOption(legal, "pass_priority", null, null, null));
            }
            if ("declare_attacker".equals(decisionClass)) {
                if (attackP2 && !attacked.get()) {
                    JsonObject attack = exactOption(
                            legal, "declare_attackers", "declare_attacker",
                            "Grizzly Bears", seats.get("P2").getId().toString());
                    attacked.set(true);
                    return proposal("rg03-attack-" + decisionIndex, actor, attack);
                }
                return proposal("rg03-hold-" + decisionIndex, actor,
                        exactOption(legal, "declare_attackers", "hold_attacker",
                                "Grizzly Bears", null));
            }
            if ("declare_blocker".equals(decisionClass) && declineBlocks) {
                return emptySelectionProposal(
                        "rg03-no-block-" + decisionIndex, actor, "structural_decision");
            }
            return null;
        };
    }

    private static JsonObject exactOption(
            JsonObject legal,
            String actionType,
            String optionType,
            String objectName,
            String defenderId
    ) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!actionType.equals(action.get("action_type").getAsString())) {
                continue;
            }
            JsonObject metadata = action.getAsJsonObject("metadata");
            if (optionType != null
                    && !optionType.equals(metadata.get("option_type").getAsString())) {
                continue;
            }
            JsonObject nativeMeta = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
            if (objectName != null) {
                String name = nativeMeta.has("name")
                        ? nativeMeta.get("name").getAsString() : "";
                if (!objectName.equals(name)) {
                    continue;
                }
            }
            if (defenderId != null) {
                String actual = nativeMeta.has("defender_id")
                        ? nativeMeta.get("defender_id").getAsString() : "";
                if (!defenderId.equals(actual)) {
                    continue;
                }
            }
            matches.add(action);
        }
        if (matches.size() != 1) {
            throw new AssertionError("expected exact one offered action, observed "
                    + matches.size() + " for " + actionType + "/" + optionType
                    + "/" + objectName + "/" + defenderId);
        }
        return matches.get(0);
    }

    private static JsonObject proposal(
            String proposalId,
            String actor,
            JsonObject action
    ) {
        return XmageFullGameTaxExecutionTest.genericProposal(
                proposalId,
                actor,
                action.get("action_id").getAsString(),
                action.get("action_type").getAsString());
    }

    private static JsonObject emptySelectionProposal(
            String proposalId,
            String actor,
            String actionType
    ) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        proposal.addProperty("actor_id", actor);
        proposal.add("legal_action_id", JsonNull.INSTANCE);
        proposal.addProperty("action_type", actionType);
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("selected_option_ids", new JsonArray());
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "rg03-explicit-temporal-script");
        return proposal;
    }

    private record TargetCase(
            TurnPhase phase,
            PhaseStep step,
            String priority
    ) {
    }

    private record Arrived(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats
    ) {
    }
}
