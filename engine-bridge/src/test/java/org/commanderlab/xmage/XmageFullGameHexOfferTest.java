package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.permanent.Permanent;
import mage.game.stack.StackObject;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * RG-07 Lab closure: exact-N target legal-action offering through the bridge.
 *
 * <p>Reuse classification: {@code ENGINE_NATIVE_REUSE}. The pinned residual
 * candidate already carries the generic corrected offering path
 * ({@code PlayerImpl.getPlayable} through {@code Target.canChooseFromPossibleTargets}
 * with exact minimum/maximum cardinality), runtime-qualified on the engine side
 * by RG-07 (Hex 5/6/7 baselines plus actual six-target cast). No Lab production
 * change is claimed here: these tests prove the Lab bridge surfaces the native
 * offer faithfully — priority {@code getPlayable} enumeration, exact-cardinality
 * target domain, distinct-target enforcement, hexproof pool reduction, and
 * Rules-Core-owned resolution when a target becomes illegal.</p>
 *
 * <p>Vehicle: Hex ({@code {4}{B}{B}}, "Destroy six target creatures" as
 * implemented by the pinned engine; the exact-N mechanism is wording
 * independent). All mana is homogeneous Swamps; all targets are Grizzly Bears
 * unless stated. Seeds are fixed (424242) and every choice is an explicit
 * offered option — no first/random/default selection anywhere.</p>
 */
class XmageFullGameHexOfferTest {

    private static final String HEX = "Hex";
    private static final String BEARS = "Grizzly Bears";
    private static final String SWAMP_LABEL = "Swamp \u2014 {T}: Add {B}.";
    private static final String MOUNTAIN_LABEL = "Mountain \u2014 {T}: Add {R}.";
    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    record SessionSeats(
            XmageFullGameSession session,
            Map<String, Player> seats,
            XmageNativeStateRestoration restoration) {
    }

