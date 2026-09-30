package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Semantic replay of whole multiplayer games with real Commander decks.
 *
 * <p>Two games are started with the same explicit Rules seed and the same
 * decks (RogShai, Kaervek, Hosts of Mordor, Lorehold Spirits, rotated through the seats). A deterministic test pilot
 * plays both by <em>semantic</em> keys only: it chooses by option label and
 * never by position or engine id. It prefers land drops, then a bounded number
 * of casts per turn, attacks when offered, pays mana from the pool before
 * tapping, and takes the smallest label or value otherwise. Each decision is
 * transcribed as turn, step, actor, class, bounds, the sorted offered labels
 * and the chosen labels. Engine ids are stripped, because they are random per
 * game by design.</p>
 *
 * <p>With the same seed and the same choices, the transcripts must be
 * identical. The first divergence is reported with its context. That is the
 * replay property the project's end state requires (AGENTS.md §5), and a
 * divergence is an engine or lane nondeterminism, such as F-29's hash-ordered
 * block declarations.</p>
 */
class XmageFullGameReplayTwinTest {

    private static final int MAX_DECISIONS = 3000;
    private static final int CASTS_PER_TURN = 2;
    /** Real Commander decks, rotated through the seats. */
    private static final List<String> DECKS = List.of(
            "data/decks/rogshai_current.json",
            "data/decks/opponents/kaervek/current/deck.json",
            "data/opponents/hosts_of_mordor_precon.json",
            "data/opponents/lorehold_spirit_precon.json");

    /**
     * One real-deck game per player count by default (about two minutes); the extended
     * set (nine games) with -Dtwin.extended, e.g. before a repin.
     */
    static Stream<Arguments> games() {
        Stream<Arguments> core = Stream.of(
                Arguments.of(3, 1234L), Arguments.of(4, 1618L), Arguments.of(5, 777L), Arguments.of(6, 31337L));
        if (System.getProperty("twin.extended") == null) {
            return core;
        }
        return Stream.concat(core, Stream.of(
                Arguments.of(4, 4242L), Arguments.of(4, 9001L), Arguments.of(4, 2718L),
                Arguments.of(5, 2024L), Arguments.of(6, 99L)));
    }

    @ParameterizedTest(name = "{0} players, seed {1}")
    @MethodSource("games")
    void sameSeedAndChoicesReplayTheSameDecisionSequence(int playerCount, long seed) throws IOException {
        List<String> first = play(playerCount, seed, "a");
        List<String> second = play(playerCount, seed, "b");
        System.out.println("STATS " + playerCount + "P seed " + seed + ": decisions=" + first.size()
                + " casts=" + first.stream().filter(l -> l.contains("|=>") && l.substring(l.indexOf("|=>")).contains(" — Cast ")).count()
                + " attacks=" + first.stream().filter(l -> l.contains("|=>") && l.substring(l.indexOf("|=>")).contains(" attacks ")).count()
                + " blockDecisions=" + first.stream().filter(l -> l.contains("|declare_blocker|")).count()
                + " lastTurn=" + first.get(first.size() - 1).split("\\|")[0] + " end=" + first.get(first.size() - 1).substring(Math.max(0, first.get(first.size() - 1).length() - 80)));
        int limit = Math.min(first.size(), second.size());
        for (int index = 0; index < limit; index++) {
            if (!first.get(index).equals(second.get(index))) {
                fail("replay diverged at decision " + index + " of " + limit + "\n  a: " + first.get(index)
                        + "\n  b: " + second.get(index) + "\ncontext:\n  "
                        + String.join("\n  ", first.subList(Math.max(0, index - 3), index)));
            }
        }
        assertTrue(first.size() == second.size(), "same length: " + first.size() + " vs " + second.size()
                + "; last a=" + first.get(first.size() - 1) + " last b=" + second.get(second.size() - 1));
        assertTrue(first.size() > 200, "non-vacuous: " + first.size() + " decisions");
    }

