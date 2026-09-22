package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.CommanderCardType;
import mage.game.permanent.Permanent;
import mage.players.Player;
import mage.watchers.common.CommanderPlaysCountWatcher;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * FULL107 Phase C execution: WS05-CMD-TAX-2 fixture run.
 *
 * <p>Fixture-faithful execution (no deviation): restored requested state
 * (Rograkh commanders with P1 prior casts 2, Bears + Mountains placed,
 * life 40, seed 424242) via the qualified WS2 restoration path, natural
 * arrival at turn 1 precombat main with keeps and priority passes only,
 * deterministic mana pump (homogeneity-gated least-UUID among identical
 * Mountain activations), then the scripted {@code cast_commander} P1
 * selection resolved against projected legal actions with exact-one-match
 * fail-closed semantics. Required events are asserted from native facts
 * (stack spell, pool delta, cast-count delta) and terminal postconditions
 * via native readback. Forbidden fallbacks prohibited throughout.</p>
 */
class XmageFullGameTaxExecutionTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";
    private static final String MOUNTAIN_MANA_LABEL = "Mountain \u2014 {T}: Add {R}.";

    static JsonObject singleActionOfType(
            JsonObject legal, String actionType, String optionType) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!actionType.equals(action.get("action_type").getAsString())) {
                continue;
            }
            JsonObject metadata = action.getAsJsonObject("metadata");
            String actual = metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if (optionType == null || optionType.equals(actual)) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(),
                "expected exactly one " + actionType + "/" + optionType);
        return matches.get(0);
    }

    static JsonObject singleSelfAction(JsonObject legal, String actorId) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (action.get("action_id").getAsString().endsWith(":" + actorId)) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(), "expected exactly one self action");
        return matches.get(0);
    }

    static JsonObject genericProposal(
            String proposalId, String actorId, String actionId, String actionType) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        proposal.addProperty("actor_id", actorId);
        proposal.addProperty("legal_action_id", actionId);
        proposal.addProperty("action_type", actionType);
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "full107-tax-execution");
        return proposal;
    }

    static JsonObject submit(
            XmageFullGameSession session, String proposalId, JsonObject action) {
        JsonObject legal = session.legalActionsPayload();
        String actorId = legal.get("actor_id").getAsString();
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject after = session.submitAction(genericProposal(
                proposalId, actorId,
                action.get("action_id").getAsString(),
                action.get("action_type").getAsString()));
        assertEquals(pending.get("decision_id").getAsString(),
                after.get("executed_decision_id").getAsString());
        return after;
    }

    static JsonObject castOffer(JsonObject legal, String commanderName) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            JsonObject engine = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
            String abilityType = engine.has("ability_type") && !engine.get("ability_type").isJsonNull()
                    ? engine.get("ability_type").getAsString() : "";
            String sourceName = engine.has("source_name") && !engine.get("source_name").isJsonNull()
                    ? engine.get("source_name").getAsString() : "";
            if ("spell".equals(abilityType) && commanderName.equals(sourceName)) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(),
                "expected exactly one cast offer for " + commanderName);
        return matches.get(0);
    }

    static List<String> events = new ArrayList<>();

    @Test
    void ws05CmdTax2CastsCommanderWithTax() {
        executeTax("WS05-CMD-TAX-2", "exec-tax2");
    }

    @Test
    void ws05CmdTax4CastsCommanderWithTax() {
        executeTax("WS05-CMD-TAX-4", "exec-tax4");
    }

    static void executeTax(String fixtureId, String gameTag) {
        events.clear();
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord(fixtureId),
                        gameTag, 424242L);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, gameTag);
        XmageFullGameSession session = new XmageFullGameSession(
                fixtureId, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        Player p1 = seats.get("P1");

        // Arrival: keeps + passes to turn 1 precombat main (harness transport).
        for (int step = 0; step < 40; step++) {
            JsonObject readback = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats);
            if (readback.get("turn_number").getAsInt() == 1
                    && readback.get("phase").getAsString().equals("PRECOMBAT_MAIN")) {
                break;
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before arrival");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            if ("mulligan".equals(decisionClass)) {
                submit(session, gameTag + "-keep-" + step,
                        singleActionOfType(legal, "mulligan", "keep"));
                events.add("keep:" + actorId.substring(0, 8));
            } else if ("choose_object".equals(decisionClass)) {
                submit(session, gameTag + "-start-" + step,
                        singleSelfAction(legal, actorId));
            } else if ("priority".equals(decisionClass)) {
                submit(session, gameTag + "-pass-" + step,
                        singleActionOfType(legal, "pass_priority", null));
            } else {
                fail("unexpected decision class during arrival: " + decisionClass);
            }
            if (step == 39) {
                fail("arrival bound breached");
            }
        }
        restoration.restoreCommanderCasts(session.restorationGame(), seats);
        XmageNativeStateRestoration.revalidate(session.restorationGame());
        XmageNativeStateRestoration.CompareVerdict constructed =
                restoration.compare(
                        XmageNativeStateRestoration.readback(
                                session.restorationGame(), seats),
                        seats);
        assertTrue(constructed.match(),
                "construction must match before execution: " + constructed.mismatches());

        UUID commanderUuid = null;
        for (Card card : session.restorationGame().getCommanderCardsFromCommandZone(
                p1, CommanderCardType.COMMANDER_OR_OATHBREAKER)) {
            if (card.getName().equals(ROGRAKH)) {
                commanderUuid = card.getId();
            }
        }
        assertTrue(commanderUuid != null, "P1 Rograkh must be in the command zone");
        CommanderPlaysCountWatcher watcher = session.restorationGame()
                .getState().getWatcher(CommanderPlaysCountWatcher.class);
        assertEquals(2, watcher.getPlaysCount(commanderUuid), "prior casts 2");
        assertEquals(0, p1.getManaPool().getMana().count(), "pool starts empty");

        // Scripted cast_commander P1 with an empty pool: the engine owns
        // payment and parks on mana_payment decisions, which the executor
        // answers with homogeneity-gated least-UUID Mountain activations.
        JsonObject castLegal = session.legalActionsPayload();
        assertEquals("priority", castLegal.get("decision_class").getAsString());
        JsonObject castAction = castOffer(castLegal, ROGRAKH);
        submit(session, gameTag + "-cast", castAction);
        events.add("cast_commander:P1");
        for (int round = 0; round < 8; round++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal during payment");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            if ("priority".equals(decisionClass)) {
                break;
            }
            assertEquals("mana_payment", decisionClass,
                    "only engine-driven mana payment may follow the cast, round " + round);
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
                        assertEquals(label, candidate, "heterogeneous mana options fail closed");
                    }
                }
                assertEquals(MOUNTAIN_MANA_LABEL, label, "only Mountain mana expected");
                mana.sort((left, right) -> left.get("action_id").getAsString()
                        .compareTo(right.get("action_id").getAsString()));
                submit(session, gameTag + "-pay-" + round, mana.get(0));
            } else if (pool.size() == 1) {
                submit(session, gameTag + "-spend-" + round, pool.get(0));
            } else {
                fail("payment round " + round + " offers neither mana abilities ("
                        + mana.size() + ") nor exactly one pool spend (" + pool.size() + ")");
            }
        }

        // Required events from native facts (no parsing, no static checks).
        boolean onStack = false;
        for (mage.game.stack.StackObject stackObject
                : session.restorationGame().getStack()) {
            if (stackObject.getName().equals(ROGRAKH)) {
                onStack = true;
            }
        }
        assertTrue(onStack, "commander_cast_from_command: Rograkh must be on the stack");
        events.add("commander_cast_from_command:P1");
        int tappedMountains = 0;
        for (Permanent permanent
                : session.restorationGame().getBattlefield().getAllPermanents()) {
            if (permanent.getName().equals("Mountain")
                    && p1.getId().equals(permanent.getControllerId())
                    && permanent.isTapped()) {
                tappedMountains++;
            }
        }
        assertEquals(4, tappedMountains, "four Mountains tapped to pay {4}");
        events.add("mana_paid:4");
        assertEquals(3, watcher.getPlaysCount(commanderUuid), "cast count becomes 3");
        events.add("commander_tax:+4_generic");

        // Resolve through passes (both actors) until Rograkh is on the
        // battlefield under P1 or the bound is breached.
        boolean resolved = false;
        for (int step = 0; step < 40; step++) {
            boolean present = false;
            for (Permanent permanent
                    : session.restorationGame().getBattlefield().getAllPermanents()) {
                if (permanent.getName().equals(ROGRAKH)
                        && p1.getId().equals(permanent.getControllerId())) {
                    present = true;
                }
            }
            if (present) {
                resolved = true;
                break;
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before resolution");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            if (!"priority".equals(decisionClass)) {
                fail("unexpected decision class during resolution: " + decisionClass);
            }
            submit(session, gameTag + "-resolve-" + step,
                    singleActionOfType(
                            session.legalActionsPayload(), "pass_priority", null));
        }
        assertTrue(resolved, "Rograkh must resolve onto P1's battlefield");
        assertEquals(3, watcher.getPlaysCount(commanderUuid),
                "terminal postcondition: cast count becomes 3");
        assertTrue(events.contains("cast_commander:P1"));
        assertTrue(events.contains("commander_cast_from_command:P1"));
        assertTrue(events.contains("mana_paid:4"));
        assertTrue(events.contains("commander_tax:+4_generic"));
    }
}
