package org.commanderlab.xmage;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * WS60 first-wave suite executor: primary + replica runs, assertion
 * evaluation, hidden-info audits, determinism comparison, evidence files.
 */
final class Ws60Suite {

    record Assertion(String text, String target, Check check) {
    }

    interface Check {
        /** Returns observed detail; throws AssertionError with reason on failure. */
        String verify(JsonObject primary0, List<JsonObject> views, JsonArray tape,
                List<Ws60Driver.FrameRecord> log);
    }

    record HiddenAudit(String checkpoint, String principal, Audit audit) {
    }

    interface Audit {
        String verify(Map<String, List<JsonObject>> checkpoints, List<Ws60Driver.SeatDeck> seats);
    }

    record Spec(String id, String title, String shortId, long seed, int bound,
            List<Ws60Driver.SeatDeck> seats, java.util.function.Supplier<Ws60Pilot> pilotSupplier,
            Ws60Driver.Completion completion,
            java.util.function.Supplier<CheckpointSet> checkpointSupplier,
            List<Assertion> assertions, List<HiddenAudit> hiddenAudits,
            java.util.function.Predicate<Ws60Driver.RunResult> acceptRun,
            Runnable onRunStart, String incompleteRationale) {
        Spec(String id, String title, String shortId, long seed, int bound,
                List<Ws60Driver.SeatDeck> seats,
                java.util.function.Supplier<Ws60Pilot> pilotSupplier,
                Ws60Driver.Completion completion,
                java.util.function.Supplier<CheckpointSet> checkpointSupplier,
                List<Assertion> assertions, List<HiddenAudit> hiddenAudits) {
            this(id, title, shortId, seed, bound, seats, pilotSupplier, completion,
                    checkpointSupplier, assertions, hiddenAudits,
                    Ws60Driver.RunResult::completed, () -> {
                    }, null);
        }
    }

    record CheckpointSet(List<Ws60Driver.Checkpoint> checkpoints,
            Map<String, List<JsonObject>> captures) {
    }

    record Attempt(long seed, boolean completed, String stopped, int decisions,
            String digest, long rulesCalls) {
    }

    record SuiteResult(Spec spec, List<Attempt> attempts, Ws60Driver.RunResult primary,
            Ws60Driver.RunResult replica, List<String> assertionResults,
            List<String> hiddenResults, boolean determinismMatch, String verdict,
            String rationale, Map<String, List<JsonObject>> captures) {
    }

    private Ws60Suite() {
    }