    private static List<String> play(int playerCount, long seed, String run) throws IOException {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>();
        for (int seat = 0; seat < playerCount; seat++) {
            Deck deck = load(DECKS.get(seat % DECKS.size()));
            handles.add(importer.importCommanderDeck(deck.id(), deck.hash(), deck.main(), deck.commanders())
                    .deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                "replay-twin-" + playerCount + "p-" + seed + "-" + run, handles, 0, 40, seed, importer);
        session.start();
        List<String> transcript = new ArrayList<>();
        Map<String, Integer> castsThisTurn = new HashMap<>();
        int paymentSteps = 0;
        for (int step = 0; step < MAX_DECISIONS; step++) {
            JsonObject pendingPayload = session.pendingDecisionPayload();
            if (pendingPayload.get("decision").isJsonNull()) {
                JsonObject end = pendingPayload.deepCopy();
                end.remove("engine_game_id");
                end.remove("game_id");
                if (!end.get("failure").isJsonNull()) {
                    System.out.println("CRASH " + run + " " + end.get("failure") + "\n  "
                            + String.join("\n  ", transcript.subList(Math.max(0, transcript.size() - 4), transcript.size())));
                }
                transcript.add("TERMINAL failure=" + String.valueOf(end.get("failure")).replaceAll("[0-9a-f]{64}", "<option>")
                        + " errors=" + end.get("engine_error_count")
                        + " outcomes=" + String.valueOf(end.get("outcomes")).replaceAll("[0-9a-f]{8}-[0-9a-f-]{27}", "id"));
                break;
            }
            JsonObject pending = pendingPayload.getAsJsonObject("decision");
            JsonObject legal = session.legalActionsPayload();
            String actor = seatOf(session, legal.get("actor_id").getAsString());
            String cls = pending.get("decision_class").getAsString();
            mage.game.Game game = session.restorationGame();
            int turn = game == null ? -1 : game.getTurnNum();
            String phase = game == null || game.getStep() == null ? "?" : game.getStep().getType().name();
            labelGame = game;
            JsonArray actions = legal.getAsJsonArray("actions");
            List<JsonObject> options = new ArrayList<>();
            actions.forEach(element -> options.add(element.getAsJsonObject()));
            List<String> labels = new ArrayList<>();
            options.forEach(option -> labels.add(label(option)));
            labels.sort(String::compareTo);
            String state = publicState(game);
            String head = "t" + turn + "|" + phase + "|" + actor + "|" + cls + "|"
                    + pending.get("minimum_selections") + ".." + pending.get("maximum_selections") + "|" + labels;
            String kind = options.isEmpty() ? "none"
                    : options.get(0).getAsJsonObject("choices_schema").get("response_kind").getAsString();
            String chosen;
            JsonObject schema = options.isEmpty() ? new JsonObject() : options.get(0).getAsJsonObject("choices_schema");
            if ("numeric".equals(kind) && schema.has("numeric_legs")) {
                // Joint vector (e.g. mana of several colours): fill the legs in order, each up
                // to its maximum, until the required total is reached.
                int remaining = schema.get("numeric_total_min").getAsInt();
                List<Integer> vector = new ArrayList<>();
                for (JsonElement leg : schema.getAsJsonArray("numeric_legs")) {
                    int min = leg.getAsJsonObject().get("min").getAsInt();
                    int value = Math.max(min, Math.min(leg.getAsJsonObject().get("max").getAsInt(), remaining));
                    vector.add(value);
                    remaining -= value;
                }
                submitNumericVector(session, "v" + step, vector);
                chosen = "#" + vector;
            } else if ("numeric".equals(kind)) {
                JsonObject context = pending.getAsJsonObject("context");
                int value = context != null && context.has("numeric_min") ? context.get("numeric_min").getAsInt() : 0;
                submitNumeric(session, "n" + step, value);
                chosen = "#" + value;
            } else if ("target_amount".equals(cls)) {
                // Divide-as-you-choose: the whole remaining amount to the smallest key.
                List<JsonObject> sortedTargets = new ArrayList<>(options);
                sortedTargets.sort(Comparator.comparing(XmageFullGameReplayTwinTest::label));
                int amount = pending.getAsJsonObject("context").get("numeric_max").getAsInt();
                submitOptions(session, "ta" + step, List.of(sortedTargets.get(0)), amount);
                chosen = label(sortedTargets.get(0)) + " x" + amount;
            } else if (!"options".equals(kind)) {
                transcript.add(head + "|STOP unsupported response kind " + kind);
                break;
            } else {
                String budgetKey = actor + "@" + turn;
                paymentSteps = "mana_payment".equals(cls) ? paymentSteps + 1 : 0;
                int budget = "mana_payment".equals(cls) && paymentSteps > 12 ? -1
                        : castsThisTurn.getOrDefault(budgetKey, 0);
                List<JsonObject> pick = choose(cls, options, pending, budget);
                if (pick.isEmpty()) {
                    chooseNone(session, "e" + step);
                    chosen = "-";
                } else {
                    String pickedLabel = label(pick.get(0));
                    if ("priority".equals(cls) && pickedLabel.contains(" — Cast ")) {
                        castsThisTurn.merge(budgetKey, 1, Integer::sum);
                    }
                    submitOptions(session, "o" + step, pick);
                    List<String> names = new ArrayList<>();
                    pick.forEach(option -> names.add(label(option)));
                    chosen = String.join("+", names);
                }
            }
            long same = labels.stream().filter(l -> chosen.equals(l)).count();
            transcript.add(head + "|=>" + chosen + (same > 1 ? " (AMBIGUOUS x" + same + ")" : "") + "\n      state " + state);
        }
        return transcript;
    }

    /** Semantic, position-free choice. An empty result submits an empty selection (only when min is 0). */
    private static List<JsonObject> choose(String cls, List<JsonObject> options, JsonObject pending, int casts) {
        int min = pending.get("minimum_selections").getAsInt();
        List<JsonObject> sorted = new ArrayList<>(options);
        sorted.sort(Comparator.comparing(XmageFullGameReplayTwinTest::label));
        switch (cls) {
            case "priority" -> {
                for (String fragment : new String[] {" — Play ", casts < CASTS_PER_TURN ? " — Cast " : null}) {
                    if (fragment == null) {
                        continue;
                    }
                    for (JsonObject option : sorted) {
                        if (label(option).contains(fragment)) {
                            return List.of(option);
                        }
                    }
                }
                for (JsonObject option : sorted) {
                    if (label(option).startsWith("Pass")) {
                        return List.of(option);
                    }
                }
            }
            case "mana_payment" -> {
                // Pool mana only when the engine says it advances this payment; otherwise tap
                // a source; a payment that cannot progress is cancelled (bounded by the caller).
                for (JsonObject option : sorted) {
                    JsonObject engine = option.getAsJsonObject("metadata").getAsJsonObject("xmage_option_metadata");
                    if ("mana_pool".equals(optionType(option)) && engine != null
                            && engine.has("advances_payment") && engine.get("advances_payment").getAsBoolean()) {
                        return List.of(option);
                    }
                }
                if (casts >= 0) {
                    for (JsonObject option : sorted) {
                        if ("mana_ability".equals(optionType(option))) {
                            return List.of(option);
                        }
                    }
                }
                for (JsonObject option : sorted) {
                    if ("cancel_mana_payment".equals(optionType(option))) {
                        return List.of(option);
                    }
                }
            }
            case "declare_attacker" -> {
                for (JsonObject option : sorted) {
                    if (label(option).contains(" attacks ")) {
                        return List.of(option);
                    }
                }
            }
            default -> {
                if (min == 0) {
                    return List.of();
                }
            }
        }
        return sorted.subList(0, Math.max(1, min));
    }

    /** Public, id-free state: per seat life, hand/library size, battlefield (tapped marked), graveyard. */
    private static String publicState(mage.game.Game game) {
        if (game == null) {
            return "?";
        }
        StringBuilder out = new StringBuilder();
        List<String> stack = new ArrayList<>();
        game.getStack().forEach(object -> stack.add(object.getName() + "<" + object.getStackAbility().getRule() + ">"));
        if (!stack.isEmpty()) {
            out.append("STACK").append(stack).append("; ");
        }
        for (java.util.UUID playerId : game.getState().getPlayerList()) {
            mage.players.Player player = game.getPlayer(playerId);
            List<String> board = new ArrayList<>();
            for (mage.game.permanent.Permanent permanent : game.getBattlefield().getAllActivePermanents(playerId)) {
                board.add(permanent.getName() + (permanent.isTapped() ? "(T)" : ""));
            }
            board.sort(String::compareTo);
            List<String> yard = new ArrayList<>();
            player.getGraveyard().getCards(game).forEach(card -> yard.add(card.getName()));
            yard.sort(String::compareTo);
            out.append(player.getName()).append(" L").append(player.getLife()).append(" H")
                    .append(player.getHand().size()).append(" Y").append(player.getLibrary().size())
                    .append(" B").append(board).append(" G").append(yard).append("; ");
        }
        return out.toString();
    }

    /** Game of the decision being labelled (both runs are single-threaded per test). */
    private static mage.game.Game labelGame;

    /**
     * The option's semantic key: its label, plus, when it names a permanent (as target or
     * ability source), that permanent's controller, tapped state, counters and attachments.
     * Engine ids are never part of the key.
     */
    private static String label(JsonObject option) {
        String text = option.getAsJsonObject("metadata").get("label").getAsString()
                .replaceAll("\\[[0-9a-f]{3,}\\]", "[id]");
        JsonObject engine = option.getAsJsonObject("metadata").getAsJsonObject("xmage_option_metadata");
        if (labelGame == null || engine == null) {
            return text;
        }
        for (String field : new String[] {"object_id", "source_object_id"}) {
            if (engine.has(field) && !engine.get(field).isJsonNull()) {
                try {
                    mage.game.permanent.Permanent permanent =
                            labelGame.getPermanent(java.util.UUID.fromString(engine.get(field).getAsString()));
                    if (permanent != null) {
                        return text + " @" + labelGame.getPlayer(permanent.getControllerId()).getName()
                                + (permanent.isTapped() ? " T" : "")
                                + " c" + permanent.getCounters(labelGame).values().stream()
                                        .map(c -> c.getName() + c.getCount()).sorted().toList()
                                + " a" + permanent.getAttachments().size();
                    }
                } catch (IllegalArgumentException ignored) {
                    // not an object id
                }
            }
        }
        return text;
    }

    private static String optionType(JsonObject option) {
        JsonObject meta = option.getAsJsonObject("metadata");
        return meta.has("option_type") && !meta.get("option_type").isJsonNull() ? meta.get("option_type").getAsString() : "";
    }

    private static String seatOf(XmageFullGameSession session, String actorId) {
        mage.game.Game game = session.restorationGame();
        if (game != null) {
            int seat = 1;
            for (java.util.UUID playerId : game.getState().getPlayerList()) {
                if (playerId.toString().equals(actorId)) {
                    return game.getPlayer(playerId).getName();
                }
                seat++;
            }
        }
        return "?";
    }

    private static void submitOptions(XmageFullGameSession session, String tag, List<JsonObject> pick) {
        submitOptions(session, tag, pick, null);
    }

    private static void submitOptions(XmageFullGameSession session, String tag, List<JsonObject> pick,
            Integer amount) {
        if (pick.size() == 1 && amount == null) {
            XmageFullGameTaxExecutionTest.submit(session, tag, pick.get(0));
            return;
        }
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        String decisionId = pending.get("decision_id").getAsString();
        JsonArray selected = new JsonArray();
        pick.forEach(option -> selected.add(option.getAsJsonObject("metadata").get("option_id").getAsString()));
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", pick.get(0).get("action_id").getAsString());
        proposal.addProperty("action_type", pick.get(0).get("action_type").getAsString());
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", selected);
        if (amount != null) {
            choices.addProperty("numeric_choice", amount);
        }
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        session.submitAction(proposal);
    }

    private static void chooseNone(XmageFullGameSession session, String tag) {
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
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
        session.submitAction(proposal);
    }

    private static void submitNumericVector(XmageFullGameSession session, String tag, List<Integer> values) {
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        JsonObject numeric = legal.getAsJsonArray("actions").get(0).getAsJsonObject();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", numeric.get("action_id").getAsString());
        proposal.addProperty("action_type", "structural_decision");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", pending.get("decision_id").getAsString());
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", new JsonArray());
        JsonArray vector = new JsonArray();
        values.forEach(vector::add);
        choices.add("numeric_choices", vector);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        session.submitAction(proposal);
    }

    private static void submitNumeric(XmageFullGameSession session, String tag, int value) {
        JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
        JsonObject legal = session.legalActionsPayload();
        JsonObject numeric = legal.getAsJsonArray("actions").get(0).getAsJsonObject();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", tag);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", numeric.get("action_id").getAsString());
        proposal.addProperty("action_type", "structural_decision");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", pending.get("decision_id").getAsString());
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", new JsonArray());
        choices.addProperty("numeric_choice", value);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        session.submitAction(proposal);
    }

    private record Deck(String id, String hash, List<String> main, List<String> commanders) {
    }

    private static Deck load(String relative) throws IOException {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        JsonObject root = JsonParser.parseString(Files.readString(
                Path.of(repoRoot, relative).normalize(), StandardCharsets.UTF_8)).getAsJsonObject();
        if (root.has("deck") && root.get("deck").isJsonObject()) {
            root = root.getAsJsonObject("deck");
        }
        List<String> main = new ArrayList<>();
        List<String> commanders = new ArrayList<>();
        root.getAsJsonArray("cards").forEach(element -> {
            JsonObject card = element.getAsJsonObject();
            List<String> target = "commander".equals(card.get("zone").getAsString()) ? commanders : main;
            for (int copy = 0; copy < card.get("quantity").getAsInt(); copy++) {
                target.add(card.get("oracle_name").getAsString());
            }
        });
        String id = root.get("deck_id").getAsString();
        return new Deck(id, root.has("deck_hash") ? root.get("deck_hash").getAsString() : id,
                List.copyOf(main), List.copyOf(commanders));
    }
}
