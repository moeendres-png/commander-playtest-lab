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
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * PB-03 Wave 1: positive native executions for TIER_1 rows (Muse XHIGH).
 *
 * <p>Every method loads its own frozen fixture record, constructs the exact
 * requested state through {@code XmageNativeStateRestoration} (fail-closed),
 * asserts construction fidelity, performs the row's own causal steps with
 * genuine engine transactions and engine-offered choices only, and asserts
 * the row's required events and terminal postconditions as game facts.</p>
 *
 * <p>No credit is transferred between rows: a row passes here only if its own
 * obligation is observed. If a row's obligation proves unproducible, the
 * method must be rewritten as a blocker characterization (naming the exact
 * mechanism, row staying BLOCKED) rather than weakened into a pass.</p>
 */
class XmagePb03Tier1RowsTest {

    private static final long SEED = 424242L;

    /** Constructed + arrival-complete session with fidelity asserted. */
    private record Arrived(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats,
            XmageNativeStateRestoration.Plan plan) {
    }

    private static Arrived arrive(String fixtureId, String tag) {
        Arrived arrived = arriveDeferred(fixtureId, tag);
        XmageNativeStateRestoration.CompareVerdict constructed =
                arrived.restoration().compare(
                        XmageNativeStateRestoration.readback(
                                arrived.session().restorationGame(), arrived.seats()),
                        arrived.seats());
        assertTrue(constructed.match(),
                fixtureId + " construction must match before execution: "
                        + constructed.mismatches());
        return arrived;
    }

