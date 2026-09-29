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
import java.util.function.BiFunction;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Actual-card behaviour for members of the frozen 29-card corpus
 * (COMMON_FIXTURE_MANIFEST_v1 CARD_xx) on the pinned XMage engine through the
 * full-game external-pilot lane.
 *
 * <p>Each test restores a real board with the engine's native restoration
 * seam, lets the engine offer every spell, ability, target and choice, answers
 * only with engine-offered options selected by exact identity or name, and
 * asserts the outcome the card's Oracle text requires. Expected values are
 * derived from Oracle text, not from engine parity. Mana is paid from a
 * single-colour land base, so every pool choice is semantically identical.</p>
 *
 * <p>This is native technical evidence for the named cards at the pinned
 * engine. It is not a FULL107 row and carries no current-boundary credit on
 * its own.</p>
 */
class XmageActualCardCorpusTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";
    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";
    private static final String ISLAND_LABEL = "Island — {T}: Add {U}.";
    private static final String SWAMP_LABEL = "Swamp — {T}: Add {B}.";
    private static final long SEED = 424242L;

    record Started(XmageFullGameSession session, Map<String, Player> seats) {
    }

    // ------------------------------------------------------------------ setup

    private static XmageNativeStateRestoration.RequestedObject object(
            String zoneTag, mage.constants.Zone zone, String pid, String name, int index) {
        String slug = name.replaceAll("[^A-Za-z0-9]+", "");
        if (slug.length() > 24) {
            slug = slug.substring(0, 24);
        }
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + slug,
                name, pid, pid, zone, false);
    }

    private static XmageNativeStateRestoration.RequestedObject battlefield(
            String pid, String name, int index) {
        return object("bf", mage.constants.Zone.BATTLEFIELD, pid, name, index);
    }

    private static XmageNativeStateRestoration.RequestedObject hand(
            String pid, String name, int index) {
        return object("hand", mage.constants.Zone.HAND, pid, name, index);
    }

    private static List<XmageNativeStateRestoration.RequestedObject> lands(
            String pid, String name, int count) {
        List<XmageNativeStateRestoration.RequestedObject> out = new ArrayList<>();
        for (int index = 0; index < count; index++) {
            out.add(battlefield(pid, name, index));
        }
        return out;
    }

    /** Restores the board at turn-1 precombat main with P1 active and holding priority. */
    private static Started start(
            String tag, int playerCount,
            List<XmageNativeStateRestoration.RequestedObject> objects) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", ROGRAKH, pid, 0));
        }
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                tag, playerCount, SEED, List.copyOf(players), List.copyOf(commanders),
                List.copyOf(objects),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedPlayer player : players) {
            List<String> mainboard = new ArrayList<>();
            for (int index = 0; index < 99; index++) {
                mainboard.add("Mountain");
            }
            handles.add(importer.importCommanderDeck(
                    tag + "-" + player.playerId(), tag + "-hash",
                    mainboard, List.of(ROGRAKH)).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new Started(session, seats);
    }

    // ---------------------------------------------------------------- queries

    private static int life(Started started, String pid) {
        return started.seats().get(pid).getLife();
    }

    private static int handSize(Started started, String pid) {
        return started.seats().get(pid).getHand().size();
    }

    private static int onBattlefield(Started started, String pid, String name) {
        int count = 0;
        for (Permanent permanent : started.session().restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (name.equals(permanent.getName())
                    && started.seats().get(pid).getId().equals(permanent.getControllerId())) {
                count++;
            }
        }
        return count;
    }

    private static Permanent permanent(Started started, String pid, String name) {
        Permanent found = null;
        for (Permanent permanent : started.session().restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (name.equals(permanent.getName())
                    && started.seats().get(pid).getId().equals(permanent.getControllerId())) {
                assertTrue(found == null, "unique " + name + " expected for " + pid);
                found = permanent;
            }
        }
        assertNotNull(found, name + " must be on " + pid + "'s battlefield");
        return found;
    }

    private static int inGraveyard(Started started, String pid, String name) {
        int count = 0;
        for (Card card : started.seats().get(pid).getGraveyard()
                .getCards(started.session().restorationGame())) {
            if (name.equals(card.getName())) {
                count++;
            }
        }
        return count;
    }

    private static String decisionClass(Started started) {
        JsonObject payload = started.session().pendingDecisionPayload();
        if (payload.get("decision").isJsonNull()) {
            fail("engine terminal while a decision was expected");
        }
        return payload.getAsJsonObject("decision").get("decision_class").getAsString();
    }

    private static String actorPid(Started started) {
        return XmageNativeStateRestorationTest.pidOf(started.seats(),
                started.session().legalActionsPayload().get("actor_id").getAsString());
    }

    // ---------------------------------------------------------------- actions

    private static void submit(Started started, String tag, JsonObject action) {
        XmageFullGameTaxExecutionTest.submit(started.session(), tag, action);
    }

    private static void pass(Started started, String tag) {
        submit(started, tag, XmageFullGameTaxExecutionTest.singleActionOfType(
                started.session().legalActionsPayload(), "pass_priority", null));
    }

    private static void cast(Started started, String tag, String cardName) {
        submit(started, tag, XmageExternalRiskSignalTest.spellOffer(
                started.session().legalActionsPayload(), cardName));
    }

    /** The target option naming exactly this player, by engine identity. */
    private static JsonObject playerTarget(Started started, String pid) {
        String wanted = started.seats().get(pid).getId().toString();
        JsonObject match = null;
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta != null && meta.has("object_id")
                    && wanted.equals(meta.get("object_id").getAsString())) {
                assertTrue(match == null, "unique player target expected for " + pid);
                match = action;
            }
        }
        assertNotNull(match, pid + " must be engine-offered as a target");
        return match;
    }

    /** The target option naming exactly this permanent, by engine identity. */
    private static JsonObject permanentTarget(Started started, Permanent permanent) {
        String wanted = permanent.getId().toString();
        JsonObject match = null;
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta != null && meta.has("object_id")
                    && wanted.equals(meta.get("object_id").getAsString())) {
                assertTrue(match == null, "unique target expected for " + permanent.getName());
                match = action;
            }
        }
        assertNotNull(match, permanent.getName() + " must be engine-offered as a target");
        return match;
    }

    /**
     * One option of a single-select choice whose offered options are all
     * sourced from {@code sourceName}, i.e. semantically identical. The
     * equivalence is asserted before the lowest action id is taken.
     */
    private static JsonObject equivalentOption(Started started, String sourceName) {
        List<JsonObject> options = new ArrayList<>();
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            assertTrue(action.toString().contains(sourceName),
                    "only equivalent " + sourceName + " options may be offered: " + action);
            options.add(action);
        }
        assertTrue(options.size() >= 2, "an ordering choice offers at least two options");
        options.sort((left, right) -> left.get("action_id").getAsString()
                .compareTo(right.get("action_id").getAsString()));
        return options.get(0);
    }

    /**
     * Selects {@code count} options of a multi-select object choice. Every
     * offered option must carry {@code requiredName}, so the selected set is
     * semantically identical to any other selection of the same size.
     */
    private static void chooseNamed(Started started, String tag, String requiredName, int count) {
        XmageFullGameSession session = started.session();
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        List<String> offered = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata");
            JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
            String name = engine != null && engine.has("name")
                    ? engine.get("name").getAsString()
                    : meta.get("label").getAsString();
            assertTrue(name.startsWith(requiredName),
                    "only equivalent " + requiredName + " options may be offered; saw " + name);
            offered.add(meta.get("option_id").getAsString());
        }
        assertTrue(offered.size() >= count, "too few options for a required choice");
        offered.sort(String::compareTo);
        List<String> selected = offered.subList(0, count);
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", decisionId + ":" + selected.get(0));
        proposal.addProperty("action_type", "choose_targets");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        JsonArray selectedJson = new JsonArray();
        selected.forEach(selectedJson::add);
        choices.add("selected_option_ids", selectedJson);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = session.submitAction(proposal);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());
    }

    /**
     * Pays mana and passes priority until the stack is empty with priority
     * pending. Any other decision is handed to {@code handler}, which must
     * return true when it answered; unanswered decisions fail the test.
     */
    private static void resolveAll(
            Started started, String tag, String manaLabel,
            BiFunction<String, Integer, Boolean> handler) {
        for (int step = 0; step < 80; step++) {
            String decisionClass = decisionClass(started);
            if ("priority".equals(decisionClass)
                    && started.session().restorationGame().getStack().isEmpty()) {
                return;
            }
            switch (decisionClass) {
                case "priority" -> pass(started, tag + "-pass-" + step);
                case "mana_payment" -> {
                    if (manaLabel == null) {
                        if (!handler.apply(decisionClass, step)) {
                            fail("[" + tag + "] mana payment needs a handler");
                        }
                    } else {
                        XmageExternalRiskSignalTest.payHomogeneous(
                                started.session(), tag + "-pay-" + step, manaLabel, 12);
                    }
                }
                default -> {
                    if (!handler.apply(decisionClass, step)) {
                        fail("[" + tag + "] unhandled " + decisionClass + " for "
                                + actorPid(started) + " prompt="
                                + started.session().pendingDecisionPayload()
                                        .getAsJsonObject("decision").get("prompt"));
                    }
                }
            }
        }
        fail("[" + tag + "] resolution bound breached");
    }

    private static final BiFunction<String, Integer, Boolean> NONE = (cls, step) -> false;

    /** Cast offers for {@code cardName} whose label does / does not contain {@code fragment}. */
    private static List<JsonObject> offers(Started started, String cardName, String fragment,
            boolean containing) {
        List<JsonObject> out = new ArrayList<>();
        for (JsonObject offer : XmageExternalRiskSignalTest.spellOffers(
                started.session().legalActionsPayload(), cardName)) {
            String label = offer.getAsJsonObject("metadata").get("label").getAsString();
            if (label.contains(fragment) == containing) {
                out.add(offer);
            }
        }
        return out;
    }

    /** The single target option naming a stack object (spell) by name. */
    private static JsonObject spellTarget(Started started, String spellName) {
        JsonObject match = null;
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta != null && meta.has("name")
                    && spellName.equals(meta.get("name").getAsString())) {
                assertTrue(match == null, "unique spell target expected for " + spellName);
                match = action;
            }
        }
        assertNotNull(match, spellName + " must be engine-offered as a target: "
                + started.session().legalActionsPayload().getAsJsonArray("actions"));
        return match;
    }

    /** The single boolean option with the given value. */
    private static JsonObject booleanOption(Started started, boolean value) {
        JsonObject match = null;
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta != null && meta.has("value") && !meta.get("value").isJsonNull()
                    && meta.get("value").getAsBoolean() == value) {
                assertTrue(match == null, "unique boolean option expected");
                match = action;
            }
        }
        assertNotNull(match, "boolean option " + value + " must be offered");
        return match;
    }

    /**
     * Pays a Swamp/Forest cost by its remaining unpaid symbols: Swamps pay
     * generic and {B}, the Forest pays only a lone remaining {G}. The pool
     * only ever holds the mana just produced, so pool choices are equivalent.
     */
    private static boolean payGolgari(Started started, String tag) {
        JsonObject pending = started.session().pendingDecisionPayload()
                .getAsJsonObject("decision");
        String unpaid = pending.get("prompt").getAsString();
        unpaid = unpaid.contains("<") ? unpaid.substring(0, unpaid.indexOf('<')) : unpaid;
        String want = unpaid.equals("{G}") ? "Forest" : "Swamp";
        JsonObject pool = null;
        JsonObject tap = null;
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata");
            String type = meta.get("option_type").getAsString();
            String label = meta.get("label").getAsString();
            if ("mana_pool".equals(type) && pool == null) {
                pool = action;
            } else if ("mana_ability".equals(type) && label.startsWith(want)
                    && (tap == null || action.get("action_id").getAsString()
                            .compareTo(tap.get("action_id").getAsString()) < 0)) {
                tap = action;
            }
        }
        JsonObject pick = pool != null ? pool : tap;
        assertNotNull(pick, "no " + want + " source for unpaid " + unpaid);
        submit(started, tag, pick);
        return true;
    }

    // ---------------------------------------------------------- batch 2 cards

    /**
     * CARD_28 Find // Finality. Oracle and the official rulings: an ordinary
     * split card (no aftermath keyword; "You can cast it even if you control
     * no creatures"). Either half may be cast from hand; neither half may be
     * cast from a graveyard without a permission. Finality gives all
     * creatures -4/-4, and the card goes to its owner's graveyard.
     */
    @Test
    void findFinalityIsAPlainSplitCardCastableFromHandOnly() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Swamp", 5));
        objects.add(battlefield("P1", "Forest", 0));
        objects.add(hand("P1", "Find // Finality", 0));
        objects.add(battlefield("P2", "Grizzly Bears", 0));
        Started started = start("card28-finality", 2, objects);

        assertEquals(1, offers(started, "Finality", "Cast Finality", true).size(),
                "Finality is castable from hand (no aftermath)");
        submit(started, "card28-cast", offers(started, "Finality", "Cast Finality", true).get(0));
        resolveAll(started, "card28", null, (cls, step) -> {
            if ("mana_payment".equals(cls)) {
                return payGolgari(started, "card28-pay-" + step);
            }
            return false;
        });

        assertEquals(0, onBattlefield(started, "P2", "Grizzly Bears"),
                "all creatures get -4/-4: the 2/2 dies");
        assertEquals(1, inGraveyard(started, "P2", "Grizzly Bears"));
        assertEquals(1, inGraveyard(started, "P1", "Find // Finality"),
                "a split card cast from hand goes to the graveyard, not exile");
        // Negative control: nothing permits casting either half from the
        // graveyard, even with {4}{B}{G} available again.
        assertEquals(0, offers(started, "Finality", "", true).size(),
                "Finality must not be castable from the graveyard");
        assertEquals(0, offers(started, "Find", "", true).size(),
                "Find must not be castable from the graveyard");
    }

    /** CARD_01 Ishai: "Whenever an opponent casts a spell, put a +1/+1 counter on Ishai." */
    @Test
    void ishaiGrowsWhenAnOpponentCastsASpell() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Ishai, Ojutai Dragonspeaker", 0));
        objects.add(battlefield("P2", "Mountain", 0));
        objects.add(hand("P2", "Lightning Bolt", 0));
        Started started = start("card01-ishai", 2, objects);
        Permanent ishai = permanent(started, "P1", "Ishai, Ojutai Dragonspeaker");
        assertEquals(0, ishai.getCounters(started.session().restorationGame())
                .getCount(mage.counters.CounterType.P1P1));

        XmageExternalRiskSignalTest.passToActor(
                started.session(), "card01", started.seats(), "P2");
        cast(started, "card01-bolt", "Lightning Bolt");
        submit(started, "card01-bolt-target", playerTarget(started, "P1"));
        resolveAll(started, "card01", MOUNTAIN_LABEL, NONE);

        assertEquals(1, permanent(started, "P1", "Ishai, Ojutai Dragonspeaker")
                .getCounters(started.session().restorationGame())
                .getCount(mage.counters.CounterType.P1P1), "one opponent spell: one counter");
        assertEquals(37, life(started, "P1"));
    }

    /** CARD_14 Vandalblast: destroy target artifact you don't control. */
    @Test
    void vandalblastDestroysOneArtifactYouDontControl() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Mountain", 0));
        objects.add(battlefield("P1", "Ornithopter", 0));
        objects.add(battlefield("P2", "Ornithopter", 0));
        objects.add(battlefield("P2", "Ornithopter", 1));
        objects.add(hand("P1", "Vandalblast", 0));
        Started started = start("card14-vandal", 2, objects);

        submit(started, "card14-cast", offers(started, "Vandalblast", "overload", false).get(0));
        assertEquals("target", decisionClass(started));
        Player p1 = started.seats().get("P1");
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            String objectId = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata").get("object_id").getAsString();
            Permanent offered = started.session().restorationGame()
                    .getPermanent(java.util.UUID.fromString(objectId));
            assertTrue(offered != null && !p1.getId().equals(offered.getControllerId()),
                    "only artifacts P1 doesn't control may be targeted");
        }
        JsonObject first = started.session().legalActionsPayload()
                .getAsJsonArray("actions").get(0).getAsJsonObject();
        submit(started, "card14-target", first);
        resolveAll(started, "card14", MOUNTAIN_LABEL, NONE);

        assertEquals(1, onBattlefield(started, "P2", "Ornithopter"), "exactly one destroyed");
        assertEquals(1, onBattlefield(started, "P1", "Ornithopter"), "own artifact untouched");
    }

    /** CARD_14 Vandalblast overload: destroy each artifact you don't control. */
    @Test
    void vandalblastOverloadDestroysEachArtifactYouDontControl() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Mountain", 5));
        objects.add(battlefield("P1", "Ornithopter", 0));
        objects.add(battlefield("P2", "Ornithopter", 0));
        objects.add(battlefield("P2", "Ornithopter", 1));
        objects.add(hand("P1", "Vandalblast", 0));
        Started started = start("card14-overload", 2, objects);

        List<JsonObject> overload = offers(started, "Vandalblast", "overload", true);
        assertEquals(1, overload.size(), "overload must be offered as its own cast");
        submit(started, "card14o-cast", overload.get(0));
        resolveAll(started, "card14o", MOUNTAIN_LABEL, NONE);

        assertEquals(0, onBattlefield(started, "P2", "Ornithopter"), "each opposing artifact");
        assertEquals(1, onBattlefield(started, "P1", "Ornithopter"),
                "overload still spares artifacts P1 controls");
    }

    /**
     * CARD_05 Veyran: magecraft +1/+1, and "If you casting or copying an
     * instant or sorcery spell causes a triggered ability of a permanent you
     * control to trigger, that ability triggers an additional time." Veyran's
     * own magecraft therefore triggers twice: 2/2 becomes 4/4.
     */
    @Test
    void veyranDoublesItsOwnMagecraft() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Veyran, Voice of Duality", 0));
        objects.add(battlefield("P1", "Mountain", 0));
        objects.add(hand("P1", "Lightning Bolt", 0));
        Started started = start("card05-veyran", 2, objects);
        cast(started, "card05-bolt", "Lightning Bolt");
        submit(started, "card05-target", playerTarget(started, "P2"));
        resolveAll(started, "card05", MOUNTAIN_LABEL, (cls, step) -> {
            if ("trigger_order".equals(cls)) {
                submit(started, "card05-order-" + step, equivalentOption(started, "Veyran"));
                return true;
            }
            return false;
        });
        Permanent veyran = permanent(started, "P1", "Veyran, Voice of Duality");
        assertEquals(4, veyran.getPower().getValue(), "magecraft triggers twice: +2/+2");
        assertEquals(4, veyran.getToughness().getValue());
        assertEquals(37, life(started, "P2"));
    }

    /**
     * CARD_06 Harmonic Prodigy: "If a triggered ability of a Shaman or another
     * Wizard you control triggers, that ability triggers an additional time."
     * Young Pyromancer (Human Shaman) makes two Elemental tokens per spell.
     */
    @Test
    void harmonicProdigyDoublesAShamansTrigger() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Harmonic Prodigy", 0));
        objects.add(battlefield("P1", "Young Pyromancer", 0));
        objects.add(battlefield("P1", "Mountain", 0));
        objects.add(hand("P1", "Lightning Bolt", 0));
        Started started = start("card06-prodigy", 2, objects);
        cast(started, "card06-bolt", "Lightning Bolt");
        submit(started, "card06-target", playerTarget(started, "P2"));
        resolveAll(started, "card06", MOUNTAIN_LABEL, (cls, step) -> {
            if ("trigger_order".equals(cls)) {
                submit(started, "card06-order-" + step, anyOrderingOption(started));
                return true;
            }
            return false;
        });
        assertEquals(2, onBattlefield(started, "P1", "Elemental Token"),
                "the Shaman's trigger triggers an additional time");
        assertEquals(2, permanent(started, "P1", "Harmonic Prodigy").getPower().getValue(),
                "prowess (not a Shaman/other Wizard trigger) triggers once: 1/3 becomes 2/4");
    }

    /**
     * CARD_10 Wash Away with cleave: "Counter target spell [that wasn't cast
     * from its owner's hand]" - cleave removes the bracketed words, so it
     * counters a Lightning Bolt cast from hand; the uncleaved cast cannot.
     */
    @Test
    void washAwayCleaveCountersASpellCastFromHand() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Island", 3));
        objects.add(hand("P1", "Wash Away", 0));
        objects.add(battlefield("P2", "Mountain", 0));
        objects.add(hand("P2", "Lightning Bolt", 0));
        Started started = start("card10-wash", 2, objects);

        XmageExternalRiskSignalTest.passToActor(
                started.session(), "card10", started.seats(), "P2");
        cast(started, "card10-bolt", "Lightning Bolt");
        submit(started, "card10-bolt-target", playerTarget(started, "P1"));
        XmageExternalRiskSignalTest.payHomogeneous(
                started.session(), "card10-bolt-pay", MOUNTAIN_LABEL, 6);
        XmageExternalRiskSignalTest.passToActor(
                started.session(), "card10-respond", started.seats(), "P1");
        assertEquals(0, offers(started, "Wash Away", "leave", false).size(),
                "uncleaved Wash Away has no legal target: the Bolt was cast from hand");
        List<JsonObject> cleave = offers(started, "Wash Away", "leave", true);
        assertEquals(1, cleave.size(), "the cleave cast must be offered");
        submit(started, "card10-cleave", cleave.get(0));
        submit(started, "card10-cleave-target", spellTarget(started, "Lightning Bolt"));
        resolveAll(started, "card10", ISLAND_LABEL, NONE);

        assertEquals(40, life(started, "P1"), "the countered Bolt deals no damage");
        assertEquals(1, inGraveyard(started, "P2", "Lightning Bolt"));
    }

    /**
     * CARD_13 Flare of Duplication: "You may sacrifice a nontoken red creature
     * rather than pay this spell's mana cost. Copy target instant or sorcery
     * spell." With no untapped land, only the alternative cost is payable.
     */
    @Test
    void flareOfDuplicationCopiesViaItsAlternativeCost() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Mountain", 0));
        objects.add(battlefield("P1", "Raging Goblin", 0));
        objects.add(hand("P1", "Lightning Bolt", 0));
        objects.add(hand("P1", "Flare of Duplication", 0));
        Started started = start("card13-flare", 2, objects);

        cast(started, "card13-bolt", "Lightning Bolt");
        submit(started, "card13-bolt-target", playerTarget(started, "P2"));
        XmageExternalRiskSignalTest.payHomogeneous(
                started.session(), "card13-bolt-pay", MOUNTAIN_LABEL, 6);
        List<JsonObject> flare = offers(started, "Flare of Duplication", "", true);
        assertTrue(!flare.isEmpty(), "Flare must be castable by sacrificing the Goblin");
        submit(started, "card13-flare", flare.get(0));
        boolean[] sacrificed = {false};
        resolveAll(started, "card13", MOUNTAIN_LABEL, (cls, step) -> {
            JsonObject pending = started.session().pendingDecisionPayload()
                    .getAsJsonObject("decision");
            String prompt = pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    ? pending.get("prompt").getAsString() : "";
            if ("choose_use".equals(cls) && prompt.toLowerCase().contains("new target")) {
                submit(started, "card13-keep-target-" + step, booleanOption(started, false));
                return true;
            }
            if ("choose_use".equals(cls)) {
                submit(started, "card13-alt-" + step, booleanOption(started, true));
                return true;
            }
            if ("choice".equals(cls) && prompt.contains("alternative cost")) {
                submit(started, "card13-alt-" + step, labelled(started, "acrifice"));
                return true;
            }
            if ("target".equals(cls) && "Lightning Bolt".equals(targetSourceName(started))) {
                // "You may choose new targets for the copy": keep P2.
                submit(started, "card13-copy-keeps-p2-" + step, playerTarget(started, "P2"));
                return true;
            }
            if ("target".equals(cls) || "choose_object".equals(cls)) {
                if (prompt.contains("acrifice") || prompt.contains("red creature")) {
                    chooseNamed(started, "card13-sac-" + step, "Raging Goblin", 1);
                    sacrificed[0] = true;
                } else {
                    submit(started, "card13-copy-target-" + step,
                            spellTarget(started, "Lightning Bolt"));
                }
                return true;
            }
            return false;
        });

        assertEquals(34, life(started, "P2"), "Bolt and its copy: 6 damage");
        assertEquals(1, inGraveyard(started, "P1", "Raging Goblin"),
                "the alternative cost sacrificed the red creature");
        assertTrue(sacrificed[0] || inGraveyard(started, "P1", "Raging Goblin") == 1);
    }

    /**
     * CARD_22 Bolt Bend: costs {3} less with a power-4-or-greater creature;
     * "Change the target of target spell or ability with a single target."
     * One Mountain can only pay the reduced cost.
     */
    @Test
    void boltBendIsCheapWithABigCreatureAndRedirectsABolt() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Shivan Dragon", 0));
        objects.add(battlefield("P1", "Mountain", 0));
        objects.add(hand("P1", "Bolt Bend", 0));
        objects.add(battlefield("P2", "Mountain", 0));
        objects.add(hand("P2", "Lightning Bolt", 0));
        Started started = start("card22-bend", 2, objects);

        XmageExternalRiskSignalTest.passToActor(
                started.session(), "card22", started.seats(), "P2");
        cast(started, "card22-bolt", "Lightning Bolt");
        submit(started, "card22-bolt-target", playerTarget(started, "P1"));
        XmageExternalRiskSignalTest.payHomogeneous(
                started.session(), "card22-bolt-pay", MOUNTAIN_LABEL, 6);
        XmageExternalRiskSignalTest.passToActor(
                started.session(), "card22-respond", started.seats(), "P1");
        cast(started, "card22-bend", "Bolt Bend");
        submit(started, "card22-bend-target", spellTarget(started, "Lightning Bolt"));
        resolveAll(started, "card22", MOUNTAIN_LABEL, (cls, step) -> {
            if ("target".equals(cls) && "P1".equals(actorPid(started))) {
                submit(started, "card22-new-target-" + step, playerTarget(started, "P2"));
                return true;
            }
            if ("choose_use".equals(cls) && "P1".equals(actorPid(started))) {
                submit(started, "card22-change-" + step, booleanOption(started, true));
                return true;
            }
            return false;
        });

        assertEquals(40, life(started, "P1"), "the Bolt was redirected away from P1");
        assertEquals(37, life(started, "P2"), "the redirected Bolt hits P2");
    }

    /** CARD_15 Finale of Revelation with X = 2: draw two, then exile Finale. */
    @Test
    void finaleOfRevelationDrawsXAndExilesItself() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Island", 4));
        objects.add(hand("P1", "Finale of Revelation", 0));
        Started started = start("card15-finale", 2, objects);
        int handBefore = handSize(started, "P1");

        cast(started, "card15-cast", "Finale of Revelation");
        resolveAll(started, "card15", ISLAND_LABEL, (cls, step) -> {
            if ("announce_x".equals(cls)) {
                submitNumeric(started, "card15-x-" + step, 2);
                return true;
            }
            return false;
        });

        assertEquals(handBefore - 1 + 2, handSize(started, "P1"), "X = 2: two cards drawn");
        assertEquals(0, inGraveyard(started, "P1", "Finale of Revelation"));
        assertTrue(started.session().restorationGame().getExile().getAllCards(
                started.session().restorationGame()).stream()
                .anyMatch(card -> "Finale of Revelation".equals(card.getName())),
                "Finale exiles itself");
    }

    /**
     * CARD_23 Makeshift Mannequin: returns a creature card with a mannequin
     * counter; "When this creature becomes the target of a spell or ability,
     * sacrifice it."
     */
    @Test
    void makeshiftMannequinReturnsACreatureThatDiesWhenTargeted() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Swamp", 4));
        objects.add(hand("P1", "Makeshift Mannequin", 0));
        objects.add(object("gy", mage.constants.Zone.GRAVEYARD, "P1", "Grizzly Bears", 0));
        objects.add(battlefield("P2", "Mountain", 0));
        objects.add(hand("P2", "Lightning Bolt", 0));
        Started started = start("card23-mannequin", 2, objects);

        cast(started, "card23-cast", "Makeshift Mannequin");
        resolveAll(started, "card23", SWAMP_LABEL, (cls, step) -> {
            if ("target".equals(cls) || "choose_object".equals(cls)) {
                chooseNamed(started, "card23-return-" + step, "Grizzly Bears", 1);
                return true;
            }
            return false;
        });
        Permanent bears = permanent(started, "P1", "Grizzly Bears");
        assertEquals(1, bears.getCounters(started.session().restorationGame())
                .getCount(mage.counters.CounterType.MANNEQUIN), "returns with a mannequin counter");

        XmageExternalRiskSignalTest.passToActor(
                started.session(), "card23", started.seats(), "P2");
        cast(started, "card23-bolt", "Lightning Bolt");
        submit(started, "card23-bolt-target", permanentTarget(started, bears));
        resolveAll(started, "card23-b", MOUNTAIN_LABEL, NONE);

        assertEquals(0, onBattlefield(started, "P1", "Grizzly Bears"),
                "becoming the target sacrifices it");
        assertEquals(1, inGraveyard(started, "P1", "Grizzly Bears"));
        assertEquals(40, life(started, "P1"));
    }

    /**
     * Pays by the remaining unpaid symbols: the first coloured symbol still
     * unpaid picks its land, otherwise {@code genericLand} pays generic. The
     * pool only ever holds mana just produced, so pool choices are equivalent.
     */
    private static boolean payBySymbols(Started started, String tag,
            Map<String, String> landForSymbol, String genericLand) {
        JsonObject pending = started.session().pendingDecisionPayload()
                .getAsJsonObject("decision");
        String unpaid = pending.get("prompt").getAsString();
        unpaid = unpaid.contains("<") ? unpaid.substring(0, unpaid.indexOf('<')) : unpaid;
        String want = genericLand;
        for (Map.Entry<String, String> entry : landForSymbol.entrySet()) {
            if (unpaid.contains(entry.getKey())) {
                want = entry.getValue();
                break;
            }
        }
        JsonObject pool = null;
        JsonObject tap = null;
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata");
            String type = meta.get("option_type").getAsString();
            String label = meta.get("label").getAsString();
            if ("mana_pool".equals(type) && pool == null) {
                pool = action;
            } else if ("mana_ability".equals(type) && label.startsWith(want)
                    && (tap == null || action.get("action_id").getAsString()
                            .compareTo(tap.get("action_id").getAsString()) < 0)) {
                tap = action;
            }
        }
        JsonObject pick = pool != null ? pool : tap;
        assertNotNull(pick, "no " + want + " source for unpaid " + unpaid);
        submit(started, tag, pick);
        return true;
    }

    /** Names of the permanents offered by the current target decision. */
    private static List<String> offeredTargetNames(Started started) {
        List<String> names = new ArrayList<>();
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta != null && meta.has("name")) {
                names.add(meta.get("name").getAsString());
            }
        }
        return names;
    }

    // ---------------------------------------------------------- batch 3 cards

    /**
     * CARD_07 Narset, Parter of Veils: "Each opponent can't draw more than one
     * card each turn." P1 (Narset's opponent) casts Divination and draws one.
     */
    @Test
    void narsetLimitsAnOpponentToOneDrawPerTurn() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P2", "Narset, Parter of Veils", 0));
        objects.addAll(lands("P1", "Island", 3));
        objects.add(hand("P1", "Divination", 0));
        Started started = start("card07-narset", 2, objects);
        int handBefore = handSize(started, "P1");
        cast(started, "card07-cast", "Divination");
        resolveAll(started, "card07", ISLAND_LABEL, NONE);
        assertEquals(handBefore - 1 + 1, handSize(started, "P1"),
                "Divination would draw two; Narset allows only one");
    }

    /**
     * CARD_11 Wear // Tear with fuse: "Wear: Destroy target artifact. /
     * Tear: Destroy target enchantment." Fused from hand, both halves resolve.
     */
    @Test
    void wearTearFusedDestroysAnArtifactAndAnEnchantment() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Mountain", 2));
        objects.add(battlefield("P1", "Plains", 0));
        objects.add(hand("P1", "Wear // Tear", 0));
        objects.add(battlefield("P2", "Ornithopter", 0));
        objects.add(battlefield("P2", "Warstorm Surge", 0));
        Started started = start("card11-weartear", 2, objects);

        List<JsonObject> fused = offers(started, "Wear // Tear", "fuse", true);
        if (fused.isEmpty()) {
            fused = offers(started, "Wear // Tear", "Fuse", true);
        }
        assertEquals(1, fused.size(), "the fused cast must be offered from hand");
        submit(started, "card11-fuse", fused.get(0));
        resolveAll(started, "card11", null, (cls, step) -> {
            if ("target".equals(cls)) {
                List<String> names = offeredTargetNames(started);
                String pick = names.contains("Ornithopter") && !names.contains("Warstorm Surge")
                        ? "Ornithopter" : "Warstorm Surge";
                chooseNamed(started, "card11-target-" + step, pick, 1);
                return true;
            }
            if ("mana_payment".equals(cls)) {
                return payBySymbols(started, "card11-pay-" + step,
                        new java.util.LinkedHashMap<>(Map.of("{W}", "Plains")), "Mountain");
            }
            return false;
        });
        assertEquals(0, onBattlefield(started, "P2", "Ornithopter"), "Wear destroyed the artifact");
        assertEquals(0, onBattlefield(started, "P2", "Warstorm Surge"),
                "Tear destroyed the enchantment");
    }

    /**
     * CARD_18 Shriekmaw: "When this creature enters, destroy target
     * nonartifact, nonblack creature." Artifact and black creatures are never
     * offered as targets.
     */
    @Test
    void shriekmawDestroysOnlyANonartifactNonblackCreature() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Swamp", 5));
        objects.add(hand("P1", "Shriekmaw", 0));
        objects.add(battlefield("P2", "Grizzly Bears", 0));
        objects.add(battlefield("P2", "Ornithopter", 0));
        objects.add(battlefield("P2", "Vampire Nighthawk", 0));
        Started started = start("card18-shriek", 2, objects);

        cast(started, "card18-cast", "Shriekmaw");
        List<List<String>> offered = new ArrayList<>();
        resolveAll(started, "card18", SWAMP_LABEL, (cls, step) -> {
            if ("choice".equals(cls)) {
                // Evoke is an alternative cost chosen during casting: hardcast.
                submit(started, "card18-normal-" + step, labelledWithout(started, "voke"));
                return true;
            }
            if ("target".equals(cls)) {
                offered.add(offeredTargetNames(started));
                chooseNamed(started, "card18-target-" + step, "Grizzly Bears", 1);
                return true;
            }
            return false;
        });
        assertEquals(List.of(List.of("Grizzly Bears")), offered,
                "only the nonartifact, nonblack creature may be targeted");
        assertEquals(0, onBattlefield(started, "P2", "Grizzly Bears"));
        assertEquals(1, onBattlefield(started, "P2", "Ornithopter"));
        assertEquals(1, onBattlefield(started, "P2", "Vampire Nighthawk"));
        assertEquals(1, onBattlefield(started, "P1", "Shriekmaw"), "hardcast Shriekmaw stays");
    }

    /** CARD_18 Shriekmaw evoke {1}{B}: the ETB still destroys, then it is sacrificed. */
    @Test
    void shriekmawEvokeDestroysThenIsSacrificed() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Swamp", 2));
        objects.add(hand("P1", "Shriekmaw", 0));
        objects.add(battlefield("P2", "Grizzly Bears", 0));
        Started started = start("card18-evoke", 2, objects);

        cast(started, "card18e-cast", "Shriekmaw");
        boolean[] evoked = {false};
        resolveAll(started, "card18e", SWAMP_LABEL, (cls, step) -> {
            if ("choice".equals(cls)) {
                submit(started, "card18e-evoke-" + step, labelled(started, "voke"));
                evoked[0] = true;
                return true;
            }
            if ("target".equals(cls)) {
                chooseNamed(started, "card18e-target-" + step, "Grizzly Bears", 1);
                return true;
            }
            if ("trigger_order".equals(cls)) {
                // Sacrifice and destroy are independent; either order ends
                // with both creatures in their graveyards.
                submit(started, "card18e-order-" + step, anyOrderingOption(started));
                return true;
            }
            return false;
        });
        assertEquals(0, onBattlefield(started, "P2", "Grizzly Bears"));
        assertEquals(0, onBattlefield(started, "P1", "Shriekmaw"));
        assertTrue(evoked[0], "evoke must be offered as an alternative cost");
        assertEquals(1, inGraveyard(started, "P1", "Shriekmaw"), "evoked Shriekmaw is sacrificed");
    }

    /**
     * CARD_25 Basilisk Collar: "Equipped creature has deathtouch and
     * lifelink. Equip {2}."
     */
    @Test
    void basiliskCollarGrantsDeathtouchAndLifelinkWhenEquipped() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Basilisk Collar", 0));
        objects.add(battlefield("P1", "Grizzly Bears", 0));
        objects.addAll(lands("P1", "Mountain", 2));
        Started started = start("card25-collar", 2, objects);
        Permanent bears = permanent(started, "P1", "Grizzly Bears");
        assertTrue(!bears.hasAbility(mage.abilities.keyword.DeathtouchAbility.getInstance(),
                started.session().restorationGame()));

        JsonObject equip = null;
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            String label = action.getAsJsonObject("metadata").get("label").getAsString();
            if (label.startsWith("Basilisk Collar") && label.contains("Equip")) {
                assertTrue(equip == null, "unique equip offer");
                equip = action;
            }
        }
        assertNotNull(equip, "equip must be offered at sorcery speed in main phase");
        submit(started, "card25-equip", equip);
        resolveAll(started, "card25", MOUNTAIN_LABEL, (cls, step) -> {
            if ("target".equals(cls)) {
                submit(started, "card25-target-" + step, permanentTarget(started, bears));
                return true;
            }
            return false;
        });
        Permanent equipped = permanent(started, "P1", "Grizzly Bears");
        mage.game.Game game = started.session().restorationGame();
        assertTrue(equipped.hasAbility(mage.abilities.keyword.DeathtouchAbility.getInstance(), game),
                "equipped creature has deathtouch");
        assertTrue(equipped.hasAbility(mage.abilities.keyword.LifelinkAbility.getInstance(), game),
                "equipped creature has lifelink");
    }

    /** CARD_26 Burn Down the House, mode 1: 5 damage to each creature and planeswalker. */
    @Test
    void burnDownTheHouseDealsFiveToEachCreature() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Mountain", 5));
        objects.add(hand("P1", "Burn Down the House", 0));
        objects.add(battlefield("P1", "Shivan Dragon", 0));
        objects.add(battlefield("P2", "Grizzly Bears", 0));
        objects.add(battlefield("P2", "Narset, Parter of Veils", 0));
        Started started = start("card26-burn", 2, objects);
        cast(started, "card26-cast", "Burn Down the House");
        resolveAll(started, "card26", MOUNTAIN_LABEL, (cls, step) -> {
            if ("mode".equals(cls) || "choose_mode".equals(cls)) {
                submit(started, "card26-mode-" + step, labelled(started, "5 damage"));
                return true;
            }
            return false;
        });
        assertEquals(0, onBattlefield(started, "P1", "Shivan Dragon"), "5/5 takes 5: dies");
        assertEquals(0, onBattlefield(started, "P2", "Grizzly Bears"));
        assertEquals(0, onBattlefield(started, "P2", "Narset, Parter of Veils"),
                "planeswalkers are hit too (Narset has 5 loyalty)");
        assertEquals(40, life(started, "P2"), "players are not damaged");
    }

    /** CARD_26 Burn Down the House, mode 2: three 1/1 red Devils with haste. */
    @Test
    void burnDownTheHouseMakesThreeHastyDevils() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Mountain", 5));
        objects.add(hand("P1", "Burn Down the House", 0));
        Started started = start("card26-devils", 2, objects);
        cast(started, "card26d-cast", "Burn Down the House");
        resolveAll(started, "card26d", MOUNTAIN_LABEL, (cls, step) -> {
            if ("mode".equals(cls) || "choose_mode".equals(cls)) {
                submit(started, "card26d-mode-" + step, labelled(started, "Devil"));
                return true;
            }
            return false;
        });
        assertEquals(3, onBattlefield(started, "P1", "Devil Token"), "three Devil tokens");
        mage.game.Game game = started.session().restorationGame();
        for (Permanent permanent : game.getBattlefield().getAllPermanents()) {
            if ("Devil Token".equals(permanent.getName())) {
                assertEquals(1, permanent.getPower().getValue());
                assertEquals(1, permanent.getToughness().getValue());
                assertTrue(permanent.hasAbility(
                        mage.abilities.keyword.HasteAbility.getInstance(), game),
                        "Devils gain haste until end of turn");
            }
        }
    }

    /** The source name of the spell or ability asking for the current target. */
    private static String targetSourceName(Started started) {
        JsonArray actions = started.session().legalActionsPayload().getAsJsonArray("actions");
        if (actions.isEmpty()) {
            return "";
        }
        JsonObject meta = actions.get(0).getAsJsonObject().getAsJsonObject("metadata");
        JsonObject source = meta.has("source_object") && meta.get("source_object").isJsonObject()
                ? meta.getAsJsonObject("source_object") : null;
        return source != null && source.has("source_name")
                ? source.get("source_name").getAsString() : "";
    }

    /** Answers a numeric decision (e.g. announce X) with an in-range value. */
    private static void submitNumeric(Started started, String tag, int value) {
        XmageFullGameSession session = started.session();
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        JsonObject numeric = legal.getAsJsonArray("actions").get(0).getAsJsonObject();
        assertEquals("numeric", numeric.getAsJsonObject("choices_schema")
                .get("response_kind").getAsString());
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", numeric.get("action_id").getAsString());
        proposal.addProperty("action_type", "structural_decision");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", new JsonArray());
        choices.addProperty("numeric_choice", value);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = session.submitAction(proposal);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());
    }

    /** The single option whose label contains {@code fragment}; dumps options otherwise. */
    private static JsonObject labelled(Started started, String fragment) {
        JsonObject match = null;
        JsonArray actions = started.session().legalActionsPayload().getAsJsonArray("actions");
        for (JsonElement element : actions) {
            JsonObject action = element.getAsJsonObject();
            if (action.getAsJsonObject("metadata").get("label").getAsString().contains(fragment)) {
                assertTrue(match == null, "unique option expected for " + fragment);
                match = action;
            }
        }
        assertNotNull(match, "no option labelled *" + fragment + "*: " + actions);
        return match;
    }

    /** The single option whose label does not contain {@code fragment}. */
    private static JsonObject labelledWithout(Started started, String fragment) {
        JsonObject match = null;
        JsonArray actions = started.session().legalActionsPayload().getAsJsonArray("actions");
        for (JsonElement element : actions) {
            JsonObject action = element.getAsJsonObject();
            if (!action.getAsJsonObject("metadata").get("label").getAsString().contains(fragment)) {
                assertTrue(match == null, "unique option without " + fragment + ": " + actions);
                match = action;
            }
        }
        assertNotNull(match, "no option without *" + fragment + "*: " + actions);
        return match;
    }

    /** Any option of a trigger-ordering choice (orders are equivalent where asserted). */
    private static JsonObject anyOrderingOption(Started started) {
        List<JsonObject> options = new ArrayList<>();
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            options.add(element.getAsJsonObject());
        }
        options.sort((left, right) -> left.get("action_id").getAsString()
                .compareTo(right.get("action_id").getAsString()));
        return options.get(0);
    }

    /** The option of an amount/X choice whose value is exactly {@code value}. */
    private static JsonObject amountOption(Started started, int value) {
        JsonObject match = null;
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata");
            JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
            String raw = engine != null && engine.has("value") ? engine.get("value").getAsString()
                    : meta.get("label").getAsString();
            if (raw.equals(Integer.toString(value))) {
                assertTrue(match == null, "unique amount option expected");
                match = action;
            }
        }
        assertNotNull(match, "amount " + value + " must be offered; options: "
                + started.session().legalActionsPayload().getAsJsonArray("actions"));
        return match;
    }

    // ------------------------------------------------------------------ cards

    /**
     * CARD_16 Psychosis Crawler: "power and toughness are each equal to the
     * number of cards in your hand" and "Whenever you draw a card, each
     * opponent loses 1 life." Divination draws two: each opponent loses 2.
     */
    @Test
    void psychosisCrawlerDrainsEachOpponentPerDrawAndTracksHandSize() {
        // The Crawler is cast, not restored: a pre-start battlefield Crawler
        // would (correctly) trigger on the opening-hand draws (CR 103.5).
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Island", 8));
        objects.add(hand("P1", "Psychosis Crawler", 0));
        objects.add(hand("P1", "Divination", 0));
        Started started = start("card16-crawler", 4, objects);
        cast(started, "card16-crawler-cast", "Psychosis Crawler");
        resolveAll(started, "card16-crawler", ISLAND_LABEL, NONE);
        for (String pid : List.of("P1", "P2", "P3", "P4")) {
            assertEquals(40, life(started, pid), "casting the Crawler draws nothing");
        }
        Permanent crawler = permanent(started, "P1", "Psychosis Crawler");
        assertEquals(handSize(started, "P1"),
                crawler.getPower().getValue(), "power equals hand size");

        cast(started, "card16-cast", "Divination");
        int[] orderings = {0};
        resolveAll(started, "card16", ISLAND_LABEL, (cls, step) -> {
            if ("trigger_order".equals(cls) && "P1".equals(actorPid(started))) {
                // Two draws put two identical Crawler triggers on the stack
                // at once (CR 603.3b); every order is semantically identical.
                submit(started, "card16-order-" + step,
                        equivalentOption(started, "Psychosis Crawler"));
                orderings[0]++;
                return true;
            }
            return false;
        });
        assertTrue(orderings[0] >= 1, "simultaneous Crawler triggers must be ordered explicitly");

        assertEquals(40, life(started, "P1"), "the controller loses nothing");
        for (String opponent : List.of("P2", "P3", "P4")) {
            assertEquals(38, life(started, opponent),
                    "two draws: " + opponent + " loses 1 per card drawn");
        }
        assertEquals(handSize(started, "P1"),
                permanent(started, "P1", "Psychosis Crawler").getPower().getValue(),
                "power still equals hand size after drawing");
        assertEquals(handSize(started, "P1"),
                permanent(started, "P1", "Psychosis Crawler").getToughness().getValue());
    }

    /**
     * CARD_17 Kaervek the Merciless: "Whenever an opponent casts a spell,
     * Kaervek deals damage equal to that spell's mana value to any target."
     * P2 casts Lightning Bolt (mana value 1) at P1; Kaervek's controller
     * aims the trigger at P2.
     */
    @Test
    void kaervekDealsTheOpponentSpellsManaValue() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Kaervek the Merciless", 0));
        objects.add(battlefield("P2", "Mountain", 0));
        objects.add(hand("P2", "Lightning Bolt", 0));
        Started started = start("card17-kaervek", 2, objects);

        XmageExternalRiskSignalTest.passToActor(
                started.session(), "card17", started.seats(), "P2");
        cast(started, "card17-bolt", "Lightning Bolt");
        assertEquals("target", decisionClass(started));
        submit(started, "card17-bolt-target", playerTarget(started, "P1"));
        boolean[] kaervekAimed = {false};
        resolveAll(started, "card17", MOUNTAIN_LABEL, (cls, step) -> {
            if ("target".equals(cls) && "P1".equals(actorPid(started))) {
                submit(started, "card17-trigger-" + step, playerTarget(started, "P2"));
                kaervekAimed[0] = true;
                return true;
            }
            return false;
        });

        assertTrue(kaervekAimed[0], "Kaervek's trigger must ask its controller for a target");
        assertEquals(39, life(started, "P2"), "mana value 1 spell: Kaervek deals 1");
        assertEquals(37, life(started, "P1"), "Lightning Bolt still deals 3");
    }

    private static Started surgeBoard(String tag, boolean violence) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Warstorm Surge", 0));
        if (violence) {
            objects.add(battlefield("P1", "Gratuitous Violence", 0));
        }
        objects.addAll(lands("P1", "Mountain", 3));
        objects.add(hand("P1", "Gray Ogre", 0));
        return start(tag, 2, objects);
    }

    private static void castOgreAndAimAt(Started started, String tag, String victim) {
        cast(started, tag + "-cast", "Gray Ogre");
        boolean[] aimed = {false};
        resolveAll(started, tag, MOUNTAIN_LABEL, (cls, step) -> {
            if ("target".equals(cls) && "P1".equals(actorPid(started))) {
                submit(started, tag + "-trigger-" + step, playerTarget(started, victim));
                aimed[0] = true;
                return true;
            }
            return false;
        });
        assertTrue(aimed[0], "the enters trigger must ask its controller for a target");
        assertEquals(1, onBattlefield(started, "P1", "Gray Ogre"));
    }

    /**
     * CARD_24 Warstorm Surge: "Whenever a creature you control enters, it
     * deals damage equal to its power to any target." Gray Ogre (power 2).
     */
    @Test
    void warstormSurgeHitsForTheEnteringCreaturesPower() {
        Started started = surgeBoard("card24-surge", false);
        castOgreAndAimAt(started, "card24", "P2");
        assertEquals(38, life(started, "P2"), "power 2 creature deals 2");
        assertEquals(40, life(started, "P1"));
    }

    /**
     * CARD_21 Gratuitous Violence: "If a creature you control would deal
     * damage to a permanent or player, it deals double that damage instead."
     * The Surge damage is dealt by the creature (Gray Ogre), so it doubles.
     */
    @Test
    void gratuitousViolenceDoublesCreatureDamage() {
        Started started = surgeBoard("card21-violence", true);
        castOgreAndAimAt(started, "card21", "P2");
        assertEquals(36, life(started, "P2"), "2 damage from a creature doubles to 4");
    }

    /**
     * CARD_19 Butcher of Malakir: "Whenever Butcher of Malakir or another
     * creature you control dies, each opponent sacrifices a creature." P1
     * bolts its own Raging Goblin; each of three opponents sacrifices its
     * only creature.
     */
    @Test
    void butcherMakesEachOpponentSacrificeWhenOwnCreatureDies() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Butcher of Malakir", 0));
        objects.add(battlefield("P1", "Raging Goblin", 0));
        objects.add(battlefield("P1", "Mountain", 0));
        objects.add(hand("P1", "Lightning Bolt", 0));
        for (String opponent : List.of("P2", "P3", "P4")) {
            objects.add(battlefield(opponent, "Grizzly Bears", 0));
        }
        Started started = start("card19-butcher", 4, objects);
        Permanent goblin = permanent(started, "P1", "Raging Goblin");

        cast(started, "card19-bolt", "Lightning Bolt");
        assertEquals("target", decisionClass(started));
        submit(started, "card19-bolt-target", permanentTarget(started, goblin));
        resolveAll(started, "card19", MOUNTAIN_LABEL, (cls, step) -> {
            String actor = actorPid(started);
            if (!"P1".equals(actor) && ("target".equals(cls) || "choose_object".equals(cls))) {
                chooseNamed(started, "card19-sac-" + step, "Grizzly Bears", 1);
                return true;
            }
            return false;
        });

        assertEquals(1, inGraveyard(started, "P1", "Raging Goblin"));
        assertEquals(1, onBattlefield(started, "P1", "Butcher of Malakir"));
        for (String opponent : List.of("P2", "P3", "P4")) {
            assertEquals(0, onBattlefield(started, opponent, "Grizzly Bears"),
                    opponent + " must sacrifice a creature");
            assertEquals(1, inGraveyard(started, opponent, "Grizzly Bears"));
        }
    }

    /**
     * CARD_20 Syphon Mind: "Each other player discards a card. You draw a
     * card for each card discarded this way." Four players: three discards,
     * three draws.
     */
    @Test
    void syphonMindDrawsOnePerOpponentDiscard() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Swamp", 4));
        objects.add(hand("P1", "Syphon Mind", 0));
        Started started = start("card20-syphon", 4, objects);
        int p1Hand = handSize(started, "P1");
        int[] opponentHands = {
                handSize(started, "P2"), handSize(started, "P3"), handSize(started, "P4")};

        cast(started, "card20-cast", "Syphon Mind");
        resolveAll(started, "card20", SWAMP_LABEL, (cls, step) -> {
            if (!"P1".equals(actorPid(started)) && "choose_object".equals(cls)) {
                // Opening hands are all Mountains, so every discard choice
                // is semantically identical.
                chooseNamed(started, "card20-discard-" + step, "Mountain", 1);
                return true;
            }
            return false;
        });

        assertEquals(p1Hand - 1 + 3, handSize(started, "P1"),
                "Syphon Mind leaves the hand, then three cards are drawn");
        List<String> opponents = List.of("P2", "P3", "P4");
        for (int index = 0; index < opponents.size(); index++) {
            String opponent = opponents.get(index);
            assertEquals(opponentHands[index] - 1, handSize(started, opponent),
                    opponent + " discards exactly one card");
            assertEquals(1, inGraveyard(started, opponent, "Mountain"));
        }
        assertEquals(1, inGraveyard(started, "P1", "Syphon Mind"));
    }
}
