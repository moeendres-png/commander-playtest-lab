package org.commanderlab.xmage;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.MageObject;
import mage.abilities.Ability;
import mage.cards.Card;
import mage.cards.Cards;
import mage.cards.CardsImpl;
import mage.cards.decks.Deck;
import mage.cards.decks.DeckCardInfo;
import mage.cards.decks.DeckCardLists;
import mage.cards.repository.CardInfo;
import mage.cards.repository.CardRepository;
import mage.constants.CommanderCardType;
import mage.constants.PhaseStep;
import mage.constants.TurnPhase;
import mage.counters.Counter;
import mage.counters.CounterType;
import mage.counters.Counters;
import mage.game.Game;
import mage.game.Revealed;
import mage.game.command.Commander;
import mage.game.permanent.Permanent;
import mage.game.stack.Spell;
import mage.game.stack.StackObject;
import mage.players.Player;
import mage.target.Target;
import mage.target.Targets;
import mage.watchers.common.CommanderInfoWatcher;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.UUID;

/**
 * WS74 XMage Full107 construction/readback staging harness.
 *
 * <p>New WS74-owned staging code. It REUSES the qualified CPL provider lane
 * ({@link XmageDeckImporter}, {@link XmageGameManager}, {@link XmageBridgePlayer})
 * read-only through the same package; it modifies no bridge, provider, or engine
 * source. One OS process may construct many fixtures sequentially, each in a
 * fresh native {@code CommanderFreeForAll} game with an explicit Rules seed
 * (cross-game isolation for this pattern was proven in WS54 and is spot-checked
 * by isolated single-fixture runs in {@code ws74_construct.py}).
 *
 * <p>Scope is construction + readback ONLY. The harness never submits an
 * external decision, never passes priority, never casts through gameplay, never
 * resolves, never declares attackers/blockers, never advances turns/steps, and
 * never applies loss/elimination. Anything beyond direct native state placement
 * is recorded with an exact failure code for terminal adjudication.
 */
public final class Ws74StagingHarness {

    static final String ENGINE_COMMIT = "7135d5e85ddb4c8aa4b49b4192ca51947c822704";
    static final String ENGINE_TREE = "ea193e0d04493d53d962ed13ebd3b5d2f68838c7";
    static final String ENGINE_REPO = "moeendres-png/mage";
    static final String HARNESS_SCHEMA = "ws74.xmage-construction-readback/1.0.0";
    static final String FILLER_CARD_NAME = "Wastes";

    private Ws74StagingHarness() {
    }

    // ------------------------------------------------------------------ model

    private record SemanticObject(
            String semanticId,
            String cardIdentity,
            String owner,
            String controller,
            String zone,
            boolean faceDown,
            boolean tapped,
            Map<String, Integer> counters,
            int zonePosition, // -1 when absent
            String commanderId // null when absent
    ) {
    }

    private record PlayerSpec(String playerId, int seat, int life, int startingLife) {
    }

    private record PlacementLedger(String semanticId, String nativeId, String zone) {
    }

    private record FailedPlacement(String semanticId, String code, String detail) {
    }

    // ------------------------------------------------------------------ entry

    public static void main(String[] args) throws Exception {
        Map<String, String> cli = parseArgs(args);
        String materializationPath = require(cli, "materialization");
        String denominatorPath = require(cli, "denominator");
        String outDir = require(cli, "out");
        String cplCommit = require(cli, "cpl-commit");
        String cplTree = require(cli, "cpl-tree");
        String only = cli.get("only");

        String matRaw = Files.readString(new File(materializationPath).toPath(), StandardCharsets.UTF_8);
        String denRaw = Files.readString(new File(denominatorPath).toPath(), StandardCharsets.UTF_8);
        Gson gson = new Gson();
        JsonObject mat = gson.fromJson(matRaw, JsonObject.class);
        JsonObject den = gson.fromJson(denRaw, JsonObject.class);

        Map<String, JsonObject> byId = new HashMap<>();
        for (var e : mat.getAsJsonArray("records")) {
            JsonObject r = e.getAsJsonObject();
            byId.put(r.get("fixture_id").getAsString(), r);
        }
        List<String> ids = new ArrayList<>();
        for (var e : den.getAsJsonArray("fixture_ids")) {
            ids.add(e.getAsString());
        }

        new File(outDir).mkdirs();
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);

