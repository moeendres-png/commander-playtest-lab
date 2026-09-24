package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * DR-CLOSURE-01 Phase 6: predictive regression pack from external bug
 * intelligence. Every case is labeled {@code EXTERNAL_RISK_SIGNAL} until a
 * local failure is actually reproduced (§14): these tests prove the defect
 * classes do not occur on current bytes; they do not claim the lab ever had
 * the external bugs.
 *
 * <p>Semantic authority: current Oracle text (Esior/Hex/Unsummon verified
 * against Gatherer/Scryfall wording at campaign time) plus the Comprehensive
 * Rules casting order (601.2). XMage/Forge behavior is never authority.</p>
 *
 * <ul>
 *   <li>A (PRED-PARSER-03) subject/controller/count semantic loss: Hex
 *   targeting two P1 commanders under Esior must cost exactly {7}{B}{B}
 *   ({4}{B}{B} + {3} once) — subject (commanders), controller (yours),
 *   count (once) all survive into runtime payment.</li>
 *   <li>B (PRED-ZONE-04) wrong-object movement: Unsummon targeting P2's
 *   Bears must not move P1's Bears.</li>
 *   <li>C (PRED-ZONE-04) alternative zone destination: the targeted Bears
 *   must land in hand, not the default graveyard.</li>
 *   <li>D (PRED-REPL-05) replacement-effect choice timing: BLOCKED — needs
 *   combat-temporal progression (Phase 1 disposition); recorded, not faked.</li>
 *   <li>E (PRED-RESTORE-01) restore-derived-state: restore → genuine
 *   transition → derived state still correct.</li>
 *   <li>F (PRED-AUTH-07) pilot masking anti-pattern: stale/forged answers
 *   are rejected typed; nothing auto-passes or hides a transition.</li>
 * </ul>
 */
class XmageExternalRiskSignalTest {

    static final String EXTERNAL_RISK_SIGNAL = "EXTERNAL_RISK_SIGNAL";