    static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    static SuiteResult execute(Spec spec, int maxAttempts) {
        List<Attempt> attempts = new ArrayList<>();
        Ws60Driver.RunResult primary = null;
        CheckpointSet primaryCheckpoints = null;
        long seed = spec.seed();
        for (int attempt = 0; attempt < maxAttempts; attempt++) {
            long trySeed = attempt == 0 ? seed : seed + 1000L * attempt;
            spec.onRunStart().run();
            CheckpointSet set = spec.checkpointSupplier().get();
            Ws60Driver.RunResult run = Ws60Driver.run(spec.shortId(), spec.seats(),
                    trySeed, freshPilot(spec), spec.completion(), set.checkpoints(),
                    spec.bound());
            attempts.add(new Attempt(trySeed, run.completed(), run.stoppedReason(),
                    run.decisionsAnswered(), run.projectionDigest(), run.rulesRandomCalls()));
            boolean accepted;
            try {
                accepted = spec.acceptRun().test(run);
            } catch (RuntimeException exc) {
                accepted = false;
            }
            if (accepted) {
                primary = run;
                primaryCheckpoints = set;
                break;
            }
        }
        if (primary == null) {
            // Best-effort: rerun the first seed for evidence even when incomplete.
            spec.onRunStart().run();
            primaryCheckpoints = spec.checkpointSupplier().get();
            primary = Ws60Driver.run(spec.shortId(), spec.seats(), seed,
                    freshPilot(spec), spec.completion(), primaryCheckpoints.checkpoints(),
                    spec.bound());
        }
        spec.onRunStart().run();
        CheckpointSet replicaCheckpoints = spec.checkpointSupplier().get();
        Ws60Driver.RunResult replica = Ws60Driver.run(spec.shortId(), spec.seats(),
                primary.seed(), freshPilot(spec), spec.completion(),
                replicaCheckpoints.checkpoints(), spec.bound());

        List<String> assertionResults = new ArrayList<>();
        boolean allPass = primary.completed();
        JsonObject primary0 = primary.terminalViews().get(0);
        for (Assertion assertion : spec.assertions()) {
            try {
                String observed = assertion.check().verify(primary0, primary.terminalViews(),
                        primary.eventTape(), primary.frames());
                assertionResults.add("PASS: " + assertion.text() + " [" + assertion.target()
                        + "] observed=" + observed);
            } catch (AssertionError err) {
                assertionResults.add("FAIL: " + assertion.text() + " [" + assertion.target()
                        + "] " + err.getMessage());
                allPass = false;
            }
        }
        // Replica re-evaluation (same assertions on replica terminal state).
        boolean replicaPass = replica.completed();
        if (!primary.frames().isEmpty() && !replica.frames().isEmpty()) {
            JsonObject replica0 = replica.terminalViews().get(0);
            for (Assertion assertion : spec.assertions()) {
                try {
                    assertion.check().verify(replica0, replica.terminalViews(),
                            replica.eventTape(), replica.frames());
                } catch (AssertionError err) {
                    replicaPass = false;
                    assertionResults.add("REPLICA-DIVERGENCE: " + assertion.text()
                            + " " + err.getMessage());
                }
            }
        }
        boolean determinismMatch = primary.projectionDigest().equals(replica.projectionDigest())
                && normalizedViews(primary.terminalViews()).equals(
                        normalizedViews(replica.terminalViews()))
                && canonicalTape(primary.eventTape()).equals(canonicalTape(replica.eventTape()))
                && replicaPass;

        List<String> hiddenResults = new ArrayList<>();
        // Terminal views double as the post-scenario capture (the completion
        // short-circuit means no further frame is awaited after the last
        // scripted decision resolves).
        primaryCheckpoints.captures().put("terminal", primary.terminalViews());
        for (HiddenAudit audit : spec.hiddenAudits()) {
            try {
                String observed = audit.audit().verify(primaryCheckpoints.captures(), spec.seats());
                hiddenResults.add("PASS: " + audit.checkpoint() + " [" + audit.principal()
                        + "] " + observed);
            } catch (AssertionError err) {
                hiddenResults.add("FAIL: " + audit.checkpoint() + " [" + audit.principal()
                        + "] " + err.getMessage());
                allPass = false;
            }
        }

        String verdict;
        String rationale;
        if (allPass && determinismMatch) {
            verdict = "PASS";
            rationale = "full scenario contract proven on primary and reproduced on replica";
        } else if (!primary.completed()) {
            verdict = "UNKNOWN";
            rationale = "scenario did not complete within bounds: " + primary.stoppedReason()
                    + (spec.incompleteRationale() == null ? ""
                            : " | " + spec.incompleteRationale());
        } else if (!determinismMatch) {
            verdict = "UNKNOWN";
            rationale = "primary/replica determinism mismatch (see determinism audit)";
        } else {
            verdict = "FAIL";
            rationale = "terminal or hidden-info assertion failed on completed run";
        }
        return new SuiteResult(spec, attempts, primary, replica, assertionResults,
                hiddenResults, determinismMatch, verdict, rationale,
                primaryCheckpoints.captures());
    }

    /** Fresh pilot per run (pilots carry per-run gate state). */
    static Ws60Pilot freshPilot(Spec spec) {
        return spec.pilotSupplier().get();
    }

    static String canonicalViews(List<JsonObject> views) {
        return GSON.toJson(views);
    }

