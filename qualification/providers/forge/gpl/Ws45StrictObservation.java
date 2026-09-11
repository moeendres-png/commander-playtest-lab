// SPDX-License-Identifier: GPL-3.0-or-later
package forge.game.player;

import forge.game.Game;
import forge.game.card.Card;
import forge.game.qualification.NativeQualificationObservation;
import forge.game.qualification.Ws45ObservationPolicy;
import forge.game.qualification.Ws45ObservationPolicy.FactKind;
import forge.game.qualification.Ws45ObservationPolicy.KnowledgeFact;
import forge.game.qualification.Ws45ObservationPolicy.ObservationPolicy;
import forge.game.qualification.Ws45ObservationPolicy.ViewerPolicy;
import forge.game.qualification.Ws45ValidatedExtraTurnHistory;
import forge.game.qualification.Ws45ValidatedExtraTurnHistory.ResolutionKind;
import forge.game.zone.ZoneType;
import forge.item.PaperCard;

import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

/**
 * WS-45 qualification-only bridge from declarative setup operations to typed/native Forge
 * observation state. Canonical requested JSON is never retained or returned by this class.
 * Magic legality remains exclusively in Forge.
 */
public final class Ws45StrictObservation {
    private Ws45StrictObservation() {}

    private record MulliganDecision(int playerId, int cardsToReturn, boolean keep, int handSizeAtDecision) {}
    private static final Map<Game, List<MulliganDecision>> MULLIGANS =
            Collections.synchronizedMap(new WeakHashMap<>());

    private static String env(String key) {
        String v = System.getenv(key);
        return v == null ? "" : v;
    }

    private static String b64(String key) {
        String v = env(key);
        return v.isEmpty() ? "" : new String(Base64.getDecoder().decode(v), StandardCharsets.UTF_8);
    }

    private static String dec(String s) {
        return URLDecoder.decode(s == null ? "" : s, StandardCharsets.UTF_8);
    }

    private static List<String[]> rows(String key) {
        List<String[]> out = new ArrayList<>();
        String raw = b64(key);
        if (raw.isEmpty()) return out;
        for (String line : raw.split("\\n")) {
            if (!line.isEmpty()) out.add(line.split("\\t", -1));
        }
        return out;
    }

    private static List<String> list(String encoded) {
        String raw = dec(encoded);
        if (raw.isEmpty()) return List.of();
        return List.of(raw.split("\\u001f", -1));
    }

    private static Integer optInt(String raw) { return raw == null || raw.isEmpty() ? null : Integer.valueOf(raw); }
    private static Boolean optBool(String raw) { return raw == null || raw.isEmpty() ? null : Boolean.valueOf(raw); }

    private static Player player(Game game, String pid) {
        if (pid == null || !pid.matches("P[1-6]")) throw fail("WS45_BAD_PLAYER_ID:" + pid);
        int seat = Integer.parseInt(pid.substring(1));
        if (seat < 1 || seat > game.getPlayers().size()) throw fail("WS45_BAD_PLAYER_SEAT:" + pid);
        return game.getPlayers().get(seat - 1);
    }

    private static String pid(Game game, int nativePlayerId) {
        for (int i = 0; i < game.getPlayers().size(); i++) {
            if (game.getPlayers().get(i).getId() == nativePlayerId) return "P" + (i + 1);
        }
        throw fail("WS45_NATIVE_PLAYER_ID_UNBOUND:" + nativePlayerId);
    }

    private static Card semanticCard(Map<String, Card> semanticCards, String sid) {
        Card c = semanticCards.get(sid);
        if (c == null) throw fail("WS45_NATIVE_CARD_SEMANTIC_UNBOUND:" + sid);
        return c;
    }

    private static Card commander(Map<String, Card> commanders, String cid) {
        Card c = commanders.get(cid);
        if (c == null) throw fail("WS45_NATIVE_COMMANDER_UNBOUND:" + cid);
        return c;
    }