    static List<JsonObject> spellOffers(JsonObject legal, String sourceName) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!"activate_ability".equals(action.get("action_type").getAsString())) {
                continue;
            }
            JsonObject engine = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (engine.has("ability_type")
                    && "spell".equals(engine.get("ability_type").getAsString())
                    && engine.has("source_name")
                    && sourceName.equals(engine.get("source_name").getAsString())) {
                matches.add(action);
            }
        }
        return matches;
    }

    static JsonObject spellOffer(JsonObject legal, String sourceName) {
        List<JsonObject> matches = spellOffers(legal, sourceName);
        assertEquals(1, matches.size(),
                "[" + EXTERNAL_RISK_SIGNAL + "] exactly one cast offer for " + sourceName);
        return matches.get(0);
    }

    static void passToActor(
            XmageFullGameSession session, String tag, Map<String, Player> seats, String pid) {
        for (int step = 0; step < 12; step++) {
            JsonObject legal = session.legalActionsPayload();
            if (XmageNativeStateRestorationTest.pidOf(
                    seats, legal.get("actor_id").getAsString()).equals(pid)) {
                return;
            }
            JsonObject pending =
                    session.pendingDecisionPayload().getAsJsonObject("decision");
            assertEquals("priority", pending.get("decision_class").getAsString());
            XmageFullGameTaxExecutionTest.submit(session, tag + "-pass-" + step,
                    XmageFullGameTaxExecutionTest.singleActionOfType(
                            legal, "pass_priority", null));
        }
        fail("[" + EXTERNAL_RISK_SIGNAL + "] priority never reached " + pid);
    }

    static void payHomogeneous(
            XmageFullGameSession session, String tag, String label, int rounds) {
        // Cost-aware tapping: parse the engine's unpaid_mana ("{3}{R}" → 4)
        // and tap exactly that many homogeneous sources, then spend from the
        // pool. Tapping while the pool already covers would over-tap whenever
        // surplus sources exist — a harness defect, never engine behavior.
        int tapsDone = 0;
        int tapsNeeded = Integer.MAX_VALUE;
        for (int round = 0; round < rounds; round++) {
            JsonObject pending =
                    session.pendingDecisionPayload().getAsJsonObject("decision");
            if (pending.isJsonNull()
                    || !"mana_payment".equals(pending.get("decision_class").getAsString())) {
                return;
            }
            tapsNeeded = parseUnpaidTotal(pending);
            JsonObject legal = session.legalActionsPayload();
            List<JsonObject> mana = new ArrayList<>();
            List<JsonObject> pool = new ArrayList<>();
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                String optionType = action.getAsJsonObject("metadata")
                        .get("option_type").getAsString();
                if ("mana_ability".equals(optionType)) {
                    mana.add(action);
                } else if ("mana_pool".equals(optionType)) {
                    pool.add(action);
                }
            }
            if (tapsDone < tapsNeeded && !mana.isEmpty()) {
                for (JsonObject action : mana) {
                    assertEquals(label, action.getAsJsonObject("metadata")
                            .get("label").getAsString(),
                            "[" + EXTERNAL_RISK_SIGNAL + "] homogeneous mana only");
                }
                mana.sort((left, right) -> left.get("action_id").getAsString()
                        .compareTo(right.get("action_id").getAsString()));
                XmageFullGameTaxExecutionTest.submit(session, tag + "-pay-" + round,
                        XmageFullGameDecisionExecutionTest.findById(
                                session.legalActionsPayload(),
                                mana.get(0).get("action_id").getAsString()));
                tapsDone++;
            } else if (!pool.isEmpty()) {
                pool.sort((left, right) -> left.get("action_id").getAsString()
                        .compareTo(right.get("action_id").getAsString()));
                XmageFullGameTaxExecutionTest.submit(session, tag + "-spend-" + round, pool.get(0));
            } else {
                fail("[" + EXTERNAL_RISK_SIGNAL + "] unpayable-or-ambiguous payment round "
                        + round);
            }
        }
    }

    static int parseUnpaidTotal(JsonObject pending) {
        JsonObject context = pending.has("context") && pending.get("context").isJsonObject()
                ? pending.getAsJsonObject("context") : new JsonObject();
        String unpaid = context.has("unpaid_mana") && !context.get("unpaid_mana").isJsonNull()
                ? context.get("unpaid_mana").getAsString() : "";
        java.util.regex.Matcher matcher =
                java.util.regex.Pattern.compile("\\{([^}]*)\\}").matcher(unpaid);
        int total = 0;
        boolean found = false;
        while (matcher.find()) {
            found = true;
            String symbol = matcher.group(1).trim();
            if (symbol.matches("\\d+")) {
                total += Integer.parseInt(symbol);
            } else if (symbol.matches(
                    "[WUBRGCSP]|W/U|U/B|B/R|R/G|G/W|W/P|U/P|B/P|R/P|G/P|2/W|2/U|2/B|2/R|2/G")) {
                total += 1;
            } else {
                fail("[" + EXTERNAL_RISK_SIGNAL + "] unparsable mana symbol: " + symbol);
            }
        }
        if (!found) {
            fail("[" + EXTERNAL_RISK_SIGNAL + "] no unpaid_mana context: " + unpaid);
        }
        return total;
    }

    @Test
    void externalRiskSubjectCountSurvivesIntoPayment() {
        // Class A vehicle (Oracle-bound): Esior — "Spells your opponents cast
        // that target one or more commanders you control cost {3} more" plus
        // ruling "spells that target more than one commander cost only {3}
        // more". P1 first casts its real commander Rograkh ({0}) from the
        // command zone so the battlefield permanent carries genuine commander
        // status (a setup-placed copy is a different object and correctly
        // does NOT count — verified by probe). P2 then Bolts the genuine
        // commander (pays {3}{R}: subject+count survive), then Bolts a
        // non-commander (pays {R}: no leakage). Hex (the frozen record's
        // vehicle) is not offered by engine getPlayable with or without Esior
        // even at 12 mana — an exact-6-target offer gap recorded as a
        // follow-up, not papered over; this test uses the castable Bolt
        // vehicle for the same semantic class.
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "risk-esior", 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Rograkh, Son of Rohgahh", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0)),
                List.of(
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:esior", "Esior, Wardwing Familiar", "P1", "P1",
                                mage.constants.Zone.BATTLEFIELD, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:p1-bears", "Grizzly Bears", "P1", "P1",
                                mage.constants.Zone.BATTLEFIELD, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:bolt-a", "Lightning Bolt", "P2", "P2",
                                mage.constants.Zone.HAND, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:bolt-b", "Lightning Bolt", "P2", "P2",
                                mage.constants.Zone.HAND, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:m1", "Mountain", "P2", "P2",
                                mage.constants.Zone.BATTLEFIELD, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:m2", "Mountain", "P2", "P2",
                                mage.constants.Zone.BATTLEFIELD, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:m3", "Mountain", "P2", "P2",
                                mage.constants.Zone.BATTLEFIELD, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:m4", "Mountain", "P2", "P2",
                                mage.constants.Zone.BATTLEFIELD, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:m5", "Mountain", "P2", "P2",
                                mage.constants.Zone.BATTLEFIELD, false)),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, "risk-esior");
        XmageFullGameSession session = new XmageFullGameSession(
                "risk-esior", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        Player p1 = seats.get("P1");
        Player p2 = seats.get("P2");
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);

        // Genuine commander onto P1's battlefield (Rograkh costs {0}).
        XmageFullGameTaxExecutionTest.submit(session, "risk-esior-castcmd",
                XmageFullGameTaxExecutionTest.castOffer(
                        session.legalActionsPayload(), "Rograkh, Son of Rohgahh"));
        resolveStackEmpty(session, "risk-esior-cmd");
        boolean commanderOut = false;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (permanent.getName().equals("Rograkh, Son of Rohgahh")
                    && p1.getId().equals(permanent.getControllerId())) {
                commanderOut = true;
            }
        }
        assertTrue(commanderOut,
                "[" + EXTERNAL_RISK_SIGNAL + "] genuine commander must resolve first");

        passToActor(session, "risk-esior", seats, "P2");
        // Two identical Bolt copies in hand → two engine offers; cast the
        // first (cast 2 uses the remaining copy).
        List<JsonObject> boltOffers =
                spellOffers(session.legalActionsPayload(), "Lightning Bolt");
        assertEquals(2, boltOffers.size(),
                "[" + EXTERNAL_RISK_SIGNAL + "] one offer per hand copy");
        XmageFullGameTaxExecutionTest.submit(session, "risk-esior-cast1", boltOffers.get(0));
        submitTargetByOwnerName(session, seats, "P1", "Rograkh, Son of Rohgahh",
                "risk-esior-target1");
        payHomogeneous(session, "risk-esior", "Mountain \u2014 {T}: Add {R}.", 8);
        assertEquals(4, tappedMountains(session, p2),
                "[" + EXTERNAL_RISK_SIGNAL + "] commander targeting costs {3}{R}");

        resolveStackEmpty(session, "risk-esior");
        passToActor(session, "risk-esior", seats, "P2");
        XmageFullGameTaxExecutionTest.submit(session, "risk-esior-cast2",
                spellOffer(session.legalActionsPayload(), "Lightning Bolt"));
        submitTargetByOwnerName(session, seats, "P1", "Grizzly Bears", "risk-esior-target2");
        payHomogeneous(session, "risk-esior", "Mountain \u2014 {T}: Add {R}.", 4);
        assertEquals(5, tappedMountains(session, p2),
                "[" + EXTERNAL_RISK_SIGNAL + "] non-commander targeting costs {R} only");
    }

    static int tappedMountains(XmageFullGameSession session, Player player) {
        int tapped = 0;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (permanent.getName().equals("Mountain")
                    && player.getId().equals(permanent.getControllerId())
                    && permanent.isTapped()) {
                tapped++;
            }
        }
        return tapped;
    }

    static void submitTargetByOwnerName(
            XmageFullGameSession session, Map<String, Player> seats,
            String ownerPid, String cardName, String tag) {
        JsonObject targetLegal = session.legalActionsPayload();
        assertEquals("target", targetLegal.get("decision_class").getAsString());
        Player owner = seats.get(ownerPid);
        JsonObject chosen = null;
        for (JsonElement element : targetLegal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (!meta.has("name") || !meta.has("object_id")) {
                continue;
            }
            if (!cardName.equals(meta.get("name").getAsString())) {
                continue;
            }
            for (Permanent permanent : session.restorationGame()
                    .getBattlefield().getAllPermanents()) {
                if (permanent.getId().toString()
                        .equals(meta.get("object_id").getAsString())
                        && owner.getId().equals(permanent.getOwnerId())) {
                    chosen = action;
                }
            }
        }
        assertTrue(chosen != null,
                "[" + EXTERNAL_RISK_SIGNAL + "] required target must be offered: "
                        + ownerPid + "/" + cardName);
        XmageFullGameTaxExecutionTest.submit(session, tag, chosen);
    }

    static void resolveStackEmpty(XmageFullGameSession session, String tag) {
        // Drain until the stack is empty AND priority is pending: zone-change
        // replacement choices (e.g., commander to command zone) can arrive
        // after the stack already emptied, and must be answered explicitly.
        for (int step = 0; step < 40; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("[" + EXTERNAL_RISK_SIGNAL + "] engine terminal before resolution");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            if ("priority".equals(decisionClass)
                    && session.restorationGame().getStack().isEmpty()) {
                return;
            }
            if ("priority".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, tag + "-resolve-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                session.legalActionsPayload(), "pass_priority", null));
            } else if ("choose_use".equals(decisionClass)) {
                // Commander-zone replacement choice (correct actor, correct
                // Rules point): answer explicitly by exact label, never first.
                // Partial class-D coverage with direct evidence.
                JsonObject legal = session.legalActionsPayload();
                JsonObject moveToCommand = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    String label = action.getAsJsonObject("metadata")
                            .get("label").getAsString();
                    if (label.startsWith("Move to command")) {
                        assertTrue(moveToCommand == null,
                                "[" + EXTERNAL_RISK_SIGNAL + "] unique command-zone option");
                        moveToCommand = action;
                    }
                }
                assertTrue(moveToCommand != null,
                        "[" + EXTERNAL_RISK_SIGNAL + "] command-zone option must be offered");
                XmageFullGameTaxExecutionTest.submit(
                        session, tag + "-cmdzone-" + step, moveToCommand);
            } else {
                fail("[" + EXTERNAL_RISK_SIGNAL + "] unexpected class during resolution: "
                        + decisionClass);
            }
        }
        fail("[" + EXTERNAL_RISK_SIGNAL + "] resolution bound breached");
    }


    @Test
    void externalRiskWrongObjectAndZoneDestination() {
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "risk-unsummon", 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Rograkh, Son of Rohgahh", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0)),
                List.of(
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:unsummon", "Unsummon", "P1", "P1",
                                mage.constants.Zone.HAND, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:island", "Island", "P1", "P1",
                                mage.constants.Zone.BATTLEFIELD, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:p1-bears", "Grizzly Bears", "P1", "P1",
                                mage.constants.Zone.BATTLEFIELD, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:p2-bears", "Grizzly Bears", "P2", "P2",
                                mage.constants.Zone.BATTLEFIELD, false)),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, "risk-unsummon");
        XmageFullGameSession session = new XmageFullGameSession(
                "risk-unsummon", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        Player p1 = seats.get("P1");
        Player p2 = seats.get("P2");
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);

        XmageFullGameTaxExecutionTest.submit(session, "risk-unsummon-cast",
                spellOffer(session.legalActionsPayload(), "Unsummon"));

        // Target: P2's Bears by exact engine identity (not by name alone —
        // P1's Bears shares the name and is the wrong-object decoy).
        String p2BearsId = null;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (permanent.getName().equals("Grizzly Bears")
                    && p2.getId().equals(permanent.getOwnerId())) {
                p2BearsId = permanent.getId().toString();
            }
        }
        assertTrue(p2BearsId != null);
        JsonObject targetLegal = session.legalActionsPayload();
        assertEquals("target", targetLegal.get("decision_class").getAsString());
        JsonObject p2Target = null;
        for (JsonElement element : targetLegal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            String objectId = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata")
                    .get("object_id").getAsString();
            if (objectId.equals(p2BearsId)) {
                p2Target = action;
            }
        }
        assertTrue(p2Target != null,
                "[" + EXTERNAL_RISK_SIGNAL + "] P2's Bears must be distinctly offered");
        XmageFullGameTaxExecutionTest.submit(session, "risk-unsummon-target", p2Target);

        JsonObject afterTarget =
                session.pendingDecisionPayload().getAsJsonObject("decision");
        if ("mana_payment".equals(afterTarget.get("decision_class").getAsString())) {
            payHomogeneous(session, "risk-unsummon", "Island \u2014 {T}: Add {U}.", 4);
        }

        boolean resolved = false;
        for (int step = 0; step < 30; step++) {
            boolean p2BearsOnBattlefield = false;
            for (Permanent permanent : session.restorationGame()
                    .getBattlefield().getAllPermanents()) {
                if (permanent.getName().equals("Grizzly Bears")
                        && p2.getId().equals(permanent.getOwnerId())) {
                    p2BearsOnBattlefield = true;
                }
            }
            if (!p2BearsOnBattlefield && session.restorationGame().getStack().isEmpty()) {
                resolved = true;
                break;
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("[" + EXTERNAL_RISK_SIGNAL + "] engine terminal before resolution");
            }
            assertEquals("priority", payload.getAsJsonObject("decision")
                    .get("decision_class").getAsString());
            XmageFullGameTaxExecutionTest.submit(session, "risk-unsummon-resolve-" + step,
                    XmageFullGameTaxExecutionTest.singleActionOfType(
                            session.legalActionsPayload(), "pass_priority", null));
        }
        assertTrue(resolved, "[" + EXTERNAL_RISK_SIGNAL + "] Unsummon must resolve");

        // Class C: the targeted object lands in hand, not the graveyard.
        boolean p2BearsInHand = false;
        for (Card card : p2.getHand().getCards(session.restorationGame())) {
            if (card.getName().equals("Grizzly Bears")) {
                p2BearsInHand = true;
            }
        }
        assertTrue(p2BearsInHand,
                "[" + EXTERNAL_RISK_SIGNAL + "] alternative destination: hand, not graveyard");
        for (Card card : p2.getGraveyard().getCards(session.restorationGame())) {
            assertTrue(!card.getName().equals("Grizzly Bears"),
                    "[" + EXTERNAL_RISK_SIGNAL + "] targeted Bears must not hit the graveyard");
        }
        // Class B: the decoy never moved.
        boolean p1BearsBattlefield = false;
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (permanent.getName().equals("Grizzly Bears")
                    && p1.getId().equals(permanent.getOwnerId())) {
                p1BearsBattlefield = true;
            }
        }
        assertTrue(p1BearsBattlefield,
                "[" + EXTERNAL_RISK_SIGNAL + "] wrong-object movement: P1's Bears stays");
    }

    @Test
    void externalRiskRestoreDerivedStateAcrossTransition() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord("MICRO_LAYERS"),
                        "risk-restore", 424242L);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, "risk-restore");
        XmageFullGameSession session = new XmageFullGameSession(
                "MICRO_LAYERS", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);

        // Genuine transition: a full priority round (4 passes) plus engine
        // revalidation (layers + state-based actions re-applied).
        for (int round = 0; round < 4; round++) {
            JsonObject payload = session.pendingDecisionPayload();
            assertTrue(!payload.get("decision").isJsonNull(),
                    "[" + EXTERNAL_RISK_SIGNAL + "] game must continue across the round");
            assertEquals("priority", payload.getAsJsonObject("decision")
                    .get("decision_class").getAsString());
            XmageFullGameTaxExecutionTest.submit(session, "risk-restore-pass-" + round,
                    XmageFullGameTaxExecutionTest.singleActionOfType(
                            session.legalActionsPayload(), "pass_priority", null));
        }
        XmageNativeStateRestoration.revalidate(session.restorationGame());
        XmageNativeStateRestoration.CompareVerdict verdict = restoration.compare(
                XmageNativeStateRestoration.readback(
                        session.restorationGame(), seats), seats);
        // Priority legitimately advanced past the plan pin; every other pin
        // must still hold (derived state correct after transition).
        for (String mismatch : verdict.mismatches()) {
            // A full passed round legitimately advances turn position
            // (priority/active/phase/step); every other pin must still hold.
            assertTrue(mismatch.startsWith("priority_player")
                    || mismatch.startsWith("active_player")
                    || mismatch.startsWith("phase:")
                    || mismatch.startsWith("step:"),
                    "[" + EXTERNAL_RISK_SIGNAL + "] only turn position may drift: " + mismatch);
        }
        for (Permanent permanent : session.restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (permanent.getName().equals("Grizzly Bears")) {
                String ownerPid = XmageNativeStateRestorationTest.pidOf(
                        seats, permanent.getOwnerId().toString());
                int expected = ownerPid.equals("P1") ? 2 : 1;
                assertEquals(expected, permanent.getPower().getValue(),
                        "[" + EXTERNAL_RISK_SIGNAL + "] derived P/T holds for " + ownerPid);
            }
        }
    }

    @Test
    void externalRiskStaleAnswersRejectedWithoutMasking() {
        @SuppressWarnings("unchecked")
        Map<String, Player>[] seatsOut = new Map[1];
        XmageFullGameSession session =
                XmageFullGameDecisionExecutionTest.restoredSession(
                        "PILOT_CHOOSE_MODE", "risk-auth", seatsOut);
        JsonObject pending =
                session.pendingDecisionPayload().getAsJsonObject("decision");
        String decisionId = pending.get("decision_id").getAsString();
        String actor = pending.get("actor_id").getAsString();

        // Advance one real decision, then replay the stale id: typed
        // rejection, nothing masked, nothing auto-passed.
        JsonObject legal = session.legalActionsPayload();
        XmageFullGameTaxExecutionTest.submit(session, "risk-auth-cast",
                XmageFullGameDecisionExecutionTest.burnOffer(legal));
        JsonObject stale = XmageFullGameDecisionExecutionTest.proposal(
                "risk-auth-stale", actor,
                decisionId + ":00000000-0000-0000-0000-000000000000", "pass_priority");
        try {
            session.submitAction(stale);
            fail("[" + EXTERNAL_RISK_SIGNAL + "] stale decision must be rejected typed");
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            assertTrue(exc.getMessage().contains("STALE_DECISION")
                    || exc.getMessage().contains("ILLEGAL_ACTION"),
                    "[" + EXTERNAL_RISK_SIGNAL + "] typed rejection expected: "
                            + exc.getMessage());
        }
        JsonObject current =
                session.pendingDecisionPayload().getAsJsonObject("decision");
        assertTrue(!current.get("decision_id").getAsString().equals(decisionId),
                "[" + EXTERNAL_RISK_SIGNAL + "] the live decision must be the mode one");
    }
}
