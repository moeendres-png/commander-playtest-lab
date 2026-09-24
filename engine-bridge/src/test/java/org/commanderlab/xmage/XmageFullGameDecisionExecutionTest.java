package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * DR-CLOSURE-01 Phase 3: exact decision-family execution.
 *
 * <p>{@code PILOT_CHOOSE_MODE} (4P, seed 424242): restores Burn Down the
 * House to P1's hand, casts it through engine legality, selects the
 * provider-offered Devil-token mode by exact option identity (the second of
 * two engine-offered modes — never a first-option fallback), pays {3}{R}{R}
 * through engine-owned mana payment, resolves through real priority passes,
 * and asserts three Devil tokens under P1.</p>
 *
 * <p>{@code NEGATIVE_FIRST_OPTION} (4P, seed 424242): proves the
 * forbidden-fallback negative with direct runtime evidence. A forged
 * (un-offered) mode option is rejected with a typed
 * {@code ILLEGAL_ACTION} failure and the session stays parked (no fallback,
 * no silent skip); the compliant path then selects the Devil mode
 * explicitly, observes the parked under-resourced payment without
 * auto-answering, and cancels explicitly. The frozen terminal's
 * terminate-with-failure half is superseded (the bridge supports the mode
 * class, proven here), so this cell is recorded with direct negative
 * evidence but NOT promoted.</p>
 */
class XmageFullGameDecisionExecutionTest {

