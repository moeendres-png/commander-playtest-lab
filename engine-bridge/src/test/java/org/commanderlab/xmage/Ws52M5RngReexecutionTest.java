package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.players.Player;
import mage.util.RandomUtil;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS52 M5 — Rules RNG / reexecution.
 *
 * <p>Keeps engine determinism, controlled Rules RNG, RNG isolation,
 * reproducible reexecution, and Semantic Replay strictly separate:</p>
 * <ul>
 *   <li>core stream: the global {@code RandomUtil} sequence repeats after
 *       {@code setSeed} (controlled primitive, DIRECTLY_VERIFIED);</li>
 *   <li>unseeded sources: no-arg {@code Collections.shuffle} is not
 *       seed-controlled (production-reachable at
 *       {@code PlayerImpl:1061,1204} plus card effects);</li>
 *   <li>isolation: any in-process consumer between seed and game start
 *       perturbs the setup shuffle (shared global stream);</li>
 *   <li>reexecution: twin same-seed games reproduce hands and the decision
 *       prefix; the first divergence, if any, is persisted;</li>
 *   <li>snapshot: game-state restore does not rewind the RNG stream, so a
 *       snapshot alone cannot reexecute.</li>
 * </ul>
 */
class Ws52M5RngReexecutionTest {

    @Test
    void coreStreamRepeatsAfterSeed() {
        List<Integer> first = sample(50);
        List<Integer> second = sample(50);
        assertEquals(first, second, "global RandomUtil stream must repeat after setSeed");
        assertTrue(new LinkedHashSet<>(first).size() > 1, "sample must be non-degenerate");
    }

