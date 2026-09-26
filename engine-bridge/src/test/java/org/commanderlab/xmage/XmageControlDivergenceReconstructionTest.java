package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.CommanderCardType;
import mage.constants.PhaseStep;
import mage.constants.TurnPhase;
import mage.constants.Zone;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** RG-04 actual-card control-divergence qualification. */
class XmageControlDivergenceReconstructionTest {

    private static final long SEED = 424242L;

    @Test
    void persistentControlMagicAndControllerLeaveCleanupAreNative() {
        Arrived arrived = arrive(plan(
                "rg04-control-magic", 3,
                List.of(
                        object("target", "Grizzly Bears", "P1", Zone.BATTLEFIELD),
                        object("control", "Control Magic", "P2", Zone.HAND),
                        island("u1", "P2"), island("u2", "P2"),
                        island("u3", "P2"), island("u4", "P2"))));
        UUID target = arrived.restoration().injectedObjectId("target");
        cast(arrived, "P2", "control", List.of(target), List.of("u1","u2","u3","u4"), "blue");
        XmageControlDivergenceReconstruction.requireOwnerController(
                arrived.session(), target,
                arrived.seats().get("P1").getId(), arrived.seats().get("P2").getId());

        // Native leave cleanup removes P2-owned Control Magic; P1-owned target remains.
        arrived.session().submitConcede(concede(arrived.seats().get("P2").getId().toString()));
        Permanent bear = arrived.session().restorationGame().getPermanent(target);
        assertNotNull(bear);
        assertEquals(arrived.seats().get("P1").getId(), bear.getControllerId());
        assertFalse(hasPermanentOwnedBy(arrived, "P2", "Control Magic"));
    }

    @Test
    void ownerLeavingRemovesOwnedPermanentEvenWhenOpponentControlsIt() {
        Arrived arrived = arrive(plan(
                "rg04-owner-leaves", 3,
                List.of(
                        object("target", "Grizzly Bears", "P1", Zone.BATTLEFIELD),
                        object("control", "Control Magic", "P2", Zone.HAND),
                        island("u1", "P2"), island("u2", "P2"),
                        island("u3", "P2"), island("u4", "P2"))));
        UUID target = arrived.restoration().injectedObjectId("target");
        cast(arrived, "P2", "control", List.of(target), List.of("u1","u2","u3","u4"), "blue");
        arrived.session().submitConcede(concede(arrived.seats().get("P1").getId().toString()));
        assertTrue(arrived.session().restorationGame().getPermanent(target) == null,
                "owner leave must remove owned permanent despite foreign controller");
    }

    @Test
    void temporaryActOfTreasonExpiresThroughNativeCleanup() {
        Arrived arrived = arrive(plan(
                "rg04-temp", 3,
                List.of(
                        object("target", "Grizzly Bears", "P1", Zone.BATTLEFIELD),
                        object("act", "Act of Treason", "P2", Zone.HAND),
                        mountain("r1","P2"), mountain("r2","P2"), mountain("r3","P2"))));
        UUID target = arrived.restoration().injectedObjectId("target");
        cast(arrived, "P2", "act", List.of(target), List.of("r1","r2","r3"), "red");
        XmageControlDivergenceReconstruction.requireOwnerController(
                arrived.session(), target,
                arrived.seats().get("P1").getId(), arrived.seats().get("P2").getId());

        XmageTemporalProgressionDriver.driveUntil(
                arrived.session(), arrived.seats(),
                (session, seats, observed) -> observed.get("turn_number").getAsInt() >= 2,
                neutral(), 260);
        XmageControlDivergenceReconstruction.requireOwnerController(
                arrived.session(), target,
                arrived.seats().get("P1").getId(), arrived.seats().get("P1").getId());
    }

    @Test
    void overlappingControlEffectsUseNativeTimestampAndRevert() {
        Arrived arrived = arrive(plan(
                "rg04-overlap", 3,
                List.of(
                        object("target", "Grizzly Bears", "P1", Zone.BATTLEFIELD),
                        object("c2", "Control Magic", "P2", Zone.HAND),
                        island("p2u1","P2"), island("p2u2","P2"),
                        island("p2u3","P2"), island("p2u4","P2"),
                        object("c3", "Control Magic", "P3", Zone.HAND),
                        island("p3u1","P3"), island("p3u2","P3"),
                        island("p3u3","P3"), island("p3u4","P3"))));
        UUID target = arrived.restoration().injectedObjectId("target");
        cast(arrived, "P2", "c2", List.of(target),
                List.of("p2u1","p2u2","p2u3","p2u4"), "blue");
        cast(arrived, "P3", "c3", List.of(target),
                List.of("p3u1","p3u2","p3u3","p3u4"), "blue");
        assertEquals(arrived.seats().get("P3").getId(),
                arrived.session().restorationGame().getPermanent(target).getControllerId());

        // P3 leaves: newest P3-owned Aura leaves and the older P2 control effect resumes.
        arrived.session().submitConcede(concede(arrived.seats().get("P3").getId().toString()));
        assertEquals(arrived.seats().get("P2").getId(),
                arrived.session().restorationGame().getPermanent(target).getControllerId());
    }