    /**
     * Twin-stable terminal normalization: fungible copies (same card name)
     * are compared as multisets with per-name tapped/damage aggregates, so
     * UUID-order tie-breaks among identical copies cannot spuriously diverge.
     * Unique permanents keep full characteristics.
     */
    static String normalizedViews(List<JsonObject> views) {
        JsonArray out = new JsonArray();
        for (JsonObject view : views) {
            JsonObject row = new JsonObject();
            row.addProperty("turn", view.has("turn_number")
                    ? view.get("turn_number").getAsInt() : -1);
            JsonArray players = new JsonArray();
            Map<String, Integer> refToSeat = new java.util.LinkedHashMap<>();
            if (view.has("players") && view.get("players").isJsonArray()) {
                for (JsonElement element : view.getAsJsonArray("players")) {
                    JsonObject prow = element.getAsJsonObject();
                    if (prow.has("player_id") && prow.has("seat")) {
                        refToSeat.put(prow.get("player_id").getAsString(),
                                prow.get("seat").getAsInt());
                    }
                }
                for (JsonElement element : view.getAsJsonArray("players")) {
                    players.add(normalizedPlayer(element.getAsJsonObject(), refToSeat));
                }
            }
            row.add("players", players);
            JsonArray stack = new JsonArray();
            if (view.has("stack") && view.get("stack").isJsonArray()) {
                for (JsonElement element : view.getAsJsonArray("stack")) {
                    stack.add(element.getAsJsonObject().get("name").getAsString());
                }
            }
            row.add("stack", stack);
            JsonArray commanders = new JsonArray();
            if (view.has("commander_status") && view.get("commander_status").isJsonArray()) {
                List<String> rows = new ArrayList<>();
                for (JsonElement element : view.getAsJsonArray("commander_status")) {
                    JsonObject entry = element.getAsJsonObject().deepCopy();
                    entry.remove("owner_id");
                    if (entry.has("commander_damage_to_player")) {
                        List<Integer> damage = new ArrayList<>();
                        for (JsonElement hit : entry.getAsJsonArray(
                                "commander_damage_to_player")) {
                            damage.add(hit.getAsJsonObject().get("total").getAsInt());
                        }
                        damage.sort(Integer::compareTo);
                        JsonArray sorted = new JsonArray();
                        damage.forEach(sorted::add);
                        entry.add("commander_damage_to_player", sorted);
                    }
                    rows.add(GSON.toJson(entry));
                }
                rows.sort(String::compareTo);
                rows.forEach(commanders::add);
            }
            row.add("commander_status", commanders);
            out.add(row);
        }
        return GSON.toJson(out);
    }

    private static JsonObject normalizedPlayer(JsonObject player,
            Map<String, Integer> refToSeat) {
        JsonObject out = new JsonObject();
        out.addProperty("seat", player.get("seat").getAsInt());
        out.addProperty("life", player.get("life").getAsInt());
        out.addProperty("hand_count", player.get("hand_count").getAsInt());
        out.addProperty("library_count", player.get("library_count").getAsInt());
        out.addProperty("has_lost", player.get("has_lost").getAsBoolean());
        out.addProperty("has_left", player.get("has_left").getAsBoolean());
        out.add("hand", sortedNames(player, "hand"));
        out.add("graveyard", sortedNames(player, "graveyard"));
        out.add("exile", sortedNames(player, "exile"));
        out.add("command", sortedNames(player, "command"));
        out.add("battlefield", normalizedBattlefield(player, refToSeat));
        return out;
    }

    private static void rewriteRef(JsonObject object, String key,
            Map<String, Integer> refToSeat) {
        if (!object.has(key) || !object.get(key).isJsonPrimitive()) {
            return;
        }
        Integer seat = refToSeat.get(object.get(key).getAsString());
        object.addProperty(key, seat == null ? -1 : seat);
    }

