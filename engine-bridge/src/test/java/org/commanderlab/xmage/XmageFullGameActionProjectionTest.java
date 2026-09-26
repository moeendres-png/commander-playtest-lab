package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS204 B4-D generic projection/submission unit boundary.
 *
 * <p>Pure representational tests over synthetic pending decisions shaped
 * exactly like {@link XmageFullGameDecisionController} output. No engine,
 * no legality computation: every option is supplied, never enumerated.</p>
 */
class XmageFullGameActionProjectionTest {

    @Test
    void priorityPassProjectsToSingleBoundAction() {
        JsonObject pending = pending(
                "decision-1", 1L, "actor-1", "priority", "Choose priority action", 1, 1,
                List.of(option("pass-1", "Pass priority", "pass_priority", new JsonObject())),
                new JsonObject(), null
        );
        JsonArray actions = XmageFullGameActionProjection.project(pending);
        assertEquals(1, actions.size());
        JsonObject action = actions.get(0).getAsJsonObject();
        assertEquals("decision-1:pass-1", action.get("action_id").getAsString());
        assertEquals("actor-1", action.get("actor_id").getAsString());
        assertEquals("pass_priority", action.get("action_type").getAsString());
        JsonObject metadata = action.getAsJsonObject("metadata");
        assertEquals("decision-1", metadata.get("decision_id").getAsString());
        assertEquals(1L, metadata.get("decision_offset").getAsLong());
        assertEquals("priority", metadata.get("decision_class").getAsString());

        JsonObject proposal = proposal("p-1", "actor-1", "decision-1:pass-1", "pass_priority");
        JsonObject response = XmageFullGameActionProjection.toDecisionResponse(pending, proposal);
        assertEquals("decision-1", response.get("decision_id").getAsString());
        assertEquals("actor-1", response.get("actor_id").getAsString());
        assertEquals(1, response.getAsJsonArray("selected_option_ids").size());
        assertEquals("pass-1", response.getAsJsonArray("selected_option_ids").get(0).getAsString());
    }

    @Test
    void everySupportedDecisionClassProjectsWithoutLoss() {
        record Case(String decisionClass, String optionType, String expectedActionType,
                    int min, int max, boolean numeric) {}
        List<Case> cases = List.of(
                new Case("priority", "pass_priority", "pass_priority", 1, 1, false),
                new Case("priority", "activated_ability", "activate_ability", 1, 1, false),
                new Case("target", "target", "choose_targets", 1, 1, false),
                new Case("choose_object", "choice", "choose_targets", 1, 1, false),
                new Case("target_amount", "target_amount", "choose_targets", 1, 1, true),
                new Case("mulligan", "keep", "mulligan", 1, 1, false),
                new Case("mulligan", "mulligan", "mulligan", 1, 1, false),
                new Case("choose_use", "boolean", "structural_decision", 1, 1, false),
                new Case("choice", "choice", "structural_decision", 1, 1, false),
                new Case("choice", "cast_ability", "structural_decision", 1, 1, false),
                new Case("choice", "play_land_ability", "play_land", 1, 1, false),
                new Case("pile", "pile", "structural_decision", 1, 1, false),
                new Case("mana_payment", "mana_pool", "pay_cost", 1, 1, false),
                new Case("mana_payment", "mana_ability", "pay_cost", 1, 1, false),
                new Case("mana_payment", "cancel_mana_payment", "pay_cost", 1, 1, false),
                new Case("replacement_effect", "replacement_effect", "structural_decision", 1, 1, false),
                new Case("trigger_order", "triggered_ability", "structural_decision", 1, 1, false),
                new Case("mode", "mode", "choose_mode", 1, 1, false),
                new Case("declare_attacker", "declare_attacker", "declare_attackers", 1, 1, false),
                new Case("declare_attacker", "hold_attacker", "declare_attackers", 1, 1, false),
                new Case("declare_blocker", "declare_blocker", "declare_blockers", 0, 2, false)
        );
        for (Case c : cases) {
            JsonObject context = new JsonObject();
            if (c.numeric()) {
                context.addProperty("numeric_min", 1);
                context.addProperty("numeric_max", 3);
            }
            JsonObject meta = new JsonObject();
            JsonObject pending = pending(
                    "d-" + c.decisionClass() + "-" + c.optionType(), 7L, "actor-9",
                    c.decisionClass(), "prompt", c.min(), c.max(),
                    List.of(option("opt-1", "Label", c.optionType(), meta)),
                    context, null
            );
            JsonArray actions = XmageFullGameActionProjection.project(pending);
            assertEquals(1, actions.size(), c.decisionClass() + "/" + c.optionType());
            JsonObject action = actions.get(0).getAsJsonObject();
            assertEquals(c.expectedActionType(), action.get("action_type").getAsString(),
                    c.decisionClass() + "/" + c.optionType());
            JsonObject proposal = proposal(
                    "p-" + c.decisionClass(), "actor-9",
                    "d-" + c.decisionClass() + "-" + c.optionType() + ":opt-1",
                    c.expectedActionType()
            );
            if (c.numeric()) {
                proposal.getAsJsonObject("choices").addProperty("numeric_choice", 2);
            }
            JsonObject response = XmageFullGameActionProjection.toDecisionResponse(pending, proposal);
            assertEquals(1, response.getAsJsonArray("selected_option_ids").size(),
                    c.decisionClass() + "/" + c.optionType());
        }
    }