    @Test
    void switcherooExchangesControllersThroughRealSpell() {
        Arrived arrived = arrive(plan(
                "rg04-exchange", 3,
                List.of(
                        object("p1", "Grizzly Bears", "P1", Zone.BATTLEFIELD),
                        object("p2", "Runeclaw Bear", "P2", Zone.BATTLEFIELD),
                        object("switch", "Switcheroo", "P2", Zone.HAND),
                        island("u1","P2"), island("u2","P2"), island("u3","P2"),
                        island("u4","P2"), island("u5","P2"))));
        UUID p1 = arrived.restoration().injectedObjectId("p1");
        UUID p2 = arrived.restoration().injectedObjectId("p2");
        cast(arrived, "P2", "switch", List.of(p1, p2),
                List.of("u1","u2","u3","u4","u5"), "blue");
        assertEquals(arrived.seats().get("P2").getId(),
                arrived.session().restorationGame().getPermanent(p1).getControllerId());
        assertEquals(arrived.seats().get("P1").getId(),
                arrived.session().restorationGame().getPermanent(p2).getControllerId());
    }

    @Test
    void stolenCommanderKeepsNativeCommanderIdentityAndDamageWatcher() {
        Arrived arrived = arrive(plan(
                "rg04-commander", 4,
                List.of(
                        object("act", "Act of Treason", "P3", Zone.HAND),
                        mountain("r1","P3"), mountain("r2","P3"), mountain("r3","P3"))));
        // Cast the genuine P1 Commander (zero mana) before stealing it.
        XmageFullGameTaxExecutionTest.submit(
                arrived.session(), "rg04-cmd-cast",
                XmageFullGameTaxExecutionTest.castOffer(
                        arrived.session().legalActionsPayload(), "Rograkh, Son of Rohgahh"));
        XmageExternalRiskSignalTest.resolveStackEmpty(arrived.session(), "rg04-cmd-resolve");
        UUID commander = arrived.session().restorationGame()
                .getCommandersIds(arrived.seats().get("P1"),
                        CommanderCardType.ANY, false).iterator().next();
        assertNotNull(arrived.session().restorationGame().getPermanent(commander));

        cast(arrived, "P3", "act", List.of(commander),
                List.of("r1","r2","r3"), "red");
        Permanent permanent = arrived.session().restorationGame().getPermanent(commander);
        assertEquals(arrived.seats().get("P1").getId(), permanent.getOwnerId());
        assertEquals(arrived.seats().get("P3").getId(), permanent.getControllerId());
        assertNotNull(arrived.session().restorationGame().getState()
                .getWatcher(mage.watchers.common.CommanderInfoWatcher.class, commander));
    }

    @Test
    void zoneChangeClearsControlEffectUsingNormalObjectSemantics() {
        Arrived arrived = arrive(plan(
                "rg04-zone", 3,
                List.of(
                        object("target", "Grizzly Bears", "P1", Zone.BATTLEFIELD),
                        object("control", "Control Magic", "P2", Zone.HAND),
                        island("u1","P2"), island("u2","P2"), island("u3","P2"),
                        island("u4","P2"), island("uns","P2"),
                        object("unsummon", "Unsummon", "P2", Zone.HAND))));
        UUID target = arrived.restoration().injectedObjectId("target");
        cast(arrived, "P2", "control", List.of(target),
                List.of("u1","u2","u3","u4"), "blue");
        cast(arrived, "P2", "unsummon", List.of(target), List.of("uns"), "blue");
        assertTrue(arrived.session().restorationGame().getPermanent(target) == null);
        assertTrue(arrived.seats().get("P1").getHand().contains(target),
                "zone change returns controlled card to owner's hand");
    }

    private static Arrived arrive(XmageNativeStateRestoration.Plan plan) {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, plan.planId());
        XmageFullGameSession session = new XmageFullGameSession(
                plan.planId(), handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new Arrived(session, restoration, seats);
    }