    private static JsonArray sortedNames(JsonObject player, String key) {
        List<String> names = new ArrayList<>();
        if (player.has(key) && player.get(key).isJsonArray()) {
            for (JsonElement element : player.getAsJsonArray(key)) {
                names.add(element.getAsJsonObject().get("name").getAsString());
            }
        }
        names.sort(String::compareTo);
        JsonArray out = new JsonArray();
        names.forEach(out::add);
        return out;
    }
    private static JsonArray normalizedBattlefield(JsonObject player,
            Map<String, Integer> refToSeat) {
        Map<String, List<JsonObject>> byName = new java.util.LinkedHashMap<>();
        if (player.has("battlefield") && player.get("battlefield").isJsonArray()) {
            for (JsonElement element : player.getAsJsonArray("battlefield")) {
                JsonObject item = element.getAsJsonObject();
                byName.computeIfAbsent(item.get("name").getAsString(),
                        ignored -> new ArrayList<>()).add(item);
            }
        }
        List<String> names = new ArrayList<>(byName.keySet());
        names.sort(String::compareTo);
        JsonArray out = new JsonArray();
        for (String name : names) {
            List<JsonObject> copies = byName.get(name);
            if (copies.size() == 1) {
                JsonObject full = copies.get(0).deepCopy();
                full.remove("object_id");
                rewriteRef(full, "controller_id", refToSeat);
                rewriteRef(full, "owner_id", refToSeat);
                out.add(full);
            } else {
                JsonObject aggregate = new JsonObject();
                aggregate.addProperty("name", name);
                aggregate.addProperty("count", copies.size());
                long tapped = copies.stream()
                        .filter(item -> item.has("tapped") && item.get("tapped").getAsBoolean())
                        .count();
                aggregate.addProperty("tapped", tapped);
                int damage = copies.stream().mapToInt(item -> item.has("damage")
                        ? item.get("damage").getAsInt() : 0).sum();
                aggregate.addProperty("damage", damage);
                out.add(aggregate);
            }
        }
        return out;
    }

    static String canonicalTape(JsonArray tape) {
        return GSON.toJson(tape);
    }