    @Test
    void numericOnlyDecisionProjectsToSingleStructuralAction() {
        JsonObject context = new JsonObject();
        context.addProperty("numeric_min", 0);
        context.addProperty("numeric_max", 5);
        JsonObject pending = pending(
                "dec-x", 4L, "actor-x", "announce_x", "Announce X", 0, 0,
                List.of(), context, null
        );
        JsonArray actions = XmageFullGameActionProjection.project(pending);
        assertEquals(1, actions.size());
        JsonObject action = actions.get(0).getAsJsonObject();
        assertEquals("dec-x:numeric", action.get("action_id").getAsString());
        assertEquals("structural_decision", action.get("action_type").getAsString());

        JsonObject proposal = proposal("p-x", "actor-x", "dec-x:numeric", "structural_decision");
        proposal.getAsJsonObject("choices").addProperty("numeric_choice", 3);
        JsonObject response = XmageFullGameActionProjection.toDecisionResponse(pending, proposal);
        assertEquals(3, response.get("numeric_choice").getAsInt());
        assertEquals(0, response.getAsJsonArray("selected_option_ids").size());
    }

    @Test
    void staleDecisionIdentityIsRejected() {
        JsonObject pending = pending(
                "current-1", 2L, "actor-1", "priority", "prompt", 1, 1,
                List.of(option("o1", "O1", "pass_priority", new JsonObject())),
                new JsonObject(), null
        );
        JsonObject proposal = proposal("p", "actor-1", "prior-9:o1", "pass_priority");
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, proposal)
        );
        assertTrue(failure.getMessage().contains("STALE_DECISION"));
    }

    @Test
    void wrongActorIsRejected() {
        JsonObject pending = pending(
                "d1", 1L, "actor-1", "priority", "prompt", 1, 1,
                List.of(option("o1", "O1", "pass_priority", new JsonObject())),
                new JsonObject(), null
        );
        JsonObject proposal = proposal("p", "actor-2", "d1:o1", "pass_priority");
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, proposal)
        );
        assertTrue(failure.getMessage().contains("wrong actor"));
    }

    @Test
    void unknownOptionIsRejected() {
        JsonObject pending = pending(
                "d1", 1L, "actor-1", "priority", "prompt", 1, 1,
                List.of(option("o1", "O1", "pass_priority", new JsonObject())),
                new JsonObject(), null
        );
        JsonObject proposal = proposal("p", "actor-1", "d1:ghost", "pass_priority");
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, proposal)
        );
        assertTrue(failure.getMessage().contains("ILLEGAL_ACTION"));
    }

    @Test
    void priorDecisionOptionIsRejectedAsStale() {
        JsonObject first = pending(
                "decision-aaa", 1L, "actor-1", "priority", "prompt", 1, 1,
                List.of(option("shared-opt", "O", "pass_priority", new JsonObject())),
                new JsonObject(), null
        );
        JsonArray firstActions = XmageFullGameActionProjection.project(first);
        String staleActionId = firstActions.get(0).getAsJsonObject().get("action_id").getAsString();

        JsonObject second = pending(
                "decision-bbb", 2L, "actor-1", "priority", "prompt", 1, 1,
                List.of(option("shared-opt", "O", "pass_priority", new JsonObject())),
                new JsonObject(), null
        );
        JsonObject proposal = proposal("p", "actor-1", staleActionId, "pass_priority");
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(second, proposal)
        );
        assertTrue(failure.getMessage().contains("STALE_DECISION"));
    }

    @Test
    void duplicateOptionsAreRejected() {
        JsonObject pending = pending(
                "d1", 1L, "actor-1", "declare_blocker", "prompt", 0, 2,
                List.of(
                        option("b1", "B1", "declare_blocker", new JsonObject()),
                        option("b2", "B2", "declare_blocker", new JsonObject())
                ),
                new JsonObject(), null
        );
        JsonObject proposal = proposal("p", "actor-1", "d1:b1", "declare_blockers");
        JsonObject choices = proposal.getAsJsonObject("choices");
        JsonArray selected = new JsonArray();
        selected.add("b1");
        selected.add("b1");
        choices.add("selected_option_ids", selected);
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, proposal)
        );
        assertTrue(failure.getMessage().contains("duplicate"));
    }

    @Test
    void malformedProposalsFailClosed() {
        JsonObject pending = pending(
                "d1", 1L, "actor-1", "priority", "prompt", 1, 1,
                List.of(option("o1", "O1", "pass_priority", new JsonObject())),
                new JsonObject(), null
        );
        JsonObject blankAction = proposal("p", "actor-1", "   ", "pass_priority");
        assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, blankAction)
        );
        JsonObject noColon = proposal("p", "actor-1", "nocolon", "pass_priority");
        XmageFullGameActionProjection.ProjectionException malformed = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, noColon)
        );
        assertTrue(malformed.getMessage().contains("malformed"));
    }

    @Test
    void actionTypeMismatchIsRejected() {
        JsonObject pending = pending(
                "d1", 1L, "actor-1", "priority", "prompt", 1, 1,
                List.of(option("o1", "O1", "pass_priority", new JsonObject())),
                new JsonObject(), null
        );
        JsonObject proposal = proposal("p", "actor-1", "d1:o1", "activate_ability");
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, proposal)
        );
        assertTrue(failure.getMessage().contains("ACTION_TYPE_MISMATCH"));
    }

    @Test
    void forbiddenTargetsAndModesAreRejected() {
        JsonObject pending = pending(
                "d1", 1L, "actor-1", "priority", "prompt", 1, 1,
                List.of(option("o1", "O1", "pass_priority", new JsonObject())),
                new JsonObject(), null
        );
        JsonObject withTargets = proposal("p", "actor-1", "d1:o1", "pass_priority");
        JsonArray targets = new JsonArray();
        targets.add("invented-target");
        withTargets.add("target_ids", targets);
        assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, withTargets)
        );
        JsonObject withModes = proposal("p", "actor-1", "d1:o1", "pass_priority");
        JsonArray modes = new JsonArray();
        modes.add("invented-mode");
        withModes.add("selected_modes", modes);
        assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, withModes)
        );
        JsonObject withForbiddenChoice = proposal("p", "actor-1", "d1:o1", "pass_priority");
        withForbiddenChoice.getAsJsonObject("choices").addProperty("requested_result", "win");
        XmageFullGameActionProjection.ProjectionException forbidden = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, withForbiddenChoice)
        );
        assertTrue(forbidden.getMessage().contains("forbidden choice field"));
    }

    @Test
    void outOfRangeNumericIsRejected() {
        JsonObject context = new JsonObject();
        context.addProperty("numeric_min", 0);
        context.addProperty("numeric_max", 5);
        JsonObject pending = pending(
                "dec-x", 4L, "actor-x", "announce_x", "Announce X", 0, 0,
                List.of(), context, null
        );
        JsonObject proposal = proposal("p-x", "actor-x", "dec-x:numeric", "structural_decision");
        proposal.getAsJsonObject("choices").addProperty("numeric_choice", 9);
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, proposal)
        );
        assertTrue(failure.getMessage().contains("out of range"));
    }

    @Test
    void orderingWithUnknownOptionIsRejected() {
        JsonObject pending = pending(
                "d1", 1L, "actor-1", "replacement_effect", "prompt", 1, 1,
                List.of(option("r1", "R1", "replacement_effect", new JsonObject())),
                new JsonObject(), null
        );
        JsonObject proposal = proposal("p", "actor-1", "d1:r1", "structural_decision");
        JsonArray ordering = new JsonArray();
        ordering.add("ghost-option");
        proposal.getAsJsonObject("choices").add("ordering", ordering);
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, proposal)
        );
        assertTrue(failure.getMessage().contains("ordering contains unknown option"));
    }

    @Test
    void projectionNeverEmbedsPilotState() {
        JsonObject pending = pending(
                "d1", 1L, "actor-1", "priority", "prompt", 1, 1,
                List.of(option("o1", "O1", "pass_priority", new JsonObject())),
                new JsonObject(), null
        );
        JsonObject pilotState = new JsonObject();
        pilotState.addProperty("secret_hand", "hidden-card");
        pending.add("pilot_state", pilotState);
        JsonArray actions = XmageFullGameActionProjection.project(pending);
        for (int i = 0; i < actions.size(); i++) {
            String encoded = actions.get(i).toString();
            assertTrue(!encoded.contains("secret_hand") && !encoded.contains("hidden-card"),
                    "projection must not leak pilot_state");
        }
    }

    @Test
    void noPendingDecisionFailsClosed() {
        JsonObject proposal = proposal("p", "actor-1", "d1:o1", "pass_priority");
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(null, proposal)
        );
        assertTrue(failure.getMessage().contains("STALE_DECISION"));
    }

    @Test
    void multiBlockerSelectionTravelsThroughChoicesMembership() {
        JsonObject pending = pending(
                "d-block", 9L, "actor-1", "declare_blocker", "Choose blockers", 0, 2,
                List.of(
                        option("blk-a", "Block A", "declare_blocker", new JsonObject()),
                        option("blk-b", "Block B", "declare_blocker", new JsonObject())
                ),
                new JsonObject(), null
        );
        JsonObject proposal = proposal("p", "actor-1", "d-block:blk-a", "declare_blockers");
        JsonArray selected = new JsonArray();
        selected.add("blk-a");
        selected.add("blk-b");
        proposal.getAsJsonObject("choices").add("selected_option_ids", selected);
        JsonObject response = XmageFullGameActionProjection.toDecisionResponse(pending, proposal);
        assertEquals(2, response.getAsJsonArray("selected_option_ids").size());
    }

    @Test
    void revisionOffsetMismatchIsStale() {
        JsonObject pending = pending(
                "d1", 5L, "actor-1", "priority", "prompt", 1, 1,
                List.of(option("o1", "O1", "pass_priority", new JsonObject())),
                new JsonObject(), null
        );
        JsonObject proposal = proposal("p", "actor-1", "d1:o1", "pass_priority");
        proposal.getAsJsonObject("choices").addProperty("decision_offset", 4L);
        XmageFullGameActionProjection.ProjectionException failure = assertThrows(
                XmageFullGameActionProjection.ProjectionException.class,
                () -> XmageFullGameActionProjection.toDecisionResponse(pending, proposal)
        );
        assertTrue(failure.getMessage().contains("STALE_DECISION"));
    }

    private static JsonObject pending(
            String decisionId,
            long offset,
            String actorId,
            String decisionClass,
            String prompt,
            int min,
            int max,
            List<JsonObject> options,
            JsonObject context,
            JsonObject sourceObject
    ) {
        JsonObject pending = new JsonObject();
        pending.addProperty("decision_id", decisionId);
        pending.addProperty("decision_offset", offset);
        pending.addProperty("actor_id", actorId);
        pending.addProperty("seat", 0);
        pending.addProperty("decision_class", decisionClass);
        pending.addProperty("prompt", prompt);
        pending.add("context", context == null ? new JsonObject() : context);
        pending.addProperty("minimum_selections", min);
        pending.addProperty("maximum_selections", max);
        JsonArray legal = new JsonArray();
        options.forEach(legal::add);
        pending.add("legal_options", legal);
        if (sourceObject != null) {
            pending.add("source_object", sourceObject);
        } else {
            pending.add("source_object", JsonNull.INSTANCE);
        }
        return pending;
    }

    private static JsonObject option(String id, String label, String type, JsonObject metadata) {
        JsonObject option = new JsonObject();
        option.addProperty("option_id", id);
        option.addProperty("label", label);
        option.addProperty("option_type", type);
        option.add("metadata", metadata == null ? new JsonObject() : metadata);
        return option;
    }

    private static JsonObject proposal(String proposalId, String actorId, String actionId, String actionType) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        proposal.addProperty("actor_id", actorId);
        proposal.addProperty("legal_action_id", actionId);
        proposal.addProperty("action_type", actionType);
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        proposal.add("choices", new JsonObject());
        proposal.getAsJsonObject("choices").add("ordering", new JsonArray());
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "ws204-unit");
        return proposal;
    }
}
