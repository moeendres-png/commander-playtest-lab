package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Authoritative pinned-engine execution tests for the six Chulane combo and finisher
 * lines (Refs #1179).
 *
 * <p>Requirements:
 * 1. COMBO-OWN-001: Shrieking Drake + Lonis + Academy Manufactor (2P, 4P, 6P positive, negative without Manufactor).
 * 2. COMBO-OWN-002: Whitemane Lion + Lonis + Academy Manufactor + Adrix (2P, 4P, 6P positive, negative without Adrix).
 * 3. COMBO-OWN-003: Chulane + Shrieking Drake + Simic Growth Chamber + Provisioner (2P, 4P, 6P positive, deckout negative).
 * 4. COMBO-OWN-004: Chulane + Whitemane Lion + Bounce-Land + Provisioner + Adrix (2P, 4P, 6P positive, negative without Adrix).
 * 5. FINISHER-OWN-005: Mechanized Production on Food with Killer Service + Manufactor + Adrix (4P win, 3P no win, 2P/6P, negative without Aura).
 * 6. FINISHER-OWN-006: Esix + Psychosis Crawler + Killer Service + Manufactor (2P, 4P, 6P positive, negative on empty hand & second token event).
 * </p>
 */
class XmageChulaneComboFinisherLinesTest {

    private static final String PINNED_ENGINE_SHA = "f4d12f6e80";

    // ---------------------------------------------------------------- helpers

    static int onBattlefield(Game game, Player player, String name) {
        int count = 0;
        for (Permanent p : game.getBattlefield().getAllPermanents()) {
            if (name.equals(p.getName()) && player.getId().equals(p.getControllerId())) {
                count++;
            }
        }
        return count;
    }

    static int inHand(Game game, Player player, String name) {
        int count = 0;
        for (mage.cards.Card c : player.getHand().getCards(game)) {
            if (name.equals(c.getName())) {
                count++;
            }
        }
        return count;
    }

    static boolean advancesPayment(JsonObject action) {
        if (action != null && action.has("metadata")) {
            JsonObject meta = action.getAsJsonObject("metadata");
            if (meta.has("xmage_option_metadata")) {
                JsonObject xmeta = meta.getAsJsonObject("xmage_option_metadata");
                if (xmeta.has("advances_payment") && !xmeta.get("advances_payment").isJsonNull()) {
                    return xmeta.get("advances_payment").getAsBoolean();
                }
            }
        }
        return true;
    }

    static JsonObject actionWithLabel(XmageMultiplayerScenario s, String labelPart) {
        JsonObject legal = s.session.legalActionsPayload();
        if (legal == null || !legal.has("actions")) return null;
        for (JsonElement e : legal.getAsJsonArray("actions")) {
            JsonObject a = e.getAsJsonObject();
            if (a.has("metadata") && a.getAsJsonObject("metadata").has("label")) {
                String label = a.getAsJsonObject("metadata").get("label").getAsString();
                if (label.contains(labelPart)) {
                    return a;
                }
            }
        }
        return null;
    }

    static JsonObject actionWithLabelAdvancing(XmageMultiplayerScenario s, String labelPart) {
        JsonObject legal = s.session.legalActionsPayload();
        if (legal == null || !legal.has("actions")) return null;
        for (JsonElement e : legal.getAsJsonArray("actions")) {
            JsonObject a = e.getAsJsonObject();
            if (a.has("metadata") && a.getAsJsonObject("metadata").has("label")) {
                String label = a.getAsJsonObject("metadata").get("label").getAsString();
                if (label.contains(labelPart) && advancesPayment(a)) {
                    return a;
                }
            }
        }
        return null;
    }

    static JsonObject firstAction(XmageMultiplayerScenario s) {
        JsonObject legal = s.session.legalActionsPayload();
        if (legal == null || !legal.has("actions")) return null;
        JsonArray arr = legal.getAsJsonArray("actions");
        return arr.size() > 0 ? arr.get(0).getAsJsonObject() : null;
    }

    static void stepDecision(XmageMultiplayerScenario s, String preferredChoice) {
        JsonObject payload = s.session.pendingDecisionPayload();
        assertTrue(payload.get("failure").isJsonNull(), "engine lane failure: " + payload.get("failure"));
        String cls = s.decisionClass();
        if (cls == null) return;

        switch (cls) {
            case "priority" -> {
                JsonObject pass = s.action("pass_priority", "Pass");
                if (pass != null) {
                    s.submit(pass);
                } else {
                    fail("priority expected pass_priority, available: " + s.labels());
                }
            }
            case "mana_payment" -> {
                // Spend floating pool mana first (only if it actually advances payment)
                JsonObject spend = actionWithLabelAdvancing(s, "Spend ");
                if (spend != null) {
                    s.submit(spend);
                    return;
                }
                // Try Treasure mana
                JsonObject treasure = actionWithLabelAdvancing(s, "Treasure");
                if (treasure != null) {
                    s.submit(treasure);
                    return;
                }
                // Try basic lands
                for (String land : List.of("Island", "Plains", "Forest")) {
                    JsonObject landAct = actionWithLabelAdvancing(s, land);
                    if (landAct != null) {
                        s.submit(landAct);
                        return;
                    }
                }
                fail("mana_payment could not satisfy cost, available: " + s.labels());
            }
            case "choose_object", "target", "choose_choice", "choose_mode", "choice", "choose_use" -> {
                if (preferredChoice != null) {
                    JsonObject preferred = actionWithLabel(s, preferredChoice);
                    if (preferred != null) {
                        s.submit(preferred);
                        return;
                    }
                }
                // Automatic intelligent defaults for combo loops:
                // Esix copying Psychosis Crawler
                JsonObject crawler = actionWithLabel(s, "Psychosis Crawler");
                if (crawler != null) {
                    s.submit(crawler);
                    return;
                }
                // Tireless Provisioner: choose Treasure
                JsonObject treasure = actionWithLabel(s, "Treasure");
                if (treasure != null) {
                    s.submit(treasure);
                    return;
                }
                // Simic Growth Chamber (land drop or bounce self)
                JsonObject chamber = actionWithLabel(s, "Simic Growth Chamber");
                if (chamber != null) {
                    s.submit(chamber);
                    return;
                }
                // Self-bounce creatures
                JsonObject drake = actionWithLabel(s, "Shrieking Drake");
                if (drake != null) {
                    s.submit(drake);
                    return;
                }
                JsonObject lion = actionWithLabel(s, "Whitemane Lion");
                if (lion != null) {
                    s.submit(lion);
                    return;
                }
                // For color choices from Treasure: match preferred card/color context
                if ("Shrieking Drake".equals(preferredChoice) || "Blue".equals(preferredChoice)) {
                    JsonObject blue = actionWithLabel(s, "Blue");
                    if (blue != null) {
                        s.submit(blue);
                        return;
                    }
                }
                if ("Whitemane Lion".equals(preferredChoice) || "White".equals(preferredChoice)) {
                    JsonObject white = actionWithLabel(s, "White");
                    if (white != null) {
                        s.submit(white);
                        return;
                    }
                }
                JsonObject white = actionWithLabel(s, "White");
                if (white != null) {
                    s.submit(white);
                    return;
                }
                JsonObject blue = actionWithLabel(s, "Blue");
                if (blue != null) {
                    s.submit(blue);
                    return;
                }
                JsonObject green = actionWithLabel(s, "Green");
                if (green != null) {
                    s.submit(green);
                    return;
                }
                JsonObject first = firstAction(s);
                if (first != null) {
                    s.submit(first);
                } else {
                    fail(cls + " has no legal action, available: " + s.labels());
                }
            }
            case "yes_no" -> {
                JsonObject yes = actionWithLabel(s, "Yes");
                if (yes != null) {
                    s.submit(yes);
                } else {
                    JsonObject first = firstAction(s);
                    if (first != null) s.submit(first);
                    else fail("yes_no has no legal action: " + s.labels());
                }
            }
            case "order", "order_triggers", "trigger_order", "replacement_effect" -> {
                JsonObject first = firstAction(s);
                if (first != null) {
                    s.submit(first);
                } else {
                    fail(cls + " has no legal action: " + s.labels());
                }
            }
            default -> fail("unhandled decision class " + cls + " for " + s.actor() + ": " + s.labels());
        }
    }

    static void passPriorityUntilStackEmpty(XmageMultiplayerScenario s, int maxSteps, String preferredChoice) {
        Game game = s.session.restorationGame();
        for (int i = 0; i < maxSteps; i++) {
            if ("priority".equals(s.decisionClass()) && game.getStack().isEmpty()) {
                return;
            }
            // System.out.println("Step " + i + " " + s.actor() + " " + s.decisionClass() + " " + s.labels());
            stepDecision(s, preferredChoice);
        }
        fail("stack did not empty within " + maxSteps + " steps, pending: " + s.decisionClass() + " for " + s.actor() + " " + s.labels() + " stack=" + game.getStack().size());
    }

    // ---------------------------------------------------------------- COMBO-OWN-001

    @ParameterizedTest(name = "COMBO-OWN-001 positive: Drake + Lonis + Manufactor at {0}P")
    @ValueSource(ints = {2, 4, 6})
    void testCombo001PositiveTwoLoopsSelfFinancing(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        // P1 setup: Lonis and Manufactor on battlefield, 1 Island for first cast
        objects.add(XmageMultiplayerScenario.obj("P1", "Lonis, Cryptozoologist", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Academy Manufactor", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Island", 3, Zone.BATTLEFIELD));
        // Shrieking Drake in hand
        objects.add(XmageMultiplayerScenario.obj("P1", "Shrieking Drake", 10, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "c001-pos-" + playerCount + "p", playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // Precondition
        assertEquals(1, onBattlefield(game, p1, "Lonis, Cryptozoologist"));
        assertEquals(1, onBattlefield(game, p1, "Academy Manufactor"));
        assertEquals(1, inHand(game, p1, "Shrieking Drake"));
        assertEquals(0, onBattlefield(game, p1, "Clue Token"));
        assertEquals(0, onBattlefield(game, p1, "Food Token"));
        assertEquals(0, onBattlefield(game, p1, "Treasure Token"));

        // Loop 1: Cast Shrieking Drake paying {U} with Island
        JsonObject cast1 = s.action("activate_ability", "Cast Shrieking Drake");
        assertNotNull(cast1, "P1 must have action to cast Shrieking Drake");
        s.submit(cast1);
        passPriorityUntilStackEmpty(s, 50, "Shrieking Drake");

        // After Loop 1: Drake bounced itself to hand; Manufactor created 1 Clue, 1 Food, 1 Treasure
        assertEquals(1, inHand(game, p1, "Shrieking Drake"), "Drake must have returned to hand");
        assertEquals(1, onBattlefield(game, p1, "Clue Token"), "1 Clue created");
        assertEquals(1, onBattlefield(game, p1, "Food Token"), "1 Food created");
        assertEquals(1, onBattlefield(game, p1, "Treasure Token"), "1 Treasure created");

        // Loop 2: Recast Shrieking Drake paying {U} with the Treasure token!
        JsonObject cast2 = s.action("activate_ability", "Cast Shrieking Drake");
        assertNotNull(cast2, "P1 must be able to recast Shrieking Drake via Treasure");
        s.submit(cast2);
        passPriorityUntilStackEmpty(s, 50, "Shrieking Drake");

        // After Loop 2: Drake returned to hand again; 2 Clues, 2 Foods, 1 Treasure (1 spent, 1 newly created)
        assertEquals(1, inHand(game, p1, "Shrieking Drake"), "Drake back in hand after loop 2");
        assertEquals(2, onBattlefield(game, p1, "Clue Token"), "2 total Clues after 2 loops");
        assertEquals(2, onBattlefield(game, p1, "Food Token"), "2 total Foods after 2 loops");
        assertEquals(1, onBattlefield(game, p1, "Treasure Token"), "1 net Treasure remaining (self-financing)");
    }

    @Test
    @DisplayName("COMBO-OWN-001 negative: without Manufactor, Lonis creates Clue only (not self-financing)")
    void testCombo001NegativeWithoutManufactorNotSelfFinancing() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        // P1 setup: Lonis on battlefield, 1 Island for first cast, NO Manufactor
        objects.add(XmageMultiplayerScenario.obj("P1", "Lonis, Cryptozoologist", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Island", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Shrieking Drake", 10, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "c001-neg-4p", 4, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // Cast Shrieking Drake paying with Island
        s.submit(s.action("activate_ability", "Cast Shrieking Drake"));
        passPriorityUntilStackEmpty(s, 50, "Shrieking Drake");

        // Verify: Lonis created only 1 Clue; 0 Treasure created
        assertEquals(1, onBattlefield(game, p1, "Clue Token"));
        assertEquals(0, onBattlefield(game, p1, "Treasure Token"), "No Treasure created without Manufactor");
        assertEquals(0, onBattlefield(game, p1, "Food Token"), "No Food created without Manufactor");
        assertEquals(1, inHand(game, p1, "Shrieking Drake"));

        // Island is tapped, no Treasure exists -> Drake cannot be recast
        JsonObject recast = s.action("activate_ability", "Cast Shrieking Drake");
        boolean canCast = recast != null && recast.getAsJsonObject("metadata").get("submission_ready").getAsBoolean();
        assertFalse(canCast, "Drake cannot be recast: not self-financing without Manufactor");
    }

    // ---------------------------------------------------------------- COMBO-OWN-002

    @ParameterizedTest(name = "COMBO-OWN-002 positive: Lion + Lonis + Manufactor + Adrix at {0}P")
    @ValueSource(ints = {2, 4, 6})
    void testCombo002PositiveTwoLoopsSelfFinancingZeroSurplusMana(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        // P1 setup: Lonis, Manufactor, and Adrix on battlefield, 2 Plains for initial cast
        objects.add(XmageMultiplayerScenario.obj("P1", "Lonis, Cryptozoologist", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Academy Manufactor", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Adrix and Nev, Twincasters", 3, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Plains", 4, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Plains", 5, Zone.BATTLEFIELD));
        // Whitemane Lion in hand
        objects.add(XmageMultiplayerScenario.obj("P1", "Whitemane Lion", 10, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "c002-pos-" + playerCount + "p", playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // Precondition
        assertEquals(1, onBattlefield(game, p1, "Lonis, Cryptozoologist"));
        assertEquals(1, onBattlefield(game, p1, "Academy Manufactor"));
        assertEquals(1, onBattlefield(game, p1, "Adrix and Nev, Twincasters"));
        assertEquals(1, inHand(game, p1, "Whitemane Lion"));
        assertEquals(0, onBattlefield(game, p1, "Clue Token"));
        assertEquals(0, onBattlefield(game, p1, "Food Token"));
        assertEquals(0, onBattlefield(game, p1, "Treasure Token"));

        // Loop 1: Cast Whitemane Lion paying {1}{W} with 2 Plains
        JsonObject cast1 = s.action("activate_ability", "Cast Whitemane Lion");
        assertNotNull(cast1, "P1 must have action to cast Whitemane Lion");
        s.submit(cast1);
        passPriorityUntilStackEmpty(s, 60, "Whitemane Lion");

        // After Loop 1: Lion bounced itself to hand.
        // Lonis investigates -> Manufactor creates 1 each -> Adrix doubles to 2 Clues, 2 Foods, 2 Treasures.
        assertEquals(1, inHand(game, p1, "Whitemane Lion"), "Lion must have returned to hand");
        assertEquals(2, onBattlefield(game, p1, "Clue Token"), "2 Clues created via Adrix doubling");
        assertEquals(2, onBattlefield(game, p1, "Food Token"), "2 Foods created via Adrix doubling");
        assertEquals(2, onBattlefield(game, p1, "Treasure Token"), "2 Treasures created via Adrix doubling");

        // Loop 2: Recast Whitemane Lion paying {1}{W} using the 2 Treasure tokens
        JsonObject cast2 = s.action("activate_ability", "Cast Whitemane Lion");
        assertNotNull(cast2, "P1 must be able to recast Whitemane Lion via 2 Treasures");
        s.submit(cast2);
        passPriorityUntilStackEmpty(s, 60, "Whitemane Lion");

        // After Loop 2: 2 Treasures spent, 2 new Treasures created -> net 0 surplus Treasures!
        // Clues and Foods grow by +2 each loop.
        assertEquals(1, inHand(game, p1, "Whitemane Lion"), "Lion back in hand after loop 2");
        assertEquals(4, onBattlefield(game, p1, "Clue Token"), "4 total Clues after 2 loops");
        assertEquals(4, onBattlefield(game, p1, "Food Token"), "4 total Foods after 2 loops");
        assertEquals(2, onBattlefield(game, p1, "Treasure Token"), "2 Treasures remaining: net 0 surplus mana");
    }

    @Test
    @DisplayName("COMBO-OWN-002 negative: without Adrix, only 1 Treasure created for {1}{W} cost (net deficit, not self-financing)")
    void testCombo002NegativeWithoutAdrixNotSelfFinancing() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        // P1 setup: Lonis + Manufactor on battlefield, NO Adrix, 2 Plains for initial cast
        objects.add(XmageMultiplayerScenario.obj("P1", "Lonis, Cryptozoologist", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Academy Manufactor", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Plains", 3, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Plains", 4, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Whitemane Lion", 10, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "c002-neg-4p", 4, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // Cast Whitemane Lion paying with 2 Plains
        s.submit(s.action("activate_ability", "Cast Whitemane Lion"));
        passPriorityUntilStackEmpty(s, 60, "Whitemane Lion");

        // Verify: Manufactor without Adrix creates exactly 1 of each token
        assertEquals(1, onBattlefield(game, p1, "Clue Token"));
        assertEquals(1, onBattlefield(game, p1, "Food Token"));
        assertEquals(1, onBattlefield(game, p1, "Treasure Token"));
        assertEquals(1, inHand(game, p1, "Whitemane Lion"));

        // Both Plains are tapped, only 1 Treasure token exists. Whitemane Lion costs {1}{W} (2 mana).
        JsonObject recast = s.action("activate_ability", "Cast Whitemane Lion");
        boolean canCast = recast != null && recast.getAsJsonObject("metadata").get("submission_ready").getAsBoolean();
        assertFalse(canCast, "Lion cannot be recast: 1 Treasure cannot pay {1}{W} cost without Adrix");
    }

    // ---------------------------------------------------------------- COMBO-OWN-003

    @ParameterizedTest(name = "COMBO-OWN-003 positive: Chulane + Drake + Growth Chamber + Provisioner at {0}P")
    @ValueSource(ints = {2, 4, 6})
    void testCombo003PositiveTwoLoopsSelfFinancingWithDraw(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        // P1 setup: Chulane and Provisioner on battlefield, 1 Island for first cast
        objects.add(XmageMultiplayerScenario.obj("P1", "Chulane, Teller of Tales", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Tireless Provisioner", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Island", 3, Zone.BATTLEFIELD));
        // Drake and Simic Growth Chamber in hand
        objects.add(XmageMultiplayerScenario.obj("P1", "Shrieking Drake", 10, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Simic Growth Chamber", 11, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "c003-pos-" + playerCount + "p", playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // Precondition
        assertEquals(1, onBattlefield(game, p1, "Chulane, Teller of Tales"));
        assertEquals(1, onBattlefield(game, p1, "Tireless Provisioner"));
        assertEquals(1, inHand(game, p1, "Shrieking Drake"));
        assertEquals(1, inHand(game, p1, "Simic Growth Chamber"));
        assertEquals(0, onBattlefield(game, p1, "Treasure Token"));
        int initialHandSize = p1.getHand().size();

        // Loop 1: Cast Shrieking Drake paying {U} with Island
        JsonObject cast1 = s.action("activate_ability", "Cast Shrieking Drake");
        assertNotNull(cast1, "P1 must have action to cast Shrieking Drake");
        s.submit(cast1);
        passPriorityUntilStackEmpty(s, 60, "Blue");

        // After Loop 1: Drake and Chamber returned to hand, 1 card drawn, 1 Treasure created
        assertEquals(1, inHand(game, p1, "Shrieking Drake"), "Drake back in hand");
        assertEquals(1, inHand(game, p1, "Simic Growth Chamber"), "Chamber back in hand");
        assertEquals(1, onBattlefield(game, p1, "Treasure Token"), "1 Treasure created by Provisioner");
        assertEquals(initialHandSize + 1, p1.getHand().size(), "Chulane drew 1 card");

        // Loop 2: Recast Shrieking Drake paying {U} with the Treasure token
        JsonObject cast2 = s.action("activate_ability", "Cast Shrieking Drake");
        assertNotNull(cast2, "P1 must be able to recast Shrieking Drake via Treasure");
        s.submit(cast2);
        passPriorityUntilStackEmpty(s, 60, "Blue");

        // After Loop 2: 1 Treasure consumed and 1 newly created -> 1 net Treasure, another card drawn!
        assertEquals(1, inHand(game, p1, "Shrieking Drake"), "Drake back in hand after loop 2");
        assertEquals(1, inHand(game, p1, "Simic Growth Chamber"), "Chamber back in hand after loop 2");
        assertEquals(1, onBattlefield(game, p1, "Treasure Token"), "1 net Treasure remains (self-financing)");
        assertEquals(initialHandSize + 2, p1.getHand().size(), "Chulane drew another card (2 total draws)");
    }

    @Test
    @DisplayName("COMBO-OWN-003 negative: deckout on empty library causes loss on Chulane draw")
    void testCombo003NegativeDeckoutCausesLoss() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Chulane, Teller of Tales", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Tireless Provisioner", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Island", 3, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Shrieking Drake", 10, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Simic Growth Chamber", 11, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "c003-neg-deckout", 4, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // Simulate library depletion: empty P1's library
        p1.getLibrary().clear();
        assertEquals(0, p1.getLibrary().size(), "P1 library must be empty");
        assertFalse(p1.hasLost(), "P1 has not lost yet before draw attempt");

        // Cast Shrieking Drake: Chulane cast trigger attempts to draw from empty library
        s.submit(s.action("activate_ability", "Cast Shrieking Drake"));
        passPriorityUntilStackEmpty(s, 60, null);

        // Engine rules verification: player lost the game from deckout (CR 704.5b)
        assertTrue(p1.hasLost(), "P1 must have lost the game after drawing from an empty library");
    }

    @Test
    @DisplayName("COMBO-OWN-003 negative: without Provisioner, land entry produces no mana (not self-financing)")
    void testCombo003NegativeWithoutProvisionerNotSelfFinancing() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Chulane, Teller of Tales", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Island", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Shrieking Drake", 10, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Simic Growth Chamber", 11, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "c003-neg-noprovisioner", 4, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // Cast Drake with Island
        s.submit(s.action("activate_ability", "Cast Shrieking Drake"));
        passPriorityUntilStackEmpty(s, 60, null);

        // No Treasure exists, Island tapped -> cannot recast
        assertEquals(0, onBattlefield(game, p1, "Treasure Token"));
        JsonObject recast = s.action("activate_ability", "Cast Shrieking Drake");
        boolean canCast = recast != null && recast.getAsJsonObject("metadata").get("submission_ready").getAsBoolean();
        assertFalse(canCast, "Drake cannot be recast without Provisioner mana generation");
    }

    // ---------------------------------------------------------------- COMBO-OWN-004

    @ParameterizedTest(name = "COMBO-OWN-004 positive: Chulane + Lion + BounceLand + Provisioner + Adrix at {0}P")
    @ValueSource(ints = {2, 4, 6})
    void testCombo004PositiveTwoLoopsSelfFinancingZeroSurplusMana(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        // P1 setup: Chulane, Provisioner, and Adrix on battlefield, 2 Plains for initial cast
        objects.add(XmageMultiplayerScenario.obj("P1", "Chulane, Teller of Tales", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Tireless Provisioner", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Adrix and Nev, Twincasters", 3, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Plains", 4, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Plains", 5, Zone.BATTLEFIELD));
        // Whitemane Lion and Simic Growth Chamber in hand
        objects.add(XmageMultiplayerScenario.obj("P1", "Whitemane Lion", 10, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Simic Growth Chamber", 11, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "c004-pos-" + playerCount + "p", playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // Precondition
        assertEquals(1, onBattlefield(game, p1, "Chulane, Teller of Tales"));
        assertEquals(1, onBattlefield(game, p1, "Tireless Provisioner"));
        assertEquals(1, onBattlefield(game, p1, "Adrix and Nev, Twincasters"));
        assertEquals(1, inHand(game, p1, "Whitemane Lion"));
        assertEquals(1, inHand(game, p1, "Simic Growth Chamber"));
        assertEquals(0, onBattlefield(game, p1, "Treasure Token"));
        int initialHandSize = p1.getHand().size();

        // Loop 1: Cast Whitemane Lion paying {1}{W} with 2 Plains
        JsonObject cast1 = s.action("activate_ability", "Cast Whitemane Lion");
        assertNotNull(cast1, "P1 must have action to cast Whitemane Lion");
        s.submit(cast1);
        passPriorityUntilStackEmpty(s, 60, null);

        // After Loop 1: Provisioner creates 1 Treasure -> Adrix doubles to 2 Treasures!
        // Lion and Chamber bounce themselves. Chulane drew 1 card.
        assertEquals(1, inHand(game, p1, "Whitemane Lion"), "Lion back in hand");
        assertEquals(1, inHand(game, p1, "Simic Growth Chamber"), "Chamber back in hand");
        assertEquals(2, onBattlefield(game, p1, "Treasure Token"), "2 Treasures created (Adrix doubling)");
        assertEquals(initialHandSize + 1, p1.getHand().size(), "Chulane drew 1 card");

        // Loop 2: Recast Whitemane Lion paying {1}{W} with the 2 Treasures
        JsonObject cast2 = s.action("activate_ability", "Cast Whitemane Lion");
        assertNotNull(cast2, "P1 must be able to recast Whitemane Lion via 2 Treasures");
        s.submit(cast2);
        passPriorityUntilStackEmpty(s, 60, null);

        // After Loop 2: 2 Treasures spent, 2 new Treasures created -> net 0 surplus mana!
        // Infinite draw and cast loop.
        assertEquals(1, inHand(game, p1, "Whitemane Lion"), "Lion back in hand after loop 2");
        assertEquals(1, inHand(game, p1, "Simic Growth Chamber"), "Chamber back in hand after loop 2");
        assertEquals(2, onBattlefield(game, p1, "Treasure Token"), "2 Treasures remaining (net 0 surplus mana)");
        assertEquals(initialHandSize + 2, p1.getHand().size(), "Chulane drew 2 cards total");
    }

    @Test
    @DisplayName("COMBO-OWN-004 negative: without Adrix, Provisioner generates only 1 Treasure for {1}{W} cost")
    void testCombo004NegativeWithoutAdrixNotSelfFinancing() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        // P1 setup: Chulane + Provisioner, NO Adrix, 2 Plains
        objects.add(XmageMultiplayerScenario.obj("P1", "Chulane, Teller of Tales", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Tireless Provisioner", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Plains", 3, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Plains", 4, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Whitemane Lion", 10, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Simic Growth Chamber", 11, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "c004-neg-4p", 4, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // Cast Whitemane Lion with 2 Plains
        s.submit(s.action("activate_ability", "Cast Whitemane Lion"));
        passPriorityUntilStackEmpty(s, 60, null);

        // Only 1 Treasure created without Adrix
        assertEquals(1, onBattlefield(game, p1, "Treasure Token"));
        JsonObject recast = s.action("activate_ability", "Cast Whitemane Lion");
        boolean canCast = recast != null && recast.getAsJsonObject("metadata").get("submission_ready").getAsBoolean();
        assertFalse(canCast, "Lion cannot be recast: 1 Treasure cannot pay {1}{W} cost without Adrix");
    }

    // ---------------------------------------------------------------- FINISHER-OWN-005

    static void advanceToTurn2UpkeepAndResolve(XmageMultiplayerScenario s, int maxSteps) {
        Game game = s.session.restorationGame();
        for (int i = 0; i < maxSteps; i++) {
            if (game.hasEnded()) {
                return;
            }
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "lane error: " + payload.get("failure"));
            String cls = s.decisionClass();
            if (cls == null) {
                if (game.hasEnded()) return;
                continue;
            }
            switch (cls) {
                case "priority" -> {
                    JsonObject pass = s.action("pass_priority", "Pass");
                    if (pass != null) s.submit(pass);
                    else {
                        JsonObject first = firstAction(s);
                        if (first != null) s.submit(first);
                    }
                }
                case "yes_no" -> {
                    // Killer Service upkeep prompt: "Sacrifice a token?" -> choose No
                    JsonObject no = actionWithLabel(s, "No");
                    if (no != null) s.submit(no);
                    else {
                        JsonObject first = firstAction(s);
                        if (first != null) s.submit(first);
                    }
                }
                case "order", "order_triggers", "trigger_order", "replacement_effect" -> {
                    JsonObject first = firstAction(s);
                    if (first != null) s.submit(first);
                }
                case "choose_object", "target", "choice", "choose_choice", "choose_use" -> {
                    JsonObject first = firstAction(s);
                    if (first != null) s.submit(first);
                }
                default -> {
                    JsonObject first = firstAction(s);
                    if (first != null) s.submit(first);
                }
            }
            String activePid = s.pidOf(game.getActivePlayerId().toString());
            if (game.getTurnNum() > 1 && "P1".equals(activePid) && game.getStep().getType() != mage.constants.PhaseStep.UPKEEP) {
                // Reached past P1's next upkeep
                return;
            }
        }
    }

    @Test
    @DisplayName("FINISHER-OWN-005 positive 4P: Killer Service (3 opps -> 6 Foods) + Mechanized Production (+2 at upkeep = 8 Foods) -> WIN")
    void testFinisher005Positive4PWinOn8Foods() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        // P1 setup: Manufactor + Adrix on battlefield, lands to cast Killer Service {2}{G} and Mechanized Production {2}{U}{U}
        objects.add(XmageMultiplayerScenario.obj("P1", "Academy Manufactor", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Adrix and Nev, Twincasters", 2, Zone.BATTLEFIELD));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 10 + i, Zone.BATTLEFIELD));
        }
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", 20 + i, Zone.BATTLEFIELD));
        }
        // In hand: Killer Service and Mechanized Production
        objects.add(XmageMultiplayerScenario.obj("P1", "Killer Service", 30, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Mechanized Production", 31, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "f005-pos-4p", 4, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // 1. Cast Killer Service
        s.submit(s.action("activate_ability", "Cast Killer Service"));
        passPriorityUntilStackEmpty(s, 200, null);

        // In 4P (3 opponents), Killer Service creates 3 Food tokens.
        // Manufactor + Adrix doubles to 6 Foods, 6 Clues, 6 Treasures!
        assertEquals(6, onBattlefield(game, p1, "Food Token"), "3 opps * 2 = 6 Foods");
        assertEquals(6, onBattlefield(game, p1, "Clue Token"));
        assertEquals(6, onBattlefield(game, p1, "Treasure Token"));

        // 2. Cast Mechanized Production targeting a Food Token
        JsonObject castMP = s.action("activate_ability", "Cast Mechanized Production");
        assertNotNull(castMP, "P1 must have action to cast Mechanized Production");
        s.submit(castMP);
        passPriorityUntilStackEmpty(s, 200, "Food Token");

        assertEquals(1, onBattlefield(game, p1, "Mechanized Production"));

        // 3. Advance to P1's turn 2 upkeep
        advanceToTurn2UpkeepAndResolve(s, 2000);

        // At upkeep, Mechanized Production created 2 more Food tokens (6 + 2 = 8 Foods)
        // 8 artifacts with same name -> P1 WINS!
        assertTrue(p1.hasWon(), "P1 must have won the game via Mechanized Production with 8 Foods");
        assertTrue(game.hasEnded(), "Game must have ended upon P1 win");
    }

    @Test
    @DisplayName("FINISHER-OWN-005 negative 3P: Killer Service (2 opps -> 4 Foods) + MP (+2 = 6 Foods < 8) -> NO WIN")
    void testFinisher005Negative3PNoWinOn6Foods() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Academy Manufactor", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Adrix and Nev, Twincasters", 2, Zone.BATTLEFIELD));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 10 + i, Zone.BATTLEFIELD));
        }
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", 20 + i, Zone.BATTLEFIELD));
        }
        objects.add(XmageMultiplayerScenario.obj("P1", "Killer Service", 30, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Mechanized Production", 31, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "f005-neg-3p", 3, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // 1. Cast Killer Service
        s.submit(s.action("activate_ability", "Cast Killer Service"));
        passPriorityUntilStackEmpty(s, 200, null);

        // In 3P (2 opponents): 2 opps * 2 = 4 Foods
        assertEquals(4, onBattlefield(game, p1, "Food Token"));

        // 2. Cast Mechanized Production on a Food token
        s.submit(s.action("activate_ability", "Cast Mechanized Production"));
        passPriorityUntilStackEmpty(s, 200, "Food Token");

        // 3. Advance to P1's next upkeep
        advanceToTurn2UpkeepAndResolve(s, 2000);

        // At upkeep, 4 + 2 = 6 Foods. 6 < 8 -> P1 does NOT win!
        assertEquals(6, onBattlefield(game, p1, "Food Token"), "4 + 2 = 6 Foods at upkeep");
        assertFalse(p1.hasWon(), "P1 must NOT have won with only 6 Foods (needs 8)");
        assertFalse(game.hasEnded(), "Game must still be ongoing");
    }

    @Test
    @DisplayName("FINISHER-OWN-005 negative 2P: Killer Service (1 opp -> 2 Foods) + MP (+2 = 4 Foods < 8) -> NO WIN")
    void testFinisher005Negative2PNoWinOn4Foods() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Academy Manufactor", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Adrix and Nev, Twincasters", 2, Zone.BATTLEFIELD));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 10 + i, Zone.BATTLEFIELD));
        }
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", 20 + i, Zone.BATTLEFIELD));
        }
        objects.add(XmageMultiplayerScenario.obj("P1", "Killer Service", 30, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Mechanized Production", 31, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "f005-neg-2p", 2, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        s.submit(s.action("activate_ability", "Cast Killer Service"));
        passPriorityUntilStackEmpty(s, 200, null);
        assertEquals(2, onBattlefield(game, p1, "Food Token"), "1 opp * 2 = 2 Foods");

        s.submit(s.action("activate_ability", "Cast Mechanized Production"));
        passPriorityUntilStackEmpty(s, 200, "Food Token");

        advanceToTurn2UpkeepAndResolve(s, 2000);

        assertEquals(4, onBattlefield(game, p1, "Food Token"), "2 + 2 = 4 Foods at upkeep");
        assertFalse(p1.hasWon(), "P1 must NOT have won with only 4 Foods");
        assertFalse(game.hasEnded());
    }

    @Test
    @DisplayName("FINISHER-OWN-005 positive 6P: Killer Service (5 opps -> 10 Foods) + MP (+2 = 12 Foods >= 8) -> WIN")
    void testFinisher005Positive6PWinOn12Foods() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Academy Manufactor", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Adrix and Nev, Twincasters", 2, Zone.BATTLEFIELD));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 10 + i, Zone.BATTLEFIELD));
        }
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", 20 + i, Zone.BATTLEFIELD));
        }
        objects.add(XmageMultiplayerScenario.obj("P1", "Killer Service", 30, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Mechanized Production", 31, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "f005-pos-6p", 6, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        s.submit(s.action("activate_ability", "Cast Killer Service"));
        passPriorityUntilStackEmpty(s, 300, null);
        assertEquals(10, onBattlefield(game, p1, "Food Token"), "5 opps * 2 = 10 Foods");

        s.submit(s.action("activate_ability", "Cast Mechanized Production"));
        passPriorityUntilStackEmpty(s, 300, "Food Token");

        advanceToTurn2UpkeepAndResolve(s, 3000);

        assertTrue(p1.hasWon(), "P1 must have won with 12 Foods (>= 8)");
        assertTrue(game.hasEnded());
    }

    @Test
    @DisplayName("FINISHER-OWN-005 negative without Aura: Killer Service alone produces Foods but no win condition")
    void testFinisher005NegativeWithoutAuraNoWin() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Academy Manufactor", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Adrix and Nev, Twincasters", 2, Zone.BATTLEFIELD));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 10 + i, Zone.BATTLEFIELD));
        }
        objects.add(XmageMultiplayerScenario.obj("P1", "Killer Service", 30, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "f005-neg-noaura", 4, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        s.submit(s.action("activate_ability", "Cast Killer Service"));
        passPriorityUntilStackEmpty(s, 200, null);
        assertEquals(6, onBattlefield(game, p1, "Food Token"));

        advanceToTurn2UpkeepAndResolve(s, 2000);

        assertFalse(p1.hasWon(), "Without Mechanized Production, no win occurs");
        assertFalse(game.hasEnded());
    }

    // ---------------------------------------------------------------- FINISHER-OWN-006

    @Test
    @DisplayName("FINISHER-OWN-006 positive 4P: Esix copies Psychosis Crawler on Killer Service (3 copies + 1 original = 4 Crawlers) -> card draw deals 4 damage")
    void testFinisher006Positive4PCrawlersAndDamage() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        // Battlefield: Esix, Psychosis Crawler, 4 Forests for Killer Service, 4 Islands for Reach Through Mists
        objects.add(XmageMultiplayerScenario.obj("P1", "Esix, Fractal Bloom", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Psychosis Crawler", 2, Zone.BATTLEFIELD));
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 10 + i, Zone.BATTLEFIELD));
        }
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", 20 + i, Zone.BATTLEFIELD));
        }

        // Hand: 3 buffer cards (keep hand size > 0 so Crawler has positive P/T) + Killer Service + Reach Through Mists
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", 30 + i, Zone.HAND));
        }
        objects.add(XmageMultiplayerScenario.obj("P1", "Killer Service", 40, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Reach Through Mists", 41, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "f006-pos-4p", 4, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");
        Player p2 = s.seats.get("P2");
        Player p3 = s.seats.get("P3");
        Player p4 = s.seats.get("P4");

        // Precondition: In 4P Commander, the starting player draws on Turn 1, triggering
        // the initial Psychosis Crawler for 1 damage to each opponent (40 -> 39).
        assertEquals(1, onBattlefield(game, p1, "Esix, Fractal Bloom"));
        assertEquals(1, onBattlefield(game, p1, "Psychosis Crawler"));
        assertEquals(39, p2.getLife(), "P2 lost 1 life on Turn 1 draw");
        assertEquals(39, p3.getLife(), "P3 lost 1 life on Turn 1 draw");
        assertEquals(39, p4.getLife(), "P4 lost 1 life on Turn 1 draw");

        // 1. Cast Killer Service {2}{G}
        s.submit(s.action("activate_ability", "Cast Killer Service"));
        // Esix replaces 3 Food tokens with 3 Psychosis Crawler tokens
        passPriorityUntilStackEmpty(s, 200, "Psychosis Crawler");

        // 3 token copies + 1 original = 4 Psychosis Crawlers!
        assertEquals(4, onBattlefield(game, p1, "Psychosis Crawler"), "3 token copies + 1 original = 4 Crawlers");

        // 2. Cast Reach Through Mists {U}: Draw a card
        JsonObject castReach = actionWithLabel(s, "Reach Through Mists");
        assertNotNull(castReach, "Must have action to cast Reach Through Mists: " + s.labels());
        s.submit(castReach);
        passPriorityUntilStackEmpty(s, 100, null);

        // Drawing a card triggered 4 Psychosis Crawlers: each opponent loses 4 life (39 -> 35)
        assertEquals(35, p2.getLife(), "P2 loses 4 life from 4 Crawlers");
        assertEquals(35, p3.getLife(), "P3 loses 4 life from 4 Crawlers");
        assertEquals(35, p4.getLife(), "P4 loses 4 life from 4 Crawlers");
    }

    @ParameterizedTest(name = "FINISHER-OWN-006 positive scaling: Esix copies Crawler on Killer Service at {0}P")
    @ValueSource(ints = {2, 6})
    void testFinisher006PositiveScalingCrawlersCount(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Esix, Fractal Bloom", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Psychosis Crawler", 2, Zone.BATTLEFIELD));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 10 + i, Zone.BATTLEFIELD));
        }
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", 30 + i, Zone.HAND));
        }
        objects.add(XmageMultiplayerScenario.obj("P1", "Killer Service", 40, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "f006-scale-" + playerCount + "p", playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        s.submit(s.action("activate_ability", "Cast Killer Service"));
        passPriorityUntilStackEmpty(s, 300, "Psychosis Crawler");

        // Expected crawlers = (playerCount - 1) opponents as copies + 1 original = playerCount Crawlers!
        assertEquals(playerCount, onBattlefield(game, p1, "Psychosis Crawler"),
                playerCount + "P game produces " + (playerCount - 1) + " copies + 1 original = " + playerCount + " Crawlers");
    }

    @Test
    @DisplayName("FINISHER-OWN-006 negative empty hand: Psychosis Crawler P/T is 0/0 and dies to SBAs")
    void testFinisher006NegativeEmptyHandDiesToSBA() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Esix, Fractal Bloom", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Psychosis Crawler", 2, Zone.BATTLEFIELD));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 10 + i, Zone.BATTLEFIELD));
        }
        // ONLY Killer Service in hand
        objects.add(XmageMultiplayerScenario.obj("P1", "Killer Service", 40, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "f006-neg-emptyhand", 4, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // Remove any turn-1 drawn cards so that ONLY Killer Service is in hand
        mage.cards.Card ks = p1.getHand().getCards(game).stream()
                .filter(c -> "Killer Service".equals(c.getName()))
                .findFirst().orElseThrow();
        p1.getHand().clear();
        p1.getHand().add(ks);
        assertEquals(1, p1.getHand().size(), "Only Killer Service remains in hand");

        // When Killer Service is cast, hand size drops to 0!
        s.submit(s.action("activate_ability", "Cast Killer Service"));
        passPriorityUntilStackEmpty(s, 200, "Psychosis Crawler");

        // Hand size is 0 -> Power/Toughness is 0/0 -> all Psychosis Crawlers die to SBAs (CR 704.5f)
        assertEquals(0, onBattlefield(game, p1, "Psychosis Crawler"),
                "With empty hand (0 cards), Psychosis Crawlers are 0/0 and die to SBAs");
    }

    @Test
    @DisplayName("FINISHER-OWN-006 negative second token event: Esix applies only to first token creation per turn")
    void testFinisher006NegativeSecondTokenEventEsixFirstTimeGate() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Esix, Fractal Bloom", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Psychosis Crawler", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P1", "Tireless Provisioner", 3, Zone.BATTLEFIELD));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 10 + i, Zone.BATTLEFIELD));
        }
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", 30 + i, Zone.HAND));
        }
        // Forest to play for Landfall (token event 1) and Killer Service (token event 2)
        objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 35, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Killer Service", 40, Zone.HAND));

        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "f006-neg-gate", 4, "P1", objects);
        Game game = s.session.restorationGame();
        Player p1 = s.seats.get("P1");

        // 1. Play Forest as normal land drop to trigger Provisioner (first token event of turn)
        JsonObject playLand = actionWithLabel(s, "Play Forest");
        assertNotNull(playLand, "Must be able to play Forest: " + s.labels());
        s.submit(playLand);
        // Provisioner creates Treasure (Event 1). Esix applies here and copies Crawler (now 2 Crawlers).
        passPriorityUntilStackEmpty(s, 100, null);

        // 2. Now cast Killer Service (second token event of turn)
        s.submit(s.action("activate_ability", "Cast Killer Service"));
        passPriorityUntilStackEmpty(s, 200, "Psychosis Crawler");

        // Esix gate was already consumed by Event 1!
        // Killer Service creates normal Food tokens (3 opponents -> 3 Foods).
        // No new Psychosis Crawlers are created: only the 2 Crawlers remain!
        assertEquals(2, onBattlefield(game, p1, "Psychosis Crawler"),
                "Esix first-time gate prohibits copying on second token creation; 2 Crawlers remain");
        assertEquals(3, onBattlefield(game, p1, "Food Token"),
                "Killer Service creates 3 Food tokens without Esix replacement");
    }
}
