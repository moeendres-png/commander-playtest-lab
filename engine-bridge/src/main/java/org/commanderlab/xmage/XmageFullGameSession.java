package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.cards.decks.Deck;
import mage.constants.RangeOfInfluence;
import mage.game.GameCommanderImpl;
import mage.game.GameOptions;
import mage.game.events.TableEvent;
import mage.game.mulligan.MulliganType;
import mage.players.Player;
import mage.util.ThreadUtils;
import mage.util.XmageThreadFactory;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;

/**
 * One-process/one-game full Commander session for external pilot conformance.
 *
 * <p>Every credited session binds the orchestration seed to the authoritative
 * per-game Rules RNG ({@code game.setRulesSeed(seed)} plus
 * {@code game.setRequireExplicitSeed(true)}) immediately after game
 * construction and before any Rules-random consumption (initial shuffle,
 * choosing-player pick, opening hands). The legacy process-global
 * {@code RandomUtil} seed is retired: it is not Rules-RNG authority and no
 * non-Rules purpose for it remains in this session. The one-game-per-process
 * discipline is retained as defense in depth. JVM UUIDs are deliberately not
 * treated as seeded replay identity.</p>
 */
final class XmageFullGameSession {

    /** WS215 variable-player contract, R19 widened: Commander tables for 2..6 principals. */
    static final int MIN_PLAYERS = 2;
    static final int MAX_PLAYERS = 6;
    static final String EVIDENCE_CLASS = "technical_conformance_only";

    private final String protocolGameId;
    private final long seed;
    private final int playerCount;
    private final GameCommanderImpl game;
    private final List<XmageFullGamePlayer> players;
    private final XmageFullGameDecisionController controller;
    private final int startingPlayerSeat;
    private final XmageNativeStateRestoration restoration;
    private final AtomicReference<Throwable> engineFailure = new AtomicReference<>();
    private final AtomicReference<String> shutdownUnwind = new AtomicReference<>();
    private final List<String> engineErrorDiagnostics =
            Collections.synchronizedList(new ArrayList<>());

    private Thread engineThread;
    private boolean started;
    /** #662: set once by {@link #shutdownGame()}; every later decision request is refused. */
    private volatile boolean shutDown;
    private final int startingLife;
    /** #662 replay export: per seat, the exact deck import request. */
    private final JsonArray replayDecks = new JsonArray();

    XmageFullGameSession(
            String protocolGameId,
            List<String> deckHandles,
            int startingPlayerSeat,
            int startingLife,
            long seed,
            XmageDeckImporter deckImporter
    ) {
        this(protocolGameId, deckHandles, startingPlayerSeat, startingLife,
                seed, deckImporter, null);
    }

    /**
     * Restoration-aware construction for native-state qualification.
     *
     * <p>When {@code restoration} is non-null, its pre-start assembly runs
     * against the freshly constructed (not yet started) game after normal
     * player/deck setup. Post-arrival steps (cast-count restore, revalidate,
     * readback, compare) stay with the caller through
     * {@link #restorationGame()} and {@link #restorationSeats()}.</p>
     */
    XmageFullGameSession(
            String protocolGameId,
            List<String> deckHandles,
            int startingPlayerSeat,
            int startingLife,
            long seed,
            XmageDeckImporter deckImporter,
            XmageNativeStateRestoration restoration
    ) {
        if (protocolGameId == null || protocolGameId.isBlank()) {
            throw new IllegalArgumentException("game_id must be nonblank");
        }
        if (deckHandles == null || deckHandles.size() < MIN_PLAYERS
                || deckHandles.size() > MAX_PLAYERS) {
            throw new IllegalArgumentException(
                    "FULL_GAME_INVALID_PLAYER_COUNT: observed "
                            + (deckHandles == null ? "null" : deckHandles.size())
                            + " (supported " + MIN_PLAYERS + ".." + MAX_PLAYERS + ")"
            );
        }
        int sessionsPlayers = deckHandles.size();
        if (startingPlayerSeat < 0 || startingPlayerSeat >= sessionsPlayers) {
            throw new IllegalArgumentException("invalid starting_player_seat");
        }
        if (startingLife < 1) {
            throw new IllegalArgumentException("starting_life must be positive");
        }
        if (deckImporter == null) {
            throw new IllegalArgumentException("deckImporter must not be null");
        }

        this.protocolGameId = protocolGameId;
        this.seed = seed;
        this.playerCount = sessionsPlayers;
        this.startingPlayerSeat = startingPlayerSeat;
        this.controller = new XmageFullGameDecisionController(Duration.ofMinutes(2));

        this.startingLife = startingLife;
        List<Deck> decks = new ArrayList<>(playerCount);
        for (String deckHandle : deckHandles) {
            decks.add(deckImporter.requireDeck(deckHandle));
            XmageDeckImporter.ImportRequest request = deckImporter.requireRequest(deckHandle);
            JsonObject deck = new JsonObject();
            deck.addProperty("seat", replayDecks.size());
            deck.addProperty("deck_id", request.deckId());
            deck.addProperty("deck_hash", request.deckHash());
            JsonArray mainboard = new JsonArray();
            request.mainboard().forEach(mainboard::add);
            deck.add("mainboard", mainboard);
            JsonArray commanders = new JsonArray();
            request.commanders().forEach(commanders::add);
            deck.add("commanders", commanders);
            replayDecks.add(deck);
        }

        // FULL107 WS05-CMD-MULL-2/4 fixture-faithful free mulligan: the free
        // multiplayer mulligan applies above two players (CR 102.1
        // multiplayer = more than two players), so 2P London bottoms one
        // card while 3..6P keep the free first mulligan. A blanket grant
        // would silently zero the 2P bottom count the fixtures require.
        int freeMulligans = sessionsPlayers > 2 ? 1 : 0;
        // Two-player tables use the engine's own two-player Commander type so
        // the engine applies CR 103.8a (see XmageCommanderGames).
        this.game = XmageCommanderGames.create(
                playerCount,
                MulliganType.LONDON.getMulligan(freeMulligans),
                startingLife
        );
        // WS213 authoritative Rules-RNG binding (WS212 engine contract): the
        // explicit orchestration seed replaces the per-game Rules stream and
        // arms the fail-closed explicit-seed requirement. This lands after
        // construction and before any Rules-random consumption: construction,
        // deck loading and player setup consume zero Rules randomness on the
        // pinned engine, while game.start/init performs the initial shuffle,
        // choosing-player pick and opening hands. The legacy process-global
        // seed call is retired here: it never was Rules-RNG authority.
        XmageRulesSeedBinding.bind(game, seed);
        GameOptions options = new GameOptions();
        options.rollbackTurnsAllowed = false;
        game.setGameOptions(options);
        game.addTableEventListener(event -> {
            if (event.getEventType() != TableEvent.EventType.ERROR) {
                return;
            }
            Exception exception = event.getException();
            String exceptionClass = exception == null
                    ? "unknown"
                    : exception.getClass().getName();
            String exceptionMessage = exception == null ? "" : safeMessage(exception);
            String eventMessage = event.getMessage() == null ? "" : event.getMessage();
            engineErrorDiagnostics.add(
                    exceptionClass + ": " + exceptionMessage + " [event=" + eventMessage + "]"
            );
        });

        List<XmageFullGamePlayer> createdPlayers = new ArrayList<>(playerCount);
        for (int index = 0; index < playerCount; index++) {
            Deck deck = decks.get(index);
            XmageFullGamePlayer player = new XmageFullGamePlayer(
                    "Full Game Seat " + (index + 1),
                    RangeOfInfluence.ALL,
                    controller
            );
            player.init(game);
            game.loadCards(deck.getCards(), player.getId());
            game.loadCards(deck.getSideboard(), player.getId());
            createdPlayers.add(player);
        }
        // F-41: seat order is turn order (see XmageSeating).
        for (int index : XmageSeating.additionOrder(seatIndices(playerCount))) {
            game.addPlayer(createdPlayers.get(index), decks.get(index));
        }
        if (game.getPlayers().size() != playerCount) {
            throw new IllegalStateException(
                    "XMAGE_PLAYER_SETUP_FAILED: expected " + playerCount
                            + ", observed " + game.getPlayers().size()
            );
        }
        this.players = List.copyOf(createdPlayers);
        this.restoration = restoration;
        if (restoration != null) {
            restoration.applyPreStart(game, restorationSeats());
        }
        // #662 export_event_log: the public semantic event tape is part of every
        // full game's state (restoration registers its own before start).
        if (game.getState().getWatcher(XmagePublicEventWatcher.class) == null) {
            game.getState().addWatcher(new XmagePublicEventWatcher());
        }
    }