    private static String semanticOf(Map<String, Card> semanticCards, int nativeCardId) {
        String result = null;
        for (Map.Entry<String, Card> e : semanticCards.entrySet()) {
            if (e.getValue() != null && e.getValue().getId() == nativeCardId) {
                if (result != null && !result.equals(e.getKey())) throw fail("WS45_NATIVE_CARD_ID_AMBIGUOUS:" + nativeCardId);
                result = e.getKey();
            }
        }
        if (result == null) throw fail("WS45_NATIVE_CARD_ID_UNBOUND:" + nativeCardId);
        return result;
    }

    private static String commanderIdOf(Map<String, Card> commanders, int nativeCardId) {
        String result = null;
        for (Map.Entry<String, Card> e : commanders.entrySet()) {
            if (e.getValue() != null && e.getValue().getId() == nativeCardId) {
                if (result != null && !result.equals(e.getKey())) throw fail("WS45_NATIVE_COMMANDER_ID_AMBIGUOUS:" + nativeCardId);
                result = e.getKey();
            }
        }
        if (result == null) throw fail("WS45_NATIVE_COMMANDER_CARD_UNBOUND:" + nativeCardId);
        return result;
    }

    private static ZoneType zone(String z) {
        return switch (z) {
            case "battlefield" -> ZoneType.Battlefield;
            case "graveyard" -> ZoneType.Graveyard;
            case "exile" -> ZoneType.Exile;
            case "hand" -> ZoneType.Hand;
            case "library" -> ZoneType.Library;
            case "command" -> ZoneType.Command;
            default -> throw fail("WS45_BAD_ZONE:" + z);
        };
    }

    /** Install Rules RNG before Match.startGame/prepareAllZones. */
    public static void installRulesRandomnessBeforeGameStart() {
        List<String[]> rr = rows("COMMANDER_LAB_WS45_RANDOMNESS_ROWS_B64");
        if (rr.isEmpty()) throw fail("WS45_RANDOMNESS_STATE_MISSING");
        Long fixed = null;
        String binding = null;
        Long effective = null;
        boolean pilot = false;
        boolean nativeCalls = false;
        List<String> channels = new ArrayList<>();
        List<NativeQualificationObservation.PredeterminedDraw> draws = new ArrayList<>();
        for (String[] r : rr) {
            if (r.length < 2) throw fail("WS45_RANDOMNESS_ROW_ARITY");
            switch (r[0]) {
                case "fixed_seed" -> fixed = r[1].isEmpty() ? null : Long.valueOf(r[1]);
                case "seed_binding" -> binding = dec(r[1]);
                case "effective_seed" -> effective = Long.valueOf(r[1]);
                case "pilot_prohibited" -> pilot = Boolean.parseBoolean(r[1]);
                case "native_calls" -> nativeCalls = Boolean.parseBoolean(r[1]);
                case "channel" -> channels.add(dec(r[1]));
                case "draw" -> {
                    if (r.length != 4) throw fail("WS45_RANDOMNESS_DRAW_ARITY");
                    draws.add(new NativeQualificationObservation.PredeterminedDraw(dec(r[1]), dec(r[2]), dec(r[3])));
                }
                default -> throw fail("WS45_RANDOMNESS_ROW_KIND:" + r[0]);
            }
        }
        if (effective == null) throw fail("WS45_RANDOMNESS_EFFECTIVE_SEED_MISSING");
        NativeQualificationObservation.installRulesRandomness(fixed, binding, effective, channels, draws, pilot, nativeCalls);
    }

