package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonNull;
import mage.cards.decks.Deck;
import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
import mage.game.CommanderFreeForAll;
import mage.game.GameOptions;
import mage.game.mulligan.MulliganType;
import mage.players.Player;
import mage.util.RandomUtil;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * WS52-owned live XMage game fixture.
 *
 * <p>Mirrors {@link XmageFullGameSession} construction (same engine calls,
 * same order: deck registration, global seed, game creation, ledger/seat
 * registration, player init/load/add) but exposes the live game, players,
 * ledger, and decision controllers to the test pilot, and never starts a
 * hidden engine thread unless {@link #start} is called. No existing bridge
 * file is modified; all binding/visibility/RNG semantics under test are the
 * production ones.</p>
 *
 * <p>Each seat owns an independent decision controller (per-principal pilot
 * channels). The engine thread parks on exactly one of them at a time; a
 * direct witness may drive a side call on a FREE seat's player+controller
 * while the engine is parked, without any cross-channel interference.</p>
 */
final class Ws52Harness implements AutoCloseable {

    /** One seat: a registered game participant plus its own pilot channel. */
    record Slot(XmageFullGamePlayer player, XmageFullGameDecisionController controller) {
    }

    final long seed;
    final XmageDeckImporter importer = new XmageDeckImporter();
    final XmageKnowledgeLedger ledger = new XmageKnowledgeLedger();
    final CommanderFreeForAll game;
    final List<Slot> slots;
    final AtomicReference<Throwable> engineFailure = new AtomicReference<>();

    private Thread engineThread;

    boolean engineAlive() {
        return engineThread != null && engineThread.isAlive();
    }
    private volatile boolean closed;

    Ws52Harness(String deckIdPrefix, List<String> mainboard, List<String> commanders,
            int playerCount, long seed, int startingLife) {
        this(deckIdPrefix, Collections.nCopies(playerCount, mainboard),
                Collections.nCopies(playerCount, commanders), seed, startingLife);
    }

    Ws52Harness(String deckIdPrefix, List<List<String>> mainboards,
            List<List<String>> commandersList, long seed, int startingLife) {
        int playerCount = mainboards.size();
        if (commandersList.size() != playerCount) {
            throw new IllegalArgumentException("mainboards and commanders must align by seat");
        }
        this.seed = seed;
        List<Deck> decks = new ArrayList<>(playerCount);
        for (int index = 0; index < playerCount; index++) {
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    deckIdPrefix + "-" + index, deckIdPrefix + "-hash-" + index,
                    mainboards.get(index), commandersList.get(index));
            decks.add(importer.requireDeck(imported.deckHandle()));
        }
        for (int index = 0; index < decks.size(); index++) {
            ledger.registerDeck(index, decks.get(index));
        }

        RandomUtil.setSeed(seed);

        this.game = new CommanderFreeForAll(
                MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL,
                MulliganType.LONDON.getMulligan(1),
                startingLife,
                7);
        // WS56: successor per-game Rules seed (fail-closed when missing).
        game.setRulesSeed(seed);
        game.setRequireExplicitSeed(true);
        game.setNumPlayers(playerCount);
        GameOptions options = new GameOptions();
        options.rollbackTurnsAllowed = false;
        game.setGameOptions(options);
        XmageFullGameStateRedactor.registerKnowledgeLedger(game, ledger);

        List<Slot> created = new ArrayList<>(playerCount);
        List<XmageFullGamePlayer> seatPlayers = new ArrayList<>(playerCount);
        for (int index = 0; index < playerCount; index++) {
            Deck deck = decks.get(index);
            XmageFullGameDecisionController seatController = new XmageFullGameDecisionController();
            XmageFullGamePlayer player = new XmageFullGamePlayer(
                    "WS52 Seat " + (index + 1), RangeOfInfluence.ALL, seatController);
            player.init(game);
            game.loadCards(deck.getCards(), player.getId());
            game.loadCards(deck.getSideboard(), player.getId());
            game.addPlayer(player, deck);
            created.add(new Slot(player, seatController));
            seatPlayers.add(player);
        }
        if (game.getPlayers().size() != playerCount) {
            fail("WS52_HARNESS_SETUP_FAILED: expected " + playerCount
                    + " players, observed " + game.getPlayers().size());
        }
        this.slots = List.copyOf(created);
        XmageFullGameStateRedactor.registerSeats(game, seatPlayers);
    }

    /** Seat players in order. */
    List<XmageFullGamePlayer> players() {
        List<XmageFullGamePlayer> out = new ArrayList<>(slots.size());
        for (Slot slot : slots) {
            out.add(slot.player());
        }
        return List.copyOf(out);
    }

    static Ws52Harness sentinelTwoPlayer(long seed) {
        // Disjoint sentinel identities per seat (mirrors Ws52.sentinelDeckA/B):
        // seat 0 sees Islands, seat 1 sees Mountains; commanders are public.
        return new Ws52Harness("ws52-harness",
                List.of(nCopies(99, "Island"), nCopies(99, "Mountain")),
                List.of(List.of("Ishai, Ojutai Dragonspeaker"),
                        List.of("Rograkh, Son of Rohgahh")),
                seed, Ws52.STARTING_LIFE);
    }

    private static List<String> nCopies(int count, String name) {
        List<String> out = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            out.add(name);
        }
        return List.copyOf(out);
    }

    /** Starts the engine loop on a daemon game thread (mirrors session start). */
    void start(int startingSeat) {
        Player startingPlayer = slots.get(startingSeat).player();
        // The engine enforces ThreadUtils.ensureRunInGameThread by thread
        // NAME: only THREAD_PREFIX_GAME threads (plus AI-sim and "main")
        // may run game code. Mirror XmageFullGameSession exactly here.
        mage.util.XmageThreadFactory gameThreadFactory = new mage.util.XmageThreadFactory(
                mage.util.ThreadUtils.THREAD_PREFIX_GAME + " ws52-harness", true);
        engineThread = gameThreadFactory.newThread(() -> {
            try {
                game.start(startingPlayer.getId());
            } catch (Throwable exc) {
                engineFailure.compareAndSet(null, exc);
                for (Slot slot : slots) {
                    slot.controller().failClosed("WS52_HARNESS_ENGINE_FAILED",
                            exc.getClass().getSimpleName() + ": " + exc.getMessage());
                }
            } finally {
                for (Slot slot : slots) {
                    slot.controller().markTerminal();
                }
            }
        });
        engineThread.start();
    }

    /** Awaits the single live pending decision across all seat channels. */
    SlotDecision awaitDecision() {
        long deadlineNanos = System.nanoTime() + Duration.ofSeconds(30).toNanos();
        while (true) {
            SlotDecision found = null;
            for (Slot slot : slots) {
                if (slot.controller().terminalFailure() != null) {
                    fail("harness controller terminal: "
                            + slot.controller().terminalFailure().getMessage());
                }
                JsonObject pending = slot.controller().pendingDecision();
                if (pending != null) {
                    if (found != null) {
                        fail("WS52 harness has two live pending decisions");
                    }
                    found = new SlotDecision(slot, pending);
                }
            }
            if (found != null) {
                return found;
            }
            if (System.nanoTime() >= deadlineNanos) {
                fail("timed out awaiting WS52 harness decision");
            }
            try {
                Thread.sleep(5L);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                fail("WS52 harness decision wait interrupted");
            }
        }
    }

    /** Backwards-compatible: the pending frame without its channel. */
    JsonObject awaitFrame() {
        return awaitDecision().pending();
    }

    record SlotDecision(Slot slot, JsonObject pending) {
    }

    void submit(JsonObject pending, List<String> selectedExternalIds, Integer numericChoice) {
        Slot slot = route(pending);
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", pending.get("decision_id").getAsString());
        response.addProperty("actor_id", pending.get("actor_id").getAsString());
        if (pending.has("frame_digest") && !pending.get("frame_digest").isJsonNull()) {
            response.addProperty("frame_digest", pending.get("frame_digest").getAsString());
        }
        if (pending.has("option_digest") && !pending.get("option_digest").isJsonNull()) {
            response.addProperty("option_digest", pending.get("option_digest").getAsString());
        }
        if (pending.has("frame_revision") && !pending.get("frame_revision").isJsonNull()) {
            response.addProperty("frame_revision", pending.get("frame_revision").getAsLong());
        } else if (pending.has("decision_offset") && !pending.get("decision_offset").isJsonNull()) {
            response.addProperty("frame_revision", pending.get("decision_offset").getAsLong());
        }
        JsonArray selected = new JsonArray();
        selectedExternalIds.forEach(selected::add);
        response.add("selected_option_ids", selected);
        response.add("ordering", new JsonArray());
        if (numericChoice == null) {
            response.add("numeric_choice", JsonNull.INSTANCE);
        } else {
            response.addProperty("numeric_choice", numericChoice);
        }
        slot.controller().submit(response);
        // Advance barrier (mirrors XmageFullGameSession.awaitDecisionAdvance):
        // without it the next await could observe the just-consumed frame and
        // submit against the inter-frame gap. Rejected submits throw above
        // and never reach this barrier.
        awaitAdvance(slot, pending.get("decision_id").getAsString());
    }

    private Slot route(JsonObject pending) {
        String id = pending.get("decision_id").getAsString();
        for (Slot slot : slots) {
            JsonObject live = slot.controller().pendingDecision();
            if (live != null && id.equals(live.get("decision_id").getAsString())) {
                return slot;
            }
        }
        // No live frame carries this id: the caller holds a stale copy.
        throw new XmageFullGameDecisionController.DecisionException(
                "STALE_DECISION: expected a live WS52 harness frame");
    }

    private void awaitAdvance(Slot slot, String submittedDecisionId) {
        long deadlineNanos = System.nanoTime() + Duration.ofSeconds(20).toNanos();
        while (true) {
            if (slot.controller().terminalFailure() != null || isEngineTerminal()) {
                return;
            }
            JsonObject current = slot.controller().pendingDecision();
            if (current == null) {
                return;
            }
            if (!submittedDecisionId.equals(current.get("decision_id").getAsString())) {
                return;
            }
            if (System.nanoTime() >= deadlineNanos) {
                fail("WS52 harness engine did not consume " + submittedDecisionId);
            }
            try {
                Thread.sleep(1L);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                fail("WS52 harness advance wait interrupted for " + submittedDecisionId);
            }
        }
    }

    private boolean isEngineTerminal() {
        return engineThread != null && !engineThread.isAlive();
    }

    /**
     * Deterministic opening prelude: consume the engine's "Select a starting
     * player" frame (always installing Seat 1) and keep every mulligan.
     * After this returns, the engine thread is parked at the next pending
     * decision and the test thread may safely read live state or drive side
     * calls on a free seat channel without racing the engine.
     */
    void pilotOpening(int expectedMulligans) {
        for (int i = 0; i < 2; i++) {
            JsonObject pending = awaitFrame();
            if (!"choose_object".equals(pending.get("decision_class").getAsString())) {
                break;
            }
            String seat1 = null;
            for (int o = 0; o < pending.getAsJsonArray("legal_options").size(); o++) {
                JsonObject option = pending.getAsJsonArray("legal_options").get(o).getAsJsonObject();
                if (option.get("label").getAsString().endsWith("Seat 1")) {
                    seat1 = option.get("option_id").getAsString();
                }
            }
            assertNotNull(seat1, "starting-player frame must offer Seat 1: " + pending);
            submit(pending, List.of(seat1), null);
        }
        for (int i = 0; i < expectedMulligans; i++) {
            submitKeep(awaitFrame());
        }
    }

    /**
     * A seat whose channel currently holds no pending decision (the engine
     * is parked on another seat's channel), for {@link #directSlot}.
     */
    int freeSeat() {
        int actorSeat = awaitFrame().get("seat").getAsInt();
        for (int seat = 0; seat < slots.size(); seat++) {
            if (seat != actorSeat && slots.get(seat).controller().pendingDecision() == null) {
                return seat;
            }
        }
        fail("WS52 harness has no free direct channel");
        throw new IllegalStateException("unreachable");
    }

    /**
     * A free seat channel for side decision calls: a registered game
     * participant whose controller currently holds no pending decision
     * (the engine is parked on another seat's channel). Side calls
     * (targets, numerics, modes) compute their option sets from the live
     * engine exactly like engine-driven decisions.
     *
     * <p>Call only while the engine thread is parked at a known pending
     * session decision, and prefer a seat that is not the decision actor.</p>
     */
    DirectHandle directSlot(int seat) {
        Slot slot = slots.get(seat);
        assertTrue(slot.controller().pendingDecision() == null,
                "direct channel must be free of pending decisions");
        assertTrue(slot.controller().terminalFailure() == null,
                "direct channel must not be terminal");
        return new DirectHandle(slot.player(), slot.controller());
    }

    record DirectHandle(XmageFullGamePlayer player, XmageFullGameDecisionController controller) {

        JsonObject awaitDecision() {
            assertTrue(controller.awaitPendingOrTerminal(Duration.ofSeconds(30)),
                    "timed out awaiting WS52 direct decision");
            if (controller.terminalFailure() != null) {
                fail("direct controller terminal: " + controller.terminalFailure().getMessage());
            }
            JsonObject pending = controller.pendingDecision();
            assertNotNull(pending, "direct call ended without a pending decision");
            return pending;
        }

        void submit(JsonObject pending, List<String> selectedExternalIds, Integer numericChoice) {
            JsonObject response = new JsonObject();
            response.addProperty("decision_id", pending.get("decision_id").getAsString());
            response.addProperty("actor_id", pending.get("actor_id").getAsString());
            if (pending.has("frame_digest") && !pending.get("frame_digest").isJsonNull()) {
                response.addProperty("frame_digest", pending.get("frame_digest").getAsString());
            }
            if (pending.has("option_digest") && !pending.get("option_digest").isJsonNull()) {
                response.addProperty("option_digest", pending.get("option_digest").getAsString());
            }
            if (pending.has("frame_revision") && !pending.get("frame_revision").isJsonNull()) {
                response.addProperty("frame_revision", pending.get("frame_revision").getAsLong());
            } else if (pending.has("decision_offset") && !pending.get("decision_offset").isJsonNull()) {
                response.addProperty("frame_revision", pending.get("decision_offset").getAsLong());
            }
            JsonArray selected = new JsonArray();
            selectedExternalIds.forEach(selected::add);
            response.add("selected_option_ids", selected);
            response.add("ordering", new JsonArray());
            if (numericChoice == null) {
                response.add("numeric_choice", JsonNull.INSTANCE);
            } else {
                response.addProperty("numeric_choice", numericChoice);
            }
            controller.submit(response);
        }
    }

    void submitKeep(JsonObject mulliganPending) {        String keep = null;
        for (int i = 0; i < mulliganPending.getAsJsonArray("legal_options").size(); i++) {
            JsonObject option = mulliganPending.getAsJsonArray("legal_options").get(i).getAsJsonObject();
            if ("Keep opening hand".equals(option.get("label").getAsString())) {
                keep = option.get("option_id").getAsString();
            }
        }
        assertNotNull(keep, "mulligan frame without keep option: " + mulliganPending);
        submit(mulliganPending, List.of(keep), null);
    }

    @Override
    public void close() {
        closed = true;
        for (Slot slot : slots) {
            slot.controller().markTerminal();
        }
        if (engineThread != null) {
            try {
                engineThread.join(10_000L);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            }
        }
    }
}
