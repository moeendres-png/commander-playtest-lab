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
    static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";
    private static final String ISLAND_LABEL = "Island — {T}: Add {U}.";
    static final String SWAMP_LABEL = "Swamp — {T}: Add {B}.";
    private static final long SEED = 424242L;
    private static final String PATH_LABEL = "Path of Ancestry \u2014 {T}: Add one mana of any "
            + "color in your commander's color identity. When that mana is spent to cast a "
            + "creature spell that shares a creature type with your commander, scry 1. "
            + "<i>(Look at the top card of your library. You may put that card on the bottom "
            + "of your library.)</i>";

    record Started(
            XmageFullGameSession session,
            Map<String, Player> seats,
            XmageNativeStateRestoration restoration) {
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
    static Started start(
            String tag, int playerCount,
            List<XmageNativeStateRestoration.RequestedObject> objects) {
        return start(tag, playerCount, objects, Map.of(), 0);
    }

    /**
     * As {@link #start(String, int, List)}, but P-ids in {@code extraCommanders}
     * get a partner commander next to Rograkh (both have partner), and
     * {@code forests} Mountains are replaced by Forests in the decks of those
     * players only (a basic Forest has green colour identity, so it needs a
     * green partner commander).
     */
    static Started start(
            String tag, int playerCount,
            List<XmageNativeStateRestoration.RequestedObject> objects,
            Map<String, String> extraCommanders, int forests) {
        return start(tag, playerCount, objects, extraCommanders, forests, SEED);
    }

    /** As above, with an explicit Rules seed (for Rules-RNG reproducibility probes). */
    static Started start(
            String tag, int playerCount,
            List<XmageNativeStateRestoration.RequestedObject> objects,
            Map<String, String> extraCommanders, int forests, long seed) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", ROGRAKH, pid, 0));
            if (extraCommanders.containsKey(pid)) {
                commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                        "cmd:" + pid + "-B", extraCommanders.get(pid), pid, 0));
            }
        }
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                tag, playerCount, seed, List.copyOf(players), List.copyOf(commanders),
                List.copyOf(objects),
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedPlayer player : players) {
            String extra = extraCommanders.get(player.playerId());
            List<String> deckCommanders = extra == null ? List.of(ROGRAKH) : List.of(ROGRAKH, extra);
            List<String> mainboard = new ArrayList<>();
            for (int index = 0; index < 100 - deckCommanders.size(); index++) {
                mainboard.add(extra != null && index < forests ? "Forest" : "Mountain");
            }
            handles.add(importer.importCommanderDeck(
                    tag + "-" + player.playerId(), tag + "-hash",
                    mainboard, deckCommanders).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new Started(session, seats, restoration);
    }

    // ---------------------------------------------------------------- queries

    private static int life(Started started, String pid) {
        return started.seats().get(pid).getLife();
    }

    private static int handSize(Started started, String pid) {
        return started.seats().get(pid).getHand().size();
    }

    static int onBattlefield(Started started, String pid, String name) {
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

    static int inGraveyard(Started started, String pid, String name) {
        int count = 0;
        for (Card card : started.seats().get(pid).getGraveyard()
                .getCards(started.session().restorationGame())) {
            if (name.equals(card.getName())) {
                count++;
            }
        }
        return count;
    }

    static String decisionClass(Started started) {
        JsonObject payload = started.session().pendingDecisionPayload();
        if (payload.get("decision").isJsonNull()) {
            fail("engine terminal while a decision was expected");
        }
        return payload.getAsJsonObject("decision").get("decision_class").getAsString();
    }

    static String actorPid(Started started) {
        return XmageNativeStateRestorationTest.pidOf(started.seats(),
                started.session().legalActionsPayload().get("actor_id").getAsString());
    }

    // ---------------------------------------------------------------- actions

    static void submit(Started started, String tag, JsonObject action) {
        XmageFullGameTaxExecutionTest.submit(started.session(), tag, action);
    }

    static void pass(Started started, String tag) {
        submit(started, tag, XmageFullGameTaxExecutionTest.singleActionOfType(
                started.session().legalActionsPayload(), "pass_priority", null));
    }

    static void cast(Started started, String tag, String cardName) {
        submit(started, tag, XmageExternalRiskSignalTest.spellOffer(
                started.session().legalActionsPayload(), cardName));
    }

    /** The target option naming exactly this player, by engine identity. */
    static JsonObject playerTarget(Started started, String pid) {
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
    static void chooseNamed(Started started, String tag, String requiredName, int count) {
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
    static void resolveAll(
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
                        payOneFromRestoredMana(
                                started,
                                tag + "-pay-" + step,
                                List.of(manaSourceName(manaLabel)),
                                java.util.Set.of(manaLabel));
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

    static final BiFunction<String, Integer, Boolean> NONE = (cls, step) -> false;

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

    private static JsonObject singleOffer(
            List<JsonObject> options, String description) {
        assertEquals(
                1,
                options.size(),
                description + " must have exactly one engine-offered option: " + options);
        return options.get(0);
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
    private static String manaSourceName(String label) {
        int separator = label.indexOf(" — ");
        assertTrue(separator > 0, "mana label must expose a semantic source name: " + label);
        return label.substring(0, separator);
    }

    private static String manaTypeForBasic(String sourceName) {
        return switch (sourceName) {
            case "Plains" -> "white";
            case "Island" -> "blue";
            case "Swamp" -> "black";
            case "Mountain" -> "red";
            case "Forest" -> "green";
            // Fixture-scoped: every commander here is Rograkh (colour identity
            // red), so Path of Ancestry can only produce red.
            case "Path of Ancestry" -> "red";
            default -> throw new AssertionError("unsupported scripted basic source " + sourceName);
        };
    }

    private static String manaSymbolForBasic(String sourceName) {
        return switch (sourceName) {
            case "Plains" -> "{W}";
            case "Island" -> "{U}";
            case "Swamp" -> "{B}";
            case "Mountain" -> "{R}";
            case "Forest" -> "{G}";
            case "Path of Ancestry" -> "{R}";
            default -> throw new AssertionError("unsupported scripted basic source " + sourceName);
        };
    }

    private static String unpaidMana(Started started) {
        JsonObject pending = started.session().pendingDecisionPayload().getAsJsonObject("decision");
        assertEquals("mana_payment", pending.get("decision_class").getAsString());
        JsonObject context =
                pending.has("context") && pending.get("context").isJsonObject()
                        ? pending.getAsJsonObject("context")
                        : new JsonObject();
        if (context.has("unpaid_mana") && !context.get("unpaid_mana").isJsonNull()) {
            return context.get("unpaid_mana").getAsString();
        }
        String prompt =
                pending.has("prompt") && !pending.get("prompt").isJsonNull()
                        ? pending.get("prompt").getAsString()
                        : "";
        return prompt.contains("<") ? prompt.substring(0, prompt.indexOf('<')) : prompt;
    }

    /**
     * Submits exactly one engine-offered mana decision from an explicit
     * fixture-scripted semantic source. Returning after one decision is
     * intentional: legal target/trigger choices may intervene between payment
     * callbacks and must return to resolveAll rather than being swallowed by a
     * payment helper.
     */
    private static boolean payOneFromRestoredMana(
            Started started,
            String tag,
            List<String> sourcePreference,
            java.util.Set<String> allowedLabels) {
        assertTrue(!sourcePreference.isEmpty(), "[" + tag + "] scripted mana source required");
        String pid = actorPid(started);
        String unpaid = unpaidMana(started);

        List<String> desired = new ArrayList<>();
        for (String sourceName : sourcePreference) {
            if (unpaid.contains(manaSymbolForBasic(sourceName))) {
                desired.add(sourceName);
            }
        }
        if (desired.isEmpty()) {
            desired.addAll(sourcePreference);
        }

        JsonArray actions = started.session().legalActionsPayload().getAsJsonArray("actions");
        List<JsonObject> mana = new ArrayList<>();
        List<JsonObject> pool = new ArrayList<>();
        for (JsonElement element : actions) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType =
                    metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                            ? metadata.get("option_type").getAsString()
                            : "";
            if ("mana_ability".equals(optionType)) {
                mana.add(action);
            } else if ("mana_pool".equals(optionType)) {
                pool.add(action);
            }
        }

        for (String sourceName : desired) {
            String wantedManaType = manaTypeForBasic(sourceName);
            List<JsonObject> poolMatches = new ArrayList<>();
            for (JsonObject action : pool) {
                JsonObject metadata = action.getAsJsonObject("metadata");
                JsonObject engine =
                        metadata.has("xmage_option_metadata")
                                        && metadata.get("xmage_option_metadata").isJsonObject()
                                ? metadata.getAsJsonObject("xmage_option_metadata")
                                : new JsonObject();
                String manaType =
                        engine.has("mana_type") && !engine.get("mana_type").isJsonNull()
                                ? engine.get("mana_type").getAsString()
                                : metadata.has("mana_type") && !metadata.get("mana_type").isJsonNull()
                                        ? metadata.get("mana_type").getAsString()
                                        : "";
                if (wantedManaType.equalsIgnoreCase(manaType)) {
                    poolMatches.add(action);
                }
            }
            assertTrue(
                    poolMatches.size() <= 1,
                    "[" + tag + "] ambiguous " + wantedManaType + " pool spend");
            if (poolMatches.size() == 1) {
                submit(started, tag + "-spend-" + wantedManaType, poolMatches.get(0));
                return true;
            }

            for (XmageNativeStateRestoration.RequestedObject object
                    : started.restoration().plan().objects()) {
                if (object.zone() != mage.constants.Zone.BATTLEFIELD
                        || !pid.equals(object.controller())
                        || !sourceName.equals(object.cardIdentity())) {
                    continue;
                }
                String sourceId =
                        started.restoration().injectedObjectId(object.semanticId()).toString();
                List<JsonObject> matches = new ArrayList<>();
                for (JsonObject action : mana) {
                    JsonObject metadata = action.getAsJsonObject("metadata");
                    JsonObject engine =
                            metadata.has("xmage_option_metadata")
                                            && metadata.get("xmage_option_metadata").isJsonObject()
                                    ? metadata.getAsJsonObject("xmage_option_metadata")
                                    : new JsonObject();
                    if (engine.has("source_object_id")
                            && !engine.get("source_object_id").isJsonNull()
                            && sourceId.equals(engine.get("source_object_id").getAsString())) {
                        matches.add(action);
                    }
                }
                assertTrue(
                        matches.size() <= 1,
                        "[" + tag + "] ambiguous mana action for " + object.semanticId());
                if (matches.size() == 1) {
                    JsonObject selected = matches.get(0);
                    String label = selected.getAsJsonObject("metadata").get("label").getAsString();
                    assertTrue(
                            allowedLabels.contains(label),
                            "[" + tag + "] scripted source offered unexpected label " + label);
                    submit(started, tag + "-tap-" + object.semanticId(), selected);
                    return true;
                }
            }
        }

        fail("[" + tag + "] no scripted mana decision for unpaid " + unpaid
                + "; actions=" + actions);
        return false;
    }

    private static boolean payAllFromRestoredMana(
            Started started,
            String tag,
            List<String> sourcePreference,
            java.util.Set<String> allowedLabels) {
        for (int step = 0; step < 30; step++) {
            JsonObject pending =
                    started.session().pendingDecisionPayload().getAsJsonObject("decision");
            if (pending.isJsonNull()
                    || !"mana_payment".equals(
                            pending.get("decision_class").getAsString())) {
                return true;
            }
            payOneFromRestoredMana(
                    started,
                    tag + "-" + step,
                    sourcePreference,
                    allowedLabels);
        }
        fail("[" + tag + "] mana-payment bound breached");
        return false;
    }

    private static boolean payGolgari(Started started, String tag) {
        return payOneFromRestoredMana(
                started,
                tag,
                List.of("Forest", "Swamp"),
                java.util.Set.of(
                        SWAMP_LABEL,
                        "Forest — {T}: Add {G}."));
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

        List<JsonObject> finality =
                offers(started, "Finality", "Cast Finality", true);
        submit(
                started,
                "card28-cast",
                singleOffer(finality, "Finality cast from hand (no aftermath)"));
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

        submit(
                started,
                "card14-cast",
                singleOffer(
                        offers(started, "Vandalblast", "overload", false),
                        "normal Vandalblast cast"));
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
        chooseNamed(started, "card14-target", "Ornithopter", 1);
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
        submit(
                started,
                "card14o-cast",
                singleOffer(overload, "Vandalblast overload cast"));
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
                submit(
                        started,
                        "card06-order-" + step,
                        triggerOrderOption(
                                started,
                                "Harmonic Prodigy",
                                "Young Pyromancer"));
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
        payAllFromRestoredMana(
                started,
                "card10-bolt-pay",
                List.of("Mountain"),
                java.util.Set.of(MOUNTAIN_LABEL));
        XmageExternalRiskSignalTest.passToActor(
                started.session(), "card10-respond", started.seats(), "P1");
        assertEquals(0, offers(started, "Wash Away", "leave", false).size(),
                "uncleaved Wash Away has no legal target: the Bolt was cast from hand");
        List<JsonObject> cleave = offers(started, "Wash Away", "leave", true);
        submit(
                started,
                "card10-cleave",
                singleOffer(cleave, "Wash Away cleave cast"));
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
        payAllFromRestoredMana(
                started,
                "card13-bolt-pay",
                List.of("Mountain"),
                java.util.Set.of(MOUNTAIN_LABEL));
        List<JsonObject> flare = offers(started, "Flare of Duplication", "", true);
        submit(
                started,
                "card13-flare",
                singleOffer(flare, "Flare of Duplication cast"));
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
        payAllFromRestoredMana(
                started,
                "card22-bolt-pay",
                List.of("Mountain"),
                java.util.Set.of(MOUNTAIN_LABEL));
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
        submit(
                started,
                "card11-fuse",
                singleOffer(fused, "Wear // Tear fused cast"));
        resolveAll(started, "card11", null, (cls, step) -> {
            if ("target".equals(cls)) {
                List<String> names = offeredTargetNames(started);
                String pick = names.contains("Ornithopter") && !names.contains("Warstorm Surge")
                        ? "Ornithopter" : "Warstorm Surge";
                chooseNamed(started, "card11-target-" + step, pick, 1);
                return true;
            }
            if ("mana_payment".equals(cls)) {
                return payOneFromRestoredMana(
                        started,
                        "card11-pay-" + step,
                        List.of("Plains", "Mountain"),
                        java.util.Set.of(
                                MOUNTAIN_LABEL,
                                "Plains — {T}: Add {W}."));
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
                submit(
                        started,
                        "card18e-order-" + step,
                        triggerOrderByLabel(started, "destroy target"));
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

    // ---------------------------------------------------------- batch 4 cards

    private static int tappedCount(Started started, String pid, String name) {
        int count = 0;
        for (Permanent permanent : started.session().restorationGame()
                .getBattlefield().getAllPermanents()) {
            if (name.equals(permanent.getName()) && permanent.isTapped()
                    && started.seats().get(pid).getId().equals(permanent.getControllerId())) {
                count++;
            }
        }
        return count;
    }

    private static String prompt(Started started) {
        JsonObject pending = started.session().pendingDecisionPayload().getAsJsonObject("decision");
        return pending.has("prompt") && !pending.get("prompt").isJsonNull()
                ? pending.get("prompt").getAsString() : "";
    }

    /** Answers the owner's commander-zone replacement choice explicitly by label. */
    private static boolean moveToCommandZone(Started started, String cls, int step, String tag) {
        if ("choose_use".equals(cls) && prompt(started).toLowerCase().contains("command")) {
            submit(started, tag + "-cmdzone-" + step, labelled(started, "command"));
            return true;
        }
        return false;
    }

    /**
     * CARD_03 Esior, Wardwing Familiar: "Spells your opponents cast that
     * target one or more commanders you control cost {3} more to cast." The
     * same Lightning Bolt costs P2 one Mountain at P1 and four at Esior.
     */
    @Test
    void esiorTaxesOpponentSpellsTargetingItsControllersCommander() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Island", 2));
        objects.addAll(lands("P2", "Mountain", 5));
        objects.add(hand("P2", "Shock", 0));
        objects.add(hand("P2", "Lightning Bolt", 0));
        Started started = start("card03-esior", 2, objects,
                Map.of("P1", "Esior, Wardwing Familiar"), 0);

        submit(started, "card03-cast-esior", XmageFullGameTaxExecutionTest.castOffer(
                started.session().legalActionsPayload(), "Esior, Wardwing Familiar"));
        resolveAll(started, "card03-esior", ISLAND_LABEL, NONE);
        Permanent esior = permanent(started, "P1", "Esior, Wardwing Familiar");

        XmageExternalRiskSignalTest.passToActor(started.session(), "card03-a", started.seats(), "P2");
        cast(started, "card03-shock-p1", "Shock");
        submit(started, "card03-shock-p1-target", playerTarget(started, "P1"));
        resolveAll(started, "card03-p1", MOUNTAIN_LABEL, NONE);
        assertEquals(1, tappedCount(started, "P2", "Mountain"), "untaxed Shock costs {R}");
        assertEquals(38, life(started, "P1"));

        XmageExternalRiskSignalTest.passToActor(started.session(), "card03-b", started.seats(), "P2");
        cast(started, "card03-bolt-esior", "Lightning Bolt");
        submit(started, "card03-bolt-esior-target", permanentTarget(started, esior));
        resolveAll(started, "card03-esior-kill", MOUNTAIN_LABEL,
                (cls, step) -> moveToCommandZone(started, cls, step, "card03"));
        assertEquals(5, tappedCount(started, "P2", "Mountain"),
                "targeting P1's commander costs {3} more: four more Mountains");
        assertEquals(0, onBattlefield(started, "P1", "Esior, Wardwing Familiar"),
                "3 damage to a 1/3 is lethal");
    }

    /**
     * CARD_08 Jeska, Thrice Reborn: "enters with a loyalty counter on her for
     * each time you've cast a commander from the command zone this game."
     * Ruling 2020-11-10: casting Jeska as your commander counts. First cast
     * from the command zone: one loyalty. "-X: Jeska deals X damage to each
     * of up to three targets." X = 1 at P2.
     */
    @Test
    void jeskaEntersWithLoyaltyPerCommanderCastAndMinusXBurns() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Mountain", 3));
        Started started = start("card08-jeska", 2, objects,
                Map.of("P1", "Jeska, Thrice Reborn"), 0);

        submit(started, "card08-cast", XmageFullGameTaxExecutionTest.castOffer(
                started.session().legalActionsPayload(), "Jeska, Thrice Reborn"));
        resolveAll(started, "card08", MOUNTAIN_LABEL, NONE);
        Permanent jeska = permanent(started, "P1", "Jeska, Thrice Reborn");
        assertEquals(1, jeska.getCounters(started.session().restorationGame())
                .getCount(mage.counters.CounterType.LOYALTY),
                "one commander cast from the command zone (Jeska herself)");

        JsonObject minusX = null;
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            String label = action.getAsJsonObject("metadata").get("label").getAsString();
            if (label.startsWith("Jeska") && (label.contains("-X") || label.contains("−X"))) {
                assertTrue(minusX == null, "unique -X offer");
                minusX = action;
            }
        }
        assertNotNull(minusX, "the -X loyalty ability must be offered: "
                + started.session().legalActionsPayload().getAsJsonArray("actions"));
        submit(started, "card08-minus-x", minusX);
        boolean[] targeted = {false};
        resolveAll(started, "card08-x", MOUNTAIN_LABEL, (cls, step) -> {
            if ("announce_x".equals(cls)) {
                submitNumeric(started, "card08-x-" + step, 1);
                return true;
            }
            if ("target".equals(cls) && !targeted[0]) {
                submit(started, "card08-target-" + step, playerTarget(started, "P2"));
                targeted[0] = true;
                return true;
            }
            if ("target".equals(cls)) {
                // "up to three targets": stop after P2.
                chooseNone(started, "card08-stop-" + step);
                return true;
            }
            return moveToCommandZone(started, cls, step, "card08");
        });
        assertTrue(targeted[0], "Jeska's -X must ask for targets");
        assertEquals(39, life(started, "P2"), "X = 1 deals 1");
    }

    /** Selects exactly these engine object ids from a multi-select target decision. */
    private static void chooseByObjectIds(Started started, String tag, List<String> objectIds) {
        XmageFullGameSession session = started.session();
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        List<String> selected = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
            JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
            if (engine != null && engine.has("object_id")
                    && objectIds.contains(engine.get("object_id").getAsString())) {
                selected.add(meta.get("option_id").getAsString());
            }
        }
        assertEquals(objectIds.size(), selected.size(), "every requested target must be offered");
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

    /** Answers a divided-amount target decision: one target by engine id plus its amount. */
    private static void submitTargetAmount(Started started, String tag, String objectId, int amount) {
        XmageFullGameSession session = started.session();
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        String optionId = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
            JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
            if (engine != null && engine.has("object_id")
                    && objectId.equals(engine.get("object_id").getAsString())) {
                assertTrue(optionId == null, "unique target option expected");
                optionId = meta.get("option_id").getAsString();
            }
        }
        assertNotNull(optionId, "target must be engine-offered: " + objectId);
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", decisionId + ":" + optionId);
        proposal.addProperty("action_type", "choose_targets");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        JsonArray selected = new JsonArray();
        selected.add(optionId);
        choices.add("selected_option_ids", selected);
        choices.addProperty("numeric_choice", amount);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = session.submitAction(proposal);
        assertEquals(decisionId, after.get("executed_decision_id").getAsString());
    }

    /**
     * CARD_04 Kediss, Emberclaw Familiar: "Whenever a commander you control
     * deals combat damage to an opponent, it deals that much damage to each
     * other opponent." Ruling 2020-11-10: the extra damage is not combat
     * damage. Three players; Kediss (1/1, P1's partner commander) is cast on
     * turn 1 and attacks P2 on P1's next turn (turn 4).
     */
    @Test
    void kedissMirrorsCommanderCombatDamageToEachOtherOpponent() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Mountain", 2));
        Started started = start("card04-kediss", 3, objects,
                Map.of("P1", "Kediss, Emberclaw Familiar"), 0);
        submit(started, "card04-cast", XmageFullGameTaxExecutionTest.castOffer(
                started.session().legalActionsPayload(), "Kediss, Emberclaw Familiar"));
        resolveAll(started, "card04-cast", MOUNTAIN_LABEL, NONE);
        assertEquals(1, onBattlefield(started, "P1", "Kediss, Emberclaw Familiar"));

        mage.game.Game game = started.session().restorationGame();
        java.util.UUID p2 = started.seats().get("P2").getId();
        boolean attacked = false;
        for (int step = 0; step < 400; step++) {
            if (attacked && life(started, "P2") < 40 && game.getStack().isEmpty()
                    && "priority".equals(decisionClass(started))) {
                break;
            }
            String cls = decisionClass(started);
            String actor = actorPid(started);
            JsonObject legal = started.session().legalActionsPayload();
            switch (cls) {
                case "priority" -> pass(started, "card04-pass-" + step);
                case "declare_attacker" -> {
                    boolean kedissTurn = "P1".equals(actor)
                            && game.getState().getTurnNum() >= 4;
                    JsonObject action = null;
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        JsonObject candidate = element.getAsJsonObject();
                        JsonObject meta = candidate.getAsJsonObject("metadata")
                                .getAsJsonObject("xmage_option_metadata");
                        if (kedissTurn && meta != null && meta.has("defender_id")
                                && p2.toString().equals(meta.get("defender_id").getAsString())) {
                            assertTrue(action == null, "unique attack at P2 expected");
                            action = candidate;
                        }
                    }
                    if (kedissTurn) {
                        assertNotNull(action, "Kediss must be able to attack P2: " + legal);
                        attacked = true;
                    } else {
                        action = XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "declare_attackers", "hold_attacker");
                    }
                    submit(started, "card04-attack-" + step, action);
                }
                case "declare_blocker" -> chooseNone(started, "card04-noblock-" + step);
                case "choose_object" -> {
                    // Cleanup discard to seven: hands hold only Mountains.
                    JsonObject pending = started.session().pendingDecisionPayload()
                            .getAsJsonObject("decision");
                    chooseNamed(started, "card04-discard-" + step, "Mountain",
                            Math.max(1, pending.get("minimum_selections").getAsInt()));
                }
                default -> fail("unexpected decision " + cls + " for " + actor);
            }
        }
        assertTrue(attacked, "Kediss attacked on P1's next turn");
        assertEquals(39, life(started, "P2"), "1 combat damage from the commander");
        assertEquals(39, life(started, "P3"), "Kediss mirrors it to each other opponent");
        assertEquals(40, life(started, "P1"), "the controller is not an opponent");
    }

    /**
     * Selects {@code count} options named exactly {@code name} from a choice
     * that may also offer other cards. Same-named cards are rules-identical
     * here, so which copy is taken does not matter.
     */
    static void chooseByExactName(Started started, String tag, String name, int count) {
        XmageFullGameSession session = started.session();
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        List<String> matching = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
            JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
            String optionName = engine != null && engine.has("name")
                    ? engine.get("name").getAsString() : meta.get("label").getAsString();
            if (name.equals(optionName)) {
                matching.add(meta.get("option_id").getAsString());
            }
        }
        assertTrue(matching.size() >= count, "need " + count + " x " + name + ": " + legal);
        matching.sort(String::compareTo);
        List<String> selected = matching.subList(0, count);
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
     * CARD_29 Boseiju Reaches Skyward // Branch of Boseiju (saga). I: search
     * for up to two basic Forest cards, reveal them, put them into your hand.
     * II: put up to one target land card from your graveyard on top of your
     * library. III: exile this Saga, then return it transformed. Branch of
     * Boseiju: reach, +1/+1 for each land you control (0/0 base).
     */
    @Test
    void boseijuSagaSearchesRecursesAndTransforms() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Forest", 0));
        objects.addAll(lands("P1", "Mountain", 3));
        objects.add(hand("P1", "Boseiju Reaches Skyward", 0));
        objects.add(object("gy", mage.constants.Zone.GRAVEYARD, "P1", "Mountain", 9));
        // Tana, the Bloodsower (R/G, Partner) makes Forests legal for P1.
        Started started = start("card29-boseiju", 2, objects,
                Map.of("P1", "Tana, the Bloodsower"), 2);
        mage.game.Game game = started.session().restorationGame();
        Player p1 = started.seats().get("P1");

        submit(started, "card29-cast", singleOffer(
                offers(started, "Boseiju Reaches Skyward", "", true),
                "Boseiju cast"));
        boolean[] searched = {false};
        boolean[] recursed = {false};
        java.util.UUID[] recurredCard = {null};
        for (int step = 0; step < 600; step++) {
            if (onBattlefield(started, "P1", "Branch of Boseiju") == 1
                    && game.getStack().isEmpty() && "priority".equals(decisionClass(started))) {
                break;
            }
            String cls = decisionClass(started);
            String actor = actorPid(started);
            String text = prompt(started).toLowerCase();
            JsonObject pending = started.session().pendingDecisionPayload()
                    .getAsJsonObject("decision");
            if (recurredCard[0] != null && !recursed[0] && "priority".equals(cls)
                    && game.getStack().isEmpty()) {
                // Chapter II resolved; P1 has not drawn again yet.
                mage.cards.Card top = p1.getLibrary().getFromTop(game);
                assertNotNull(top, "P1's library has a top card");
                assertEquals(recurredCard[0], top.getId(),
                        "chapter II put the chosen graveyard Mountain on top of the library");
                assertTrue(p1.getGraveyard().getCards(game).stream()
                                .noneMatch(card -> card.getId().equals(recurredCard[0])),
                        "the recurred Mountain left the graveyard");
                recursed[0] = true;
            }
            switch (cls) {
                case "priority" -> pass(started, "card29-pass-" + step);
                case "mana_payment" -> payOneFromRestoredMana(started, "card29-pay-" + step,
                        List.of("Forest", "Mountain"),
                        java.util.Set.of("Forest — {T}: Add {G}.", MOUNTAIN_LABEL));
                case "declare_attacker" -> submit(started, "card29-hold-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                started.session().legalActionsPayload(),
                                "declare_attackers", "hold_attacker"));
                case "declare_blocker" -> chooseNone(started, "card29-noblock-" + step);
                case "choose_object", "target" -> {
                    if ("P1".equals(actor) && text.contains("basic forest")) {
                        // Chapter I: every Forest the library still holds
                        // (one may already be in the opening hand).
                        int offeredForests = started.session().legalActionsPayload()
                                .getAsJsonArray("actions").size();
                        chooseByExactName(started, "card29-search-" + step, "Forest",
                                Math.min(offeredForests, pending.get("maximum_selections").getAsInt()));
                        searched[0] = true;
                    } else if ("P1".equals(actor) && text.contains("land card from your graveyard")) {
                        // Chapter II: a Mountain from P1's graveyard to the top.
                        // Remember its engine id so the zone move is verified.
                        String chosen = null;
                        for (JsonElement element : started.session().legalActionsPayload()
                                .getAsJsonArray("actions")) {
                            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                                    .getAsJsonObject("xmage_option_metadata");
                            if (meta != null && meta.has("object_id") && meta.has("name")
                                    && "Mountain".equals(meta.get("name").getAsString())
                                    && (chosen == null
                                            || meta.get("object_id").getAsString().compareTo(chosen) < 0)) {
                                chosen = meta.get("object_id").getAsString();
                            }
                        }
                        assertNotNull(chosen, "a graveyard Mountain must be offered");
                        chooseByObjectIds(started, "card29-recur-" + step, List.of(chosen));
                        recurredCard[0] = java.util.UUID.fromString(chosen);
                    } else if (text.contains("discard")) {
                        // Cleanup discard to seven: discard Mountains only.
                        chooseByExactName(started, "card29-discard-" + step, "Mountain",
                                Math.max(1, pending.get("minimum_selections").getAsInt()));
                    } else {
                        fail("unexpected object choice for " + actor + ": " + text);
                    }
                }
                default -> fail("unexpected decision " + cls + " for " + actor + ": " + text);
            }
        }
        assertTrue(searched[0], "chapter I searched for basic Forests");
        assertTrue(recursed[0],
                "chapter II's zone move (graveyard to library top) was observed before the next draw");
        long lands = game.getBattlefield().getAllActivePermanents(p1.getId()).stream()
                .filter(permanent -> permanent.isLand(game)).count();
        Permanent branch = permanent(started, "P1", "Branch of Boseiju");
        assertEquals(lands, branch.getPower().getValue(), "+1/+1 for each land (0/0 base)");
        assertEquals(lands, branch.getToughness().getValue());
        assertTrue(branch.hasAbility(mage.abilities.keyword.ReachAbility.getInstance(), game),
                "Branch of Boseiju has reach");
        long forestsInHand = p1.getHand().getCards(game).stream()
                .filter(card -> "Forest".equals(card.getName())).count();
        assertEquals(2, forestsInHand,
                "the deck's two Forests end in hand (chapter I; only Mountains are discarded)");
    }

    /** Submits an empty selection for an optional (minimum 0) target/object choice. */
    static void chooseNone(Started started, String tag) {
        XmageFullGameSession session = started.session();
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        assertEquals(0, pending.get("minimum_selections").getAsInt(),
                "only an optional choice may be left empty: " + pending);
        JsonObject legal = session.legalActionsPayload();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", "");
        proposal.addProperty("action_type", "structural_decision");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", pending.get("decision_id").getAsString());
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", new JsonArray());
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        JsonObject after = session.submitAction(proposal);
        assertEquals(pending.get("decision_id").getAsString(),
                after.get("executed_decision_id").getAsString());
    }

    /**
     * CARD_27 Path of Ancestry: "{T}: Add one mana of any color in your
     * commander's color identity. When that mana is spent to cast a creature
     * spell that shares a creature type with your commander, scry 1." Rograkh
     * is a Kobold Warrior (Oracle): Goblin Piker (Goblin Warrior) paid partly
     * with Path mana scries; Kird Ape (Ape) paid with Path mana does not.
     */
    @Test
    void pathOfAncestryScriesForACreatureSharingACommanderType() {
        pathOfAncestryProbe("Goblin Piker");
    }

    @Test
    void pathOfAncestryDoesNotScryForACreatureSharingNoCommanderType() {
        pathOfAncestryProbe("Kird Ape");
    }

    /**
     * CARD_27 Path of Ancestry: "{T}: Add one mana of any color in your
     * commander's color identity. When that mana is spent to cast a creature
     * spell that shares a creature type with your commander, scry 1." Rograkh
     * is a Kobold Warrior (Oracle): Goblin Piker (Goblin Warrior) paid partly
     * with Path mana scries; Kird Ape (Ape) paid with Path mana does not.
     */
    private static void pathOfAncestryProbe(String creature) {
        {
            boolean shares = "Goblin Piker".equals(creature);
            List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
            objects.add(battlefield("P1", "Path of Ancestry", 0));
            if (shares) {
                objects.add(battlefield("P1", "Mountain", 0));
            }
            objects.add(hand("P1", creature, 0));
            String tag = "card27-" + (shares ? "piker" : "ape");
            Started started = start(tag, 2, objects);
            cast(started, tag + "-cast", creature);
            boolean[] scried = {false};
            resolveAll(started, tag, null, (cls, step) -> {
                if ("mana_payment".equals(cls)) {
                    return payOneFromRestoredMana(started, tag + "-pay-" + step,
                            List.of("Path of Ancestry", "Mountain"),
                            java.util.Set.of(PATH_LABEL, MOUNTAIN_LABEL));
                }
                if ("choice".equals(cls) && prompt(started).toLowerCase().contains("color")) {
                    submit(started, tag + "-red-" + step, labelled(started, "Red"));
                    return true;
                }
                String text = prompt(started).toLowerCase();
                if (text.contains("scry") || text.contains("bottom")) {
                    scried[0] = true;
                    if ("choose_use".equals(cls)) {
                        submit(started, tag + "-scry-" + step, booleanOption(started, false));
                    } else {
                        chooseNone(started, tag + "-scry-" + step);
                    }
                    return true;
                }
                return false;
            });
            assertEquals(1, onBattlefield(started, "P1", creature));
            assertEquals(shares, scried[0], shares
                    ? "Path mana spent on a creature sharing Rograkh's Warrior type must scry 1"
                    : "a creature sharing no type with the commander must not scry");
        }
    }

    /**
     * CARD_12 Dig Through Time: "Delve. Look at the top seven cards of your
     * library. Put two of them into your hand and the rest on the bottom of
     * your library in any order." Six graveyard cards pay the {6}; two
     * Islands pay {U}{U}.
     */
    @Test
    void digThroughTimeDelvesSixAndKeepsTwoOfSeven() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.addAll(lands("P1", "Island", 2));
        for (int index = 0; index < 6; index++) {
            objects.add(object("gy", mage.constants.Zone.GRAVEYARD, "P1", "Memnite", index));
        }
        objects.add(hand("P1", "Dig Through Time", 0));
        Started started = start("card12-dig", 2, objects);
        int handBefore = handSize(started, "P1");
        int libraryBefore = started.seats().get("P1").getLibrary().size();

        cast(started, "card12-cast", "Dig Through Time");
        boolean[] delved = {false};
        int[] delvePicks = {0};
        resolveAll(started, "card12", null, (cls, step) -> {
            String text = prompt(started);
            if ("mana_payment".equals(cls)) {
                JsonObject delve = null;
                boolean islandOffered = false;
                for (JsonElement element : started.session().legalActionsPayload()
                        .getAsJsonArray("actions")) {
                    JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
                    String type = meta.get("option_type").getAsString();
                    String label = meta.get("label").getAsString();
                    if (("mana_ability".equals(type) && label.equals(ISLAND_LABEL))
                            || "mana_pool".equals(type)) {
                        islandOffered = true;
                    }
                    if ("special_mana_action".equals(type) && label.contains("Delve")) {
                        assertTrue(delve == null, "unique delve action expected");
                        delve = element.getAsJsonObject();
                    }
                }
                if (islandOffered) {
                    return payOneFromRestoredMana(started, "card12-pay-" + step,
                            List.of("Island"), java.util.Set.of(ISLAND_LABEL));
                }
                assertNotNull(delve, "delve must be engine-offered once only {6} remains: "
                        + started.session().legalActionsPayload().getAsJsonArray("actions"));
                submit(started, "card12-delve-action-" + step, delve);
                delved[0] = true;
                return true;
            }
            if (("choose_object".equals(cls) || "target".equals(cls))
                    && started.session().legalActionsPayload().getAsJsonArray("actions")
                            .toString().contains("Memnite")) {
                // Delve's exile choice, one card per request: the graveyard
                // holds exactly six Memnites and {6} is owed, so six picks.
                if (delvePicks[0] < 6) {
                    chooseNamed(started, "card12-delve-" + step, "Memnite", 1);
                    delvePicks[0]++;
                } else {
                    chooseNone(started, "card12-delve-done-" + step);
                }
                return true;
            }
            if ("choose_object".equals(cls) || "target".equals(cls)) {
                // The top seven are all Mountains: every pick is equivalent.
                // The engine asks one card at a time.
                JsonObject pending = started.session().pendingDecisionPayload()
                        .getAsJsonObject("decision");
                chooseNamed(started, "card12-pick-" + step, "Mountain",
                        Math.max(1, pending.get("minimum_selections").getAsInt()));
                return true;
            }
            if ("choose_use".equals(cls) && text.toLowerCase().contains("delve")) {
                submit(started, "card12-use-delve-" + step, booleanOption(started, true));
                return true;
            }
            return false;
        });

        assertTrue(delved[0], "delve was chosen as an engine-offered special mana action");
        long exiledMemnites = started.session().restorationGame().getExile()
                .getAllCards(started.session().restorationGame()).stream()
                .filter(card -> "Memnite".equals(card.getName())).count();
        assertEquals(6, exiledMemnites, "delve exiled six cards for the {6}");
        assertEquals(2, tappedCount(started, "P1", "Island"), "{U}{U} came from the two Islands");
        assertEquals(handBefore - 1 + 2, handSize(started, "P1"), "two of seven to hand");
        assertEquals(libraryBefore - 2, started.seats().get("P1").getLibrary().size(),
                "five return to the library bottom");
        assertEquals(1, inGraveyard(started, "P1", "Dig Through Time"));
    }

    /**
     * CARD_09 Magma Opus: "deals 4 damage divided as you choose among any
     * number of targets. Tap two target permanents. Create a 4/4 blue and red
     * Elemental creature token. Draw two cards." All 4 at P2; tap P2's two
     * Bears.
     */
    @Test
    void magmaOpusDividesFourTapsTwoMakesAFourFourAndDrawsTwo() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(battlefield("P1", "Island", 0));
        objects.addAll(lands("P1", "Mountain", 7));
        objects.add(hand("P1", "Magma Opus", 0));
        objects.add(battlefield("P2", "Grizzly Bears", 0));
        objects.add(battlefield("P2", "Grizzly Bears", 1));
        Started started = start("card09-opus", 2, objects);
        int handBefore = handSize(started, "P1");

        submit(started, "card09-cast",
                singleOffer(offers(started, "Magma Opus", "Cast Magma Opus", true), "Magma Opus cast"));
        int[] targetRounds = {0};
        int[] tapPicks = {0};
        resolveAll(started, "card09", null, (cls, step) -> {
            if ("mana_payment".equals(cls)) {
                return payOneFromRestoredMana(started, "card09-pay-" + step,
                        List.of("Island", "Mountain"),
                        java.util.Set.of(ISLAND_LABEL, MOUNTAIN_LABEL));
            }
            String text = prompt(started).toLowerCase();
            if ("target".equals(cls) && text.contains("tap")) {
                // "Tap two target permanents": P2's two Bears, by engine identity.
                List<String> bears = new ArrayList<>();
                for (Permanent permanent : started.session().restorationGame()
                        .getBattlefield().getAllPermanents()) {
                    if ("Grizzly Bears".equals(permanent.getName())) {
                        bears.add(permanent.getId().toString());
                    }
                }
                int max = started.session().pendingDecisionPayload().getAsJsonObject("decision")
                        .get("maximum_selections").getAsInt();
                chooseByObjectIds(started, "card09-tap-" + step,
                        max >= 2 ? bears : List.of(bears.get(tapPicks[0]++)));
                return true;
            }
            if ("target_amount".equals(cls) && targetRounds[0] == 0) {
                // Divided damage: the target and its share are one response
                // (options + numeric). All 4 at P2.
                submitTargetAmount(started, "card09-dmg-" + step,
                        started.seats().get("P2").getId().toString(), 4);
                targetRounds[0]++;
                return true;
            }
            if ("target_amount".equals(cls)) {
                chooseNone(started, "card09-dmg-done-" + step);
                return true;
            }
            return false;
        });

        assertEquals(36, life(started, "P2"), "all 4 damage at P2");
        assertEquals(2, tappedCount(started, "P2", "Grizzly Bears"), "two target permanents tapped");
        assertEquals(1, onBattlefield(started, "P1", "Elemental Token"));
        Permanent token = permanent(started, "P1", "Elemental Token");
        assertEquals(4, token.getPower().getValue());
        assertEquals(4, token.getToughness().getValue());
        assertEquals(handBefore - 1 + 2, handSize(started, "P1"), "draw two");
    }

    /** The source name of the spell or ability asking for the current target. */
    private static String targetSourceName(Started started) {
        JsonArray actions = started.session().legalActionsPayload().getAsJsonArray("actions");
        if (actions.isEmpty()) {
            return "";
        }
        String sourceName = null;
        for (JsonElement element : actions) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
            JsonObject source =
                    meta.has("source_object") && meta.get("source_object").isJsonObject()
                            ? meta.getAsJsonObject("source_object")
                            : null;
            String current =
                    source != null && source.has("source_name")
                            ? source.get("source_name").getAsString()
                            : "";
            assertTrue(!current.isEmpty(), "every target option must expose its source name");
            if (sourceName == null) {
                sourceName = current;
            } else {
                assertEquals(
                        sourceName,
                        current,
                        "all options of one target decision must share the same source");
            }
        }
        return sourceName;
    }

    /** Answers a numeric decision (e.g. announce X) with an in-range value. */
    private static void submitNumeric(Started started, String tag, int value) {
        XmageFullGameSession session = started.session();
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        JsonArray numericActions = legal.getAsJsonArray("actions");
        assertEquals(
                1,
                numericActions.size(),
                "numeric decisions must expose exactly one structural action envelope");
        JsonObject numeric = numericActions.get(0).getAsJsonObject();
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
    static JsonObject labelled(Started started, String fragment) {
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

    /**
     * Chooses a semantic trigger-order option. A unique preferred source is
     * selected explicitly. If that source is absent, every remaining option
     * must have the same source and the same Rules-visible label before any
     * stable ordering is used; only then are the alternatives equivalent.
     */
    private static JsonObject triggerOrderOption(
            Started started, String preferredUniqueSource, String equivalentFallbackSource) {
        List<JsonObject> actions = new ArrayList<>();
        List<JsonObject> preferred = new ArrayList<>();
        String fallbackLabel = null;
        for (JsonElement element : started.session().legalActionsPayload()
                .getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            JsonObject nativeMetadata = metadata.getAsJsonObject("xmage_option_metadata");
            String source =
                    nativeMetadata != null && nativeMetadata.has("source_name")
                            ? nativeMetadata.get("source_name").getAsString()
                            : "";
            String label = metadata.get("label").getAsString();
            assertTrue(
                    preferredUniqueSource.equals(source)
                            || equivalentFallbackSource.equals(source),
                    "unexpected trigger-order source " + source + ": "
                            + started.session().legalActionsPayload().getAsJsonArray("actions"));
            actions.add(action);
            if (preferredUniqueSource.equals(source)) {
                preferred.add(action);
            } else {
                if (fallbackLabel == null) {
                    fallbackLabel = label;
                } else {
                    assertEquals(
                            fallbackLabel,
                            label,
                            "fallback trigger-order alternatives must be Rules-visible equivalents");
                }
            }
        }
        assertTrue(!actions.isEmpty(), "trigger-order decision must offer an option");
        assertTrue(
                preferred.size() <= 1,
                "preferred trigger source must be unique: " + preferredUniqueSource);
        if (preferred.size() == 1) {
            return preferred.get(0);
        }
        for (JsonObject action : actions) {
            JsonObject nativeMetadata = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            assertEquals(
                    equivalentFallbackSource,
                    nativeMetadata.get("source_name").getAsString(),
                    "remaining trigger-order alternatives must be semantically equivalent");
        }
        actions.sort((left, right) -> left.get("action_id").getAsString()
                .compareTo(right.get("action_id").getAsString()));
        return actions.get(0);
    }

    /** Selects one explicitly named Rules-visible trigger, never a positional option. */
    private static JsonObject triggerOrderByLabel(Started started, String fragment) {
        JsonObject match = null;
        String wanted = fragment.toLowerCase(java.util.Locale.ROOT);
        JsonArray actions = started.session().legalActionsPayload().getAsJsonArray("actions");
        for (JsonElement element : actions) {
            JsonObject action = element.getAsJsonObject();
            String label = action.getAsJsonObject("metadata").get("label").getAsString();
            if (label.toLowerCase(java.util.Locale.ROOT).contains(wanted)) {
                assertTrue(
                        match == null,
                        "trigger-order label fragment must identify exactly one option: " + fragment);
                match = action;
            }
        }
        assertNotNull(
                match,
                "no trigger-order option labelled *" + fragment + "*: " + actions);
        return match;
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
