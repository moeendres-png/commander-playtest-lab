// SPDX-License-Identifier: GPL-3.0-or-later
package forge.game.player;

import forge.CardStorageReader;
import forge.StaticData;
import forge.card.CardRarity;
import forge.card.CardRules;
import forge.game.Game;
import forge.game.GameEntity;
import forge.game.GameState;
import forge.game.card.Card;
import forge.game.card.CounterType;
import forge.game.combat.Combat;
import forge.game.phase.PhaseType;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.item.PaperCard;

import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Qualification-only native state-loader/observer for WS-40.
 *
 * The input is declarative state data supplied to the isolated GPL Forge JVM.
 * Magic legality is never computed here. State is materialized through Forge
 * GameState plus direct native Commander/Combat/Stack APIs where GameState does
 * not carry the required multiplayer state. The emitted snapshot is rebuilt
 * from the resulting native Forge objects and is intentionally not a copy of
 * the requested JSON projection.
 */
public final class Ws40SuccessorState {
    private Ws40SuccessorState() {}

    private static final Map<String, Card> semanticCards = new LinkedHashMap<>();
    private static final Map<String, Card> commanderCards = new LinkedHashMap<>();
    private static final Map<String, SpellAbility> stackAbilities = new LinkedHashMap<>();
    private static final List<ObjSpec> objectSpecs = new ArrayList<>();

    static final class ObjSpec {
        final String semanticId;
        final String name;
        final int owner;
        final int controller;
        final String zone;
        final boolean tapped;
        final boolean faceDown;
        final String counters;
        final String attachedTo;
        final Integer zonePosition;
        final String commanderId;
        final boolean controlledSinceTurnBegan;
        final boolean emitSemantic;

        ObjSpec(String[] p) {
            semanticId = dec(p[0]);
            name = dec(p[1]);
            owner = Integer.parseInt(p[2]);
            controller = Integer.parseInt(p[3]);
            zone = p[4];
            tapped = Boolean.parseBoolean(p[5]);
            faceDown = Boolean.parseBoolean(p[6]);
            counters = dec(p[7]);
            attachedTo = dec(p[8]);
            zonePosition = p[9].isEmpty() ? null : Integer.valueOf(p[9]);
            commanderId = dec(p[10]);
            controlledSinceTurnBegan = Boolean.parseBoolean(p[11]);
            emitSemantic = Boolean.parseBoolean(p[12]);
        }
    }

    private static String env(String name) {
        String value = System.getenv(name);
        return value == null ? "" : value;
    }

    private static String decodeB64Env(String name) {
        String value = env(name);
        if (value.isEmpty()) return "";
        return new String(Base64.getDecoder().decode(value), StandardCharsets.UTF_8);
    }

    private static String dec(String value) {
        return URLDecoder.decode(value, StandardCharsets.UTF_8);
    }

    private static List<String[]> rows(String envName) {
        List<String[]> out = new ArrayList<>();
        String raw = decodeB64Env(envName);
        if (raw.isEmpty()) return out;
        for (String line : raw.split("\\n")) {
            if (line.isEmpty()) continue;
            out.add(line.split("\\t", -1));
        }
        return out;
    }