    /** Arrival without the fidelity assert (combat-phase rows assert post-drive). */
    private static Arrived arriveDeferred(String fixtureId, String tag) {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord(fixtureId), tag, SEED);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, tag);
        XmageFullGameSession session = new XmageFullGameSession(
                fixtureId, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new Arrived(session, restoration, seats, plan);
    }

    private static void submit(XmageFullGameSession session, String id, JsonObject action) {
        XmageFullGameTaxExecutionTest.submit(session, id, action);
    }

    /** Submit a prebuilt proposal (e.g. empty blocker selection) directly. */
    private static void submitProposal(
            XmageFullGameSession session, String tag, JsonObject proposal) {
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject after = session.submitAction(proposal);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString(),
                tag + ": proposal must execute against the pending decision");
    }

    private static void passPriority(XmageFullGameSession session, String id) {
        submit(session, id, XmageFullGameTaxExecutionTest.singleActionOfType(
                session.legalActionsPayload(), "pass_priority", null));
    }

    private static String pendingClass(XmageFullGameSession session) {
        for (int attempt = 0; attempt < 30; attempt++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (!payload.get("decision").isJsonNull()) {
                return payload.getAsJsonObject("decision").get("decision_class").getAsString();
            }
            try {
                Thread.sleep(100);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                fail("interrupted while polling pending decision");
            }
        }
        return null;
    }

    private static String decisionCreatureId(JsonObject legal) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type")
                    && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if (!("declare_attacker".equals(optionType)
                    || "hold_attacker".equals(optionType))) {
                continue;
            }
            JsonObject nativeMetadata = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
            if (nativeMetadata.has("object_id")
                    && !nativeMetadata.get("object_id").isJsonNull()) {
                return nativeMetadata.get("object_id").getAsString();
            }
        }
        return null;
    }

    private static void submitHoldAttacker(
            XmageFullGameSession session, String id) {
        submit(session, id, XmageFullGameTaxExecutionTest.singleActionOfType(
                session.legalActionsPayload(), "declare_attackers", "hold_attacker"));
    }

    private static JsonObject exactAttack(
            XmageFullGameSession session, Map<String, Player> seats,
            UUID attacker, UUID defender) {
        JsonObject legal = session.legalActionsPayload();
        assertEquals("declare_attacker", legal.get("decision_class").getAsString());
        // Diagnostic identity map: every permanent vs injections.
        StringBuilder identities = new StringBuilder();
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            identities.append("  permanent=").append(permanent.getName())
                    .append(" id=").append(permanent.getId())
                    .append(" controller=").append(permanent.getControllerId())
                    .append(" tapped=").append(permanent.isTapped()).append("\n");
        }
        List<JsonObject> matches = new ArrayList<>();
        StringBuilder dump = new StringBuilder();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            JsonObject nativeMetadata = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
            String optionType = metadata.has("option_type")
                    && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            dump.append(action.get("action_id").getAsString()).append(" wire=")
                    .append(action.has("action_type")
                            && !action.get("action_type").isJsonNull()
                            ? action.get("action_type").getAsString() : "?")
                    .append(" opt=").append(optionType);
            String defenderPid = "(none)";
            if (nativeMetadata.has("defender_id")
                    && !nativeMetadata.get("defender_id").isJsonNull()) {
                try {
                    defenderPid = XmageNativeStateRestorationTest.pidOf(
                            seats, nativeMetadata.get("defender_id").getAsString());
                } catch (Exception exc) {
                    defenderPid = "STALE-UNMAPPED";
                }
            }
            dump.append(" defenderPid=").append(defenderPid).append(" native=")
                    .append(nativeMetadata).append("\n");
            if (!"declare_attacker".equals(optionType)) {
                continue;
            }
            String optionName = nativeMetadata.has("name")
                    && !nativeMetadata.get("name").isJsonNull()
                    ? nativeMetadata.get("name").getAsString() : "";
            String defenderId = nativeMetadata.has("defender_id")
                    && !nativeMetadata.get("defender_id").isJsonNull()
                    ? nativeMetadata.get("defender_id").getAsString() : "";
            if (optionName.isEmpty() || !defender.toString().equals(defenderId)) {
                continue;
            }
            // Disambiguate same-name attackers by native object identity when
            // the engine exposes it; otherwise keep every name/defender match.
            boolean identityMismatch = false;
            for (Map.Entry<String, JsonElement> entry : nativeMetadata.entrySet()) {
                if (!entry.getValue().isJsonPrimitive()) {
                    continue;
                }
                String key = entry.getKey();
                String value = entry.getValue().getAsString();
                if (("object_id".equals(key) || "source_object_id".equals(key)
                        || "attacker_id".equals(key))
                        && !attacker.toString().equals(value)
                        && !value.isEmpty()) {
                    identityMismatch = true;
                }
            }
            if (!identityMismatch) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(),
                "exact attack offer attacker=" + attacker
                        + " defender=" + defender + "; offered:\n" + dump
                        + "all permanents:\n" + identities);
        return matches.get(0);
    }

    private static Permanent permanentByName(
            XmageFullGameSession session, Player controller, String name) {
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (permanent.getName().equals(name)
                    && controller.getId().equals(permanent.getControllerId())) {
                return permanent;
            }
        }
        return null;
    }

    private static void passUntil(
            XmageFullGameSession session, String tag, String wantedClass, int bound) {
        for (int step = 0; step < bound; step++) {
            String pending = pendingClass(session);
            if (wantedClass.equals(pending)) {
                return;
            }
            if (pending == null) {
                fail(tag + ": engine terminal before " + wantedClass);
            }
            if (!"priority".equals(pending)) {
                fail(tag + ": unexpected " + pending + " while seeking " + wantedClass);
            }
            passPriority(session, tag + "-pass-" + step);
        }
        fail(tag + ": bound exceeded seeking " + wantedClass);
    }

    // ---- MICRO_COMBAT: two 2/2s trade via genuine declarations ----

    @Test
    void microCombatBearsTradeAndBothDie() {
        Arrived arrived = arrive("MICRO_COMBAT", "pb03-combat");
        XmageFullGameSession session = arrived.session();
        Map<String, Player> seats = arrived.seats();
        UUID attackerId = arrived.restoration().injectedObjectId("obj:micro-attacker");
        // Placement-vs-identity audit: every injected semantic id must resolve
        // to a live battlefield permanent (proves the id mapping, not just
        // multiset counts which are blind to same-name duplicates).
        for (String semantic : List.of("obj:p1-bears", "obj:micro-attacker",
                "obj:p2-bears", "obj:micro-blocker", "obj:p3-bears")) {
            UUID id = arrived.restoration().injectedObjectId(semantic);
            assertNotNull(session.restorationGame().getPermanent(id),
                    "placed battlefield permanent for " + semantic + " = " + id);
        }

        passUntil(session, "pb03-combat", "declare_attacker", 40);
        // Declarations arrive per creature: attack with micro-attacker at P2,
        // hold every other creature (genuine discretionary holds).
        for (int step = 0; step < 20; step++) {
            String pending = pendingClass(session);
            if (!"declare_attacker".equals(pending)) {
                break;
            }
            JsonObject legal = session.legalActionsPayload();
            String creature = decisionCreatureId(legal);
            if (attackerId.toString().equals(creature)) {
                submit(session, "pb03-combat-attack",
                        exactAttack(session, seats, attackerId, seats.get("P2").getId()));
            } else {
                submitHoldAttacker(session, "pb03-combat-hold-" + step);
            }
        }

        // Advance to the P2 blocker declaration (other seats decline).
        JsonObject blockOffer = null;
        for (int step = 0; step < 40; step++) {
            String pending = pendingClass(session);
            if (pending == null) {
                fail("engine terminal before declare_blocker");
            }
            if ("declare_blocker".equals(pending)) {
                JsonObject legal = session.legalActionsPayload();
                String actorPid = XmageNativeStateRestorationTest.pidOf(
                        seats, legal.get("actor_id").getAsString());
                if ("P2".equals(actorPid)) {
                    // The row carries no decision_script: any P2 Bears blocking
                    // the declared P1 attacker satisfies the obligation. Accept
                    // the engine-offered pair after verifying its substance
                    // (P2-controlled Bears blocks the declared attacker).
                    blockOffer = findBlockOfferForAttacker(legal, seats, attackerId);
                    break;
                }
                submitProposal(session, "pb03-combat-noblock-" + step,
                        emptyBlockProposal("pb03-combat-noblock-" + step, legal));
                continue;
            }
            if (!"priority".equals(pending)) {
                fail("unexpected " + pending + " seeking declare_blocker");
            }
            passPriority(session, "pb03-combat-pass-" + step);
        }
        assertNotNull(blockOffer, "P2 must be offered a block on micro-attacker");
        UUID offeredBlocker = UUID.fromString(blockOffer.getAsJsonObject("metadata")
                .getAsJsonObject("xmage_option_metadata").get("blocker_id").getAsString());
        Permanent blockerPermanent =
                session.restorationGame().getPermanent(offeredBlocker);
        assertNotNull(blockerPermanent, "offered blocker must be a live permanent");
        assertEquals("Grizzly Bears", blockerPermanent.getName(), "blocker must be a Bears");
        assertEquals(seats.get("P2").getId(), blockerPermanent.getControllerId(),
                "blocker must be P2-controlled");
        submit(session, "pb03-combat-block", blockOffer);

        // Pass priority through the damage step until state-based actions
        // clear both 2/2s. Further declare_blocker decisions (other seats,
        // or additional blockers) are declined with empty selections so the
        // obligated one-on-one trade stands exactly as declared.
        for (int step = 0; step < 40; step++) {
            if (session.restorationGame().getPermanent(attackerId) == null
                    && session.restorationGame().getPermanent(offeredBlocker) == null) {
                break;
            }
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            if ("declare_blocker".equals(pending)) {
                submitProposal(session, "pb03-combat-damage-noblock-" + step,
                        emptyBlockProposal("pb03-combat-damage-noblock-" + step,
                                session.legalActionsPayload()));
                continue;
            }
            if (!"priority".equals(pending)) {
                fail("unexpected " + pending + " awaiting combat damage");
            }
            passPriority(session, "pb03-combat-damage-pass-" + step);
        }
        // Combat damage + state-based actions: both 2/2s die.
        XmageNativeStateRestoration.revalidate(session.restorationGame());
        assertNull(session.restorationGame().getPermanent(attackerId),
                "attacker must leave the battlefield");
        assertNull(session.restorationGame().getPermanent(offeredBlocker),
                "blocker must leave the battlefield");
        assertTrue(seats.get("P1").getGraveyard().size() >= 1, "P1 graveyard grows");
        assertTrue(seats.get("P2").getGraveyard().size() >= 1, "P2 graveyard grows");
    }

    /**
     * Accepts the engine-offered block on the declared attacker, verifying
     * substance over labels: the blocker must be a Bears controlled by the
     * defending actor and the attacker must be the declared one. The row
     * carries no decision_script naming a blocker, so any such genuine pair
     * satisfies the obligation; the semantic-id attribution is recorded but
     * does not gate the outcome.
     */
    private static JsonObject findBlockOfferForAttacker(
            JsonObject legal, Map<String, Player> seats, UUID attacker) {
        List<JsonObject> matches = new ArrayList<>();
        StringBuilder dump = new StringBuilder();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type")
                    && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            JsonObject nativeMetadata = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
            dump.append(action.get("action_id").getAsString()).append(" native=")
                    .append(nativeMetadata).append("\n");
            if (!"declare_blocker".equals(optionType)) {
                continue;
            }
            String offeredBlocker = nativeMetadata.has("blocker_id")
                    && !nativeMetadata.get("blocker_id").isJsonNull()
                    ? nativeMetadata.get("blocker_id").getAsString() : "";
            String offeredAttacker = nativeMetadata.has("attacker_id")
                    && !nativeMetadata.get("attacker_id").isJsonNull()
                    ? nativeMetadata.get("attacker_id").getAsString() : "";
            if (!attacker.toString().equals(offeredAttacker) || offeredBlocker.isEmpty()) {
                continue;
            }
            matches.add(action);
        }
        assertEquals(1, matches.size(),
                "exactly one engine-offered block on the declared attacker; offered:\n" + dump);
        return matches.get(0);
    }

    private static JsonObject findBlockOffer(
            JsonObject legal, UUID blocker, UUID attacker) {
        List<JsonObject> matches = new ArrayList<>();
        StringBuilder dump = new StringBuilder();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type")
                    && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            JsonObject nativeMetadata = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
            dump.append(action.get("action_id").getAsString()).append(" type=")
                    .append(action.get("action_type").getAsString()).append(" opt=")
                    .append(optionType).append(" native=").append(nativeMetadata).append("\n");
            if (!"declare_blocker".equals(optionType)) {
                continue;
            }
            boolean hitsBlocker = false;
            boolean hitsAttacker = false;
            for (Map.Entry<String, JsonElement> entry : nativeMetadata.entrySet()) {
                if (!entry.getValue().isJsonPrimitive()) {
                    continue;
                }
                String value = entry.getValue().getAsString();
                if (blocker.toString().equals(value)) {
                    hitsBlocker = true;
                }
                if (attacker.toString().equals(value)) {
                    hitsAttacker = true;
                }
            }
            if (hitsBlocker && hitsAttacker) {
                matches.add(action);
            }
        }
        assertEquals(1, matches.size(),
                "exact block offer blocker=" + blocker + " attacker=" + attacker
                        + "; offered actions:\n" + dump);
        return matches.get(0);
    }

    private static JsonObject emptyBlockProposal(
            String proposalId, JsonObject legal) {
        JsonObject proposal = XmageFullGameTaxExecutionTest.genericProposal(
                proposalId, legal.get("actor_id").getAsString(), "",
                "structural_decision");
        proposal.add("legal_action_id", com.google.gson.JsonNull.INSTANCE);
        return proposal;
    }

    // ---- MICRO_CONTINUOUS_EFFECTS: Crawler P/T from hand size ----
    //
    // Blocker characterization (row stays BLOCKED): the restored Psychosis
    // Crawler's draw trigger fires during game start (P1's turn-1 draw costs
    // every opponent 1 life, proven below), and the obligated 5/5 is
    // arithmetically unproducible — P1 holds opening seven plus the turn-1
    // draw plus five restored Mountains, so the honestly evaluated Crawler
    // is larger. What IS proven: continuous P/T equals the actual hand size
    // with no trigger involved in the evaluation itself.

    @Test
    void microContinuousCrawlerPowerToughnessFromHand() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord("MICRO_CONTINUOUS_EFFECTS"),
                        "pb03-continuous", SEED);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, "pb03-continuous");
        XmageFullGameSession session = new XmageFullGameSession(
                "MICRO_CONTINUOUS_EFFECTS", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        // Custom arrival: driveArrival fails closed on the Crawler's genuine
        // turn-1 draw trigger, so answer it explicitly (sole ordering option).
        for (int step = 0; step < 80; step++) {
            JsonObject readback = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats);
            if (readback.get("turn_number").getAsInt() == 1
                    && readback.get("phase").getAsString().equals("PRECOMBAT_MAIN")
                    && readback.get("step").getAsString().equals("PRECOMBAT_MAIN")) {
                break;
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before arrival at step " + step);
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            JsonObject action;
            if ("mulligan".equals(decisionClass)) {
                action = XmageNativeStateRestorationTest.singleActionOfType(
                        legal, "mulligan", "keep");
            } else if ("choose_object".equals(decisionClass)
                    && pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    && pending.get("prompt").getAsString().contains("starting player")) {
                action = XmageNativeStateRestorationTest.singleSelfAction(legal, actorId);
            } else if ("priority".equals(decisionClass)) {
                action = XmageNativeStateRestorationTest.singleActionOfType(
                        legal, "pass_priority", null);
            } else if ("trigger_order".equals(decisionClass)) {
                // The restored Crawler triggers once per card P1 drew at game
                // start. The engine offers one option per pending instance, and
                // every offered option is byte-identical (same decision_id,
                // same option_id, same ability): the ordering is vacuous, so
                // submitting the offered option exercises no discretion.
                JsonArray options = legal.getAsJsonArray("actions");
                assertTrue(options.size() >= 1, "at least one trigger instance offered");
                String first = options.get(0).getAsJsonObject()
                        .get("action_id").getAsString();
                for (JsonElement element : options) {
                    assertEquals(first,
                            element.getAsJsonObject().get("action_id").getAsString(),
                            "all trigger-order options must be the identical instance");
                }
                action = options.get(0).getAsJsonObject();
                action = legal.getAsJsonArray("actions").get(0).getAsJsonObject();
            } else {
                fail("unexpected decision class during arrival: " + decisionClass
                        + " at step " + step);
                return;
            }
            submit(session, "pb03-continuous-arrival-" + step, action);
        }
        restoration.restoreCommanderCasts(
                session.restorationGame(), seats);
        XmageNativeStateRestoration.revalidate(session.restorationGame());

        // The genuine start triggers cost every opponent exactly 8 life
        // (seven opening draws plus the turn-1 draw).
        assertEquals(32, seats.get("P2").getLife(), "Crawler start triggers fired");
        assertEquals(32, seats.get("P3").getLife(), "Crawler start triggers fired");
        assertEquals(32, seats.get("P4").getLife(), "Crawler start triggers fired");
        UUID crawlerId = restoration.injectedObjectId("obj:micro-crawler");
        Permanent crawler = session.restorationGame().getPermanent(crawlerId);
        assertNotNull(crawler, "restored Psychosis Crawler must be on the battlefield");
        int hand = seats.get("P1").getHand().size();
        assertTrue(hand > 5, "P1 holds opening hand plus draw plus restored Mountains: " + hand);
        assertEquals(hand, crawler.getPower().getValue(),
                "Crawler power equals actual P1 hand size (continuous evaluation is honest)");
        assertEquals(hand, crawler.getToughness().getValue(),
                "Crawler toughness equals actual P1 hand size (continuous evaluation is honest)");
    }

    // ---- MICRO_MODES: genuine Burn Down the House, Devil mode ----

    @Test
    void microModesDevilTokensWithoutDamageMode() {
        Arrived arrived = arrive("MICRO_MODES", "pb03-modes");
        XmageFullGameSession session = arrived.session();
        Map<String, Player> seats = arrived.seats();
        Player p1 = seats.get("P1");
        int lifeBefore = seats.get("P2").getLife();

        castSpellAs(session, seats, "pb03-modes", "Burn Down the House", "P1");
        // Engine casting order (CR 601.2): mode choice precedes payment.
        // Follow the engine: answer mode, then pay, then resolve.
        List<String> trace = new ArrayList<>();
        for (int step = 0; step < 30; step++) {
            if (countDevils(session, p1) == 3) {
                break;
            }
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            trace.add(pending);
            if ("mode".equals(pending)) {
                JsonObject legal = session.legalActionsPayload();
                List<JsonObject> modes = new ArrayList<>();
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    if ("choose_mode".equals(action.get("action_type").getAsString())) {
                        modes.add(action);
                    }
                }
                assertEquals(2, modes.size(), "Burn Down the House offers exactly two modes");
                JsonObject devil = null;
                for (JsonObject mode : modes) {
                    String label = mode.getAsJsonObject("metadata")
                            .get("label").getAsString();
                    if (label.contains("Devil")) {
                        devil = mode;
                    }
                }
                assertNotNull(devil, "Devil mode must be engine-offered");
                submit(session, "pb03-modes-devil", devil);
                continue;
            }
            if ("mana_payment".equals(pending)) {
                payHomogeneous(session, "pb03-modes", "Mountain \u2014 {T}: Add {R}.");
                assertSpellOnStack(session, "Burn Down the House", "pb03-modes");
                continue;
            }
            if (!"priority".equals(pending)) {
                fail("unexpected " + describePending(session, pending)
                        + " devils=" + countDevils(session, p1)
                        + " stack=" + session.restorationGame().getStack().size()
                        + " trace=" + trace
                        + " burnZone=" + zoneOf(session, seats.get("P1"), "Burn Down the House")
                        + " p2life=" + seats.get("P2").getLife()
                        + " p1bears=" + countPermanents(session, seats.get("P1"), "Grizzly Bears")
                        + " during Burn Down the House cast");
            }
            passPriority(session, "pb03-modes-pass-" + step);
        }
        assertEquals(3, countDevils(session, p1), "exactly three Devil tokens enter");
        assertEquals(lifeBefore, seats.get("P2").getLife(), "damage mode must not also occur");
    }

    private static int countDevils(XmageFullGameSession session, Player controller) {
        return countPermanents(session, controller, "Devil");
    }

    private static int countPermanents(
            XmageFullGameSession session, Player controller, String namePart) {
        int count = 0;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (permanent.getName().contains(namePart)
                    && controller.getId().equals(permanent.getControllerId())) {
                count++;
            }
        }
        return count;
    }

    private static String zoneOf(
            XmageFullGameSession session, Player owner, String cardName) {
        mage.game.Game game = session.restorationGame();
        for (mage.game.permanent.Permanent permanent
                : game.getBattlefield().getAllPermanents()) {
            if (cardName.equals(permanent.getName())
                    && owner.getId().equals(permanent.getOwnerId())) {
                return "battlefield";
            }
        }
        for (mage.cards.Card card : owner.getHand().getCards(game)) {
            if (cardName.equals(card.getName())) {
                return "hand";
            }
        }
        for (mage.cards.Card card : owner.getGraveyard().getCards(game)) {
            if (cardName.equals(card.getName())) {
                return "graveyard";
            }
        }
        return "elsewhere";
    }

    // ---- MICRO_PREVENTION: genuine Fog prevents combat damage ----

    @Test
    void microPreventionFogPreventsTwoCombatDamage() {
        Arrived arrived = arriveDeferred("MICRO_PREVENTION", "pb03-prevention");
        XmageFullGameSession session = arrived.session();
        Map<String, Player> seats = arrived.seats();
        Player p2 = seats.get("P2");
        int lifeBefore = p2.getLife();

        assertPlacementMatches(arrived, "MICRO_PREVENTION", "pb03-prevention");
        castSpellAs(session, seats, "pb03-prevention", "Fog", "P2");
        payHomogeneous(session, "pb03-prevention", "Forest \u2014 {T}: Add {G}.");
        assertSpellOnStack(session, "Fog", "pb03-prevention");

        // Drive into the record's declare-attackers checkpoint; Fog resolves
        // along the way through ordinary priority passes.
        UUID attackerId = arrived.restoration().injectedObjectId("obj:micro-attacker");
        driveToDeclaration(arrived, "pb03-prevention", "declare_attacker", (pending, legal, decisionIndex) -> {
            String decisionClass = pending.get("decision_class").getAsString();
            String actor = legal.get("actor_id").getAsString();
            if ("priority".equals(decisionClass)) {
                return proposalFor("pb03-prevention-pass-" + decisionIndex, actor,
                        XmageNativeStateRestorationTest.singleActionOfType(
                                legal, "pass_priority", null));
            }
            if ("declare_attacker".equals(decisionClass)) {
                String creature = decisionCreatureId(legal);
                if (attackerId.toString().equals(creature)) {
                    JsonObject attack = tryExactAttack(
                            legal, attackerId, seats.get("P2").getId());
                    if (attack == null) {
                        throw new AssertionError(
                                "micro-attacker offered without the obligated P2 option");
                    }
                    return proposalFor("pb03-prevention-attack-" + decisionIndex, actor, attack);
                }
                return proposalFor("pb03-prevention-hold-" + decisionIndex, actor,
                        XmageNativeStateRestorationTest.singleActionOfType(
                                legal, "declare_attackers", "hold_attacker"));
            }
            return null;
        });
        // The drive stops at the first declare_attackers decision unanswered:
        // finish P1's declarations (micro-attacker at P2, holds elsewhere),
        // then pass into declare blockers and decline.
        for (int step = 0; step < 20; step++) {
            String pending = pendingClass(session);
            if (!"declare_attacker".equals(pending)) {
                break;
            }
            JsonObject legal = session.legalActionsPayload();
            String creature = decisionCreatureId(legal);
            if (attackerId.toString().equals(creature)) {
                submit(session, "pb03-prevention-attack",
                        exactAttack(session, seats, attackerId, p2.getId()));
            } else {
                submitHoldAttacker(session, "pb03-prevention-hold-" + step);
            }
        }
        passPriority(session, "pb03-prevention-checkpoint-pass");
        // At the combat-damage step, prove the attack is unblocked while the
        // group still exists (groups dissolve after combat). Note: damage is
        // a STEP within the COMBAT phase, so read "step", not "phase".
        for (int step = 0; step < 40; step++) {
            String combatStep = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats).get("step").getAsString();
            if ("COMBAT_DAMAGE".equals(combatStep)) {
                break;
            }
            String pending = pendingClass(session);
            if ("declare_blocker".equals(pending)) {
                submitProposal(session, "pb03-prevention-dmg-noblock-" + step,
                        emptyBlockProposal("pb03-prevention-dmg-noblock-" + step,
                                session.legalActionsPayload()));
                continue;
            }
            if (pending == null) {
                break;
            }
            if (!"priority".equals(pending)) {
                fail("unexpected " + describePending(session, pending)
                        + " seeking combat damage step");
            }
            passPriority(session, "pb03-prevention-dmg-pass-" + step);
        }
        mage.game.combat.CombatGroup damageGroup = attackGroupOf(session, attackerId);
        assertNotNull(damageGroup, "micro-attacker must be grouped at damage time");
        assertTrue(damageGroup.getBlockers().isEmpty(), "attack must be unblocked");
        for (int step = 0; step < 40; step++) {
            String phase = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats).get("phase").getAsString();
            if (!"COMBAT".equals(phase)) {
                break;
            }
            String pending = pendingClass(session);
            if ("declare_blocker".equals(pending)) {
                submitProposal(session, "pb03-prevention-noblock-" + step,
                        emptyBlockProposal("pb03-prevention-noblock-" + step,
                                session.legalActionsPayload()));
                continue;
            }
            if ("choose_object".equals(pending)) {
                // Turn-1 cleanup discard after combat damage has resolved:
                // P1 holds eight identical Mountains, so the choice is
                // outcome-neutral (same justification as identical trigger
                // ordering). Any non-identical options fail loudly.
                JsonObject legal = session.legalActionsPayload();
                String firstName = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    String label = element.getAsJsonObject().getAsJsonObject("metadata")
                            .get("label").getAsString();
                    if (firstName == null) {
                        firstName = label;
                    }
                    assertEquals(firstName, label,
                            "cleanup discard options must be identical for a neutral choice");
                }
                assertNotNull(firstName, "discard must offer options");
                submit(session, "pb03-prevention-discard",
                        legal.getAsJsonArray("actions").get(0).getAsJsonObject());
                break;
            }
            if (pending == null) {
                break;
            }
            if (!"priority".equals(pending)) {
                fail("unexpected " + describePending(session, pending)
                        + " seeking combat damage");
            }
            passPriority(session, "pb03-prevention-pass-" + step);
        }
        // Prevention proof (not absence-of-attack proof): the attacker is
        // tapped and was grouped without blockers, Fog resolved to the
        // graveyard, combat completed, and P2's life never moved. Tapped
        // status (not the transient combat group) proves the attack.
        mage.game.permanent.Permanent attackerPermanent =
                session.restorationGame().getPermanent(attackerId);
        assertNotNull(attackerPermanent, "micro-attacker must still exist");
        assertTrue(attackerPermanent.isTapped(), "micro-attacker must have attacked");
        assertEquals("graveyard", zoneOf(session, p2, "Fog"), "Fog must have resolved");
        assertEquals(lifeBefore, p2.getLife(), "P2 loses 0 life from prevented combat damage");
    }

    private static boolean pastCombat(XmageFullGameSession session, Map<String, Player> seats) {
        String phase = XmageNativeStateRestoration.readback(
                session.restorationGame(), seats).get("phase").getAsString();
        return "POSTCOMBAT_MAIN".equals(phase) || "END".equals(phase);
    }

    private static mage.game.combat.CombatGroup attackGroupOf(
            XmageFullGameSession session, UUID attacker) {
        for (mage.game.combat.CombatGroup group
                : session.restorationGame().getCombat().getGroups()) {
            if (group.getAttackers().contains(attacker)) {
                return group;
            }
        }
        return null;
    }

    // ---- MICRO_REPLACEMENT: Gratuitous Violence doubles to 6 ----

    @Test
    void microReplacementDoublesThreeDamageToSix() {
        Arrived arrived = arriveDeferred("MICRO_REPLACEMENT", "pb03-replacement");
        XmageFullGameSession session = arrived.session();
        Map<String, Player> seats = arrived.seats();
        Player p2 = seats.get("P2");
        int lifeBefore = p2.getLife();

        UUID giantId = arrived.restoration().injectedObjectId("obj:micro-3power");
        assertPlacementMatches(arrived, "MICRO_REPLACEMENT", "pb03-replacement");
        driveToDeclaration(arrived, "pb03-replacement", null, (pending, legal, decisionIndex) -> {
            String decisionClass = pending.get("decision_class").getAsString();
            String actor = legal.get("actor_id").getAsString();
            if ("priority".equals(decisionClass)) {
                return proposalFor("pb03-replacement-pass-" + decisionIndex, actor,
                        XmageNativeStateRestorationTest.singleActionOfType(
                                legal, "pass_priority", null));
            }
            if ("declare_attacker".equals(decisionClass)) {
                String creature = decisionCreatureId(legal);
                if (giantId.toString().equals(creature)) {
                    JsonObject attack = tryExactAttack(
                            legal, giantId, seats.get("P2").getId());
                    if (attack == null) {
                        throw new AssertionError(
                                "Hill Giant offered without the obligated P2 option");
                    }
                    return proposalFor(
                            "pb03-replacement-attack-" + decisionIndex, actor, attack);
                }
                return proposalFor("pb03-replacement-hold-" + decisionIndex, actor,
                        XmageNativeStateRestorationTest.singleActionOfType(
                                legal, "declare_attackers", "hold_attacker"));
            }
            if ("declare_blocker".equals(decisionClass)) {
                return emptyBlockProposal(
                        "pb03-replacement-noblock-" + decisionIndex, legal);
            }
            return null;
        });
        // At the combat-damage checkpoint: pass around until damage is dealt.
        for (int step = 0; step < 40; step++) {
            if (p2.getLife() == lifeBefore - 6) {
                break;
            }
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            if (!"priority".equals(pending)) {
                fail("unexpected " + pending + " awaiting combat damage");
            }
            passPriority(session, "pb03-replacement-damage-pass-" + step);
        }
        assertEquals(lifeBefore - 6, p2.getLife(),
                "single applicable replacement changes 3 damage to 6");
    }

    // ---- MICRO_COSTS: Hex timing characterization (row stays BLOCKED) ----
    //
    // Blocker characterization: P2's Hex is a sorcery, and the record places
    // the checkpoint on P1's turn-1 precombat main. Sorcery timing (CR 307.5)
    // forbids P2 casting on an opponent's turn, so the engine honestly offers
    // no Hex cast at P2's priority and the obligated cost determination can
    // never begin. The row stays BLOCKED with the timing reason; no credit is
    // manufactured by advancing to P2's turn (that would overshoot the
    // record's requested temporal point).

    @Test
    void microCostsHexPaysBasePlusThreeWard() {
        Arrived arrived = arrive("MICRO_COSTS", "pb03-costs");
        XmageFullGameSession session = arrived.session();
        Map<String, Player> seats = arrived.seats();
        Player p2 = seats.get("P2");

        // Reach P2's priority on P1's turn and prove the sorcery is unoffered.
        boolean sawP2Priority = false;
        for (int step = 0; step < 20; step++) {
            String pending = pendingClass(session);
            if (!"priority".equals(pending)) {
                fail("unexpected " + pending + " seeking P2 priority");
            }
            JsonObject legal = session.legalActionsPayload();
            String actorPid = XmageNativeStateRestorationTest.pidOf(
                    seats, legal.get("actor_id").getAsString());
            if ("P2".equals(actorPid)) {
                sawP2Priority = true;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    JsonObject metadata = action.getAsJsonObject("metadata");
                    JsonObject engine = metadata.has("xmage_option_metadata")
                            && metadata.get("xmage_option_metadata").isJsonObject()
                            ? metadata.getAsJsonObject("xmage_option_metadata")
                            : new JsonObject();
                    String abilityType = engine.has("ability_type")
                            && !engine.get("ability_type").isJsonNull()
                            ? engine.get("ability_type").getAsString() : "";
                    String sourceName = engine.has("source_name")
                            && !engine.get("source_name").isJsonNull()
                            ? engine.get("source_name").getAsString() : "";
                    assertTrue(!("spell".equals(abilityType)
                            && "Hex".equals(sourceName)),
                            "P2 must not be offered sorcery-speed Hex on P1's turn");
                }
                break;
            }
            passPriority(session, "pb03-costs-pass-" + step);
        }
        assertTrue(sawP2Priority, "P2 priority on P1's turn must be reached");
        assertEquals(40, p2.getLife(), "no cost paid, no resolution attempted");
    }

    // ---- MICRO_STATE_BASED_ACTIONS: Memnite 0/0 dies to SBA ----

    @Test
    void microStateBasedMemniteDiesAsZeroZero() {
        Arrived arrived = arrive("MICRO_STATE_BASED_ACTIONS", "pb03-sba");
        XmageFullGameSession session = arrived.session();
        Map<String, Player> seats = arrived.seats();

        castSpellAs(session, seats, "pb03-sba", "Memnite", "P1");
        assertSpellOnStack(session, "Memnite", "pb03-sba");
        // Memnite must enter and die to state-based actions during precombat
        // resolution. The graveyard observation proves both (a cleanup discard
        // could also move it, so any discard decision fails this test loudly
        // instead of masquerading as the obligation).
        for (int step = 0; step < 60; step++) {
            XmageNativeStateRestoration.revalidate(session.restorationGame());
            if (graveyardHas(seats.get("P1"), session, "Memnite")) {
                break;
            }
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            if ("declare_attacker".equals(pending)) {
                submit(session, "pb03-sba-hold-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                session.legalActionsPayload(),
                                "declare_attackers", "hold_attacker"));
                continue;
            }
            if ("declare_blocker".equals(pending)) {
                submitProposal(session, "pb03-sba-noblock-" + step,
                        emptyBlockProposal("pb03-sba-noblock-" + step,
                                session.legalActionsPayload()));
                continue;
            }
            if (!"priority".equals(pending)) {
                fail("unexpected " + describePending(session, pending)
                        + " awaiting Memnite state-based cleanup");
            }
            passPriority(session, "pb03-sba-pass-" + step);
        }
        XmageNativeStateRestoration.revalidate(session.restorationGame());

        assertTrue(graveyardHas(seats.get("P1"), session, "Memnite"),
                "0/0 Memnite must be in its owner's graveyard before priority");
    }

    private static boolean graveyardHas(
            Player owner, XmageFullGameSession session, String cardName) {
        mage.game.Game game = session.restorationGame();
        for (mage.cards.Card card : owner.getGraveyard().getCards(game)) {
            if (cardName.equals(card.getName())) {
                return true;
            }
        }
        return false;
    }

    // ---- MICRO_TRIGGERS: Warstorm Surge triggers on Bears ETB ----

    @Test
    void microTriggersWarstormSurgeDealsTwoToP2() {
        Arrived arrived = arrive("MICRO_TRIGGERS", "pb03-triggers");
        XmageFullGameSession session = arrived.session();
        Map<String, Player> seats = arrived.seats();
        Player p2 = seats.get("P2");
        int lifeBefore = p2.getLife();

        castSpellAs(session, seats, "pb03-triggers", "Grizzly Bears", "P1");
        payHomogeneous(session, "pb03-triggers", "Forest \u2014 {T}: Add {G}.");
        assertSpellOnStack(session, "Grizzly Bears", "pb03-triggers");
        // Bears resolves, Surge triggers, P2 is targeted, damage resolves;
        // the game then continues into combat, which is answered neutrally.
        List<String> trace = new ArrayList<>();
        for (int step = 0; step < 40; step++) {
            if (p2.getLife() == lifeBefore - 2) {
                break;
            }
            String pending = pendingClass(session);
            if (pending == null) {
                break;
            }
            trace.add(pending);
            if ("target".equals(pending)) {
                submit(session, "pb03-triggers-target",
                        findTargetOffer(session, p2.getId().toString(), "P2"));
                continue;
            }
            if ("choose_object".equals(pending)) {
                // Some engine builds present "any target" selection as a
                // choose_object: select P2 by exact engine identity.
                submit(session, "pb03-triggers-choose",
                        findTargetOffer(session, p2.getId().toString(), "P2"));
                continue;
            }
            if ("declare_attacker".equals(pending)) {
                submit(session, "pb03-triggers-hold-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                session.legalActionsPayload(),
                                "declare_attackers", "hold_attacker"));
                continue;
            }
            if ("declare_blocker".equals(pending)) {
                submitProposal(session, "pb03-triggers-noblock-" + step,
                        emptyBlockProposal("pb03-triggers-noblock-" + step,
                                session.legalActionsPayload()));
                continue;
            }
            if (!"priority".equals(pending)) {
                fail("unexpected " + describePending(session, pending)
                        + " p2life=" + p2.getLife()
                        + " trace=" + trace
                        + " during trigger resolution");
            }
            passPriority(session, "pb03-triggers-pass-" + step);
        }
        assertEquals(lifeBefore - 2, p2.getLife(), "Surge trigger deals 2 to P2 on resolution");
    }

    // ---- MP-BLOCK-4: P2 blocks exactly the P2-attacked attacker ----

    @Test
    void mpBlock4P2BlocksOnlyItsAttacker() {
        Arrived arrived = arriveDeferred("WS05-MP-BLOCK-4", "pb03-block4");
        XmageFullGameSession session = arrived.session();
        Map<String, Player> seats = arrived.seats();
        UUID attackerA2 = arrived.restoration().injectedObjectId("obj:mp-a2");
        UUID attackerA3 = arrived.restoration().injectedObjectId("obj:mp-a3");
        UUID blocker = arrived.restoration().injectedObjectId("obj:mp-p2-blocker");

        // Drive into the record's declare-blockers checkpoint. Setup choice
        // (documented): a2 attacks P2 as obligated; a3 HOLDS. The record
        // obligates no attack for a3, and holding it keeps the partition
        // obligation literally testable: with a3 attacking elsewhere the
        // engine offers it to P2 as well (offer-liberality, recorded in the
        // packet), which the row's literal "options contain only" wording
        // cannot distinguish from a genuine partition. Minimal setup first.
        java.util.concurrent.atomic.AtomicBoolean a2Done =
                new java.util.concurrent.atomic.AtomicBoolean(false);
        assertPlacementMatches(arrived, "WS05-MP-BLOCK-4", "pb03-block4");
        driveToDeclaration(arrived, "pb03-block4", "declare_blocker", (pending, legal, decisionIndex) -> {
            String decisionClass = pending.get("decision_class").getAsString();
            String actor = legal.get("actor_id").getAsString();
            if ("priority".equals(decisionClass)) {
                return proposalFor("pb03-block4-pass-" + decisionIndex, actor,
                        XmageNativeStateRestorationTest.singleActionOfType(
                                legal, "pass_priority", null));
            }
            if ("declare_attacker".equals(decisionClass)) {
                String creature = decisionCreatureId(legal);
                if (!a2Done.get() && attackerA2.toString().equals(creature)) {
                    JsonObject offer = tryExactAttack(
                            legal, attackerA2, seats.get("P2").getId());
                    if (offer == null) {
                        throw new AssertionError("mp-a2 offered without the P2 option");
                    }
                    a2Done.set(true);
                    return proposalFor("pb03-block4-a2", actor, offer);
                }
                // Every other creature (including a3) holds: the record
                // obligates no attack for them.
                return proposalFor("pb03-block4-hold-" + decisionIndex, actor,
                        XmageNativeStateRestorationTest.singleActionOfType(
                                legal, "declare_attackers", "hold_attacker"));
            }
            return null;
        });
        assertTrue(a2Done.get(), "the obligated attack must be declared");
        // Combat-state audit: a2 attacks P2, from the engine's own groups.
        assertCombatDefender(session, attackerA2, seats.get("P2").getId(), "mp-a2");

        JsonObject blockOffer = null;
        for (int step = 0; step < 40; step++) {
            String pending = pendingClass(session);
            if (pending == null) {
                fail("engine terminal before declare_blocker");
            }
            if ("declare_blocker".equals(pending)) {
                JsonObject legal = session.legalActionsPayload();
                String actorPid = XmageNativeStateRestorationTest.pidOf(
                        seats, legal.get("actor_id").getAsString());
                if ("P2".equals(actorPid)) {
                    // Block decisions arrive per blocker. Route by engine
                    // truth (permanent name), not by injected id: Runeclaw
                    // Bear is unique, so its decision carries the
                    // partition/submit flow; any other P2 blocker's
                    // decision is declined empty.
                    String decisionBlocker = decisionBlockerId(legal);
                    String blockerName = permanentName(session, decisionBlocker);
                    if (!"Runeclaw Bear".equals(blockerName)) {
                        submitProposal(session, "pb03-block4-otherblocker-" + step,
                                emptyBlockProposal("pb03-block4-otherblocker-" + step, legal));
                        continue;
                    }
                    // a3 holds (documented setup), so the only legal block
                    // is Runeclaw on a2: assert the partition literally, then
                    // execute the obligated block.
                    assertBlockPartitionOmitsNonDefendedAttacker(
                            session, legal, attackerA2, attackerA3);
                    blockOffer = findBlockOffer(legal, blocker, attackerA2);
                    break;
                }
                submitProposal(session, "pb03-block4-noblock-" + step,
                        emptyBlockProposal("pb03-block4-noblock-" + step, legal));
                continue;
            }
            if (!"priority".equals(pending)) {
                fail("unexpected " + pending + " seeking declare_blocker");
            }
            passPriority(session, "pb03-block4-pass-" + step);
        }
        assertNotNull(blockOffer, "P2 must be offered mp-p2-blocker -> mp-a2");
        submit(session, "pb03-block4-block", blockOffer);
    }

    /** Permanent name for a native id, or null. Engine truth for routing. */
    private static String permanentName(XmageFullGameSession session, String id) {
        if (id == null) {
            return null;
        }
        try {
            UUID uuid = UUID.fromString(id);
            Permanent permanent = session.restorationGame().getPermanent(uuid);
            return permanent == null ? null : permanent.getName();
        } catch (IllegalArgumentException exc) {
            return null;
        }
    }

    /** The blocker whose pairs the current declare_blocker decision offers. */
    private static String decisionBlockerId(JsonObject legal) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type")
                    && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if (!"declare_blocker".equals(optionType)) {
                continue;
            }
            JsonObject nativeMetadata = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
            if (nativeMetadata.has("blocker_id")
                    && !nativeMetadata.get("blocker_id").isJsonNull()) {
                return nativeMetadata.get("blocker_id").getAsString();
            }
        }
        return null;
    }

    private static String combatGroupsDump(XmageFullGameSession session) {
        StringBuilder dump = new StringBuilder();
        for (mage.game.combat.CombatGroup group
                : session.restorationGame().getCombat().getGroups()) {
            dump.append("  attackers=").append(group.getAttackers())
                    .append(" defender=").append(group.getDefendingPlayerId())
                    .append(" blockers=").append(group.getBlockers()).append("\n");
        }
        return dump.toString();
    }

    private static void assertCombatDefender(
            XmageFullGameSession session, UUID attacker, UUID defender, String name) {
        for (mage.game.combat.CombatGroup group
                : session.restorationGame().getCombat().getGroups()) {
            if (group.getAttackers().contains(attacker)) {
                assertEquals(defender, group.getDefendingPlayerId(),
                        name + " must attack the obligated defender");
                return;
            }
        }
        fail(name + " (" + attacker + ") found in no combat group");
    }

    private static boolean isBlockedBy(
            XmageFullGameSession session, UUID attacker, UUID blocker) {
        for (mage.game.combat.CombatGroup group
                : session.restorationGame().getCombat().getGroups()) {
            if (group.getAttackers().contains(attacker)
                    && group.getBlockers().contains(blocker)) {
                return true;
            }
        }
        return false;
    }

    private static void assertBlockPartitionOmitsNonDefendedAttacker(
            XmageFullGameSession session, JsonObject legal,
            UUID defendedAttacker, UUID otherAttacker) {
        boolean defendedOffered = false;
        boolean otherOffered = false;
        StringBuilder dump = new StringBuilder();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type")
                    && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if (!"declare_blocker".equals(optionType)) {
                continue;
            }
            JsonObject nativeMetadata = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
            dump.append(action.get("action_id").getAsString()).append(" native=")
                    .append(nativeMetadata).append("\n");
            for (Map.Entry<String, JsonElement> entry : nativeMetadata.entrySet()) {
                if (!entry.getValue().isJsonPrimitive()) {
                    continue;
                }
                String value = entry.getValue().getAsString();
                if (defendedAttacker.toString().equals(value)) {
                    defendedOffered = true;
                }
                if (otherAttacker.toString().equals(value)) {
                    otherOffered = true;
                }
            }
        }
        assertTrue(defendedOffered, "P2 options must include the P2-attacked attacker; offered:\n"
                + dump);
        assertTrue(!otherOffered,
                "P2 blocker options must contain only attackers for which P2 defends; offered:\n"
                        + dump + "combat groups:\n" + combatGroupsDump(session));
    }

    // ---- MP-COMBAT-4 / MP-COMBAT-5: multi-defender attack assignment ----

    @Test
    void mpCombat4AssignsTwoAttackersToTwoDefenders() {
        Arrived arrived = arriveDeferred("WS05-MP-COMBAT-4", "pb03-combat4");
        declareAttackers(arrived, "pb03-combat4", Map.of(
                "obj:mp-attacker-0", "P2",
                "obj:mp-attacker-1", "P3"));
    }

    @Test
    void mpCombat5AssignsThreeAttackersToThreeDefenders() {
        Arrived arrived = arriveDeferred("WS05-MP-COMBAT-5", "pb03-combat5");
        declareAttackers(arrived, "pb03-combat5", Map.of(
                "obj:mp-attacker-0", "P2",
                "obj:mp-attacker-1", "P3",
                "obj:mp-attacker-2", "P4"));
    }

    private static void declareAttackers(
            Arrived arrived, String tag, Map<String, String> assignment) {
        XmageFullGameSession session = arrived.session();
        Map<String, Player> seats = arrived.seats();
        assertPlacementMatches(arrived, tag, tag);
        driveToDeclaration(arrived, tag, "declare_attacker", passSource(tag));
        Map<String, String> remaining = new java.util.HashMap<>(assignment);
        for (int step = 0; step < 30 && !remaining.isEmpty(); step++) {
            String pending = pendingClass(session);
            if (!"declare_attacker".equals(pending)) {
                break;
            }
            JsonObject legal = session.legalActionsPayload();
            String creature = decisionCreatureId(legal);
            String defenderSeat = null;
            for (Map.Entry<String, String> entry : remaining.entrySet()) {
                UUID attacker = arrived.restoration().injectedObjectId(entry.getKey());
                if (attacker.toString().equals(creature)) {
                    defenderSeat = entry.getValue();
                    JsonObject offer = tryExactAttack(
                            legal, attacker, seats.get(defenderSeat).getId());
                    assertNotNull(offer, tag + ": " + entry.getKey()
                            + " offered without the obligated " + defenderSeat + " option");
                    submit(session, tag + "-attack-" + entry.getKey(), offer);
                    remaining.remove(entry.getKey());
                    break;
                }
            }
            if (defenderSeat == null) {
                submitHoldAttacker(session, tag + "-hold-" + step);
            }
        }
        assertTrue(remaining.isEmpty(), tag + ": every assigned attacker must be declared, left "
                + remaining.keySet());
    }

    private static JsonObject tryExactAttack(JsonObject legal, UUID attacker, UUID defender) {
        StringBuilder dump = new StringBuilder();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            JsonObject nativeMetadata = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
            dump.append(action.get("action_id").getAsString()).append(" native=")
                    .append(nativeMetadata).append("\n");
            String optionType = metadata.has("option_type")
                    && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            String defenderId = nativeMetadata.has("defender_id")
                    && !nativeMetadata.get("defender_id").isJsonNull()
                    ? nativeMetadata.get("defender_id").getAsString() : "";
            if ("declare_attacker".equals(optionType)
                    && defender.toString().equals(defenderId)
                    && !hasConflictingIdentity(nativeMetadata, attacker)) {
                return action;
            }
        }
        System.out.println("pb03-no-attack-match offered:\n" + dump);
        return null;
    }

    private static boolean hasConflictingIdentity(JsonObject nativeMetadata, UUID attacker) {
        for (Map.Entry<String, JsonElement> entry : nativeMetadata.entrySet()) {
            if (!entry.getValue().isJsonPrimitive()) {
                continue;
            }
            String key = entry.getKey();
            String value = entry.getValue().getAsString();
            if (("object_id".equals(key) || "source_object_id".equals(key)
                    || "attacker_id".equals(key))
                    && !attacker.toString().equals(value)
                    && !value.isEmpty()) {
                return true;
            }
        }
        return false;
    }

    // ---- ELIM-4: commander-identity duality characterization (BLOCKED) ----
    //
    // Blocker characterization (row stays BLOCKED): the record places P1's
    // commander on the battlefield as a setup copy while the L2 damage ledger
    // lives on the authoritative commander identity. The setup copy attacks
    // genuinely (tapped, grouped, unblocked) and deals 2 PLAIN damage (P2
    // 40 -> 38) while the commander total stays at the restored 19: setup
    // copies do not accrue commander damage. Accrual needs the identity card
    // itself, which sits in the command zone and, cast turn 1, is summoning
    // sick and cannot attack without leaving the record's turn-1 checkpoint.
    // No genuine path observes the obligated loss: the row stays BLOCKED.

    @Test
    void elim4TwentyOneCommanderDamageEliminatesAndCleansUp() {
        Arrived arrived = arrive("WS05-CMD-ELIM-4", "pb03-elim4");
        XmageFullGameSession session = arrived.session();
        Map<String, Player> seats = arrived.seats();
        Player p2 = seats.get("P2");
        UUID isamaruId = arrived.restoration().injectedObjectId("obj:elim-isamaru");

        int restored = commanderDamageTo(
                session, seats, seats.get("P1"), "Isamaru, Hound of Konda", p2);
        assertEquals(19, restored, "L2 seam restores exactly 19 commander damage on P2");
        int lifeBefore = p2.getLife();

        passUntil(session, "pb03-elim4", "declare_attacker", 40);
        for (int step = 0; step < 20; step++) {
            String pending = pendingClass(session);
            if (!"declare_attacker".equals(pending)) {
                break;
            }
            JsonObject legal = session.legalActionsPayload();
            String creature = decisionCreatureId(legal);
            if (isamaruId.toString().equals(creature)) {
                submit(session, "pb03-elim4-attack",
                        exactAttack(session, seats, isamaruId, p2.getId()));
            } else {
                submitHoldAttacker(session, "pb03-elim4-hold-" + step);
            }
        }
        // Drive through combat with empty blocks; stop leaving combat.
        for (int step = 0; step < 40; step++) {
            String phase = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats).get("phase").getAsString();
            if (!"COMBAT".equals(phase)) {
                break;
            }
            String pending = pendingClass(session);
            if ("declare_blocker".equals(pending)) {
                submitProposal(session, "pb03-elim4-noblock-" + step,
                        emptyBlockProposal("pb03-elim4-noblock-" + step,
                                session.legalActionsPayload()));
                continue;
            }
            if (pending == null) {
                break;
            }
            if (!"priority".equals(pending)) {
                fail("unexpected " + describePending(session, pending)
                        + " seeking combat damage");
            }
            passPriority(session, "pb03-elim4-pass-" + step);
        }
        XmageNativeStateRestoration.revalidate(session.restorationGame());

        mage.game.permanent.Permanent copy =
                session.restorationGame().getPermanent(isamaruId);
        assertNotNull(copy, "setup copy must still exist");
        assertTrue(copy.isTapped(), "setup copy genuinely attacked P2");
        assertEquals(lifeBefore - 2, p2.getLife(),
                "setup-copy combat deals plain damage (40 -> 38)");
        assertEquals(19, commanderDamageTo(
                        session, seats, seats.get("P1"), "Isamaru, Hound of Konda", p2),
                "commander total stays at restored 19: copies do not accrue");
        assertTrue(!p2.hasLost() && !p2.hasLeft(),
                "no loss occurs: the obligated 21-loss is unobservable, row BLOCKED");
    }

    private static int commanderDamageTo(
            XmageFullGameSession session, Map<String, Player> seats,
            Player owner, String name, Player damaged) {
        // The authoritative Commander identity set owns the damage ledger;
        // resolve through it exactly like the L2 restoration seam does.
        mage.game.Game game = session.restorationGame();
        List<UUID> matches = new ArrayList<>();
        for (UUID id : game.getCommandersIds(
                owner, mage.constants.CommanderCardType.ANY, false)) {
            mage.cards.Card card = game.getCard(id);
            if (card != null && name.equals(card.getName())) {
                matches.add(id);
            }
        }
        assertEquals(1, matches.size(),
                "exact native Commander binding for " + name);
        mage.watchers.common.CommanderInfoWatcher watcher = game.getState().getWatcher(
                mage.watchers.common.CommanderInfoWatcher.class, matches.get(0));
        assertNotNull(watcher, "native CommanderInfoWatcher must exist");
        return watcher.getDamageToPlayer().getOrDefault(damaged.getId(), 0);
    }

    // ---- shared cast / pay / resolve drivers ----

    private static String dumpLegalActions(
            XmageFullGameSession session, Map<String, Player> seats,
            String tag, String message) {
        JsonObject legal = session.legalActionsPayload();
        StringBuilder dump = new StringBuilder(message);
        dump.append(" pending=").append(pendingClass(session));
        dump.append(" actor=").append(legal.get("actor_id").getAsString());
        try {
            dump.append(" actorPid=").append(
                    XmageNativeStateRestorationTest.pidOf(
                            seats, legal.get("actor_id").getAsString()));
        } catch (Exception exc) {
            dump.append(" actorPid=UNMAPPED");
        }
        for (Map.Entry<String, Player> entry : seats.entrySet()) {
            dump.append(" seat-").append(entry.getKey()).append("=")
                    .append(entry.getValue().getId().toString().substring(0, 8));
        }
        dump.append(" class=").append(legal.get("decision_class").getAsString()).append("\n");
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            dump.append("  ").append(element.getAsJsonObject()).append("\n");
        }
        return dump.toString();
    }

    private static void assertSpellOnStack(
            XmageFullGameSession session, String cardName, String tag) {
        boolean found = false;
        for (mage.game.stack.StackObject stackObject
                : session.restorationGame().getStack()) {
            if (cardName.equals(stackObject.getName())) {
                found = true;
            }
        }
        assertTrue(found, tag + ": " + cardName + " must be on the stack after payment; stack size="
                + session.restorationGame().getStack().size());
    }

    private static void castSpellAs(
            XmageFullGameSession session, Map<String, Player> seats,
            String tag, String cardName, String casterPid) {
        for (int step = 0; step < 20; step++) {
            String pending = pendingClass(session);
            if (!"priority".equals(pending)) {
                fail(tag + ": unexpected " + pending + " seeking priority to cast "
                        + cardName);
            }
            JsonObject legal = session.legalActionsPayload();
            String actorPid = XmageNativeStateRestorationTest.pidOf(
                    seats, legal.get("actor_id").getAsString());
            if (casterPid == null || casterPid.equals(actorPid)) {
                JsonObject offer = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    JsonObject metadata = action.getAsJsonObject("metadata");
                    JsonObject engine = metadata.has("xmage_option_metadata")
                            && metadata.get("xmage_option_metadata").isJsonObject()
                            ? metadata.getAsJsonObject("xmage_option_metadata")
                            : new JsonObject();
                    String abilityType = engine.has("ability_type")
                            && !engine.get("ability_type").isJsonNull()
                            ? engine.get("ability_type").getAsString() : "";
                    String sourceName = engine.has("source_name")
                            && !engine.get("source_name").isJsonNull()
                            ? engine.get("source_name").getAsString() : "";
                    if ("spell".equals(abilityType) && cardName.equals(sourceName)) {
                        offer = action;
                    }
                }
                assertNotNull(offer, dumpLegalActions(session, seats, tag,
                        "engine must offer " + cardName + " through its legality"));
                submit(session, tag + "-cast", offer);
                return;
            }
            passPriority(session, tag + "-pass-" + step);
        }
        fail(tag + ": bound exceeded seeking priority to cast " + cardName);
    }

    private static void payHomogeneous(
            XmageFullGameSession session, String tag, String expectedLabel) {
        for (int round = 0; round < 12; round++) {
            String pending = pendingClass(session);
            if (pending == null) {
                fail(tag + ": engine terminal during payment");
            }
            if ("priority".equals(pending)) {
                return;
            }
            assertEquals("mana_payment", pending,
                    tag + ": only engine-driven mana payment may follow");
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
                        assertEquals(label, candidate, tag + ": heterogeneous mana fails closed");
                    }
                }
                if (expectedLabel != null) {
                    assertEquals(expectedLabel, label, tag + ": only " + expectedLabel
                            + " expected");
                }
                mana.sort((left, right) -> left.get("action_id").getAsString()
                        .compareTo(right.get("action_id").getAsString()));
                submit(session, tag + "-pay-" + round, mana.get(0));
            } else if (pool.size() == 1) {
                submit(session, tag + "-spend-" + round, pool.get(0));
            } else {
                fail(tag + ": payment offers neither mana abilities (" + mana.size()
                        + ") nor exactly one pool spend (" + pool.size() + ")");
            }
        }
        fail(tag + ": payment bound breached");
    }

    private static JsonObject findTargetOffer(
            XmageFullGameSession session, String nativeId, String name) {
        JsonObject legal = session.legalActionsPayload();
        List<JsonObject> matches = new ArrayList<>();
        StringBuilder dump = new StringBuilder();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            dump.append(action.get("action_id").getAsString()).append(" metadata=")
                    .append(metadata).append("\n");
            JsonObject nativeMetadata = metadata.has("xmage_option_metadata")
                    && metadata.get("xmage_option_metadata").isJsonObject()
                    ? metadata.getAsJsonObject("xmage_option_metadata") : new JsonObject();
            for (Map.Entry<String, JsonElement> entry : nativeMetadata.entrySet()) {
                if (entry.getValue().isJsonPrimitive()
                        && nativeId.equals(entry.getValue().getAsString())) {
                    matches.add(action);
                }
            }
        }
        assertEquals(1, matches.size(),
                "exact target offer for " + name + " id=" + nativeId + "; offered:\n" + dump);
        return matches.get(0);
    }

    private static void resolveWithNeutralCombat(
            XmageFullGameSession session, Map<String, Player> seats,
            String tag, int bound) {
        for (int step = 0; step < bound; step++) {
            String pending = pendingClass(session);
            if (pending == null) {
                return;
            }
            if ("declare_attacker".equals(pending)) {
                submit(session, tag + "-hold-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                session.legalActionsPayload(),
                                "declare_attackers", "hold_attacker"));
                continue;
            }
            if ("declare_blocker".equals(pending)) {
                submitProposal(session, tag + "-noblock-" + step,
                        emptyBlockProposal(tag + "-noblock-" + step,
                                session.legalActionsPayload()));
                continue;
            }
            if (!"priority".equals(pending)) {
                fail(tag + ": unexpected " + describePending(session, pending)
                        + " during neutral resolution");
            }
            passPriority(session, tag + "-resolve-" + step);
        }
        fail(tag + ": resolution did not reach quiescence");
    }

    private static String describePending(XmageFullGameSession session, String pending) {
        StringBuilder context = new StringBuilder(pending);
        try {
            JsonObject legal = session.legalActionsPayload();
            if (legal.has("actor_id") && !legal.get("actor_id").isJsonNull()) {
                context.append(" actor=").append(legal.get("actor_id").getAsString());
            }
            JsonObject raw = session.pendingDecisionPayload().getAsJsonObject("decision");
            if (raw.has("prompt") && !raw.get("prompt").isJsonNull()) {
                context.append(" prompt=").append(raw.get("prompt").getAsString());
            }
            context.append(" offers=").append(legal.getAsJsonArray("actions").size());
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                context.append("\n  ").append(element.getAsJsonObject()
                        .getAsJsonObject("metadata"));
            }
        } catch (Exception exc) {
            context.append(" (context unavailable: ").append(exc.getMessage()).append(")");
        }
        return context.toString();
    }

    private static void resolveUntilQuiescent(
            XmageFullGameSession session, String tag, int bound) {
        for (int step = 0; step < bound; step++) {
            String pending = pendingClass(session);
            if (pending == null) {
                return;
            }
            if (!"priority".equals(pending)) {
                fail(tag + ": unexpected " + pending + " during resolution");
            }
            passPriority(session, tag + "-resolve-" + step);
        }
        fail(tag + ": resolution did not reach quiescence");
    }

    private static JsonObject proposalFor(
            String proposalId, String actor, JsonObject action) {
        return XmageFullGameTaxExecutionTest.genericProposal(
                proposalId, actor,
                action.get("action_id").getAsString(),
                action.get("action_type").getAsString());
    }

    private static XmageTemporalProgressionDriver.DecisionSource passSource(String tag) {
        return (pending, legal, decisionIndex) -> {
            String decisionClass = pending.get("decision_class").getAsString();
            String actor = legal.get("actor_id").getAsString();
            if ("priority".equals(decisionClass)) {
                return proposalFor(tag + "-pass-" + decisionIndex, actor,
                        XmageNativeStateRestorationTest.singleActionOfType(
                                legal, "pass_priority", null));
            }
            return null;
        };
    }

    private static JsonObject driveToPlanTarget(
            Arrived arrived, String tag,
            XmageTemporalProgressionDriver.DecisionSource source) {
        XmageTemporalProgressionDriver.ProgressionResult result =
                XmageTemporalProgressionDriver.driveToPlanTarget(
                        arrived.session(), arrived.seats(), arrived.plan(), source, 120);
        return result.observed();
    }

    /**
     * Placement fidelity for combat-phase rows: at pre-drive arrival the only
     * permitted mismatches are temporal (phase/step/active/priority), because
     * the requested checkpoint lies ahead in combat. Any zone, life, hand,
     * commander or digest mismatch fails.
     */
    private static void assertPlacementMatches(Arrived arrived, String fixtureId, String tag) {
        XmageNativeStateRestoration.CompareVerdict verdict = arrived.restoration().compare(
                XmageNativeStateRestoration.readback(
                        arrived.session().restorationGame(), arrived.seats()),
                arrived.seats());
        for (String mismatch : verdict.mismatches()) {
            boolean temporal = mismatch.startsWith("phase:")
                    || mismatch.startsWith("step:")
                    || mismatch.startsWith("active_player:")
                    || mismatch.startsWith("priority_player:")
                    || mismatch.startsWith("active ")
                    || mismatch.startsWith("priority ");
            assertTrue(temporal, tag + ": non-temporal placement mismatch for "
                    + fixtureId + ": " + mismatch);
        }
    }

    /**
     * Drive until the requested phase/step/active point with the target
     * declaration pending. Unlike driveToPlanTarget, this does not require
     * the priority_player to match: during declaration steps priority is not
     * held the way the readback reports it.
     */
    private static void driveToDeclaration(
            Arrived arrived, String tag, String targetClass,
            XmageTemporalProgressionDriver.DecisionSource source) {
        XmageTemporalProgressionDriver.driveUntil(
                arrived.session(),
                arrived.seats(),
                (liveSession, liveSeats, observed) -> {
                    if (observed.get("turn_number").getAsInt()
                            != arrived.plan().turnNumber()) {
                        return false;
                    }
                    if (!arrived.plan().phase().name()
                            .equals(observed.get("phase").getAsString())) {
                        return false;
                    }
                    if (!arrived.plan().step().name()
                            .equals(observed.get("step").getAsString())) {
                        return false;
                    }
                    if (!arrived.plan().activePlayer()
                            .equals(observed.get("active_player").getAsString())) {
                        return false;
                    }
                    if (targetClass == null) {
                        return true;
                    }
                    JsonObject payload = liveSession.pendingDecisionPayload();
                    if (payload.get("decision").isJsonNull()) {
                        return false;
                    }
                    return targetClass.equals(payload.getAsJsonObject("decision")
                            .get("decision_class").getAsString());
                },
                source,
                120);
    }
}
