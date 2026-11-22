package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.cards.Card;
import mage.cards.decks.Deck;
import mage.cards.decks.DeckCardInfo;
import mage.cards.decks.DeckCardLists;
import mage.cards.repository.CardInfo;
import mage.cards.repository.CardRepository;
import mage.constants.CommanderCardType;
import mage.constants.PhaseStep;
import mage.constants.TurnPhase;
import mage.constants.Zone;
import mage.game.GameCommanderImpl;
import mage.game.Game;
import mage.game.PutToBattlefieldInfo;
import mage.game.permanent.Permanent;
import mage.game.stack.Spell;
import mage.game.stack.StackObject;
import mage.players.Player;
import mage.watchers.common.CommanderInfoWatcher;
import mage.watchers.common.CommanderPlaysCountState;
import mage.watchers.common.CommanderPlaysCountWatcher;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.UUID;

/**
 * NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE for the engine bridge.
 *
 * <p>Translates an explicit requested starting state (frozen semantic fields:
 * players, commanders, public-zone objects, life, turn/phase/priority, seed)
 * into engine-native state through public engine APIs only, then validates
 * with engine-authoritative state-based actions plus layers and proves the
 * result with a strict native readback compared field-by-field against the
 * request. Anything outside the supported dimensions fails closed with a
 * coded reason before any game mutation.</p>
 *
 * <p>Placement uses the engine's own typed setup primitive ({@code Game.cheat}
 * with explicit card lists, the mechanism backing the engine's qualified
 * scenario setup) for silent assembly, plus normal game creation (validated
 * Commander scaffolding decks carrying the exact commanders plus
 * deterministic filler), {@code Player.initLife}, game-state turn/active
 * setters, and the engine's game-load restoration path for commander cast
 * counts ({@code CommanderPlaysCountWatcher.restoreStateForGameLoad}). No
 * reflection into privates, no fabricated history events, no outcome
 * injection, no legality bypass: post-placement {@code Game.applyEffects}
 * plus {@code Game.checkStateAndTriggered} run before any credit, and credit
 * requires an exact readback match.</p>
 *
 * <p>Scaffolding decks are harness construction vehicles, never fixture
 * content: requested non-commander objects are materialized as real cards
 * (existence enforced, Commander-legality validation intentionally not
 * applied to the materialization vehicle, which is never registered as a
 * game deck) and the compared set covers only requested objects plus
 * requested player/temporal fields. Library contents are unspecified
 * by construction and excluded from comparison.</p>
 *
 * <p>Supported dimensions (v2): zones command/battlefield/graveyard/exile
 * plus hand identity (see privacy contract below);
 * permanents owned and controlled by the same principal (setup attribution),
 * untapped, without counters or attachments; commander cast counts; genuine
 * commanders on the battlefield; life totals equal to each player's starting
 * life; turn-1 precombat-main arrival envelope with active/priority
 * binding; explicit Rules-seed binding; a record-declared already-fully-cast
 * stack spell (see {@link RequestedStackSpell}). Everything else (stack spells
 * without that declaration, library identity, revealed, facedown, attachments, counters, tapped
 * permanents, controller/owner divergence, commander damage, poison, other
 * temporal points) is rejected fail-closed. Control divergence is rejected
 * deliberately: the engine's layer application re-derives control from
 * owners plus continuous effects, so directly assigned control does not
 * survive engine operation (proven by probe) and is reachable compliantly
 * only by resolving real control-change effects (executor scope).</p>
 *
 * <p>Hand-identity privacy contract: restored hand cards are placed through
 * the engine's typed setup primitive and are readable engine-direct in this
 * class's readback (test-only, never pilot-facing). Pilot-facing observation
 * stays principal-scoped via {@code XmageFullGameStateRedactor}
 * (opponent hands remain counts-only); hand identity must never appear in
 * global observations, logs, error details, or digests exposed to wrong
 * principals. Honeycard adversarial tests prove non-leakage.</p>
 *
 * <p>The global {@code starting_state_injection_supported} capability stays
 * {@code false}; this class only advertises its explicit dimensions.</p>
 */
final class XmageNativeStateRestoration {

    /**
     * Whether a requested counter map places any counter. A kind requested with a
     * count of zero places none (a permanent has a counter only while its count is
     * at least one), so {"age": 0} is the same request as no counters and needs no
     * counter dimension. A count that is not a non-negative integer fails closed.
     */
    static boolean hasNonZeroCounter(JsonObject counters) {
        for (Map.Entry<String, JsonElement> entry : counters.entrySet()) {
            JsonElement count = entry.getValue();
            if (count == null || !count.isJsonPrimitive() || !count.getAsJsonPrimitive().isNumber()) {
                return true;
            }
            java.math.BigDecimal value = count.getAsBigDecimal();
            if (value.signum() != 0) {
                return true;
            }
        }
        return false;
    }

    /** Fail-closed rejection before any game mutation. */
    static final class RestorationException extends RuntimeException {
        RestorationException(String code, String detail) {
            super(code + ": " + detail);
        }
    }

    /**
     * The game's colorless basic land. Used only as the scaffolding filler for a
     * commander with a legitimately empty colored identity, so a colorless
     * Commander deck is never given a fabricated colored land.
     */
    static final String COLORLESS_BASIC_LAND = "Wastes";

    /** One requested object in a public zone. */
    record RequestedObject(
            String semanticId,
            String cardIdentity,
            String owner,
            String controller,
            Zone zone,
            boolean tapped,
            /**
             * The record's producing step id when the object's zone change is
             * caused by the engine's own scripted history (contract 1.0.26's
             * {@code produced_by_step}); {@code null} when the object is setup
             * state this lane places. A produced object is never topped up: the
             * engine's own zone change is the only source and a missing one is
             * an exact-comparison mismatch (fail closed), never a silent cheat.
             */
            String producedByStep
    ) {
        RequestedObject(
                String semanticId,
                String cardIdentity,
                String owner,
                String controller,
                Zone zone,
                boolean tapped
        ) {
            this(semanticId, cardIdentity, owner, controller, zone, tapped, null);
        }
    }

    /**
     * A stack spell the record itself declares as already fully cast.
     *
     * <p>Only a record with {@code execution_entry_mode NATIVE_STATE_LOAD} and
     * a {@code NATIVE_RESUME_WITH_FULLY_CAST_STACK_SPELL} native-procedure step
     * naming this object may request one, and its {@code stack_state} entry must
     * declare {@code cast_complete true}, {@code costs_paid true} and no
     * targets/modes. The engine then resumes the real card as a real stack
     * object; it never casts, pays, targets or chooses anything for it. This is
     * restoration of a declared already-cast object, never casting out of
     * timing.</p>
     */
    record RequestedStackSpell(
            String semanticId,
            String cardIdentity,
            String owner,
            String controller,
            Zone fromZone
    ) {
    }

    /**
     * One requested commander binding. {@code zone} is where the genuine commander
     * is requested (COMMAND or BATTLEFIELD); {@code semanticId} names the frozen
     * object that is this commander outside the command zone (null in the command
     * zone).
     */
    record RequestedCommander(
            String commanderId,
            String cardIdentity,
            String owner,
            int priorCasts,
            Zone zone,
            String semanticId
    ) {
        /** A commander requested in the command zone. */
        RequestedCommander(String commanderId, String cardIdentity, String owner, int priorCasts) {
            this(commanderId, cardIdentity, owner, priorCasts, Zone.COMMAND, null);
        }
    }

    /** One requested accumulated combat-damage edge for an exact Commander identity. */
    record RequestedCommanderDamage(
            String commanderId,
            String damagedPlayer,
            int combatDamage
    ) {
    }

    /** Requested player fields. */
    /**
     * One requested player. {@code startingLife} is the player's own recorded
     * starting life (CR 103.4): setup, set when the first turn begins. The
     * requested {@code life} is history: it is caused by the arrival and only
     * compared, never set (F-40).
     */
    record RequestedPlayer(String playerId, int seat, int life, int startingLife) {
        RequestedPlayer(String playerId, int seat, int life) {
            this(playerId, seat, life, life);
        }
    }

    /** Explicit restoration input. Seats are 1-indexed player ids P1..PN. */
    record Plan(
            String planId,
            int playerCount,
            long seed,
            List<RequestedPlayer> players,
            List<RequestedCommander> commanders,
            List<RequestedCommanderDamage> commanderDamage,
            List<RequestedObject> objects,
            int turnNumber,
            TurnPhase phase,
            PhaseStep step,
            String activePlayer,
            String priorityPlayer,
            Map<String, Map<String, Integer>> objectCounters,
            Map<String, Boolean> controlledSinceTurnBegan,
            Set<String> declaredAttackers,
            RequestedStackSpell resumeStackSpell
    ) {
        /**
         * Backward-compatible constructor for plans that resume no declared
         * already-cast stack spell.
         */
        Plan(
                String planId,
                int playerCount,
                long seed,
                List<RequestedPlayer> players,
                List<RequestedCommander> commanders,
                List<RequestedCommanderDamage> commanderDamage,
                List<RequestedObject> objects,
                int turnNumber,
                TurnPhase phase,
                PhaseStep step,
                String activePlayer,
                String priorityPlayer,
                Map<String, Map<String, Integer>> objectCounters,
                Map<String, Boolean> controlledSinceTurnBegan,
                Set<String> declaredAttackers
        ) {
            this(planId, playerCount, seed, players, commanders, commanderDamage, objects,
                    turnNumber, phase, step, activePlayer, priorityPlayer, objectCounters,
                    controlledSinceTurnBegan, declaredAttackers, null);
        }

        /**
         * Backward-compatible constructor for plans whose requested combat
         * declares no attacker.
         */
        Plan(
                String planId,
                int playerCount,
                long seed,
                List<RequestedPlayer> players,
                List<RequestedCommander> commanders,
                List<RequestedCommanderDamage> commanderDamage,
                List<RequestedObject> objects,
                int turnNumber,
                TurnPhase phase,
                PhaseStep step,
                String activePlayer,
                String priorityPlayer,
                Map<String, Map<String, Integer>> objectCounters,
                Map<String, Boolean> controlledSinceTurnBegan
        ) {
            this(planId, playerCount, seed, players, commanders, commanderDamage, objects,
                    turnNumber, phase, step, activePlayer, priorityPlayer, objectCounters,
                    controlledSinceTurnBegan, Set.of());
        }

        /** Backward-compatible constructor for plans with no control-history request. */
        Plan(
                String planId,
                int playerCount,
                long seed,
                List<RequestedPlayer> players,
                List<RequestedCommander> commanders,
                List<RequestedCommanderDamage> commanderDamage,
                List<RequestedObject> objects,
                int turnNumber,
                TurnPhase phase,
                PhaseStep step,
                String activePlayer,
                String priorityPlayer,
                Map<String, Map<String, Integer>> objectCounters
        ) {
            this(planId, playerCount, seed, players, commanders, commanderDamage, objects,
                    turnNumber, phase, step, activePlayer, priorityPlayer, objectCounters, Map.of());
        }

        /** Backward-compatible constructor for plans with no requested counters. */
        Plan(
                String planId,
                int playerCount,
                long seed,
                List<RequestedPlayer> players,
                List<RequestedCommander> commanders,
                List<RequestedCommanderDamage> commanderDamage,
                List<RequestedObject> objects,
                int turnNumber,
                TurnPhase phase,
                PhaseStep step,
                String activePlayer,
                String priorityPlayer
        ) {
            this(planId, playerCount, seed, players, commanders, commanderDamage, objects,
                    turnNumber, phase, step, activePlayer, priorityPlayer, Map.of());
        }

        /** Backward-compatible constructor for plans with no Commander-damage history. */
        Plan(
                String planId,
                int playerCount,
                long seed,
                List<RequestedPlayer> players,
                List<RequestedCommander> commanders,
                List<RequestedObject> objects,
                int turnNumber,
                TurnPhase phase,
                PhaseStep step,
                String activePlayer,
                String priorityPlayer
        ) {
            this(planId, playerCount, seed, players, commanders, List.of(), objects,
                    turnNumber, phase, step, activePlayer, priorityPlayer, Map.of());
        }
    }

    /** Field-level compare verdict with digests, never any hidden content. */
    record CompareVerdict(
            boolean match,
            List<String> mismatches,
            String requestedDigest,
            String constructedDigest
    ) {
    }

    private final Plan plan;
    private final Deck materializationVehicle;
    private final XmageLosslessHiddenPlan losslessHidden;
    private final Map<String, Set<UUID>> injectedHandIdsByPlayer = new HashMap<>();
    /**
     * Requested hand objects of a turn-2 checkpoint, placed at the checkpoint
     * instead of before the opening deal. Placing them earlier would add them
     * to P1's opening hand across the whole of turn 1 and force a cleanup
     * discard choice (CR 514.1) the record does not declare; the hand is
     * checkpoint state (like a requested library), so it is placed when the
     * engine stands at the checkpoint.
     */
    private final Map<String, List<Card>> deferredHandByPlayer = new HashMap<>();
    /**
     * Requested graveyard objects of a turn-2 checkpoint. The engine's own
     * turn 1 can already produce the recorded graveyard result (P1's cleanup
     * discard, CR 514.1, scripted by the record as one Mountain), so these are
     * not placed before the opening deal. At the checkpoint each requested
     * object is materialized only as far as the engine's own state does not
     * already contain a matching identity: the construction tops the zone up
     * to the record, it never duplicates an engine-performed zone change.
     */
    private final Map<String, List<Card>> deferredGraveyardByPlayer = new HashMap<>();
    /**
     * The deferred graveyard cards whose record object declares
     * {@code produced_by_step} (contract 1.0.26): their zone change is the
     * engine's own scripted history, so the checkpoint never tops them up. A
     * missing engine zone change stays missing and the exact comparison fails
     * the construction.
     */
    private final Set<UUID> producedByStepGraveyardCardIds = new HashSet<>();
    private final Map<String, UUID> injectedObjectIdsBySemanticId = new HashMap<>();
    private final Map<String, UUID> commanderObjectIdsBySemanticId = new HashMap<>();
    private boolean arrivalRestored;
    private boolean losslessLibrariesApplied;
    private boolean preStartApplied;
    /** The real card of the record's declared already-fully-cast stack spell. */
    private Card resumeSpellCard;
    private boolean resumeSpellResumed;
    /** Restored face-up permanents that enter when the first turn begins (CR 103.6). */
    private final List<String> firstTurnPlacedSemanticIds = new ArrayList<>();

    XmageNativeStateRestoration(Plan plan, Deck materializationVehicle) {
        this(plan, materializationVehicle, XmageLosslessHiddenPlan.EMPTY);
    }

    XmageNativeStateRestoration(
            Plan plan, Deck materializationVehicle, XmageLosslessHiddenPlan losslessHidden) {
        if (losslessHidden == null) {
            throw new RestorationException(
                    "INVALID_PLAN", "lossless hidden-state plan must not be null");
        }
        this.losslessHidden = losslessHidden;
        if (plan == null) {
            throw new RestorationException(
                    "INVALID_PLAN", "restoration plan must not be null");
        }
        if (materializationVehicle == null) {
            throw new RestorationException(
                    "INVALID_VEHICLE", "card materialization vehicle must not be null");
        }
        validatePlan(plan);
        this.plan = plan;
        this.materializationVehicle = materializationVehicle;
    }

    Plan plan() {
        return plan;
    }

    Deck materializationVehicleForTests() {
        return materializationVehicle;
    }