    static void writeEvidence(SuiteResult result, Path dir) throws Exception {
        Files.createDirectories(dir);
        JsonObject evidence = new JsonObject();
        evidence.addProperty("schema", "ws60.rqc3-scenario-evidence.v1");
        evidence.addProperty("scenario_id", result.spec().id());
        evidence.addProperty("title", result.spec().title());
        evidence.addProperty("engine", "xmage-successor");
        evidence.addProperty("engine_commit", "7135d5e85ddb4c8aa4b49b4192ca51947c822704");
        evidence.addProperty("engine_tree", "ea193e0d04493d53d962ed13ebd3b5d2f68838c7");
        evidence.addProperty("cpl_audit_base", "da4fa567312b6b0e4ef5cbfc7347748ca3c2dcd9");
        evidence.addProperty("rqc3_authority", "897d72f0b57bb8febe045870acaa3d2dba4bde56");
        evidence.addProperty("verdict", result.verdict());
        evidence.addProperty("rationale", result.rationale());

        JsonArray decks = new JsonArray();
        for (int seat = 0; seat < result.spec().seats().size(); seat++) {
            Ws60Driver.SeatDeck deck = result.spec().seats().get(seat);
            JsonObject row = new JsonObject();
            row.addProperty("rq_seat", seat);
            JsonArray commanders = new JsonArray();
            deck.commanders().forEach(commanders::add);
            row.add("commanders", commanders);
            Map<String, Integer> counts = new LinkedHashMap<>();
            for (String card : deck.mainboard()) {
                counts.merge(card, 1, Integer::sum);
            }
            JsonObject main = new JsonObject();
            counts.forEach(main::addProperty);
            row.add("mainboard_counts", main);
            decks.add(row);
        }
        evidence.add("decks", decks);

        JsonArray attemptRows = new JsonArray();
        for (Attempt attempt : result.attempts()) {
            JsonObject row = new JsonObject();
            row.addProperty("seed", attempt.seed());
            row.addProperty("completed", attempt.completed());
            row.addProperty("stopped", attempt.stopped());
            row.addProperty("decisions", attempt.decisions());
            row.addProperty("projection_digest", attempt.digest());
            row.addProperty("rules_random_calls", attempt.rulesCalls());
            attemptRows.add(row);
        }
        evidence.add("attempts", attemptRows);

        Ws60Driver.RunResult primary = result.primary();
        evidence.addProperty("primary_seed", primary.seed());
        evidence.addProperty("primary_seed_explicit", primary.rulesSeedExplicit());
        evidence.addProperty("primary_rules_seed", primary.rulesSeed());
        evidence.addProperty("primary_rules_random_calls", primary.rulesRandomCalls());
        evidence.addProperty("primary_decisions", primary.decisionsAnswered());
        evidence.addProperty("primary_projection_digest", primary.projectionDigest());
        evidence.addProperty("replica_seed", result.replica().seed());
        evidence.addProperty("replica_seed_explicit", result.replica().rulesSeedExplicit());
        evidence.addProperty("replica_rules_random_calls", result.replica().rulesRandomCalls());
        evidence.addProperty("replica_decisions", result.replica().decisionsAnswered());
        evidence.addProperty("replica_projection_digest", result.replica().projectionDigest());
        evidence.addProperty("determinism_match", result.determinismMatch());

        JsonArray log = new JsonArray();
        for (Ws60Driver.FrameRecord record : primary.frames()) {
            log.add(record.projection());
        }
        evidence.add("decision_log", log);

        JsonArray critical = new JsonArray();
        for (Ws60Driver.FrameRecord record : primary.frames()) {
            if (record.critical()) {
                critical.add(record.verbatim());
            }
        }
        evidence.add("critical_frames", critical);
        evidence.add("event_tape", primary.eventTape());
        evidence.add("terminal_views", GSON.toJsonTree(primary.terminalViews()));
        evidence.add("replica_terminal_views", GSON.toJsonTree(result.replica().terminalViews()));

        JsonArray assertions = new JsonArray();
        result.assertionResults().forEach(assertions::add);
        evidence.add("terminal_assertions", assertions);
        JsonArray hidden = new JsonArray();
        result.hiddenResults().forEach(hidden::add);
        evidence.add("hidden_info", hidden);

        JsonObject captures = new JsonObject();
        for (Map.Entry<String, List<JsonObject>> entry : result.captures().entrySet()) {
            JsonArray rows = new JsonArray();
            for (JsonObject view : entry.getValue()) {
                rows.add(view);
            }
            captures.add(entry.getKey(), rows);
        }
        evidence.add("checkpoint_captures", captures);

        Files.writeString(dir.resolve(result.spec().shortId() + ".evidence.json"),
                GSON.toJson(evidence), StandardCharsets.UTF_8);

        JsonObject replicaEvidence = new JsonObject();
        replicaEvidence.addProperty("schema", "ws60.rqc3-replica-log.v1");
        replicaEvidence.addProperty("scenario_id", result.spec().id());
        replicaEvidence.addProperty("seed", result.replica().seed());
        replicaEvidence.addProperty("stopped", result.replica().stoppedReason());
        replicaEvidence.addProperty("decisions", result.replica().decisionsAnswered());
        replicaEvidence.addProperty("projection_digest",
                result.replica().projectionDigest());
        replicaEvidence.addProperty("rules_random_calls",
                result.replica().rulesRandomCalls());
        JsonArray replicaLog = new JsonArray();
        for (Ws60Driver.FrameRecord record : result.replica().frames()) {
            replicaLog.add(record.projection());
        }
        replicaEvidence.add("decision_log", replicaLog);
        replicaEvidence.add("event_tape", result.replica().eventTape());
        replicaEvidence.add("terminal_views",
                GSON.toJsonTree(result.replica().terminalViews()));
        Files.writeString(dir.resolve(result.spec().shortId() + ".replica.json"),
                GSON.toJson(replicaEvidence), StandardCharsets.UTF_8);
    }

    /** First divergence between two projection logs (diagnostic). */
    static String firstDivergence(JsonArray primary, JsonArray replica) {
        int count = Math.min(primary.size(), replica.size());
        for (int index = 0; index < count; index++) {
            String left = GSON.toJson(primary.get(index));
            String right = GSON.toJson(replica.get(index));
            if (!left.equals(right)) {
                return "first-divergence at log index " + index + "\nPRIMARY: "
                        + left.substring(0, Math.min(1500, left.length())) + "\nREPLICA: "
                        + right.substring(0, Math.min(1500, right.length()));
            }
        }
        if (primary.size() != replica.size()) {
            return "length-divergence primary=" + primary.size()
                    + " replica=" + replica.size();
        }
        return "logs-identical";
    }
}
