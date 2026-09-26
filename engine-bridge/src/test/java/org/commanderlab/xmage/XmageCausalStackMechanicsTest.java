package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.stack.Spell;
import mage.game.stack.StackObject;
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
import static org.junit.jupiter.api.Assertions.fail;

/**
 * RG-01 mechanism matrix. These cases do not snapshot-insert stack objects;
 * each stack object is created by the real XMage action that causes it.
 */
class XmageCausalStackMechanicsTest {

    private static final long SEED = 424242L;

    @Test
    void activatedAbilityIsCreatedByNativeActivationWithRealTargetAndSacrificeCost() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg01-activated", 3, List.of(
                        object("obj:bombardment", "Goblin Bombardment", "P1", Zone.BATTLEFIELD),
                        object("obj:sacrifice", "Grizzly Bears", "P1", Zone.BATTLEFIELD)));
        Live live = arrive(plan, "rg01-activated");

        UUID bombardmentId = live.restoration().injectedObjectId("obj:bombardment");
        UUID bearId = live.restoration().injectedObjectId("obj:sacrifice");
        JsonObject action = exactNonManaAbility(
                live.session().legalActionsPayload(), bombardmentId);
        submit(live.session(), "rg01-activate", action);

        boolean complete = false;
        for (int step = 0; step < 12; step++) {
            StackObject object = stackBySource(live, bombardmentId);
            JsonObject pending = live.session().pendingDecisionPayload()
                    .getAsJsonObject("decision");
            if (object != null && "priority".equals(
                    pending.get("decision_class").getAsString())) {
                complete = true;
                List<UUID> targets = targets(object);
                assertEquals(List.of(live.seats().get("P2").getId()), targets);
                break;
            }
            String dc = pending.get("decision_class").getAsString();
            if ("target".equals(dc)) {
                submit(live.session(), "rg01-act-target-" + step,
                        exactTarget(live.session().legalActionsPayload(),
                                live.seats().get("P2").getId()));
            } else if ("choose_object".equals(dc)) {
                submit(live.session(), "rg01-act-cost-" + step,
                        exactTarget(live.session().legalActionsPayload(), bearId));
            } else {
                fail("unexpected activation decision: " + dc);
            }
        }
        assertTrue(complete, "activated ability must complete onto the native stack");
        assertFalse(live.session().restorationGame().getBattlefield()
                        .containsPermanent(bearId),
                "real sacrifice cost removes the chosen creature");
    }

    @Test
    void triggeredAbilityAppearsAfterRealCreatureResolution() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg01-triggered", 3, List.of(
                        object("obj:warden", "Soul Warden", "P1", Zone.BATTLEFIELD),
                        object("obj:bears", "Grizzly Bears", "P1", Zone.HAND),
                        object("obj:f1", "Forest", "P1", Zone.BATTLEFIELD),
                        object("obj:f2", "Forest", "P1", Zone.BATTLEFIELD)));
        Live live = arrive(plan, "rg01-triggered");

        submit(live.session(), "rg01-cast-bears",
                XmageExternalRiskSignalTest.spellOffer(
                        live.session().legalActionsPayload(), "Grizzly Bears"));
        XmageFullGameDecisionExecutionTest.payHomogeneousMana(
                live.session(), "rg01-bears", "Forest — {T}: Add {G}.");

        StackObject trigger = null;
        for (int step = 0; step < 40; step++) {
            for (StackObject object : live.session().restorationGame().getStack()) {
                if ("Soul Warden".equals(object.getName())
                        && object.getStackAbility() != null
                        && object.getStackAbility().getAbilityType().name()
                                .toLowerCase().contains("trigger")) {
                    trigger = object;
                }
            }
            if (trigger != null) {
                break;
            }
            JsonObject pending = live.session().pendingDecisionPayload()
                    .getAsJsonObject("decision");
            if (!"priority".equals(pending.get("decision_class").getAsString())) {
                fail("unexpected decision before Soul Warden trigger: "
                        + pending.get("decision_class").getAsString());
            }
            submit(live.session(), "rg01-trigger-pass-" + step,
                    exactActionType(live.session().legalActionsPayload(), "pass_priority"));
        }
        assertNotNull(trigger, "real Soul Warden ETB trigger must reach the native stack");
    }

    @Test
    void flareOfDuplicationCreatesNativeCopiedSpell() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg01-copy", 3, List.of(
                        object("obj:bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("obj:flare", "Flare of Duplication", "P1", Zone.HAND),
                        object("obj:m1", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("obj:m2", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("obj:m3", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("obj:m4", "Mountain", "P1", Zone.BATTLEFIELD)));
        Live live = arrive(plan, "rg01-copy");

        submit(live.session(), "rg01-copy-bolt",
                XmageExternalRiskSignalTest.spellOffer(
                        live.session().legalActionsPayload(), "Lightning Bolt"));
        submit(live.session(), "rg01-copy-bolt-target",
                exactTarget(live.session().legalActionsPayload(),
                        live.seats().get("P2").getId()));
        XmageFullGameDecisionExecutionTest.payHomogeneousMana(
                live.session(), "rg01-copy-bolt", "Mountain — {T}: Add {R}.");

        StackObject bolt = stackBySource(
                live, live.restoration().injectedObjectId("obj:bolt"));
        assertNotNull(bolt);

        submit(live.session(), "rg01-copy-flare",
                XmageExternalRiskSignalTest.spellOffer(
                        live.session().legalActionsPayload(), "Flare of Duplication"));
        submit(live.session(), "rg01-copy-flare-target",
                exactTarget(live.session().legalActionsPayload(), bolt.getId()));
        XmageFullGameDecisionExecutionTest.payHomogeneousMana(
                live.session(), "rg01-copy-flare", "Mountain — {T}: Add {R}.");

        boolean copied = false;
        for (int step = 0; step < 50; step++) {
            int boltCount = 0;
            boolean anyCopy = false;
            for (StackObject object : live.session().restorationGame().getStack()) {
                if ("Lightning Bolt".equals(object.getName())) {
                    boltCount++;
                    anyCopy |= object.isCopy();
                }
            }
            if (boltCount >= 2 && anyCopy) {
                copied = true;
                break;
            }
            JsonObject pending = live.session().pendingDecisionPayload()
                    .getAsJsonObject("decision");
            String dc = pending.get("decision_class").getAsString();
            if ("priority".equals(dc)) {
                submit(live.session(), "rg01-copy-pass-" + step,
                        exactActionType(live.session().legalActionsPayload(), "pass_priority"));
            } else if ("choose_use".equals(dc)) {
                submit(live.session(), "rg01-copy-keep-targets-" + step,
                        exactLabel(live.session().legalActionsPayload(), "No"));
            } else {
                fail("unexpected copy decision: " + dc);
            }
        }
        assertTrue(copied, "Flare must create a real copied Bolt stack object");
    }

    @Test
    void morphCastCreatesNativeFaceDownSpell() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg01-facedown", 3, List.of(
                        object("obj:morph", "Sagu Mauler", "P1", Zone.HAND),
                        object("obj:m1", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("obj:m2", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("obj:m3", "Mountain", "P1", Zone.BATTLEFIELD)));
        Live live = arrive(plan, "rg01-facedown");

        List<JsonObject> offers =
                XmageExternalRiskSignalTest.spellOffers(
                        live.session().legalActionsPayload(), "Sagu Mauler");
        JsonObject morph = null;
        for (JsonObject offer : offers) {
            JsonObject engine = offer.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            int generic = engine.has("mana_cost_generic")
                    ? engine.get("mana_cost_generic").getAsInt() : -1;
            int green = engine.has("mana_cost_green")
                    ? engine.get("mana_cost_green").getAsInt() : 0;
            int blue = engine.has("mana_cost_blue")
                    ? engine.get("mana_cost_blue").getAsInt() : 0;
            if (generic == 3 && green == 0 && blue == 0) {
                assertTrue(morph == null, "unique {3} Morph cast offer");
                morph = offer;
            }
        }
        assertNotNull(morph, "engine must expose the Morph cast ability");
        submit(live.session(), "rg01-morph-cast", morph);
        XmageFullGameDecisionExecutionTest.payHomogeneousMana(
                live.session(), "rg01-morph-pay", "Mountain — {T}: Add {R}.");

        StackObject stack = stackBySource(
                live, live.restoration().injectedObjectId("obj:morph"));
        assertTrue(stack instanceof Spell);
        assertTrue(((Spell) stack).isFaceDown(live.session().restorationGame()));
        assertTrue(stack.getStackAbility().getSpellAbilityCastMode().isFaceDown());
    }

    @Test
    void targetLeavingMakesBoltFizzleThroughNativeResolution() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg01-fizzle", 3, List.of(
                        object("obj:bolt", "Lightning Bolt", "P1", Zone.HAND),
                        object("obj:p2-bears", "Grizzly Bears", "P2", Zone.BATTLEFIELD),
                        object("obj:unsummon", "Unsummon", "P2", Zone.HAND),
                        object("obj:red", "Mountain", "P1", Zone.BATTLEFIELD),
                        object("obj:blue", "Island", "P2", Zone.BATTLEFIELD)));
        Live live = arrive(plan, "rg01-fizzle");
        UUID bears = live.restoration().injectedObjectId("obj:p2-bears");

        submit(live.session(), "rg01-fizzle-bolt",
                XmageExternalRiskSignalTest.spellOffer(
                        live.session().legalActionsPayload(), "Lightning Bolt"));
        submit(live.session(), "rg01-fizzle-bolt-target",
                exactTarget(live.session().legalActionsPayload(), bears));
        XmageFullGameDecisionExecutionTest.payHomogeneousMana(
                live.session(), "rg01-fizzle-bolt", "Mountain — {T}: Add {R}.");

        XmageExternalRiskSignalTest.passToActor(
                live.session(), "rg01-fizzle", live.seats(), "P2");
        submit(live.session(), "rg01-fizzle-unsummon",
                XmageExternalRiskSignalTest.spellOffer(
                        live.session().legalActionsPayload(), "Unsummon"));
        submit(live.session(), "rg01-fizzle-unsummon-target",
                exactTarget(live.session().legalActionsPayload(), bears));
        XmageFullGameDecisionExecutionTest.payHomogeneousMana(
                live.session(), "rg01-fizzle-unsummon", "Island — {T}: Add {U}.");

        for (int step = 0; step < 80; step++) {
            if (live.session().restorationGame().getStack().isEmpty()) {
                break;
            }
            JsonObject pending = live.session().pendingDecisionPayload()
                    .getAsJsonObject("decision");
            assertEquals("priority", pending.get("decision_class").getAsString());
            submit(live.session(), "rg01-fizzle-resolve-" + step,
                    exactActionType(live.session().legalActionsPayload(), "pass_priority"));
        }
        assertTrue(live.session().restorationGame().getStack().isEmpty());
        assertEquals(40, live.seats().get("P2").getLife(),
                "fizzled Bolt cannot deal player damage or be retargeted");
        assertTrue(live.seats().get("P2").getHand().getCards(
                        live.session().restorationGame()).stream()
                .anyMatch(card -> "Grizzly Bears".equals(card.getName())));
    }

    @Test
    void counterspellCountersExactLowerSpell() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg01-countered", 3, List.of(
                        object("obj:bolt", "Lightning Bolt", "P2", Zone.HAND),
                        object("obj:counter", "Counterspell", "P1", Zone.HAND),
                        object("obj:red", "Mountain", "P2", Zone.BATTLEFIELD),
                        object("obj:u1", "Island", "P1", Zone.BATTLEFIELD),
                        object("obj:u2", "Island", "P1", Zone.BATTLEFIELD)));
        Live live = arrive(plan, "rg01-countered");

        XmageExternalRiskSignalTest.passToActor(
                live.session(), "rg01-countered", live.seats(), "P2");
        submit(live.session(), "rg01-countered-bolt",
                XmageExternalRiskSignalTest.spellOffer(
                        live.session().legalActionsPayload(), "Lightning Bolt"));
        submit(live.session(), "rg01-countered-bolt-target",
                exactTarget(live.session().legalActionsPayload(),
                        live.seats().get("P1").getId()));
        XmageFullGameDecisionExecutionTest.payHomogeneousMana(
                live.session(), "rg01-countered-bolt", "Mountain — {T}: Add {R}.");
        StackObject bolt = stackBySource(
                live, live.restoration().injectedObjectId("obj:bolt"));
        assertNotNull(bolt);

        XmageExternalRiskSignalTest.passToActor(
                live.session(), "rg01-countered", live.seats(), "P1");
        submit(live.session(), "rg01-countered-counterspell",
                XmageExternalRiskSignalTest.spellOffer(
                        live.session().legalActionsPayload(), "Counterspell"));
        submit(live.session(), "rg01-countered-target",
                exactTarget(live.session().legalActionsPayload(), bolt.getId()));
        XmageFullGameDecisionExecutionTest.payHomogeneousMana(
                live.session(), "rg01-countered-pay", "Island — {T}: Add {U}.");

        for (int step = 0; step < 80; step++) {
            if (live.session().restorationGame().getStack().isEmpty()) {
                break;
            }
            JsonObject pending = live.session().pendingDecisionPayload()
                    .getAsJsonObject("decision");
            assertEquals("priority", pending.get("decision_class").getAsString());
            submit(live.session(), "rg01-countered-resolve-" + step,
                    exactActionType(live.session().legalActionsPayload(), "pass_priority"));
        }
        assertEquals(40, live.seats().get("P1").getLife(),
                "countered Bolt never resolves");
        assertTrue(live.session().restorationGame().getStack().isEmpty());
    }

    @Test
    void leaverOwnedSpellLeavesStackAndSurvivorsContinue() {
        XmageNativeStateRestoration.Plan plan = plan(
                "rg01-leaver", 4, List.of(
                        object("obj:bolt", "Lightning Bolt", "P2", Zone.HAND),
                        object("obj:red", "Mountain", "P2", Zone.BATTLEFIELD)));
        Live live = arrive(plan, "rg01-leaver");

        XmageExternalRiskSignalTest.passToActor(
                live.session(), "rg01-leaver", live.seats(), "P2");
        submit(live.session(), "rg01-leaver-bolt",
                XmageExternalRiskSignalTest.spellOffer(
                        live.session().legalActionsPayload(), "Lightning Bolt"));
        submit(live.session(), "rg01-leaver-target",
                exactTarget(live.session().legalActionsPayload(),
                        live.seats().get("P1").getId()));
        XmageFullGameDecisionExecutionTest.payHomogeneousMana(
                live.session(), "rg01-leaver-pay", "Mountain — {T}: Add {R}.");
        assertNotNull(stackBySource(
                live, live.restoration().injectedObjectId("obj:bolt")));

        String p2 = live.seats().get("P2").getId().toString();
        assertTrue(live.session().concedeOfferPayload(p2)
                .get("concede_available").getAsBoolean());
        live.session().submitConcede(concedeProposal(p2));

        assertTrue(live.session().restorationGame().getStack().stream()
                .noneMatch(object -> "Lightning Bolt".equals(object.getName())));
        JsonObject next = live.session().pendingDecisionPayload();
        assertTrue(next.get("decision").isJsonNull()
                || !p2.equals(next.getAsJsonObject("decision")
                        .get("actor_id").getAsString()));
    }

    private static Live arrive(
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
        XmageNativeStateRestorationTest.completeArrival(
                session, restoration, seats);
        return new Live(session, restoration, seats);
    }

    private static XmageNativeStateRestoration.Plan plan(
            String id,
            int count,
            List<XmageNativeStateRestoration.RequestedObject> objects
    ) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int seat = 1; seat <= count; seat++) {
            String pid = "P" + seat;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid, "Rograkh, Son of Rohgahh", pid, 0));
        }
        return new XmageNativeStateRestoration.Plan(
                id, count, SEED, players, commanders, List.of(), objects,
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
    }

    private static XmageNativeStateRestoration.RequestedObject object(
            String semantic,
            String card,
            String owner,
            Zone zone
    ) {
        return new XmageNativeStateRestoration.RequestedObject(
                semantic, card, owner, owner, zone, false);
    }

    private static JsonObject exactNonManaAbility(
            JsonObject legal,
            UUID sourceId
    ) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!"activate_ability".equals(action.get("action_type").getAsString())) {
                continue;
            }
            JsonObject engine = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (engine.has("source_object_id")
                    && sourceId.toString().equals(
                            engine.get("source_object_id").getAsString())
                    && (!engine.has("mana_ability")
                            || !engine.get("mana_ability").getAsBoolean())) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "one exact non-mana activated ability");
        return matches.get(0);
    }

    private static JsonObject exactTarget(JsonObject legal, UUID id) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject engine = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (engine.has("object_id")
                    && id.toString().equals(engine.get("object_id").getAsString())) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "one exact target " + id);
        return matches.get(0);
    }

    private static JsonObject exactActionType(JsonObject legal, String type) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (type.equals(action.get("action_type").getAsString())) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "one " + type + " action");
        return matches.get(0);
    }

    private static JsonObject exactLabel(JsonObject legal, String label) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (label.equals(action.getAsJsonObject("metadata")
                    .get("label").getAsString())) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "one exact label " + label);
        return matches.get(0);
    }

    private static void submit(
            XmageFullGameSession session,
            String id,
            JsonObject action
    ) {
        XmageFullGameTaxExecutionTest.submit(session, id, action);
    }

    private static StackObject stackBySource(Live live, UUID sourceId) {
        StackObject found = null;
        for (StackObject object : live.session().restorationGame().getStack()) {
            if (sourceId.equals(object.getSourceId())) {
                if (found != null) {
                    fail("ambiguous native stack source " + sourceId);
                }
                found = object;
            }
        }
        return found;
    }

    private static List<UUID> targets(StackObject object) {
        List<UUID> ids = new ArrayList<>();
        object.getStackAbility().getTargets().forEach(
                target -> ids.addAll(target.getTargets()));
        return ids;
    }

    private static JsonObject concedeProposal(String actorId) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "rg01-leaver-concede");
        proposal.addProperty("actor_id", actorId);
        proposal.addProperty("action_type", "concede");
        return proposal;
    }

    private record Live(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats
    ) {
    }
}