    /**
     * Game handle for post-arrival restoration steps. The engine thread must
     * be parked on an external decision (or not yet started) when the caller
     * touches game state.
     */
    GameCommanderImpl restorationGame() {
        return game;
    }

    // ---- #662 SLOT-06: event log, game shutdown, replay export -----------------

    private void ensureNotShutDown() {
        if (shutDown) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "FULL_GAME_SHUT_DOWN: the game was shut down; no further decision is accepted");
        }
    }

    boolean isShutDown() {
        return shutDown;
    }

    /**
     * Ends the game on request: the native game is ended, decision intake stops,
     * and the engine thread is joined. Every later decision, submission or
     * concession is refused with {@code FULL_GAME_SHUT_DOWN}.
     */
    JsonObject shutdownGame() {
        ensureStarted();
        synchronized (this) {
            if (shutDown) {
                throw new XmageFullGameDecisionController.DecisionException(
                        "FULL_GAME_SHUT_DOWN: the game was already shut down");
            }
            shutDown = true;
        }
        game.end();
        controller.shutDown();
        try {
            if (engineThread != null) {
                engineThread.join(SETTLE_TIMEOUT.toMillis());
            }
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
        }
        boolean alive = engineThread != null && engineThread.isAlive();
        if (alive) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "FULL_GAME_SHUTDOWN_TIMEOUT: the engine thread did not end");
        }
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", protocolGameId);
        payload.addProperty("shut_down", true);
        payload.addProperty("engine_thread_alive", false);
        payload.addProperty("game_over", game.getState().isGameOver());
        String unwind = shutdownUnwind.get();
        payload.addProperty("shutdown_unwind", unwind == null ? "none" : unwind);
        return payload;
    }

    /**
     * The public semantic event log after {@code afterOffset}: the engine's own
     * events recorded by {@link XmagePublicEventWatcher}, players named by seat
     * ({@code P1..PN}), hidden objects unnamed. Monotonic {@code sequence}; the
     * decision count links the log to the decision stream.
     */
    synchronized JsonObject eventLogPayload(int afterOffset) {
        ensureStarted();
        XmagePublicEventWatcher watcher = game.getState().getWatcher(XmagePublicEventWatcher.class);
        if (watcher == null) {
            throw new IllegalStateException("EVENT_LOG_UNAVAILABLE: no public event tape");
        }
        if (afterOffset < 0 || afterOffset > watcher.size()) {
            throw new IllegalArgumentException(
                    "INVALID_EVENT_OFFSET: after_offset must be between 0 and " + watcher.size());
        }
        if (parkedDecisionClass() != null) {
            watcher.settle(game);
        }
        Map<String, String> seatByPlayer = new java.util.HashMap<>();
        restorationSeats().forEach((label, player) -> seatByPlayer.put(player.getId().toString(), label));
        JsonArray events = new JsonArray();
        for (JsonObject raw : watcher.eventsAfter(afterOffset)) {
            events.add(publicEvent(raw, seatByPlayer));
        }
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", protocolGameId);
        payload.addProperty("after_offset", afterOffset);
        payload.addProperty("latest_offset", watcher.size());
        payload.addProperty("decision_count", controller.decisionCount());
        payload.addProperty("observation_scope", "public");
        payload.add("events", events);
        return payload;
    }

    private static JsonObject publicEvent(JsonObject raw, Map<String, String> seatByPlayer) {
        JsonObject event = new JsonObject();
        for (String key : List.of("sequence", "type", "turn", "step", "amount", "flag", "data",
                "from", "to", "combat", "last_power", "last_toughness", "coin_result", "coin_won",
                "public_identity", "target_name", "source_name")) {
            if (raw.has(key)) {
                event.add(key, raw.get(key));
            }
        }
        for (String key : List.of("player", "target", "source")) {
            if (!raw.has(key)) {
                continue;
            }
            String seat = seatByPlayer.get(raw.get(key).getAsString());
            if (seat != null) {
                event.addProperty(key + "_player", seat);
            } else if (!"player".equals(key)) {
                // Only that an object has this role; never its engine id.
                event.addProperty(key + "_present", true);
            }
        }
        return event;
    }

    /**
     * #662 SLOT-06 (c) R1: the replay export. Orchestration-only (R4): it carries
     * the seed and the decklists, so it holds hidden information and is never
     * part of a pilot frame. Only while the engine is parked or has ended.
     */
    synchronized JsonObject replayExportPayload() {
        ensureStarted();
        String state = engineState();
        if (!"PARKED".equals(state) && !"CLEAN_TERMINAL".equals(state)) {
            throw new IllegalStateException("REPLAY_EXPORT_UNAVAILABLE: engine state " + state);
        }
        JsonArray decisions = controller.replayRecord();
        JsonObject export = new JsonObject();
        export.addProperty("schema_version", XmageFullGameReplay.SCHEMA_VERSION);
        export.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        export.add("engine", XmageProvider.providerVersion());
        export.addProperty("scope", "orchestration_only");
        export.addProperty("seed", seed);
        export.addProperty("player_count", playerCount);
        export.addProperty("starting_player_seat", startingPlayerSeat);
        export.addProperty("starting_life", startingLife);
        export.add("decks", replayDecks.deepCopy());
        export.addProperty("decision_count", decisions.size());
        export.add("decisions", decisions);
        export.addProperty("decisions_digest", XmageFullGameReplay.sha256(decisions.toString()));
        export.addProperty("final_state_digest", semanticStateDigest());
        // R3: the frame the engine was parked on when the export was taken. A
        // replay that ends on any other frame asked for one the tape lacks.
        export.add("final_pending", XmageFullGameReplay.pendingFrame(controller.pendingDecision()));
        export.addProperty("final_engine_state", state);
        return export;
    }

    /**
     * A semantic digest of the game state (names and seats, never engine ids):
     * turn, step, per seat life, zone sizes and contents of public zones, and the
     * stack. Two games that made the same semantic choices have equal digests.
     */
    synchronized String semanticStateDigest() {
        JsonObject state = new JsonObject();
        state.addProperty("turn", game.getTurnNum());
        state.addProperty("step", game.getStep() == null ? "" : game.getStep().getType().name());
        state.addProperty("game_over", game.getState().isGameOver());
        JsonArray seats = new JsonArray();
        for (XmageFullGamePlayer player : players) {
            JsonObject seat = new JsonObject();
            seat.addProperty("life", player.getLife());
            seat.addProperty("hand", player.getHand().size());
            seat.addProperty("library", player.getLibrary().size());
            seat.addProperty("in_game", player.isInGame());
            seat.addProperty("lost", player.hasLost());
            seat.add("graveyard", sortedNames(player.getGraveyard().getCards(game)));
            seat.add("battlefield", sortedNames(game.getBattlefield().getAllActivePermanents(player.getId()).stream()
                    .map(permanent -> permanent.getName() + (permanent.isTapped() ? "(T)" : ""))
                    .toList()));
            seat.add("command", sortedNames(game.getState().getCommand().stream()
                    .filter(object -> player.getId().equals(object.getControllerId()))
                    .map(object -> object.getName())
                    .toList()));
            seats.add(seat);
        }
        state.add("seats", seats);
        state.add("stack", sortedNames(game.getStack().stream().map(object -> object.getName()).toList()));
        state.add("exile", sortedNames(game.getExile().getAllCards(game)));
        return XmageFullGameReplay.sha256(state.toString());
    }

    private static JsonArray sortedNames(java.util.Collection<?> items) {
        List<String> names = new ArrayList<>();
        for (Object item : items) {
            names.add(item instanceof mage.MageObject object ? object.getName() : String.valueOf(item));
        }
        names.sort(String::compareTo);
        JsonArray array = new JsonArray();
        names.forEach(array::add);
        return array;
    }

    /**
     * #662 SLOT-06 L1 test oracle: the native callback arguments of the pending
     * decision's actor. Package-private and test-only; never part of any
     * protocol payload.
     */
    Object[] pendingNativeWitness() {
        JsonObject pending = controller.pendingDecision();
        if (pending == null || game == null) {
            return new Object[0];
        }
        mage.players.Player actor = game.getPlayer(
                java.util.UUID.fromString(pending.get("actor_id").getAsString()));
        return actor instanceof XmageFullGamePlayer external
                ? external.nativeWitness(pending.get("decision_offset").getAsLong()) : new Object[0];
    }

    private static List<Integer> seatIndices(int count) {
        List<Integer> indices = new ArrayList<>(count);
        for (int index = 0; index < count; index++) {
            indices.add(index);
        }
        return indices;
    }

    /** Deterministic seat map (P1..PN in deck-handle order) for restoration. */
    Map<String, Player> restorationSeats() {
        Map<String, Player> seats = new java.util.LinkedHashMap<>();
        for (int index = 0; index < players.size(); index++) {
            seats.put("P" + (index + 1), players.get(index));
        }
        return java.util.Collections.unmodifiableMap(seats);
    }

    int playerCount() {
        return playerCount;
    }

    synchronized JsonObject start() {
        if (started) {
            throw new IllegalStateException("FULL_GAME_ALREADY_STARTED");
        }
        started = true;
        Player startingPlayer = players.get(startingPlayerSeat);
        XmageThreadFactory gameThreadFactory = new XmageThreadFactory(
                ThreadUtils.THREAD_PREFIX_GAME + " full-game " + protocolGameId,
                true
        );
        engineThread = gameThreadFactory.newThread(() -> runEngine(startingPlayer.getId()));
        engineThread.start();
        awaitSettled(controller, engineThread, SETTLE_TIMEOUT);
        return statusPayload();
    }

    /**
     * The class of the decision the engine thread is parked on right now, or
     * null. A non-blocking read: it never waits for a decision to appear.
     */
    String parkedDecisionClass() {
        JsonObject pending = controller.pendingDecision();
        if (pending == null || !pending.has("decision_class")
                || pending.get("decision_class").isJsonNull()) {
            return null;
        }
        return pending.get("decision_class").getAsString();
    }

    JsonObject pendingDecisionPayload() {
        ensureStarted();
        awaitSettled(controller, engineThread, SETTLE_TIMEOUT);
        JsonObject payload = statusPayload();
        JsonObject pending = controller.pendingDecision();
        payload.add("decision", pending == null ? JsonNull.INSTANCE : pending);
        return payload;
    }

    JsonObject submit(JsonObject response) {
        ensureNotShutDown();
        ensureStarted();
        controller.submit(response);
        String submittedDecisionId = response.get("decision_id").getAsString();
        awaitDecisionAdvance(submittedDecisionId, Duration.ofSeconds(20));
        return pendingDecisionPayload();
    }

    /**
     * R22 public-zone counts per seat (Commander open information only).
     *
     * <p>Reports hand/library/graveyard/exile/battlefield/command zone
     * <em>counts</em> per seat in game order (seat 0 first). No card
     * identities, order, or hidden content is exposed, so principal-scoped
     * hidden information is preserved. Intended for verifying countable
     * game-state effects (e.g., London mulligan bottom counts via library
     * size) without touching engine internals.</p>
     */
    /**
     * The real principal id at a seat.
     *
     * <p>This is the inverse of {@link #seatOrder()} and exists for a direct
     * engine driver, which legitimately needs to address a principal to submit
     * on its behalf. It is deliberately NOT projected: observations mask every
     * non-viewer id, so a pilot acting through an observation can never obtain
     * an opponent's real identity by way of this method.
     */
    String principalIdAtSeat(int seat) {
        if (seat < 0 || seat >= players.size()) {
            return null;
        }
        return players.get(seat).getId().toString();
    }

    /**
     * Seat index per real principal id, in seat order.
     *
     * <p>Seat order is public information, so this discloses nothing that a
     * projection must hide. It exists because a principal-scoped projection now
     * masks non-viewer ids, and a caller that legitimately needs to relate a
     * real id to a seat must ask the session rather than trying to recover it
     * from an observation.
     */
    Map<String, Integer> seatOrder() {
        Map<String, Integer> order = new LinkedHashMap<>();
        for (int seat = 0; seat < players.size(); seat++) {
            order.put(players.get(seat).getId().toString(), seat);
        }
        return order;
    }

    JsonObject zoneCountsPayload(UUID actorId) {
        return zoneCountsPayload(actorId == null ? null : game.getPlayer(actorId));
    }

    JsonObject zoneCountsPayload(Player actor) {
        ensureStarted();
        JsonArray seats = new JsonArray();
        for (Player player : XmageSeating.playersInSeatOrder(game)) {
            JsonObject item = new JsonObject();
            item.addProperty("seat", XmageSeating.seat(game, player.getId()));
            // Actor-safe: counts are public, but the principal id behind each
            // seat is not. The viewer keeps its own id; every other seat is an
            // opaque token stable for this game.
            item.addProperty("player_id", ActorSafeIdentity.forSeat(game, actor, player));
            item.addProperty("hand_count", player.getHand().size());
            item.addProperty("library_count", player.getLibrary().size());
            item.addProperty("graveyard_count", player.getGraveyard().size());
            item.addProperty("exile_count",
                    game.getExile().getCardsOwned(game, player.getId()).size());
            item.addProperty("battlefield_count",
                    game.getBattlefield().getAllPermanents().stream()
                            .filter(permanent ->
                                    player.getId().equals(permanent.getControllerId()))
                            .count());
            item.addProperty("command_count",
                    game.getCommanderCardsFromCommandZone(
                            player,
                            mage.constants.CommanderCardType.COMMANDER_OR_OATHBREAKER
                    ).size());
            seats.add(item);
        }
        JsonObject payload = new JsonObject();
        payload.add("seats", seats);
        return payload;
    }

    /**
     * WS204 B4-D generic decision-scoped legal-action projection.
     *
     * <p>Returns only the exact currently pending native decision projected
     * through {@link XmageFullGameActionProjection}. Never synthesizes options;
     * fails closed when no decision is pending. The payload is decision-scoped,
     * not a globally complete free-standing legal-actions API.</p>
     */
    synchronized JsonObject legalActionsPayload() {
        return legalActionsPayload(new JsonObject());
    }

    /**
     * #662 (request binding; AF01 unsupported-decision invariant): a request that names
     * a game, an actor or a decision class is bound to the exact pending decision.
     * Any mismatch fails closed with a typed error and returns no part of the
     * decision, so a request for another actor or an unsupported class never
     * receives this actor's options.
     */
    synchronized JsonObject legalActionsPayload(JsonObject request) {
        ensureNotShutDown();
        ensureStarted();
        controller.awaitPendingOrTerminal(Duration.ofSeconds(20));
        JsonObject pending = controller.pendingDecision();
        if (pending == null) {
            if (controller.terminalFailure() != null) {
                throw controller.terminalFailure();
            }
            throw new XmageFullGameDecisionController.DecisionException(
                    "STALE_DECISION: no pending decision"
            );
        }
        requireRequestMatches(request, "game_id", protocolGameId, "UNKNOWN_GAME");
        requireRequestMatches(
                request, "actor_id", pending.get("actor_id").getAsString(), "WRONG_ACTOR");
        requireRequestMatches(
                request,
                "decision_class",
                pending.get("decision_class").getAsString(),
                "UNSUPPORTED_DECISION_CLASS");
        JsonArray actions;
        try {
            actions = XmageFullGameActionProjection.project(pending);
        } catch (XmageFullGameActionProjection.ProjectionException exc) {
            throw new XmageFullGameDecisionController.DecisionException(exc.getMessage(), exc);
        }
        JsonObject payload = statusPayload();
        payload.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        payload.addProperty("decision_id", pending.get("decision_id").getAsString());
        payload.addProperty("actor_id", pending.get("actor_id").getAsString());
        payload.addProperty("decision_class", pending.get("decision_class").getAsString());
        payload.addProperty("decision_scoped", true);
        payload.addProperty("global_capability_promoted", false);
        payload.addProperty("complete", true);
        payload.add("actions", actions);
        payload.add("decision", pending);
        return payload;
    }

    private static void requireRequestMatches(
            JsonObject request, String field, String expected, String code) {
        if (request == null || !request.has(field) || request.get(field).isJsonNull()) {
            return;
        }
        String requested;
        try {
            requested = request.get(field).getAsString();
        } catch (RuntimeException exc) {
            throw new XmageFullGameDecisionController.DecisionException(
                    code + ": " + field + " must be a string");
        }
        if (!expected.equals(requested)) {
            throw new XmageFullGameDecisionController.DecisionException(
                    code + ": " + field + " does not match the pending decision");
        }
    }

    /**
     * WS204 B4-D generic submission: validates a generic proposal against the
     * exact current pending decision, translates only the selected authoritative
     * option into the native controller response, and lets XMage execute.
     *
     * <p>The {@code executed_*} facts describe the native action that already
     * ran; nothing here rolls it back. A projection failure for the <em>next</em>
     * decision is reported explicitly via {@code next_actions_status} (never a
     * silent empty array): an unprojectable existing decision stays
     * observationally distinct from no offered next actions.</p>
     */
    JsonObject submitAction(JsonObject proposal) {
        ensureNotShutDown();
        ensureStarted();
        controller.awaitPendingOrTerminal(Duration.ofSeconds(20));
        JsonObject pending = controller.pendingDecision();
        if (pending == null) {
            if (controller.terminalFailure() != null) {
                throw controller.terminalFailure();
            }
            throw new XmageFullGameDecisionController.DecisionException(
                    "STALE_DECISION: no pending decision"
            );
        }
        JsonObject response;
        try {
            response = XmageFullGameActionProjection.toDecisionResponse(pending, proposal);
        } catch (XmageFullGameActionProjection.ProjectionException exc) {
            throw new XmageFullGameDecisionController.DecisionException(exc.getMessage(), exc);
        }
        String legalActionId = proposal.has("legal_action_id")
                && !proposal.get("legal_action_id").isJsonNull()
                ? proposal.get("legal_action_id").getAsString() : "";
        String proposalType = proposal.has("action_type")
                && !proposal.get("action_type").isJsonNull()
                ? proposal.get("action_type").getAsString() : "";
        controller.submit(response);
        awaitDecisionAdvance(pending.get("decision_id").getAsString(), Duration.ofSeconds(20));
        JsonObject result = pendingDecisionPayload();
        result.addProperty("executed_decision_id", pending.get("decision_id").getAsString());
        result.addProperty("executed_actor_id", pending.get("actor_id").getAsString());
        result.addProperty("executed_action_id", legalActionId);
        result.addProperty("executed_action_type", proposalType);
        result.addProperty("decision_scoped", true);
        result.addProperty("global_capability_promoted", false);
        JsonObject nextFragment = nextActionsPayload(controller.pendingDecision());
        result.add("next_actions", nextFragment.getAsJsonArray("next_actions"));
        for (java.util.Map.Entry<String, JsonElement> entry : nextFragment.entrySet()) {
            if (!entry.getKey().equals("next_actions")) {
                result.add(entry.getKey(), entry.getValue());
            }
        }
        return result;
    }

    /**
     * R21 fail-closed next-decision projection (Coordinator Finding A).
     *
     * <p>Projects one already-observed next pending decision into the
     * {@code next_actions} array plus an explicit {@code next_actions_status}:
     * {@code "projected"} (projection succeeded, array may legitimately be
     * empty), {@code "no_pending_decision"} (terminal — nothing to project),
     * or {@code "projection_failed"} with {@code next_actions_projection_error}
     * (an existing decision could not be projected; the already-executed
     * action is unaffected — no rollback implied). A projection failure is
     * never reported as a silent empty success.</p>
     */
    static JsonObject nextActionsPayload(JsonObject next) {
        JsonObject fragment = new JsonObject();
        if (next == null) {
            fragment.add("next_actions", new JsonArray());
            fragment.addProperty("next_actions_status", "no_pending_decision");
            return fragment;
        }
        try {
            fragment.add("next_actions", XmageFullGameActionProjection.project(next));
            fragment.addProperty("next_actions_status", "projected");
        } catch (XmageFullGameActionProjection.ProjectionException exc) {
            fragment.add("next_actions", new JsonArray());
            fragment.addProperty("next_actions_status", "projection_failed");
            fragment.addProperty("next_actions_projection_error", exc.getMessage());
        }
        return fragment;
    }

    /**
     * WS213 live Rules-seed binding proof. Every field is read from the native
     * game at payload time; nothing is cached from construction. {@code
     * seed_supported} is true only when this proof holds for the run.
     */
    synchronized JsonObject rulesSeedBindingPayload() {
        return XmageRulesSeedBinding.payload(game, seed);
    }

    /**
     * AF09 orchestration channel: the engine's Rules-RNG results and a
     * privileged state digest, HMAC digests only under the launch's
     * orchestration key ({@link XmageRulesRngResultTape}). Read only while the
     * engine is parked on a decision or has ended; {@code engine_state} says
     * which, and whether an end was a clean game over or a failure.
     */
    synchronized JsonObject rulesRngTapePayload() {
        ensureStarted();
        if (!XmageRulesRngResultTape.enabled()) {
            String problem = XmageRulesRngResultTape.keyProblem();
            throw new IllegalStateException("ORCHESTRATION_CHANNEL_NOT_ENABLED: "
                    + (problem == null ? "this launch carries no orchestration key" : problem));
        }
        JsonObject payload = new JsonObject();
        String engineState = engineState();
        payload.addProperty("engine_state", engineState);
        payload.addProperty("observation_scope", "orchestration_keyed_digests");
        if (!"PARKED".equals(engineState) && !"CLEAN_TERMINAL".equals(engineState)) {
            // No digest of an engine that is still running or failed.
            return payload;
        }
        payload.addProperty("rules_random_calls", game.getRulesRandomCalls());
        payload.add("rules_rng_results", XmageRulesRngResultTape.results(game));
        payload.addProperty("privileged_state_digest", privilegedStateDigest());
        // The engine must still be in the same state after the digest: a
        // decision answered or a thread ended meanwhile voids it.
        if (!engineState.equals(engineState())) {
            JsonObject moved = new JsonObject();
            moved.addProperty("engine_state", "RUNNING");
            moved.addProperty("observation_scope", "orchestration_keyed_digests");
            return moved;
        }
        return payload;
    }

    /**
     * PARKED: waiting on an external decision. CLEAN_TERMINAL: the engine
     * thread ended a game that is over, with no failure and no engine error.
     * FAILED: a failure, or an ended thread without a clean game over.
     * RUNNING: anything else. Thread liveness is sampled first, so a thread that
     * fails and ends between two reads is never taken for a clean end.
     */
    /** #662 replay verifier: the engine state after a replay (see {@link #engineState()}). */
    synchronized String replayEngineState() {
        awaitSettled(controller, engineThread, SETTLE_TIMEOUT);
        return engineState();
    }

    private String engineState() {
        boolean alive = engineThread != null && engineThread.isAlive();
        if (controller.terminalFailure() != null) {
            return alive ? "RUNNING" : "FAILED";
        }
        if (controller.pendingDecision() != null) {
            return "PARKED";
        }
        if (engineThread != null && !alive) {
            boolean clean = game.hasEnded() && controller.terminalFailure() == null
                    && game.getTotalErrorsCount() == 0;
            return clean ? "CLEAN_TERMINAL" : "FAILED";
        }
        return "RUNNING";
    }

    /** The controller's decision transcript (orchestration-side; tests and receipts). */
    JsonArray controllerTranscript() {
        return controller.transcript();
    }

    /**
     * Every player's zones in seating order (library order included), the
     * command zone, the stack and the turn position, each object written as its
     * requested semantic id or otherwise its true name (a face-down object by
     * its underlying card), with tapped, face-down, phasing, damage, counters
     * and attachment.
     */
    String privilegedStateDigest() {
        List<String> lines = new ArrayList<>();
        mage.game.turn.Step step = game.getStep();
        lines.add("turn:" + game.getTurnNum() + " step:" + (step == null ? "none" : step.getType())
                + " active:" + XmageRulesRngResultTape.seatIndex(game, game.getActivePlayerId()));
        // Seat order, not the PlayerList's iteration from its moving pointer.
        for (Player player : XmageSeating.playersInSeatOrder(game)) {
            UUID playerId = player.getId();
            lines.add("seat:" + XmageRulesRngResultTape.seatIndex(game, playerId)
                    + " life:" + player.getLife() + " in_game:" + player.isInGame());
            lines.add("library:" + String.join(",", tokens(player.getLibrary().getCardList(), false)));
            lines.add("hand:" + String.join(",", tokens(new ArrayList<>(player.getHand()), true)));
            lines.add("graveyard:" + String.join(",", tokens(new ArrayList<>(player.getGraveyard()), false)));
            List<UUID> exiled = new ArrayList<>();
            for (mage.cards.Card card : game.getExile().getAllCards(game)) {
                if (playerId.equals(card.getOwnerId())) {
                    exiled.add(card.getId());
                }
            }
            lines.add("exile:" + String.join(",", tokens(exiled, true)));
            List<String> permanents = new ArrayList<>();
            for (mage.game.permanent.Permanent permanent : game.getBattlefield().getAllPermanents()) {
                if (!playerId.equals(permanent.getControllerId())) {
                    continue;
                }
                List<String> counters = new ArrayList<>();
                for (mage.counters.Counter counter : permanent.getCounters(game).values()) {
                    counters.add(counter.getName() + "=" + counter.getCount());
                }
                Collections.sort(counters);
                String name = permanent.getName();
                if (permanent.isFaceDown(game)) {
                    mage.cards.Card card = game.getCard(permanent.getId());
                    name = "face_down:" + (card == null ? "?" : card.getName());
                }
                UUID attachedTo = permanent.getAttachedTo();
                permanents.add(token(permanent.getId(), name)
                        + (permanent.isTapped() ? "|tapped" : "")
                        + (permanent.isPhasedIn() ? "" : "|phased_out")
                        + "|damage=" + permanent.getDamage()
                        + "|attached=" + (attachedTo == null ? "" : token(attachedTo, nameOf(attachedTo)))
                        + "|" + String.join(";", counters));
            }
            Collections.sort(permanents);
            lines.add("battlefield:" + String.join(",", permanents));
        }
        List<String> command = new ArrayList<>();
        for (mage.game.command.CommandObject object : game.getState().getCommand()) {
            command.add(token(object.getId(), object.getName()));
        }
        Collections.sort(command);
        lines.add("command:" + String.join(",", command));
        List<String> stack = new ArrayList<>();
        for (mage.game.stack.StackObject object : game.getStack()) {
            stack.add(object.getName());
        }
        lines.add("stack:" + String.join(",", stack));
        return XmageRulesRngResultTape.digest(lines);
    }

    private String nameOf(UUID id) {
        mage.MageObject object = game.getObject(id);
        return object == null ? "?" : object.getName();
    }

    private List<String> tokens(List<UUID> ids, boolean sorted) {
        List<String> out = new ArrayList<>(ids.size());
        for (UUID id : ids) {
            mage.cards.Card card = game.getCard(id);
            out.add(token(id, card == null ? "?" : card.getName()));
        }
        if (sorted) {
            Collections.sort(out);
        }
        return out;
    }

    private String token(UUID id, String name) {
        String semantic = restoration == null ? null : restoration.semanticIdOf(id);
        return semantic != null ? "s:" + semantic : "n:" + name;
    }

    /**
     * WS213 authoritative concession offer (WS211 engine contract).
     *
     * <p>Availability originates exclusively in {@code
     * game.canConcede(exactPrincipal)}: true if and only if the game has not
     * ended and the actor is a player still in this game. No Lab-side legality
     * heuristic exists. The offer is per-principal and carries no priority,
     * stack, step or turn-control requirement (CR 104.3a, CR 723.6).</p>
     */
    synchronized JsonObject concedeOfferPayload(String principalId) {
        ensureNotShutDown();
        ensureStarted();
        UUID principal = requireSessionPlayer(principalId);
        boolean available = game.canConcede(principal);
        JsonObject payload = statusPayload();
        payload.addProperty("concede_available", available);
        payload.addProperty("concede_actor_id", principal.toString());
        if (available) {
            JsonObject action = new JsonObject();
            action.addProperty("action_id", "concede:" + principal);
            action.addProperty("actor_id", principal.toString());
            action.addProperty("action_type", "concede");
            action.add("source_object_id", com.google.gson.JsonNull.INSTANCE);
            action.add("target_ids", new JsonArray());
            action.add("allowed_target_ids", new JsonArray());
            action.add("modes", new JsonArray());
            JsonObject metadata = new JsonObject();
            metadata.addProperty("availability", "Game.canConcede(exactPrincipal)");
            metadata.addProperty("rules_authority", "xmage");
            action.add("metadata", metadata);
            payload.add("concede_action", action);
        } else {
            payload.add("concede_action", com.google.gson.JsonNull.INSTANCE);
        }
        return payload;
    }

    /**
     * WS213 authoritative concession execution (WS211 engine contract).
     *
     * <p>Binding order: the proposal must name the exact native session player
     * UUID as both actor and subject (actor == subject == exact principal).
     * A controller UUID named for a controlled player is rejected: execution
     * always submits the named principal itself to native {@code
     * game.concede}, so one principal can never be conceded for another.
     * Availability is re-checked live; stale requests fail closed. Execution
     * is native (one-shot principal-bound authorization releases the player's
     * exact native concede path; no Lab-side outcome is synthesized).</p>
     */
    synchronized JsonObject submitConcede(JsonObject proposal) {
        ensureNotShutDown();
        ensureStarted();
        if (proposal == null) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "PILOT_RESPONSE_INVALID: concede proposal is null"
            );
        }
        String actor = textOrEmpty(proposal, "actor_id");
        String subject = textOrEmpty(proposal, "player_id");
        if (actor.isBlank() || subject.isBlank()) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "PILOT_RESPONSE_INVALID: concede proposal requires actor_id and player_id"
            );
        }
        if (!actor.equals(subject)) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "PILOT_RESPONSE_INVALID: concede actor must be the conceding principal itself"
            );
        }
        UUID principal = requireSessionPlayer(actor);
        if (!game.canConcede(principal)) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "CONCEDE_UNAVAILABLE: Game.canConcede rejects this principal now"
            );
        }
        XmageFullGamePlayer player = playerById(principal);
        player.armConcession(principal);
        try {
            game.concede(principal);
        } finally {
            player.disarmConcession(principal);
        }
        controller.recordReplayConcession(players.indexOf(player));
        // F-34: a frame the conceder was making for a player whose turn it
        // controlled follows the engine's control state after the leave.
        // F-42: a stale own frame of the conceder that the native signal did not reach.
        controller.cancelPendingForDepartedPlayer(game);
        controller.followTurnControl(game);
        JsonObject result = pendingDecisionPayload();
        result.addProperty("conceded_actor_id", principal.toString());
        result.addProperty("concede_available_before", true);
        result.addProperty("concede_available_after", game.canConcede(principal));
        return result;
    }

    private UUID requireSessionPlayer(String principalId) {
        UUID principal;
        try {
            principal = UUID.fromString(principalId == null ? "" : principalId.trim());
        } catch (IllegalArgumentException exc) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "PILOT_RESPONSE_INVALID: unknown concede principal", exc
            );
        }
        for (XmageFullGamePlayer player : players) {
            if (player.getId().equals(principal)) {
                return principal;
            }
        }
        throw new XmageFullGameDecisionController.DecisionException(
                "PILOT_RESPONSE_INVALID: unknown concede principal"
        );
    }

    private XmageFullGamePlayer playerById(UUID principal) {
        for (XmageFullGamePlayer player : players) {
            if (player.getId().equals(principal)) {
                return player;
            }
        }
        throw new XmageFullGameDecisionController.DecisionException(
                "PILOT_RESPONSE_INVALID: unknown concede principal"
        );
    }

    private static String textOrEmpty(JsonObject proposal, String property) {
        if (!proposal.has(property) || proposal.get(property).isJsonNull()) {
            return "";
        }
        try {
            return proposal.get(property).getAsString().trim();
        } catch (RuntimeException exc) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "PILOT_RESPONSE_INVALID: " + property + " must be a string", exc
            );
        }
    }

    JsonObject resultPayload() {
        ensureStarted();
        JsonObject payload = statusPayload();
        payload.add("transcript", controller.transcript());
        payload.addProperty("decision_count", controller.decisionCount());
        payload.addProperty("evidence_class", EVIDENCE_CLASS);
        payload.addProperty("consumed_gameplay_evidence", false);
        payload.addProperty("holdout_consumed", false);
        payload.addProperty("official_campaign_eligible", false);
        payload.addProperty("rules_authority", "xmage");
        payload.addProperty("decision_policy_authority", "commander_lab_external_pilot");
        payload.addProperty("seed", seed);
        payload.addProperty("seed_scope", "single_isolated_jvm_process");
        payload.add("rules_seed_binding", rulesSeedBindingPayload());
        payload.addProperty("bit_exact_replay_validated", false);
        return payload;
    }

    boolean isTerminal() {
        return controller.terminalFailure() != null || controller.pendingDecision() == null
                && engineThread != null && !engineThread.isAlive();
    }

    private void awaitDecisionAdvance(String submittedDecisionId, Duration timeout) {
        long deadlineNanos = System.nanoTime() + timeout.toNanos();
        while (true) {
            if (controller.terminalFailure() != null || isEngineTerminal()) {
                return;
            }
            JsonObject pending = controller.pendingDecision();
            if (pending == null) {
                return;
            }
            String pendingDecisionId = pending.get("decision_id").getAsString();
            if (!submittedDecisionId.equals(pendingDecisionId)) {
                return;
            }
            if (System.nanoTime() >= deadlineNanos) {
                throw new XmageFullGameDecisionController.DecisionException(
                        "DECISION_ADVANCE_TIMEOUT: engine did not consume " + submittedDecisionId
                );
            }
            try {
                Thread.sleep(1L);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                throw new XmageFullGameDecisionController.DecisionException(
                        "DECISION_ADVANCE_TIMEOUT: interrupted while advancing "
                                + submittedDecisionId,
                        exc
                );
            }
        }
    }

    /**
     * Bound for {@link #awaitSettled}. A submit can first spend up to 20 s on
     * the decision advance and 20 s more on a legal-action wait, so 75 s keeps
     * the whole request below the Lab transport's 120 s request timeout and an
     * honest bridge-side timeout is reported before the client gives up.
     */
    static final Duration SETTLE_TIMEOUT = Duration.ofSeconds(75);

    /**
     * Test seam: runs on the engine thread right after the controller is marked
     * terminal, i.e. inside the window {@link #awaitSettled} closes. A no-op in
     * production.
     */
    static volatile Runnable afterTerminalMarked = () -> { };

    /**
     * Waits until the engine is parked on a decision or has ended, and only
     * then lets a status be built. {@code markTerminal()} runs in
     * {@code runEngine}'s finally block on the engine thread, just before that
     * thread ends, while {@code terminal} in the status is derived from thread
     * liveness. A controller already marked terminal is therefore joined
     * (bounded) first; without that a finished game could be reported as
     * running with no pending decision, which a replay consumer correctly
     * refuses as an early termination. A wait that ends with neither a decision
     * nor a game over is an explicit DECISION_ADVANCE_TIMEOUT, never a status
     * that looks like a mid-step engine.
     */
    static void awaitSettled(
            XmageFullGameDecisionController controller, Thread engineThread, Duration timeout) {
        long deadline = System.nanoTime() + timeout.toNanos();
        if (!controller.awaitPendingOrTerminal(timeout)) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "DECISION_ADVANCE_TIMEOUT: engine neither offered a decision nor ended within "
                            + timeout.toSeconds() + "s"
            );
        }
        if (controller.pendingDecision() != null || !controller.terminalMarked()
                || engineThread == null) {
            return;
        }
        try {
            engineThread.join(Math.max(1L, (deadline - System.nanoTime()) / 1_000_000L));
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
            throw new XmageFullGameDecisionController.DecisionException(
                    "DECISION_ADVANCE_TIMEOUT: interrupted while the ended engine thread finished",
                    exc
            );
        }
        if (engineThread.isAlive()) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "DECISION_ADVANCE_TIMEOUT: engine marked the game over but its thread did not end"
            );
        }
    }

    private void runEngine(UUID startingPlayerId) {
        try {
            game.start(startingPlayerId);
            if (game.getTotalErrorsCount() != 0) {
                throw new IllegalStateException(
                        "XMAGE_INTERNAL_ERRORS: " + game.getTotalErrorsCount()
                                + "; diagnostics=" + diagnosticSummary()
                );
            }
        } catch (Throwable exc) {
            if (shutDown) {
                // #662: an orchestrator-ordered shutdown unwinds the engine thread
                // through the refused decision; that is the requested end, not a
                // Rules failure. The unwind is still recorded for the result.
                shutdownUnwind.compareAndSet(null, exc.getClass().getSimpleName() + ": " + safeMessage(exc));
            } else {
                engineFailure.compareAndSet(null, exc);
                controller.failClosed(
                        "XMAGE_FULL_GAME_FAILED",
                        exc.getClass().getSimpleName() + ": " + safeMessage(exc)
                );
            }
        } finally {
            controller.markTerminal();
            afterTerminalMarked.run();
        }
    }

    private synchronized void ensureStarted() {
        if (!started) {
            throw new IllegalStateException("FULL_GAME_NOT_STARTED");
        }
    }

    private JsonObject statusPayload() {
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", protocolGameId);
        payload.addProperty("engine_game_id", game.getId().toString());
        payload.addProperty("player_count", game.getPlayers().size());
        payload.addProperty("starting_player_seat", startingPlayerSeat);
        payload.addProperty("seed", seed);
        payload.addProperty("started", started);
        payload.addProperty("terminal", isEngineTerminal());
        payload.addProperty("engine_thread_alive", engineThread != null && engineThread.isAlive());
        payload.addProperty(
                "engine_thread_name",
                engineThread == null ? "" : engineThread.getName()
        );
        payload.addProperty("decision_count", controller.decisionCount());
        payload.addProperty("engine_error_count", game.getTotalErrorsCount());
        payload.add("engine_error_diagnostics", diagnosticPayload());
        payload.addProperty("evidence_class", EVIDENCE_CLASS);
        payload.addProperty("consumed_gameplay_evidence", false);
        payload.addProperty("holdout_consumed", false);
        payload.addProperty("operational_pod_size", playerCount);

        Throwable failure = engineFailure.get();
        if (failure == null && controller.terminalFailure() == null) {
            payload.add("failure", JsonNull.INSTANCE);
        } else {
            JsonObject error = new JsonObject();
            if (failure != null) {
                error.addProperty("type", failure.getClass().getName());
                error.addProperty("message", safeMessage(failure));
            } else {
                error.addProperty("type", "decision_controller");
                error.addProperty("message", controller.terminalFailure().getMessage());
            }
            payload.add("failure", error);
        }

        JsonArray outcomes = new JsonArray();
        for (Player player : XmageSeating.playersInSeatOrder(game)) {
            JsonObject item = new JsonObject();
            item.addProperty("seat", XmageSeating.seat(game, player.getId()));
            // Actor-safe: a game result must not enumerate opponents' real ids.
            item.addProperty("player_id", ActorSafeIdentity.forSeat(game, player, player));
            item.addProperty("life", player.getLife());
            item.addProperty("won", player.hasWon());
            item.addProperty("lost", player.hasLost());
            item.addProperty("left", player.hasLeft());
            // WS213 live authoritative availability per principal (WS211):
            // proof, not heuristic; re-evaluated on every payload.
            item.addProperty("can_concede", game.canConcede(player.getId()));
            outcomes.add(item);
        }
        payload.add("outcomes", outcomes);
        payload.add("rules_seed_binding", rulesSeedBindingPayload());
        payload.addProperty("turn_number", game.getState().getTurnNum());
        return payload;
    }

    private JsonArray diagnosticPayload() {
        JsonArray payload = new JsonArray();
        synchronized (engineErrorDiagnostics) {
            for (String diagnostic : engineErrorDiagnostics) {
                payload.add(diagnostic);
            }
        }
        return payload;
    }

    private String diagnosticSummary() {
        synchronized (engineErrorDiagnostics) {
            if (engineErrorDiagnostics.isEmpty()) {
                return "[]";
            }
            int limit = Math.min(5, engineErrorDiagnostics.size());
            return engineErrorDiagnostics.subList(0, limit).toString();
        }
    }

    private boolean isEngineTerminal() {
        return started
                && engineThread != null
                && !engineThread.isAlive();
    }

    private static String safeMessage(Throwable exc) {
        String message = exc.getMessage();
        return message == null || message.isBlank() ? exc.getClass().getName() : message;
    }
}