    /** Convert inputs to typed/native Forge observation state and validate native rule relations. */
    public static void afterNativeStateLoad(Game game, Map<String, Card> semanticCards, Map<String, Card> commanders) {
        installKnowledge(game, semanticCards);
        Ws45ValidatedExtraTurnHistory.clear(game);
        for (String[] r : rows("COMMANDER_LAB_WS45_EXTRA_TURN_ROWS_B64")) {
            if (r.length != 3) throw fail("WS45_EXTRA_TURN_ROW_ARITY");
            Ws45ValidatedExtraTurnHistory.validateAndRecord(
                    game, Integer.parseInt(r[0]), player(game, dec(r[1])), semanticCard(semanticCards, dec(r[2])));
        }
        NativeQualificationObservation.clear(game);
        for (String[] r : rows("COMMANDER_LAB_WS45_ZONE_MOVE_ROWS_B64")) {
            if (r.length != 2) throw fail("WS45_ZONE_MOVE_ROW_ARITY");
            NativeQualificationObservation.validateCommanderMovePlan(game, commander(commanders, dec(r[0])), zone(dec(r[1])));
        }
        for (String[] r : rows("COMMANDER_LAB_WS45_PARTNER_ROWS_B64")) {
            if (r.length != 2) throw fail("WS45_PARTNER_ROW_ARITY");
            NativeQualificationObservation.validatePartnerRelation(game, commander(commanders, dec(r[0])), commander(commanders, dec(r[1])));
        }
    }

    /** Natural records have no object knowledge facts, but still install the typed policy. */
    public static void prepareNatural(Game game) {
        installKnowledge(game, Map.of());
        synchronized (MULLIGANS) { MULLIGANS.put(game, new ArrayList<>()); }
    }

    private static void installKnowledge(Game game, Map<String, Card> semanticCards) {
        String channelPolicy = b64("COMMANDER_LAB_WS45_KNOWLEDGE_CHANNEL_POLICY_B64");
        if (channelPolicy.isEmpty()) throw fail("WS45_KNOWLEDGE_CHANNEL_POLICY_MISSING");
        Map<String, List<KnowledgeFact>> facts = new LinkedHashMap<>();
        for (String[] r : rows("COMMANDER_LAB_WS45_KNOWLEDGE_FACT_ROWS_B64")) {
            if (r.length != 15) throw fail("WS45_KNOWLEDGE_FACT_ARITY:" + r.length);
            String viewerPid = dec(r[1]);
            int viewerId = player(game, viewerPid).getId();
            Integer objectId = r[2].isEmpty() ? null : semanticCard(semanticCards, dec(r[2])).getId();
            Integer libraryPlayerId = r[3].isEmpty() ? null : player(game, dec(r[3])).getId();
            Integer controlledId = r[12].isEmpty() ? null : player(game, dec(r[12])).getId();
            Integer controllerId = r[13].isEmpty() ? null : player(game, dec(r[13])).getId();
            boolean allPlayers = "ALL_PLAYERS".equals(dec(r[14]));
            Integer permissionViewerId = r[14].isEmpty() || allPlayers ? null : player(game, dec(r[14])).getId();
            FactKind fk = FactKind.valueOf(r[0]);
            facts.computeIfAbsent(viewerPid, ignored -> new ArrayList<>()).add(new KnowledgeFact(
                    fk, viewerId, objectId, libraryPlayerId,
                    dec(r[4]), dec(r[5]), dec(r[6]), optInt(r[7]), optInt(r[8]), optBool(r[9]), optBool(r[10]), dec(r[11]),
                    controlledId, controllerId, permissionViewerId, allPlayers));
        }
        List<ViewerPolicy> viewers = new ArrayList<>();
        for (String[] r : rows("COMMANDER_LAB_WS45_KNOWLEDGE_VIEWER_ROWS_B64")) {
            if (r.length != 14) throw fail("WS45_KNOWLEDGE_VIEWER_ARITY:" + r.length);
            String vp = dec(r[0]);
            viewers.add(new ViewerPolicy(
                    player(game, vp).getId(),
                    Boolean.parseBoolean(r[1]), list(r[2]),
                    Boolean.parseBoolean(r[3]), list(r[4]),
                    list(r[5]), Boolean.parseBoolean(r[6]), dec(r[7]),
                    Boolean.parseBoolean(r[8]), list(r[9]),
                    Boolean.parseBoolean(r[10]), list(r[11]),
                    Boolean.parseBoolean(r[12]), list(r[13]),
                    facts.getOrDefault(vp, List.of())));
        }
        Ws45ObservationPolicy.clear(game);
        Ws45ObservationPolicy.install(game, new ObservationPolicy(channelPolicy, viewers));
    }

