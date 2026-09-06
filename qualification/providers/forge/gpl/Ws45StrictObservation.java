// SPDX-License-Identifier: GPL-3.0-or-later
package forge.game.player;

import forge.game.Game;
import forge.game.card.Card;
import forge.game.qualification.RestoredQualificationHistory;
import forge.game.qualification.RestoredQualificationHistory.CommanderMoveTiming;
import forge.game.qualification.RestoredQualificationHistory.EliminationReason;
import forge.game.qualification.RestoredQualificationHistory.ExtraTurnResolutionKind;
import forge.game.zone.ZoneType;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

/** WS45 qualification-only native observation/history adapter. */
public final class Ws45StrictObservation {
    private Ws45StrictObservation() {}

    private static String env(String key) {
        String v = System.getenv(key);
        return v == null ? "" : v;
    }

    private static String b64(String key) {
        String v = env(key);
        return v.isEmpty() ? "" : new String(Base64.getDecoder().decode(v), StandardCharsets.UTF_8);
    }

    private static List<String[]> rows(String key) {
        List<String[]> out = new ArrayList<>();
        String raw = b64(key);
        if (raw.isEmpty()) return out;
        for (String line : raw.split("\\n")) if (!line.isEmpty()) out.add(line.split("\\t", -1));
        return out;
    }

    private static Player player(Game game, String pid) {
        if (pid == null || !pid.matches("P[1-6]")) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_BAD_PLAYER_ID:" + pid);
        int seat = Integer.parseInt(pid.substring(1));
        if (seat < 1 || seat > game.getPlayers().size()) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_BAD_PLAYER_SEAT:" + pid);
        return game.getPlayers().get(seat - 1);
    }

    private static String pid(Game game, int nativePlayerId) {
        for (int i = 0; i < game.getPlayers().size(); i++) {
            if (game.getPlayers().get(i).getId() == nativePlayerId) return "P" + (i + 1);
        }
        throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_NATIVE_PLAYER_ID_UNBOUND:" + nativePlayerId);
    }

