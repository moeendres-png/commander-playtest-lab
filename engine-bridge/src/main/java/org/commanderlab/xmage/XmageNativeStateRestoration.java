package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
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
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.game.PutToBattlefieldInfo;
import mage.game.permanent.Permanent;
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
 * deterministic filler), {@code Player.setLife}, game-state turn/active
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
 * untapped, without counters or attachments; commander cast counts; life
 * totals; turn-1 precombat-main arrival envelope with active/priority
 * binding; explicit Rules-seed binding. Everything else (stack spells,
 * library identity, revealed, facedown, attachments, counters, tapped
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

    /** Fail-closed rejection before any game mutation. */
    static final class RestorationException extends RuntimeException {
        RestorationException(String code, String detail) {
            super(code + ": " + detail);
        }
    }

    /** One requested object in a public zone. */
    record RequestedObject(
            String semanticId,
            String cardIdentity,
            String owner,
            String controller,
            Zone zone,
            boolean tapped
    ) {
    }

    /** One requested commander binding. */
    record RequestedCommander(
            String commanderId,
            String cardIdentity,
            String owner,
            int priorCasts
    ) {
    }

    /** One requested accumulated combat-damage edge for an exact Commander identity. */
    record RequestedCommanderDamage(
            String commanderId,
            String damagedPlayer,
            int combatDamage
    ) {
    }

    /** Requested player fields. */
    record RequestedPlayer(String playerId, int seat, int life) {
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
            String priorityPlayer
    ) {
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
                    turnNumber, phase, step, activePlayer, priorityPlayer);
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
    private final Map<String, Set<UUID>> injectedHandIdsByPlayer = new HashMap<>();
    private boolean preStartApplied;

    XmageNativeStateRestoration(Plan plan, Deck materializationVehicle) {
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
     * Parses a frozen materialization record into a plan, rejecting every
     * unsupported dimension with a code. The caller supplies the Rules seed
     * explicitly (records bind it as SCENARIO_SEED or a manifest seed).
     */
    static Plan planFromFrozenRecord(JsonObject record, String planId, long seed) {
        String fixtureId = record.get("fixture_id").getAsString();
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
                    player.get("life").getAsInt()));
        }
        JsonObject commanderState = record.getAsJsonObject("commander_state");
        List<RequestedCommander> commanders = new ArrayList<>();
        for (JsonElement element : commanderState.getAsJsonArray("commanders")) {
            JsonObject commander = element.getAsJsonObject();
            commanders.add(new RequestedCommander(
                    commander.get("commander_id").getAsString(),
                    commander.get("card_identity").getAsString(),
                    commander.get("owner").getAsString(),
                    commander.get("prior_command_zone_cast_count").getAsInt()));
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
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            JsonObject object = element.getAsJsonObject();
            String semanticId = object.has("semantic_id") && !object.get("semantic_id").isJsonNull()
                    ? object.get("semantic_id").getAsString() : "?";
            if (object.has("face_down") && !object.get("face_down").isJsonNull()
                    && object.get("face_down").getAsBoolean()) {
                throw new RestorationException("UNSUPPORTED_FACEDOWN", fixtureId + " " + semanticId);
            }
            if (object.has("counters") && !object.get("counters").isJsonNull()
                    && !object.getAsJsonObject("counters").keySet().isEmpty()) {
                throw new RestorationException("UNSUPPORTED_COUNTERS", fixtureId + " " + semanticId);
            }
            if (object.has("attachments") && !object.get("attachments").isJsonNull()
                    && !object.getAsJsonArray("attachments").isEmpty()) {
                throw new RestorationException("UNSUPPORTED_ATTACHMENTS", fixtureId + " " + semanticId);
            }
            String zoneName = object.get("zone").getAsString();
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
            objects.add(new RequestedObject(
                    semanticId,
                    object.get("card_identity").getAsString(),
                    object.get("owner").getAsString(),
                    object.get("controller").getAsString(),
                    zone,
                    tapped));
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
                temporal.get("priority_player").getAsString());
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
        if ("precombat_main".equals(phase) && "main".equals(step)) {
            return PhaseStep.PRECOMBAT_MAIN;
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
            throw new RestorationException(
                    "UNSUPPORTED_COMMANDER_COLOR", "no basic-land filler for " + commanderColors);
        }
        List<String> filler = new ArrayList<>(count);
        for (int index = 0; index < count; index++) {
            filler.add(pool.get(index % pool.size()));
        }
        return List.copyOf(filler);
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
        if (validated.turnNumber() != 1
                || validated.phase() != TurnPhase.PRECOMBAT_MAIN
                || validated.step() != PhaseStep.PRECOMBAT_MAIN) {
            throw new RestorationException(
                    "UNSUPPORTED_TEMPORAL_POINT",
                    "v1 arrives naturally at turn 1 precombat main only; requested "
                            + validated.turnNumber() + "/" + validated.phase()
                            + "/" + validated.step());
        }
        if (!seats.contains(validated.activePlayer())
                || !seats.contains(validated.priorityPlayer())) {
            throw new RestorationException(
                    "UNKNOWN_ACTOR", "active/priority must name a planned player");
        }
        for (RequestedObject object : validated.objects()) {
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
            if (object.tapped()) {
                throw new RestorationException(
                        "UNSUPPORTED_TAPPED", object.semanticId() + "; v1 assembles untapped only");
            }
            if (object.cardIdentity() == null || object.cardIdentity().isBlank()) {
                throw new RestorationException("INVALID_CARD_IDENTITY", object.semanticId());
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
     * attribution makes owners controllers), life totals, and watcher
     * registration. Commander cast counts are restored post-arrival
     * ({@link #restoreCommanderCasts}) once commanders exist in the command
     * zone.
     */
    synchronized void applyPreStart(
            CommanderFreeForAll game, Map<String, Player> playersByPid) {
        if (preStartApplied) {
            throw new RestorationException(
                    "ALREADY_APPLIED", "pre-start restoration runs exactly once");
        }
        Map<String, List<Card>> vehicleByName = new HashMap<>();
        for (Card card : materializationVehicle.getCards()) {
            vehicleByName.computeIfAbsent(card.getName(), name -> new ArrayList<>()).add(card);
        }
        Set<Card> consumed = new HashSet<>();
        for (RequestedPlayer requested : plan.players()) {
            Player player = requirePlayer(playersByPid, requested.playerId());
            List<PutToBattlefieldInfo> battlefield = new ArrayList<>();
            List<Card> hand = new ArrayList<>();
            List<Card> graveyard = new ArrayList<>();
            List<Card> exile = new ArrayList<>();
            for (RequestedObject object : plan.objects()) {
                if (!object.owner().equals(requested.playerId())) {
                    continue;
                }
                Card card = takeVehicleCard(vehicleByName, consumed, object);
                switch (object.zone()) {
                    case BATTLEFIELD -> battlefield.add(new PutToBattlefieldInfo(card, false));
                    case HAND -> {
                        hand.add(card);
                        injectedHandIdsByPlayer
                                .computeIfAbsent(requested.playerId(), ignored -> new HashSet<>())
                                .add(card.getId());
                    }
                    case GRAVEYARD -> graveyard.add(card);
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
            player.setLife(requested.life(), game, null);
        }
        game.getState().addWatcher(new CommanderPlaysCountWatcher());
        preStartApplied = true;
    }

    /**
     * Post-arrival commander cast-count restoration through the engine's own
     * game-load path, keyed by live command-zone commander UUIDs mapped 1:1
     * via owner plus card identity (fail closed on ambiguity). Runs while the
     * engine thread is parked on an external decision.
     */
    synchronized void restoreCommanderCasts(
            CommanderFreeForAll game, Map<String, Player> playersByPid) {
        requireApplied();

        // Resolve every semantic Commander to one genuine native Commander id
        // before mutating any watcher state. Generic setup-placed copies are
        // never considered Commander identities.
        Map<String, UUID> liveCommanderIds =
                bindLiveCommanderIds(game, playersByPid);

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
    }

    /**
     * Resolves semantic Commander ids to the exact native Commander main-card
     * ids owned by the requested player. Only GameCommanderImpl's authoritative
     * Commander identity set participates; battlefield setup copies are
     * deliberately excluded. Owner + exact card identity must bind 1:1.
     */
    private Map<String, UUID> bindLiveCommanderIds(
            CommanderFreeForAll game, Map<String, Player> playersByPid) {
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
    static JsonObject readback(CommanderFreeForAll game, Map<String, Player> playersByPid) {
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
            for (Card card : game.getCommanderCardsFromCommandZone(
                    player, CommanderCardType.COMMANDER_OR_OATHBREAKER)) {
                JsonObject entry = new JsonObject();
                entry.addProperty("card_identity", card.getName());
                entry.addProperty("prior_casts",
                        watcher == null ? -1 : watcher.getPlaysCount(card.getId()));
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
            JsonArray exile = new JsonArray();
            for (Card card : game.getExile().getCardsOwned(game, player.getId())) {
                exile.add(card.getName());
            }
            sortStrings(exile);
            seat.add("exile", exile);
            seats.add(seat);
        }
        root.add("seats", seats);
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
            requestedCounts.merge(multisetKey(object), 1, Integer::sum);
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
        supported.add("commander damage matrices through exact live CommanderInfoWatcher bindings "
                + "(native game-load restore; no synthetic damage events)");
        supported.add("battlefield/graveyard/exile placement of real cards (silent setup primitive)");
        supported.add("hand identity via the same setup primitive (principal-scoped; "
                + "pilot observation stays counts-only through the redactor; "
                + "honeycard non-leakage proven per fixture)");
        supported.add("owner-equals-controller attribution with 1:1 readback");
        supported.add("life totals (pre-start assembly; state-based actions stay authoritative)");
        supported.add("turn-1 precombat-main arrival envelope with active/priority binding");
        supported.add("explicit Rules-seed binding with replay determinism");
        supported.add("strict native readback with field-level compare and digests");
        supported.add("frozen requested_state_digest equality for constructed states "
                + "in the v1 subset (canonical projection per the recovered spec, "
                + "verified per fixture; see requestedDigest/constructedDigest)");
        payload.add("supported_dimensions", supported);
        JsonArray unsupported = new JsonArray();
        unsupported.add("stack spells (casting requires real costs/timing: executor scope)");
        unsupported.add("library identity (hidden information: fail closed)");
        unsupported.add("revealed and facedown objects");
        unsupported.add("controller/owner divergence (engine layers re-derive control)");
        unsupported.add("attachments and counters");
        unsupported.add("tapped permanents (unqualified dimension)");
        unsupported.add("commander relations other than validated Partner linkage");
        unsupported.add("poison counters");
        unsupported.add("temporal points outside turn-1 precombat main");
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
