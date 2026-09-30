package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.stack.StackObject;
import mage.players.Player;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Causal reconstruction entries for the production-reachable mid-game lane.
 *
 * <p><b>What this class is.</b> The placement entry mode can only put a game
 * into a position the engine seam can construct directly. Some requested
 * states cannot truthfully be reached that way: a spell on the stack must have
 * been cast, a player at zero life must have lost that life, and a commander
 * in a graveyard must have moved there through a zone change. This class
 * builds the <em>pre-causal</em> position for those rows — the same physical
 * cards in hand, the declared fuel to pay for them, the declared instruments
 * to cause the elimination — and verifies afterwards that the running engine
 * itself produced the requested causal outcome. It never casts, never pays,
 * never resolves and never eliminates anything itself; every one of those
 * transitions is an ordinary engine decision answered by the external pilot
 * over the lane protocol.</p>
 *
 * <p><b>What this class is not.</b> It is not a second reconstruction engine.
 * The stack route reuses {@link XmageCausalStackReconstruction#prepare} for
 * parsing, validation and the pre-stack plan. The elimination route reuses
 * {@link XmageNativeStateRestoration#planFromFrozenRecord} and
 * {@link XmageNativeStateRestoration#validatePlan}. The five elimination
 * verdict codes mirror
 * {@link XmageCausalEliminationReconstruction}'s own codes so a reviewer can
 * compare the lane result against the native suite one-to-one. Verification
 * reads only live engine state through public engine APIs.</p>
 *
 * <p><b>Fuel and instruments are declared, never inferred.</b> Every card that
 * exists only to make the causal route executable — a Mountain to pay for a
 * Lightning Bolt, fourteen Mountains and fourteen Bolts to eliminate a player
 * at forty life — arrives in the request, is placed through the engine seam,
 * and is published in the plan payload. Nothing here invents a card.</p>
 */
final class XmageMidgameCausalBridge {

    /** One declared fuel or instrument card. */
    record DeclaredCard(
            String semanticId,
            String cardIdentity,
            String owner,
            String zone
    ) {
    }

    /** A life request the engine cannot honour at placement, recorded openly. */
    record LifeSubstitution(
            String playerId,
            int recordedLife,
            int placedLife
    ) {
    }

    /** A stack frame bound to its placed native source card. */
    record FrameBinding(
            String semanticId,
            String cardIdentity,
            String owner,
            String controller,
            List<String> targets,
            List<String> modes,
            String nativeSourceId
    ) {
    }

    /** A prepared causal-stack entry: the native plan plus its declared fuel. */
    record CausalStackPlan(
            XmageCausalStackReconstruction.Prepared prepared,
            List<DeclaredCard> fuel
    ) {
    }

    /** A prepared causal-elimination entry. */
    record CausalEliminationPlan(
            XmageNativeStateRestoration.Plan plan,
            String actorPid,
            String victimPid,
            List<DeclaredCard> instruments,
            List<LifeSubstitution> lifeSubstitutions,
            Set<String> expectedSurvivors
    ) {
    }

    static final class CausalException extends RuntimeException {
        CausalException(String code, String detail) {
            super(code + ": " + detail);
        }
    }

    private XmageMidgameCausalBridge() {
    }

    // ------------------------------------------------------------------
    // Planning: stack route.
    // ------------------------------------------------------------------

    /**
     * Prepares the pre-causal position for a stack-bearing record.
     *
     * <p>The fuel cards are appended to the record's own
     * {@code semantic_objects} before parsing, exactly as the native tier
     * suites do, so {@code prepare} validates them through the same path as
     * every other requested object. A fuel card in any zone but battlefield or
     * hand, or with any owner/controller divergence, fails closed here.</p>
     */
    static CausalStackPlan prepareCausalStack(
            JsonObject frozenRecord,
            List<DeclaredCard> fuel,
            String planId,
            long seed) {
        JsonObject record = frozenRecord.deepCopy();
        appendDeclaredCards(record, fuel, "fuel");
        try {
            XmageCausalStackReconstruction.Prepared prepared =
                    XmageCausalStackReconstruction.prepare(record, planId, seed);
            return new CausalStackPlan(prepared, List.copyOf(fuel));
        } catch (XmageCausalStackReconstruction.ReconstructionException exc) {
            throw new CausalException(
                    "CAUSAL_STACK_PREPARATION_REJECTED", exc.getMessage());
        }
    }

    static List<FrameBinding> bindFrames(
            XmageCausalStackReconstruction.Prepared prepared,
            XmageNativeStateRestoration restoration) {
        List<FrameBinding> bindings = new ArrayList<>();
        for (XmageCausalStackReconstruction.StackFrame frame
                : prepared.bottomToTop()) {
            UUID sourceId;
            try {
                sourceId = restoration.injectedObjectId(frame.semanticId());
            } catch (XmageNativeStateRestoration.RestorationException exc) {
                throw new CausalException(
                        "CAUSAL_FRAME_UNBOUND", exc.getMessage());
            }
            bindings.add(new FrameBinding(
                    frame.semanticId(),
                    frame.cardIdentity(),
                    frame.owner(),
                    frame.controller(),
                    List.copyOf(frame.targets()),
                    List.copyOf(frame.modes()),
                    sourceId.toString()));
        }
        return List.copyOf(bindings);
    }

    // ------------------------------------------------------------------
    // Planning: elimination route.
    // ------------------------------------------------------------------

    /**
     * Prepares the pre-causal position for an elimination-trigger record.
     *
     * <p>The record's {@code elimination_trigger} names the victim and the
     * reason. A victim whose recorded life the engine cannot honour at
     * placement — the engine re-derives starting life during game start, so a
     * requested zero becomes the recorded starting life — is substituted
     * openly and the substitution is part of the plan payload. The recorded
     * life is then reached only by causing real damage through the engine. The
     * instruments (damage spells in the actor's hand, mana on the actor's
     * battlefield) are declared in the request and validated as ordinary
     * supported dimensions.</p>
     */
    static CausalEliminationPlan planCausalElimination(
            JsonObject frozenRecord,
            String actorPid,
            String victimPid,
            List<DeclaredCard> instruments,
            String planId,
            long seed) {
        JsonObject record = frozenRecord.deepCopy();
        String fixtureId = requiredText(record, "fixture_id");
        if (!record.has("elimination_trigger")
                || !record.get("elimination_trigger").isJsonObject()) {
            throw new CausalException(
                    "ELIMINATION_TRIGGER_MISSING",
                    fixtureId + " declares no elimination_trigger");
        }
        JsonObject trigger = record.getAsJsonObject("elimination_trigger");
        String triggerPlayer = requiredText(trigger, "player");
        if (!victimPid.equals(triggerPlayer)) {
            throw new CausalException(
                    "ELIMINATION_VICTIM_MISMATCH",
                    fixtureId + " trigger names " + triggerPlayer
                            + " but the request names " + victimPid);
        }
        if (actorPid.equals(victimPid)) {
            throw new CausalException(
                    "ELIMINATION_ACTOR_IS_VICTIM", fixtureId + " " + actorPid);
        }

        Set<String> playerIds = new LinkedHashSet<>();
        for (JsonElement element : record.getAsJsonArray("players")) {
            playerIds.add(requiredText(element.getAsJsonObject(), "player_id"));
        }
        if (!playerIds.contains(actorPid) || !playerIds.contains(victimPid)) {
            throw new CausalException(
                    "ELIMINATION_UNKNOWN_PRINCIPAL",
                    fixtureId + " actor=" + actorPid + " victim=" + victimPid);
        }

        List<LifeSubstitution> substitutions = new ArrayList<>();
        for (JsonElement element : record.getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            if (!victimPid.equals(requiredText(player, "player_id"))) {
                continue;
            }
            int recorded = player.get("life").getAsInt();
            int starting = player.has("starting_life")
                    && !player.get("starting_life").isJsonNull()
                    ? player.get("starting_life").getAsInt() : 40;
            if (recorded != starting) {
                // The engine re-derives starting life during game start, so a
                // recorded zero (or any non-starting value) cannot be placed.
                // Substitute the recorded starting life openly; the recorded
                // value is then reachable only by causing real damage.
                player.addProperty("life", starting);
                substitutions.add(new LifeSubstitution(victimPid, recorded, starting));
            }
        }

        appendDeclaredCards(record, instruments, "instrument");

        final XmageNativeStateRestoration.Plan plan;
        try {
            plan = XmageNativeStateRestoration.planFromFrozenRecord(record, planId, seed);
            XmageNativeStateRestoration.validatePlan(plan);
        } catch (XmageNativeStateRestoration.RestorationException exc) {
            throw new CausalException(
                    "CAUSAL_ELIMINATION_PREPARATION_REJECTED", exc.getMessage());
        }

        Set<String> survivors = new LinkedHashSet<>();
        for (String pid : playerIds) {
            if (!pid.equals(victimPid)) {
                survivors.add(pid);
            }
        }
        if (survivors.isEmpty()) {
            throw new CausalException(
                    "ELIMINATION_NO_SURVIVORS",
                    fixtureId + " expects survivors after " + victimPid + " leaves");
        }
        return new CausalEliminationPlan(
                plan, actorPid, victimPid,
                List.copyOf(instruments),
                List.copyOf(substitutions),
                Set.copyOf(survivors));
    }

    private static void appendDeclaredCards(
            JsonObject record, List<DeclaredCard> cards, String kind) {
        String fixtureId = requiredText(record, "fixture_id");
        Set<String> known = new LinkedHashSet<>();
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            known.add(requiredText(element.getAsJsonObject(), "semantic_id"));
        }
        for (DeclaredCard card : cards) {
            if (!known.add(card.semanticId())) {
                throw new CausalException(
                        "DUPLICATE_DECLARED_CARD",
                        fixtureId + " " + card.semanticId());
            }
            if (!"battlefield".equals(card.zone()) && !"hand".equals(card.zone())) {
                throw new CausalException(
                        "UNSUPPORTED_DECLARED_ZONE",
                        fixtureId + " " + card.semanticId() + " zone=" + card.zone());
            }
            JsonObject object = new JsonObject();
            object.addProperty("semantic_id", card.semanticId());
            object.addProperty("card_identity", card.cardIdentity());
            object.addProperty("owner", card.owner());
            object.addProperty("controller", card.owner());
            object.addProperty("zone", card.zone());
            object.addProperty("tapped", false);
            object.add("counters", new JsonObject());
            record.getAsJsonArray("semantic_objects").add(object);
        }
    }

    // ------------------------------------------------------------------
    // Verification: stack route.
    // ------------------------------------------------------------------

    /**
     * Verifies that the running engine produced the prepared stack.
     *
     * <p>Checks, for every frame bottom-to-top: the source card is on the
     * stack, controlled by the frame's controller, with the requested identity;
     * its targets match the frame's target multiset (players by seat, earlier
     * stack objects by native id, other objects by injected id); its selected
     * mode count matches when the frame names modes. Finally the top-to-bottom
     * source order must equal the frozen request. Reads live engine state
     * only; mutates nothing.</p>
     */
    static JsonObject verifyCausalStack(
            XmageFullGameSession session,
            Map<String, Player> seats,
            XmageCausalStackReconstruction.Prepared prepared) {
        List<String> failures = new ArrayList<>();
        Map<String, UUID> stackIds = new LinkedHashMap<>();
        Game game = session.restorationGame();

        for (XmageCausalStackReconstruction.StackFrame frame : prepared.bottomToTop()) {
            UUID sourceId;
            try {
                sourceId = prepared.restoration().injectedObjectId(frame.semanticId());
            } catch (XmageNativeStateRestoration.RestorationException exc) {
                failures.add("STACK_SOURCE_UNBOUND: " + frame.semanticId());
                continue;
            }
            StackObject found = null;
            for (StackObject object : game.getStack()) {
                if (sourceId.equals(object.getSourceId())) {
                    if (found != null) {
                        failures.add("AMBIGUOUS_NATIVE_STACK_SOURCE: "
                                + frame.semanticId());
                        found = null;
                        break;
                    }
                    found = object;
                }
            }
            if (found == null) {
                failures.add("STACK_SOURCE_ABSENT: " + frame.semanticId()
                        + " was never cast by the engine");
                continue;
            }
            String controller = pidOf(seats, found.getControllerId().toString());
            if (controller == null || !frame.controller().equals(controller)) {
                failures.add("STACK_CONTROLLER_MISMATCH: " + frame.semanticId()
                        + " expected=" + frame.controller() + " actual=" + controller);
            }
            if (!frame.cardIdentity().equals(found.getName())) {
                failures.add("STACK_IDENTITY_MISMATCH: " + frame.semanticId()
                        + " expected=" + frame.cardIdentity() + " actual=" + found.getName());
            }
            List<UUID> expectedTargets = new ArrayList<>();
            boolean unbound = false;
            for (String target : frame.targets()) {
                Player player = seats.get(target);
                if (player != null) {
                    expectedTargets.add(player.getId());
                    continue;
                }
                UUID earlier = stackIds.get(target);
                if (earlier != null) {
                    expectedTargets.add(earlier);
                    continue;
                }
                try {
                    expectedTargets.add(
                            prepared.restoration().injectedObjectId(target));
                } catch (XmageNativeStateRestoration.RestorationException exc) {
                    failures.add("STACK_TARGET_UNBOUND: " + frame.semanticId()
                            + " -> " + target);
                    unbound = true;
                    break;
                }
            }
            if (unbound) {
                continue;
            }
            List<UUID> actualTargets = new ArrayList<>();
            if (found.getStackAbility() != null) {
                found.getStackAbility().getTargets().forEach(
                        target -> actualTargets.addAll(target.getTargets()));
            }
            if (!multiset(expectedTargets).equals(multiset(actualTargets))) {
                failures.add("STACK_TARGET_MISMATCH: " + frame.semanticId()
                        + " expected=" + expectedTargets + " actual=" + actualTargets);
            }
            if (found.getStackAbility() == null) {
                if (!frame.modes().isEmpty()) {
                    failures.add("STACK_MODE_MISMATCH: " + frame.semanticId()
                            + " has requested modes but no stack ability");
                }
            } else if (!frame.modes().isEmpty()) {
                int selected = found.getStackAbility().getModes().getSelectedModes().size();
                if (selected != frame.modes().size()) {
                    failures.add("STACK_MODE_COUNT_MISMATCH: " + frame.semanticId()
                            + " expected=" + frame.modes().size() + " actual=" + selected);
                }
            }
            stackIds.put(frame.semanticId(), found.getId());
        }

        List<String> expectedOrder = new ArrayList<>();
        for (JsonElement element
                : prepared.requestedRecord().getAsJsonArray("stack_state")) {
            expectedOrder.add(
                    requiredText(element.getAsJsonObject(), "source_semantic_id"));
        }
        Map<UUID, String> semanticByNative = new LinkedHashMap<>();
        stackIds.forEach((semantic, nativeId) -> semanticByNative.put(nativeId, semantic));
        List<String> actualOrder = new ArrayList<>();
        for (StackObject object : game.getStack()) {
            String semantic = semanticByNative.get(object.getId());
            if (semantic != null) {
                actualOrder.add(semantic);
            }
        }
        if (!expectedOrder.equals(actualOrder)) {
            failures.add("STACK_ORDER_MISMATCH: expected=" + expectedOrder
                    + " actual=" + actualOrder);
        }

        JsonObject verdict = new JsonObject();
        verdict.addProperty("causal_match", failures.isEmpty());
        JsonArray mismatches = new JsonArray();
        failures.forEach(mismatches::add);
        verdict.add("mismatches", mismatches);
        verdict.addProperty("frames_verified", stackIds.size());
        verdict.addProperty("frames_requested", prepared.bottomToTop().size());
        JsonArray order = new JsonArray();
        actualOrder.forEach(order::add);
        verdict.add("stack_order_top_to_bottom", order);
        return verdict;
    }

    // ------------------------------------------------------------------
    // Verification: elimination route.
    // ------------------------------------------------------------------

    /**
     * Verifies that the running engine eliminated the victim itself.
     *
     * <p>The verdict codes mirror
     * {@link XmageCausalEliminationReconstruction}'s own codes so the lane
     * result compares one-to-one with the native suite: the victim must have
     * lost or left by engine SBA, must not be retained in the survivor set,
     * and at least one survivor must remain. Life totals are reported for both
     * sides as discriminating evidence — a vacuous "player disappeared" result
     * cannot satisfy the survivor and life accounting together.</p>
     */
    static JsonObject verifyCausalElimination(
            XmageFullGameSession session,
            Map<String, Player> seats,
            String victimPid,
            Set<String> expectedSurvivors) {
        List<String> failures = new ArrayList<>();
        Player victim = seats.get(victimPid);
        if (victim == null) {
            failures.add("ELIMINATION_UNKNOWN_VICTIM: " + victimPid);
        } else if (!(victim.hasLost() || victim.hasLeft())) {
            failures.add("NATIVE_CAUSE_DID_NOT_ELIMINATE: " + victimPid
                    + " life=" + victim.getLife()
                    + " lost=" + victim.hasLost() + " left=" + victim.hasLeft());
        }

        Set<String> survivors = new LinkedHashSet<>();
        JsonObject lifeTotals = new JsonObject();
        for (Map.Entry<String, Player> entry : seats.entrySet()) {
            Player player = entry.getValue();
            lifeTotals.addProperty(entry.getKey(), player.getLife());
            if (!player.hasLost() && !player.hasLeft()) {
                survivors.add(entry.getKey());
            }
        }
        if (victim != null && survivors.contains(victimPid)) {
            failures.add("ELIMINATED_PLAYER_RETAINED: " + victimPid);
        }
        if (survivors.isEmpty()) {
            failures.add("ELIMINATION_NO_SURVIVORS: bounded multiplayer elimination"
                    + " expected survivors");
        }
        List<String> unexpectedSurvivors = new ArrayList<>(survivors);
        unexpectedSurvivors.removeAll(expectedSurvivors);
        List<String> missingSurvivors = new ArrayList<>(expectedSurvivors);
        missingSurvivors.removeAll(survivors);
        if (!unexpectedSurvivors.isEmpty() || !missingSurvivors.isEmpty()) {
            failures.add("ELIMINATION_SURVIVOR_MISMATCH: expected=" + expectedSurvivors
                    + " actual=" + survivors);
        }

        JsonObject verdict = new JsonObject();
        verdict.addProperty("causal_match", failures.isEmpty());
        JsonArray mismatches = new JsonArray();
        failures.forEach(mismatches::add);
        verdict.add("mismatches", mismatches);
        verdict.addProperty("victim", victimPid);
        verdict.addProperty("victim_life", victim == null ? -1 : victim.getLife());
        verdict.addProperty("victim_lost", victim != null && victim.hasLost());
        verdict.addProperty("victim_left", victim != null && victim.hasLeft());
        JsonArray survivorArray = new JsonArray();
        survivors.forEach(survivorArray::add);
        verdict.add("survivors", survivorArray);
        verdict.add("life_totals", lifeTotals);
        return verdict;
    }

    // ------------------------------------------------------------------
    // Payloads.
    // ------------------------------------------------------------------

    static JsonObject causalStackPayload(
            CausalStackPlan plan,
            XmageNativeStateRestoration restoration) {
        JsonObject payload = new JsonObject();
        payload.addProperty("entry_mode", "causal_stack");
        payload.addProperty("fixture_id", plan.prepared().fixtureId());
        payload.add("placed_objects", placedObjectsPayload(
                restoration, plan.prepared().preStackPlan().objects()));
        JsonArray frames = new JsonArray();
        for (FrameBinding binding : bindFrames(plan.prepared(), restoration)) {
            JsonObject frame = new JsonObject();
            frame.addProperty("semantic_id", binding.semanticId());
            frame.addProperty("card_identity", binding.cardIdentity());
            frame.addProperty("owner", binding.owner());
            frame.addProperty("controller", binding.controller());
            JsonArray targets = new JsonArray();
            binding.targets().forEach(targets::add);
            frame.add("targets", targets);
            JsonArray modes = new JsonArray();
            binding.modes().forEach(modes::add);
            frame.add("modes", modes);
            frame.addProperty("native_source_id", binding.nativeSourceId());
            frames.add(frame);
        }
        payload.add("frames_bottom_to_top", frames);
        JsonArray fuel = new JsonArray();
        for (DeclaredCard card : plan.fuel()) {
            JsonObject entry = new JsonObject();
            entry.addProperty("semantic_id", card.semanticId());
            entry.addProperty("card_identity", card.cardIdentity());
            entry.addProperty("owner", card.owner());
            entry.addProperty("zone", card.zone());
            try {
                entry.addProperty("native_id",
                        restoration.injectedObjectId(card.semanticId()).toString());
            } catch (XmageNativeStateRestoration.RestorationException exc) {
                throw new CausalException("CAUSAL_FUEL_UNBOUND", exc.getMessage());
            }
            fuel.add(entry);
        }
        payload.add("fuel", fuel);
        JsonObject checkpoint = new JsonObject();
        XmageNativeStateRestoration.Plan pre = plan.prepared().preStackPlan();
        checkpoint.addProperty("turn_number", pre.turnNumber());
        checkpoint.addProperty("phase", pre.phase().name());
        checkpoint.addProperty("step", pre.step().name());
        checkpoint.addProperty("active_player", pre.activePlayer());
        checkpoint.addProperty("priority_player", pre.priorityPlayer());
        payload.add("pre_stack_checkpoint", checkpoint);
        return payload;
    }

    static JsonObject eliminationPlanPayload(
            CausalEliminationPlan plan,
            XmageNativeStateRestoration restoration) {
        JsonObject payload = new JsonObject();
        payload.addProperty("entry_mode", "causal_elimination");
        payload.addProperty("actor", plan.actorPid());
        payload.addProperty("victim", plan.victimPid());
        payload.add("placed_objects", placedObjectsPayload(
                restoration, plan.plan().objects()));
        JsonArray instruments = new JsonArray();
        for (DeclaredCard card : plan.instruments()) {
            JsonObject entry = new JsonObject();
            entry.addProperty("semantic_id", card.semanticId());
            entry.addProperty("card_identity", card.cardIdentity());
            entry.addProperty("owner", card.owner());
            entry.addProperty("zone", card.zone());
            try {
                entry.addProperty("native_id",
                        restoration.injectedObjectId(card.semanticId()).toString());
            } catch (XmageNativeStateRestoration.RestorationException exc) {
                throw new CausalException("CAUSAL_INSTRUMENT_UNBOUND", exc.getMessage());
            }
            instruments.add(entry);
        }
        payload.add("instruments", instruments);
        JsonArray substitutions = new JsonArray();
        for (LifeSubstitution substitution : plan.lifeSubstitutions()) {
            JsonObject entry = new JsonObject();
            entry.addProperty("player_id", substitution.playerId());
            entry.addProperty("recorded_life", substitution.recordedLife());
            entry.addProperty("placed_life", substitution.placedLife());
            substitutions.add(entry);
        }
        payload.add("life_substitutions", substitutions);
        JsonArray survivors = new JsonArray();
        plan.expectedSurvivors().forEach(survivors::add);
        payload.add("expected_survivors", survivors);
        return payload;
    }

    // ------------------------------------------------------------------
    // Small helpers.
    // ------------------------------------------------------------------

    /**
     * Every placed object bound to its engine-minted native id. The pilot
     * needs these to match the engine's own offered target and source options
     * against the requested frames; placed-object ids already appear in every
     * offered action's metadata, so publishing the map adds no new exposure.
     */
    static JsonObject placedObjectsPayload(
            XmageNativeStateRestoration restoration,
            List<XmageNativeStateRestoration.RequestedObject> objects) {
        JsonObject map = new JsonObject();
        for (XmageNativeStateRestoration.RequestedObject object : objects) {
            try {
                map.addProperty(object.semanticId(),
                        restoration.injectedObjectId(object.semanticId()).toString());
            } catch (XmageNativeStateRestoration.RestorationException exc) {
                throw new CausalException("CAUSAL_OBJECT_UNBOUND", exc.getMessage());
            }
        }
        restoration.commanderObjectIds().forEach(
                (semanticId, nativeId) -> map.addProperty(semanticId, nativeId.toString()));
        return map;
    }

    private static Map<UUID, Integer> multiset(List<UUID> ids) {
        Map<UUID, Integer> counts = new LinkedHashMap<>();
        for (UUID id : ids) {
            counts.merge(id, 1, Integer::sum);
        }
        return counts;
    }

    private static String pidOf(Map<String, Player> seats, String actorUuid) {
        for (Map.Entry<String, Player> entry : seats.entrySet()) {
            if (entry.getValue().getId().toString().equals(actorUuid)) {
                return entry.getKey();
            }
        }
        return null;
    }

    private static String requiredText(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            throw new CausalException(
                    "INVALID_CAUSAL_REQUEST", "missing required field: " + property);
        }
        return object.get(property).getAsString();
    }
}