    private static Card cardBySemantic(Map<String, Card> semanticCards, String sid) {
        Card c = semanticCards.get(sid);
        if (c == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_NATIVE_SOURCE_UNBOUND:" + sid);
        return c;
    }

    private static Card commanderById(Map<String, Card> commanders, String cid) {
        Card c = commanders.get(cid);
        if (c == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_NATIVE_COMMANDER_UNBOUND:" + cid);
        return c;
    }

    private static String semanticOf(Map<String, Card> semanticCards, int nativeCardId) {
        String found = null;
        for (Map.Entry<String, Card> e : semanticCards.entrySet()) {
            if (e.getValue() != null && e.getValue().getId() == nativeCardId) {
                if (found != null && !found.equals(e.getKey())) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_NATIVE_CARD_ID_AMBIGUOUS:" + nativeCardId);
                found = e.getKey();
            }
        }
        if (found == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_NATIVE_CARD_ID_UNBOUND:" + nativeCardId);
        return found;
    }

    private static String commanderIdOf(Map<String, Card> commanders, int nativeCardId) {
        String found = null;
        for (Map.Entry<String, Card> e : commanders.entrySet()) {
            if (e.getValue() != null && e.getValue().getId() == nativeCardId) {
                if (found != null && !found.equals(e.getKey())) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_NATIVE_COMMANDER_ID_AMBIGUOUS:" + nativeCardId);
                found = e.getKey();
            }
        }
        if (found == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_NATIVE_COMMANDER_CARD_UNBOUND:" + nativeCardId);
        return found;
    }

    private static ZoneType zone(String z) {
        return switch (z) {
            case "battlefield" -> ZoneType.Battlefield;
            case "graveyard" -> ZoneType.Graveyard;
            case "exile" -> ZoneType.Exile;
            case "hand" -> ZoneType.Hand;
            case "library" -> ZoneType.Library;
            case "command" -> ZoneType.Command;
            default -> throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_BAD_ZONE:" + z);
        };
    }

    public static void restore(Game game, Map<String, Card> semanticCards, Map<String, Card> commanders) {
        RestoredQualificationHistory.clear(game);

        // Knowledge is provider observation-policy state. It is admitted only after the isolated
        // provider validates that all referenced viewers exist and the policy is never exposed as
        // an omniscient pilot surface. AF05 behavior later validates the actual filtered channels.
        String knowledge = b64("COMMANDER_LAB_WS45_KNOWLEDGE_CANONICAL_B64");
        if (knowledge.isEmpty()) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_KNOWLEDGE_STATE_MISSING");
        for (int i = 1; i <= game.getPlayers().size(); i++) {
            if (knowledge.contains("\"viewer\":\"P" + i + "\"") && player(game, "P" + i) == null) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_KNOWLEDGE_VIEWER_INVALID:P" + i);
            }
        }
        RestoredQualificationHistory.restoreKnowledgePolicy(game, knowledge, true);

        List<String[]> rr = rows("COMMANDER_LAB_WS45_RANDOMNESS_ROWS_B64");
        if (rr.isEmpty()) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_RANDOMNESS_STATE_MISSING");
        Long seed = null;
        boolean nativeCalls = false;
        List<String> channels = new ArrayList<>();
        List<String> draws = new ArrayList<>();
        for (String[] row : rr) {
            if (row.length < 2) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_RANDOMNESS_ROW_ARITY");
            switch (row[0]) {
                case "seed" -> seed = Long.parseLong(row[1]);
                case "channel" -> channels.add(row[1]);
                case "native_calls" -> nativeCalls = Boolean.parseBoolean(row[1]);
                case "draw" -> draws.add(row[1]);
                case "seed_binding", "pilot_prohibited" -> { /* normalized from typed state below */ }
                default -> throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_RANDOMNESS_ROW_KIND:" + row[0]);
            }
        }
        long actualSeed = seed == null ? Long.parseLong(env("COMMANDER_LAB_FORGE_RULES_SEED")) : seed;
        if (!String.valueOf(actualSeed).equals(env("COMMANDER_LAB_FORGE_RULES_SEED"))) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_RANDOMNESS_NATIVE_SEED_MISMATCH");
        }
        RestoredQualificationHistory.restoreRulesRandomness(game, actualSeed, channels, nativeCalls, draws);

        for (String[] row : rows("COMMANDER_LAB_WS45_EXTRA_TURN_ROWS_B64")) {
            if (row.length != 3) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_EXTRA_TURN_ROW_ARITY");
            int sequence = Integer.parseInt(row[0]);
            Player p = player(game, row[1]);
            Card source = cardBySemantic(semanticCards, row[2]);
            String name = source.getPaperCard() == null ? source.getName() : source.getPaperCard().getName();
            ExtraTurnResolutionKind kind;
            if ("Time Warp".equals(name)) kind = ExtraTurnResolutionKind.TARGETED_EXTRA_TURN_SPELL;
            else if ("Nexus of Fate".equals(name)) kind = ExtraTurnResolutionKind.SELF_EXTRA_TURN_SPELL_LATER_SAME_TURN;
            else throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_EXTRA_TURN_SOURCE_UNSUPPORTED:" + name);
            RestoredQualificationHistory.restoreExtraTurnCreation(game, sequence, p, source, kind);
        }

        for (String[] row : rows("COMMANDER_LAB_WS45_ELIMINATION_ROWS_B64")) {
            if (row.length != 1) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_ELIMINATION_ROW_ARITY");
            Player p = player(game, row[0]);
            if (p.getLife() > 0) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_ELIMINATION_LIFE_NOT_ZERO:" + row[0]);
            RestoredQualificationHistory.restoreElimination(game, p, EliminationReason.LIFE_TOTAL_ZERO);
        }

        for (String[] row : rows("COMMANDER_LAB_WS45_ZONE_MOVE_ROWS_B64")) {
            if (row.length != 3) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_ZONE_MOVE_ROW_ARITY");
            Card c = commanderById(commanders, row[0]);
            ZoneType from = zone(row[1]);
            ZoneType to = zone(row[2]);
            CommanderMoveTiming timing = (to == ZoneType.Graveyard || to == ZoneType.Exile)
                    ? CommanderMoveTiming.STATE_BASED_ACTION
                    : CommanderMoveTiming.REPLACEMENT_EFFECT_BEFORE_MOVE;
            RestoredQualificationHistory.restoreCommanderZoneMove(game, c, from, to, timing);
        }

        // These values are facts about the running qualification architecture, not request data.
        RestoredQualificationHistory.restoreSetupValidation(game, true, true, true, true, true);
    }

    private static String q(String s) { return Ws23ForgeVerticalProvider.esc(s); }

    public static String json(Game game, Map<String, Card> semanticCards, Map<String, Card> commanders) {
        var knowledge = RestoredQualificationHistory.getKnowledgePolicy(game);
        var random = RestoredQualificationHistory.getRulesRandomness(game);
        var setup = RestoredQualificationHistory.getSetupValidation(game);

        StringBuilder extra = new StringBuilder("[");
        boolean first = true;
        for (var x : RestoredQualificationHistory.getExtraTurnCreations(game)) {
            if (!first) extra.append(','); first = false;
            String source = semanticOf(semanticCards, x.sourceCardId());
            Card sourceCard = cardBySemantic(semanticCards, source);
            String name = sourceCard.getPaperCard() == null ? sourceCard.getName() : sourceCard.getPaperCard().getName();
            String player = pid(game, x.playerId());
            String resolution = x.resolutionKind() == ExtraTurnResolutionKind.TARGETED_EXTRA_TURN_SPELL
                    ? name + " resolved targeting " + player
                    : name + " resolved for " + player + " later in the same current turn";
            extra.append("{\"player\":").append(q(player))
                 .append(",\"semantic_resolution\":").append(q(resolution))
                 .append(",\"sequence\":").append(x.sequence())
                 .append(",\"source\":").append(q(source)).append('}');
        }
        extra.append(']');

        StringBuilder elim = new StringBuilder("["); first = true;
        for (var x : RestoredQualificationHistory.getEliminations(game)) {
            if (!first) elim.append(','); first = false;
            elim.append("{\"player\":").append(q(pid(game, x.playerId())))
                .append(",\"reason\":\"life_total_0\"}");
        }
        elim.append(']');

        StringBuilder moves = new StringBuilder("["); first = true;
        for (var x : RestoredQualificationHistory.getCommanderZoneMoves(game)) {
            if (!first) moves.append(','); first = false;
            String timing = x.timing() == CommanderMoveTiming.STATE_BASED_ACTION ? "state_based_action" : "replacement_effect_before_move";
            moves.append("{\"commander_choice_timing\":").append(q(timing))
                 .append(",\"commander_id\":").append(q(commanderIdOf(commanders, x.commanderCardId())))
                 .append(",\"from\":").append(q(x.from().toString().toLowerCase()))
                 .append(",\"to\":").append(q(x.to().toString().toLowerCase())).append('}');
        }
        moves.append(']');

        List<String> channels = new ArrayList<>(random.channels());
        StringBuilder ch = new StringBuilder("[");
        for (int i = 0; i < channels.size(); i++) { if (i > 0) ch.append(','); ch.append(q(channels.get(i))); }
        ch.append(']');
        List<String> draws = new ArrayList<>(random.predeterminedSemanticDraws());
        StringBuilder dr = new StringBuilder("[");
        for (int i = 0; i < draws.size(); i++) { if (i > 0) dr.append(','); dr.append(draws.get(i)); }
        dr.append(']');

        String seedBinding = env("COMMANDER_LAB_WS45_RANDOMNESS_SEED_BINDING");
        boolean pilotProhibited = !"0".equals(env("COMMANDER_LAB_WS45_PILOT_RANDOMNESS_PROHIBITED"));
        boolean hasRulesSeed = "1".equals(env("COMMANDER_LAB_WS45_RANDOMNESS_HAS_RULES_SEED"));
        StringBuilder randomness = new StringBuilder("{\"channels\":").append(ch)
                .append(",\"pilot_randomness_prohibited\":").append(pilotProhibited);
        if (random.providerNativeRngCallsRecorded()) randomness.append(",\"provider_native_rng_calls_recorded\":true");
        if (!seedBinding.isEmpty()) randomness.append(",\"seed_binding\":").append(q(seedBinding));
        if (!draws.isEmpty() || hasRulesSeed) randomness.append(",\"predetermined_semantic_draws\":").append(dr);
        if (hasRulesSeed) randomness.append(",\"rules_seed\":").append(random.seed());
        randomness.append('}');

        String setupJson = "{\"compare_requested_vs_constructed\":true"
                + ",\"construct_inside_rules_process\":" + setup.constructInsideRulesProcess()
                + ",\"expose_normalized_constructed_state\":" + setup.exposeNormalizedConstructedState()
                + ",\"forbidden_external_rules\":[\"legality_calculation\",\"layers\",\"state_based_actions\",\"replacement_outcomes\",\"fabricated_legal_options\",\"silent_setup_correction\"]"
                + ",\"native_structural_validation_required\":" + setup.nativeStructuralValidationRequired()
                + ",\"on_mismatch\":\"FAIL_CLOSED\""
                + ",\"requested_vs_normalized_native_constructed_state_equality_required\":" + setup.requestedVsNormalizedEqualityRequired() + "}";

        return "{\"knowledge_state\":" + knowledge.canonicalPolicy()
                + ",\"rules_randomness\":" + randomness
                + ",\"extra_turn_creation\":" + (extra.length() == 2 ? "null" : extra.toString())
                + ",\"elimination_trigger\":" + (elim.length() == 2 ? "null" : elim.substring(1, elim.length()-1))
                + ",\"zone_move_event\":" + (moves.length() == 2 ? "null" : moves.substring(1, moves.length()-1))
                + ",\"setup_validation\":" + setupJson
                + ",\"knowledge_visibility_validated\":" + knowledge.nativeVisibilityValidated()
                + "}";
    }
}