    private static XmageNativeStateRestoration.Plan plan(
            String id, int count, List<XmageNativeStateRestoration.RequestedObject> objects) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int i = 1; i <= count; i++) {
            String pid = "P" + i;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, i, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", "Rograkh, Son of Rohgahh", pid, 0));
        }
        return new XmageNativeStateRestoration.Plan(
                id, count, SEED, players, commanders, List.of(), objects,
                1, TurnPhase.PRECOMBAT_MAIN, PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
    }

    private static XmageNativeStateRestoration.RequestedObject object(
            String id, String name, String owner, Zone zone) {
        return new XmageNativeStateRestoration.RequestedObject(
                id, name, owner, owner, zone, false);
    }

    private static XmageNativeStateRestoration.RequestedObject island(String id, String owner) {
        return object(id, "Island", owner, Zone.BATTLEFIELD);
    }

    private static XmageNativeStateRestoration.RequestedObject mountain(String id, String owner) {
        return object(id, "Mountain", owner, Zone.BATTLEFIELD);
    }

    private static void cast(
            Arrived arrived,
            String actor,
            String sourceSemanticId,
            List<UUID> targets,
            List<String> manaSemanticIds,
            String manaType
    ) {
        advanceToOwnPrecombatMain(arrived, actor);
        List<UUID> manaIds = manaSemanticIds.stream()
                .map(arrived.restoration()::injectedObjectId).toList();
        XmageControlDivergenceReconstruction.castAndResolve(
                arrived.session(), arrived.seats(), actor,
                arrived.restoration().injectedObjectId(sourceSemanticId),
                new Script(targets, manaIds, manaType),
                80);
    }

    private static void advanceToOwnPrecombatMain(Arrived arrived, String actor) {
        JsonObject now = XmageNativeStateRestoration.readback(
                arrived.session().restorationGame(), arrived.seats());
        if (actor.equals(now.get("active_player").getAsString())
                && "PRECOMBAT_MAIN".equals(now.get("phase").getAsString())
                && "PRECOMBAT_MAIN".equals(now.get("step").getAsString())
                && actor.equals(now.get("priority_player").getAsString())) {
            return;
        }
        XmageTemporalProgressionDriver.driveUntil(
                arrived.session(),
                arrived.seats(),
                (session, seats, observed) ->
                        actor.equals(observed.get("active_player").getAsString())
                                && "PRECOMBAT_MAIN".equals(observed.get("phase").getAsString())
                                && "PRECOMBAT_MAIN".equals(observed.get("step").getAsString())
                                && actor.equals(observed.get("priority_player").getAsString()),
                progressionScript(),
                520);
    }

    private static XmageTemporalProgressionDriver.DecisionSource progressionScript() {
        return (pending, legal, index) -> {
            String dc = pending.get("decision_class").getAsString();
            if ("priority".equals(dc)) {
                return proposal("rg04-progress-pass-" + index, legal,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "pass_priority", null));
            }
            if ("declare_attacker".equals(dc)) {
                return proposal("rg04-progress-hold-" + index, legal,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "declare_attackers", "hold_attacker"));
            }
            if ("declare_blocker".equals(dc)) {
                JsonObject p = XmageFullGameTaxExecutionTest.genericProposal(
                        "rg04-progress-no-block-" + index,
                        legal.get("actor_id").getAsString(), "", "structural_decision");
                p.add("legal_action_id", com.google.gson.JsonNull.INSTANCE);
                return p;
            }
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
                String chosenKey = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    JsonObject nativeMeta = nativeMeta(action);
                    if (!nativeMeta.has("name") || !nativeMeta.has("zone_index")) {
                        continue;
                    }
                    String key = nativeMeta.get("name").getAsString()
                            + "|" + nativeMeta.get("zone_index").getAsInt();
                    if (chosen == null || key.compareTo(chosenKey) > 0) {
                        chosen = action;
                        chosenKey = key;
                    } else if (key.equals(chosenKey)) {
                        throw new AssertionError(
                                "cleanup discard semantic key is ambiguous: " + key);
                    }
                }
                if (chosen == null) {
                    throw new AssertionError(
                            "cleanup discard exposed no semantically keyed option");
                }
                return proposal("rg04-progress-discard-" + index, legal, chosen);
            }
            return null;
        };
    }

    private static final class Script
            implements XmageControlDivergenceReconstruction.DecisionSource {
        private final List<UUID> targets;
        private final List<UUID> manaSources;
        private final String manaType;
        private int targetIndex;
        private int manaIndex;

        Script(List<UUID> targets, List<UUID> manaSources, String manaType) {
            this.targets = List.copyOf(targets);
            this.manaSources = List.copyOf(manaSources);
            this.manaType = manaType;
        }

        @Override
        public JsonObject choose(JsonObject pending, JsonObject legal, int decisionIndex) {
            String dc = pending.get("decision_class").getAsString();
            if ("target".equals(dc)) {
                if (targetIndex >= targets.size()) {
                    throw new AssertionError("unexpected extra target decision");
                }
                UUID wanted = targets.get(targetIndex++);
                JsonObject match = exactNativeObject(legal, wanted);
                return proposal("rg04-target-" + decisionIndex, legal, match);
            }
            if ("mana_payment".equals(dc)) {
                JsonObject pool = exactManaPoolIfPresent(legal, manaType);
                if (pool != null) {
                    return proposal("rg04-pool-" + decisionIndex, legal, pool);
                }
                if (manaIndex >= manaSources.size()) {
                    throw new AssertionError("insufficient scripted mana sources");
                }
                JsonObject ability = exactManaSource(legal, manaSources.get(manaIndex++));
                return proposal("rg04-mana-" + decisionIndex, legal, ability);
            }
            return null;
        }
    }

    private static JsonObject exactNativeObject(JsonObject legal, UUID wanted) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement e : legal.getAsJsonArray("actions")) {
            JsonObject action = e.getAsJsonObject();
            JsonObject meta = nativeMeta(action);
            if (wanted.toString().equals(text(meta, "object_id"))) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "exact target option");
        return matches.get(0);
    }

    private static JsonObject exactManaSource(JsonObject legal, UUID wanted) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement e : legal.getAsJsonArray("actions")) {
            JsonObject action = e.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            if (!"mana_ability".equals(text(metadata, "option_type"))) {
                continue;
            }
            if (wanted.toString().equals(text(nativeMeta(action), "source_object_id"))) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "exact scripted mana source");
        return matches.get(0);
    }

    private static JsonObject exactManaPoolIfPresent(JsonObject legal, String manaType) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement e : legal.getAsJsonArray("actions")) {
            JsonObject action = e.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            if (!"mana_pool".equals(text(metadata, "option_type"))) {
                continue;
            }
            if (manaType.equalsIgnoreCase(text(nativeMeta(action), "mana_type"))) {
                matches.add(action);
            }
        }
        return matches.size() == 1 ? matches.get(0) : null;
    }

    private static JsonObject nativeMeta(JsonObject action) {
        JsonObject metadata = action.getAsJsonObject("metadata");
        return metadata != null && metadata.has("xmage_option_metadata")
                && metadata.get("xmage_option_metadata").isJsonObject()
                ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
    }

    private static String text(JsonObject object, String key) {
        return object != null && object.has(key) && !object.get(key).isJsonNull()
                ? object.get(key).getAsString() : "";
    }

    private static JsonObject proposal(String id, JsonObject legal, JsonObject action) {
        return XmageCausalStackReconstruction.proposal(
                id, legal.get("actor_id").getAsString(), action);
    }

    private static XmageTemporalProgressionDriver.DecisionSource neutral() {
        return (pending, legal, index) -> {
            String dc = pending.get("decision_class").getAsString();
            if ("priority".equals(dc)) {
                return proposal("rg04-pass-" + index, legal,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "pass_priority", null));
            }
            if ("declare_attacker".equals(dc)) {
                return proposal("rg04-hold-" + index, legal,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "declare_attackers", "hold_attacker"));
            }
            if ("declare_blocker".equals(dc)) {
                JsonObject p = XmageFullGameTaxExecutionTest.genericProposal(
                        "rg04-no-block-" + index,
                        legal.get("actor_id").getAsString(), "", "structural_decision");
                p.add("legal_action_id", com.google.gson.JsonNull.INSTANCE);
                return p;
            }
            return null;
        };
    }

    private static JsonObject concede(String actor) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "rg04-concede-" + actor.substring(0, 8));
        proposal.addProperty("actor_id", actor);
        proposal.addProperty("action_type", "concede");
        proposal.add("legal_action_id", com.google.gson.JsonNull.INSTANCE);
        proposal.add("target_ids", new com.google.gson.JsonArray());
        proposal.add("selected_modes", new com.google.gson.JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new com.google.gson.JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "rg04-native-leave-cleanup");
        return proposal;
    }

    private static boolean hasPermanentOwnedBy(Arrived arrived, String pid, String name) {
        UUID owner = arrived.seats().get(pid).getId();
        for (Permanent p : arrived.session().restorationGame().getBattlefield().getAllPermanents()) {
            if (owner.equals(p.getOwnerId()) && name.equals(p.getName())) {
                return true;
            }
        }
        return false;
    }

    private record Arrived(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats
    ) {}
}