    public static void recordMulliganDecision(Game game, Player player, int cardsToReturn, boolean keep) {
        synchronized (MULLIGANS) {
            MULLIGANS.computeIfAbsent(game, ignored -> new ArrayList<>())
                    .add(new MulliganDecision(player.getId(), cardsToReturn, keep, player.getCardsIn(ZoneType.Hand).size()));
        }
    }

    private static String q(String s) { return Ws23ForgeVerticalProvider.esc(s); }

    private static String randomnessJson() {
        var r = NativeQualificationObservation.getRulesRandomness();
        boolean fixedPresent = "1".equals(env("COMMANDER_LAB_WS45_RANDOMNESS_HAS_FIXED_SEED"));
        boolean bindingPresent = "1".equals(env("COMMANDER_LAB_WS45_RANDOMNESS_HAS_SEED_BINDING"));
        boolean drawsPresent = "1".equals(env("COMMANDER_LAB_WS45_RANDOMNESS_HAS_PREDETERMINED"));
        boolean nativePresent = "1".equals(env("COMMANDER_LAB_WS45_RANDOMNESS_HAS_NATIVE_CALLS"));
        StringBuilder b = new StringBuilder("{\"channels\":[");
        for (int i = 0; i < r.declaredChannels().size(); i++) {
            if (i > 0) b.append(','); b.append(q(r.declaredChannels().get(i)));
        }
        b.append("],\"pilot_randomness_prohibited\":").append(r.pilotRandomnessProhibited());
        if (nativePresent) b.append(",\"provider_native_rng_calls_recorded\":").append(r.providerNativeRngCallsRecorded());
        if (bindingPresent) b.append(",\"seed_binding\":").append(q(r.seedBinding()));
        if (drawsPresent) {
            b.append(",\"predetermined_semantic_draws\":[");
            for (int i = 0; i < r.predeterminedDraws().size(); i++) {
                if (i > 0) b.append(',');
                var d = r.predeterminedDraws().get(i);
                b.append("{\"channel\":").append(q(d.channel())).append(",\"operation\":").append(q(d.operation()))
                        .append(",\"result\":").append(q(d.result())).append('}');
            }
            b.append(']');
        }
        if (fixedPresent) b.append(",\"rules_seed\":").append(r.fixedSeed());
        return b.append('}').toString();
    }

