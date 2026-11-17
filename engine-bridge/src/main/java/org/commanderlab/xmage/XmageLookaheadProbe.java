package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.events.TableEvent;
import mage.players.Player;
import mage.util.ThreadUtils;
import mage.util.XmageThreadFactory;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;
import java.util.Random;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Bounded, isolated in-JVM look-ahead probe over a {@code Game.copy()} branch.
 *
 * <p>Implements §2/§5 of the Studio Bridge contract: XMage remains the sole Rules
 * authority; the copy binds an explicit probe seed, isolates static redactor
 * and RNG-tape keys via {@link XmageFullGameStateRedactor#registerProbeGame},
 * redetermines every opponent hidden hand/library slice from what the deciding
 * viewer is not entitled to see, and always cleans up both its thread and
 * redactor records on completion or {@link #end()}.</p>
 */
final class XmageLookaheadProbe implements AutoCloseable {

    private static final Duration PROBE_DECISION_TIMEOUT = Duration.ofSeconds(15);
    private static final Duration PROBE_SETTLE_TIMEOUT = Duration.ofSeconds(25);
    private static final Duration PROBE_END_JOIN_TIMEOUT = Duration.ofSeconds(5);

    private record CandidateSignature(String optionId, String optionType, String label, int occurrence) {
    }

    private final String probeId;
    private final long probeSeed;
    private final boolean redetermined;
    private final Game copy;
    private final String probeKey;
    private final UUID viewerId;
    private final Player probeViewer;
    private final int baseErrorCount;
    private final XmageFullGameDecisionController probeController;
    private final AtomicReference<Throwable> probeFailure = new AtomicReference<>();
    private final List<String> engineErrorDiagnostics =
            Collections.synchronizedList(new ArrayList<>());
    private final Thread probeThread;

    private volatile boolean stopped;
    private volatile boolean closed;

    private XmageLookaheadProbe(
            String probeId,
            long probeSeed,
            boolean redetermined,
            Game realGame,
            UUID viewerId
    ) {
        this.probeId = probeId;
        this.probeSeed = probeSeed;
        this.redetermined = redetermined;
        this.viewerId = viewerId;
        this.copy = realGame.copy();
        this.baseErrorCount = Math.max(0, copy.getTotalErrorsCount());
        this.probeKey = XmageFullGameStateRedactor.registerProbeGame(copy);
        XmageFullGameStateRedactor.copyRestoredFaceDownIdentities(realGame, copy);
        this.probeController = new XmageFullGameDecisionController(PROBE_DECISION_TIMEOUT, false);

        copy.addTableEventListener(event -> {
            if (event.getEventType() != TableEvent.EventType.ERROR) {
                return;
            }
            Exception exception = event.getException();
            String exceptionClass = exception == null ? "unknown" : exception.getClass().getName();
            String exceptionMessage = exception == null ? "" : safeMessage(exception);
            String eventMessage = event.getMessage() == null ? "" : event.getMessage();
            engineErrorDiagnostics.add(
                    exceptionClass + ": " + exceptionMessage + " [event=" + eventMessage + "]"
            );
        });

        XmageRulesSeedBinding.bind(copy, probeSeed);

        Player foundViewer = null;
        for (Player player : copy.getPlayers().values()) {
            if (player instanceof XmageFullGamePlayer fgp) {
                fgp.rebindForLookaheadProbe(probeController);
            }
            if (player != null && viewerId.equals(player.getId())) {
                foundViewer = player;
            }
        }
        if (foundViewer == null) {
            XmageFullGameStateRedactor.unregisterProbeGame(copy);
            throw new XmageFullGameDecisionController.DecisionException(
                    "WRONG_ACTOR: viewer player missing in copied game: " + viewerId
            );
        }
        this.probeViewer = foundViewer;

        if (redetermined) {
            redetermineHiddenZones(copy, probeViewer);
        }

        XmageThreadFactory factory = new XmageThreadFactory(
                ThreadUtils.THREAD_PREFIX_GAME + " lookahead-probe-" + probeId,
                true
        );
        this.probeThread = factory.newThread(this::runProbe);
    }

    static StartResult start(
            Game realGame,
            JsonObject realPending,
            UUID viewerId,
            String candidateOptionId,
            long probeSeed,
            boolean redetermine
    ) {
        if (realGame == null || realPending == null || viewerId == null) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "LOOKAHEAD_PROBE_INVALID: active game, pending priority frame, and viewer required"
            );
        }
        String decisionClass = strictString(realPending, "decision_class");
        if (!"priority".equals(decisionClass)) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "LOOKAHEAD_REQUIRES_PRIORITY: cannot branch on decision_class=" + decisionClass
            );
        }
        String pendingActor = strictString(realPending, "actor_id");
        if (!viewerId.toString().equals(pendingActor)) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "WRONG_ACTOR: pending decision belongs to " + pendingActor + ", not " + viewerId
            );
        }
        CandidateSignature candidate = extractCandidateSignature(realPending, candidateOptionId);

        String probeId = "probe-" + UUID.randomUUID();
        XmageLookaheadProbe probe = new XmageLookaheadProbe(
                probeId, probeSeed, redetermine, realGame, viewerId
        );
        try {
            JsonObject initialPayload = probe.launchAndTakeCandidate(candidate);
            return new StartResult(probe, initialPayload);
        } catch (RuntimeException | Error exc) {
            probe.close();
            throw exc;
        }
    }

    record StartResult(XmageLookaheadProbe probe, JsonObject payload) {
    }

    String probeId() {
        return probeId;
    }

    String probeKey() {
        return probeKey;
    }

    boolean isClosed() {
        return closed;
    }

    private JsonObject launchAndTakeCandidate(CandidateSignature candidate) {
        probeThread.start();
        XmageFullGameSession.awaitSettled(probeController, probeThread, PROBE_SETTLE_TIMEOUT);
        ensureHealthy();

        JsonObject firstPending = probeController.pendingDecision();
        if (firstPending == null) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "LOOKAHEAD_PROBE_FAILED: copied game did not reach initial priority decision"
            );
        }
        if (!"priority".equals(strictString(firstPending, "decision_class"))) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "LOOKAHEAD_PROBE_FAILED: expected priority decision after resume, got "
                            + strictString(firstPending, "decision_class")
            );
        }
        if (!viewerId.toString().equals(strictString(firstPending, "actor_id"))) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "LOOKAHEAD_PROBE_FAILED: expected actor " + viewerId + " after resume, got "
                            + strictString(firstPending, "actor_id")
            );
        }

        String matchedOptionId = matchCandidateOptionId(firstPending, candidate);
        String firstDecisionId = strictString(firstPending, "decision_id");

        JsonObject response = new JsonObject();
        response.addProperty("decision_id", firstDecisionId);
        response.addProperty("actor_id", viewerId.toString());
        JsonArray selected = new JsonArray();
        selected.add(matchedOptionId);
        response.add("selected_option_ids", selected);
        response.add("ordering", new JsonArray());

        probeController.submit(response);
        awaitDecisionAdvance(firstDecisionId, Duration.ofSeconds(15));
        XmageFullGameSession.awaitSettled(probeController, probeThread, PROBE_SETTLE_TIMEOUT);
        return statusPayload();
    }

    synchronized JsonObject step(JsonObject response) {
        if (closed) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "LOOKAHEAD_PROBE_CLOSED: probe " + probeId + " was ended"
            );
        }
        if (isTerminal()) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "LOOKAHEAD_PROBE_TERMINAL: probe " + probeId + " has already finished"
            );
        }
        JsonObject pending = probeController.pendingDecision();
        if (pending == null) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "STALE_DECISION: probe has no pending decision"
            );
        }
        String pendingId = strictString(pending, "decision_id");
        probeController.submit(response);
        awaitDecisionAdvance(pendingId, Duration.ofSeconds(15));
        XmageFullGameSession.awaitSettled(probeController, probeThread, PROBE_SETTLE_TIMEOUT);
        return statusPayload();
    }

    synchronized JsonObject end() {
        closeInternal();
        JsonObject payload = new JsonObject();
        payload.addProperty("probe_id", probeId);
        payload.addProperty("ended", true);
        payload.addProperty("probe_thread_alive", probeThread.isAlive());
        return payload;
    }

    @Override
    public synchronized void close() {
        closeInternal();
    }

    private void closeInternal() {
        if (closed && !probeThread.isAlive()) {
            XmageFullGameStateRedactor.unregisterProbeGame(copy);
            return;
        }
        stopped = true;
        closed = true;
        try {
            copy.pause();
            copy.end();
        } catch (RuntimeException ignored) {
            // Best-effort engine stop; controller shutdown forces clean unwind.
        }
        probeController.shutDownForProbe();
        try {
            if (probeThread.isAlive()) {
                probeThread.join(PROBE_END_JOIN_TIMEOUT.toMillis());
            }
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
        } finally {
            XmageFullGameStateRedactor.unregisterProbeGame(copy);
        }
    }

    private void runProbe() {
        try {
            copy.resume();
        } catch (XmageFullGameDecisionController.ProbeStopError ignored) {
            // Cleanly cancelled by end() or close().
        } catch (Throwable exc) {
            if (!stopped) {
                probeFailure.compareAndSet(null, exc);
                String detail = exc.getClass().getSimpleName() + ": " + safeMessage(exc);
                probeController.failClosed("LOOKAHEAD_PROBE_FAILED", detail);
            }
        } finally {
            probeController.markTerminal();
        }
    }

    private boolean isTerminal() {
        return probeController.terminalFailure() != null
                || (probeController.pendingDecision() == null && !probeThread.isAlive());
    }

    private void ensureHealthy() {
        XmageFullGameDecisionController.DecisionException controllerFailure =
                probeController.terminalFailure();
        if (controllerFailure != null) {
            throw controllerFailure;
        }
        Throwable rawFailure = probeFailure.get();
        if (rawFailure != null) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "LOOKAHEAD_PROBE_FAILED: " + safeMessage(rawFailure),
                    rawFailure
            );
        }
    }

    private int newEngineErrors() {
        return Math.max(0, copy.getTotalErrorsCount() - baseErrorCount);
    }

    private JsonObject statusPayload() {
        JsonObject payload = new JsonObject();
        payload.addProperty("probe_id", probeId);
        payload.addProperty("probe_seed", probeSeed);
        payload.addProperty("redetermined", redetermined);
        payload.addProperty("terminal", isTerminal());
        payload.addProperty("engine_error_count", newEngineErrors());
        JsonArray diagnostics = new JsonArray();
        synchronized (engineErrorDiagnostics) {
            for (String item : engineErrorDiagnostics) {
                diagnostics.add(item);
            }
        }
        payload.add("engine_error_diagnostics", diagnostics);

        Throwable failure = probeFailure.get();
        XmageFullGameDecisionController.DecisionException controllerFailure =
                probeController.terminalFailure();
        if (failure == null && controllerFailure == null) {
            payload.add("failure", JsonNull.INSTANCE);
        } else {
            JsonObject failureObj = new JsonObject();
            if (failure != null) {
                failureObj.addProperty("type", failure.getClass().getName());
                failureObj.addProperty("message", safeMessage(failure));
            } else {
                failureObj.addProperty("type", "decision_controller");
                failureObj.addProperty("message", controllerFailure.getMessage());
            }
            payload.add("failure", failureObj);
        }

        JsonObject pending = probeController.pendingDecision();
        payload.add("decision", pending == null ? JsonNull.INSTANCE : pending);
        payload.add("actor_view", XmageFullGameStateRedactor.actorView(copy, probeViewer));
        return payload;
    }

    private void awaitDecisionAdvance(String submittedDecisionId, Duration timeout) {
        long deadlineNanos = System.nanoTime() + timeout.toNanos();
        while (true) {
            if (probeController.terminalFailure() != null || !probeThread.isAlive()) {
                return;
            }
            JsonObject pending = probeController.pendingDecision();
            if (pending == null) {
                return;
            }
            String currentId = strictString(pending, "decision_id");
            if (!submittedDecisionId.equals(currentId)) {
                return;
            }
            if (System.nanoTime() >= deadlineNanos) {
                throw new XmageFullGameDecisionController.DecisionException(
                        "DECISION_ADVANCE_TIMEOUT: probe engine did not consume " + submittedDecisionId
                );
            }
            try {
                Thread.sleep(1L);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                throw new XmageFullGameDecisionController.DecisionException(
                        "DECISION_ADVANCE_TIMEOUT: interrupted while advancing probe",
                        exc
                );
            }
        }
    }

    /**
     * Per-owner §5 hidden-zone redetermination under {@code copy.getRulesRandom()}.
     *
     * <p>Visible private states (viewer and any player whose turn the viewer
     * currently controls under CR 723.4) retain their exact hand and only have
     * the hidden portion of their library shuffled. Non-visible opponents have
     * their owned hand + hidden library pooled, shuffled with Fisher-Yates, and
     * re-dealt to exact original hand and library sizes. Publicly revealed top
     * library cards ({@code player.isTopCardRevealed()}) stay pinned at position 0.</p>
     */
    private static void redetermineHiddenZones(Game copy, Player viewer) {
        Random rng = copy.getRulesRandom();
        for (Player player : XmageSeating.playersInSeatOrder(copy)) {
            if (player == null) {
                continue;
            }
            UUID playerId = player.getId();
            boolean visibleToViewer = playerId.equals(viewer.getId())
                    || viewer.getId().equals(player.getTurnControlledBy());

            List<UUID> libIds = new ArrayList<>(player.getLibrary().getCardList());
            Card pinnedTop = null;
            if (player.isTopCardRevealed() && !libIds.isEmpty()) {
                UUID topId = libIds.remove(0);
                pinnedTop = copy.getCard(topId);
            }

            if (visibleToViewer) {
                shuffleList(libIds, rng);
                rebuildLibrary(copy, player, pinnedTop, libIds);
                continue;
            }

            List<UUID> keptForeignHand = new ArrayList<>();
            List<UUID> pool = new ArrayList<>(libIds);
            int ownedHandCount = 0;
            for (UUID cardId : new ArrayList<>(player.getHand())) {
                Card card = copy.getCard(cardId);
                if (card != null && card.isOwnedBy(playerId)) {
                    pool.add(cardId);
                    ownedHandCount++;
                } else {
                    keptForeignHand.add(cardId);
                }
            }
            shuffleList(pool, rng);

            player.getHand().clear();
            for (UUID foreignId : keptForeignHand) {
                player.getHand().add(foreignId);
            }
            for (int index = 0; index < ownedHandCount; index++) {
                UUID drawnId = pool.get(index);
                Card card = copy.getCard(drawnId);
                if (card != null) {
                    card.setZone(Zone.HAND, copy);
                    player.getHand().add(card);
                }
            }
            List<UUID> remainingHiddenLib = pool.subList(ownedHandCount, pool.size());
            rebuildLibrary(copy, player, pinnedTop, remainingHiddenLib);
        }
    }

    private static void shuffleList(List<UUID> items, Random rng) {
        for (int index = items.size() - 1; index > 0; index--) {
            int pick = rng.nextInt(index + 1);
            UUID swap = items.get(index);
            items.set(index, items.get(pick));
            items.set(pick, swap);
        }
    }

    private static void rebuildLibrary(Game copy, Player player, Card pinnedTop, List<UUID> hiddenIds) {
        player.getLibrary().clear();
        if (pinnedTop != null) {
            player.getLibrary().putOnBottom(pinnedTop, copy);
        }
        for (UUID cardId : hiddenIds) {
            Card card = copy.getCard(cardId);
            if (card != null) {
                player.getLibrary().putOnBottom(card, copy);
            }
        }
    }

    private static CandidateSignature extractCandidateSignature(
            JsonObject pending,
            String candidateOptionId
    ) {
        if (candidateOptionId == null || candidateOptionId.isBlank()) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "PILOT_RESPONSE_INVALID: candidate_option_id must be nonblank"
            );
        }
        JsonArray options = pending.getAsJsonArray("legal_options");
        if (options == null || options.isEmpty()) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "LOOKAHEAD_CANDIDATE_UNAVAILABLE: pending decision has no legal_options"
            );
        }
        String targetType = null;
        String targetLabel = null;
        int occurrence = 0;
        for (JsonElement element : options) {
            JsonObject option = element.getAsJsonObject();
            String id = strictString(option, "option_id");
            if (candidateOptionId.equals(id)) {
                targetType = strictString(option, "option_type");
                targetLabel = strictString(option, "label");
                break;
            }
        }
        if (targetType == null) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "ILLEGAL_ACTION: candidate_option_id is not offered by real pending decision: "
                            + candidateOptionId
            );
        }
        for (JsonElement element : options) {
            JsonObject option = element.getAsJsonObject();
            String id = strictString(option, "option_id");
            if (candidateOptionId.equals(id)) {
                break;
            }
            if (Objects.equals(targetType, strictString(option, "option_type"))
                    && Objects.equals(targetLabel, strictString(option, "label"))) {
                occurrence++;
            }
        }
        return new CandidateSignature(candidateOptionId, targetType, targetLabel, occurrence);
    }

    private static String matchCandidateOptionId(
            JsonObject probePending,
            CandidateSignature signature
    ) {
        JsonArray options = probePending.getAsJsonArray("legal_options");
        if (options == null || options.isEmpty()) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "LOOKAHEAD_CANDIDATE_UNAVAILABLE: probe pending priority has no legal_options"
            );
        }
        for (JsonElement element : options) {
            JsonObject option = element.getAsJsonObject();
            String id = strictString(option, "option_id");
            if (signature.optionId().equals(id)) {
                return id;
            }
        }
        int seen = 0;
        for (JsonElement element : options) {
            JsonObject option = element.getAsJsonObject();
            if (Objects.equals(signature.optionType(), strictString(option, "option_type"))
                    && Objects.equals(signature.label(), strictString(option, "label"))) {
                if (seen == signature.occurrence()) {
                    return strictString(option, "option_id");
                }
                seen++;
            }
        }
        throw new XmageFullGameDecisionController.DecisionException(
                "LOOKAHEAD_CANDIDATE_UNAVAILABLE: candidate '" + signature.label()
                        + "' (" + signature.optionType() + ") disappeared in copied game"
        );
    }

    private static String strictString(JsonObject object, String key) {
        if (object == null || !object.has(key) || object.get(key).isJsonNull()) {
            return "";
        }
        JsonElement element = object.get(key);
        return element.isJsonPrimitive() ? element.getAsString() : "";
    }

    private static String safeMessage(Throwable exc) {
        String message = exc.getMessage();
        return message == null || message.isBlank() ? exc.getClass().getName() : message;
    }
}
