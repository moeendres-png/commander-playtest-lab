package org.commanderlab.xmage;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.cards.Card;
import mage.game.CommanderFreeForAll;

import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * WS207 qualification-only opening-hand probe (fresh JVM per seed).
 *
 * <p>Starts ONE isolated full-game session with the supplied Commander decks
 * and explicit seed, lets XMage perform its native shuffle and initial deal,
 * then captures the dealt opening hands plus library sizes WITHOUT answering
 * any decision. XMage owns all shuffling and dealing; this probe only reads
 * the dealt state.</p>
 *
 * <p>Hand CONTENTS are QUALIFICATION_ASSERTION_ONLY setup-control knowledge:
 * they select candidate setup seeds (fixture construction) and must never be
 * passed to any pilot as gameplay input. The setup-state machine and the
 * successor phased pilot see only principal-scoped observations plus
 * authoritative legal Decision Options.</p>
 *
 * <p>Modes: {@code opening-hand} only. No mulligan/keep decision is answered;
 * the process exits after capture.</p>
 */
public final class Ws207OpeningHandProbe {

    private static final String ENGINE_PIN = "cfc36f445f917f101fa2ed588770e043f53bc44c";

    private Ws207OpeningHandProbe() {
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> argv = parseArgs(args);
        String mode = required(argv, "mode");
        if (!"opening-hand".equals(mode)) {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
        runOpeningHand(argv);
    }

    private static void runOpeningHand(Map<String, String> argv) throws Exception {
        Path decksFile = Path.of(required(argv, "decks"));
        long seed = Long.parseLong(required(argv, "seed"));
        int startingSeat = Integer.parseInt(
                argv.getOrDefault("starting-seat", String.valueOf(Math.floorMod(seed, 4))));
        Path outFile = Path.of(required(argv, "out"));
        String slot = argv.getOrDefault("slot", "");
        String subcase = argv.getOrDefault("case", "");

        JsonObject decks = JsonParser.parseString(
                Files.readString(decksFile, StandardCharsets.UTF_8)).getAsJsonObject();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>(4);
        for (int seat = 0; seat < 4; seat++) {
            JsonObject spec = decks.getAsJsonObject("seat" + seat);
            List<String> mainboard = strings(spec.getAsJsonArray("mainboard"));
            List<String> commanders = strings(spec.getAsJsonArray("commanders"));
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    spec.get("deck_id").getAsString(),
                    spec.get("deck_hash").getAsString(),
                    mainboard, commanders);
            handles.add(imported.deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                "ws207-opening-hand-" + slot + "-" + seed,
                handles, startingSeat, 40, seed, importer);

        // WS208/WS212 IMPACT BINDING (qualification-only): the production
        // session seeds only the process-global RandomUtil. The per-game
        // Rules RNG that drives native library shuffling must be bound
        // explicitly BEFORE game.start/init. This reflective hook touches no
        // production code: it calls the pinned engine's public Game contract
        // (verified on mage-1.4.61: setRulesSeed/getRulesSeed/
        // isRulesSeedExplicit/setRequireExplicitSeed) on the constructed
        // game object before the engine thread starts. RandomUtil-only
        // evidence is NOT reproducible setup evidence (see
        // AUTHORITY_ADJUDICATION.md).
        CommanderFreeForAll boundGame =
                field(session, "game", CommanderFreeForAll.class);
        boundGame.setRulesSeed(seed);
        boundGame.setRequireExplicitSeed(true);
        boolean rulesSeedExplicit = boundGame.isRulesSeedExplicit();
        long boundRulesSeed = boundGame.getRulesSeed();
        if (!rulesSeedExplicit || boundRulesSeed != seed) {
            throw new IllegalStateException(
                    "WS207_RULES_SEED_BINDING_FAILED: explicit=" + rulesSeedExplicit
                            + " rulesSeed=" + boundRulesSeed + " want=" + seed);
        }
        // Optional WS208/WS212 discrimination: override the process-global
        // RandomUtil stream AFTER construction/binding but BEFORE start, so
        // experiments can separate deal-RNG (RandomUtil) from in-game
        // Rules-RNG (rulesSeed) effects. Default equals seed (dual-fixed).
        String ruOverride = argv.getOrDefault("ru-seed", "");
        long randomutilSeed = seed;
        if (!ruOverride.isBlank()) {
            randomutilSeed = Long.parseLong(ruOverride);
            mage.util.RandomUtil.setSeed(randomutilSeed);
        }
        session.start();

        // Advance ONLY pre-game setup decisions through the generic boundary:
        // (1) starting-player selection -> configured starting seat;
        // (2) mulligan frames -> engine-offered keep (same keep policy as
        // WS205 ws205-pilot-v1). Stop as soon as the initial deal is
        // observable (libraries drawn) or after a bounded pre-game budget.
        // Every selection is an XMage-offered native option.
        JsonArray pregameSteps = new JsonArray();
        String pregameStop = "dealt";
        for (int step = 0; step < 12; step++) {
            @SuppressWarnings("unchecked")
            List<XmageFullGamePlayer> probePlayers =
                    (List<XmageFullGamePlayer>) field(session, "players", List.class);
            if (dealt(probePlayers)) {
                pregameStop = "dealt";
                break;
            }
            JsonObject payload = session.pendingDecisionPayload();
            JsonObject pending = payload.has("decision") && payload.get("decision").isJsonObject()
                    ? payload.getAsJsonObject("decision") : null;
            if (pending == null) {
                pregameStop = "terminal-before-deal";
                break;
            }
            String decisionClass = pending.has("decision_class")
                    ? pending.get("decision_class").getAsString() : "";
            String prompt = pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    ? pending.get("prompt").getAsString() : "";
            JsonObject legal = session.legalActionsPayload();
            JsonObject chosen = null;
            String basis = "";
            if (prompt.contains("Select a starting player")) {
                chosen = actionForLabelSubstring(legal, pending, "Seat " + (startingSeat + 1));
                basis = "starting-seat-" + startingSeat;
            } else if ("mulligan".equals(decisionClass)) {
                chosen = actionOfOptionType(legal, "keep");
                basis = "keep";
            } else {
                pregameStop = "unexpected-pregame-class:" + decisionClass;
                break;
            }
            if (chosen == null) {
                pregameStop = "no-offered-pregame-option:" + decisionClass;
                break;
            }
            JsonObject proposal = baseProposal("ws207-pregame", legal, pending, chosen);
            session.submitAction(proposal);
            JsonObject stepRecord = new JsonObject();
            stepRecord.addProperty("class", decisionClass);
            stepRecord.addProperty("basis", basis);
            pregameSteps.add(stepRecord);
            pregameStop = "budget";
        }

        @SuppressWarnings("unchecked")
        List<XmageFullGamePlayer> players =
                (List<XmageFullGamePlayer>) field(session, "players", List.class);
        CommanderFreeForAll game =
                field(session, "game", CommanderFreeForAll.class);

        JsonObject out = new JsonObject();
        out.addProperty("schema", "ws207.opening-hand.v1");
        out.addProperty("slot", slot);
        out.addProperty("subcase", subcase);
        out.addProperty("engine_pin", ENGINE_PIN);
        out.addProperty("seed", seed);
        out.addProperty("rules_seed", boundRulesSeed);
        out.addProperty("rules_seed_bound_before_start", true);
        out.addProperty("rules_seed_explicit", rulesSeedExplicit);
        out.addProperty("randomutil_seed", randomutilSeed);
        out.addProperty("seed_binding_model",
                "EXPLICIT_RULES_SEED (setRulesSeed + requireExplicitSeed before start/init; "
                        + "RandomUtil.setSeed retained by production constructor for compat only)");
        out.addProperty("starting_seat", startingSeat);
        out.addProperty("hand_contents_classification",
                "QUALIFICATION_ASSERTION_ONLY: setup seed-selection control only; "
                        + "never pilot gameplay input");
        JsonArray seats = new JsonArray();
        for (int index = 0; index < players.size(); index++) {
            XmageFullGamePlayer player = players.get(index);
            JsonObject row = new JsonObject();
            row.addProperty("seat", index);
            JsonArray hand = new JsonArray();
            int handSize = -1;
            try {
                handSize = player.getHand().size();
            } catch (RuntimeException exc) {
                row.addProperty("hand_capture_failed", String.valueOf(exc.getMessage()));
            }
            try {
                for (Card card : player.getHand().getCards(game)) {
                    try {
                        hand.add(card.getName());
                    } catch (RuntimeException ignored) {
                        hand.add("<unknown>");
                    }
                }
            } catch (RuntimeException exc) {
                row.addProperty("hand_names_failed", String.valueOf(exc.getMessage()));
            }
            row.add("hand_names", hand);
            row.addProperty("hand_size", handSize);
            try {
                row.addProperty("library_size", player.getLibrary().size());
            } catch (RuntimeException exc) {
                row.addProperty("library_size", -1);
            }
            seats.add(row);
        }
        out.add("seats", seats);
        out.add("pregame_steps", pregameSteps);
        out.addProperty("pregame_stop", pregameStop);
        // Pending first decision identity (proves the engine parked natively).
        try {
            JsonObject pending = session.pendingDecisionPayload();
            JsonObject decision = pending.has("decision") && pending.get("decision").isJsonObject()
                    ? pending.getAsJsonObject("decision") : new JsonObject();
            out.addProperty("first_decision_class", decision.has("decision_class")
                    ? decision.get("decision_class").getAsString() : "<none>");
            out.addProperty("first_decision_seat",
                    decision.has("seat") ? decision.get("seat").getAsInt() : -1);
            out.addProperty("first_decision_prompt", decision.has("prompt")
                    ? decision.get("prompt").getAsString() : "<none>");
            JsonArray labels = new JsonArray();
            if (decision.has("legal_options") && decision.get("legal_options").isJsonArray()) {
                for (com.google.gson.JsonElement element
                        : decision.getAsJsonArray("legal_options")) {
                    JsonObject option = element.getAsJsonObject();
                    labels.add(option.has("label") && !option.get("label").isJsonNull()
                            ? option.get("label").getAsString() : option.toString());
                    if (labels.size() >= 12) {
                        break;
                    }
                }
            }
            out.add("first_decision_offered_labels", labels);
        } catch (RuntimeException exc) {
            out.addProperty("pending_capture_failed", String.valueOf(exc.getMessage()));
        }
        Files.writeString(outFile,
                new GsonBuilder().setPrettyPrinting().create().toJson(out),
                StandardCharsets.UTF_8);
        System.out.println("WS207_OPENING_HAND_WRITTEN " + outFile + " seed=" + seed);
        System.exit(0);
    }

    /** True once XMage has natively dealt opening hands (libraries drawn). */
    private static boolean dealt(List<XmageFullGamePlayer> players) {
        boolean anyDrawn = false;
        for (XmageFullGamePlayer player : players) {
            try {
                if (player.getLibrary().size() < 99) {
                    anyDrawn = true;
                }
            } catch (RuntimeException ignored) {
                return false;
            }
        }
        return anyDrawn;
    }

    /** Offered-only substring match over native pending labels. */
    private static JsonObject actionForLabelSubstring(
            JsonObject legal, JsonObject pending, String needle) {
        String decisionId = pending.get("decision_id").getAsString();
        String lowered = needle.toLowerCase(java.util.Locale.ROOT);
        for (com.google.gson.JsonElement element : pending.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            String label = option.has("label") && !option.get("label").isJsonNull()
                    ? option.get("label").getAsString() : "";
            if (!label.toLowerCase(java.util.Locale.ROOT).contains(lowered)) {
                continue;
            }
            String optionId = option.has("option_id") && !option.get("option_id").isJsonNull()
                    ? option.get("option_id").getAsString() : null;
            if (optionId == null) {
                continue;
            }
            JsonObject action = actionForOption(legal, decisionId, optionId);
            if (action != null) {
                return action;
            }
        }
        return null;
    }

    private static JsonObject actionForOption(
            JsonObject legal, String decisionId, String optionId) {
        for (com.google.gson.JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if ((decisionId + ":" + optionId).equals(action.get("action_id").getAsString())) {
                return action;
            }
        }
        return null;
    }

    private static JsonObject actionOfOptionType(JsonObject legal, String optionType) {
        for (com.google.gson.JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.has("metadata") && action.get("metadata").isJsonObject()
                    ? action.getAsJsonObject("metadata") : new JsonObject();
            String actual = metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if (optionType.equals(actual)) {
                return action;
            }
        }
        return null;
    }

    /** Same generic proposal shape as the WS205 driver (WS204 boundary). */
    private static JsonObject baseProposal(
            String proposalId, JsonObject legal, JsonObject pending, JsonObject action) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", action.get("action_id").getAsString());
        proposal.addProperty("action_type", action.get("action_type").getAsString());
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", pending.get("decision_id").getAsString());
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "ws207-setup-v1-pregame");
        return proposal;
    }

    private static List<String> strings(com.google.gson.JsonArray array) {        List<String> out = new ArrayList<>(array.size());
        for (com.google.gson.JsonElement element : array) {
            out.add(element.getAsString());
        }
        return out;
    }

    @SuppressWarnings("unchecked")
    private static <T> T field(Object target, String name, Class<T> type)
            throws ReflectiveOperationException {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return (T) field.get(target);
    }

    private static Map<String, String> parseArgs(String[] args) {
        Map<String, String> out = new LinkedHashMap<>();
        for (String arg : args) {
            if (arg.startsWith("--") && arg.contains("=")) {
                out.put(arg.substring(2, arg.indexOf('=')),
                        arg.substring(arg.indexOf('=') + 1));
            }
        }
        return out;
    }

    private static String required(Map<String, String> argv, String key) {
        String value = argv.get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("missing required arg --" + key);
        }
        return value;
    }
}