    static JsonObject proposal(String pid, String actor, String actionId, String type) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", pid);
        proposal.addProperty("actor_id", actor);
        proposal.addProperty("legal_action_id", actionId);
        proposal.addProperty("action_type", type);
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "dr-closure-phase3");
        return proposal;
    }

    static JsonObject burnOffer(JsonObject legal) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (action.toString().contains("Burn Down the House")
                    && "activate_ability".equals(action.get("action_type").getAsString())) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "exactly one Burn cast offer expected");
        return matches.get(0);
    }

    static List<JsonObject> modeOffers(JsonObject legal) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if ("choose_mode".equals(action.get("action_type").getAsString())) {
                matches.add(action);
            }
        }
        return matches;
    }

    static String modeLabel(JsonObject mode) {
        return mode.getAsJsonObject("metadata").get("label").getAsString();
    }

    static XmageFullGameSession restoredSession(
            String fixtureId, String gameTag, Map<String, Player>[] seatsOut) {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord(fixtureId),
                        gameTag, 424242L);
        assertEquals(4, plan.playerCount(), "exact 4P count for " + fixtureId);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, gameTag);
        XmageFullGameSession session = new XmageFullGameSession(
                fixtureId, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        seatsOut[0] = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seatsOut[0]);
        XmageNativeStateRestoration.CompareVerdict constructed = restoration.compare(
                XmageNativeStateRestoration.readback(
                        session.restorationGame(), seatsOut[0]), seatsOut[0]);
        assertTrue(constructed.match(),
                "construction must match before execution: " + constructed.mismatches());
        return session;
    }

    static void payHomogeneousMana(
            XmageFullGameSession session, String gameTag, String expectedLabel) {
        for (int round = 0; round < 12; round++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal during payment");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            if ("priority".equals(pending.get("decision_class").getAsString())) {
                return;
            }
            assertEquals("mana_payment", pending.get("decision_class").getAsString(),
                    "only engine-driven mana payment may follow, round " + round);
            JsonObject legal = session.legalActionsPayload();
            List<JsonObject> mana = new ArrayList<>();
            List<JsonObject> pool = new ArrayList<>();
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                JsonObject metadata = action.getAsJsonObject("metadata");
                String optionType = metadata.has("option_type")
                        && !metadata.get("option_type").isJsonNull()
                        ? metadata.get("option_type").getAsString() : "";
                if ("mana_ability".equals(optionType)) {
                    mana.add(action);
                } else if ("mana_pool".equals(optionType)) {
                    pool.add(action);
                }
            }
            if (!mana.isEmpty()) {
                String label = null;
                for (JsonObject action : mana) {
                    String candidate = action.getAsJsonObject("metadata")
                            .get("label").getAsString();
                    if (label == null) {
                        label = candidate;
                    } else {
                        assertEquals(label, candidate, "heterogeneous mana fails closed");
                    }
                }
                assertEquals(expectedLabel, label, "only " + expectedLabel + " expected");
                mana.sort((left, right) -> left.get("action_id").getAsString()
                        .compareTo(right.get("action_id").getAsString()));
                JsonObject useLegal = session.legalActionsPayload();
                XmageFullGameTaxExecutionTest.submit(session, gameTag + "-pay-" + round,
                        findById(useLegal, mana.get(0).get("action_id").getAsString()));
            } else if (pool.size() == 1) {
                XmageFullGameTaxExecutionTest.submit(session, gameTag + "-spend-" + round,
                        pool.get(0));
            } else {
                fail("payment round " + round + " offers neither mana abilities ("
                        + mana.size() + ") nor exactly one pool spend (" + pool.size() + ")");
            }
        }
        fail("payment bound breached");
    }

    static JsonObject findById(JsonObject legal, String actionId) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (actionId.equals(action.get("action_id").getAsString())) {
                return action;
            }
        }
        fail("action vanished between projection and submission: " + actionId);
        return null;
    }

    static void passUntil(
            XmageFullGameSession session, String gameTag, java.util.function.BooleanSupplier done,
            int bound) {
        for (int step = 0; step < bound; step++) {
            if (done.getAsBoolean()) {
                return;
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before checkpoint");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            assertEquals("priority", pending.get("decision_class").getAsString(),
                    "only priority passes during resolution, step " + step);
            XmageFullGameTaxExecutionTest.submit(session, gameTag + "-resolve-" + step,
                    XmageFullGameTaxExecutionTest.singleActionOfType(
                            session.legalActionsPayload(), "pass_priority", null));
        }
        fail("resolution bound breached");
    }

    @Test
    void pilotChooseModeSelectsDevilTokenMode() {
        @SuppressWarnings("unchecked")
        Map<String, Player>[] seatsOut = new Map[1];
        XmageFullGameSession session =
                restoredSession("PILOT_CHOOSE_MODE", "exec-choosemode", seatsOut);
        Map<String, Player> seats = seatsOut[0];
        Player p1 = seats.get("P1");

        JsonObject castLegal = session.legalActionsPayload();
        assertEquals("priority", castLegal.get("decision_class").getAsString());
        XmageFullGameTaxExecutionTest.submit(session, "exec-choosemode-cast",
                burnOffer(castLegal));

        // The engine — not the harness — offers exactly the two Oracle modes.
        JsonObject modeLegal = session.legalActionsPayload();
        assertEquals("mode", modeLegal.get("decision_class").getAsString());
        List<JsonObject> modes = modeOffers(modeLegal);
        assertEquals(2, modes.size(), "engine must offer exactly two modes");
        JsonObject devil = null;
        for (JsonObject mode : modes) {
            // Match the action's own option label: the shared decision prompt
            // embeds every mode's text, so serialized-contains is ambiguous.
            if (modeLabel(mode).contains("Devil")) {
                devil = mode;
            }
        }
        assertTrue(devil != null, "Devil-token mode must be engine-offered");
        // No first-option fallback by mechanism (not by position): the choice
        // is routed by exact engine-issued option identity, and the transport
        // rejects anything un-offered (proven in negativeFirstOption… below).
        // Position in the projected list is representational only.
        assertTrue(modes.stream().anyMatch(mode -> modeLabel(mode).contains("deals 5 damage")),
                "damage mode must be distinctly offered alongside Devil mode");
        XmageFullGameTaxExecutionTest.submit(session, "exec-choosemode-devil", devil);

        payHomogeneousMana(session, "exec-choosemode", "Mountain \u2014 {T}: Add {R}.");

        passUntil(session, "exec-choosemode", () -> {
            int devils = 0;
            for (Permanent permanent : session.restorationGame()
                    .getBattlefield().getAllPermanents()) {
                if (permanent.getName().equals("Devil Token")
                        && p1.getId().equals(permanent.getControllerId())) {
                    devils++;
                }
            }
            return devils == 3 && session.restorationGame().getStack().isEmpty();
        }, 60);

        int devils = 0;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (permanent.getName().equals("Devil Token")
                    && p1.getId().equals(permanent.getControllerId())) {
                devils++;
            }
        }
        assertEquals(3, devils,
                "terminal postcondition: three Devil tokens under P1 (Devil-token mode)");
    }

    @Test
    void negativeFirstOptionFailsClosedWithoutFallback() {
        @SuppressWarnings("unchecked")
        Map<String, Player>[] seatsOut = new Map[1];
        XmageFullGameSession session =
                restoredSession("NEGATIVE_FIRST_OPTION", "exec-negfirst", seatsOut);

        JsonObject castLegal = session.legalActionsPayload();
        XmageFullGameTaxExecutionTest.submit(session, "exec-negfirst-cast",
                burnOffer(castLegal));

        JsonObject modeLegal = session.legalActionsPayload();
        List<JsonObject> modes = modeOffers(modeLegal);
        assertEquals(2, modes.size(), "engine must offer exactly two modes");

        // Forgery (first-option-style fabrication) is rejected typed; the
        // session stays parked — no fallback, no silent skip.
        JsonObject devil = null;
        for (JsonObject mode : modes) {
            if (modeLabel(mode).contains("Devil")) {
                devil = mode;
            }
        }
        assertTrue(devil != null);
        String pendingId = modeLegal.get("decision_id").getAsString();
        String actor = modeLegal.get("actor_id").getAsString();
        JsonObject forged = proposal("exec-negfirst-forge", actor,
                pendingId + ":00000000-0000-0000-0000-000000000000", "choose_mode");
        try {
            session.submitAction(forged);
            fail("un-offered option must be rejected typed");
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            assertTrue(exc.getMessage().contains("ILLEGAL_ACTION"),
                    "typed rejection expected, got: " + exc.getMessage());
        }
        JsonObject still = session.pendingDecisionPayload().getAsJsonObject("decision");
        assertEquals(pendingId, still.get("decision_id").getAsString(),
                "rejected forgery must leave the decision parked, not skipped");

        // Compliant explicit selection of the SECOND mode, then parked
        // under-resourced payment: poll without answering and prove no
        // auto-progress, then cancel explicitly (a recorded pilot decision).
        XmageFullGameTaxExecutionTest.submit(session, "exec-negfirst-devil", devil);
        JsonObject payPending =
                session.pendingDecisionPayload().getAsJsonObject("decision");
        assertEquals("mana_payment", payPending.get("decision_class").getAsString());
        String payId = payPending.get("decision_id").getAsString();
        for (int poll = 0; poll < 3; poll++) {
            JsonObject again =
                    session.pendingDecisionPayload().getAsJsonObject("decision");
            assertEquals(payId, again.get("decision_id").getAsString(),
                    "payment must stay parked without pilot input (no auto-pass), poll " + poll);
        }
        JsonObject payLegal = session.legalActionsPayload();
        JsonObject cancel = null;
        for (JsonElement element : payLegal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if ("cancel_mana_payment".equals(action.getAsJsonObject("metadata")
                    .get("option_type").getAsString())) {
                cancel = action;
            }
        }
        assertTrue(cancel != null, "engine must offer explicit cancel");
        XmageFullGameTaxExecutionTest.submit(session, "exec-negfirst-cancel", cancel);
        JsonObject afterCancel =
                session.pendingDecisionPayload().getAsJsonObject("decision");
        assertEquals("priority", afterCancel.get("decision_class").getAsString(),
                "explicit cancel returns to priority (no silent skip)");
    }
}