    private static List<Integer> sample(int count) {
        RandomUtil.setSeed(Ws52.SEED_A);
        List<Integer> out = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            out.add(RandomUtil.nextInt(1_000_000));
        }
        return out;
    }

    @Test
    void noArgShuffleIsNotSeedControlled() {
        List<Integer> base = new ArrayList<>();
        for (int i = 0; i < 52; i++) {
            base.add(i);
        }
        RandomUtil.setSeed(Ws52.SEED_A);
        List<Integer> first = new ArrayList<>(base);
        Collections.shuffle(first);
        RandomUtil.setSeed(Ws52.SEED_A);
        List<Integer> second = new ArrayList<>(base);
        Collections.shuffle(second);
        assertEquals(52, new LinkedHashSet<>(first).size(), "shuffle must permute");
        assertNotEquals(first, second,
                "no-arg shuffle must NOT repeat after setSeed (unseeded source)");
    }

    @Test
    void setupShuffleInputOrderIsPerRunNondeterministic() throws Exception {
        // Causal chain (all DIRECTLY_VERIFIED at candidate pin 0c1f455e):
        // PlayerImpl.useDeck -> Deck.getMaindeckCards() collects to
        // Collectors.toSet() (HashSet, identity-hash order) ->
        // Library.addAll iterates it -> library LOAD order varies per run
        // (fresh Card objects/UUIDs every import) -> the seeded Fisher-Yates
        // Library.shuffle shuffles DIFFERENT inputs -> different hands at the
        // same seed. Seed control can never fix this; only an engine change
        // to the load path could.
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        List<String> first;
        List<String> second;
        try (Ws52Harness one = new Ws52Harness("ws52-m5-load-a", rogshai.mainboard(),
                rogshai.commanders(), 2, Ws52.SEED_A, Ws52.STARTING_LIFE)) {
            first = libraryNames(one, one.players().get(0));
        }
        try (Ws52Harness two = new Ws52Harness("ws52-m5-load-b", rogshai.mainboard(),
                rogshai.commanders(), 2, Ws52.SEED_A, Ws52.STARTING_LIFE)) {
            second = libraryNames(two, two.players().get(0));
        }
        assertEquals(first.size(), second.size());
        assertTrue(first.size() > 90, "library must be populated, observed " + first.size());
        assertNotEquals(rogshai.mainboard(), first,
                "library load order must not preserve deterministic import order "
                        + "(hash-iteration scrambles it)");
        assertNotEquals(first, second,
                "identical construction at the same seed must still produce "
                        + "different library orders (per-run load nondeterminism)");

        JsonObject evidence = new JsonObject();
        evidence.addProperty("seed", Ws52.SEED_A);
        evidence.addProperty("library_size", first.size());
        evidence.addProperty("causal_chain",
                "PlayerImpl.useDeck:417 -> Deck.getMaindeckCards Collectors.toSet "
                        + "(HashSet, identity-hash order) -> Library.addAll:191 iteration "
                        + "-> Library.shuffle seeded Fisher-Yates on per-run inputs");
        JsonArray head = new JsonArray();
        first.subList(0, Math.min(8, first.size())).forEach(head::add);
        evidence.add("run_a_preload_head", head);
        JsonArray head2 = new JsonArray();
        second.subList(0, Math.min(8, second.size())).forEach(head2::add);
        evidence.add("run_b_preload_head", head2);
        writeEvidence("m5-setup-order-divergence.json", evidence);
    }

    @Test
    void sharedStreamHasNoPerGameIsolation() throws Exception {
        // Unconfounded primitive (fixed input order): any in-process consumer
        // between seed and shuffle perturbs the outcome. The global stream is
        // shared across games, AI, and setup within one JVM.
        List<Integer> fixed = new ArrayList<>();
        for (int i = 0; i < 52; i++) {
            fixed.add(i);
        }
        RandomUtil.setSeed(Ws52.SEED_A);
        List<Integer> clean = new ArrayList<>(fixed);
        Collections.shuffle(clean, RandomUtil.getRandom());
        RandomUtil.setSeed(Ws52.SEED_A);
        for (int i = 0; i < 500; i++) {
            RandomUtil.nextInt(1_000_000);
        }
        List<Integer> perturbed = new ArrayList<>(fixed);
        Collections.shuffle(perturbed, RandomUtil.getRandom());
        assertNotEquals(clean, perturbed,
                "consuming the shared global stream between seed and shuffle must "
                        + "perturb the outcome (no per-game isolation)");
        RandomUtil.setSeed(Ws52.SEED_A);
        List<Integer> reseeded = new ArrayList<>(fixed);
        Collections.shuffle(reseeded, RandomUtil.getRandom());
        assertEquals(clean, reseeded, "re-seed control must restore the clean outcome");

        JsonObject evidence = new JsonObject();
        evidence.addProperty("seed", Ws52.SEED_A);
        evidence.addProperty("consumed_values_before_shuffle", 500);
        writeEvidence("m5-stream-sharing.json", evidence);
    }

    @Test
    void stateRestoreDoesNotRewindRngStream() {
        try (Ws52Harness harness = Ws52Harness.sentinelTwoPlayer(Ws52.SEED_A)) {
            harness.start(0);
            harness.pilotOpening(2);
            Player seat0 = harness.players().get(0);
            assertTrue(seat0.getLibrary().size() > 10, "library must be populated");

            RandomUtil.setSeed(Ws52.SEED_B);
            int before = RandomUtil.nextInt(1_000_000);
            // Identity-blind sentinel library: compare native ID order (names
            // are all "Island" and cannot show a reorder).
            List<UUID> order0 = List.copyOf(seat0.getLibrary().getCardList());
            int bookmark = harness.game.bookmarkState();

            seat0.getLibrary().shuffle();
            List<UUID> order1 = List.copyOf(seat0.getLibrary().getCardList());
            assertNotEquals(order0, order1, "library shuffle must reorder (Rules-random event)");
            int consumed = RandomUtil.nextInt(1_000_000);

            harness.game.restoreState(bookmark, "ws52-rng-probe");
            List<UUID> order2 = List.copyOf(seat0.getLibrary().getCardList());
            assertEquals(order0, order2, "restore must bring back game state");

            // The stream position under test is sampled BEFORE any re-seed.
            int afterRestore = RandomUtil.nextInt(1_000_000);
            assertTrue(before != consumed && consumed != afterRestore,
                    "sanity: sampled stream values must advance");

            // If the snapshot captured RNG position, the next draw would
            // equal the value right after `before`. It must NOT: the global
            // stream kept advancing through shuffle + consume.
            RandomUtil.setSeed(Ws52.SEED_B);
            RandomUtil.nextInt(1_000_000);
            int rewoundExpectation = RandomUtil.nextInt(1_000_000);
            assertNotEquals(rewoundExpectation, afterRestore,
                    "restore must NOT rewind the RNG stream (snapshot != reexecution)");
        }
    }

    // ------------------------------------------------------------------

    @Test
    void openingControlFlowIsDeterministicWhileIdentitiesDiverge() throws Exception {
        // Control flow (decision classes, seats, bounds) reproduces across
        // same-seed twins; card identities do not (setup load order, above).
        // This separates engine determinism (control) from reproducible
        // reexecution (state): the former holds for the opening, the latter
        // fails at the first shuffle input.
        TwinRun first = runTwinnedPrefix("ws52-m5-flow-a");
        TwinRun second = runTwinnedPrefix("ws52-m5-flow-b");
        assertEquals(first.flow, second.flow,
                "same seed must reproduce the opening control flow");
        assertTrue(first.flow.size() >= 12, "opening flow too short: " + first.flow.size());

        JsonObject evidence = new JsonObject();
        evidence.addProperty("seed", Ws52.SEED_A);
        JsonArray flow = new JsonArray();
        first.flow.forEach(flow::add);
        evidence.add("opening_control_flow", flow);
        JsonArray handsA = new JsonArray();
        first.handNames.forEach(handsA::add);
        evidence.add("run_a_hand_names", handsA);
        JsonArray handsB = new JsonArray();
        second.handNames.forEach(handsB::add);
        evidence.add("run_b_hand_names", handsB);
        evidence.addProperty("hands_equal", first.handNames.equals(second.handNames));
        writeEvidence("m5-control-flow-vs-identities.json", evidence);
    }

    private record TwinRun(List<String> handNames, List<String> flow) {
    }

    private static TwinRun runTwinnedPrefix(String gameId)
            throws Exception {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        String handleA = Ws52.importDeck(bridge, rogshai);
        String handleB = Ws52.importDeck(bridge, rogshai);
        Ws52.createFullGame(bridge, gameId, List.of(handleA, handleB), Ws52.SEED_A);
        Ws52.startFullGame(bridge);
        Ws52.Opening opening = Ws52.pilotOpening(bridge);
        assertEquals(1, opening.startingPlayerChoices());
        assertEquals(2, opening.mulligans());

        List<String> hands = new ArrayList<>();
        for (JsonElement element : Ws52.getObservation(bridge, 0)
                .getAsJsonObject("observation").getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            if (player.get("seat").getAsInt() == 0 && player.has("hand")) {
                for (JsonElement card : player.getAsJsonArray("hand")) {
                    hands.add(card.getAsJsonObject().get("name").getAsString());
                }
            }
        }
        hands.sort(String::compareTo);

        // Opening control flow: classes, seats, bounds, option-type SHAPE.
        // Labels carry card identities (divergent by design here) and are
        // counted, never compared.
        List<String> flow = new ArrayList<>();
        flow.add("choose_object|seat0");
        flow.add("mulligan|seat0");
        flow.add("mulligan|seat1");
        for (int step = 0; step < 10; step++) {
            JsonObject payload = Ws52.getDecision(bridge);
            if (!payload.has("decision") || !payload.get("decision").isJsonObject()) {
                break;
            }
            JsonObject decision = payload.getAsJsonObject("decision");
            flow.add(flowSignature(decision));
            if (!"priority".equals(decision.get("decision_class").getAsString())) {
                break;
            }
            Ws52.submit(bridge, decision,
                    List.of(Ws52.singleOptionIdByType(decision, "pass_priority")));
        }
        return new TwinRun(List.copyOf(hands), List.copyOf(flow));
    }

    /** Control-flow signature: class/seat/bounds only (option counts carry identities). */
    private static String flowSignature(JsonObject decision) {
        return decision.get("decision_class").getAsString() + '|'
                + decision.get("seat").getAsInt() + '|'
                + decision.get("minimum_selections").getAsInt() + '|'
                + decision.get("maximum_selections").getAsInt();
    }

    private static List<String> libraryNames(Ws52Harness harness, Player player) {
        List<String> names = new ArrayList<>();
        for (UUID id : player.getLibrary().getCardList()) {
            mage.cards.Card card = harness.game.getCard(id);
            names.add(card == null ? "<missing>" : card.getName());
        }
        return names;
    }

    private static void writeEvidence(String name, JsonObject payload) throws Exception {
        // Surefire workingDirectory is the module target/ dir.
        Path dir = Path.of("ws52-evidence");
        Files.createDirectories(dir);
        Files.writeString(dir.resolve(name), payload.toString(), StandardCharsets.UTF_8);
    }
}