    private static String extraTurnJson(Game game, Map<String, Card> semanticCards) {
        List<Ws45ValidatedExtraTurnHistory.Entry> entries = Ws45ValidatedExtraTurnHistory.get(game);
        if (entries.isEmpty()) return "null";
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < entries.size(); i++) {
            if (i > 0) b.append(',');
            var e = entries.get(i);
            String p = pid(game, e.playerId());
            String sid = semanticOf(semanticCards, e.sourceCardId());
            Card source = semanticCard(semanticCards, sid);
            String name = source.getPaperCard() == null ? source.getName() : source.getPaperCard().getName();
            String resolution = e.kind() == ResolutionKind.TARGETED_EXTRA_TURN
                    ? name + " resolved targeting " + p
                    : name + " resolved for " + p + " later in the same current turn";
            b.append("{\"player\":").append(q(p)).append(",\"semantic_resolution\":").append(q(resolution))
                    .append(",\"sequence\":").append(e.sequence()).append(",\"source\":").append(q(sid)).append('}');
        }
        return b.append(']').toString();
    }

    private static String eliminationJson(Game game) {
        var e = NativeQualificationObservation.pendingStateBasedEliminations(game);
        if (e.isEmpty()) return "null";
        if (e.size() != 1) throw fail("WS45_ELIMINATION_NONUNIQUE:" + e.size());
        return "{\"player\":" + q(pid(game, e.get(0).playerId())) + ",\"reason\":" + q(e.get(0).reason()) + "}";
    }

    private static String zoneMoveJson(Game game, Map<String, Card> commanders) {
        var moves = NativeQualificationObservation.getCommanderMovePlans(game);
        if (moves.isEmpty()) return "null";
        if (moves.size() != 1) throw fail("WS45_ZONE_MOVE_NONUNIQUE:" + moves.size());
        var m = moves.get(0);
        String timing = m.timing() == NativeQualificationObservation.CommanderMoveTiming.STATE_BASED_ACTION
                ? "state_based_action" : "replacement_effect_before_move";
        return "{\"commander_choice_timing\":" + q(timing)
                + ",\"commander_id\":" + q(commanderIdOf(commanders, m.commanderCardId()))
                + ",\"from\":" + q(m.from().toString().toLowerCase())
                + ",\"to\":" + q(m.to().toString().toLowerCase()) + "}";
    }

    private static String partnerJson(Game game, Map<String, Card> commanders) {
        var rel = NativeQualificationObservation.getPartnerRelations(game);
        if (rel.isEmpty()) return "[]";
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < rel.size(); i++) {
            if (i > 0) b.append(',');
            var x = rel.get(i);
            b.append("{\"commander_ids\":[").append(q(commanderIdOf(commanders, x.firstCommanderCardId())))
                    .append(',').append(q(commanderIdOf(commanders, x.secondCommanderCardId())))
                    .append("],\"relation\":\"Partner\"}");
        }
        return b.append(']').toString();
    }

    private static String setupJson() {
        return "{\"compare_requested_vs_constructed\":true,\"construct_inside_rules_process\":true"
                + ",\"expose_normalized_constructed_state\":true"
                + ",\"forbidden_external_rules\":[\"legality_calculation\",\"layers\",\"state_based_actions\",\"replacement_outcomes\",\"fabricated_legal_options\",\"silent_setup_correction\"]"
                + ",\"native_structural_validation_required\":true,\"on_mismatch\":\"FAIL_CLOSED\""
                + ",\"requested_vs_normalized_native_constructed_state_equality_required\":true}";
    }

    public static String json(Game game, Map<String, Card> semanticCards, Map<String, Card> commanders) {
        String knowledge = Ws45ObservationPolicy.toContractJson(game,
                id -> pid(game, id), id -> semanticOf(semanticCards, id));
        return "{\"knowledge_state\":" + knowledge
                + ",\"rules_randomness\":" + randomnessJson()
                + ",\"extra_turn_creation\":" + extraTurnJson(game, semanticCards)
                + ",\"elimination_trigger\":" + eliminationJson(game)
                + ",\"zone_move_event\":" + zoneMoveJson(game, commanders)
                + ",\"multiple_commander_relations\":" + partnerJson(game, commanders)
                + ",\"setup_validation\":" + setupJson() + "}";
    }

    private static String mulliganTraceJson(Game game) {
        List<MulliganDecision> trace;
        synchronized (MULLIGANS) { trace = List.copyOf(MULLIGANS.getOrDefault(game, List.of())); }
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < trace.size(); i++) {
            if (i > 0) b.append(',');
            var x = trace.get(i);
            b.append("{\"player\":").append(q(pid(game, x.playerId())))
                    .append(",\"cards_to_return\":").append(x.cardsToReturn())
                    .append(",\"keep\":").append(x.keep())
                    .append(",\"hand_size_at_decision\":").append(x.handSizeAtDecision()).append('}');
        }
        return b.append(']').toString();
    }

    private static String naturalDecksJson(Game game) {
        StringBuilder decks = new StringBuilder("[");
        List<RegisteredPlayer> rps = game.getMatch().getPlayers();
        for (int i = 0; i < rps.size(); i++) {
            if (i > 0) decks.append(',');
            RegisteredPlayer rp = rps.get(i);
            int mainCount = 0, mountainCount = 0;
            for (Map.Entry<PaperCard,Integer> e : rp.getDeck().getMain()) {
                mainCount += e.getValue();
                if ("Mountain".equals(e.getKey().getName())) mountainCount += e.getValue();
            }
            StringBuilder commanderNames = new StringBuilder("[");
            for (int j = 0; j < rp.getCommanders().size(); j++) {
                if (j > 0) commanderNames.append(','); commanderNames.append(q(rp.getCommanders().get(j).getName()));
            }
            commanderNames.append(']');
            Player p = game.getPlayers().get(i);
            decks.append("{\"player_id\":\"P").append(i + 1).append("\",\"main_count\":").append(mainCount)
                    .append(",\"mountain_count\":").append(mountainCount)
                    .append(",\"commander_count\":").append(rp.getCommanders().size())
                    .append(",\"commander_names\":").append(commanderNames)
                    .append(",\"registered_starting_life\":").append(rp.getStartingLife())
                    .append(",\"live_life\":").append(p.getLife())
                    .append(",\"hand_count\":").append(p.getCardsIn(ZoneType.Hand).size())
                    .append(",\"library_count\":").append(p.getCardsIn(ZoneType.Library).size())
                    .append(",\"native_commander_count\":").append(p.getCommanders().size()).append('}');
        }
        return decks.append(']').toString();
    }

    /** Called by the real Match.startGame hook, after native mulligan processing and first-turn setup. */
    public static void emitNaturalLifecycle(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        String phase = game.getPhaseHandler().getPhase() == null ? null : game.getPhaseHandler().getPhase().toString();
        String raw = "{\"natural_lifecycle\":true,\"provider_entry_mode\":\"NATURAL_GAME_START\""
                + ",\"player_count\":" + game.getPlayers().size()
                + ",\"rules_commander\":" + game.getRules().hasAppliedVariant(forge.game.GameType.Commander)
                + ",\"decks\":" + naturalDecksJson(game)
                + ",\"mulligan_trace\":" + mulliganTraceJson(game)
                + ",\"native_turn\":" + game.getPhaseHandler().getTurn()
                + ",\"native_phase\":" + q(phase)
                + ",\"native_active_player\":" + q(pid(game, game.getPhaseHandler().getPlayerTurn().getId()))
                + ",\"native_priority_player\":" + (game.getPhaseHandler().getPriorityPlayer() == null ? "null" : q(pid(game, game.getPhaseHandler().getPriorityPlayer().getId())))
                + ",\"knowledge_state\":" + Ws45ObservationPolicy.toContractJson(game, id -> pid(game, id), id -> { throw fail("WS45_NATURAL_CARD_SEMANTIC_UNEXPECTED:" + id); })
                + ",\"rules_randomness\":" + randomnessJson()
                + ",\"setup_validation\":" + setupJson() + "}";
        broker.out.println("{\"protocol\":" + q(Ws23ForgeVerticalProvider.PROTOCOL)
                + ",\"message_type\":\"QUALIFICATION_STATE\",\"request_id\":\"ws45-natural-lifecycle\",\"session_id\":"
                + q(Ws23ForgeVerticalProvider.SESSION_ID)
                + ",\"payload\":{\"stage\":\"native_post_mulligan_pre_main_loop\",\"raw_native\":" + raw + "}}");
        broker.out.flush();
        if ("1".equals(env("COMMANDER_LAB_WS40_CONSTRUCTION_ONLY"))) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_CONSTRUCTION_COMPLETE");
        }
    }

    private static Ws23ForgeVerticalProvider.ControlledStop fail(String msg) {
        return new Ws23ForgeVerticalProvider.ControlledStop(msg);
    }
}