    Set<UUID> injectedHandIdsForTests(String playerId) {
        return Set.copyOf(injectedHandIdsByPlayer.getOrDefault(playerId, Set.of()));
    }

    /**
     * Native ids of the commanders requested outside the command zone, keyed by
     * their semantic object id. Bound before the game starts, so a pilot can
     * match the engine's offers before the first-turn setup moves them.
     */
    Map<String, UUID> commanderObjectIds() {
        return Map.copyOf(commanderObjectIdsBySemanticId);
    }

    /** The semantic id of a placed object or commander, or null for any other native id. */
    String semanticIdOf(UUID nativeId) {
        for (Map.Entry<String, UUID> entry : injectedObjectIdsBySemanticId.entrySet()) {
            if (entry.getValue().equals(nativeId)) {
                return entry.getKey();
            }
        }
        for (Map.Entry<String, UUID> entry : commanderObjectIdsBySemanticId.entrySet()) {
            if (entry.getValue().equals(nativeId)) {
                return entry.getKey();
            }
        }
        return null;
    }

    XmageLosslessHiddenPlan losslessHidden() {
        return losslessHidden;
    }

    /**
     * Reserves one materialization-vehicle card of the identity for a requested
     * object placed after arrival (a library object): a vehicle card the game
     * has not loaded yet, bound to the semantic id exactly once.
     */
    synchronized Card reserveVehicleCard(String semanticId, String cardIdentity, mage.game.Game game) {
        if (injectedObjectIdsBySemanticId.containsKey(semanticId)) {
            throw new RestorationException("DUPLICATE_SEMANTIC_OBJECT", semanticId);
        }
        Set<UUID> bound = new HashSet<>(injectedObjectIdsBySemanticId.values());
        for (Card card : materializationVehicle.getCards()) {
            if (cardIdentity.equals(card.getName())
                    && !bound.contains(card.getId())
                    && game.getCard(card.getId()) == null) {
                injectedObjectIdsBySemanticId.put(semanticId, card.getId());
                return card;
            }
        }
        throw new RestorationException("VEHICLE_SHORTAGE", "no unplaced vehicle card for " + semanticId);
    }

    /**
     * Engine-direct lossless hidden-state verification: the checks performed and
     * the mismatches found, coded, with no hidden identity.
     */
    XmageLosslessHiddenPlan.Verification losslessHiddenVerification(
            GameCommanderImpl game, Map<String, Player> playersByPid) {
        if (!losslessLibrariesApplied && requestsCheckpointState()) {
            // Before the checkpoint the requested libraries, tapped state and
            // counters are not placed yet. One coded mismatch, never per object:
            // naming a requested library object here would tell the requester
            // that such a hidden card was requested.
            return new XmageLosslessHiddenPlan.Verification(
                    List.of(), List.of("checkpoint_state: the requested checkpoint was not reached"));
        }
        XmageLosslessHiddenPlan.Verification hidden = losslessHidden.verify(game, playersByPid, this);
        XmageLosslessHiddenPlan.Verification permanents = checkpointPermanentVerification(game);
        List<String> checks = new ArrayList<>(hidden.checks());
        checks.addAll(permanents.checks());
        List<String> mismatches = new ArrayList<>(hidden.mismatches());
        mismatches.addAll(permanents.mismatches());
        return new XmageLosslessHiddenPlan.Verification(checks, mismatches);
    }

    UUID injectedObjectId(String semanticId) {
        UUID id = injectedObjectIdsBySemanticId.get(semanticId);
        if (id == null) {
            throw new RestorationException(
                    "UNKNOWN_SEMANTIC_OBJECT", String.valueOf(semanticId));
        }
        return id;
    }

