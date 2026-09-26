package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * DR-CLOSURE-01 Phase 4: bounded candidate-domain correctness.
 *
 * <p>Systemic invariant (no second legality engine, no card-name logic):</p>
 * <pre>
 * offered_options ⊆ authoritative_candidate_domain
 * chosen_option ∈ offered_options
 * non_candidate_object ∉ offered_options
 * </pre>
 * <p>Actual-card regression uses Serum Visions (scry 2): the engine offers
 * exactly the 2 looked cards; an adversarial decoy (a hand-card UUID, outside
 * the look domain) is never offered and is rejected typed on forgery; the
 * scry completes only through an explicit offered selection. A second test
 * cross-checks the Lightning Bolt target set against the engine-direct game
 * object universe. Dig Through Time was not used: it needs delve fuel plus
 * {7}{U} mana, far outside the minimal restoration vehicle; Serum Visions
 * exercises the identical generic look-domain path (choose-from-looked-cards
 * via the native bottom-of-library callback identity) with {U}.</p>
 */
class XmageFullGameCandidateDomainTest {

    static XmageFullGameSession scrySession(Map<String, Player>[] seatsOut) {
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "exec-domain-scry", 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Rograkh, Son of Rohgahh", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0)),
                List.of(
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:visions", "Serum Visions", "P1", "P1",
                                mage.constants.Zone.HAND, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:island", "Island", "P1", "P1",
                                mage.constants.Zone.BATTLEFIELD, false)),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, "exec-domain");
        XmageFullGameSession session = new XmageFullGameSession(
                "exec-domain-scry", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        seatsOut[0] = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seatsOut[0]);
        return session;
    }

    static JsonObject visionsOffer(JsonObject legal) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if ("activate_ability".equals(action.get("action_type").getAsString())
                    && action.toString().contains("Serum Visions")) {
                return action;
            }
        }
        fail("engine must offer Serum Visions through its legality");
        return null;
    }

    static void castAndPayVisions(XmageFullGameSession session, String tag) {
        XmageFullGameTaxExecutionTest.submit(session, tag + "-cast",
                visionsOffer(session.legalActionsPayload()));
        for (int round = 0; round < 4; round++) {
            JsonObject pending =
                    session.pendingDecisionPayload().getAsJsonObject("decision");
            if (pending.isJsonNull()
                    || !"mana_payment".equals(pending.get("decision_class").getAsString())) {
                return;
            }
            JsonObject legal = session.legalActionsPayload();
            JsonObject mana = null;
            JsonObject pool = null;
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                String optionType = action.getAsJsonObject("metadata")
                        .get("option_type").getAsString();
                if ("mana_ability".equals(optionType) && mana == null) {
                    mana = action;
                }
                if ("mana_pool".equals(optionType) && pool == null) {
                    pool = action;
                }
            }
            XmageFullGameTaxExecutionTest.submit(session, tag + "-pay-" + round,
                    mana != null ? mana : pool);
        }
    }

    static JsonObject scryPending(XmageFullGameSession session, String tag) {
        for (int step = 0; step < 30; step++) {
            JsonObject pending =
                    session.pendingDecisionPayload().getAsJsonObject("decision");
            if (pending.isJsonNull()) {
                fail("engine terminal before scry surface");
            }
            String decisionClass = pending.get("decision_class").getAsString();
            if (!"priority".equals(decisionClass) && !"mana_payment".equals(decisionClass)) {
                return pending;
            }
            XmageFullGameTaxExecutionTest.submit(session, tag + "-pass-" + step,
                    XmageFullGameTaxExecutionTest.singleActionOfType(
                            session.legalActionsPayload(), "pass_priority", null));
        }
        fail("scry surface never arrived");
        return null;
    }

    @Test
    void scryDomainConfinementWithDecoy() {
        @SuppressWarnings("unchecked")
        Map<String, Player>[] seatsOut = new Map[1];
        XmageFullGameSession session = scrySession(seatsOut);
        Map<String, Player> seats = seatsOut[0];
        Player p1 = seats.get("P1");
        castAndPayVisions(session, "exec-domain");
        JsonObject pending = scryPending(session, "exec-domain");
        assertTrue(pending.get("prompt").getAsString().contains("Scry"),
                "must reach the scry surface, got: " + pending.get("prompt").getAsString());

        // Oracle (test-only peeking): the live library UUID universe plus a
        // decoy from P1's hand (outside the look domain by construction).
        Set<String> libraryIds = new HashSet<>();
        for (Card card : p1.getLibrary().getCards(session.restorationGame())) {
            libraryIds.add(card.getId().toString());
        }
        String decoy = p1.getHand().getCards(session.restorationGame())
                .iterator().next().getId().toString();
        assertTrue(!libraryIds.contains(decoy), "decoy must sit outside the library");

        JsonObject legal = session.legalActionsPayload();
        List<JsonObject> offered = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            offered.add(element.getAsJsonObject());
        }
        assertEquals(2, offered.size(), "scry 2 bounds the domain to exactly 2");
        Set<String> offeredIds = new HashSet<>();
        for (JsonObject action : offered) {
            String optionId = action.getAsJsonObject("metadata")
                    .get("option_id").getAsString();
            offeredIds.add(optionId);
            assertTrue(libraryIds.contains(optionId),
                    "offered option must come from the looked library domain: " + optionId);
            assertTrue(!optionId.equals(decoy), "decoy must never be offered");
        }

        // Forgery with the decoy identity is rejected typed; decision parked.
        String decisionId = pending.get("decision_id").getAsString();
        String actor = pending.get("actor_id").getAsString();
        JsonObject forged = XmageFullGameDecisionExecutionTest.proposal(
                "exec-domain-forge", actor, decisionId + ":" + decoy, "choose_targets");
        try {
            session.submitAction(forged);
            fail("out-of-domain decoy must be rejected typed");
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            assertTrue(exc.getMessage().contains("ILLEGAL_ACTION"),
                    "typed rejection expected, got: " + exc.getMessage());
        }
        JsonObject still = session.pendingDecisionPayload().getAsJsonObject("decision");
        assertEquals(decisionId, still.get("decision_id").getAsString(),
                "rejected forgery must leave the scry parked");

        // Explicit completion through offered identities only: keep both on
        // top in engine-offered order when the schema allows empty bottom
        // selection, else bottom both explicitly.
        int minimum = pending.has("minimum_selections")
                ? pending.get("minimum_selections").getAsInt() : 1;
        if (minimum == 0) {
            JsonObject keep = XmageFullGameDecisionExecutionTest.proposal(
                    "exec-domain-keep", actor, "", "structural_decision");
            JsonObject after = session.submitAction(keep);
            assertEquals(decisionId, after.get("executed_decision_id").getAsString());
        } else {
            for (JsonObject action : offered) {
                XmageFullGameTaxExecutionTest.submit(session,
                        "exec-domain-bottom-" + action.get("action_id").getAsString().hashCode(),
                        action);
                JsonObject next =
                        session.pendingDecisionPayload().getAsJsonObject("decision");
                if (next.isJsonNull()
                        || !decisionId.equals(next.get("decision_id").getAsString())) {
                    break;
                }
            }
        }
        JsonObject after =
                session.pendingDecisionPayload().getAsJsonObject("decision");
        assertTrue(after.isJsonNull()
                || !decisionId.equals(after.get("decision_id").getAsString()),
                "explicit offered selections must complete the scry");
    }

    @Test
    void targetOptionsSubsetOfEngineGameUniverse() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord("MICRO_TARGETS"),
                        "exec-domain-targets", 424242L);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(
                        importer, plan, "exec-domain-targets");
        XmageFullGameSession session = new XmageFullGameSession(
                "MICRO_TARGETS", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);

        // Engine-direct universe: every permanent plus every player.
        Set<String> universe = new HashSet<>();
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            universe.add(permanent.getId().toString());
        }
        for (Player player : seats.values()) {
            universe.add(player.getId().toString());
        }

        JsonObject castLegal = session.legalActionsPayload();
        JsonObject bolt = null;
        for (JsonElement element : castLegal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject engine = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (engine.has("source_name")
                    && "Lightning Bolt".equals(engine.get("source_name").getAsString())) {
                bolt = action;
            }
        }
        assertTrue(bolt != null);
        XmageFullGameTaxExecutionTest.submit(session, "exec-domain-cast", bolt);

        JsonObject targetLegal = session.legalActionsPayload();
        assertEquals("target", targetLegal.get("decision_class").getAsString());
        for (JsonElement element : targetLegal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            String objectId = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata")
                    .get("object_id").getAsString();
            assertTrue(universe.contains(objectId),
                    "every offered target must exist in the engine game universe: " + objectId);
        }
    }
}