        int constructed = 0;
        int failed = 0;
        for (String fid : ids) {
            if (only != null && !only.equals(fid)) {
                continue;
            }
            JsonObject record = byId.get(fid);
            JsonObject readback;
            try {
                readback = constructOne(manager, importer, fid, record, cplCommit, cplTree, gson);
            } catch (Exception exc) {
                readback = fatalReadback(fid, record, cplCommit, cplTree, exc);
            }
            String result = readback.getAsJsonObject("construction").get("result").getAsString();
            if ("CONSTRUCTED".equals(result)) {
                constructed++;
            } else {
                failed++;
            }
            Gson pretty = new GsonBuilder().setPrettyPrinting().create();
            Files.writeString(
                    new File(outDir + "/" + fid + ".json").toPath(),
                    pretty.toJson(readback),
                    StandardCharsets.UTF_8);
            System.out.println("WS74_CONSTRUCT " + fid + " " + result + " "
                    + readback.getAsJsonObject("construction").get("code").getAsString());
            System.out.flush();
        }
        System.out.println("WS74_CONSTRUCT_SUMMARY constructed=" + constructed + " failed=" + failed);
    }

    private static Map<String, String> parseArgs(String[] args) {
        Map<String, String> cli = new HashMap<>();
        for (int i = 0; i < args.length; i++) {
            if (args[i].startsWith("--") && i + 1 < args.length) {
                cli.put(args[i].substring(2), args[i + 1]);
                i++;
            }
        }
        return cli;
    }

    private static String require(Map<String, String> cli, String key) {
        String value = cli.get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("WS74_MISSING_CLI_ARG:" + key);
        }
        return value;
    }

    // ------------------------------------------------------------- construction

    private static JsonObject constructOne(
            XmageGameManager manager,
            XmageDeckImporter importer,
            String fid,
            JsonObject record,
            String cplCommit,
            String cplTree,
            Gson gson) {
        JsonObject construction = new JsonObject();
        List<PlacementLedger> ledger = new ArrayList<>();
        List<FailedPlacement> failed = new ArrayList<>();
        Map<String, String> fillerUuids = new LinkedHashMap<>(); // nativeId -> playerId
        String code = "CONSTRUCTED_OK";
        String entryMode = str(record, "execution_entry_mode");

        JsonObject readback = new JsonObject();
        readback.addProperty("schema_version", HARNESS_SCHEMA);
        readback.addProperty("fixture_id", fid);
        readback.addProperty("contract_digest", str(record, "requested_state_digest"));
        readback.addProperty("execution_entry_mode", entryMode);

        JsonObject provenance = new JsonObject();
        provenance.addProperty("engine_repository", ENGINE_REPO);
        provenance.addProperty("engine_commit", ENGINE_COMMIT);
        provenance.addProperty("engine_tree", ENGINE_TREE);
        provenance.addProperty("cpl_commit", cplCommit);
        provenance.addProperty("cpl_tree", cplTree);
        provenance.addProperty("provider_lane", "XmageGameManager+XmageBridgePlayer(external_control)+XmageActionExecutor(startup-passes-only)");
        long rulesSeed = 424242L;
        if (record.has("rules_randomness")
                && record.getAsJsonObject("rules_randomness").has("rules_seed")) {
            rulesSeed = record.getAsJsonObject("rules_randomness").get("rules_seed").getAsLong();
        }
        provenance.addProperty("rules_seed", rulesSeed);
        provenance.add("runtime_jar_digests", runtimeJarDigests());
        readback.add("provenance", provenance);

        // ---- player specs
        List<PlayerSpec> specs = new ArrayList<>();
        if (!record.has("players") || record.getAsJsonArray("players").size() == 0) {
            return failReadback(readback, construction, ledger, failed, fillerUuids,
                    "RECORD_MISSING_PLAYERS", fid);
        }
        for (var e : record.getAsJsonArray("players")) {
            JsonObject p = e.getAsJsonObject();
            specs.add(new PlayerSpec(
                    p.get("player_id").getAsString(),
                    p.get("seat").getAsInt(),
                    p.get("life").getAsInt(),
                    p.get("starting_life").getAsInt()));
        }
        specs.sort(Comparator.comparingInt(PlayerSpec::seat));
        if (specs.size() < 2 || specs.size() > 5) {
            return failReadback(readback, construction, ledger, failed, fillerUuids,
                    "INVALID_PLAYER_COUNT_FOR_ENGINE", "players=" + specs.size());
        }
        int startingLife = specs.get(0).startingLife();
        for (PlayerSpec s : specs) {
            if (s.startingLife() != startingLife) {
                return failReadback(readback, construction, ledger, failed, fillerUuids,
                        "MIXED_STARTING_LIFE", s.playerId());
            }
        }

        // ---- commanders per player (all zones: deck import needs every
        // ---- commander identity; battlefield commanders are relocated below)
        Map<String, List<String>> commandersByPlayer = new HashMap<>();
        if (record.has("commander_state") && record.getAsJsonObject("commander_state").has("commanders")) {
            for (var e : record.getAsJsonObject("commander_state").getAsJsonArray("commanders")) {
                JsonObject c = e.getAsJsonObject();
                commandersByPlayer
                        .computeIfAbsent(str(c, "owner"), k -> new ArrayList<>())
                        .add(str(c, "card_identity"));
            }
        }

        // ---- import decks (commander(s) + filler)
        List<String> deckHandles = new ArrayList<>();
        List<String> deckPlayerIds = new ArrayList<>();
        try {
            for (PlayerSpec s : specs) {
                List<String> commanders = commandersByPlayer.getOrDefault(s.playerId(), List.of());
                if (commanders.isEmpty()) {
                    return failReadback(readback, construction, ledger, failed, fillerUuids,
                            "NO_COMMANDER_FOR_PLAYER", s.playerId());
                }
                List<String> mainboard = new ArrayList<>();
                int filler = 100 - commanders.size();
                if (filler < 0) {
                    return failReadback(readback, construction, ledger, failed, fillerUuids,
                            "TOO_MANY_COMMANDERS", s.playerId());
                }
                for (int i = 0; i < filler; i++) {
                    mainboard.add(FILLER_CARD_NAME);
                }
                XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                        "ws74-" + fid + "-" + s.playerId(),
                        shaHex(("ws74-" + fid + "-" + s.playerId()).getBytes(StandardCharsets.UTF_8)),
                        mainboard,
                        commanders);
                deckHandles.add(imported.deckHandle());
                deckPlayerIds.add(s.playerId());
            }
        } catch (RuntimeException exc) {
            return failReadback(readback, construction, ledger, failed, fillerUuids,
                    "DECK_IMPORT_FAILED", rootMessage(exc));
        }

        // ---- create + seed + start (external-control lane: the game pauses at
        // ---- the first startup priority; staging then completes game startup to
        // ---- the contractual load boundary, see advanceStartup below)
        String gameHandle;
        Game game;
        try {
            var created = manager.createCommanderGame(
                    "ws74-" + fid, deckHandles, 0, startingLife, true);
            gameHandle = created.gameHandle();
            game = manager.requireGame(gameHandle);
            game.setRulesSeed(rulesSeed);
            game.setRequireExplicitSeed(true);
            manager.startGame(gameHandle);
        } catch (RuntimeException exc) {
            return failReadback(readback, construction, ledger, failed, fillerUuids,
                    "GAME_CREATE_OR_START_FAILED", rootMessage(exc));
        }

        // ---- seat mapping: deck order == spec order == seats (needed by startup)
        Map<String, UUID> playerUuidByPid = new HashMap<>();
        Map<UUID, String> pidByUuid = new HashMap<>();
        {
            Collection<? extends Player> live = game.getPlayers().values();
            if (live.size() != specs.size()) {
                return failReadback(readback, construction, ledger, failed, fillerUuids,
                        "PLAYER_COUNT_MISMATCH_AFTER_START", String.valueOf(live.size()));
            }
            List<Player> inSeatOrder = new ArrayList<>(live);
            // Players is a LinkedHashMap: iteration order is creation order, which
            // follows deck order (positional seat mapping). The starting-player pin
            // below verifies position 0 independently of this ordering assumption.
            for (int i = 0; i < specs.size(); i++) {
                playerUuidByPid.put(specs.get(i).playerId(), inSeatOrder.get(i).getId());
                pidByUuid.put(inSeatOrder.get(i).getId(), specs.get(i).playerId());
            }
            if (!inSeatOrder.get(0).getId().equals(game.getStartingPlayerId())) {
                return failReadback(readback, construction, ledger, failed, fillerUuids,
                        "STARTING_PLAYER_PIN_FAILED", "seat0 != starting player");
            }
        }

        // ---- complete game startup to the contractual load boundary
        // ---- (precombat main, turn 1, active P1, priority P1)
        String startupFailure = advanceStartup(manager, gameHandle, game, specs, playerUuidByPid,
                ledger, failed, construction);
        if (startupFailure != null) {
            return failReadback(readback, construction, ledger, failed, fillerUuids,
                    startupFailure, "startup");
        }

        // ---- verify commanders landed (positional seat check via commander identity)
        if (!verifyCommanders(game, specs, commandersByPlayer, playerUuidByPid, pidByUuid)) {
            return failReadback(readback, construction, ledger, failed, fillerUuids,
                    "COMMANDER_ZONE_IDENTITY_MISMATCH", "positional seat mapping rejected");
        }

        // ---- filler ledger (every Wastes in hands/libraries is tracked setup noise)
        try {
            for (PlayerSpec s : specs) {
                Player p = game.getPlayer(playerUuidByPid.get(s.playerId()));
                for (UUID id : p.getLibrary().getCardList()) {
                    Card c = game.getCard(id);
                    if (c == null || !FILLER_CARD_NAME.equals(c.getName())) {
                        return failReadback(readback, construction, ledger, failed, fillerUuids,
                                "FILLER_IDENTITY_VIOLATION", "library:" + s.playerId());
                    }
                    fillerUuids.put(id.toString(), s.playerId());
                }
                for (Card c : p.getHand().getCards(game)) {
                    if (!FILLER_CARD_NAME.equals(c.getName())) {
                        return failReadback(readback, construction, ledger, failed, fillerUuids,
                                "FILLER_IDENTITY_VIOLATION", "hand:" + s.playerId());
                    }
                    fillerUuids.put(c.getId().toString(), s.playerId());
                }
            }
        } catch (RuntimeException exc) {
            return failReadback(readback, construction, ledger, failed, fillerUuids,
                    "FILLER_LEDGER_FAILED", rootMessage(exc));
        }

        // ---- parse semantic objects
        List<SemanticObject> objects = parseObjects(record);

        // ---- life totals (requested state; no loss applied, no SBA run)
        try {
            for (PlayerSpec s : specs) {
                if (s.life() != s.startingLife()) {
                    Player p = game.getPlayer(playerUuidByPid.get(s.playerId()));
                    p.setLife(s.life(), game, null);
                }
            }
        } catch (RuntimeException exc) {
            return failReadback(readback, construction, ledger, failed, fillerUuids,
                    "LIFE_SET_FAILED", rootMessage(exc));
        }

        // ---- commander damage restore (in-pin state-restoration API; no events fired)
        try {
            code = restoreCommanderDamage(game, record, playerUuidByPid, ledger, failed);
            if (code != null) {
                return failReadback(readback, construction, ledger, failed, fillerUuids,
                        code, "commander_damage");
            }
        } catch (RuntimeException exc) {
            return failReadback(readback, construction, ledger, failed, fillerUuids,
                    "COMMANDER_DAMAGE_RESTORE_FAILED", rootMessage(exc));
        }

        // ---- place state objects (non-library first; library last, descending position)
        // ---- battlefield commanders relocate their deck copies (no duplication)
        Set<String> consumedCommanderCopies = new HashSet<>();
        List<SemanticObject> libs = new ArrayList<>();
        for (SemanticObject o : objects) {
            if ("library".equals(o.zone())) {
                libs.add(o);
            } else if ("command".equals(o.zone()) && o.commanderId() != null) {
                // already verified in command zone via decks; ledger-map it
                String nativeId = findCommanderNativeId(game, o, playerUuidByPid, consumedCommanderCopies);
                if (nativeId == null) {
                    failed.add(new FailedPlacement(o.semanticId(), "COMMANDER_NOT_FOUND", o.cardIdentity()));
                } else {
                    consumedCommanderCopies.add(nativeId);
                    ledger.add(new PlacementLedger(o.semanticId(), nativeId, "command"));
                }
            } else if ("battlefield".equals(o.zone()) && o.commanderId() != null) {
                relocateCommander(game, o, playerUuidByPid, consumedCommanderCopies, ledger, failed);
            } else if ("stack".equals(o.zone()) || "revealed".equals(o.zone())) {
                // staged after base placement (needs ledgers for targets)
                libs.add(o); // reuse list as deferred; filtered below
            } else {
                placeOne(game, o, playerUuidByPid, ledger, failed);
            }
        }
        List<SemanticObject> deferred = new ArrayList<>();
        List<SemanticObject> libOnly = new ArrayList<>();
        for (SemanticObject o : libs) {
            if ("library".equals(o.zone())) {
                libOnly.add(o);
            } else {
                deferred.add(o);
            }
        }
        libOnly.sort((a, b) -> Integer.compare(b.zonePosition(), a.zonePosition()));
        for (SemanticObject o : libOnly) {
            placeOne(game, o, playerUuidByPid, ledger, failed);
        }

        // ---- stack spells + revealed (direct native state load; nothing resolved)
        // ---- stack spells go in requested stack_state order (digest order);
        // ---- fixpoint: stack spells may target other stack spells
        Map<String, JsonObject> stackBySemantic = indexStackState(record);
        List<SemanticObject> pendingStack = new ArrayList<>();
        Map<String, SemanticObject> stackObjBySem = new HashMap<>();
        for (SemanticObject o : deferred) {
            if ("stack".equals(o.zone())) {
                stackObjBySem.put(o.semanticId(), o);
            } else if ("revealed".equals(o.zone())) {
                int pos = o.zonePosition() >= 0 ? o.zonePosition() : -1;
                placeRevealed(game, o, playerUuidByPid, ledger, failed, pos);
            }
        }
        if (record.has("stack_state")) {
            for (var e : record.getAsJsonArray("stack_state")) {
                JsonObject s = e.getAsJsonObject();
                if (s.has("source_semantic_id")) {
                    SemanticObject o = stackObjBySem.remove(s.get("source_semantic_id").getAsString());
                    if (o != null) {
                        pendingStack.add(o);
                    }
                }
            }
        }
        // any stack object without a stack_state entry goes last
        pendingStack.addAll(stackObjBySem.values());
        Set<String> attemptedStack = new HashSet<>();
        boolean progress = true;
        while (!pendingStack.isEmpty() && progress) {
            progress = false;
            var it = pendingStack.iterator();
            while (it.hasNext()) {
                SemanticObject o = it.next();
                int failsBefore = failed.size();
                placeStackSpell(game, o, stackBySemantic.get(o.semanticId()),
                        playerUuidByPid, ledger, failed);
                if (failed.size() == failsBefore) {
                    it.remove();
                    progress = true;
                } else {
                    FailedPlacement last = failed.get(failed.size() - 1);
                    // target-unresolved spells retry in a later pass (dependency order);
                    // every other failure is terminal for that spell.
                    if (last.code().startsWith("TARGET_UNRESOLVABLE")) {
                        failed.remove(failed.size() - 1);
                    } else {
                        it.remove();
                    }
                }
            }
        }
        for (SemanticObject o : pendingStack) {
            failed.add(new FailedPlacement(o.semanticId(), "STACK_TARGET_DEADLOCK", o.cardIdentity()));
        }

        // ---- knowledge procedures with native traces (look / reveal only; no decisions)
        performKnowledgeGrants(game, record, playerUuidByPid, specs, ledger, failed);

        if (!failed.isEmpty()) {
            return failReadback(readback, construction, ledger, failed, fillerUuids,
                    "OBJECT_PLACEMENT_INCOMPLETE", failed.get(0).semanticId() + ":" + failed.get(0).code());
        }

        // ---- readback
        try {
            readback.add("game", gameBlock(game, specs, playerUuidByPid));
            readback.add("players", playersBlock(game, specs, playerUuidByPid));
            readback.add("views", viewsBlock(game, specs, playerUuidByPid));
            readback.add("stack", stackBlock(game));
            readback.add("revealed", revealedBlock(game));
            readback.add("looked_at", lookedAtBlock(game, specs, playerUuidByPid));
            readback.add("commander_plays", commanderPlaysBlock(game, specs, playerUuidByPid));
            readback.add("commander_damage", commanderDamageBlock(game, specs, playerUuidByPid));
        } catch (RuntimeException exc) {
            return failReadback(readback, construction, ledger, failed, fillerUuids,
                    "READBACK_FAILED", rootMessage(exc));
        }

        construction.addProperty("result", "CONSTRUCTED");
        construction.addProperty("code", "CONSTRUCTED_OK");
        attachLedgers(construction, ledger, failed, fillerUuids, specs, objects);
        readback.add("construction", construction);

        // ---- shutdown (release deck claims; game object retained for readback data already copied)
        try {
            manager.shutdownGame(gameHandle);
        } catch (RuntimeException exc) {
            return failReadback(readback, construction, ledger, failed, fillerUuids,
                    "SHUTDOWN_FAILED", rootMessage(exc));
        }
        return readback;
    }

    // ------------------------------------------------------------- placement

    private static Card instantiateCard(String cardIdentity) {
        CardInfo info = CardRepository.instance.findCard(cardIdentity, true);
        if (info == null) {
            throw new IllegalStateException("UNKNOWN_CARD_NAME:" + cardIdentity);
        }
        if (!cardIdentity.equals(info.getName())) {
            throw new IllegalStateException("CARD_IDENTITY_MISMATCH:" + cardIdentity + "->" + info.getName());
        }
        DeckCardLists lists = new DeckCardLists();
        lists.getCards().add(new DeckCardInfo(info.getName(), info.getCardNumber(), info.getSetCode()));
        Deck deck;
        try {
            deck = Deck.load(lists, false, false);
        } catch (Exception exc) {
            throw new IllegalStateException("CARD_INSTANTIATION_FAILED:" + cardIdentity + ":" + exc.getMessage(), exc);
        }
        if (deck.getCards().size() != 1) {
            throw new IllegalStateException("CARD_INSTANTIATION_COUNT:" + cardIdentity);
        }
        return deck.getCards().iterator().next();
    }

    private static mage.constants.Zone toNativeZone(String zone, List<FailedPlacement> failed, String semanticId) {
        return switch (zone) {
            case "hand" -> mage.constants.Zone.HAND;
            case "battlefield" -> mage.constants.Zone.BATTLEFIELD;
            case "graveyard" -> mage.constants.Zone.GRAVEYARD;
            case "exile" -> mage.constants.Zone.EXILED;
            case "library" -> mage.constants.Zone.LIBRARY;
            case "command" -> mage.constants.Zone.COMMAND;
            default -> {
                failed.add(new FailedPlacement(semanticId, "UNSUPPORTED_ZONE:" + zone, zone));
                yield null;
            }
        };
    }

    private static void placeOne(
            Game game,
            SemanticObject o,
            Map<String, UUID> playerUuidByPid,
            List<PlacementLedger> ledger,
            List<FailedPlacement> failed) {
        mage.constants.Zone zone = toNativeZone(o.zone(), failed, o.semanticId());
        if (zone == null) {
            return;
        }
        UUID ownerId = playerUuidByPid.get(o.owner());
        UUID controllerId = playerUuidByPid.get(o.controller());
        if (ownerId == null || controllerId == null) {
            failed.add(new FailedPlacement(o.semanticId(), "UNKNOWN_ACTOR", o.owner() + "/" + o.controller()));
            return;
        }
        Card card;
        try {
            card = instantiateCard(o.cardIdentity());
        } catch (RuntimeException exc) {
            failed.add(new FailedPlacement(o.semanticId(), "INSTANTIATION_FAILED", rootMessage(exc)));
            return;
        }
        try {
            Set<Card> one = new LinkedHashSet<>();
            one.add(card);
            game.loadCards(one, ownerId);
            Player mover = game.getPlayer(controllerId);
            boolean moved;
            if (zone == mage.constants.Zone.BATTLEFIELD) {
                moved = mover.moveCards(card, zone, null, game, o.tapped(), o.faceDown(), false, null);
            } else if (zone == mage.constants.Zone.LIBRARY) {
                // toTop=true; caller inserts in descending position order for exactness
                moved = mover.moveCardToLibraryWithInfo(card, null, game,
                        game.getState().getZone(card.getId()), true, false);
            } else if (zone == mage.constants.Zone.EXILED && o.faceDown()) {
                // face-down exile: battlefield-first so the engine marks the card
                // face down, then exile (708.9 reveal is log-only; views stay concealed).
                boolean bf = mover.moveCards(card, mage.constants.Zone.BATTLEFIELD, null, game,
                        false, true, false, null);
                if (!bf) {
                    failed.add(new FailedPlacement(o.semanticId(), "FACEDOWN_STAGING_FAILED", o.cardIdentity()));
                    return;
                }
                moved = mover.moveCards(card, zone, null, game, false, false, false, null);
            } else {
                moved = mover.moveCards(card, zone, null, game, false, o.faceDown(), false, null);
            }
            if (!moved) {
                failed.add(new FailedPlacement(o.semanticId(), "MOVE_REJECTED:" + o.zone(), o.cardIdentity()));
                return;
            }
            UUID nativeId = card.getId();
            if (zone == mage.constants.Zone.BATTLEFIELD) {
                Permanent perm = game.getPermanent(card.getId());
                if (perm == null) {
                    // face-down permanents are still permanents; anything else is a defect
                    if (!card.isFaceDown(game)) {
                        failed.add(new FailedPlacement(o.semanticId(), "NO_PERMANENT_AFTER_ETB", o.cardIdentity()));
                        return;
                    }
                } else {
                    nativeId = perm.getId();
                    if (!o.counters().isEmpty()) {
                        for (Map.Entry<String, Integer> ce : o.counters().entrySet()) {
                            if (ce.getValue() == null || ce.getValue() <= 0) {
                                continue;
                            }
                            Counter counter = counterInstance(ce.getKey(), ce.getValue());
                            if (counter == null) {
                                failed.add(new FailedPlacement(
                                        o.semanticId(), "UNKNOWN_COUNTER_TYPE", ce.getKey()));
                                nativeId = null;
                                break;
                            }
                            boolean added = perm.addCounters(
                                    counter, controllerId, null, game);
                            if (!added) {
                                failed.add(new FailedPlacement(
                                        o.semanticId(), "COUNTER_REJECTED", ce.getKey()));
                                nativeId = null;
                                break;
                            }
                        }
                        if (nativeId == null) {
                            return;
                        }
                    }
                }
            }
            ledger.add(new PlacementLedger(o.semanticId(), nativeId.toString(), o.zone()));
        } catch (RuntimeException exc) {
            failed.add(new FailedPlacement(o.semanticId(), "PLACEMENT_EXCEPTION", rootMessage(exc)));
        }
    }

    private static Counter counterInstance(String name, int count) {
        for (CounterType type : CounterType.values()) {
            if (type.getName().equalsIgnoreCase(name)) {
                return type.createInstance(count);
            }
        }
        return null;
    }

    private static Map<String, JsonObject> indexStackState(JsonObject record) {
        Map<String, JsonObject> out = new HashMap<>();
        if (record.has("stack_state")) {
            for (var e : record.getAsJsonArray("stack_state")) {
                JsonObject s = e.getAsJsonObject();
                if (s.has("source_semantic_id")) {
                    out.put(s.get("source_semantic_id").getAsString(), s);
                }
            }
        }
        return out;
    }

    private static void placeStackSpell(
            Game game,
            SemanticObject o,
            JsonObject stackSpec,
            Map<String, UUID> playerUuidByPid,
            List<PlacementLedger> ledger,
            List<FailedPlacement> failed) {
        UUID controllerId = playerUuidByPid.get(o.controller());
        UUID ownerId = playerUuidByPid.get(o.owner());
        if (controllerId == null || ownerId == null) {
            failed.add(new FailedPlacement(o.semanticId(), "UNKNOWN_ACTOR", o.owner() + "/" + o.controller()));
            return;
        }
        // Resolve targets BEFORE instantiating (fixpoint retries must not duplicate).
        List<UUID> targetNatives = new ArrayList<>();
        if (stackSpec != null && stackSpec.has("targets")) {
            for (var t : stackSpec.getAsJsonArray("targets")) {
                String targetSem = t.getAsString();
                UUID targetNative = resolveTarget(game, targetSem, playerUuidByPid, ledger);
                if (targetNative == null) {
                    failed.add(new FailedPlacement(o.semanticId(), "TARGET_UNRESOLVABLE", targetSem));
                    return;
                }
                targetNatives.add(targetNative);
            }
        }
        List<String> modeLabels = new ArrayList<>();
        if (stackSpec != null && stackSpec.has("modes")) {
            for (var m : stackSpec.getAsJsonArray("modes")) {
                modeLabels.add(m.getAsString());
            }
        }
        try {
            Card card = instantiateCard(o.cardIdentity());
            Set<Card> one = new LinkedHashSet<>();
            one.add(card);
            game.loadCards(one, ownerId);
            Ability ability = card.getSpellAbility();
            if (ability == null) {
                failed.add(new FailedPlacement(o.semanticId(), "NO_SPELL_ABILITY", o.cardIdentity()));
                return;
            }
            if (!(ability instanceof mage.abilities.SpellAbility)) {
                failed.add(new FailedPlacement(o.semanticId(), "ABILITY_NOT_SPELL", o.cardIdentity()));
                return;
            }
            if (!modeLabels.isEmpty()) {
                String modeFailure = selectModesByLabel(ability, modeLabels, game);
                if (modeFailure != null) {
                    failed.add(new FailedPlacement(o.semanticId(), modeFailure, String.join(",", modeLabels)));
                    return;
                }
            }
            if (!targetNatives.isEmpty()) {
                Targets targets = ability.getTargets();
                if (targets.isEmpty()) {
                    failed.add(new FailedPlacement(o.semanticId(), "ABILITY_HAS_NO_TARGETS", o.cardIdentity()));
                    return;
                }
                for (UUID targetNative : targetNatives) {
                    targets.get(0).addTarget(targetNative, null, game);
                }
            }
            Spell spell = new Spell(card, (mage.abilities.SpellAbility) ability,
                    controllerId, mage.constants.Zone.HAND, game);
            game.getStack().push(spell);
            ledger.add(new PlacementLedger(o.semanticId(), spell.getId().toString(), "stack"));
        } catch (RuntimeException exc) {
            failed.add(new FailedPlacement(o.semanticId(), "STACK_PLACEMENT_EXCEPTION", rootMessage(exc)));
        }
    }

    private static UUID resolveTarget(
            Game game,
            String targetSem,
            Map<String, UUID> playerUuidByPid,
            List<PlacementLedger> ledger) {
        if (playerUuidByPid.containsKey(targetSem)) {
            return playerUuidByPid.get(targetSem);
        }
        for (PlacementLedger l : ledger) {
            if (l.semanticId().equals(targetSem)) {
                try {
                    return UUID.fromString(l.nativeId());
                } catch (IllegalArgumentException exc) {
                    return null;
                }
            }
        }
        // controller/owner-relative pseudo targets are not natively resolvable here
        return null;
    }

    /**
     * Fixed WS74 mode-label rule (also implemented independently in the
     * normalizer): lowercase, split on non-alphanumerics, strip a single
     * trailing 's' from tokens longer than 3 chars, then require the label
     * token set to be a subset of exactly one engine mode text token set.
     */
    static List<String> modeTokens(String text) {
        List<String> out = new ArrayList<>();
        if (text == null) {
            return out;
        }
        for (String tok : text.toLowerCase().split("[^a-z0-9]+")) {
            if (tok.isEmpty()) {
                continue;
            }
            if (tok.length() > 3 && tok.endsWith("s")) {
                tok = tok.substring(0, tok.length() - 1);
            }
            out.add(tok);
        }
        return out;
    }

    private static String selectModesByLabel(Ability ability, List<String> labels, Game game) {
        var modes = ability.getModes();
        if (modes == null || modes.isEmpty()) {
            return "MODES_UNSETTABLE";
        }
        for (String label : labels) {
            Set<String> want = new HashSet<>(modeTokens(label));
            List<UUID> hits = new ArrayList<>();
            for (mage.abilities.Mode mode : modes.values()) {
                String text;
                try {
                    text = mode.getEffects().getText(mode);
                } catch (RuntimeException exc) {
                    continue;
                }
                if (new HashSet<>(modeTokens(text)).containsAll(want)) {
                    hits.add(mode.getId());
                }
            }
            if (hits.size() != 1) {
                return hits.isEmpty() ? "MODES_UNMATCHED" : "MODES_AMBIGUOUS";
            }
            try {
                modes.addSelectedMode(hits.get(0));
            } catch (RuntimeException exc) {
                return "MODES_SELECT_REJECTED";
            }
        }
        return null;
    }

    private static void placeRevealed(
            Game game,
            SemanticObject o,
            Map<String, UUID> playerUuidByPid,
            List<PlacementLedger> ledger,
            List<FailedPlacement> failed) {
        placeRevealed(game, o, playerUuidByPid, ledger, failed, -1);
    }

    private static void placeRevealed(
            Game game,
            SemanticObject o,
            Map<String, UUID> playerUuidByPid,
            List<PlacementLedger> ledger,
            List<FailedPlacement> failed,
            int revealPosition) {
        UUID controllerId = playerUuidByPid.get(o.controller());
        UUID ownerId = playerUuidByPid.get(o.owner());
        if (controllerId == null || ownerId == null) {
            failed.add(new FailedPlacement(o.semanticId(), "UNKNOWN_ACTOR", o.owner() + "/" + o.controller()));
            return;
        }
        try {
            Card card = instantiateCard(o.cardIdentity());
            Set<Card> one = new LinkedHashSet<>();
            one.add(card);
            game.loadCards(one, ownerId);
            Player mover = game.getPlayer(controllerId);
            boolean moved = mover.moveCards(card, mage.constants.Zone.HAND, null, game, false, false, false, null);
            if (!moved) {
                failed.add(new FailedPlacement(o.semanticId(), "REVEAL_STAGING_FAILED", o.cardIdentity()));
                return;
            }
            Cards cards = new CardsImpl();
            cards.add(card);
            // Positional reveal titles preserve requested order: the Revealed
            // container is keyed by title, so one card per title keeps the
            // requested sequence natively observable without gameplay.
            String title = revealPosition >= 0
                    ? String.format("ws74-reveal-%05d", revealPosition)
                    : "ws74-reveal";
            mover.revealCards(null, title, cards, game, false);
            ledger.add(new PlacementLedger(o.semanticId(), card.getId().toString(), "revealed"));
        } catch (RuntimeException exc) {
            failed.add(new FailedPlacement(o.semanticId(), "REVEAL_EXCEPTION", rootMessage(exc)));
        }
    }

    private static void performKnowledgeGrants(
            Game game,
            JsonObject record,
            Map<String, UUID> playerUuidByPid,
            List<PlayerSpec> specs,
            List<PlacementLedger> ledger,
            List<FailedPlacement> failed) {
        // Native-trace knowledge procedures only: look + reveal grants with explicit
        // object references. Search/scry/surveil/shuffle grants need decisions or
        // gameplay and are left to terminal adjudication (no fabrication).
        if (!record.has("knowledge_state")) {
            return;
        }
        var viewers = record.getAsJsonObject("knowledge_state").getAsJsonArray("viewer_states");
        if (viewers == null) {
            return;
        }
        for (var ve : viewers) {
            JsonObject v = ve.getAsJsonObject();
            String viewerPid = str(v, "viewer");
            UUID viewerId = playerUuidByPid.get(viewerPid);
            if (("ALL_PLAYERS".equals(viewerPid) || viewerId != null) && v.has("temporary_permissions")) {
                // proceed
            } else {
                continue;
            }
            List<Player> grantViewers = new ArrayList<>();
            if ("ALL_PLAYERS".equals(viewerPid)) {
                for (PlayerSpec s2 : specs) {
                    grantViewers.add(game.getPlayer(playerUuidByPid.get(s2.playerId())));
                }
            } else {
                grantViewers.add(game.getPlayer(viewerId));
            }
            for (var pe : v.getAsJsonArray("temporary_permissions")) {
                JsonObject perm = pe.getAsJsonObject();
                String kind = perm.has("permission") ? perm.get("permission").getAsString() : "";
                String objSem = perm.has("object") ? perm.get("object").getAsString() : "";
                if (objSem.isEmpty()) {
                    continue; // zone-wide grants (e.g. search) need decisions: not performed
                }
                UUID nativeId = null;
                for (PlacementLedger l : ledger) {
                    if (l.semanticId().equals(objSem)) {
                        try {
                            nativeId = UUID.fromString(l.nativeId());
                        } catch (IllegalArgumentException ignore) {
                            nativeId = null;
                        }
                    }
                }
                if (nativeId == null) {
                    continue;
                }
                // Permission-exercise looks (look_at_face_down_exile) carry no
                // acquired-knowledge semantics in this contract and leave no trace.
                try {
                    if ("look".equals(kind)) {
                        Card card = game.getCard(nativeId);
                        if (card == null) {
                            Permanent perm2 = game.getPermanent(nativeId);
                            if (perm2 != null) {
                                card = game.getCard(perm2.getId());
                            }
                        }
                        if (card != null) {
                            Cards cards = new CardsImpl();
                            cards.add(card);
                            for (Player gv : grantViewers) {
                                // D10: acquisition looks recorded via the public
                                // lookedAt container API (the UI-update event path
                                // clears traces immediately; no game action
                                // intervenes before readback).
                                game.getState().getLookedAt(gv.getId()).add("ws74-staging", cards);
                            }
                        }
                    } else if ("reveal".equals(kind)) {
                        Card card = game.getCard(nativeId);
                        if (card != null) {
                            Cards cards = new CardsImpl();
                            cards.add(card);
                            // revealed container is game-global: perform once
                            grantViewers.get(0).revealCards(null, "ws74-staging", cards, game, false);
                        }
                    }
                    // 'search' and any other grant kinds: not performed (decision-gated).
                } catch (RuntimeException exc) {
                    failed.add(new FailedPlacement(objSem, "KNOWLEDGE_GRANT_FAILED", rootMessage(exc)));
                }
            }
        }
    }

    private static String restoreCommanderDamage(
            Game game,
            JsonObject record,
            Map<String, UUID> playerUuidByPid,
            List<PlacementLedger> ledger,
            List<FailedPlacement> failed) {
        if (!record.has("commander_state")) {
            return null;
        }
        var cmd = record.getAsJsonObject("commander_state");
        if (!cmd.has("commander_damage_matrix")) {
            return null;
        }
        var matrix = cmd.getAsJsonArray("commander_damage_matrix");
        if (matrix.size() == 0) {
            return null;
        }
        // group by source commander
        Map<String, Map<UUID, Integer>> bySource = new HashMap<>();
        for (var e : matrix) {
            JsonObject row = e.getAsJsonObject();
            String sourceCmd = row.get("source_commander_id").getAsString();
            String damagedPid = row.get("damaged_player").getAsString();
            int amount = row.get("combat_damage").getAsInt();
            UUID damagedId = playerUuidByPid.get(damagedPid);
            if (damagedId == null) {
                return "COMMANDER_DAMAGE_UNKNOWN_PLAYER";
            }
            bySource.computeIfAbsent(sourceCmd, k -> new HashMap<>())
                    .merge(damagedId, amount, Integer::sum);
        }
        // resolve commander native card ids from the ledger (command-zone commanders)
        Map<String, String> cmdToNative = new HashMap<>();
        for (PlacementLedger l : ledger) {
            cmdToNative.putIfAbsent(l.semanticId(), l.nativeId());
        }
        // NOTE: commander semantic ids (cmd:P1-A) differ from object semantic ids
        // (obj:...); resolve via commander_state commanders list matched on commander_id.
        Map<String, String> cmdIdToObjSem = new HashMap<>();
        for (var e : cmd.getAsJsonArray("commanders")) {
            JsonObject c = e.getAsJsonObject();
            cmdIdToObjSem.put(c.get("commander_id").getAsString(), null);
        }
        for (Map.Entry<String, Map<UUID, Integer>> en : bySource.entrySet()) {
            String sourceCmd = en.getKey();
            UUID commanderNative = findCommanderNativeForCmdId(game, record, sourceCmd, playerUuidByPid);
            if (commanderNative == null) {
                failed.add(new FailedPlacement(sourceCmd, "COMMANDER_NATIVE_UNRESOLVED", sourceCmd));
                return "COMMANDER_DAMAGE_UNRESOLVABLE";
            }
            CommanderInfoWatcher watcher =
                    game.getState().getWatcher(CommanderInfoWatcher.class, commanderNative);
            if (watcher == null) {
                failed.add(new FailedPlacement(sourceCmd, "COMMANDER_WATCHER_ABSENT", sourceCmd));
                return "COMMANDER_DAMAGE_WATCHER_ABSENT";
            }
            watcher.restoreDamageStateForGameLoad(en.getValue(), game);
        }
        return null;
    }

    // ------------------------------------------------------------- verification

    /**
     * Completes game startup to the contractual load boundary.
     *
     * <p>WS74 staging decision D6: resolving the startup priorities (upkeep and
     * draw pass-arounds, which carry zero fixture-scripted content and resolve
     * no fixture decision) through the qualified provider pass machinery is
     * game-startup completion ({@code NATIVE_START_FIRST_TURN} in contract
     * terms), not Full107 behavior. The game remains paused at the first
     * precombat-main priority; that pending decision is never resolved by
     * staging. Returns null on success, else an exact failure code.
     */
    private static String advanceStartup(
            XmageGameManager manager,
            String gameHandle,
            Game game,
            List<PlayerSpec> specs,
            Map<String, UUID> playerUuidByPid,
            List<PlacementLedger> ledger,
            List<FailedPlacement> failed,
            JsonObject construction) {
        JsonArray passes = new JsonArray();
        int maxPasses = 2 * specs.size() + 2;
        for (int i = 0; i < maxPasses; i++) {
            if (game.getState().getTurnNum() == 1
                    && game.getTurnPhaseType() == TurnPhase.PRECOMBAT_MAIN
                    && game.isPaused()) {
                break;
            }
            XmageGameManager.LegalActionsSnapshot snapshot;
            try {
                snapshot = manager.legalActions(gameHandle);
            } catch (RuntimeException exc) {
                return "STARTUP_DECISION_UNAVAILABLE:" + rootMessage(exc);
            }
            if (!"priority".equals(snapshot.decisionKind())) {
                return "STARTUP_UNEXPECTED_DECISION_KIND:" + snapshot.decisionKind();
            }
            String actorPid = pidOf(snapshot.actorId(), specs, playerUuidByPid);
            if (actorPid == null) {
                return "STARTUP_UNKNOWN_ACTOR:" + snapshot.actorId();
            }
            String passActionId = null;
            for (JsonObject action : snapshot.actions()) {
                if ("pass_priority".equals(action.get("action_type").getAsString())) {
                    passActionId = action.get("action_id").getAsString();
                    break;
                }
            }
            if (passActionId == null) {
                return "STARTUP_PASS_ACTION_ABSENT";
            }
            try {
                XmageActionExecutor.passPriority(
                        game, snapshot, snapshot.decisionId(), snapshot.actorId(), passActionId);
            } catch (RuntimeException exc) {
                return "STARTUP_PASS_REJECTED:" + rootMessage(exc);
            }
            JsonObject p = new JsonObject();
            p.addProperty("offset", snapshot.decisionOffset());
            p.addProperty("actor", actorPid);
            p.addProperty("kind", snapshot.decisionKind());
            p.addProperty("action", "pass_priority");
            passes.add(p);
        }
        construction.add("startup_passes", passes);
        if (!(game.getState().getTurnNum() == 1
                && game.getTurnPhaseType() == TurnPhase.PRECOMBAT_MAIN
                && game.isPaused())) {
            return "STARTUP_NONCONVERGENCE";
        }
        String prioPid = pidOf(
                game.getPriorityPlayerId() == null ? null : game.getPriorityPlayerId().toString(),
                specs, playerUuidByPid);
        if (!"P1".equals(prioPid)) {
            return "STARTUP_PRIORITY_NOT_P1:" + prioPid;
        }
        String activePid = pidOf(
                game.getActivePlayerId() == null ? null : game.getActivePlayerId().toString(),
                specs, playerUuidByPid);
        if (!"P1".equals(activePid)) {
            return "STARTUP_ACTIVE_NOT_P1:" + activePid;
        }
        return null;
    }

    private static String pidOf(String nativeUuid, List<PlayerSpec> specs, Map<String, UUID> byPid) {
        if (nativeUuid == null) {
            return null;
        }
        for (PlayerSpec s : specs) {
            UUID id = byPid.get(s.playerId());
            if (id != null && id.toString().equals(nativeUuid)) {
                return s.playerId();
            }
        }
        return null;
    }

    private static boolean verifyCommanders(
            Game game,
            List<PlayerSpec> specs,
            Map<String, List<String>> commandersByPlayer,
            Map<String, UUID> playerUuidByPid,
            Map<UUID, String> pidByUuid) {
        for (PlayerSpec s : specs) {
            Player p = game.getPlayer(playerUuidByPid.get(s.playerId()));
            if (p == null) {
                return false;
            }
            List<String> expected = new ArrayList<>(
                    commandersByPlayer.getOrDefault(s.playerId(), List.of()));
            List<String> observed = new ArrayList<>();
            for (Card c : game.getCommanderCardsFromCommandZone(p, CommanderCardType.COMMANDER_OR_OATHBREAKER)) {
                observed.add(c.getName());
            }
            expected.sort(String::compareTo);
            observed.sort(String::compareTo);
            if (!expected.equals(observed)) {
                return false;
            }
        }
        return true;
    }

    private static String findCommanderNativeId(
            Game game, SemanticObject o, Map<String, UUID> playerUuidByPid, Set<String> consumed) {
        UUID ownerId = playerUuidByPid.get(o.owner());
        if (ownerId == null) {
            return null;
        }
        Player p = game.getPlayer(ownerId);
        for (Card c : game.getCommanderCardsFromCommandZone(p, CommanderCardType.COMMANDER_OR_OATHBREAKER)) {
            if (o.cardIdentity().equals(c.getName()) && !consumed.contains(c.getId().toString())) {
                return c.getId().toString();
            }
        }
        return null;
    }

    /**
     * Battlefield commanders (cast pre-boundary in requested state) relocate
     * their deck copies from the command zone via a native zone move. No card
     * is duplicated; tapped/counters apply as placed state.
     */
    private static void relocateCommander(
            Game game,
            SemanticObject o,
            Map<String, UUID> playerUuidByPid,
            Set<String> consumed,
            List<PlacementLedger> ledger,
            List<FailedPlacement> failed) {
        UUID ownerId = playerUuidByPid.get(o.owner());
        UUID controllerId = playerUuidByPid.get(o.controller());
        if (ownerId == null || controllerId == null) {
            failed.add(new FailedPlacement(o.semanticId(), "UNKNOWN_ACTOR", o.owner() + "/" + o.controller()));
            return;
        }
        Player owner = game.getPlayer(ownerId);
        Card copy = null;
        for (Card c : game.getCommanderCardsFromCommandZone(
                owner, CommanderCardType.COMMANDER_OR_OATHBREAKER)) {
            if (o.cardIdentity().equals(c.getName()) && !consumed.contains(c.getId().toString())) {
                copy = c;
                break;
            }
        }
        if (copy == null) {
            // fallback: instantiate (duplicate only when no deck copy exists)
            placeOne(game, o, playerUuidByPid, ledger, failed);
            return;
        }
        try {
            Player mover = game.getPlayer(controllerId);
            boolean moved = mover.moveCards(copy, mage.constants.Zone.BATTLEFIELD, null, game,
                    o.tapped(), false, false, null);
            if (!moved) {
                failed.add(new FailedPlacement(o.semanticId(), "COMMANDER_RELOCATE_REJECTED", o.cardIdentity()));
                return;
            }
            Permanent perm = game.getPermanent(copy.getId());
            if (perm == null) {
                failed.add(new FailedPlacement(o.semanticId(), "NO_PERMANENT_AFTER_RELOCATE", o.cardIdentity()));
                return;
            }
            if (!o.counters().isEmpty()) {
                for (Map.Entry<String, Integer> ce : o.counters().entrySet()) {
                    if (ce.getValue() == null || ce.getValue() <= 0) {
                        continue;
                    }
                    Counter counter = counterInstance(ce.getKey(), ce.getValue());
                    if (counter == null || !perm.addCounters(counter, controllerId, null, game)) {
                        failed.add(new FailedPlacement(o.semanticId(), "COUNTER_REJECTED", ce.getKey()));
                        return;
                    }
                }
            }
            consumed.add(copy.getId().toString());
            ledger.add(new PlacementLedger(o.semanticId(), perm.getId().toString(), "battlefield"));
        } catch (RuntimeException exc) {
            failed.add(new FailedPlacement(o.semanticId(), "RELOCATE_EXCEPTION", rootMessage(exc)));
        }
    }

    private static UUID findCommanderNativeForCmdId(
            Game game, JsonObject record, String cmdId, Map<String, UUID> playerUuidByPid) {
        var commanders = record.getAsJsonObject("commander_state").getAsJsonArray("commanders");
        for (var e : commanders) {
            JsonObject c = e.getAsJsonObject();
            if (cmdId.equals(c.get("commander_id").getAsString())) {
                UUID ownerId = playerUuidByPid.get(c.get("owner").getAsString());
                if (ownerId == null) {
                    return null;
                }
                Player p = game.getPlayer(ownerId);
                // command-zone first, then battlefield (cast commanders)
                for (Card card : game.getCommanderCardsFromCommandZone(
                        p, CommanderCardType.COMMANDER_OR_OATHBREAKER)) {
                    if (c.get("card_identity").getAsString().equals(card.getName())) {
                        return card.getId();
                    }
                }
                for (Permanent perm : game.getBattlefield().getAllPermanents()) {
                    if (ownerId.equals(perm.getControllerId())
                            && c.get("card_identity").getAsString().equals(perm.getName())) {
                        return perm.getId();
                    }
                }
            }
        }
        return null;
    }

    // ------------------------------------------------------------- readback

    private static JsonObject gameBlock(Game game, List<PlayerSpec> specs, Map<String, UUID> byPid) {
        JsonObject g = new JsonObject();
        g.addProperty("turn_number", game.getState().getTurnNum());
        TurnPhase phase = game.getTurnPhaseType();
        prop(g, "phase", phase == null ? null : phase.name().toLowerCase());
        PhaseStep step = game.getTurnStepType();
        prop(g, "step", step == null ? null : step.name().toLowerCase());
        g.addProperty("active_seat", seatOf(game.getActivePlayerId(), specs, byPid));
        g.addProperty("priority_seat", seatOf(game.getPriorityPlayerId(), specs, byPid));
        g.addProperty("player_count", game.getPlayers().size());
        g.addProperty("paused", game.isPaused());
        g.addProperty("ended", game.hasEnded());
        return g;
    }

    private static int seatOf(UUID id, List<PlayerSpec> specs, Map<String, UUID> byPid) {
        if (id == null) {
            return -1;
        }
        for (PlayerSpec s : specs) {
            if (id.equals(byPid.get(s.playerId()))) {
                return s.seat();
            }
        }
        return -1;
    }

    private static JsonObject playersBlock(Game game, List<PlayerSpec> specs, Map<String, UUID> byPid) {
        JsonObject out = new JsonObject();
        for (PlayerSpec s : specs) {
            Player p = game.getPlayer(byPid.get(s.playerId()));
            JsonObject pj = new JsonObject();
            pj.addProperty("seat", s.seat());
            pj.addProperty("life", p.getLife());
            pj.addProperty("poison", p.getCountersCount(CounterType.POISON));
            pj.addProperty("native_uuid", p.getId().toString());
            pj.addProperty("lost", p.hasLost());
            JsonObject zones = new JsonObject();
            zones.add("library", libraryDump(game, p));
            zones.add("hand", cardDump(new ArrayList<>(p.getHand().getCards(game)), game, false));
            List<Permanent> battlefield = game.getBattlefield().getAllPermanents().stream()
                    .filter(perm -> p.getId().equals(perm.getControllerId()))
                    .sorted(Comparator.comparing(x -> x.getId().toString()))
                    .toList();
            zones.add("battlefield", permanentDump(battlefield, game));
            zones.add("graveyard", cardDump(new ArrayList<>(p.getGraveyard().getCards(game)), game, false));
            zones.add("exile", cardDump(
                    new ArrayList<>(game.getExile().getCardsOwned(game, p.getId())), game, true));
            List<Card> command = new ArrayList<>(game.getCommanderCardsFromCommandZone(
                    p, CommanderCardType.COMMANDER_OR_OATHBREAKER));
            command.sort(Comparator.comparing(c -> c.getId().toString()));
            zones.add("command", cardDump(command, game, false));
            pj.add("zones", zones);
            out.add(s.playerId(), pj);
        }
        return out;
    }

    private static JsonArray uuidList(Collection<UUID> ids) {
        JsonArray a = new JsonArray();
        List<UUID> sorted = new ArrayList<>(ids);
        sorted.sort(Comparator.comparing(UUID::toString));
        for (UUID id : sorted) {
            a.add(id.toString());
        }
        return a;
    }

    private static JsonArray libraryDump(Game game, Player player) {
        // Omniscient provider section: names included so the normalizer can
        // derive placed library identities natively. Per-viewer views stay
        // counts-only (see viewsBlock).
        JsonArray a = new JsonArray();
        List<UUID> ids = new ArrayList<>(player.getLibrary().getCardList());
        for (int index = 0; index < ids.size(); index++) {
            UUID id = ids.get(index);
            JsonObject o = new JsonObject();
            o.addProperty("uuid", id.toString());
            o.addProperty("position", index);
            Card c = game.getCard(id);
            prop(o, "name", c == null ? null : c.getName());
            prop(o, "owner", c == null || c.getOwnerId() == null ? null : c.getOwnerId().toString());
            a.add(o);
        }
        return a;
    }

    private static JsonArray cardDump(List<Card> cards, Game game, boolean withFaceDown) {
        cards.sort(Comparator.comparing(c -> c.getId().toString()));
        JsonArray a = new JsonArray();
        for (Card c : cards) {
            JsonObject o = new JsonObject();
            o.addProperty("uuid", c.getId().toString());
            o.addProperty("name", c.getName());
            prop(o, "owner", c.getOwnerId() == null ? null : c.getOwnerId().toString());
            boolean fd = false;
            try {
                fd = c.isFaceDown(game);
            } catch (RuntimeException ignore) {
                fd = false;
            }
            o.addProperty("face_down", withFaceDown && fd);
            a.add(o);
        }
        return a;
    }

    private static JsonArray permanentDump(List<Permanent> perms, Game game) {
        JsonArray a = new JsonArray();
        for (Permanent p : perms) {
            JsonObject o = new JsonObject();
            o.addProperty("uuid", p.getId().toString());
            prop(o, "name", p.getName());
            try {
                Card backing = game.getCard(p.getId());
                prop(o, "card_name", backing == null ? null : backing.getName());
            } catch (RuntimeException ignore) {
                prop(o, "card_name", null);
            }
            prop(o, "controller", p.getControllerId() == null ? null : p.getControllerId().toString());
            prop(o, "owner", p.getOwnerId() == null ? null : p.getOwnerId().toString());
            boolean fd = false;
            try {
                fd = p.isFaceDown(game);
            } catch (RuntimeException ignore) {
                fd = false;
            }
            o.addProperty("face_down", fd);
            o.addProperty("tapped", p.isTapped());
            JsonObject counters = new JsonObject();
            try {
                Counters cs = p.getCounters(game);
                if (cs != null) {
                    for (Counter counter : cs.values()) {
                        counters.addProperty(counter.getName(), counter.getCount());
                    }
                }
            } catch (RuntimeException ignore) {
                // omit on error; placement validation covers counters structurally
            }
            o.add("counters", counters);
            a.add(o);
        }
        return a;
    }

    /** Fixed principal rules, no record permissions: own hand named, others hidden;
     *  libraries counts-only; public zones named; face-down concealed everywhere. */
    private static JsonObject viewsBlock(Game game, List<PlayerSpec> specs, Map<String, UUID> byPid) {
        JsonObject views = new JsonObject();
        for (PlayerSpec viewer : specs) {
            UUID viewerId = byPid.get(viewer.playerId());
            JsonObject v = new JsonObject();
            v.addProperty("viewer", viewer.playerId());
            JsonObject zones = new JsonObject();
            for (PlayerSpec s : specs) {
                Player p = game.getPlayer(byPid.get(s.playerId()));
                JsonObject pz = new JsonObject();
                // hand
                if (s.playerId().equals(viewer.playerId())) {
                    JsonArray hand = new JsonArray();
                    List<Card> cards = new ArrayList<>(p.getHand().getCards(game));
                    cards.sort(Comparator.comparing(c -> c.getId().toString()));
                    for (Card c : cards) {
                        JsonObject e = new JsonObject();
                        e.addProperty("uuid", c.getId().toString());
                        e.addProperty("name", c.getName());
                        hand.add(e);
                    }
                    pz.add("hand", hand);
                } else {
                    JsonObject hidden = new JsonObject();
                    hidden.addProperty("hidden", true);
                    hidden.addProperty("count", p.getHand().getCards(game).size());
                    pz.add("hand", hidden);
                }
                // library: counts only, always
                JsonObject lib = new JsonObject();
                lib.addProperty("hidden", true);
                lib.addProperty("count", p.getLibrary().size());
                pz.add("library", lib);
                // battlefield
                JsonArray bf = new JsonArray();
                List<Permanent> perms = game.getBattlefield().getAllPermanents().stream()
                        .filter(perm -> p.getId().equals(perm.getControllerId()))
                        .sorted(Comparator.comparing(x -> x.getId().toString()))
                        .toList();
                for (Permanent perm : perms) {
                    boolean fd = false;
                    try {
                        fd = perm.isFaceDown(game);
                    } catch (RuntimeException ignore) {
                        fd = false;
                    }
                    JsonObject e = new JsonObject();
                    e.addProperty("uuid", perm.getId().toString());
                    if (fd) {
                        e.addProperty("concealed", true);
                    } else {
                        e.addProperty("name", perm.getName());
                    }
                    e.addProperty("tapped", perm.isTapped());
                    bf.add(e);
                }
                pz.add("battlefield", bf);
                // graveyard: public
                JsonArray gy = new JsonArray();
                List<Card> gyc = new ArrayList<>(p.getGraveyard().getCards(game));
                gyc.sort(Comparator.comparing(c -> c.getId().toString()));
                for (Card c : gyc) {
                    JsonObject e = new JsonObject();
                    e.addProperty("uuid", c.getId().toString());
                    e.addProperty("name", c.getName());
                    gy.add(e);
                }
                pz.add("graveyard", gy);
                // exile: face-down concealed
                JsonArray ex = new JsonArray();
                List<Card> exc = new ArrayList<>(game.getExile().getCardsOwned(game, p.getId()));
                exc.sort(Comparator.comparing(c -> c.getId().toString()));
                for (Card c : exc) {
                    boolean fd = false;
                    try {
                        fd = c.isFaceDown(game);
                    } catch (RuntimeException ignore) {
                        fd = false;
                    }
                    JsonObject e = new JsonObject();
                    e.addProperty("uuid", c.getId().toString());
                    if (fd) {
                        e.addProperty("concealed", true);
                    } else {
                        e.addProperty("name", c.getName());
                    }
                    ex.add(e);
                }
                pz.add("exile", ex);
                // command: public
                JsonArray co = new JsonArray();
                List<Card> com = new ArrayList<>(game.getCommanderCardsFromCommandZone(
                        p, CommanderCardType.COMMANDER_OR_OATHBREAKER));
                com.sort(Comparator.comparing(c -> c.getId().toString()));
                for (Card c : com) {
                    JsonObject e = new JsonObject();
                    e.addProperty("uuid", c.getId().toString());
                    e.addProperty("name", c.getName());
                    co.add(e);
                }
                pz.add("command", co);
                zones.add(s.playerId(), pz);
            }
            v.add("zones", zones);
            views.add(viewer.playerId(), v);
        }
        return views;
    }

    private static JsonArray stackBlock(Game game) {
        JsonArray a = new JsonArray();
        for (StackObject so : game.getStack()) {
            JsonObject o = new JsonObject();
            o.addProperty("uuid", so.getId().toString());
            o.addProperty("class", so.getClass().getSimpleName());
            String name = null;
            try {
                MageObject mo = game.getObject(so.getSourceId());
                if (mo != null) {
                    name = mo.getName();
                }
            } catch (RuntimeException ignore) {
                name = null;
            }
            if (name == null) {
                try {
                    name = so.getName();
                } catch (RuntimeException ignore) {
                    name = null;
                }
            }
            prop(o, "name", name);
            prop(o, "controller", so.getControllerId() == null ? null : so.getControllerId().toString());
            if (so instanceof Spell) {
                UUID spellOwner = ((Spell) so).getOwnerId();
                prop(o, "owner", spellOwner == null ? null : spellOwner.toString());
            } else {
                prop(o, "owner", null);
            }
            JsonArray targets = new JsonArray();
            try {
                Ability ability = so.getStackAbility();
                if (ability != null) {
                    for (Target t : ability.getTargets()) {
                        for (UUID id : t.getTargets()) {
                            targets.add(id.toString());
                        }
                    }
                }
            } catch (RuntimeException ignore) {
                // targets omitted on error
            }
            o.add("targets", targets);
            JsonArray selModes = new JsonArray();
            try {
                Ability ability = so.getStackAbility();
                if (ability != null && ability.getModes() != null) {
                    for (UUID modeId : ability.getModes().getSelectedModes()) {
                        mage.abilities.Mode mode = ability.getModes().get(modeId);
                        if (mode != null) {
                            try {
                                selModes.add(mode.getEffects().getText(mode));
                            } catch (RuntimeException ignore) {
                                selModes.add("UNREADABLE_MODE");
                            }
                        }
                    }
                }
            } catch (RuntimeException ignore) {
                // modes omitted on error
            }
            o.add("selected_mode_texts", selModes);
            a.add(o);
        }
        return a;
    }

    private static JsonArray revealedBlock(Game game) {
        JsonArray a = new JsonArray();
        try {
            Revealed revealed = game.getState().getRevealed();
            List<String> keys = new ArrayList<>(revealed.keySet());
                keys.sort(String::compareTo);
            for (String key : keys) {
                Cards cards = revealed.get(key);
                List<Card> list = new ArrayList<>(cards.getCards(game));
                list.sort(Comparator.comparing(c -> c.getId().toString()));
                for (Card c : list) {
                    JsonObject o = new JsonObject();
                    o.addProperty("group", key);
                    o.addProperty("uuid", c.getId().toString());
                    o.addProperty("name", c.getName());
                    a.add(o);
                }
            }
        } catch (RuntimeException ignore) {
            // empty on error
        }
        return a;
    }

    private static JsonObject lookedAtBlock(Game game, List<PlayerSpec> specs, Map<String, UUID> byPid) {
        JsonObject out = new JsonObject();
        for (PlayerSpec s : specs) {
            JsonArray a = new JsonArray();
            try {
                var looked = game.getState().getLookedAt(byPid.get(s.playerId()));
                if (looked != null) {
                    List<Card> list = new ArrayList<>();
                    for (Cards cards : looked.values()) {
                        list.addAll(cards.getCards(game));
                    }
                    list.sort(Comparator.comparing(c -> c.getId().toString()));
                    for (Card c : list) {
                        JsonObject o = new JsonObject();
                        o.addProperty("uuid", c.getId().toString());
                        prop(o, "name", c.getName());
                        a.add(o);
                    }
                }
            } catch (RuntimeException ignore) {
                // empty on error
            }
            out.add(s.playerId(), a);
        }
        return out;
    }

    /** Native commander cast counts (plays watcher, GAME scope). */
    private static JsonArray commanderPlaysBlock(Game game, List<PlayerSpec> specs, Map<String, UUID> byPid) {
        JsonArray a = new JsonArray();
        try {
            mage.watchers.common.CommanderPlaysCountWatcher watcher =
                    game.getState().getWatcher(mage.watchers.common.CommanderPlaysCountWatcher.class);
            for (PlayerSpec s : specs) {
                Player p = game.getPlayer(byPid.get(s.playerId()));
                List<Card> commanders = new ArrayList<>(game.getCommanderCardsFromCommandZone(
                        p, CommanderCardType.COMMANDER_OR_OATHBREAKER));
                for (Permanent perm : game.getBattlefield().getAllPermanents()) {
                    if (p.getId().equals(perm.getControllerId())) {
                        Card backing = game.getCard(perm.getId());
                        // Control-changed commanders belong to another player's
                        // commander list; check against every seat's list.
                        if (backing != null && isAnyCommander(game, specs, byPid, backing)) {
                            commanders.add(backing);
                        }
                    }
                }
                commanders.sort(Comparator.comparing(c -> c.getId().toString()));
                for (Card c : commanders) {
                    JsonObject o = new JsonObject();
                    o.addProperty("uuid", c.getId().toString());
                    prop(o, "name", c.getName());
                    int plays = 0;
                    try {
                        plays = watcher == null ? 0 : watcher.getPlaysCount(c.getId());
                    } catch (RuntimeException ignore) {
                        plays = -1;
                    }
                    o.addProperty("plays_from_command", plays);
                    a.add(o);
                }
            }
        } catch (RuntimeException ignore) {
            // empty on error
        }
        return a;
    }

    /** Native commander combat-damage tracking (info watcher per commander card). */
    private static JsonArray commanderDamageBlock(Game game, List<PlayerSpec> specs, Map<String, UUID> byPid) {
        JsonArray a = new JsonArray();
        try {
            for (PlayerSpec s : specs) {
                Player p = game.getPlayer(byPid.get(s.playerId()));
                List<Card> commanders = new ArrayList<>(game.getCommanderCardsFromCommandZone(
                        p, CommanderCardType.COMMANDER_OR_OATHBREAKER));
                for (Permanent perm : game.getBattlefield().getAllPermanents()) {
                    if (p.getId().equals(perm.getControllerId())) {
                        Card backing = game.getCard(perm.getId());
                        // Control-changed commanders belong to another player's
                        // commander list; check against every seat's list.
                        if (backing != null && isAnyCommander(game, specs, byPid, backing)) {
                            commanders.add(backing);
                        }
                    }
                }
                commanders.sort(Comparator.comparing(c -> c.getId().toString()));
                for (Card c : commanders) {
                    CommanderInfoWatcher watcher = null;
                    try {
                        watcher = game.getState().getWatcher(CommanderInfoWatcher.class, c.getId());
                    } catch (RuntimeException ignore) {
                        watcher = null;
                    }
                    if (watcher == null) {
                        continue;
                    }
                    List<UUID> damaged = new ArrayList<>(watcher.getDamageToPlayer().keySet());
                    damaged.sort(Comparator.comparing(UUID::toString));
                    for (UUID pid : damaged) {
                        JsonObject o = new JsonObject();
                        o.addProperty("commander_uuid", c.getId().toString());
                        o.addProperty("damaged_uuid", pid.toString());
                        o.addProperty("amount", watcher.getDamageToPlayer().get(pid));
                        a.add(o);
                    }
                }
            }
        } catch (RuntimeException ignore) {
            // empty on error
        }
        return a;
    }

    private static boolean isAnyCommander(
            Game game, List<PlayerSpec> specs, Map<String, UUID> byPid, Card card) {
        for (PlayerSpec s : specs) {
            Player owner = game.getPlayer(byPid.get(s.playerId()));
            if (owner != null) {
                try {
                    if (game.isCommanderObject(owner, card)) {
                        return true;
                    }
                } catch (RuntimeException ignore) {
                    // continue across seats
                }
            }
        }
        return false;
    }

    private static JsonObject runtimeJarDigests() {        JsonObject out = new JsonObject();
        String cp = System.getProperty("java.class.path", "");
        for (String entry : cp.split(File.pathSeparator)) {
            if (entry.contains("org/mage") || entry.contains("org.mage")
                    || entry.matches(".*mage[^/]*\\.jar")) {
                try {
                    byte[] bytes = Files.readAllBytes(new File(entry).toPath());
                    out.addProperty(entry, shaHex(bytes));
                } catch (Exception exc) {
                    out.addProperty(entry, "UNREADABLE:" + exc.getMessage());
                }
            }
        }
        return out;
    }

    // ------------------------------------------------------------- assembly

    private static List<SemanticObject> parseObjects(JsonObject record) {
        List<SemanticObject> out = new ArrayList<>();
        if (!record.has("semantic_objects")) {
            return out;
        }
        for (var e : record.getAsJsonArray("semantic_objects")) {
            JsonObject o = e.getAsJsonObject();
            Map<String, Integer> counters = new HashMap<>();
            if (o.has("counters")) {
                for (var ce : o.getAsJsonObject("counters").entrySet()) {
                    counters.put(ce.getKey(), ce.getValue().getAsInt());
                }
            }
            out.add(new SemanticObject(
                    o.get("semantic_id").getAsString(),
                    o.get("card_identity").getAsString(),
                    str(o, "owner"),
                    str(o, "controller"),
                    str(o, "zone"),
                    o.has("face_down") && o.get("face_down").getAsBoolean(),
                    o.has("tapped") && o.get("tapped").getAsBoolean(),
                    counters,
                    o.has("zone_position") ? o.get("zone_position").getAsInt() : -1,
                    o.has("commander_id") ? o.get("commander_id").getAsString() : null));
        }
        return out;
    }

    private static void attachLedgers(
            JsonObject construction,
            List<PlacementLedger> ledger,
            List<FailedPlacement> failed,
            Map<String, String> fillerUuids,
            List<PlayerSpec> specs,
            List<SemanticObject> objects) {
        JsonArray la = new JsonArray();
        for (PlacementLedger l : ledger) {
            JsonObject o = new JsonObject();
            o.addProperty("semantic_id", l.semanticId());
            o.addProperty("native_id", l.nativeId());
            o.addProperty("zone", l.zone());
            la.add(o);
        }
        construction.add("placement_ledger", la);
        JsonArray fa = new JsonArray();
        for (FailedPlacement f : failed) {
            JsonObject o = new JsonObject();
            o.addProperty("semantic_id", f.semanticId());
            o.addProperty("code", f.code());
            o.addProperty("detail", f.detail());
            fa.add(o);
        }
        construction.add("failed_placements", fa);
        JsonObject fu = new JsonObject();
        for (Map.Entry<String, String> e : new TreeMap<>(fillerUuids).entrySet()) {
            fu.addProperty(e.getKey(), e.getValue());
        }
        construction.add("filler_uuids", fu);
        construction.addProperty("requested_object_count", objects.size());
        construction.addProperty("placed_object_count", ledger.size());
        construction.addProperty("player_count", specs.size());
    }

    private static JsonObject failReadback(
            JsonObject readback,
            JsonObject construction,
            List<PlacementLedger> ledger,
            List<FailedPlacement> failed,
            Map<String, String> fillerUuids,
            String code,
            String detail) {
        construction.addProperty("result", code.equals("CONSTRUCTED_OK") ? "CONSTRUCTED" : "CONSTRUCTION_FAIL");
        construction.addProperty("code", code);
        construction.addProperty("detail", detail);
        JsonArray fa = new JsonArray();
        for (FailedPlacement f : failed) {
            JsonObject o = new JsonObject();
            o.addProperty("semantic_id", f.semanticId());
            o.addProperty("code", f.code());
            o.addProperty("detail", f.detail());
            fa.add(o);
        }
        construction.add("failed_placements", fa);
        JsonArray la = new JsonArray();
        for (PlacementLedger l : ledger) {
            JsonObject o = new JsonObject();
            o.addProperty("semantic_id", l.semanticId());
            o.addProperty("native_id", l.nativeId());
            o.addProperty("zone", l.zone());
            la.add(o);
        }
        construction.add("placement_ledger", la);
        JsonObject fu = new JsonObject();
        for (Map.Entry<String, String> e : new TreeMap<>(fillerUuids).entrySet()) {
            fu.addProperty(e.getKey(), e.getValue());
        }
        construction.add("filler_uuids", fu);
        readback.add("construction", construction);
        return readback;
    }

    private static JsonObject fatalReadback(
            String fid, JsonObject record, String cplCommit, String cplTree, Throwable exc) {
        JsonObject readback = new JsonObject();
        readback.addProperty("schema_version", HARNESS_SCHEMA);
        readback.addProperty("fixture_id", fid);
        readback.addProperty("contract_digest",
                record == null ? null : (record.has("requested_state_digest")
                        ? record.get("requested_state_digest").getAsString() : null));
        readback.addProperty("execution_entry_mode",
                record == null ? null : (record.has("execution_entry_mode")
                        ? record.get("execution_entry_mode").getAsString() : null));
        JsonObject provenance = new JsonObject();
        provenance.addProperty("engine_repository", ENGINE_REPO);
        provenance.addProperty("engine_commit", ENGINE_COMMIT);
        provenance.addProperty("engine_tree", ENGINE_TREE);
        provenance.addProperty("cpl_commit", cplCommit);
        provenance.addProperty("cpl_tree", cplTree);
        readback.add("provenance", provenance);
        JsonObject construction = new JsonObject();
        construction.addProperty("result", "CONSTRUCTION_FAIL");
        construction.addProperty("code", "HARNESS_EXCEPTION");
        construction.addProperty("detail", rootMessage(exc));
        construction.add("failed_placements", new JsonArray());
        construction.add("placement_ledger", new JsonArray());
        construction.add("filler_uuids", new JsonObject());
        readback.add("construction", construction);
        return readback;
    }

    // ------------------------------------------------------------- helpers

    private static String str(JsonObject o, String key) {
        if (!o.has(key) || o.get(key).isJsonNull()) {
            return null;
        }
        return o.get(key).getAsString();
    }

    private static void prop(JsonObject o, String key, String value) {
        if (value == null) {
            o.add(key, com.google.gson.JsonNull.INSTANCE);
        } else {
            o.addProperty(key, value);
        }
    }

    private static String rootMessage(Throwable exc) {
        StringBuilder sb = new StringBuilder();
        Throwable cur = exc;
        int depth = 0;
        while (cur != null && depth < 4) {
            if (sb.length() > 0) {
                sb.append(" | caused by: ");
            }
            sb.append(cur.getClass().getSimpleName());
            if (cur.getMessage() != null) {
                String msg = cur.getMessage();
                sb.append(":").append(msg.length() > 300 ? msg.substring(0, 300) : msg);
            }
            cur = cur.getCause();
            depth++;
        }
        return sb.toString();
    }

    private static String shaHex(byte[] bytes) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(bytes);
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception exc) {
            throw new IllegalStateException(exc);
        }
    }
}