    private static XmageNativeStateRestoration.RequestedObject swamp(String pid, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:swamp-" + pid + "-" + index, "Swamp", pid, pid,
                mage.constants.Zone.BATTLEFIELD, false);
    }

    private static XmageNativeStateRestoration.RequestedObject bear(String pid, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bears-" + pid + "-" + index, BEARS, pid, pid,
                mage.constants.Zone.BATTLEFIELD, false);
    }

    private static XmageNativeStateRestoration.Plan hexPlan(
            String planId,
            int p1Bears,
            int p2Bears,
            List<XmageNativeStateRestoration.RequestedObject> p1Extra,
            List<XmageNativeStateRestoration.RequestedObject> p2Extra) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        for (int index = 0; index < 6; index++) {
            objects.add(swamp("P1", index));
        }
        for (int index = 0; index < p1Bears; index++) {
            objects.add(bear("P1", index));
        }
        for (int index = 0; index < p2Bears; index++) {
            objects.add(bear("P2", index));
        }
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:hex", HEX, "P1", "P1", mage.constants.Zone.HAND, false));
        objects.addAll(p1Extra);
        objects.addAll(p2Extra);
        return new XmageNativeStateRestoration.Plan(
                planId, 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", ROGRAKH, "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", ROGRAKH, "P2", 0)),
                objects,
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
    }

    private static SessionSeats startHex(
            String tag, XmageNativeStateRestoration.Plan plan) {
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
        return new SessionSeats(session, seats, restoration);
    }

    private static List<JsonObject> targetActions(JsonObject legal) {
        List<JsonObject> actions = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            actions.add(element.getAsJsonObject());
        }
        return actions;
    }

    private static String hexTargetOwnerPid(
            SessionSeats started, String objectId) {
        for (Permanent permanent : started.session().restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (permanent.getId().toString().equals(objectId)) {
                return XmageNativeStateRestorationTest.pidOf(
                        started.seats(), permanent.getOwnerId().toString());
            }
        }
        fail("target object is not a battlefield permanent: " + objectId);
        return "?";
    }

    private static void submitHexTargets(
            SessionSeats started, String tag, List<String> optionIds) {
        XmageFullGameSession session = started.session();
        JsonObject targetLegal = session.legalActionsPayload();
        assertEquals("target", targetLegal.get("decision_class").getAsString(),
                "Hex must drive an engine target decision");
        String decisionId = targetLegal.get("decision_id").getAsString();
        String actorId = targetLegal.get("actor_id").getAsString();
        long offset = targetLegal.get("decision_offset").getAsLong();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", actorId);
        proposal.addProperty("legal_action_id", decisionId + ":" + optionIds.get(0));
        proposal.addProperty("action_type", "choose_targets");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", offset);
        JsonArray selected = new JsonArray();
        optionIds.forEach(selected::add);
        choices.add("selected_option_ids", selected);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "rg07-hex-offer");
        JsonObject after = session.submitAction(proposal);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());
    }

    private static void assertHexOnStack(SessionSeats started, int expectedTargets) {
        boolean found = false;
        for (StackObject stackObject : started.session().restorationGame().getStack()) {
            if (!HEX.equals(stackObject.getName())) {
                continue;
            }
            found = true;
            int total = 0;
            for (mage.target.Target target
                    : stackObject.getStackAbility().getTargets()) {
                total += target.getTargets().size();
            }
            assertEquals(expectedTargets, total,
                    "Hex must carry six distinct native targets on the stack");
        }
        assertTrue(found, "Hex must be a native stack object after cast and payment");
    }

    private static int graveyardBears(SessionSeats started, String pid) {
        int count = 0;
        Player player = started.seats().get(pid);
        for (mage.cards.Card card
                : player.getGraveyard().getCards(started.session().restorationGame())) {
            if (BEARS.equals(card.getName())) {
                count++;
            }
        }
        return count;
    }

    private static Set<String> battlefieldBearIds(SessionSeats started) {
        Set<String> ids = new HashSet<>();
        for (Permanent permanent : started.session().restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (BEARS.equals(permanent.getName())) {
                ids.add(permanent.getId().toString());
            }
        }
        return ids;
    }

    @Test
    void hexOfferedWithExactlySixLegalTargets() {
        SessionSeats started = startHex("rg07-hex-six",
                hexPlan("rg07-hex-six", 3, 3, List.of(), List.of()));
        List<JsonObject> offers = XmageExternalRiskSignalTest.spellOffers(
                started.session().legalActionsPayload(), HEX);
        assertEquals(1, offers.size(),
                "[RG-07] exact six legal targets must produce exactly one Hex offer");
    }

    @Test
    void hexAbsentWithFiveLegalTargets() {
        SessionSeats started = startHex("rg07-hex-five",
                hexPlan("rg07-hex-five", 2, 3, List.of(), List.of()));
        List<JsonObject> offers = XmageExternalRiskSignalTest.spellOffers(
                started.session().legalActionsPayload(), HEX);
        assertTrue(offers.isEmpty(),
                "[RG-07] five legal targets must not offer exact-six Hex");
    }

    @Test
    void hexWithSevenTargetsCastsSixAndLeavesSeventh() {
        SessionSeats started = startHex("rg07-hex-seven",
                hexPlan("rg07-hex-seven", 4, 3, List.of(), List.of()));

        JsonObject targetLegal = null;
        {
            XmageFullGameSession session = started.session();
            XmageFullGameTaxExecutionTest.submit(session, "rg07-hex-seven-cast",
                    XmageExternalRiskSignalTest.spellOffer(
                            session.legalActionsPayload(), HEX));
            targetLegal = session.legalActionsPayload();
        }
        assertEquals("target", targetLegal.get("decision_class").getAsString());
        JsonObject pending = started.session().pendingDecisionPayload()
                .getAsJsonObject("decision");
        assertEquals(6, pending.get("minimum_selections").getAsInt(),
                "[RG-07] exact-N domain minimum must be six");
        assertEquals(6, pending.get("maximum_selections").getAsInt(),
                "[RG-07] exact-N domain maximum must be six");
        List<JsonObject> options = targetActions(targetLegal);
        assertEquals(7, options.size(),
                "[RG-07] seven legal creatures must all be offered as candidates");

        // Same-name decoys are distinct identities: three P1 bears, four P2 bears.
        int p1Count = 0;
        int p2Count = 0;
        Set<String> offeredIds = new HashSet<>();
        for (JsonObject action : options) {
            String objectId = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata")
                    .get("object_id").getAsString();
            assertTrue(offeredIds.add(objectId),
                    "[RG-07] target domain must not repeat an identity");
            String ownerPid = hexTargetOwnerPid(started, objectId);
            if ("P1".equals(ownerPid)) {
                p1Count++;
            } else if ("P2".equals(ownerPid)) {
                p2Count++;
            } else {
                fail("unexpected target owner: " + ownerPid);
            }
        }
        assertEquals(4, p1Count, "[RG-07] all four P1 bears must be offered");
        assertEquals(3, p2Count, "[RG-07] all three P2 bears must be offered");

        // Spare exactly one P2 bear: submit the other six by exact identity.
        List<String> offered = new ArrayList<>(offeredIds);
        String spared = null;
        List<String> chosen = new ArrayList<>();
        for (String objectId : offered) {
            if (spared == null && "P2".equals(hexTargetOwnerPid(started, objectId))) {
                spared = objectId;
                continue;
            }
            chosen.add(objectId);
        }
        assertEquals(6, chosen.size());
        assertTrue(spared != null);
        final String sparedId = spared;
        UUID.fromString(sparedId);

        submitHexTargets(started, "rg07-hex-seven-targets", chosen);
        XmageExternalRiskSignalTest.payHomogeneous(
                started.session(), "rg07-hex-seven-pay", SWAMP_LABEL, 16);
        assertHexOnStack(started, 6);
        XmageExternalRiskSignalTest.resolveStackEmpty(
                started.session(), "rg07-hex-seven");

        assertTrue(started.session().restorationGame().getStack().isEmpty());
        Set<String> remaining = battlefieldBearIds(started);
        assertEquals(Set.of(sparedId), remaining,
                "[RG-07] exactly the spared bear must survive Hex");
        assertEquals(4, graveyardBears(started, "P1"));
        assertEquals(2, graveyardBears(started, "P2"));
    }

    @Test
    void hexDuplicateTargetCannotSatisfyDistinctRequirement() {
        SessionSeats started = startHex("rg07-hex-dupe",
                hexPlan("rg07-hex-dupe", 3, 3, List.of(), List.of()));
        XmageFullGameSession session = started.session();
        XmageFullGameTaxExecutionTest.submit(session, "rg07-hex-dupe-cast",
                XmageExternalRiskSignalTest.spellOffer(
                        session.legalActionsPayload(), HEX));
        JsonObject targetLegal = session.legalActionsPayload();
        List<String> offered = new ArrayList<>();
        for (JsonObject action : targetActions(targetLegal)) {
            offered.add(action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata")
                    .get("object_id").getAsString());
        }
        assertEquals(6, offered.size());

        // Duplicate the first identity: six selections but only five distinct.
        List<String> duplicated = new ArrayList<>(offered);
        duplicated.set(5, offered.get(0));
        String decisionId = targetLegal.get("decision_id").getAsString();
        String actorId = targetLegal.get("actor_id").getAsString();
        long offset = targetLegal.get("decision_offset").getAsLong();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "rg07-hex-dupe");
        proposal.addProperty("actor_id", actorId);
        proposal.addProperty("legal_action_id", decisionId + ":" + offered.get(0));
        proposal.addProperty("action_type", "choose_targets");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", offset);
        JsonArray selected = new JsonArray();
        duplicated.forEach(selected::add);
        choices.add("selected_option_ids", selected);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        try {
            session.submitAction(proposal);
            fail("[RG-07] duplicate target identities must be rejected typed");
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            assertTrue(exc.getMessage().contains("duplicate"),
                    "[RG-07] typed duplicate rejection expected: " + exc.getMessage());
        }

        // The decision is still pending; submit the six distinct identities.
        submitHexTargets(started, "rg07-hex-dupe-targets", offered);
        XmageExternalRiskSignalTest.payHomogeneous(
                session, "rg07-hex-dupe-pay", SWAMP_LABEL, 16);
        assertHexOnStack(started, 6);
        XmageExternalRiskSignalTest.resolveStackEmpty(session, "rg07-hex-dupe");
        assertTrue(session.restorationGame().getStack().isEmpty());
        assertEquals(3, graveyardBears(started, "P1"));
        assertEquals(3, graveyardBears(started, "P2"));
    }

    @Test
    void hexproofCreatureIsExcludedFromExactSixPool() {
        SessionSeats started = startHex("rg07-hex-proof",
                hexPlan("rg07-hex-proof", 3, 3,
                        List.of(),
                        List.of(new XmageNativeStateRestoration.RequestedObject(
                                "obj:tyrant", "Carnage Tyrant", "P2", "P2",
                                mage.constants.Zone.BATTLEFIELD, false))));
        List<JsonObject> offers = XmageExternalRiskSignalTest.spellOffers(
                started.session().legalActionsPayload(), HEX);
        assertEquals(1, offers.size(),
                "[RG-07] six legal targets plus one hexproof creature must still offer Hex");

        XmageFullGameSession session = started.session();
        XmageFullGameTaxExecutionTest.submit(session, "rg07-hex-proof-cast", offers.get(0));
        JsonObject targetLegal = session.legalActionsPayload();
        List<String> offered = new ArrayList<>();
        for (JsonObject action : targetActions(targetLegal)) {
            offered.add(action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata")
                    .get("object_id").getAsString());
        }
        assertEquals(6, offered.size(),
                "[RG-07] hexproof creature must not enter the target domain");
        String tyrantId = null;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if ("Carnage Tyrant".equals(permanent.getName())) {
                tyrantId = permanent.getId().toString();
            }
        }
        assertTrue(tyrantId != null);
        assertFalse(offered.contains(tyrantId),
                "[RG-07] Carnage Tyrant must not be a legal Hex target");

        submitHexTargets(started, "rg07-hex-proof-targets", offered);
        XmageExternalRiskSignalTest.payHomogeneous(
                session, "rg07-hex-proof-pay", SWAMP_LABEL, 16);
        assertHexOnStack(started, 6);
        XmageExternalRiskSignalTest.resolveStackEmpty(session, "rg07-hex-proof");
        assertTrue(session.restorationGame().getStack().isEmpty());
        boolean tyrantSurvives = false;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if ("Carnage Tyrant".equals(permanent.getName())) {
                tyrantSurvives = true;
            }
        }
        assertTrue(tyrantSurvives, "[RG-07] hexproof creature must survive");
        assertEquals(3, graveyardBears(started, "P1"));
        assertEquals(3, graveyardBears(started, "P2"));
    }

    @Test
    void hexResolvesWhenOneTargetBecomesIllegal() {
        SessionSeats started = startHex("rg07-hex-fizzle",
                hexPlan("rg07-hex-fizzle", 3, 3,
                        List.of(),
                        List.of(
                                new XmageNativeStateRestoration.RequestedObject(
                                        "obj:bolt", "Lightning Bolt", "P2", "P2",
                                        mage.constants.Zone.HAND, false),
                                new XmageNativeStateRestoration.RequestedObject(
                                        "obj:mtn", "Mountain", "P2", "P2",
                                        mage.constants.Zone.BATTLEFIELD, false))));

        // P1 casts Hex on all six bears and pays.
        JsonObject targetLegal;
        {
            XmageFullGameSession session = started.session();
            XmageFullGameTaxExecutionTest.submit(session, "rg07-hex-fizzle-cast",
                    XmageExternalRiskSignalTest.spellOffer(
                            session.legalActionsPayload(), HEX));
            targetLegal = session.legalActionsPayload();
        }
        List<String> offered = new ArrayList<>();
        for (JsonObject action : targetActions(targetLegal)) {
            offered.add(action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata")
                    .get("object_id").getAsString());
        }
        assertEquals(6, offered.size());
        submitHexTargets(started, "rg07-hex-fizzle-targets", offered);
        XmageExternalRiskSignalTest.payHomogeneous(
                started.session(), "rg07-hex-fizzle-pay", SWAMP_LABEL, 16);
        assertHexOnStack(started, 6);

        // P2 responds with a genuine Lightning Bolt on one Hex-targeted P1 bear.
        XmageFullGameSession session = started.session();
        Map<String, Player> seats = started.seats();
        XmageExternalRiskSignalTest.passToActor(
                session, "rg07-hex-fizzle", seats, "P2");
        XmageFullGameTaxExecutionTest.submit(session, "rg07-hex-fizzle-bolt",
                XmageExternalRiskSignalTest.spellOffer(
                        session.legalActionsPayload(), "Lightning Bolt"));
        XmageExternalRiskSignalTest.submitTargetByOwnerName(
                session, seats, "P1", BEARS, "rg07-hex-fizzle-bolttarget");
        XmageExternalRiskSignalTest.payHomogeneous(
                session, "rg07-hex-fizzle-boltpay", MOUNTAIN_LABEL, 4);

        // Bolt resolves first (one bear to graveyard); Hex then resolves over
        // the five remaining legal targets — Rules-Core-owned fizzle check.
        XmageExternalRiskSignalTest.resolveStackEmpty(
                session, "rg07-hex-fizzle-resolve");
        assertTrue(session.restorationGame().getStack().isEmpty());

        int p1Grave = graveyardBears(started, "P1");
        int p2Grave = graveyardBears(started, "P2");
        assertEquals(6, p1Grave + p2Grave,
                "[RG-07] all six bears must leave the battlefield (one bolted, five hexed)");
        assertEquals(3, p1Grave, "[RG-07] all three P1 bears must be gone");
        assertEquals(3, p2Grave, "[RG-07] all three P2 bears must be gone");
        assertTrue(battlefieldBearIds(started).isEmpty());
        boolean hexInGraveyard = false;
        for (mage.cards.Card card : seats.get("P1").getGraveyard()
                .getCards(session.restorationGame())) {
            if (HEX.equals(card.getName())) {
                hexInGraveyard = true;
            }
        }
        assertTrue(hexInGraveyard, "[RG-07] resolved Hex must reach the graveyard");
    }
}