    private static Player player(Game game, int seat) {
        if (seat < 1 || seat > game.getPlayers().size()) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_BAD_SEAT:" + seat);
        }
        return game.getPlayers().get(seat - 1);
    }

    private static String playerId(Game game, Player p) {
        int idx = game.getPlayers().indexOf(p);
        return idx < 0 ? null : "P" + (idx + 1);
    }

    private static ZoneType zoneType(String value) {
        return switch (value) {
            case "battlefield" -> ZoneType.Battlefield;
            case "hand" -> ZoneType.Hand;
            case "graveyard" -> ZoneType.Graveyard;
            case "library" -> ZoneType.Library;
            case "exile" -> ZoneType.Exile;
            case "command" -> ZoneType.Command;
            case "sideboard" -> ZoneType.Sideboard;
            case "stack" -> ZoneType.Stack;
            default -> throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_BAD_ZONE:" + value);
        };
    }

    private static String phaseStateValue() {
        String phase = env("COMMANDER_LAB_WS40_PHASE");
        String step = env("COMMANDER_LAB_WS40_STEP");
        if ("combat".equals(phase)) return "MAIN1"; // direct multiplayer combat extension follows GameState.
        if ("precombat_main".equals(phase)) return "MAIN1";
        if ("postcombat_main".equals(phase)) return "MAIN2";
        if ("beginning".equals(phase) && "upkeep".equals(step)) return "UPKEEP";
        if ("beginning".equals(phase) && "draw".equals(step)) return "DRAW";
        return "MAIN1";
    }

    private static PhaseType requestedPhaseType() {
        String phase = env("COMMANDER_LAB_WS40_PHASE");
        String step = env("COMMANDER_LAB_WS40_STEP");
        if ("combat".equals(phase)) {
            if ("declare_attackers".equals(step)) return PhaseType.COMBAT_DECLARE_ATTACKERS;
            if ("declare_blockers".equals(step)) return PhaseType.COMBAT_DECLARE_BLOCKERS;
            if ("combat_damage".equals(step)) return PhaseType.COMBAT_DAMAGE;
            return PhaseType.COMBAT_BEGIN;
        }
        if ("precombat_main".equals(phase)) return PhaseType.MAIN1;
        if ("postcombat_main".equals(phase)) return PhaseType.MAIN2;
        if ("beginning".equals(phase) && "upkeep".equals(step)) return PhaseType.UPKEEP;
        if ("beginning".equals(phase) && "draw".equals(step)) return PhaseType.DRAW;
        return PhaseType.MAIN1;
    }

    private static void registerCardRules(Set<String> names) {
        try {
            String lang = env("COMMANDER_LAB_FORGE_LANG_DIR");
            if (lang.isEmpty()) throw new IllegalStateException("COMMANDER_LAB_FORGE_LANG_DIR missing");
            Path root = Path.of(lang).toAbsolutePath().normalize().getParent().getParent().getParent();
            CardStorageReader reader = new CardStorageReader(root.resolve("forge-gui/res/cardsfolder").toString(), null, true);
            for (String name : names) {
                if (name.isEmpty()) continue;
                if (StaticData.instance().getCommonCards().getCard(name) != null) continue;
                CardRules rules = reader.attemptToLoadCard(name);
                if (rules == null) throw new IllegalStateException("missing native card rules: " + name);
                StaticData.instance().getCommonCards().addCard(new PaperCard(rules, "M11", CardRarity.Common));
            }
        } catch (Exception e) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_CARD_REGISTRATION:" + e.getClass().getSimpleName() + ":" + e.getMessage());
        }
    }

    private static String cardEntry(ObjSpec s, Map<String,Integer> ids) {
        StringBuilder b = new StringBuilder(s.name).append("|Id:").append(ids.get(s.semanticId));
        if (s.owner != s.controller) b.append("|Owner:P").append(s.owner - 1);
        if (!s.commanderId.isEmpty()) b.append("|IsCommander");
        if (s.tapped) b.append("|Tapped");
        if (s.faceDown) b.append("|FaceDown");
        if (!s.counters.isEmpty()) b.append("|Counters:").append(s.counters);
        if (!s.attachedTo.isEmpty()) b.append("|AttachedTo:").append(ids.get(s.attachedTo));
        if ("battlefield".equals(s.zone)) b.append("|NoETBTrigs");
        return b.toString();
    }

    private static void loadObjectSpecs() {
        objectSpecs.clear();
        for (String[] p : rows("COMMANDER_LAB_WS40_OBJECT_SPECS_B64")) {
            if (p.length != 13) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_OBJECT_SPEC_ARITY:" + p.length);
            objectSpecs.add(new ObjSpec(p));
        }
    }

    private static List<String> buildGameStateLines(Game game) {
        int turn = Integer.parseInt(env("COMMANDER_LAB_WS40_TURN"));
        int active = Integer.parseInt(env("COMMANDER_LAB_WS40_ACTIVE_SEAT"));
        List<String> lines = new ArrayList<>();
        lines.add("turn=" + turn);
        lines.add("activeplayer=p" + (active - 1));
        lines.add("activephase=" + phaseStateValue());

        Map<String,Integer> ids = new HashMap<>();
        int next = 1000;
        for (ObjSpec s : objectSpecs) ids.put(s.semanticId, next++);

        for (int seat = 1; seat <= game.getPlayers().size(); seat++) {
            String prefix = "p" + (seat - 1);
            String life = env("COMMANDER_LAB_WS40_LIFE_P" + seat);
            lines.add(prefix + "life=" + (life.isEmpty() ? "40" : life));
            for (String zone : List.of("battlefield","hand","graveyard","library","exile","command","sideboard")) {
                List<ObjSpec> specs = new ArrayList<>();
                for (ObjSpec s : objectSpecs) {
                    if (s.controller == seat && zone.equals(s.zone)) specs.add(s);
                }
                if ("library".equals(zone)) {
                    specs.sort(Comparator.comparingInt(s -> s.zonePosition == null ? Integer.MAX_VALUE : s.zonePosition));
                }
                List<String> values = new ArrayList<>();
                for (ObjSpec s : specs) values.add(cardEntry(s, ids));
                lines.add(prefix + zone + "=" + String.join(";", values));
            }
        }
        return lines;
    }

    private static boolean sameCard(Card c, ObjSpec s, Set<Card> used) {
        if (used.contains(c)) return false;
        String name = c.getPaperCard() == null ? c.getName() : c.getPaperCard().getName();
        if (!s.name.equals(name)) return false;
        if (c.getOwner() != player(c.getGame(), s.owner)) return false;
        if (c.getController() != player(c.getGame(), s.controller)) return false;
        if (c.getZone() == null || !c.getZone().is(zoneType(s.zone))) return false;
        return true;
    }

    private static void bindNonStackObjects(Game game) {
        semanticCards.clear();
        commanderCards.clear();
        Set<Card> used = new HashSet<>();
        for (ObjSpec s : objectSpecs) {
            if ("stack".equals(s.zone)) continue;
            List<Card> candidates = new ArrayList<>();
            for (Card c : player(game, s.controller).getCardsIn(zoneType(s.zone), false)) {
                if (sameCard(c, s, used)) candidates.add(c);
            }
            if (s.zonePosition != null && "library".equals(s.zone)) {
                Card at = player(game, s.controller).getCardsIn(ZoneType.Library, false).get(s.zonePosition);
                candidates.clear();
                if (sameCard(at, s, used)) candidates.add(at);
            }
            if (candidates.size() != 1) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_BIND_NONUNIQUE:" + s.semanticId + ":" + candidates.size());
            }
            Card c = candidates.get(0);
            used.add(c);
            semanticCards.put(s.semanticId, c);
            if (!s.commanderId.isEmpty()) commanderCards.put(s.commanderId, c);
        }
    }

    private static void applyCommanderState(Game game) {
        for (String[] p : rows("COMMANDER_LAB_WS40_COMMANDER_SPECS_B64")) {
            if (p.length != 3) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_COMMANDER_SPEC_ARITY");
            String commanderId = dec(p[0]);
            String semanticId = dec(p[1]);
            int prior = Integer.parseInt(p[2]);
            Card c = semanticCards.get(semanticId);
            if (c == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_COMMANDER_UNBOUND:" + commanderId);
            commanderCards.put(commanderId, c);
            Player owner = c.getOwner();
            if (!owner.getCommanders().contains(c)) owner.addCommander(c);
            for (int i = owner.getCommanderCast(c); i < prior; i++) owner.incCommanderCast(c);
            if (owner.getCommanderCast(c) != prior) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_COMMANDER_CAST_MISMATCH:" + commanderId);
        }
        for (String[] p : rows("COMMANDER_LAB_WS40_DAMAGE_SPECS_B64")) {
            if (p.length != 3) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_DAMAGE_SPEC_ARITY");
            Card source = commanderCards.get(dec(p[0]));
            Player damaged = player(game, Integer.parseInt(p[1]));
            int amount = Integer.parseInt(p[2]);
            if (source == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_DAMAGE_SOURCE_UNBOUND:" + dec(p[0]));
            damaged.addCommanderDamage(source, amount);
        }
    }

    private static GameEntity target(Game game, String key) {
        if (key.matches("P[1-5]")) return player(game, Integer.parseInt(key.substring(1)));
        Card c = semanticCards.get(key);
        if (c == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_TARGET_UNBOUND:" + key);
        return c;
    }

    private static void applyStack(Game game) {
        stackAbilities.clear();
        for (String[] p : rows("COMMANDER_LAB_WS40_STACK_SPECS_B64")) {
            if (p.length != 5) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_STACK_SPEC_ARITY:" + p.length);
            String sid = dec(p[0]);
            int ownerSeat = Integer.parseInt(p[1]);
            int controllerSeat = Integer.parseInt(p[2]);
            String name = dec(p[3]);
            String targetCsv = dec(p[4]);
            PaperCard pc = StaticData.instance().getCommonCards().getCard(name);
            if (pc == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_STACK_CARD_MISSING:" + name);
            Card host = Card.fromPaperCard(pc, player(game, ownerSeat));
            if (ownerSeat != controllerSeat) host.setController(player(game, controllerSeat), game.getNextTimestamp());
            SpellAbility sa = host.getFirstSpellAbility();
            if (sa == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_STACK_NO_SA:" + name);
            sa.setActivatingPlayer(player(game, controllerSeat));
            if (!targetCsv.isEmpty()) {
                for (String key : targetCsv.split(",")) sa.getTargets().add(target(game, key));
            }
            game.getStack().addAndUnfreeze(sa);
            stackAbilities.put(sid, sa);
            semanticCards.put(sid, sa.getHostCard());
        }
    }

    private static void applyCombat(Game game) {
        List<String[]> combatRows = rows("COMMANDER_LAB_WS40_COMBAT_SPECS_B64");
        if (combatRows.isEmpty()) return;
        int active = Integer.parseInt(env("COMMANDER_LAB_WS40_ACTIVE_SEAT"));
        Combat combat = new Combat(player(game, active));
        game.getPhaseHandler().setCombat(combat);
        for (String[] p : combatRows) {
            if (p.length != 3) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_COMBAT_SPEC_ARITY");
            if ("A".equals(p[0])) {
                Card attacker = semanticCards.get(dec(p[1]));
                GameEntity defender = target(game, dec(p[2]));
                if (attacker == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_ATTACKER_UNBOUND:" + dec(p[1]));
                combat.addAttacker(attacker, defender);
            }
        }
        for (String[] p : combatRows) {
            if ("B".equals(p[0])) {
                Card blocker = semanticCards.get(dec(p[1]));
                Card attacker = semanticCards.get(dec(p[2]));
                if (blocker == null || attacker == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_BLOCK_UNBOUND");
                combat.addBlocker(attacker, blocker);
                combat.setBlocked(attacker, true);
            }
        }
        game.updateCombatForView();
    }

    public static void applyNativeState(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        loadObjectSpecs();
        Set<String> names = new HashSet<>();
        for (ObjSpec s : objectSpecs) names.add(s.name);
        for (String[] p : rows("COMMANDER_LAB_WS40_STACK_SPECS_B64")) if (p.length >= 4) names.add(dec(p[3]));
        registerCardRules(names);

        GameState state = new GameState();
        state.parse(buildGameStateLines(game));
        state.applyToGame(game);

        int active = Integer.parseInt(env("COMMANDER_LAB_WS40_ACTIVE_SEAT"));
        int turn = Integer.parseInt(env("COMMANDER_LAB_WS40_TURN"));
        game.getPhaseHandler().devModeSet(requestedPhaseType(), player(game, active), turn);
        String priority = env("COMMANDER_LAB_WS40_PRIORITY_SEAT");
        if (!priority.isEmpty()) game.getPhaseHandler().setPriority(player(game, Integer.parseInt(priority)));

        bindNonStackObjects(game);
        applyCommanderState(game);
        applyStack(game);
        applyCombat(game);
        emitNativeSnapshot(game, broker, false);
        if ("1".equals(env("COMMANDER_LAB_WS40_CONSTRUCTION_ONLY"))) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_CONSTRUCTION_COMPLETE");
        }
    }

    public static void emitNaturalRegistration(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        StringBuilder decks = new StringBuilder("[");
        for (int i = 0; i < game.getMatch().getPlayers().size(); i++) {
            if (i > 0) decks.append(',');
            RegisteredPlayer rp = game.getMatch().getPlayers().get(i);
            int mainCount = 0;
            int mountainCount = 0;
            for (Map.Entry<PaperCard,Integer> e : rp.getDeck().getMain()) {
                mainCount += e.getValue();
                if ("Mountain".equals(e.getKey().getName())) mountainCount += e.getValue();
            }
            List<PaperCard> commanders = rp.getCommanders();
            String commanderName = commanders.size() == 1 ? commanders.get(0).getName() : null;
            decks.append("{\"player_id\":\"P").append(i + 1).append("\",\"main_count\":").append(mainCount)
                .append(",\"mountain_count\":").append(mountainCount)
                .append(",\"commander_count\":").append(commanders.size())
                .append(",\"commander_name\":").append(Ws23ForgeVerticalProvider.esc(commanderName)).append('}');
        }
        decks.append(']');
        String raw = "{\"natural_registration\":true,\"player_count\":" + game.getPlayers().size()
            + ",\"decks\":" + decks + ",\"rules_commander\":" + game.getRules().hasAppliedVariant(forge.game.GameType.Commander) + "}";
        broker.out.println("{\"protocol\":" + Ws23ForgeVerticalProvider.esc(Ws23ForgeVerticalProvider.PROTOCOL)
            + ",\"message_type\":\"QUALIFICATION_STATE\",\"request_id\":\"ws40-natural-registration\",\"session_id\":"
            + Ws23ForgeVerticalProvider.esc(Ws23ForgeVerticalProvider.SESSION_ID)
            + ",\"payload\":{\"stage\":\"native_registration_validation\",\"raw_native\":" + raw + "}}");
        broker.out.flush();
        if ("1".equals(env("COMMANDER_LAB_WS40_CONSTRUCTION_ONLY"))) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_CONSTRUCTION_COMPLETE");
        }
    }

    private static String counterJson(Card c) {
        StringBuilder b = new StringBuilder("{");
        boolean first = true;
        List<Map.Entry<CounterType,Integer>> entries = new ArrayList<>();
        for (var e : c.getCounters().entrySet()) entries.add(Map.entry(e.getKey(), e.getValue()));
        entries.sort(Comparator.comparing(e -> e.getKey().toString()));
        for (var e : entries) {
            if (!first) b.append(',');
            first = false;
            b.append(Ws23ForgeVerticalProvider.esc(e.getKey().toString())).append(':').append(e.getValue());
        }
        return b.append('}').toString();
    }

    private static String semanticOf(Card c) {
        if (c == null) return null;
        for (Map.Entry<String,Card> e : semanticCards.entrySet()) if (e.getValue() == c) return e.getKey();
        return null;
    }

    private static String cardJson(Game game, ObjSpec s) {
        Card c = semanticCards.get(s.semanticId);
        if (c == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_OBSERVE_UNBOUND:" + s.semanticId);
        String cardName = c.getPaperCard() == null ? c.getName() : c.getPaperCard().getName();
        String attached = c.getEntityAttachedTo() instanceof Card ? semanticOf((Card)c.getEntityAttachedTo()) : null;
        Integer zonePosition = null;
        if (c.getZone() != null && c.getZone().is(ZoneType.Library)) {
            zonePosition = c.getZone().getPlayer().getCardsIn(ZoneType.Library, false).indexOf(c);
        }
        return "{\"semantic_id\":" + Ws23ForgeVerticalProvider.esc(s.semanticId)
            + ",\"card_identity\":" + Ws23ForgeVerticalProvider.esc(cardName)
            + ",\"owner\":" + Ws23ForgeVerticalProvider.esc(playerId(game, c.getOwner()))
            + ",\"controller\":" + Ws23ForgeVerticalProvider.esc(playerId(game, c.getController()))
            + ",\"zone\":" + Ws23ForgeVerticalProvider.esc(c.getZone() == null ? null : c.getZone().getZoneType().toString().toLowerCase())
            + ",\"tapped\":" + c.isTapped()
            + ",\"face_down\":" + c.isFaceDown()
            + ",\"counters\":" + counterJson(c)
            + ",\"attached_to\":" + Ws23ForgeVerticalProvider.esc(attached)
            + ",\"zone_position\":" + (zonePosition == null ? "null" : zonePosition)
            + ",\"sick\":" + c.isSick() + "}";
    }

    private static String playersJson(Game game) {
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < game.getPlayers().size(); i++) {
            if (i > 0) b.append(',');
            Player p = game.getPlayers().get(i);
            b.append("{\"player_id\":\"P").append(i + 1).append("\",\"life\":").append(p.getLife())
                .append(",\"lost\":").append(p.hasLost())
                .append(",\"in_game\":").append(p.isInGame())
                .append(",\"poison\":").append(p.getCounters(forge.game.card.CounterEnumType.POISON)).append('}');
        }
        return b.append(']').toString();
    }

    private static String commandersJson(Game game) {
        StringBuilder b = new StringBuilder("[");
        boolean first = true;
        for (Map.Entry<String,Card> e : commanderCards.entrySet()) {
            if (!first) b.append(','); first = false;
            Card c = e.getValue();
            b.append("{\"commander_id\":").append(Ws23ForgeVerticalProvider.esc(e.getKey()))
                .append(",\"name\":").append(Ws23ForgeVerticalProvider.esc(c.getPaperCard() == null ? c.getName() : c.getPaperCard().getName()))
                .append(",\"owner\":").append(Ws23ForgeVerticalProvider.esc(playerId(game,c.getOwner())))
                .append(",\"zone\":").append(Ws23ForgeVerticalProvider.esc(c.getZone() == null ? null : c.getZone().getZoneType().toString().toLowerCase()))
                .append(",\"cast_count\":").append(c.getOwner().getCommanderCast(c)).append('}');
        }
        return b.append(']').toString();
    }

    private static String commanderDamageJson(Game game) {
        StringBuilder b = new StringBuilder("[");
        boolean first = true;
        for (int i = 0; i < game.getPlayers().size(); i++) {
            Player damaged = game.getPlayers().get(i);
            for (Map.Entry<String,Card> e : commanderCards.entrySet()) {
                int amount = damaged.getCommanderDamage(e.getValue());
                if (amount <= 0) continue;
                if (!first) b.append(','); first = false;
                b.append("{\"source_commander_id\":").append(Ws23ForgeVerticalProvider.esc(e.getKey()))
                    .append(",\"damaged_player\":\"P").append(i + 1).append("\",\"combat_damage\":").append(amount).append('}');
            }
        }
        return b.append(']').toString();
    }

    private static String combatJson(Game game) {
        Combat combat = game.getCombat();
        if (combat == null) return "null";
        StringBuilder a = new StringBuilder("{");
        boolean first = true;
        for (Card c : combat.getAttackers()) {
            String sid = semanticOf(c); if (sid == null) continue;
            if (!first) a.append(','); first = false;
            GameEntity def = combat.getDefenderByAttacker(c);
            String dk = def instanceof Player ? playerId(game,(Player)def) : semanticOf((Card)def);
            a.append(Ws23ForgeVerticalProvider.esc(sid)).append(':').append(Ws23ForgeVerticalProvider.esc(dk));
        }
        a.append('}');
        StringBuilder bl = new StringBuilder("{"); first = true;
        for (Card blocker : combat.getAllBlockers()) {
            String bsid = semanticOf(blocker); if (bsid == null) continue;
            List<Card> blocked = combat.getAttackersBlockedBy(blocker);
            if (blocked.isEmpty()) continue;
            if (!first) bl.append(','); first = false;
            bl.append(Ws23ForgeVerticalProvider.esc(bsid)).append(':').append(Ws23ForgeVerticalProvider.esc(semanticOf(blocked.get(0))));
        }
        bl.append('}');
        return "{\"attackers\":" + a + ",\"blockers\":" + bl + "}";
    }

    private static String stackJson(Game game) {
        StringBuilder b = new StringBuilder("[");
        boolean first = true;
        for (Map.Entry<String,SpellAbility> e : stackAbilities.entrySet()) {
            SpellAbility sa = e.getValue();
            if (!first) b.append(','); first = false;
            b.append("{\"source_semantic_id\":").append(Ws23ForgeVerticalProvider.esc(e.getKey()))
                .append(",\"native_stack_present\":").append(game.getStack().getInstanceMatchingSpellAbilityID(sa) != null)
                .append(",\"controller\":").append(Ws23ForgeVerticalProvider.esc(playerId(game,sa.getActivatingPlayer())))
                .append('}');
        }
        return b.append(']').toString();
    }

    private static void emitNativeSnapshot(Game game, Ws23ForgeVerticalProvider.Broker broker, boolean natural) {
        StringBuilder cards = new StringBuilder("[");
        boolean first = true;
        for (ObjSpec s : objectSpecs) {
            if (!s.emitSemantic) continue;
            if (!first) cards.append(','); first = false;
            cards.append(cardJson(game, s));
        }
        cards.append(']');
        String phase = game.getPhaseHandler().getPhase() == null ? null : game.getPhaseHandler().getPhase().toString();
        String raw = "{\"natural_registration\":" + natural
            + ",\"player_count\":" + game.getPlayers().size()
            + ",\"players\":" + playersJson(game)
            + ",\"cards\":" + cards
            + ",\"commanders\":" + commandersJson(game)
            + ",\"commander_damage\":" + commanderDamageJson(game)
            + ",\"combat\":" + combatJson(game)
            + ",\"stack\":" + stackJson(game)
            + ",\"turn\":" + game.getPhaseHandler().getTurn()
            + ",\"phase\":" + Ws23ForgeVerticalProvider.esc(phase)
            + ",\"active_player\":" + Ws23ForgeVerticalProvider.esc(playerId(game, game.getPhaseHandler().getPlayerTurn()))
            + ",\"priority_player\":" + Ws23ForgeVerticalProvider.esc(playerId(game, game.getPhaseHandler().getPriorityPlayer()))
            + ",\"rules_commander\":" + game.getRules().hasAppliedVariant(forge.game.GameType.Commander)
            + ",\"config_binding_digest\":" + Ws23ForgeVerticalProvider.esc(env("COMMANDER_LAB_WS40_CONFIG_BINDING_DIGEST")) + "}";
        broker.out.println("{\"protocol\":" + Ws23ForgeVerticalProvider.esc(Ws23ForgeVerticalProvider.PROTOCOL)
            + ",\"message_type\":\"QUALIFICATION_STATE\",\"request_id\":\"ws40-native-state\",\"session_id\":"
            + Ws23ForgeVerticalProvider.esc(Ws23ForgeVerticalProvider.SESSION_ID)
            + ",\"payload\":{\"stage\":\"after_native_setup_validation\",\"raw_native\":" + raw + "}}");
        broker.out.flush();
    }
}