    /**
     * Parses a frozen materialization record into a plan, rejecting every
     * unsupported dimension with a code. The caller supplies the Rules seed
     * explicitly (records bind it as SCENARIO_SEED or a manifest seed).
     */
    static Plan planFromFrozenRecord(JsonObject record, String planId, long seed) {
        String fixtureId = record.get("fixture_id").getAsString();
        // SLOT-04: only a record that states its hidden dimensions losslessly may
        // carry a face-down or library object; everything else fails closed below.
        XmageLosslessHiddenPlan lossless = XmageLosslessHiddenPlan.fromRecord(record);
        List<RequestedPlayer> players = new ArrayList<>();
        for (JsonElement element : record.getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            int poison = player.has("poison") && !player.get("poison").isJsonNull()
                    ? player.get("poison").getAsInt() : 0;
            if (poison != 0) {
                throw new RestorationException(
                        "UNSUPPORTED_POISON", fixtureId + " " + player.get("player_id").getAsString());
            }
            players.add(new RequestedPlayer(
                    player.get("player_id").getAsString(),
                    player.get("seat").getAsInt(),
                    player.get("life").getAsInt(),
                    player.has("starting_life") && !player.get("starting_life").isJsonNull()
                            ? player.get("starting_life").getAsInt() : 40));
        }
        JsonObject commanderState = record.getAsJsonObject("commander_state");
        List<RequestedCommander> commanders = new ArrayList<>();
        Map<String, String> commanderZoneById = new HashMap<>();
        for (JsonElement element : commanderState.getAsJsonArray("commanders")) {
            JsonObject commander = element.getAsJsonObject();
            String zoneName = commander.has("zone") && !commander.get("zone").isJsonNull()
                    ? commander.get("zone").getAsString() : "command";
            if (!"command".equals(zoneName) && !"battlefield".equals(zoneName)) {
                throw new RestorationException(
                        "UNSUPPORTED_COMMANDER_ZONE",
                        fixtureId + " " + commander.get("commander_id").getAsString() + " requests " + zoneName);
            }
            commanderZoneById.put(commander.get("commander_id").getAsString(), zoneName);
            commanders.add(new RequestedCommander(
                    commander.get("commander_id").getAsString(),
                    commander.get("card_identity").getAsString(),
                    commander.get("owner").getAsString(),
                    commander.get("prior_command_zone_cast_count").getAsInt(),
                    "battlefield".equals(zoneName) ? Zone.BATTLEFIELD : Zone.COMMAND,
                    null));
        }
        Set<String> commanderIds = new HashSet<>();
        for (RequestedCommander commander : commanders) {
            if (!commanderIds.add(commander.commanderId())) {
                throw new RestorationException(
                        "DUPLICATE_COMMANDER_ID", fixtureId + " " + commander.commanderId());
            }
        }
        List<RequestedCommanderDamage> commanderDamage = new ArrayList<>();
        if (commanderState.has("commander_damage_matrix")
                && !commanderState.get("commander_damage_matrix").isJsonNull()) {
            for (JsonElement element
                    : commanderState.getAsJsonArray("commander_damage_matrix")) {
                JsonObject edge = element.getAsJsonObject();
                commanderDamage.add(new RequestedCommanderDamage(
                        edge.get("source_commander_id").getAsString(),
                        edge.get("damaged_player").getAsString(),
                        edge.get("combat_damage").getAsInt()));
            }
        }
        if (commanderState.has("multiple_commander_relations")
                && !commanderState.get("multiple_commander_relations").isJsonNull()) {
            for (JsonElement element
                    : commanderState.getAsJsonArray("multiple_commander_relations")) {
                JsonObject relation = element.getAsJsonObject();
                if (!"Partner".equals(relation.get("relation").getAsString())) {
                    throw new RestorationException(
                            "UNSUPPORTED_COMMANDER_RELATIONS",
                            fixtureId + " " + relation.get("relation").getAsString());
                }
                for (JsonElement id : relation.getAsJsonArray("commander_ids")) {
                    if (!commanderIds.contains(id.getAsString())) {
                        throw new RestorationException(
                                "UNBOUND_COMMANDER_RELATION", fixtureId + " " + id.getAsString());
                    }
                }
            }
        }
        List<RequestedObject> objects = new ArrayList<>();
        Map<String, Map<String, Integer>> objectCounters = new TreeMap<>();
        Map<String, Boolean> controlledSinceTurnBegan = new TreeMap<>();
        RequestedStackSpell resumeStackSpell = declaredResumeStackSpell(record, fixtureId);
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            JsonObject object = element.getAsJsonObject();
            String semanticId = object.has("semantic_id") && !object.get("semantic_id").isJsonNull()
                    ? object.get("semantic_id").getAsString() : "?";
            if ("stack".equals(object.get("zone").getAsString())) {
                // The record's own declared already-fully-cast stack spell is
                // never a zone placement: it is resumed as a real stack object
                // at the record's checkpoint. Any other requested stack object
                // still fails closed.
                if (resumeStackSpell == null || !resumeStackSpell.semanticId().equals(semanticId)) {
                    throw new RestorationException(
                            "UNSUPPORTED_ZONE", fixtureId + " " + semanticId + " requests stack");
                }
                continue;
            }
            if (object.has("face_down") && !object.get("face_down").isJsonNull()
                    && object.get("face_down").getAsBoolean()
                    && !lossless.declaresFaceDown(semanticId)) {
                throw new RestorationException("UNSUPPORTED_FACEDOWN", fixtureId + " " + semanticId);
            }
            if (object.has("counters") && !object.get("counters").isJsonNull()
                    && hasNonZeroCounter(object.getAsJsonObject("counters"))) {
                // Checkpoint counters on a battlefield permanent, of a type this
                // lane restores; anything else still fails closed.
                if (!"battlefield".equals(object.get("zone").getAsString())
                        || (object.has("commander_id") && !object.get("commander_id").isJsonNull())) {
                    throw new RestorationException("UNSUPPORTED_COUNTERS", fixtureId + " " + semanticId);
                }
                Map<String, Integer> counts = new TreeMap<>();
                for (Map.Entry<String, JsonElement> counter
                        : object.getAsJsonObject("counters").entrySet()) {
                    int amount = counter.getValue().getAsInt();
                    if (amount < 0 || counterType(counter.getKey()) == null) {
                        throw new RestorationException(
                                "UNSUPPORTED_COUNTERS", fixtureId + " " + semanticId);
                    }
                    if (amount > 0) {
                        counts.put(counter.getKey(), amount);
                    }
                }
                objectCounters.put(semanticId, Map.copyOf(counts));
            }
            if (object.has("attachments") && !object.get("attachments").isJsonNull()
                    && !object.getAsJsonArray("attachments").isEmpty()) {
                throw new RestorationException("UNSUPPORTED_ATTACHMENTS", fixtureId + " " + semanticId);
            }
            // Whether a permanent has been under its controller's control since
            // that player's most recent turn began (CR 302.6) is history the
            // arrival causes; the request is never set, only verified at the
            // checkpoint (checkpointPermanentVerification).
            if (object.has("controlled_since_turn_began")
                    && !object.get("controlled_since_turn_began").isJsonNull()) {
                controlledSinceTurnBegan.put(
                        semanticId, object.get("controlled_since_turn_began").getAsBoolean());
            }
            // An attachment is history the Rules Core must cause (an equip
            // activation, an Aura resolving): this vehicle never places one, so a
            // requested attachment fails closed instead of being silently dropped.
            if (object.has("attached_to") && !object.get("attached_to").isJsonNull()) {
                throw new RestorationException("UNSUPPORTED_ATTACHMENTS", fixtureId + " " + semanticId);
            }
            String zoneName = object.get("zone").getAsString();
            String objectCommanderId = object.has("commander_id") && !object.get("commander_id").isJsonNull()
                    ? object.get("commander_id").getAsString() : null;
            if (objectCommanderId != null && !"command".equals(zoneName)) {
                // The genuine commander outside the command zone (F-38): never a generic
                // setup copy, which the engine would not treat as a commander.
                String cardIdentity = object.get("card_identity").getAsString();
                String owner = object.get("owner").getAsString();
                if (!owner.equals(object.get("controller").getAsString())) {
                    throw new RestorationException(
                            "UNSUPPORTED_CONTROL_DIVERGENCE", semanticId
                                    + "; control must equal ownership in v1 (engine layers re-derive"
                                    + " control; divergence needs resolved control-change effects)");
                }
                if (object.has("tapped") && !object.get("tapped").isJsonNull()
                        && object.get("tapped").getAsBoolean()) {
                    // Commander placement does not restore tapped state.
                    throw new RestorationException(
                            "UNSUPPORTED_COMMANDER_OBJECT_STATE", fixtureId + " " + semanticId);
                }
                if (!zoneName.equals(commanderZoneById.get(objectCommanderId))) {
                    throw new RestorationException(
                            "COMMANDER_ZONE_CONFLICT", fixtureId + " " + semanticId + " is in " + zoneName
                                    + " but " + objectCommanderId + " is requested in "
                                    + commanderZoneById.get(objectCommanderId));
                }
                for (int index = 0; index < commanders.size(); index++) {
                    RequestedCommander commander = commanders.get(index);
                    if (commander.commanderId().equals(objectCommanderId)) {
                        if (commander.semanticId() != null
                                || !commander.cardIdentity().equals(cardIdentity)
                                || !commander.owner().equals(owner)) {
                            throw new RestorationException(
                                    "COMMANDER_ZONE_CONFLICT", fixtureId + " " + semanticId
                                            + " does not bind 1:1 to " + objectCommanderId);
                        }
                        commanders.set(index, new RequestedCommander(commander.commanderId(),
                                commander.cardIdentity(), commander.owner(), commander.priorCasts(),
                                commander.zone(), semanticId));
                    }
                }
                continue;
            }
            if ("library".equals(zoneName) && lossless.declaresLibraryObject(semanticId)) {
                // Placed after the opening hands by the lossless plan, at its
                // declared position of a complete checkpoint library.
                continue;
            }
            if ("command".equals(zoneName)) {
                String commanderId = object.has("commander_id")
                        && !object.get("commander_id").isJsonNull()
                        ? object.get("commander_id").getAsString() : null;
                if (commanderId == null || !commanderIds.contains(commanderId)) {
                    throw new RestorationException(
                            "UNBOUND_COMMAND_OBJECT", fixtureId + " " + semanticId);
                }
                continue;
            }
            Zone zone = switch (zoneName) {
                case "battlefield" -> Zone.BATTLEFIELD;
                case "graveyard" -> Zone.GRAVEYARD;
                case "exile" -> Zone.EXILED;
                case "hand" -> Zone.HAND;
                default -> throw new RestorationException(
                        "UNSUPPORTED_ZONE", fixtureId + " " + semanticId + " requests " + zoneName);
            };
            boolean tapped = object.has("tapped") && !object.get("tapped").isJsonNull()
                    && object.get("tapped").getAsBoolean();
            String producedByStep = object.has("produced_by_step")
                    && !object.get("produced_by_step").isJsonNull()
                    ? object.get("produced_by_step").getAsString() : null;
            objects.add(new RequestedObject(
                    semanticId,
                    canonicalCardIdentity(object.get("card_identity").getAsString()),
                    object.get("owner").getAsString(),
                    object.get("controller").getAsString(),
                    zone,
                    tapped,
                    producedByStep));
        }
        for (RequestedCommander commander : commanders) {
            if (commander.zone() != Zone.COMMAND && commander.semanticId() == null) {
                throw new RestorationException(
                        "COMMANDER_OBJECT_MISSING", fixtureId + " " + commander.commanderId());
            }
        }
        JsonObject temporal = record.getAsJsonObject("temporal_state");
        int turnNumber = temporal.get("turn_number").getAsInt();
        TurnPhase phase = parsePhase(temporal.get("phase").getAsString(), fixtureId);
        PhaseStep step = parseStep(
                temporal.get("phase").getAsString(), temporal.get("step").getAsString(), fixtureId);
        return new Plan(
                planId,
                players.size(),
                seed,
                List.copyOf(players),
                List.copyOf(commanders),
                List.copyOf(commanderDamage),
                List.copyOf(objects),
                turnNumber,
                phase,
                step,
                temporal.get("active_player").getAsString(),
                temporal.get("priority_player").getAsString(),
                Map.copyOf(objectCounters),
                Map.copyOf(controlledSinceTurnBegan),
                declaredAttackers(record),
                resumeStackSpell);
    }

    /**
     * The creatures the record's requested combat declares as attackers. Their
     * requested tapped state is caused by that declaration (CR 508.1f), so it
     * is verified at the checkpoint and never set.
     */
    static Set<String> declaredAttackers(JsonObject record) {
        if (!record.has("combat_state") || !record.get("combat_state").isJsonObject()) {
            return Set.of();
        }
        JsonObject combat = record.getAsJsonObject("combat_state");
        if (!combat.has("attackers") || !combat.get("attackers").isJsonObject()) {
            return Set.of();
        }
        return Set.copyOf(combat.getAsJsonObject("attackers").keySet());
    }

    /**
     * The record's own declared already-fully-cast stack spell, or null.
     *
     * <p>Only {@code execution_entry_mode NATIVE_STATE_LOAD} with exactly one
     * {@code NATIVE_RESUME_WITH_FULLY_CAST_STACK_SPELL} step naming a requested
     * stack object qualifies; the step's {@code source_object} must bind 1:1 to
     * a {@code stack} semantic object and to a {@code stack_state} entry that
     * declares {@code cast_complete true}, {@code costs_paid true}, a
     * controller equal to the object's, and no targets or modes. Any
     * declaration that does not hold returns null here, and the requested stack
     * object is then refused by the zone placement exactly as before; the
     * bridge never guesses at a partially declared construction.</p>
     */
    static RequestedStackSpell declaredResumeStackSpell(JsonObject record, String fixtureId) {
        String entryMode = record.has("execution_entry_mode")
                && !record.get("execution_entry_mode").isJsonNull()
                ? record.get("execution_entry_mode").getAsString() : "";
        String resumeSource = null;
        if (record.has("native_procedure") && record.get("native_procedure").isJsonArray()) {
            for (JsonElement element : record.getAsJsonArray("native_procedure")) {
                JsonObject step = element.getAsJsonObject();
                if (!step.has("operation") || step.get("operation").isJsonNull()
                        || !"NATIVE_RESUME_WITH_FULLY_CAST_STACK_SPELL".equals(
                                step.get("operation").getAsString())) {
                    continue;
                }
                if (resumeSource != null) {
                    throw new RestorationException(
                            "DUPLICATE_RESUME_STACK_SPELL", fixtureId);
                }
                resumeSource = step.has("source_object") && !step.get("source_object").isJsonNull()
                        ? step.get("source_object").getAsString() : null;
            }
        }
        if (resumeSource == null) {
            // A record that declares no resume step is an ordinary placement
            // record regardless of its entry-mode label.
            return null;
        }
        if (!"NATIVE_STATE_LOAD".equals(entryMode)) {
            // The declaration belongs to another construction route (the causal
            // pre-stack record is rewritten and holds no stack state); it is
            // not this route's to honor.
            return null;
        }
        // The resume step only binds a genuine construction when its source is
        // a requested stack-zone semantic object. The causal pre-stack rewrite
        // keeps the step but rewrites the source out of the stack zone and
        // empties stack_state; that record is not this route's and falls
        // through to the causal pre-stack placement exactly as before.
        JsonObject requested = null;
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            JsonObject object = element.getAsJsonObject();
            if (object.has("semantic_id") && !object.get("semantic_id").isJsonNull()
                    && resumeSource.equals(object.get("semantic_id").getAsString())) {
                requested = object;
                break;
            }
        }
        if (requested == null || !"stack".equals(requested.get("zone").getAsString())) {
            return null;
        }
        if (!record.has("stack_state") || !record.get("stack_state").isJsonArray()) {
            return null;
        }
        JsonArray stackState = record.getAsJsonArray("stack_state");
        if (stackState.size() != 1) {
            // One resumed spell is exactly one stack_state entry. A second
            // entry (a waiting trigger, a second spell) is a different
            // construction this route never fabricates.
            throw new RestorationException(
                    "UNSUPPORTED_RESUME_STACK_AMBIGUITY",
                    fixtureId + " declares " + stackState.size()
                            + " stack_state entries for one resumed spell");
        }
        int stackObjects = 0;
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            if ("stack".equals(element.getAsJsonObject().get("zone").getAsString())) {
                stackObjects++;
            }
        }
        if (stackObjects != 1) {
            // The route resumes exactly the one declared stack object; any
            // other stack-zone semantic object (a second spell or trigger)
            // is refused instead of being silently dropped from the plan.
            throw new RestorationException(
                    "UNSUPPORTED_RESUME_STACK_AMBIGUITY",
                    fixtureId + " declares " + stackObjects + " stack-zone semantic objects"
                            + " for one resumed spell");
        }
        JsonObject declared = null;
        for (JsonElement element : stackState) {
            JsonObject frame = element.getAsJsonObject();
            if (frame.has("source_semantic_id") && !frame.get("source_semantic_id").isJsonNull()
                    && resumeSource.equals(frame.get("source_semantic_id").getAsString())) {
                declared = frame;
                break;
            }
        }
        if (declared == null) {
            return null;
        }
        if (!declared.has("cast_complete") || declared.get("cast_complete").isJsonNull()
                || !declared.get("cast_complete").getAsBoolean()) {
            return null;
        }
        if (!declared.has("costs_paid") || declared.get("costs_paid").isJsonNull()
                || !declared.get("costs_paid").getAsBoolean()) {
            return null;
        }
        if (declared.has("targets") && !declared.get("targets").isJsonNull()
                && !declared.getAsJsonArray("targets").isEmpty()) {
            // A targeted stack spell needs its declared targets restored; this
            // route supports only the no-target declaration and the stack
            // object stays refused by the zone placement below.
            return null;
        }
        if (declared.has("modes") && !declared.get("modes").isJsonNull()
                && !declared.getAsJsonArray("modes").isEmpty()) {
            return null;
        }
        String controller = requested.get("controller").getAsString();
        if (!declared.has("controller") || declared.get("controller").isJsonNull()
                || !controller.equals(declared.get("controller").getAsString())) {
            return null;
        }
        // The record's own declared cast-from zone, or null when it declares
        // none. There is deliberately no default: the resume refuses an
        // undeclared zone (CR 601.2a provenance is record content, never
        // invented by the bridge).
        Zone fromZone = null;
        if (declared.has("from_zone") && !declared.get("from_zone").isJsonNull()) {
            String zoneName = declared.get("from_zone").getAsString().trim();
            try {
                fromZone = Zone.valueOf(zoneName.toUpperCase(java.util.Locale.ROOT));
            } catch (IllegalArgumentException unknownZone) {
                throw new RestorationException(
                        "UNSUPPORTED_RESUME_CAST_ZONE",
                        fixtureId + " " + resumeSource + " from_zone " + zoneName);
            }
            if (fromZone == Zone.STACK) {
                throw new RestorationException(
                        "UNSUPPORTED_RESUME_CAST_ZONE",
                        fixtureId + " " + resumeSource + " declares no cast-from zone but stack");
            }
        }
        return new RequestedStackSpell(
                resumeSource,
                requested.get("card_identity").getAsString(),
                requested.get("owner").getAsString(),
                controller,
                fromZone);
    }

    /**
     * The engine's name for a requested card identity. A transforming
     * double-faced card is requested as "Front // Back" but is the card named
     * after its front face; it resolves to that name only when the engine card
     * of that front name has exactly that back face. A split card keeps its
     * full "A // B" name, which is the engine's own. Anything else is returned
     * unchanged and fails closed at vehicle construction as before.
     */
    static String canonicalCardIdentity(String identity) {
        if (identity == null || !identity.contains(" // ")) {
            return identity;
        }
        // The repository must be loaded before it is asked: on a fresh runtime
        // directory (every CI runner) an unloaded repository answers nothing,
        // and the name would fall through unresolved and be refused later.
        XmageDeckImporter.ensureRepositoryReady();
        CardInfo whole = CardRepository.instance.findCard(identity.trim(), true);
        if (whole != null && identity.trim().equals(whole.getName())) {
            return identity;
        }
        String[] faces = identity.split(" // ", 2);
        CardInfo front = CardRepository.instance.findCard(faces[0].trim(), true);
        if (front != null && faces[0].trim().equals(front.getName())
                && faces[1].trim().equals(front.getSecondSideName())) {
            return front.getName();
        }
        return identity;
    }

    /** The native counter type a record counter name restores, or null. */
    /** Evergreen keyword abilities the readback reports, by rules name. */
    static final Map<String, Class<? extends Ability>> KEYWORDS = keywordClasses();

    private static Map<String, Class<? extends Ability>> keywordClasses() {
        Map<String, Class<? extends Ability>> keywords = new TreeMap<>();
        keywords.put("deathtouch", mage.abilities.keyword.DeathtouchAbility.class);
        keywords.put("double strike", mage.abilities.keyword.DoubleStrikeAbility.class);
        keywords.put("first strike", mage.abilities.keyword.FirstStrikeAbility.class);
        keywords.put("flying", mage.abilities.keyword.FlyingAbility.class);
        keywords.put("haste", mage.abilities.keyword.HasteAbility.class);
        keywords.put("hexproof", mage.abilities.keyword.HexproofAbility.class);
        keywords.put("indestructible", mage.abilities.keyword.IndestructibleAbility.class);
        keywords.put("lifelink", mage.abilities.keyword.LifelinkAbility.class);
        keywords.put("menace", mage.abilities.keyword.MenaceAbility.class);
        keywords.put("reach", mage.abilities.keyword.ReachAbility.class);
        keywords.put("trample", mage.abilities.keyword.TrampleAbility.class);
        keywords.put("vigilance", mage.abilities.keyword.VigilanceAbility.class);
        return Collections.unmodifiableMap(keywords);
    }

    /** The checkpoint counter a planeswalker carries; set as it enters. */
    static final String LOYALTY = "loyalty";

    static mage.counters.CounterType counterType(String name) {
        return switch (name) {
            case "+1/+1" -> mage.counters.CounterType.P1P1;
            case "-1/-1" -> mage.counters.CounterType.M1M1;
            case LOYALTY -> mage.counters.CounterType.LOYALTY;
            default -> null;
        };
    }

    private static TurnPhase parsePhase(String phase, String fixtureId) {
        return switch (phase) {
            case "precombat_main" -> TurnPhase.PRECOMBAT_MAIN;
            case "combat" -> TurnPhase.COMBAT;
            case "postcombat_main" -> TurnPhase.POSTCOMBAT_MAIN;
            case "beginning" -> TurnPhase.BEGINNING;
            case "end" -> TurnPhase.END;
            default -> throw new RestorationException("UNSUPPORTED_PHASE", fixtureId + " " + phase);
        };
    }

    private static PhaseStep parseStep(String phase, String step, String fixtureId) {
        if ("beginning".equals(phase) && "upkeep".equals(step)) {
            return PhaseStep.UPKEEP;
        }
        if ("beginning".equals(phase) && "draw".equals(step)) {
            return PhaseStep.DRAW;
        }
        if ("precombat_main".equals(phase) && "main".equals(step)) {
            return PhaseStep.PRECOMBAT_MAIN;
        }
        if ("combat".equals(phase) && "declare_attackers".equals(step)) {
            return PhaseStep.DECLARE_ATTACKERS;
        }
        if ("combat".equals(phase) && "declare_blockers".equals(step)) {
            return PhaseStep.DECLARE_BLOCKERS;
        }
        if ("combat".equals(phase) && "combat_damage".equals(step)) {
            return PhaseStep.COMBAT_DAMAGE;
        }
        if ("postcombat_main".equals(phase) && "main".equals(step)) {
            return PhaseStep.POSTCOMBAT_MAIN;
        }
        throw new RestorationException(
                "UNSUPPORTED_STEP", fixtureId + " " + phase + "/" + step);
    }

    /**
     * Builds a real-card materialization vehicle for requested non-commander
     * cards. Existence in the engine card repository is enforced;
     * Commander-legality validation is intentionally not applied (the vehicle
     * is never registered as a game deck, only disassembled for setup lists).
     */
    static Deck materializeCards(List<String> cardIdentities) {
        XmageDeckImporter.ensureRepositoryReady();
        DeckCardLists lists = new DeckCardLists();
        lists.setName("native-state-restoration-vehicle");
        for (String identity : cardIdentities) {
            if (identity == null || identity.isBlank()) {
                throw new RestorationException(
                        "INVALID_CARD_IDENTITY", "requested card identity must be nonblank");
            }
            CardInfo info = CardRepository.instance.findCard(identity.trim(), true);
            if (info == null) {
                throw new RestorationException("UNKNOWN_CARD_NAME", identity);
            }
            if (!identity.trim().equals(info.getName())) {
                throw new RestorationException(
                        "CARD_IDENTITY_MISMATCH",
                        "requested " + identity + " but engine resolved " + info.getName());
            }
            lists.getCards().add(new DeckCardInfo(
                    info.getName(), info.getCardNumber(), info.getSetCode()));
        }
        try {
            Deck vehicle = Deck.load(lists, false, false);
            if (vehicle == null) {
                throw new RestorationException("VEHICLE_LOAD_FAILED", "Deck.load returned null");
            }
            return vehicle;
        } catch (RestorationException exc) {
            throw exc;
        } catch (Exception exc) {
            throw new RestorationException("VEHICLE_LOAD_FAILED", String.valueOf(exc.getMessage()));
        }
    }

    /**
     * Deterministic scaffolding filler basics for a commander color set.
     * Scaffolding decks go through the full real-cards-only Commander import
     * (existence plus Commander legality enforced there).
     *
     * <p>A colorless commander legitimately has no colored component in its
     * color identity ({@code CardInfo.getColor()} is empty), so the filler for
     * it must be a colorless basic land rather than a fabricated colored one.
     * {@code Wastes} is the game's colorless basic land; it goes through the
     * same real-cards-only Commander import as every other filler, so its
     * existence and legality are still decided by the engine. Rejecting the
     * empty color set here would make an otherwise supported colorless
     * Commander starting state unreachable.</p>
     */
    static List<String> scaffoldingFiller(int count, Set<String> commanderColors) {
        Map<String, String> colorToBasic = Map.of(
                "W", "Plains", "U", "Island", "B", "Swamp", "R", "Mountain", "G", "Forest");
        List<String> pool = new ArrayList<>();
        for (String color : List.of("W", "U", "B", "R", "G")) {
            if (commanderColors.contains(color)) {
                pool.add(colorToBasic.get(color));
            }
        }
        if (pool.isEmpty()) {
            pool.add(COLORLESS_BASIC_LAND);
        }
        List<String> filler = new ArrayList<>(count);
        for (int index = 0; index < count; index++) {
            filler.add(pool.get(index % pool.size()));
        }
        return List.copyOf(filler);
    }

    /**
     * Temporal targets qualified for native progression. This is only an
     * allow-list for a requested checkpoint; it never assigns phase/step/turn
     * fields. XmageTemporalProgressionDriver must reach the target through the
     * running engine and explicit external decisions.
     */
    static boolean isSupportedTemporalPoint(Plan validated) {
        if (validated.turnNumber() != 1) {
            // Turn 2 (#441 NEGATIVE_PARENT_CLASS_FALLBACK erratum, contract
            // 1.0.24): the record declares P2 active in P2's own turn-2
            // precombat main with P2 holding priority, after the engine's own
            // turn 1 (P1) and P2's untap/upkeep/draw. The natural turn order
            // reaches it with P1 as the starting player; only the declared
            // precombat main is qualified, so a turn-3 request still fails
            // closed with UNSUPPORTED_TEMPORAL_POINT.
            return validated.turnNumber() == 2
                    && validated.phase() == TurnPhase.PRECOMBAT_MAIN
                    && validated.step() == PhaseStep.PRECOMBAT_MAIN;
        }
        return (validated.phase() == TurnPhase.BEGINNING
                        && (validated.step() == PhaseStep.UPKEEP
                                || validated.step() == PhaseStep.DRAW))
                || (validated.phase() == TurnPhase.PRECOMBAT_MAIN
                        && validated.step() == PhaseStep.PRECOMBAT_MAIN)
                || (validated.phase() == TurnPhase.COMBAT
                        && (validated.step() == PhaseStep.DECLARE_ATTACKERS
                                || validated.step() == PhaseStep.DECLARE_BLOCKERS
                                || validated.step() == PhaseStep.COMBAT_DAMAGE))
                || (validated.phase() == TurnPhase.POSTCOMBAT_MAIN
                        && validated.step() == PhaseStep.POSTCOMBAT_MAIN);
    }

    /** Validates the whole plan before any game mutation. */
    static void validatePlan(Plan validated) {
        if (validated.playerCount() < XmageFullGameSession.MIN_PLAYERS
                || validated.playerCount() > XmageFullGameSession.MAX_PLAYERS) {
            throw new RestorationException(
                    "UNSUPPORTED_PLAYER_COUNT", String.valueOf(validated.playerCount()));
        }
        if (validated.players().size() != validated.playerCount()) {
            throw new RestorationException(
                    "PLAYER_COUNT_MISMATCH", "players list must cover every seat");
        }
        Set<String> seats = new HashSet<>();
        for (RequestedPlayer player : validated.players()) {
            if (!seats.add(player.playerId())) {
                throw new RestorationException("DUPLICATE_PLAYER", player.playerId());
            }
            if (player.life() < 0) {
                throw new RestorationException(
                        "UNSUPPORTED_LIFE", player.playerId() + "=" + player.life());
            }
        }
        if (!isSupportedTemporalPoint(validated)) {
            throw new RestorationException(
                    "UNSUPPORTED_TEMPORAL_POINT",
                    "RG-03 supports qualified turn-1 checkpoints and the turn-2 precombat"
                            + " main; requested " + validated.turnNumber() + "/"
                            + validated.phase() + "/" + validated.step());
        }
        if (!seats.contains(validated.activePlayer())
                || !seats.contains(validated.priorityPlayer())) {
            throw new RestorationException(
                    "UNKNOWN_ACTOR", "active/priority must name a planned player");
        }
        Set<String> objectIds = new HashSet<>();
        for (RequestedObject object : validated.objects()) {
            if (object.semanticId() == null || object.semanticId().isBlank()) {
                throw new RestorationException("INVALID_SEMANTIC_OBJECT", "blank semantic id");
            }
            if (!objectIds.add(object.semanticId())) {
                throw new RestorationException("DUPLICATE_SEMANTIC_OBJECT", object.semanticId());
            }
            switch (object.zone()) {
                case BATTLEFIELD, GRAVEYARD, EXILED, HAND -> {
                }
                default -> throw new RestorationException(
                        "UNSUPPORTED_ZONE",
                        object.semanticId() + " requests " + object.zone());
            }
            if (!seats.contains(object.owner()) || !seats.contains(object.controller())) {
                throw new RestorationException(
                        "UNKNOWN_ACTOR", "object owner/controller must name a planned player");
            }
            if (!object.owner().equals(object.controller())) {
                throw new RestorationException(
                        "UNSUPPORTED_CONTROL_DIVERGENCE",
                        object.semanticId() + "; control must equal ownership in v1"
                                + " (engine layers re-derive control; divergence needs"
                                + " resolved control-change effects)");
            }
            if (object.tapped() && object.zone() != Zone.BATTLEFIELD) {
                throw new RestorationException(
                        "UNSUPPORTED_TAPPED", object.semanticId() + "; only a permanent can be tapped");
            }
            if (object.cardIdentity() == null || object.cardIdentity().isBlank()) {
                throw new RestorationException("INVALID_CARD_IDENTITY", object.semanticId());
            }
        }
        RequestedStackSpell resume = validated.resumeStackSpell();
        if (resume != null) {
            if (!seats.contains(resume.owner()) || !seats.contains(resume.controller())) {
                throw new RestorationException(
                        "UNKNOWN_ACTOR", "resume spell owner/controller must name a planned player");
            }
            if (!resume.owner().equals(resume.controller())) {
                throw new RestorationException(
                        "UNSUPPORTED_CONTROL_DIVERGENCE",
                        resume.semanticId() + "; the resumed spell's control must equal ownership"
                                + " in v1 (engine layers re-derive control)");
            }
            if (resume.cardIdentity() == null || resume.cardIdentity().isBlank()) {
                throw new RestorationException("INVALID_CARD_IDENTITY", resume.semanticId());
            }
        }
        Set<String> commanderIds = new HashSet<>();
        for (RequestedCommander commander : validated.commanders()) {
            if (commander.commanderId() == null || commander.commanderId().isBlank()) {
                throw new RestorationException("INVALID_COMMANDER_ID", "blank commander id");
            }
            if (!commanderIds.add(commander.commanderId())) {
                throw new RestorationException("DUPLICATE_COMMANDER_ID", commander.commanderId());
            }
            if (!seats.contains(commander.owner())) {
                throw new RestorationException(
                        "UNKNOWN_ACTOR", "commander owner must name a planned player");
            }
            if (commander.priorCasts() < 0) {
                throw new RestorationException("UNSUPPORTED_CAST_COUNT", commander.commanderId());
            }
            if (commander.cardIdentity() == null || commander.cardIdentity().isBlank()) {
                throw new RestorationException("INVALID_CARD_IDENTITY", commander.commanderId());
            }
        }
        if (validated.commanderDamage() == null) {
            throw new RestorationException(
                    "INVALID_DAMAGE_MATRIX", "Commander damage matrix must not be null");
        }
        Set<String> damageEdges = new HashSet<>();
        for (RequestedCommanderDamage edge : validated.commanderDamage()) {
            if (edge == null || edge.commanderId() == null || edge.commanderId().isBlank()) {
                throw new RestorationException("INVALID_DAMAGE_MATRIX", "blank Commander identity");
            }
            if (!commanderIds.contains(edge.commanderId())) {
                throw new RestorationException(
                        "UNKNOWN_COMMANDER_ID", String.valueOf(edge.commanderId()));
            }
            if (edge.damagedPlayer() == null || !seats.contains(edge.damagedPlayer())) {
                throw new RestorationException(
                        "UNKNOWN_ACTOR", String.valueOf(edge.damagedPlayer()));
            }
            if (edge.combatDamage() < 0) {
                throw new RestorationException(
                        "INVALID_COMMANDER_DAMAGE",
                        edge.commanderId() + " -> " + edge.damagedPlayer()
                                + "=" + edge.combatDamage());
            }
            String key = edge.commanderId() + "|" + edge.damagedPlayer();
            if (!damageEdges.add(key)) {
                throw new RestorationException("DUPLICATE_DAMAGE_EDGE", key);
            }
        }
    }

    /**
     * Pre-start assembly in the constructing thread (engine not running):
     * silent setup placement via the engine's typed setup primitive (setup
     * attribution makes owners controllers) and watcher registration. Face-up
     * permanents are loaded here and enter when the first turn begins, where a
     * recorded starting life is also set ({@link XmageFirstTurnSetupWatcher}):
     * the battlefield is empty during the start-of-game procedure (CR 103), so
     * a restored permanent never observes the vehicle's opening-hand draws or
     * mulligans.
     * A commander requested on the battlefield leaves the command zone at the
     * same first-turn point. Commander cast counts are restored post-arrival
     * ({@link #restoreAfterArrival}), once game start has created the
     * commanders.
     */
    synchronized void applyPreStart(
            GameCommanderImpl game, Map<String, Player> playersByPid) {
        if (preStartApplied) {
            throw new RestorationException(
                    "ALREADY_APPLIED", "pre-start restoration runs exactly once");
        }
        prebindCommanderObjects(game, playersByPid);
        Map<String, List<Card>> vehicleByName = new HashMap<>();
        for (Card card : materializationVehicle.getCards()) {
            vehicleByName.computeIfAbsent(card.getName(), name -> new ArrayList<>()).add(card);
        }
        Set<Card> consumed = new HashSet<>();
        List<UUID> deferredCardIds = new ArrayList<>();
        List<UUID> deferredOwnerIds = new ArrayList<>();
        List<Integer> deferredLoyalties = new ArrayList<>();
        for (RequestedPlayer requested : plan.players()) {
            Player player = requirePlayer(playersByPid, requested.playerId());
            List<PutToBattlefieldInfo> battlefield = new ArrayList<>();
            List<Card> deferred = new ArrayList<>();
            List<Card> hand = new ArrayList<>();
            List<Card> graveyard = new ArrayList<>();
            List<Card> exile = new ArrayList<>();
            for (RequestedObject object : plan.objects()) {
                if (!object.owner().equals(requested.playerId())) {
                    continue;
                }
                Card card = takeVehicleCard(vehicleByName, consumed, object);
                if (injectedObjectIdsBySemanticId.put(object.semanticId(), card.getId()) != null) {
                    throw new RestorationException(
                            "DUPLICATE_SEMANTIC_OBJECT", object.semanticId());
                }
                switch (object.zone()) {
                    case BATTLEFIELD -> {
                        // A face-down object turns face down before game start
                        // (SLOT-04); a card whose battlefield side is another
                        // part or face would register new watchers while the
                        // engine iterates them, so it stays a setup placement.
                        Integer loyalty = plan.objectCounters()
                                .getOrDefault(object.semanticId(), Map.of()).get(LOYALTY);
                        if (!losslessHidden.declaresFaceDown(object.semanticId())
                                && XmageFirstTurnSetupWatcher.deferrable(game, card)) {
                            deferred.add(card);
                            deferredCardIds.add(card.getId());
                            deferredOwnerIds.add(player.getId());
                            deferredLoyalties.add(loyalty == null
                                    ? XmageFirstTurnSetupWatcher.NO_LOYALTY : loyalty);
                            firstTurnPlacedSemanticIds.add(object.semanticId());
                        } else if (loyalty != null) {
                            // Loyalty must be in place when the permanent enters,
                            // before the first state-based action check (CR
                            // 704.5i); only the first-turn placement does that.
                            throw new RestorationException(
                                    "UNSUPPORTED_COUNTERS", object.semanticId() + " loyalty");
                        } else {
                            battlefield.add(new PutToBattlefieldInfo(card, false));
                        }
                    }
                    case HAND -> {
                        if (plan.turnNumber() > 1) {
                            // Turn-2 checkpoint: the requested hand is
                            // checkpoint state, placed when the engine stands
                            // at the checkpoint (see deferredHandByPlayer).
                            deferredHandByPlayer
                                    .computeIfAbsent(requested.playerId(), ignored -> new ArrayList<>())
                                    .add(card);
                        } else {
                            hand.add(card);
                            injectedHandIdsByPlayer
                                    .computeIfAbsent(requested.playerId(), ignored -> new HashSet<>())
                                    .add(card.getId());
                        }
                    }
                    case GRAVEYARD -> {
                        if (plan.turnNumber() > 1) {
                            // Turn-2 checkpoint: the recorded graveyard is
                            // checkpoint state the engine's own turn 1 may
                            // already produce (the scripted cleanup discard);
                            // place only the shortfall at the checkpoint. An
                            // object the record marks with produced_by_step is
                            // never placed at all: only the engine's own zone
                            // change may satisfy it.
                            deferredGraveyardByPlayer
                                    .computeIfAbsent(requested.playerId(), ignored -> new ArrayList<>())
                                    .add(card);
                            if (object.producedByStep() != null) {
                                producedByStepGraveyardCardIds.add(card.getId());
                            }
                        } else {
                            graveyard.add(card);
                        }
                    }
                    case EXILED -> exile.add(card);
                    default -> throw new RestorationException(
                            "UNSUPPORTED_ZONE", object.semanticId());
                }
            }
            // Typed setup slots: library, hand, battlefield, graveyard,
            // command (always empty: commanders arrive via game creation),
            // exile. Verified against engine behavior; misplacement would
            // silently corrupt the restored state.
            game.cheat(player.getId(), List.of(), hand, battlefield, graveyard,
                    List.of(), exile);
            // Loaded outside the game (watchers registered), placed at turn 1.
            game.loadCards(new HashSet<>(deferred), player.getId());
            // Life is not set here: game start re-derives it (initLife). See
            // XmageFirstTurnSetupWatcher, which sets it when the first turn
            // begins (F-40).
        }
        if (plan.resumeStackSpell() != null) {
            // The record's declared already-fully-cast stack spell: materialize
            // its real card and register it with its controller as owner. The
            // stack object itself is resumed at the record's own checkpoint;
            // nothing is cast, paid, targeted or chosen here or there.
            Card card = takeVehicleCard(
                    vehicleByName,
                    consumed,
                    new RequestedObject(
                            plan.resumeStackSpell().semanticId(),
                            plan.resumeStackSpell().cardIdentity(),
                            plan.resumeStackSpell().owner(),
                            plan.resumeStackSpell().controller(),
                            Zone.BATTLEFIELD,
                            false));
            Player controller = requirePlayer(playersByPid, plan.resumeStackSpell().controller());
            if (injectedObjectIdsBySemanticId.put(
                    plan.resumeStackSpell().semanticId(), card.getId()) != null) {
                throw new RestorationException(
                        "DUPLICATE_SEMANTIC_OBJECT", plan.resumeStackSpell().semanticId());
            }
            game.loadCards(new HashSet<>(List.of(card)), controller.getId());
            resumeSpellCard = card;
        }
        // SLOT-04: the typed face-down object turns face down here, before game
        // start and before the public event tape exists, so no observation
        // ever shows it face up.
        losslessHidden.applyPreStart(game, this);
        List<UUID> lifePlayerIds = new ArrayList<>();
        List<Integer> startingLives = new ArrayList<>();
        for (RequestedPlayer requested : plan.players()) {
            if (requested.startingLife() != game.getStartingLife()) {
                lifePlayerIds.add(requirePlayer(playersByPid, requested.playerId()).getId());
                startingLives.add(requested.startingLife());
            }
        }
        // A commander requested on the battlefield leaves the command zone when
        // the first turn begins, like every other restored permanent.
        List<UUID> commanderIds = new ArrayList<>();
        List<UUID> commanderOwnerIds = new ArrayList<>();
        for (RequestedCommander requested : plan.commanders()) {
            if (requested.zone() == Zone.BATTLEFIELD) {
                UUID commanderId = commanderObjectIdsBySemanticId.get(requested.semanticId());
                Card commander = game.getCard(commanderId);
                if (commander == null || !XmageFirstTurnSetupWatcher.deferrable(game, commander)) {
                    // A commander whose battlefield permanent is another face or
                    // part (a modal double-faced or transforming card) cannot
                    // enter through the first-turn setup; refused before game
                    // start rather than half-moved inside the engine's turn.
                    throw new RestorationException(
                            "UNSUPPORTED_COMMANDER_FACE", requested.commanderId());
                }
                commanderIds.add(commanderId);
                commanderOwnerIds.add(requirePlayer(playersByPid, requested.owner()).getId());
                firstTurnPlacedSemanticIds.add(requested.semanticId());
            }
        }
        if (!deferredCardIds.isEmpty() || !commanderIds.isEmpty() || !lifePlayerIds.isEmpty()) {
            game.getState().addWatcher(new XmageFirstTurnSetupWatcher(
                    deferredCardIds, deferredOwnerIds, deferredLoyalties, commanderIds,
                    commanderOwnerIds, lifePlayerIds, startingLives));
        }
        game.getState().addWatcher(new CommanderPlaysCountWatcher());
        // After placement: the public event tape starts with the game, not the setup.
        game.getState().addWatcher(new XmagePublicEventWatcher());
        preStartApplied = true;
    }

    /**
     * Post-arrival commander cast-count restoration through the engine's own
     * game-load path, keyed by live command-zone commander UUIDs mapped 1:1
     * via owner plus card identity (fail closed on ambiguity). Runs while the
     * engine thread is parked on an external decision.
     */
    synchronized void restoreAfterArrival(
            GameCommanderImpl game, Map<String, Player> playersByPid) {
        requireApplied();
        if (arrivalRestored) {
            // Completion is queried again after the game moved on (the causal
            // route, every arrival readback). Re-applying cast counts, damage,
            // placement or life then would overwrite real engine history.
            applyLosslessLibrariesAtCheckpoint(game, playersByPid);
            return;
        }

        // Resolve every semantic Commander to one genuine native Commander id
        // before mutating any watcher state. Generic setup-placed copies are
        // never considered Commander identities.
        Map<String, UUID> liveCommanderIds =
                bindLiveCommanderIds(game, playersByPid);
        // Bind the battlefield commanders before any history is restored, so a
        // binding refusal can never leave a partial restore behind. Their
        // presence is verified at the checkpoint with every first-turn
        // placement (requireFirstTurnPlacement).
        bindCommandersOutsideCommandZone(playersByPid, liveCommanderIds);

        CommanderPlaysCountWatcher castWatcher =
                game.getState().getWatcher(CommanderPlaysCountWatcher.class);
        if (castWatcher == null) {
            throw new RestorationException(
                    "WATCHER_MISSING", "CommanderPlaysCountWatcher not registered");
        }

        Map<UUID, Integer> counts = new HashMap<>();
        for (RequestedCommander requested : plan.commanders()) {
            UUID liveId = liveCommanderIds.get(requested.commanderId());
            if (counts.put(liveId, requested.priorCasts()) != null) {
                throw new RestorationException(
                        "COMMANDER_IDENTITY_AMBIGUOUS",
                        "duplicate native Commander id for " + requested.commanderId());
            }
        }

        // Pre-resolve all CARD-scope CommanderInfoWatchers and native player
        // ids before the first restore call, so ambiguity/missing watcher/
        // unknown-player failures cannot partially mutate the damage ledgers.
        Map<CommanderInfoWatcher, Map<UUID, Integer>> damageByWatcher = new HashMap<>();
        for (RequestedCommanderDamage edge : plan.commanderDamage()) {
            UUID commanderId = liveCommanderIds.get(edge.commanderId());
            CommanderInfoWatcher watcher =
                    game.getState().getWatcher(CommanderInfoWatcher.class, commanderId);
            if (watcher == null) {
                throw new RestorationException(
                        "COMMANDER_DAMAGE_WATCHER_MISSING", edge.commanderId());
            }
            Player damaged = requirePlayer(playersByPid, edge.damagedPlayer());
            Map<UUID, Integer> ledger =
                    damageByWatcher.computeIfAbsent(watcher, ignored -> new HashMap<>());
            if (ledger.put(damaged.getId(), edge.combatDamage()) != null) {
                throw new RestorationException(
                        "DUPLICATE_DAMAGE_EDGE",
                        edge.commanderId() + "|" + edge.damagedPlayer());
            }
        }

        try {
            // One cast-history restore call: native semantics replace the whole
            // cast-count state rather than merging per Commander.
            castWatcher.restoreStateForGameLoad(
                    CommanderPlaysCountState.fromMap(counts), game);

            // One native restore call per exact Commander watcher. This is
            // state restoration, not synthetic historical damage-event replay.
            for (Map.Entry<CommanderInfoWatcher, Map<UUID, Integer>> entry
                    : damageByWatcher.entrySet()) {
                entry.getKey().restoreDamageStateForGameLoad(entry.getValue(), game);
            }
        } catch (IllegalArgumentException exc) {
            throw new RestorationException(
                    "COMMANDER_HISTORY_REJECTED", String.valueOf(exc.getMessage()));
        }

        arrivalRestored = true;
        applyLosslessLibrariesAtCheckpoint(game, playersByPid);
    }

    /**
     * Resumes the record's own declared already-fully-cast stack spell as a
     * real stack object at the record's checkpoint, or returns null while the
     * game is not yet there or the record declares none.
     *
     * <p>The engine never casts, pays, targets or chooses anything: the record
     * declares the spell {@code cast_complete} and {@code costs_paid} with no
     * targets/modes, and this resume only materializes that declared object on
     * the stack with the real card and the card's own real spell ability. The
     * readback is engine-direct and fails closed on any mismatch of stack size,
     * source card, identity or controller. Idempotent: the declared spell is
     * resumed exactly once.</p>
     */
    synchronized JsonObject resumeFullyCastStackSpell(
            GameCommanderImpl game, Map<String, Player> playersByPid) {
        requireApplied();
        if (plan.resumeStackSpell() == null || !atRequestedCheckpoint(game)) {
            return null;
        }
        if (!resumeSpellResumed) {
            if (!game.getStack().isEmpty()) {
                throw new RestorationException(
                        "RESUME_STACK_NOT_EMPTY",
                        "the declared resume expects the record's stack to hold only it; observed "
                                + game.getStack().size() + " objects");
            }
            Card card = resumeSpellCard;
            if (card == null) {
                throw new RestorationException(
                        "RESUME_STACK_CARD_MISSING", plan.resumeStackSpell().semanticId());
            }
            mage.abilities.SpellAbility spellAbility = card.getSpellAbility();
            if (spellAbility == null) {
                throw new RestorationException(
                        "RESUME_STACK_NO_SPELL_ABILITY", plan.resumeStackSpell().semanticId());
            }
            if (declaresUnsupportedResumeCosts(card)) {
                // X, kicker and every optional/additional cost need a declared
                // choice this record does not carry; the resume never invents
                // one, so the whole construction fails closed.
                throw new RestorationException(
                        "UNSUPPORTED_RESUME_COST",
                        plan.resumeStackSpell().semanticId()
                                + "; variable/optional/additional costs are not declared");
            }
            Player controller = requirePlayer(playersByPid, plan.resumeStackSpell().controller());
            if (!castableAtResumeCheckpoint(game, card, controller)) {
                // The record's declared temporal state must have been a legal
                // cast moment for this spell (CR 307.1/307.5): a sorcery can
                // only have been cast by the active player in a main phase with
                // an empty stack, an instant or a card with flash any time its
                // controller had priority. Reconstructing a spell that could
                // not have been cast there is an unreachable state.
                throw new RestorationException(
                        "UNSUPPORTED_RESUME_TIMING",
                        plan.resumeStackSpell().semanticId() + " (" + card.getName()
                                + ", controller " + plan.resumeStackSpell().controller()
                                + ") was not castable at the declared temporal state (active "
                                + pidOf(game.getState().getActivePlayerId(), playersByPid)
                                + ", phase " + game.getTurnPhaseType() + ")");
            }
            if (plan.resumeStackSpell().fromZone() == null) {
                // No Zone.HAND default: the record must declare the zone the
                // spell was cast from, or the construction is refused.
                throw new RestorationException(
                        "UNDECLARED_RESUME_CAST_ZONE",
                        plan.resumeStackSpell().semanticId()
                                + " declares no cast-from zone in its stack_state entry");
            }
            Spell spell = new Spell(
                    card, spellAbility.copy(), controller.getId(),
                    plan.resumeStackSpell().fromZone(), game);
            spell.syncZoneChangeCounterOnStack(card, game);
            game.getState().setZone(spell.getId(), Zone.STACK);
            game.getState().setZone(card.getId(), Zone.STACK);
            game.getStack().push(game, spell);
            resumeSpellResumed = true;
        }
        return resumeStackSpellReadback(game, playersByPid);
    }

    /** Engine-direct readback of the resumed declared stack spell. */
    private JsonObject resumeStackSpellReadback(
            GameCommanderImpl game, Map<String, Player> playersByPid) {
        RequestedStackSpell requested = plan.resumeStackSpell();
        JsonObject readback = new JsonObject();
        JsonArray failures = new JsonArray();
        UUID bound = injectedObjectIdsBySemanticId.get(requested.semanticId());
        List<StackObject> objects = new ArrayList<>();
        for (StackObject object : game.getStack()) {
            objects.add(object);
        }
        readback.addProperty("semantic_id", requested.semanticId());
        readback.addProperty("card_identity", requested.cardIdentity());
        readback.addProperty("stack_size", objects.size());
        if (objects.size() != 1) {
            failures.add("RESUME_STACK_SIZE_MISMATCH: expected 1 actual " + objects.size());
        }
        JsonArray observed = new JsonArray();
        for (StackObject object : objects) {
            JsonObject entry = new JsonObject();
            entry.addProperty("card_identity", object.getName());
            entry.addProperty("controller", pidOf(object.getControllerId(), playersByPid));
            entry.addProperty("source_bound", bound != null && bound.equals(object.getSourceId()));
            boolean isSpell = object instanceof Spell;
            entry.addProperty("is_spell", isSpell);
            observed.add(entry);
            if (!isSpell) {
                failures.add("RESUME_STACK_NOT_A_SPELL: " + requested.semanticId());
            } else {
                Spell spell = (Spell) object;
                entry.addProperty("from_zone", String.valueOf(spell.getFromZone()));
                if (spell.getFromZone() != requested.fromZone()) {
                    failures.add("RESUME_STACK_FROM_ZONE_MISMATCH: expected "
                            + requested.fromZone() + " actual " + spell.getFromZone());
                }
                boolean boundCard = bound != null && spell.getCard() != null
                        && bound.equals(spell.getCard().getId());
                entry.addProperty("bound_card", boundCard);
                if (!boundCard) {
                    failures.add("RESUME_STACK_BOUND_CARD_MISMATCH: " + requested.semanticId());
                }
                Zone cardZone = spell.getCard() == null
                        ? null : game.getState().getZone(spell.getCard().getId());
                entry.addProperty("card_zone", String.valueOf(cardZone));
                if (cardZone != Zone.STACK) {
                    failures.add("RESUME_STACK_CARD_ZONE_MISMATCH: expected STACK actual "
                            + cardZone);
                }
            }
            if (bound == null || !bound.equals(object.getSourceId())) {
                failures.add("RESUME_STACK_SOURCE_MISMATCH: " + requested.semanticId());
            } else if (!requested.cardIdentity().equals(object.getName())) {
                failures.add("RESUME_STACK_IDENTITY_MISMATCH: expected "
                        + requested.cardIdentity() + " actual " + object.getName());
            }
            String controller = pidOf(object.getControllerId(), playersByPid);
            if (!requested.controller().equals(controller)) {
                failures.add("RESUME_STACK_CONTROLLER_MISMATCH: expected "
                        + requested.controller() + " actual " + controller);
            }
        }
        readback.add("observed", observed);
        readback.add("failures", failures);
        readback.addProperty("verified", failures.isEmpty());
        return readback;
    }

    /**
     * Whether the spell's real card declares a cost shape this route cannot
     * resume without inventing an undeclared choice: a variable (X) mana cost,
     * any additional non-mana cost on the spell ability, or an optional
     * additional cost source (kicker, multikicker, entwine, ...).
     */
    static boolean declaresUnsupportedResumeCosts(Card card) {
        mage.abilities.SpellAbility ability = card.getSpellAbility();
        if (ability == null) {
            return false;
        }
        if (ability.getManaCosts().containsX() || card.getManaCost().containsX()) {
            return true;
        }
        if (!ability.getCosts().isEmpty()) {
            return true;
        }
        for (Ability listed : card.getAbilities()) {
            if (listed instanceof mage.abilities.costs.OptionalAdditionalSourceCosts) {
                return true;
            }
        }
        return false;
    }

    /**
     * Whether the declared already-cast spell was castable at the record's
     * declared temporal state: an instant or a card with flash any time its
     * controller had priority, or otherwise the controller was the active
     * player in a main phase with the stack otherwise empty (CR 307.1/307.5,
     * 117.1a). The stack is empty here by the resume's own precondition; the
     * check is the declared cast moment, never a real cast.
     */
    static boolean castableAtResumeCheckpoint(Game game, Card card, Player controller) {
        if (card.isInstant()
                || card.getAbilities(game).containsClass(
                        mage.abilities.keyword.FlashAbility.class)) {
            return true;
        }
        if (!controller.getId().equals(game.getState().getActivePlayerId())) {
            return false;
        }
        TurnPhase phase = game.getTurnPhaseType();
        if (phase != TurnPhase.PRECOMBAT_MAIN && phase != TurnPhase.POSTCOMBAT_MAIN) {
            return false;
        }
        return game.getStack().isEmpty();
    }

    /**
     * SLOT-04: requested library cards and the complete library order, through
     * the native game-load API, once the game stands at the requested
     * checkpoint. A requested library is the library AT the checkpoint: the
     * arrival is completed at earlier priorities too (an upkeep before the
     * first-turn draw), and placing it there would let the active player's
     * draw take the requested top card. The face-down object was already
     * turned face down before game start.
     */
    private void applyLosslessLibrariesAtCheckpoint(
            GameCommanderImpl game, Map<String, Player> playersByPid) {
        if (losslessLibrariesApplied || !atRequestedCheckpoint(game)) {
            return;
        }
        requireFirstTurnPlacement(game);
        applyDeferredHandAtCheckpoint(game, playersByPid);
        applyDeferredGraveyardAtCheckpoint(game, playersByPid);
        losslessHidden.applyAfterArrival(game, playersByPid, this);
        applyCheckpointPermanentState(game);
        losslessLibrariesApplied = true;
    }

    /**
     * Places a turn-2 record's requested hand objects at the checkpoint
     * ({@link #deferredHandByPlayer}), through the same engine setup
     * primitive the pre-start placement uses. Runs exactly once, while the
     * engine stands at the requested checkpoint.
     */
    private void applyDeferredHandAtCheckpoint(
            GameCommanderImpl game, Map<String, Player> playersByPid) {
        if (deferredHandByPlayer.isEmpty()) {
            return;
        }
        for (Map.Entry<String, List<Card>> entry : deferredHandByPlayer.entrySet()) {
            Player player = requirePlayer(playersByPid, entry.getKey());
            game.cheat(player.getId(), List.of(), entry.getValue(),
                    List.of(), List.of(), List.of(), List.of());
            for (Card card : entry.getValue()) {
                injectedHandIdsByPlayer
                        .computeIfAbsent(entry.getKey(), ignored -> new HashSet<>())
                        .add(card.getId());
            }
        }
        deferredHandByPlayer.clear();
    }

    /**
     * Places a turn-2 record's requested graveyard objects at the checkpoint
     * ({@link #deferredGraveyardByPlayer}) only as far as the engine's own
     * state does not already satisfy them: the engine's own turn 1 may have
     * produced the recorded graveyard result itself (P1's scripted cleanup
     * discard), and a construction never duplicates an engine-performed zone
     * change. A requested object the record marks with {@code produced_by_step}
     * is never topped up, however far the engine's state is from the record:
     * only the engine's own zone change may satisfy it, and a missing one is
     * left to the exact comparison (fail closed), never silently injected.
     */
    private void applyDeferredGraveyardAtCheckpoint(
            GameCommanderImpl game, Map<String, Player> playersByPid) {
        if (deferredGraveyardByPlayer.isEmpty()) {
            return;
        }
        for (Map.Entry<String, List<Card>> entry : deferredGraveyardByPlayer.entrySet()) {
            Player player = requirePlayer(playersByPid, entry.getKey());
            Map<String, Integer> present = new HashMap<>();
            for (Card card : player.getGraveyard().getCards(game)) {
                present.merge(card.getName(), 1, Integer::sum);
            }
            Map<String, Integer> planned = new HashMap<>();
            List<Card> toPlace = new ArrayList<>();
            for (Card card : entry.getValue()) {
                int want = planned.merge(card.getName(), 1, Integer::sum);
                if (producedByStepGraveyardCardIds.contains(card.getId())) {
                    // The record's produced object: the engine's own zone change
                    // is the only source. Never placed here; the exact
                    // comparison below the checkpoint fails closed when the
                    // engine's history did not produce it.
                    continue;
                }
                if (present.getOrDefault(card.getName(), 0) < want) {
                    toPlace.add(card);
                }
            }
            if (!toPlace.isEmpty()) {
                game.cheat(player.getId(), List.of(), List.of(), List.of(), toPlace,
                        List.of(), List.of());
            }
        }
        deferredGraveyardByPlayer.clear();
    }

    /**
     * Every permanent deferred to the first turn, battlefield commanders
     * included, was put onto the battlefield by the setup watcher when turn 1
     * began ({@link XmageFirstTurnSetupWatcher}) and is still there at the
     * checkpoint. One the watcher did not place, or one no longer on the
     * battlefield, fails closed with FIRST_TURN_PLACEMENT_MISSED; nothing is
     * placed late.
     */
    private void requireFirstTurnPlacement(GameCommanderImpl game) {
        if (firstTurnPlacedSemanticIds.isEmpty()) {
            return;
        }
        XmageFirstTurnSetupWatcher setup = game.getState().getWatcher(XmageFirstTurnSetupWatcher.class);
        List<UUID> placed = setup == null ? List.of() : setup.placedIds();
        for (String semanticId : firstTurnPlacedSemanticIds) {
            UUID id = injectedObjectId(semanticId);
            if (!placed.contains(id) || game.getPermanent(id) == null) {
                throw new RestorationException("FIRST_TURN_PLACEMENT_MISSED", semanticId);
            }
        }
    }

    /**
     * Tapped state and counters are checkpoint state too: a permanent placed
     * tapped before game start would be untapped by its controller's first
     * untap step. Both are set silently through the game-load path once the
     * game stands at the checkpoint (no tap or counter event is fabricated,
     * as no placement event is), and verified engine-direct by
     * {@link #checkpointPermanentVerification}.
     */
    private void applyCheckpointPermanentState(GameCommanderImpl game) {
        for (RequestedObject object : plan.objects()) {
            Map<String, Integer> counters = plan.objectCounters().getOrDefault(object.semanticId(), Map.of());
            if (!object.tapped() && counters.isEmpty()) {
                continue;
            }
            Permanent permanent = game.getPermanent(injectedObjectId(object.semanticId()));
            if (permanent == null) {
                throw new RestorationException("CHECKPOINT_PERMANENT_MISSING", object.semanticId());
            }
            if (object.tapped() && !plan.declaredAttackers().contains(object.semanticId())) {
                permanent.setTapped(true);
            }
            for (Map.Entry<String, Integer> counter : counters.entrySet()) {
                if (LOYALTY.equals(counter.getKey())) {
                    // Set when the permanent entered (XmageFirstTurnSetupWatcher).
                    continue;
                }
                permanent.getCounters(game).addCounter(
                        counterType(counter.getKey()).createInstance(counter.getValue()));
            }
        }
    }

    /** Engine-direct verification of the requested checkpoint tapped state and counters. */
    XmageLosslessHiddenPlan.Verification checkpointPermanentVerification(GameCommanderImpl game) {
        List<String> checks = new ArrayList<>();
        List<String> mismatches = new ArrayList<>();
        for (RequestedObject object : plan.objects()) {
            Map<String, Integer> counters = plan.objectCounters().getOrDefault(object.semanticId(), Map.of());
            Boolean sinceTurnBegan = plan.controlledSinceTurnBegan().get(object.semanticId());
            if (object.zone() != Zone.BATTLEFIELD
                    || (!object.tapped() && counters.isEmpty() && sinceTurnBegan == null)) {
                continue;
            }
            Permanent permanent = game.getPermanent(injectedObjectId(object.semanticId()));
            if (sinceTurnBegan != null) {
                checks.add("controlled_since_turn_began:" + object.semanticId());
                boolean observed = permanent != null && permanent.wasControlledFromStartOfControllerTurn();
                if (observed != sinceTurnBegan) {
                    mismatches.add("controlled_since_turn_began " + object.semanticId()
                            + ": requested " + sinceTurnBegan + " observed " + observed);
                }
            }
            if (object.tapped()) {
                checks.add("tapped:" + object.semanticId());
                if (permanent == null || !permanent.isTapped()) {
                    mismatches.add("tapped " + object.semanticId() + ": not tapped");
                }
            }
            if (!counters.isEmpty()) {
                checks.add("counters:" + object.semanticId());
                for (Map.Entry<String, Integer> counter : counters.entrySet()) {
                    int observed = permanent == null ? 0
                            : permanent.getCounters(game).getCount(counterType(counter.getKey()));
                    if (observed != counter.getValue()) {
                        mismatches.add("counters " + object.semanticId() + " " + counter.getKey()
                                + ": requested " + counter.getValue() + " observed " + observed);
                    }
                }
            }
        }
        // A commander requested on the battlefield is a permanent of its owner
        // like any other: its requested control history is verified too.
        for (RequestedCommander commander : plan.commanders()) {
            Boolean sinceTurnBegan = commander.zone() == Zone.BATTLEFIELD
                    ? plan.controlledSinceTurnBegan().get(commander.semanticId()) : null;
            if (sinceTurnBegan == null) {
                continue;
            }
            checks.add("controlled_since_turn_began:" + commander.semanticId());
            Permanent permanent = game.getPermanent(injectedObjectId(commander.semanticId()));
            boolean observed = permanent != null && permanent.wasControlledFromStartOfControllerTurn();
            if (observed != sinceTurnBegan) {
                mismatches.add("controlled_since_turn_began " + commander.semanticId()
                        + ": requested " + sinceTurnBegan + " observed " + observed);
            }
        }
        return new XmageLosslessHiddenPlan.Verification(checks, mismatches);
    }

    private boolean requestsCheckpointState() {
        if (!losslessHidden.isEmpty() || !plan.objectCounters().isEmpty()
                || !plan.controlledSinceTurnBegan().isEmpty()) {
            return true;
        }
        return plan.objects().stream().anyMatch(RequestedObject::tapped);
    }

    private boolean atRequestedCheckpoint(GameCommanderImpl game) {
        return game.getTurnNum() == plan.turnNumber()
                && game.getTurnPhaseType() == plan.phase()
                && game.getTurnStepType() == plan.step();
    }

    /**
     * F-38: a commander requested on the battlefield is the genuine commander. It
     * leaves the command zone when the first turn begins, as every restored
     * permanent enters ({@link XmageFirstTurnSetupWatcher}), never as a generic
     * setup copy, which the engine would not treat as a commander (no commander
     * zone choice, tax or damage). Here it is only bound: the engine must report
     * the commander published before game start. That the setup watcher itself
     * put it onto the battlefield is verified at the checkpoint
     * ({@link #requireFirstTurnPlacement}), like every first-turn placement.
     */
    private void bindCommandersOutsideCommandZone(
            Map<String, Player> playersByPid, Map<String, UUID> liveCommanderIds) {
        for (RequestedCommander requested : plan.commanders()) {
            if (requested.zone() != Zone.BATTLEFIELD) {
                continue;
            }
            UUID liveId = liveCommanderIds.get(requested.commanderId());
            if (!liveId.equals(commanderObjectIdsBySemanticId.get(requested.semanticId()))) {
                // The engine chose a different commander card than the one
                // published before the game started.
                throw new RestorationException(
                        "COMMANDER_IDENTITY_AMBIGUOUS", requested.commanderId());
            }
            requirePlayer(playersByPid, requested.owner());
            injectedObjectIdsBySemanticId.put(requested.semanticId(), liveId);
        }
    }

    /**
     * Every requested commander's card id, keyed by commander id: the owner's one
     * sideboard card of that identity, which GameCommanderImpl.init makes the
     * commander. Valid before the game starts; commanders are public objects.
     */
    JsonObject commanderCardIds(GameCommanderImpl game, Map<String, Player> playersByPid) {
        JsonObject ids = new JsonObject();
        for (RequestedCommander requested : plan.commanders()) {
            Player owner = requirePlayer(playersByPid, requested.owner());
            List<UUID> matches = new ArrayList<>();
            for (UUID cardId : owner.getSideboard()) {
                Card card = game.getCard(cardId);
                if (card != null && requested.cardIdentity().equals(card.getName())) {
                    matches.add(cardId);
                }
            }
            if (matches.size() != 1) {
                throw new RestorationException(
                        "COMMANDER_IDENTITY_AMBIGUOUS",
                        requested.commanderId() + " matched " + matches.size()
                                + " sideboard cards for " + requested.owner());
            }
            ids.addProperty(requested.commanderId(), matches.get(0).toString());
        }
        return ids;
    }

    /**
     * Binds every commander requested outside the command zone to the owner's
     * one sideboard card of that identity: GameCommanderImpl.init makes exactly
     * those sideboard cards the commanders. Placement later requires the
     * engine's genuine commander id to equal this binding.
     */
    private void prebindCommanderObjects(
            GameCommanderImpl game, Map<String, Player> playersByPid) {
        for (RequestedCommander requested : plan.commanders()) {
            if (requested.zone() == Zone.COMMAND) {
                continue;
            }
            Player owner = requirePlayer(playersByPid, requested.owner());
            List<UUID> matches = new ArrayList<>();
            for (UUID cardId : owner.getSideboard()) {
                Card card = game.getCard(cardId);
                if (card != null && requested.cardIdentity().equals(card.getName())) {
                    matches.add(cardId);
                }
            }
            if (matches.size() != 1) {
                throw new RestorationException(
                        "COMMANDER_IDENTITY_AMBIGUOUS",
                        requested.commanderId() + " matched " + matches.size()
                                + " sideboard cards for " + requested.owner());
            }
            if (commanderObjectIdsBySemanticId.put(requested.semanticId(), matches.get(0)) != null
                    || injectedObjectIdsBySemanticId.containsKey(requested.semanticId())) {
                throw new RestorationException(
                        "DUPLICATE_SEMANTIC_OBJECT", requested.semanticId());
            }
        }
    }

    /**
     * Resolves semantic Commander ids to the exact native Commander main-card
     * ids owned by the requested player. Only GameCommanderImpl's authoritative
     * Commander identity set participates; battlefield setup copies are
     * deliberately excluded. Owner + exact card identity must bind 1:1.
     */
    private Map<String, UUID> bindLiveCommanderIds(
            GameCommanderImpl game, Map<String, Player> playersByPid) {
        Map<String, UUID> resolved = new HashMap<>();
        Set<UUID> used = new HashSet<>();
        for (RequestedCommander requested : plan.commanders()) {
            Player owner = requirePlayer(playersByPid, requested.owner());
            List<UUID> matches = new ArrayList<>();
            for (UUID commanderId
                    : game.getCommandersIds(owner, CommanderCardType.ANY, false)) {
                Card card = game.getCard(commanderId);
                if (card != null && requested.cardIdentity().equals(card.getName())) {
                    matches.add(commanderId);
                }
            }
            if (matches.size() != 1) {
                throw new RestorationException(
                        "COMMANDER_IDENTITY_AMBIGUOUS",
                        requested.commanderId() + " matched " + matches.size()
                                + " genuine Commander ids for " + requested.owner());
            }
            UUID liveId = matches.get(0);
            if (!used.add(liveId)) {
                throw new RestorationException(
                        "COMMANDER_IDENTITY_AMBIGUOUS",
                        "native Commander id reused for " + requested.commanderId());
            }
            resolved.put(requested.commanderId(), liveId);
        }
        return Map.copyOf(resolved);
    }

    /** Engine-authoritative re-validation: layers plus state-based actions. */
    static void revalidate(Game game) {
        game.applyEffects();
        game.checkStateAndTriggered();
    }

    /**
     * Strict native readback of the compared dimensions. Public zones carry
     * full identity; restored hands carry full identity engine-direct
     * (test-only proof surface, never pilot-facing: pilot observation stays
     * principal-scoped through the redactor); libraries contribute counts
     * only (unspecified by construction and excluded from comparison).
     */
    static JsonObject readback(GameCommanderImpl game, Map<String, Player> playersByPid) {
        JsonObject root = new JsonObject();
        root.addProperty("turn_number", game.getState().getTurnNum());
        root.addProperty("phase", game.getTurnPhaseType() == null
                ? "UNINITIALIZED" : game.getTurnPhaseType().name());
        root.addProperty("step", game.getTurnStepType() == null
                ? "UNINITIALIZED" : game.getTurnStepType().name());
        root.addProperty("active_player", pidOf(game.getState().getActivePlayerId(), playersByPid));
        root.addProperty("priority_player",
                pidOf(game.getState().getPriorityPlayerId(), playersByPid));
        root.addProperty("rules_seed", game.getRulesSeed());
        root.addProperty("rules_seed_explicit", game.isRulesSeedExplicit());
        root.addProperty("has_extra_turn", game.getState().getExtraTurnId() != null);
        // The engine's own pending extra turns (CR 500.7), in the order it will
        // take them: the most recently created first. Always reported, empty
        // when the queue is empty, so a consumer can tell a drained queue from
        // a readback that never carried the field.
        JsonArray pendingExtraTurns = new JsonArray();
        List<mage.game.turn.TurnMod> mods = new ArrayList<>(game.getState().getTurnMods());
        Collections.reverse(mods);
        for (mage.game.turn.TurnMod mod : mods) {
            if (mod.isExtraTurn()) {
                pendingExtraTurns.add(pidOf(mod.getPlayerId(), playersByPid));
            }
        }
        root.add("pending_extra_turns", pendingExtraTurns);
        JsonArray seats = new JsonArray();
        List<String> orderedPids = new ArrayList<>(playersByPid.keySet());
        Collections.sort(orderedPids);
        for (String pid : orderedPids) {
            Player player = playersByPid.get(pid);
            JsonObject seat = new JsonObject();
            seat.addProperty("player_id", pid);
            seat.addProperty("life", player.getLife());
            seat.addProperty("lost", player.hasLost());
            seat.addProperty("left", player.hasLeft());
            seat.addProperty("poison", player.getCountersCount(mage.counters.CounterType.POISON));
            seat.addProperty("hand_count", player.getHand().size());
            seat.addProperty("library_count", player.getLibrary().size());
            JsonArray hand = new JsonArray();
            for (Card card : player.getHand().getCards(game)) {
                hand.add(card.getName());
            }
            sortStrings(hand);
            seat.add("hand", hand);
            CommanderPlaysCountWatcher watcher =
                    game.getState().getWatcher(CommanderPlaysCountWatcher.class);
            JsonArray commanders = new JsonArray();
            // Every genuine commander identity with its current zone (F-38), not only
            // those in the command zone.
            for (UUID commanderId : game.getCommandersIds(
                    player, CommanderCardType.COMMANDER_OR_OATHBREAKER, false)) {
                Card card = game.getCard(commanderId);
                if (card == null) {
                    continue;
                }
                JsonObject entry = new JsonObject();
                entry.addProperty("card_identity", card.getName());
                entry.addProperty("zone", String.valueOf(game.getState().getZone(commanderId)));
                entry.addProperty("prior_casts",
                        watcher == null ? -1 : watcher.getPlaysCount(card.getId()));
                // The engine's own live commander combat damage (CR 903.10a),
                // read from this commander's CommanderInfoWatcher: damaged
                // player -> total. Public state; reported only when present.
                CommanderInfoWatcher damageWatcher =
                        game.getState().getWatcher(CommanderInfoWatcher.class, commanderId);
                if (damageWatcher != null) {
                    JsonObject damage = new JsonObject();
                    for (String damagedPid : orderedPids) {
                        int amount = damageWatcher.getDamageToPlayer()
                                .getOrDefault(playersByPid.get(damagedPid).getId(), 0);
                        if (amount > 0) {
                            damage.addProperty(damagedPid, amount);
                        }
                    }
                    if (damage.size() > 0) {
                        entry.add("combat_damage_to", damage);
                    }
                }
                commanders.add(entry);
            }
            sortObjectsBy(commanders, "card_identity");
            seat.add("commanders", commanders);
            JsonArray battlefield = new JsonArray();
            for (Permanent permanent : game.getBattlefield().getAllPermanents()) {
                if (!player.getId().equals(permanent.getOwnerId())) {
                    continue;
                }
                JsonObject entry = new JsonObject();
                entry.addProperty("card_identity", permanent.getName());
                entry.addProperty("controller",
                        pidOf(permanent.getControllerId(), playersByPid));
                entry.addProperty("tapped", permanent.isTapped());
                entry.addProperty("power", intOr(permanent.getPower(), -1));
                entry.addProperty("toughness", intOr(permanent.getToughness(), -1));
                // Counters and evergreen keywords are public permanent state.
                // Each is reported only when present, so a permanent without
                // them reads back exactly as before.
                JsonObject counters = new JsonObject();
                for (mage.counters.Counter counter : permanent.getCounters(game).values()) {
                    if (counter.getCount() > 0) {
                        counters.addProperty(counter.getName(), counter.getCount());
                    }
                }
                if (counters.size() > 0) {
                    entry.add("counters", counters);
                }
                JsonArray keywords = new JsonArray();
                for (Map.Entry<String, Class<? extends Ability>> keyword : KEYWORDS.entrySet()) {
                    if (permanent.getAbilities(game).containsClass(keyword.getValue())) {
                        keywords.add(keyword.getKey());
                    }
                }
                if (keywords.size() > 0) {
                    entry.add("keywords", keywords);
                }
                // Token-ness and triggered abilities are public permanent
                // state too. Each triggered ability is reported by the engine's
                // own ability and effect classes (plus its rules text, for
                // reading only), so a check binds to what the engine will
                // trigger rather than to prose. Reported only when present.
                if (permanent instanceof mage.game.permanent.PermanentToken) {
                    entry.addProperty("token", true);
                }
                JsonArray triggered = new JsonArray();
                for (Ability ability : permanent.getAbilities(game)) {
                    if (!(ability instanceof mage.abilities.TriggeredAbility)) {
                        continue;
                    }
                    JsonObject trigger = new JsonObject();
                    trigger.addProperty("trigger", ability.getClass().getSimpleName());
                    JsonArray effects = new JsonArray();
                    for (mage.abilities.effects.Effect effect : ability.getEffects()) {
                        effects.add(effect.getClass().getSimpleName());
                    }
                    trigger.add("effects", effects);
                    trigger.addProperty("rule", ability.getRule());
                    triggered.add(trigger);
                }
                if (triggered.size() > 0) {
                    entry.add("triggered_abilities", triggered);
                }
                mage.ObjectColor color = permanent.getColor(game);
                JsonArray colors = new JsonArray();
                if (color.isWhite()) {
                    colors.add("white");
                }
                if (color.isBlue()) {
                    colors.add("blue");
                }
                if (color.isBlack()) {
                    colors.add("black");
                }
                if (color.isRed()) {
                    colors.add("red");
                }
                if (color.isGreen()) {
                    colors.add("green");
                }
                if (colors.size() > 0) {
                    entry.add("colors", colors);
                }
                battlefield.add(entry);
            }
            sortObjectsBy(battlefield, "card_identity");
            seat.add("battlefield", battlefield);
            JsonArray graveyard = new JsonArray();
            for (Card card : player.getGraveyard().getCards(game)) {
                graveyard.add(card.getName());
            }
            sortStrings(graveyard);
            seat.add("graveyard", graveyard);
            // Each graveyard card's mana value, from the engine's own card
            // object (a characteristic of the card, CR 202.3). Reported only
            // when the graveyard is not empty.
            JsonObject graveyardManaValues = new JsonObject();
            for (Card card : player.getGraveyard().getCards(game)) {
                graveyardManaValues.addProperty(card.getName(), card.getManaValue());
            }
            if (graveyardManaValues.size() > 0) {
                seat.add("graveyard_mana_values", graveyardManaValues);
            }
            JsonArray exile = new JsonArray();
            for (Card card : game.getExile().getCardsOwned(game, player.getId())) {
                exile.add(card.getName());
            }
            sortStrings(exile);
            seat.add("exile", exile);
            seats.add(seat);
        }
        root.add("seats", seats);
        // Public stack objects, reported only when the stack is non-empty, so
        // every other construction's readback and digest are unchanged. The
        // resumed declared spell is thus part of the constructed-state digest
        // and the principal-scoped observation, not only of its own readback.
        List<StackObject> stackObjects = new ArrayList<>();
        for (StackObject object : game.getStack()) {
            stackObjects.add(object);
        }
        if (!stackObjects.isEmpty()) {
            JsonArray stack = new JsonArray();
            for (StackObject object : stackObjects) {
                JsonObject entry = new JsonObject();
                entry.addProperty("card_identity", object.getName());
                entry.addProperty("controller", pidOf(object.getControllerId(), playersByPid));
                stack.add(entry);
            }
            root.add("stack", stack);
        }
        return root;
    }

    /**
     * Compares requested fields against the native readback. Multiset
     * semantics per (player, zone, identity, tapped, controller) so
     * homogeneous objects match without inventing identity links.
     */
    CompareVerdict compare(JsonObject observed, Map<String, Player> playersByPid) {
        List<String> mismatches = new ArrayList<>();
        expect("turn_number", observed.get("turn_number").getAsInt(), plan.turnNumber(), mismatches);
        expectText("phase", observed.get("phase").getAsString(),
                plan.phase().name(), mismatches);
        expectText("step", observed.get("step").getAsString(), plan.step().name(), mismatches);
        expectText("active_player", observed.get("active_player").getAsString(),
                plan.activePlayer(), mismatches);
        expectText("priority_player", observed.get("priority_player").getAsString(),
                plan.priorityPlayer(), mismatches);
        if (observed.get("rules_seed").getAsLong() != plan.seed()
                || !observed.get("rules_seed_explicit").getAsBoolean()) {
            mismatches.add("rules_seed: requested explicit " + plan.seed()
                    + " observed " + observed.get("rules_seed").getAsLong()
                    + " explicit=" + observed.get("rules_seed_explicit").getAsBoolean());
        }
        Map<String, JsonObject> seatsByPid = new HashMap<>();
        for (JsonElement element : observed.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            seatsByPid.put(seat.get("player_id").getAsString(), seat);
        }
        for (RequestedPlayer requested : plan.players()) {
            JsonObject seat = seatsByPid.get(requested.playerId());
            if (seat == null) {
                mismatches.add("seat missing: " + requested.playerId());
                continue;
            }
            expect("life " + requested.playerId(),
                    seat.get("life").getAsInt(), requested.life(), mismatches);
        }
        for (RequestedCommander requested : plan.commanders()) {
            JsonObject seat = seatsByPid.get(requested.owner());
            boolean found = false;
            if (seat != null) {
                for (JsonElement element : seat.getAsJsonArray("commanders")) {
                    JsonObject entry = element.getAsJsonObject();
                    if (entry.get("card_identity").getAsString()
                            .equals(requested.cardIdentity())) {
                        found = true;
                        expect("casts " + requested.commanderId(),
                                entry.get("prior_casts").getAsInt(),
                                requested.priorCasts(), mismatches);
                        expectText("zone " + requested.commanderId(),
                                entry.get("zone").getAsString(), requested.zone().name(), mismatches);
                    }
                }
            }
            if (!found) {
                mismatches.add("commander missing: " + requested.commanderId()
                        + " (" + requested.cardIdentity() + ") for " + requested.owner());
            }
        }
        Map<String, Integer> requestedCounts = new TreeMap<>();
        for (RequestedObject object : plan.objects()) {
            if (losslessHidden.declaresFaceDown(object.semanticId())) {
                // A face-down permanent has no public name (CR 708.2); its
                // underlying identity and native type are verified engine-direct
                // by the lossless plan, never through this public readback.
                requestedCounts.merge(multisetKey(new RequestedObject(object.semanticId(),
                        mage.constants.EmptyNames.FACE_DOWN_CREATURE.getObjectName(), object.owner(),
                        object.controller(), object.zone(), object.tapped())), 1, Integer::sum);
                continue;
            }
            requestedCounts.merge(multisetKey(object), 1, Integer::sum);
        }
        for (RequestedCommander commander : plan.commanders()) {
            if (commander.zone() == Zone.BATTLEFIELD) {
                // The genuine commander is a permanent of its owner like any other.
                requestedCounts.merge(multisetKey(new RequestedObject(commander.semanticId(),
                        commander.cardIdentity(), commander.owner(), commander.owner(),
                        Zone.BATTLEFIELD, false)), 1, Integer::sum);
            }
        }
        Map<String, Integer> observedCounts = new TreeMap<>();
        for (Map.Entry<String, JsonObject> entry : seatsByPid.entrySet()) {
            collectZone(entry.getValue(), "battlefield", entry.getKey(), observedCounts);
            collectZone(entry.getValue(), "graveyard", entry.getKey(), observedCounts);
            collectZone(entry.getValue(), "exile", entry.getKey(), observedCounts);
            collectZone(entry.getValue(), "hand", entry.getKey(), observedCounts);
        }
        Set<String> keys = new HashSet<>(requestedCounts.keySet());
        keys.addAll(observedCounts.keySet());
        List<String> ordered = new ArrayList<>(keys);
        Collections.sort(ordered);
        for (String key : ordered) {
            int want = requestedCounts.getOrDefault(key, 0);
            int got = observedCounts.getOrDefault(key, 0);
            if (isHandKey(key)) {
                // Hands mix requested cards with the scaffolding vehicle's
                // opening seven (harness construction, never fixture content):
                // every requested hand card must be present, extras are the
                // vehicle's draws (count-pinned by the hand-count check below).
                if (got < want) {
                    mismatches.add(
                            "hand subset " + key + ": requested " + want + " observed " + got);
                }
                continue;
            }
            if (want != got) {
                mismatches.add(
                        "zone multiset " + key + ": requested " + want + " observed " + got);
            }
        }
        for (RequestedPlayer requested : plan.players()) {
            JsonObject seat = seatsByPid.get(requested.playerId());
            if (seat == null) {
                continue;
            }
            int requestedHand = 0;
            for (RequestedObject object : plan.objects()) {
                if (object.owner().equals(requested.playerId())
                        && object.zone() == Zone.HAND) {
                    requestedHand++;
                }
            }
            // Hands also hold the scaffolding vehicle's opening seven plus
            // any natural draws on the arrival path. A name-count subset is
            // therefore insufficient when the requested identity equals a
            // scaffolding card (for example Mountain): natural draws could
            // otherwise mask a missing injected copy. Bind credit to the
            // exact native UUIDs of cards consumed from the materialization
            // vehicle and require every injected object to remain in hand.
            Set<UUID> injected =
                    injectedHandIdsByPlayer.getOrDefault(requested.playerId(), Set.of());
            if (injected.size() != requestedHand) {
                mismatches.add("hand injected-count " + requested.playerId()
                        + ": requested " + requestedHand + " tracked " + injected.size());
            }
            Player livePlayer = playersByPid.get(requested.playerId());
            if (livePlayer == null) {
                mismatches.add("hand player missing: " + requested.playerId());
            } else {
                for (UUID cardId : injected) {
                    if (!livePlayer.getHand().contains(cardId)) {
                        mismatches.add("hand injected object missing: "
                                + requested.playerId() + " native_id=" + cardId);
                    }
                }
            }
            if (seat.get("hand_count").getAsInt() < requestedHand) {
                mismatches.add("hand_count " + requested.playerId()
                        + ": requested at least " + requestedHand
                        + " observed " + seat.get("hand_count").getAsInt());
            }
        }
        return new CompareVerdict(
                mismatches.isEmpty(),
                List.copyOf(mismatches),
                digestJson(canonicalRequested()),
                digestJson(observed));
    }

    /**
     * Enumerates a commander's current cast cost through the engine's own
     * cost pipeline (cost modifications incl. commander tax) applied to a
     * faithful ability copy. The copy is zoned COMMAND via the engine's
     * {@code copyWithZone} (mirroring the stack ability's zone in the real
     * cast path, where the tax effect applies). Pure query: the live card
     * ability is never touched and no game state mutates (callers prove
     * purity with readback equality). Returns the canonical sorted figure
     * (e.g. "{0}+{4}").
     */
    static String enumerateCommanderCastCost(Game game, Card commander) {
        if (game == null || commander == null) {
            throw new RestorationException("INVALID_COMMANDER", "game and card must not be null");
        }
        mage.abilities.Ability raw = commander.getSpellAbility();
        if (!(raw instanceof mage.abilities.SpellAbility)
                || !(raw instanceof mage.abilities.AbilityImpl)) {
            throw new RestorationException(
                    "NO_SPELL_ABILITY", commander.getName() + " has no spell ability");
        }
        mage.abilities.Ability probe =
                ((mage.abilities.AbilityImpl) raw.copy()).copyWithZone(Zone.COMMAND);
        game.getContinuousEffects().costModification(probe, game);
        List<String> parts = new ArrayList<>();
        for (mage.abilities.costs.mana.ManaCost cost : probe.getManaCostsToPay()) {
            parts.add(cost.toString());
        }
        Collections.sort(parts);
        return String.join("+", parts);
    }

    /** Explicit supported/unsupported dimensions descriptor (global flag untouched). */
    static JsonObject dimensionsPayload() {        JsonObject payload = new JsonObject();
        payload.addProperty("schema_version", "native-state-restoration-dimensions-1.1.0");
        payload.addProperty("starting_state_injection_supported", false);
        JsonArray supported = new JsonArray();
        supported.add("commanders with prior cast counts (native game-load restore path)");
        supported.add("genuine commanders on the battlefield (engine command-zone removal plus the "
                + "silent battlefield primitive; never a generic setup copy)");
        supported.add("commander damage matrices through exact live CommanderInfoWatcher bindings "
                + "(native game-load restore; no synthetic damage events)");
        supported.add("battlefield/graveyard/exile placement of real cards (silent setup primitive)");
        supported.add("hand identity via the same setup primitive (principal-scoped; "
                + "pilot observation stays counts-only through the redactor; "
                + "honeycard non-leakage proven per fixture)");
        supported.add("owner-equals-controller attribution with 1:1 readback");
        supported.add("life totals equal to the player's recorded starting life (set once after"
                + " game start without a life event; any other total must be caused and is only"
                + " compared; state-based actions stay authoritative)");
        supported.add("qualified turn-1 temporal targets: upkeep, draw, precombat main, "
                + "declare attackers, declare blockers, combat damage, postcombat main; "
                + "arrival requires XmageTemporalProgressionDriver native progression");
        supported.add("the qualified turn-2 precombat-main temporal target (P2 active and "
                + "holding priority after the engine's own turn 1 and turn-based actions), "
                + "reached only through the engine's own turn structure");
        supported.add("explicit Rules-seed binding with replay determinism");
        supported.add("a record-declared already-fully-cast stack spell "
                + "(execution_entry_mode NATIVE_STATE_LOAD with "
                + "NATIVE_RESUME_WITH_FULLY_CAST_STACK_SPELL, cast_complete and costs_paid "
                + "declared, no targets/modes, exactly one stack entry and stack object, a "
                + "declared cast-from zone, no variable/optional/additional costs, and a "
                + "declared temporal state in which the spell was castable per CR 307.1/307.5) "
                + "resumed as a real stack object at the record's "
                + "checkpoint with engine-direct source/identity/controller/zone readback; "
                + "nothing is cast, paid, targeted or chosen");
        supported.add("strict native readback with field-level compare and digests");
        supported.add("explicit L7 lossless hidden-state requests: complete live-library "
                + "identity order plus one explicitly typed face-down battlefield object; "
                + "delegated to native RG-06A game-load APIs");
        supported.add("frozen requested_state_digest equality for constructed states "
                + "in the v1 subset (canonical projection per the recovered spec, "
                + "verified per fixture; see requestedDigest/constructedDigest)");
        supported.add("tapped permanents and +1/+1 or -1/-1 counters on requested battlefield "
                + "permanents, set at the requested checkpoint through the game-load path and "
                + "verified engine-direct");
        supported.add("loyalty counters on a requested battlefield planeswalker, set exactly as "
                + "it enters at the first-turn placement (before the first state-based action "
                + "check, CR 704.5i) and verified engine-direct at the checkpoint");
        supported.addAll(XmageLosslessHiddenPlan.supportedDescriptor());
        payload.add("supported_dimensions", supported);
        JsonArray unsupported = new JsonArray();
        unsupported.add("stack spells without a record declaration of an already-fully-cast "
                + "spell (NATIVE_RESUME_WITH_FULLY_CAST_STACK_SPELL with cast_complete and "
                + "costs_paid; anything else needs real casting costs/timing: executor scope)");
        unsupported.add("cast events and cast history (SpellsCastWatcher) for a record-declared "
                + "already-fully-cast stack spell: the resume fabricates neither a cast event "
                + "nor a cast count, so any row depending on either observation fails closed");
        unsupported.add("a resumed stack spell that was not castable at the record's declared "
                + "temporal state (UNSUPPORTED_RESUME_TIMING), an undeclared cast-from zone "
                + "(UNDECLARED_RESUME_CAST_ZONE), variable/optional/additional costs "
                + "(UNSUPPORTED_RESUME_COST), or more than one declared stack entry or "
                + "stack-zone object (UNSUPPORTED_RESUME_STACK_AMBIGUITY)");
        unsupported.add("legacy/frozen partial library identity: no complete permutation, fail closed");
        unsupported.add("legacy/frozen face_down=true without explicit native type: fail closed");
        unsupported.add("revealed-zone restoration");
        unsupported.add("controller/owner divergence (engine layers re-derive control)");
        unsupported.add("battlefield commanders whose permanent is another face or part "
                + "(modal double-faced, transforming): refused before game start "
                + "(UNSUPPORTED_COMMANDER_FACE)");
        unsupported.add("attachments (aura/equipment attachment relations)");
        unsupported.add("counters other than +1/+1, -1/-1 and loyalty, counters on commanders or "
                + "on objects off the battlefield, and loyalty on a permanent that is not a "
                + "first-turn placement");
        unsupported.add("commander relations other than validated Partner linkage");
        unsupported.add("poison counters");
        unsupported.add("temporal points outside the qualified RG-03 checkpoint allow-list "
                + "(turn 1 as declared, or the turn-2 precombat main)");
        unsupported.add("frozen requested_state_digest reproduction (no canonicalization spec in repo)");
        payload.add("unsupported_dimensions", unsupported);
        return payload;
    }

    private void requireApplied() {
        if (!preStartApplied) {
            throw new RestorationException(
                    "NOT_APPLIED", "applyPreStart must run before post-arrival steps");
        }
    }

    private static Player requirePlayer(Map<String, Player> playersByPid, String pid) {
        Player player = playersByPid.get(pid);
        if (player == null) {
            throw new RestorationException("UNKNOWN_ACTOR", pid);
        }
        return player;
    }

    private static Card takeVehicleCard(
            Map<String, List<Card>> vehicleByName, Set<Card> consumed, RequestedObject object) {
        List<Card> pool = vehicleByName.getOrDefault(object.cardIdentity(), List.of());
        for (Card card : pool) {
            if (consumed.add(card)) {
                return card;
            }
        }
        throw new RestorationException(
                "VEHICLE_SHORTAGE",
                "no unconsumed " + object.cardIdentity() + " for " + object.semanticId());
    }

    private String multisetKey(RequestedObject object) {
        return object.owner() + "|" + object.zone().name() + "|"
                + object.cardIdentity() + "|tapped=" + object.tapped()
                + "|controller=" + object.controller();
    }

    private static boolean isHandKey(String multisetKey) {
        return multisetKey.contains("|" + Zone.HAND.name() + "|");
    }

    private static void collectZone(
            JsonObject seat, String array, String pid, Map<String, Integer> counts) {
        for (JsonElement element : seat.getAsJsonArray(array)) {
            String identity;
            boolean tapped = false;
            String controller = pid;
            if (element.isJsonObject()) {
                JsonObject entry = element.getAsJsonObject();
                identity = entry.get("card_identity").getAsString();
                tapped = entry.get("tapped").getAsBoolean();
                controller = entry.get("controller").getAsString();
            } else {
                identity = element.getAsString();
            }
            String zone = switch (array) {
                case "battlefield" -> Zone.BATTLEFIELD.name();
                case "graveyard" -> Zone.GRAVEYARD.name();
                case "exile" -> Zone.EXILED.name();
                case "hand" -> Zone.HAND.name();
                default -> throw new RestorationException("INVALID_ZONE_ARRAY", array);
            };
            counts.merge(pid + "|" + zone + "|" + identity + "|tapped=" + tapped
                    + "|controller=" + controller, 1, Integer::sum);
        }
    }

    private static String pidOf(UUID id, Map<String, Player> playersByPid) {
        for (Map.Entry<String, Player> entry : playersByPid.entrySet()) {
            if (entry.getValue().getId().equals(id)) {
                return entry.getKey();
            }
        }
        return "unknown:" + id;
    }

    private static void expect(
            String field, int observed, int requested, List<String> mismatches) {
        if (observed != requested) {
            mismatches.add(field + ": requested " + requested + " observed " + observed);
        }
    }

    private static void expectText(
            String field, String observed, String requested, List<String> mismatches) {
        if (!observed.equals(requested)) {
            mismatches.add(field + ": requested " + requested + " observed " + observed);
        }
    }

    private JsonObject canonicalRequested() {
        JsonObject root = new JsonObject();
        root.addProperty("plan_id", plan.planId());
        root.addProperty("turn_number", plan.turnNumber());
        root.addProperty("phase", plan.phase().name());
        root.addProperty("step", plan.step().name());
        root.addProperty("active_player", plan.activePlayer());
        root.addProperty("priority_player", plan.priorityPlayer());
        root.addProperty("seed", plan.seed());
        JsonArray seats = new JsonArray();
        Map<String, List<RequestedObject>> byOwner = new HashMap<>();
        for (RequestedObject object : plan.objects()) {
            byOwner.computeIfAbsent(object.owner(), key -> new ArrayList<>()).add(object);
        }
        Map<String, List<RequestedCommander>> commandersByOwner = new HashMap<>();
        for (RequestedCommander commander : plan.commanders()) {
            commandersByOwner.computeIfAbsent(commander.owner(), key -> new ArrayList<>())
                    .add(commander);
        }
        List<RequestedPlayer> ordered = new ArrayList<>(plan.players());
        ordered.sort(Comparator.comparing(RequestedPlayer::playerId));
        for (RequestedPlayer player : ordered) {
            JsonObject seat = new JsonObject();
            seat.addProperty("player_id", player.playerId());
            seat.addProperty("life", player.life());
            JsonArray commanders = new JsonArray();
            List<RequestedCommander> owned = new ArrayList<>(
                    commandersByOwner.getOrDefault(player.playerId(), List.of()));
            owned.sort(Comparator.comparing(RequestedCommander::commanderId));
            for (RequestedCommander commander : owned) {
                JsonObject entry = new JsonObject();
                entry.addProperty("card_identity", commander.cardIdentity());
                entry.addProperty("prior_casts", commander.priorCasts());
                commanders.add(entry);
            }
            seat.add("commanders", commanders);
            Map<String, Integer> multisets = new TreeMap<>();
            for (RequestedObject object : byOwner.getOrDefault(player.playerId(), List.of())) {
                multisets.merge(multisetKey(object), 1, Integer::sum);
            }
            JsonArray zones = new JsonArray();
            for (Map.Entry<String, Integer> entry : multisets.entrySet()) {
                zones.add(entry.getKey() + "x" + entry.getValue());
            }
            seat.add("zones", zones);
            seats.add(seat);
        }
        root.add("seats", seats);
        return root;
    }

    static String digestJson(JsonObject payload) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(payload.toString().getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(hash.length * 2);
            for (byte value : hash) {
                hex.append(String.format("%02x", value));
            }
            return hex.toString();
        } catch (Exception exc) {
            throw new RestorationException("DIGEST_FAILED", String.valueOf(exc.getMessage()));
        }
    }

    private static int intOr(mage.MageInt value, int fallback) {
        return value == null ? fallback : value.getValue();
    }

    private static void sortObjectsBy(JsonArray array, String property) {
        List<JsonObject> items = new ArrayList<>();
        for (JsonElement element : array) {
            items.add(element.getAsJsonObject());
        }
        items.sort(Comparator.comparing(item -> item.get(property).getAsString()));
        for (int index = 0; index < items.size(); index++) {
            array.set(index, items.get(index));
        }
    }

    private static void sortStrings(JsonArray array) {
        List<String> items = new ArrayList<>();
        for (JsonElement element : array) {
            items.add(element.getAsString());
        }
        Collections.sort(items);
        for (int index = 0; index < items.size(); index++) {
            array.set(index, new com.google.gson.JsonPrimitive(items.get(index)));
        }
    }

    /**
     * Frozen digest spec {@code commander-lab.requested-state-digest/1.0.0}
     * (recovered from the frozen WS47 tree): SHA-256 over UTF-8 bytes of
     * canonical JSON (object keys sorted, compact separators, non-ASCII
     * unescaped) of the record projected to the spec's key list with absent
     * keys omitted. Reproduces all 135 frozen digests exactly.
     */
    static final List<String> DIGEST_PROJECTION_KEYS = List.of(
            "execution_entry_mode", "players", "deck_state", "commander_state",
            "semantic_objects", "temporal_state", "knowledge_state", "rules_randomness",
            "combat_state", "stack_state", "continuous_rules_effects", "extra_turn_creation",
            "elimination_trigger", "zone_move_event", "setup_validation");

    /** Canonical JSON writer matching the frozen spec byte-for-byte. */
    static String canonicalJson(JsonElement element) {
        StringBuilder out = new StringBuilder();
        appendCanonical(element, out);
        return out.toString();
    }

    private static void appendCanonical(JsonElement element, StringBuilder out) {
        if (element == null || element.isJsonNull()) {
            out.append("null");
        } else if (element.isJsonObject()) {
            out.append('{');
            TreeMap<String, JsonElement> sorted = new TreeMap<>();
            for (Map.Entry<String, JsonElement> entry
                    : element.getAsJsonObject().entrySet()) {
                sorted.put(entry.getKey(), entry.getValue());
            }
            boolean first = true;
            for (Map.Entry<String, JsonElement> entry : sorted.entrySet()) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                appendQuoted(entry.getKey(), out);
                out.append(':');
                appendCanonical(entry.getValue(), out);
            }
            out.append('}');
        } else if (element.isJsonArray()) {
            out.append('[');
            boolean first = true;
            for (JsonElement item : element.getAsJsonArray()) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                appendCanonical(item, out);
            }
            out.append(']');
        } else if (element.isJsonPrimitive()) {
            com.google.gson.JsonPrimitive primitive = element.getAsJsonPrimitive();
            if (primitive.isString()) {
                appendQuoted(primitive.getAsString(), out);
            } else if (primitive.isBoolean()) {
                out.append(primitive.getAsBoolean() ? "true" : "false");
            } else if (primitive.isNumber()) {
                out.append(primitive.getAsString());
            } else {
                throw new RestorationException(
                        "UNCANONICAL_VALUE", "unsupported JSON primitive");
            }
        } else {
            throw new RestorationException(
                    "UNCANONICAL_VALUE", "unsupported JSON element");
        }
    }

    private static void appendQuoted(String value, StringBuilder out) {
        out.append('"');
        for (int index = 0; index < value.length(); index++) {
            char code = value.charAt(index);
            switch (code) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\f' -> out.append("\\f");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (code < 0x20) {
                        out.append(String.format("\\u%04x", (int) code));
                    } else {
                        out.append(code);
                    }
                }
            }
        }
        out.append('"');
    }

    /** Projects a frozen record to the digest spec keys (absent keys omitted). */
    static JsonObject projectRecord(JsonObject record) {
        JsonObject projected = new JsonObject();
        for (String key : DIGEST_PROJECTION_KEYS) {
            if (record.has(key)) {
                projected.add(key, record.get(key));
            }
        }
        return projected;
    }

    /** Frozen requested-state digest of a record (must equal its frozen hex). */
    static String requestedDigest(JsonObject record) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(canonicalJson(projectRecord(record))
                    .getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(hash.length * 2);
            for (byte value : hash) {
                hex.append(String.format("%02x", value));
            }
            return hex.toString();
        } catch (Exception exc) {
            throw new RestorationException("DIGEST_FAILED", String.valueOf(exc.getMessage()));
        }
    }

    /** Evidence-grade digest of a constructed projection (canonical form). */
    static String constructedDigest(JsonObject projection) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(canonicalJson(projection)
                    .getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(hash.length * 2);
            for (byte value : hash) {
                hex.append(String.format("%02x", value));
            }
            return hex.toString();
        } catch (Exception exc) {
            throw new RestorationException("DIGEST_FAILED", String.valueOf(exc.getMessage()));
        }
    }
}
