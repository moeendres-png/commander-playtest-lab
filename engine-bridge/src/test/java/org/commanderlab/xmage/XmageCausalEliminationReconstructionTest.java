package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.constants.TurnPhase;
import mage.constants.Zone;
import mage.counters.Counter;
import mage.counters.CounterType;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * RG-05: causal multiplayer elimination. Loss is caused by real native card
 * transactions; no player lost/left flag or terminal result is injected.
 */
class XmageCausalEliminationReconstructionTest {

    private static final long SEED = 424242L;

    @Test
    void lethalBoltCausesNativeThreePlayerLossAndOwnedObjectCleanup() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-owned-3", 3, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("leave-owned", "Sol Ring", "P2", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);

        XmageCausalEliminationReconstruction.Result result =
                eliminateWithSpell(
                        arrived, "P1", "P2", "bolt",
                        List.of(arrived.seats().get("P2").getId()),
                        List.of("red"), "red");

        assertEquals(Set.of("P1", "P3"), result.survivingPlayers());
        assertTrue(arrived.seats().get("P2").hasLost() || arrived.seats().get("P2").hasLeft());
        assertNull(arrived.session().restorationGame().getPermanent(
                arrived.restoration().injectedObjectId("leave-owned")),
                "object owned by eliminated P2 must leave the battlefield");
        for (Permanent permanent
                : arrived.session().restorationGame().getBattlefield().getAllPermanents()) {
            assertNotEquals(arrived.seats().get("P2").getId(), permanent.getOwnerId(),
                    "no P2-owned permanent may remain after native cleanup");
        }
    }

    @Test
    void priorityRingExcludesEliminatedPlayerAndSurvivorContinues() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-priority-3", 3, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);

        eliminateWithSpell(
                arrived, "P1", "P2", "bolt",
                List.of(arrived.seats().get("P2").getId()),
                List.of("red"), "red");

        JsonObject pending = arrived.session().pendingDecisionPayload();
        assertFalse(pending.get("decision").isJsonNull());
        String nativeActor =
                pending.getAsJsonObject("decision").get("actor_id").getAsString();
        assertNotEquals(arrived.seats().get("P2").getId().toString(), nativeActor,
                "eliminated P2 must never receive priority again");

        JsonObject legal = arrived.session().legalActionsPayload();
        assertEquals(nativeActor, legal.get("actor_id").getAsString());
        assertFalse(legal.getAsJsonArray("actions").isEmpty(),
                "a surviving player must continue with an authoritative offer");
    }

    @Test
    void activePlayerSelfLossEndsItsTurnAndNextLivePlayerBecomesActive() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-active-turn-3", 3, 2,
                List.of(
                        object("sign", "Sign in Blood", "P2", Zone.HAND),
                        object("b1", "Swamp", "P2", Zone.BATTLEFIELD),
                        object("b2", "Swamp", "P2", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 2);

        advanceToOwnPrecombatMain(arrived, "P2");
        assertEquals("P2", XmageNativeStateRestoration.readback(
                arrived.session().restorationGame(), arrived.seats())
                .get("active_player").getAsString());

        XmageCausalEliminationReconstruction.Result result =
                eliminateWithSpell(
                        arrived, "P2", "P2", "sign",
                        List.of(arrived.seats().get("P2").getId()),
                        List.of("b1", "b2"), "black");
        assertEquals(Set.of("P1", "P3"), result.survivingPlayers());

        XmageTemporalProgressionDriver.driveUntil(
                arrived.session(),
                arrived.seats(),
                (session, seats, observed) ->
                        "P3".equals(observed.get("active_player").getAsString())
                                && "PRECOMBAT_MAIN".equals(observed.get("phase").getAsString())
                                && "PRECOMBAT_MAIN".equals(observed.get("step").getAsString()),
                progressionScript(),
                520);
        JsonObject observed = XmageNativeStateRestoration.readback(
                arrived.session().restorationGame(), arrived.seats());
        assertEquals("P3", observed.get("active_player").getAsString());
        assertNotEquals("P2", observed.get("priority_player").getAsString());
    }

    @Test
    void fivePlayerLiveRingExcludesEliminatedMiddleSeat() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-five", 5, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);

        XmageCausalEliminationReconstruction.Result result =
                eliminateWithSpell(
                        arrived, "P1", "P3", "bolt",
                        List.of(arrived.seats().get("P3").getId()),
                        List.of("red"), "red");
        assertEquals(Set.of("P1", "P2", "P4", "P5"), result.survivingPlayers());
        assertTrue(arrived.seats().get("P3").hasLost() || arrived.seats().get("P3").hasLeft());

        JsonObject pending = arrived.session().pendingDecisionPayload();
        if (!pending.get("decision").isJsonNull()) {
            String actor = pending.getAsJsonObject("decision").get("actor_id").getAsString();
            assertNotEquals(arrived.seats().get("P3").getId().toString(), actor);
        }
    }

    @Test
    void sameSeedFreshSessionsReproduceEliminationAndSurvivorSet() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-replay", 3, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("owned", "Sol Ring", "P2", Zone.BATTLEFIELD)));
        Arrived first = arrive(plan, 3);
        Arrived second = arrive(plan, 3);

        XmageCausalEliminationReconstruction.Result a =
                eliminateWithSpell(first, "P1", "P2", "bolt",
                        List.of(first.seats().get("P2").getId()),
                        List.of("red"), "red");
        XmageCausalEliminationReconstruction.Result b =
                eliminateWithSpell(second, "P1", "P2", "bolt",
                        List.of(second.seats().get("P2").getId()),
                        List.of("red"), "red");

        assertEquals(a.survivingPlayers(), b.survivingPlayers());
        assertEquals(a.eliminatedPlayer(), b.eliminatedPlayer());
        assertEquals(first.seats().get("P2").hasLost(), second.seats().get("P2").hasLost());
        assertNull(first.session().restorationGame()
                .getPermanent(first.restoration().injectedObjectId("owned")));
        assertNull(second.session().restorationGame()
                .getPermanent(second.restoration().injectedObjectId("owned")));
    }


    @Test
    void worshipReplacementPreventsLethalDamageWithoutFabricatedPrevention() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-worship", 3, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("worship", "Worship", "P2", Zone.BATTLEFIELD),
                        object("worship-creature", "Grizzly Bears", "P2", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);

        castSpell(
                arrived, "P1", "bolt",
                List.of(arrived.seats().get("P2").getId()),
                List.of("red"), "red");

        assertEquals(1, arrived.seats().get("P2").getLife(),
                "Worship must replace lethal damage with a life total of 1");
        assertFalse(arrived.seats().get("P2").hasLost());
    }

    @Test
    void platinumAngelCanPreventLossUntilActualAngelRemoval() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-cant-lose", 3, 3,
                List.of(
                        object("bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("red", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("doom", "Doom Blade", "P1", Zone.HAND),
                        object("black1", "Swamp", "P1", Zone.BATTLEFIELD),
                        object("black2", "Swamp", "P1", Zone.BATTLEFIELD),
                        object("angel", "Platinum Angel", "P2", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 3);

        castSpell(
                arrived, "P1", "bolt",
                List.of(arrived.seats().get("P2").getId()),
                List.of("red"), "red");
        assertEquals(0, arrived.seats().get("P2").getLife());
        assertFalse(arrived.seats().get("P2").hasLost(),
                "Platinum Angel must keep its controller in the game at 0 life");

        castSpell(
                arrived, "P1", "doom",
                List.of(arrived.restoration().injectedObjectId("angel")),
                List.of("black1", "black2"), "black");
        XmageNativeStateRestoration.revalidate(arrived.session().restorationGame());
        assertTrue(arrived.seats().get("P2").hasLost() || arrived.seats().get("P2").hasLeft(),
                "after native removal of Platinum Angel, native SBA must eliminate P2");
    }

    @Test
    void emptyLibraryPlusActualDrawCausesNativeDeckOut() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-deckout", 3, 40,
                List.of(
                        object("sign", "Sign in Blood", "P1", Zone.HAND),
                        object("b1", "Swamp", "P1", Zone.BATTLEFIELD),
                        object("b2", "Swamp", "P1", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 40);
        arrived.session().restorationGame().cheat(
                arrived.seats().get("P2").getId(),
                Map.of(Zone.LIBRARY, "clear"));
        assertEquals(0, arrived.seats().get("P2").getLibrary().size());

        castSpell(
                arrived, "P1", "sign",
                List.of(arrived.seats().get("P2").getId()),
                List.of("b1", "b2"), "black");
        XmageNativeStateRestoration.revalidate(arrived.session().restorationGame());

        assertTrue(arrived.seats().get("P2").hasLost() || arrived.seats().get("P2").hasLeft(),
                "attempting to draw from an empty library must cause native loss");
    }

    @Test
    void ninePoisonPlusActualPrologueCausesNativePoisonLoss() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-poison", 3, 40,
                List.of(
                        object("prologue", "Prologue to Phyresis", "P1", Zone.HAND),
                        object("u1", "Island", "P1", Zone.BATTLEFIELD),
                        object("u2", "Island", "P1", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 40);
        Player victim = arrived.seats().get("P2");
        boolean added = victim.addCounters(
                new Counter(CounterType.POISON.getName(), 9),
                arrived.seats().get("P1").getId(),
                null,
                arrived.session().restorationGame());
        assertTrue(added);
        assertEquals(9, victim.getCountersCount(CounterType.POISON));
        XmageNativeStateRestoration.revalidate(arrived.session().restorationGame());
        assertFalse(victim.hasLost());

        castSpell(
                arrived, "P1", "prologue", List.of(),
                List.of("u1", "u2"), "blue");
        XmageNativeStateRestoration.revalidate(arrived.session().restorationGame());

        assertEquals(10, victim.getCountersCount(CounterType.POISON));
        assertTrue(victim.hasLost() || victim.hasLeft());
    }

    @Test
    void flameRiftEliminatesThreeOpponentsSimultaneouslyAndProducesWinnerInFourPlayer() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-simultaneous-winner", 4, 4,
                List.of(
                        object("rift", "Flame Rift", "P1", Zone.HAND),
                        object("r1", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("r2", "Mountain", "P1", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 4);
        arrived.seats().get("P1").setLife(8, arrived.session().restorationGame(), null);
        XmageNativeStateRestoration.revalidate(arrived.session().restorationGame());

        castSpell(arrived, "P1", "rift", List.of(), List.of("r1", "r2"), "red");
        XmageNativeStateRestoration.revalidate(arrived.session().restorationGame());

        assertFalse(arrived.seats().get("P1").hasLost());
        assertEquals(4, arrived.seats().get("P1").getLife());
        for (String pid : List.of("P2", "P3", "P4")) {
            assertTrue(arrived.seats().get(pid).hasLost() || arrived.seats().get(pid).hasLeft(),
                    pid + " must be eliminated by the same resolving Flame Rift");
        }
        assertTrue(arrived.seats().get("P1").hasWon(),
                "sole surviving player must receive the native winner state");
    }

    @Test
    void flameRiftCanProduceNativeDrawWhenAllPlayersLoseSimultaneously() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg05-simultaneous-draw", 3, 4,
                List.of(
                        object("rift", "Flame Rift", "P1", Zone.HAND),
                        object("r1", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("r2", "Mountain", "P1", Zone.BATTLEFIELD)));
        Arrived arrived = arrive(plan, 4);

        castSpell(arrived, "P1", "rift", List.of(), List.of("r1", "r2"), "red");
        XmageNativeStateRestoration.revalidate(arrived.session().restorationGame());

        for (String pid : List.of("P1", "P2", "P3")) {
            assertTrue(arrived.seats().get(pid).hasLost() || arrived.seats().get(pid).hasLeft(),
                    pid + " must lose in the simultaneous native SBA batch");
            assertFalse(arrived.seats().get(pid).hasWon());
        }
    }

    private static XmageControlDivergenceReconstruction.Result castSpell(
            Arrived arrived,
            String actor,
            String sourceSemanticId,
            List<UUID> targets,
            List<String> manaSemanticIds,
            String manaType
    ) {
        List<UUID> manaIds = manaSemanticIds.stream()
                .map(arrived.restoration()::injectedObjectId)
                .toList();
        return XmageControlDivergenceReconstruction.castAndResolve(
                arrived.session(),
                arrived.seats(),
                actor,
                arrived.restoration().injectedObjectId(sourceSemanticId),
                new Script(targets, manaIds, manaType),
                180);
    }

    private static XmageCausalEliminationReconstruction.Result eliminateWithSpell(
            Arrived arrived,
            String actor,
            String victim,
            String sourceSemanticId,
            List<UUID> targets,
            List<String> manaSemanticIds,
            String manaType
    ) {
        List<UUID> manaIds = manaSemanticIds.stream()
                .map(arrived.restoration()::injectedObjectId)
                .toList();
        return XmageCausalEliminationReconstruction.castNativeCauseAndRequireElimination(
                arrived.session(),
                arrived.seats(),
                actor,
                victim,
                arrived.restoration().injectedObjectId(sourceSemanticId),
                new Script(targets, manaIds, manaType),
                120);
    }

    private static Arrived arrive(
            XmageNativeStateRestoration.Plan plan,
            int startingLife
    ) {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, plan.planId());
        XmageFullGameSession session = new XmageFullGameSession(
                plan.planId(), handles, 0, startingLife, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new Arrived(session, restoration, seats);
    }

    private static XmageNativeStateRestoration.Plan plan(
            String id,
            int count,
            int life,
            List<XmageNativeStateRestoration.RequestedObject> objects
    ) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int i = 1; i <= count; i++) {
            String pid = "P" + i;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, i, life));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", "Rograkh, Son of Rohgahh", pid, 0));
        }
        return new XmageNativeStateRestoration.Plan(
                id, count, SEED, players, commanders, List.of(), objects,
                1, TurnPhase.PRECOMBAT_MAIN, PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
    }

    private static XmageNativeStateRestoration.RequestedObject object(
            String id, String name, String owner, Zone zone
    ) {
        return new XmageNativeStateRestoration.RequestedObject(
                id, name, owner, owner, zone, false);
    }

    private static void advanceToOwnPrecombatMain(Arrived arrived, String actor) {
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
                return proposal("rg05-progress-pass-" + index, legal,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "pass_priority", null));
            }
            if ("declare_attacker".equals(dc)) {
                return proposal("rg05-progress-hold-" + index, legal,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "declare_attackers", "hold_attacker"));
            }
            if ("declare_blocker".equals(dc)) {
                JsonObject p = XmageFullGameTaxExecutionTest.genericProposal(
                        "rg05-progress-no-block-" + index,
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
                int required = pending.has("minimum_selections")
                        ? pending.get("minimum_selections").getAsInt() : 1;
                List<JsonObject> candidates = new ArrayList<>();
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    JsonObject nativeMeta = nativeMeta(action);
                    if (nativeMeta.has("name") && nativeMeta.has("zone_index")) {
                        candidates.add(action);
                    }
                }
                if (candidates.size() < required) {
                    throw new AssertionError("cleanup discard underflow");
                }
                return multiSelectProposal(
                        "rg05-discard-" + index,
                        legal,
                        candidates.subList(0, required),
                        "choose_targets");
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
                int required = pending.has("minimum_selections")
                        ? pending.get("minimum_selections").getAsInt() : 1;
                List<JsonObject> selected = new ArrayList<>();
                for (int i = 0; i < required; i++) {
                    if (targetIndex >= targets.size()) {
                        throw new AssertionError("scripted target underflow");
                    }
                    selected.add(exactNativeObject(legal, targets.get(targetIndex++)));
                }
                return multiSelectProposal(
                        "rg05-target-" + decisionIndex, legal, selected, "choose_targets");
            }
            if ("mana_payment".equals(dc)) {
                JsonObject pool = exactManaPoolIfPresent(legal, manaType);
                if (pool != null) {
                    return proposal("rg05-pool-" + decisionIndex, legal, pool);
                }
                if (manaIndex >= manaSources.size()) {
                    throw new AssertionError("scripted mana-source underflow");
                }
                return proposal(
                        "rg05-mana-" + decisionIndex,
                        legal,
                        exactManaSource(legal, manaSources.get(manaIndex++)));
            }
            return null;
        }
    }

    private static JsonObject exactNativeObject(JsonObject legal, UUID wanted) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement e : legal.getAsJsonArray("actions")) {
            JsonObject action = e.getAsJsonObject();
            if (wanted.toString().equals(text(nativeMeta(action), "object_id"))) {
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
            if ("mana_ability".equals(text(metadata, "option_type"))
                    && wanted.toString().equals(text(nativeMeta(action), "source_object_id"))) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "exact mana source");
        return matches.get(0);
    }

    private static JsonObject exactManaPoolIfPresent(JsonObject legal, String manaType) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement e : legal.getAsJsonArray("actions")) {
            JsonObject action = e.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            if ("mana_pool".equals(text(metadata, "option_type"))
                    && manaType.equalsIgnoreCase(text(nativeMeta(action), "mana_type"))) {
                matches.add(action);
            }
        }
        return matches.size() == 1 ? matches.get(0) : null;
    }

    private static JsonObject multiSelectProposal(
            String id,
            JsonObject legal,
            List<JsonObject> selected,
            String actionType
    ) {
        JsonObject proposal = XmageFullGameTaxExecutionTest.genericProposal(
                id,
                legal.get("actor_id").getAsString(),
                selected.get(0).get("action_id").getAsString(),
                actionType);
        com.google.gson.JsonArray optionIds = new com.google.gson.JsonArray();
        for (JsonObject action : selected) {
            String actionId = action.get("action_id").getAsString();
            int split = actionId.indexOf(':');
            optionIds.add(actionId.substring(split + 1));
        }
        proposal.getAsJsonObject("choices").add("selected_option_ids", optionIds);
        return proposal;
    }

    private static JsonObject nativeMeta(JsonObject action) {
        JsonObject metadata = action.has("metadata") && action.get("metadata").isJsonObject()
                ? action.getAsJsonObject("metadata") : new JsonObject();
        return metadata.has("xmage_option_metadata")
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

    private record Arrived(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats
    ) {
    }
}
