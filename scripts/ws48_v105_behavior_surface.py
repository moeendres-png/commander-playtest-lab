#!/usr/bin/env python3
"""WS-48 v1.0.5 behavior execution surface (Muse support lane).

Applied to the generated provider AFTER the exact CI chain
(generate -> bootstrap -> successor overlay -> ... -> stack-modes patch).

Adds observation-only execution surface for G48-09 behavior; Forge Rules Core
keeps exclusive ownership of legality:

- semantic descriptors on offered decision options (priority/actions, objects,
  players, modes, mana). The offered SET and ORDER are unchanged.
- native GameEvent feed subscription emitting EVENT protocol messages.
- behavior snapshots (QUALIFICATION_STATE stage=behavior_checkpoint) after each
  submitted decision, with semantic refs where bound.
- externally-driven declareAttackers/declareBlockers: native enumeration via
  CombatUtil + external assignment selection + native re-validation.
- typed fail-closed gate for unsupported decision families
  (COMMANDER_LAB_WS48_UNSUPPORTED_FAMILY).

Fail-closed: unknown anchors, unbound semantic refs in descriptors are reported
as UNBOUND (never fabricated), any forge.ai/forge.gui import is forbidden.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"WS48_BEHAVIOR_SURFACE:{label}:expected 1 anchor, found {n}")
    return text.replace(old, new, 1)


PRIORITY_LABEL_OLD = """                for (Card c : actor.getCardsIn(zone)) {
                    for (SpellAbility sa : c.getAllPossibleAbilities(actor, true)) {
                        if (seen.add(sa)) {
                            nativeOptions.add(sa);
                            labels.add("FORGE_LEGAL_ACTION");
                        }
                    }
                }"""

PRIORITY_LABEL_NEW = """                for (Card c : actor.getCardsIn(zone)) {
                    for (SpellAbility sa : c.getAllPossibleAbilities(actor, true)) {
                        if (seen.add(sa)) {
                            nativeOptions.add(sa);
                            labels.add(ws48PriorityLabel(actor, sa));
                        }
                    }
                }"""

CHOOSE_OBJECT_OLD = """        <T> T chooseObject(String kind, Player actor, java.util.List<T> options, boolean optional) {
            if (!optional) {
                if (options.isEmpty()) throw new ControlledStop("FINALIST_ZERO_NATIVE_OPTIONS:" + kind);
                if (options.size() == 1) {
                    recordAutomatic("SINGLE_NATIVE_OPTION:" + kind);
                    return options.get(0);
                }
            }
            java.util.List<String> labels = new ArrayList<>();
            if (optional) labels.add("NONE");
            for (int i = 0; i < options.size(); i++) labels.add("NATIVE_OPTION");"""

CHOOSE_OBJECT_NEW = """        <T> T chooseObject(String kind, Player actor, java.util.List<T> options, boolean optional) {
            if (!optional) {
                if (options.isEmpty()) throw new ControlledStop("FINALIST_ZERO_NATIVE_OPTIONS:" + kind);
                if (options.size() == 1) {
                    recordAutomatic("SINGLE_NATIVE_OPTION:" + kind);
                    return options.get(0);
                }
            }
            java.util.List<String> labels = new ArrayList<>();
            if (optional) labels.add("NONE");
            for (int i = 0; i < options.size(); i++) labels.add(ws48OptionLabel(actor, options.get(i)));"""

BROKER_HELPERS = """        static String ws48Pid(Player p) {
            if (p == null || p.getGame() == null) return "null";
            int idx = p.getGame().getPlayers().indexOf(p);
            return idx < 0 ? "null" : "P" + (idx + 1);
        }

        static String ws48CardDescriptor(Player viewer, Card card) {
            String semantic = Ws40SuccessorState.semanticRefOf(card);
            String zone = card.getZone() == null ? "null" : card.getZone().getZoneType().toString().toLowerCase();
            String base = card.getName() + ":" + zone + ":" + ws48Pid(card.getController());
            return semantic == null ? "NATIVE_CARD:" + base : "SEMANTIC_CARD:" + semantic + ":" + base;
        }

        static String ws48PriorityLabel(Player actor, SpellAbility sa) {
            Card host = sa.getHostCard();
            String zone = host != null && host.getZone() != null
                    ? host.getZone().getZoneType().toString().toLowerCase() : "null";
            String semantic = host == null ? null : Ws40SuccessorState.semanticRefOf(host);
            String api = sa.getApi() == null ? "null" : sa.getApi().toString();
            String desc = "FORGE_LEGAL_ACTION:" + (host == null ? "null" : host.getName())
                    + ":" + zone + ":" + api + ":" + String.valueOf(semantic);
            return desc.replace("|", "/").replace(",", ";");
        }

        static String ws48OptionLabel(Player actor, Object option) {
            if (option instanceof Card card) return ws48CardDescriptor(actor, card);
            if (option instanceof Player p) return "PLAYER:" + ws48Pid(p);
            if (option instanceof forge.game.mana.Mana mana) return "MANA:" + mana.toString();
            if (option instanceof forge.game.spellability.AbilitySub sub) {
                String text = sub.getDescription() == null ? "null" : sub.getDescription();
                return "MODE:" + text.replace("|", "/").replace(",", ";");
            }
            if (option instanceof SpellAbility sa) {
                Card host = sa.getHostCard();
                return "ABILITY:" + (host == null ? "null" : host.getName());
            }
            return "NATIVE_OPTION:" + option.getClass().getSimpleName();
        }

        static String ws48UnsupportedFamily() {
            String raw = System.getenv("COMMANDER_LAB_WS48_UNSUPPORTED_FAMILY");
            return raw == null ? "" : raw.trim();
        }

        void emitEvent(String name) {
            if (!ws48BehaviorEnabled()) return;
            recordAutomatic("EVENT:" + name);
            out.println("{\\"protocol\\":" + esc(PROTOCOL)
                + ",\\"message_type\\":\\"EVENT\\""
                + ",\\"request_id\\":\\"ws48-behavior-event\\""
                + ",\\"session_id\\":" + esc(SESSION_ID)
                + ",\\"payload\\":{\\"name\\":" + esc(name) + "}}");
            out.flush();
        }

        void emitDecisionFrame(String kind, Player actor, int optionCount) {
            if (!ws48BehaviorEnabled()) return;
            emitEvent("decision_frame:" + kind + ":" + ws48Pid(actor) + ":" + optionCount);
        }

        static boolean ws48BehaviorEnabled() {
            return "1".equals(System.getenv("COMMANDER_LAB_WS48_BEHAVIOR"));
        }

"""

CHOOSE_GATE_OLD = """        String choose(String kind, Player actor, java.util.List<String> labels) {
            long seq = ++decisionSeq;"""

CHOOSE_GATE_NEW = """        String choose(String kind, Player actor, java.util.List<String> labels) {
            String unsupported = ws48UnsupportedFamily();
            if (!unsupported.isEmpty() && (kind.equals(unsupported) || kind.startsWith(unsupported + ":"))) {
                throw new ControlledStop("UNSUPPORTED_DISCRETIONARY_DECISION:" + kind);
            }
            long seq = ++decisionSeq;"""

FRAME_HOOK_OLD = """            out.flush();
            try {
                String answer = in.readLine();"""

FRAME_HOOK_NEW = """            out.flush();
            emitDecisionFrame(kind, actor, labels.size());
            try {
                String answer = in.readLine();"""

SNAPSHOT_HOOK_OLD = """                revision++;
                return choice;"""

SNAPSHOT_HOOK_NEW = """                revision++;
                if (ws48BehaviorEnabled()) {
                    try {
                        Ws40SuccessorState.emitBehaviorCheckpoint(actor.getGame(), this);
                    } catch (ControlledStop stop) {
                        throw stop;
                    } catch (RuntimeException emitFailure) {
                        throw new ControlledStop("WS48_BEHAVIOR_SNAPSHOT_FAILED:" + emitFailure.getMessage());
                    }
                }
                return choice;"""

SUBSCRIBE_OLD = "        Game game = match.createGame();"
SUBSCRIBE_NEW = """        Game game = match.createGame();
        game.subscribeToEvents(new Ws48BehaviorEvents(broker));"""

RESULT_EVENTS_OLD = """            + ",\\"priority_decisions\\":" + broker.priorityDecisions
"""
RESULT_EVENTS_NEW = """            + ",\\"priority_decisions\\":" + broker.priorityDecisions
            + ",\\"native_events\\":" + ws48JsonStringList(broker.automatic)
            + ",\\"automatic\\":" + ws48JsonStringList(broker.automatic)
"""

EVENTS_CLASS = """    static String ws48JsonStringList(java.util.List<String> values) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < values.size(); i++) {
            if (i > 0) sb.append(',');
            sb.append(esc(values.get(i)));
        }
        return sb.append(']').toString();
    }

    static String ws48EventRef(Broker broker, Card card) {
        String semantic = Ws40SuccessorState.semanticRefOf(card);
        return semantic == null ? "NATIVE:" + card.getName() : semantic;
    }

    static String ws48EventName(String raw) {
        // Contract event names use underscores (Giant_Growth); native card
        // names use spaces. Display normalization only, no semantic change.
        return raw == null ? "null" : raw.replace(" ", "_");
    }

    static String ws48ManaPaidString(forge.card.mana.ManaCost cost) {
        if (cost == null) return "0";
        return cost.toString().replace("{", "").replace("}", "").replace(" ", "");
    }

    static String ws48EventCardRef(int nativeId) {
        String semantic = Ws40SuccessorState.semanticRefOfId(nativeId);
        return semantic == null ? "NATIVE_CARD_VIEW:" + nativeId : semantic;
    }

    static String ws48EventPlayerRef(String nativeName) {
        if (nativeName != null && nativeName.startsWith("seat-")) {
            try {
                return "P" + Integer.parseInt(nativeName.substring(5));
            } catch (NumberFormatException badSeat) {
                return "UNKNOWN_DEFENDER:" + nativeName;
            }
        }
        return "UNKNOWN_DEFENDER:" + String.valueOf(nativeName);
    }

    static final class Ws48BehaviorEvents {
        final Broker broker;
        Ws48BehaviorEvents(Broker broker) { this.broker = broker; }

        void emit(String name) {
            broker.emitEvent(name);
        }

        @com.google.common.eventbus.Subscribe
        public void onSpellCast(forge.game.event.GameEventSpellAbilityCast event) {
            if (event.sa() == null || event.sa().getHostCard() == null) return;
            String name = ws48EventName(event.sa().getHostCard().getName());
            emit("spell_cast:" + name);
            emit("stack_push:" + name);
            emit(name + "_cast");
            String ref = ws48EventCardRef(event.sa().getHostCard().getId());
            if (!ref.startsWith("NATIVE_CARD_VIEW:")) {
                emit("spell_cast:" + ref);
                emit("stack_push:" + ref);
            }
            if (event.sa().getHostCard().isCommander()) {
                emit("commander_cast");
            }
        }

        @com.google.common.eventbus.Subscribe
        public void onSpellResolved(forge.game.event.GameEventSpellResolved event) {
            if (event.spell() == null || event.spell().getHostCard() == null) return;
            String name = ws48EventName(event.spell().getHostCard().getName());
            emit("resolve:" + name);
            emit("spell_resolved");
            String ref = ws48EventCardRef(event.spell().getHostCard().getId());
            if (!ref.startsWith("NATIVE_CARD_VIEW:")) {
                emit("resolve:" + ref);
            }
        }

        @com.google.common.eventbus.Subscribe
        public void onAttackersDeclared(forge.game.event.GameEventAttackersDeclared event) {
            for (java.util.Map.Entry<forge.game.GameEntityView, forge.game.card.CardView> entry
                    : event.attackersMap().entries()) {
                String attacker = ws48EventCardRef(entry.getValue().getId());
                String defender = "UNKNOWN_DEFENDER";
                if (entry.getKey() instanceof forge.game.player.PlayerView pv) {
                    defender = ws48EventPlayerRef(pv.getName());
                }
                emit("attacker_declared:" + attacker + "->" + defender);
            }
        }

        @com.google.common.eventbus.Subscribe
        public void onBlockersDeclared(forge.game.event.GameEventBlockersDeclared event) {
            // Map: defender => attacker => blockers (see PhaseHandler).
            for (java.util.Map.Entry<forge.game.GameEntityView,
                    com.google.common.collect.Multimap<forge.game.card.CardView, forge.game.card.CardView>> outer
                    : event.blockers().entrySet()) {
                for (java.util.Map.Entry<forge.game.card.CardView, forge.game.card.CardView> pair
                        : outer.getValue().entries()) {
                    String attacker = ws48EventCardRef(pair.getKey().getId());
                    String blocker = ws48EventCardRef(pair.getValue().getId());
                    emit("blocker_declared:" + blocker + "->" + attacker);
                }
            }
            emit("blockers_declared");
        }
    }

"""

DECLARE_ATTACKERS_PATTERN = re.compile(
    r"        @Override\n        public void declareAttackers\(.*?\) \{\n(?:.*\n)*?            throw failClosed\(\"declareAttackers.*?\);\n        \}",
)

DECLARE_BLOCKERS_PATTERN = re.compile(
    r"        @Override\n        public void declareBlockers\(.*?\) \{\n(?:.*\n)*?            throw failClosed\(\"declareBlockers.*?\);\n        \}",
)

DECLARE_ATTACKERS_NEW = """        @Override
        public void declareAttackers(Player attacker, Combat combat) {
            if (attacker != this.player) throw failClosed("declareAttackers:WRONG_ACTOR");
            java.util.List<Card> nativeAttackers =
                new ArrayList<>(forge.game.combat.CombatUtil.getPossibleAttackers(attacker));
            nativeAttackers.sort(java.util.Comparator.comparing(card -> {
                String semantic = Ws40SuccessorState.semanticRefOf(card);
                return semantic == null ? "~" + card.getId() : semantic;
            }));
            java.util.List<GameEntity> nativeDefenders = new ArrayList<>(
                forge.game.combat.CombatUtil.getAllPossibleDefenders(attacker));
            java.util.List<java.util.Map<Card, GameEntity>> legalAssignments = new ArrayList<>();
            java.util.List<String> labels = new ArrayList<>();
            int n = nativeAttackers.size();
            int m = nativeDefenders.size();
            if (n > 6 || m > 5) throw failClosed("declareAttackers:ASSIGNMENT_SPACE_UNSUPPORTED:" + n + ":" + m);
            int total = (int) Math.pow(m + 1, n);
            for (int code = 0; code < total; code++) {
                java.util.Map<Card, GameEntity> candidate = new java.util.LinkedHashMap<>();
                int rest = code;
                boolean primitiveLegal = true;
                for (int i = 0; i < n; i++) {
                    int choice = rest % (m + 1);
                    rest /= (m + 1);
                    if (choice == m) continue;
                    Card card = nativeAttackers.get(i);
                    GameEntity defender = nativeDefenders.get(choice);
                    if (!forge.game.combat.CombatUtil.canAttack(card, defender)) { primitiveLegal = false; break; }
                    if (forge.game.combat.CombatUtil.getAttackCost(getGame(), card, defender) != null) {
                        throw failClosed("declareAttackers:ATTACK_COST_UNSUPPORTED");
                    }
                    candidate.put(card, defender);
                }
                if (!primitiveLegal) continue;
                Combat trial = new Combat(attacker);
                for (java.util.Map.Entry<Card, GameEntity> entry : candidate.entrySet()) {
                    trial.addAttacker(entry.getKey(), entry.getValue());
                }
                if (!forge.game.combat.CombatUtil.validateAttackers(trial)) continue;
                legalAssignments.add(candidate);
                StringBuilder label = new StringBuilder("ATTACK_ASSIGNMENT:");
                for (int i = 0; i < n; i++) {
                    if (i > 0) label.append(',');
                    Card card = nativeAttackers.get(i);
                    String semantic = Ws40SuccessorState.semanticRefOf(card);
                    label.append(semantic == null ? "NATIVE:" + card.getId() : semantic).append('=');
                    GameEntity defender = candidate.get(card);
                    if (defender instanceof Player defenderPlayer) {
                        label.append(Broker.ws48Pid(defenderPlayer));
                    } else {
                        label.append(defender == null ? "NONE" : "NONPLAYER");
                    }
                }
                labels.add(label.toString());
            }
            if (legalAssignments.isEmpty()) throw failClosed("declareAttackers:NO_NATIVE_LEGAL_ASSIGNMENTS");
            String selectedId = broker.choose("declareAttackers", this.player, labels);
            int selectedIndex = Integer.parseInt(selectedId.substring(1));
            if (selectedIndex < 0 || selectedIndex >= legalAssignments.size()) {
                throw failClosed("declareAttackers:STALE_SELECTION");
            }
            java.util.Map<Card, GameEntity> selected = legalAssignments.get(selectedIndex);
            combat.clearAttackers();
            for (java.util.Map.Entry<Card, GameEntity> entry : selected.entrySet()) {
                combat.addAttacker(entry.getKey(), entry.getValue());
            }
            if (!forge.game.combat.CombatUtil.validateAttackers(combat)) {
                throw failClosed("declareAttackers:SELECTED_ASSIGNMENT_REJECTED_BY_NATIVE_VALIDATOR");
            }
            broker.recordAutomatic("WS48_SELECTED_ATTACK_ASSIGNMENT:" + labels.get(selectedIndex));
        }"""

DECLARE_BLOCKERS_NEW = """        @Override
        public void declareBlockers(Player defender, Combat combat) {
            if (defender != this.player) throw failClosed("declareBlockers:WRONG_ACTOR");
            java.util.List<Card> nativeBlockers = new ArrayList<>(defender.getCreaturesInPlay());
            java.util.List<Card> attackers = new ArrayList<>(combat.getAttackers());
            java.util.List<java.util.Map<Card, Card>> legalAssignments = new ArrayList<>();
            java.util.List<String> labels = new ArrayList<>();
            int n = nativeBlockers.size();
            if (n > 6 || attackers.size() > 6) {
                throw failClosed("declareBlockers:ASSIGNMENT_SPACE_UNSUPPORTED");
            }
            int total = (int) Math.pow(attackers.size() + 1, n);
            for (int code = 0; code < total; code++) {
                java.util.Map<Card, Card> candidate = new java.util.LinkedHashMap<>();
                int rest = code;
                boolean primitiveLegal = true;
                for (int i = 0; i < n; i++) {
                    int choice = rest % (attackers.size() + 1);
                    rest /= (attackers.size() + 1);
                    if (choice == attackers.size()) continue;
                    Card blocker = nativeBlockers.get(i);
                    Card attacker = attackers.get(choice);
                    if (!forge.game.combat.CombatUtil.canBlock(attacker, blocker, combat)) {
                        primitiveLegal = false; break;
                    }
                    candidate.put(blocker, attacker);
                }
                if (!primitiveLegal) continue;
                legalAssignments.add(candidate);
                StringBuilder label = new StringBuilder("BLOCK_ASSIGNMENT:");
                for (int i = 0; i < n; i++) {
                    if (i > 0) label.append(',');
                    Card blocker = nativeBlockers.get(i);
                    String semantic = Ws40SuccessorState.semanticRefOf(blocker);
                    label.append(semantic == null ? "NATIVE:" + blocker.getId() : semantic).append('=');
                    Card attacker = candidate.get(blocker);
                    if (attacker == null) {
                        label.append("NONE");
                    } else {
                        String asym = Ws40SuccessorState.semanticRefOf(attacker);
                        label.append(asym == null ? "NATIVE:" + attacker.getId() : asym);
                    }
                }
                labels.add(label.toString());
            }
            if (legalAssignments.isEmpty()) throw failClosed("declareBlockers:NO_NATIVE_LEGAL_ASSIGNMENTS");
            String selectedId = broker.choose("declareBlockers", this.player, labels);
            int selectedIndex = Integer.parseInt(selectedId.substring(1));
            if (selectedIndex < 0 || selectedIndex >= legalAssignments.size()) {
                throw failClosed("declareBlockers:STALE_SELECTION");
            }
            java.util.Map<Card, Card> selected = legalAssignments.get(selectedIndex);
            for (java.util.Map.Entry<Card, Card> entry : selected.entrySet()) {
                combat.addBlocker(entry.getValue(), entry.getKey());
                combat.setBlocked(entry.getValue(), true);
            }
            broker.recordAutomatic("WS48_SELECTED_BLOCK_ASSIGNMENT:" + labels.get(selectedIndex));
        }"""

STATE_HELPERS_OLD = """    private static String semanticOf(Card c) {
        if (c == null) return null;
        for (Map.Entry<String,Card> e : semanticCards.entrySet()) if (e.getValue() == c) return e.getKey();
        return null;
    }
"""

STATE_HELPERS_NEW = """    private static String semanticOf(Card c) {
        if (c == null) return null;
        for (Map.Entry<String,Card> e : semanticCards.entrySet()) if (e.getValue() == c) return e.getKey();
        return null;
    }

    public static String semanticRefOf(Card c) {
        return semanticOf(c);
    }

    public static String semanticRefOfId(int nativeId) {
        for (Map.Entry<String,Card> e : semanticCards.entrySet()) {
            if (e.getValue() != null && e.getValue().getId() == nativeId) return e.getKey();
        }
        return null;
    }

    public static void emitBehaviorCheckpoint(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        StringBuilder cards = new StringBuilder("[");
        boolean first = true;
        java.util.List<Player> players = game.getPlayers();
        for (int pi = 0; pi < players.size(); pi++) {
            Player p = players.get(pi);
            String pid = "P" + (pi + 1);
            for (ZoneType zone : new ZoneType[] {
                    ZoneType.Battlefield, ZoneType.Hand, ZoneType.Graveyard,
                    ZoneType.Exile, ZoneType.Library, ZoneType.Command, ZoneType.Stack }) {
                for (Card c : p.getCardsIn(zone, false)) {
                    if (!first) cards.append(',');
                    first = false;
                    String cardName = c.getPaperCard() == null ? c.getName() : c.getPaperCard().getName();
                    cards.append("{\\"semantic_id\\":")
                        .append(Ws23ForgeVerticalProvider.esc(semanticOf(c)))
                        .append(",\\"card_identity\\":")
                        .append(Ws23ForgeVerticalProvider.esc(cardName))
                        .append(",\\"owner\\":").append(Ws23ForgeVerticalProvider.esc(pid))
                        .append(",\\"controller\\":")
                        .append(Ws23ForgeVerticalProvider.esc(controllerPid(game, c.getController())))
                        .append(",\\"zone\\":")
                        .append(Ws23ForgeVerticalProvider.esc(zone.toString().toLowerCase()))
                        .append(",\\"tapped\\":").append(c.isTapped())
                        .append(",\\"face_down\\":").append(c.isFaceDown())
                        .append(",\\"power\\":").append(c.getNetPower())
                        .append(",\\"toughness\\":").append(c.getNetToughness())
                        .append(",\\"damage\\":").append(c.getDamage())
                        .append('}');
                }
            }
        }
        cards.append(']');
        StringBuilder stack = new StringBuilder("[");
        boolean sfirst = true;
        for (forge.game.spellability.SpellAbilityStackInstance si : game.getStack()) {
            if (!sfirst) stack.append(',');
            sfirst = false;
            SpellAbility sa = si.getSpellAbility();
            Card host = sa.getHostCard();
            stack.append("{\\"source\\":")
                .append(Ws23ForgeVerticalProvider.esc(host == null ? null : host.getName()))
                .append(",\\"source_semantic_id\\":")
                .append(Ws23ForgeVerticalProvider.esc(host == null ? null : semanticOf(host)))
                .append(",\\"controller\\":")
                .append(Ws23ForgeVerticalProvider.esc(
                    sa.getActivatingPlayer() == null ? null
                        : controllerPid(game, sa.getActivatingPlayer())))
                .append('}');
        }
        stack.append(']');
        String phase = game.getPhaseHandler().getPhase() == null ? null
            : game.getPhaseHandler().getPhase().toString();
        StringBuilder life = new StringBuilder("[");
        for (int pi = 0; pi < players.size(); pi++) {
            if (pi > 0) life.append(',');
            Player p = players.get(pi);
            life.append("{\\"player_id\\":\\"P").append(pi + 1)
                .append("\\",\\"life\\":").append(p.getLife())
                .append(",\\"in_game\\":").append(p.isInGame())
                .append(",\\"lost\\":").append(p.hasLost())
                .append(",\\"hand_count\\":").append(p.getCardsIn(ZoneType.Hand).size())
                .append(",\\"library_count\\":").append(p.getCardsIn(ZoneType.Library).size())
                .append('}');
        }
        life.append(']');
        String raw = "{\\"behavior_checkpoint\\":true"
            + ",\\"player_count\\":" + players.size()
            + ",\\"cards\\":" + cards
            + ",\\"stack\\":" + stack
            + ",\\"players\\":" + life
            + ",\\"turn\\":" + game.getPhaseHandler().getTurn()
            + ",\\"phase\\":" + Ws23ForgeVerticalProvider.esc(phase)
            + ",\\"active_player\\":" + Ws23ForgeVerticalProvider.esc(
                controllerPid(game, game.getPhaseHandler().getPlayerTurn()))
            + ",\\"priority_player\\":" + Ws23ForgeVerticalProvider.esc(
                controllerPid(game, game.getPhaseHandler().getPriorityPlayer())) + "}";
        broker.out.println("{\\"protocol\\":" + Ws23ForgeVerticalProvider.esc(Ws23ForgeVerticalProvider.PROTOCOL)
            + ",\\"message_type\\":\\"QUALIFICATION_STATE\\",\\"request_id\\":\\"ws48-behavior-checkpoint\\",\\"session_id\\":"
            + Ws23ForgeVerticalProvider.esc(Ws23ForgeVerticalProvider.SESSION_ID)
            + ",\\"payload\\":{\\"stage\\":\\"behavior_checkpoint\\",\\"raw_native\\":" + raw + "}}");
        broker.out.flush();
    }

    private static String controllerPid(Game game, Player p) {
        if (p == null || game == null) return null;
        int idx = game.getPlayers().indexOf(p);
        return idx < 0 ? null : "P" + (idx + 1);
    }
"""


CHOOSE_TARGETS_PATTERN = re.compile(
    r"(        @Override\n)        public boolean chooseTargetsFor\(SpellAbility currentAbility\) \{\n            throw failClosed\(\"chooseTargetsFor\"\);\n        \}",
)

CHOOSE_TARGETS_NEW = """\\1        public boolean chooseTargetsFor(SpellAbility currentAbility) {
            if (currentAbility.getTargetRestrictions() == null) {
                throw failClosed("chooseTargetsFor:NO_RESTRICTIONS");
            }
            Card host = currentAbility.getHostCard();
            int min = currentAbility.getTargetRestrictions().getMinTargets(host, currentAbility);
            int max = currentAbility.getTargetRestrictions().getMaxTargets(host, currentAbility);
            if (max <= 0) return currentAbility.getTargets().size() >= min;
            java.util.List<ZoneType> zones = currentAbility.getTargetRestrictions().getZone();
            if (zones == null || zones.isEmpty()) zones = java.util.List.of(ZoneType.Battlefield);
            for (int pick = currentAbility.getTargets().size(); pick < max; pick++) {
                java.util.List<GameObject> legal = new ArrayList<>();
                for (Player candidate : getGame().getPlayers()) {
                    if (currentAbility.canTarget(candidate)) legal.add(candidate);
                }
                for (ZoneType zone : zones) {
                    for (Player candidate : getGame().getPlayers()) {
                        for (Card card : candidate.getCardsIn(zone)) {
                            if (currentAbility.canTarget(card)) legal.add(card);
                        }
                    }
                }
                if (legal.isEmpty()) {
                    return currentAbility.getTargets().size() >= min;
                }
                java.util.List<String> labels = new ArrayList<>();
                for (GameObject candidate : legal) {
                    labels.add(broker.ws48OptionLabel(this.player, candidate));
                }
                String selectedId = broker.choose("chooseTargetsFor", this.player, labels);
                int selectedIndex = Integer.parseInt(selectedId.substring(1));
                if (selectedIndex < 0 || selectedIndex >= legal.size()) {
                    throw failClosed("chooseTargetsFor:STALE_SELECTION");
                }
                currentAbility.getTargets().add(legal.get(selectedIndex));
            }
            return currentAbility.getTargets().size() >= min;
        }"""

COST_PATTERN = re.compile(
    r"(        @Override\n)        public CostDecisionMakerBase getCostDecisionMaker\(Player player, SpellAbility ability, boolean effect, String prompt\) \{\n            throw failClosed\(\"getCostDecisionMaker\"\);\n        \}",
)

COST_NEW = """\\1        public CostDecisionMakerBase getCostDecisionMaker(
                Player player, SpellAbility ability, boolean effect, String prompt) {
            return new Ws48CostDecisionMaker(
                player, effect, ability, ability == null ? null : ability.getHostCard());
        }"""

PAY_MANA_PATTERN = re.compile(
    r"(        @Override\n)        public boolean payManaCost\(ManaCost toPay, CostPartMana costPartMana, SpellAbility sa, String prompt, ManaConversionMatrix matrix, boolean effect\) \{\n            throw failClosed\(\"payManaCost\"\);\n        \}",
)

PAY_MANA_NEW = """\\1        public boolean payManaCost(
                ManaCost toPay, CostPartMana costPartMana, SpellAbility sa,
                String prompt, ManaConversionMatrix matrix, boolean effect) {
            // Neutral headless mana payment. Enumeration is native (canPlay);
            // every source activation is externally authorized from the offered
            // set via broker.choose. No AI evaluation, no GUI, no first-option.
            Player payer = this.player;
            forge.game.mana.ManaCostBeingPaid cost = new forge.game.mana.ManaCostBeingPaid(toPay);
            forge.game.mana.ManaPool manapool = payer.getManaPool();
            Ws48CostDecisionMaker activationDecisions =
                new Ws48CostDecisionMaker(payer, effect, sa, sa == null ? null : sa.getHostCard());
            for (int guard = 0; guard < 32; guard++) {
                if (cost.isPaid()) {
                    broker.emitEvent("mana_paid:" + ws48ManaPaidString(toPay));
                    return true;
                }
                java.util.List<SpellAbility> options = new ArrayList<>();
                for (Card source : payer.getCardsIn(ZoneType.Battlefield)) {
                    for (SpellAbility ma : source.getManaAbilities()) {
                        ma.setActivatingPlayer(payer);
                        if (ma.canPlay()) options.add(ma);
                    }
                }
                if (options.isEmpty()) return false;
                options.sort(java.util.Comparator.comparing(option ->
                    String.valueOf(Ws40SuccessorState.semanticRefOf(option.getHostCard()))));
                java.util.List<String> labels = new ArrayList<>();
                for (SpellAbility option : options) {
                    String semantic = Ws40SuccessorState.semanticRefOf(option.getHostCard());
                    String produced = option.getParamOrDefault("Produced", "?");
                    labels.add("MANA_SOURCE:" + String.valueOf(semantic) + ":" + produced);
                }
                String selectedId = broker.choose("payMana", payer, labels);
                int selectedIndex = Integer.parseInt(selectedId.substring(1));
                if (selectedIndex < 0 || selectedIndex >= options.size()) {
                    throw failClosed("payManaCost:STALE_SELECTION");
                }
                SpellAbility picked = options.get(selectedIndex);
                forge.game.cost.CostPayment activation =
                    new forge.game.cost.CostPayment(picked.getPayCosts(), picked);
                if (!activation.payCost(activationDecisions)) {
                    throw failClosed("payManaCost:ACTIVATION_UNPAYABLE");
                }
                payer.getGame().getStack().addAndUnfreeze(picked);
                manapool.payManaFromAbility(sa, cost, picked);
                broker.recordAutomatic("NATIVE_MANA_ACTIVATED:" + labels.get(selectedIndex));
            }
            throw failClosed("payManaCost:SELECTION_BUDGET_EXHAUSTED");
        }"""

ORDER_COSTS_PATTERN = re.compile(
    r"(        @Override\n)        public List<CostPart> orderCosts\(List<CostPart> costs\) \{\n            throw failClosed\(\"orderCosts\"\);\n        \}",
)

ORDER_COSTS_NEW = """\\1        public List<CostPart> orderCosts(List<CostPart> costs) {
            if (costs == null || costs.size() <= 1) return costs;
            if (costs.size() > 4) throw failClosed("orderCosts:PERMUTATION_SPACE_UNSUPPORTED");
            java.util.List<java.util.List<CostPart>> permutations = new ArrayList<>();
            java.util.List<String> labels = new ArrayList<>();
            ws48PermuteCosts(new ArrayList<>(costs), 0, permutations, labels);
            String selectedId = broker.choose("orderCosts", this.player, labels);
            int selectedIndex = Integer.parseInt(selectedId.substring(1));
            if (selectedIndex < 0 || selectedIndex >= permutations.size()) {
                throw failClosed("orderCosts:STALE_SELECTION");
            }
            return permutations.get(selectedIndex);
        }"""

COST_HELPERS = """    static void ws48PermuteCosts(
            java.util.List<CostPart> parts, int from,
            java.util.List<java.util.List<CostPart>> out, java.util.List<String> labels) {
        if (from == parts.size()) {
            out.add(new ArrayList<>(parts));
            StringBuilder label = new StringBuilder("COST_ORDER:");
            for (int i = 0; i < parts.size(); i++) {
                if (i > 0) label.append(',');
                label.append(parts.get(i).getClass().getSimpleName());
            }
            labels.add(label.toString());
            return;
        }
        for (int i = from; i < parts.size(); i++) {
            java.util.Collections.swap(parts, from, i);
            ws48PermuteCosts(parts, from + 1, out, labels);
            java.util.Collections.swap(parts, from, i);
        }
    }

    static final class Ws48CostDecisionMaker extends CostDecisionMakerBase {
        Ws48CostDecisionMaker(Player player, boolean effect, SpellAbility ability, Card source) {
            super(player, effect, ability, source);
        }

        @Override
        public boolean paysRightAfterDecision() {
            return false;
        }

__WS48_COST_VISITS__
    }

"""


def cost_visit_methods(forge_src: Path) -> str:
    """Render Ws48CostDecisionMaker visit overrides from the pinned ICostVisitor.

    Only CostPartMana and CostTap carry structural no-op decisions (the real
    payment happens in part.payAsDecided through externalized controller
    callbacks). Every other cost part fails closed with a typed code so new
    discretionary cost paths stay visible instead of silently AI/GUI-resolved.
    """
    visitor = forge_src / "forge-game/src/main/java/forge/game/cost/ICostVisitor.java"
    text = visitor.read_text(encoding="utf-8")
    names = re.findall(r"[A-Za-z0-9_<>, ?]+\s+visit\(([A-Za-z0-9_]+)\s+\w+\)\s*;", text)
    if not names:
        raise SystemExit("WS48_BEHAVIOR_SURFACE:no ICostVisitor visit methods found")
    if "CostPartMana" not in names:
        raise SystemExit("WS48_BEHAVIOR_SURFACE:ICostVisitor lacks CostPartMana")
    blocks = []
    for name in names:
        if name in {"CostPartMana", "CostTap"}:
            body = "return PaymentDecision.number(0);"
        else:
            body = (
                "throw new Ws23ForgeVerticalProvider.ControlledStop("
                f'"WS48_COST_PART_UNSUPPORTED:{name}");'
            )
        blocks.append(
            "        @Override\n"
            f"        public PaymentDecision visit({name} cost) {{\n"
            f"            {body}\n"
            "        }"
        )
    return "\n\n".join(blocks)


GET_ABILITY_PATTERN = re.compile(
    r"(        @Override\n)        public SpellAbility getAbilityToPlay\(.*?\) \{\n            throw failClosed\(\"getAbilityToPlay\"\);\n        \}",
)

GET_ABILITY_NEW = """\\1        public SpellAbility getAbilityToPlay(
                Card hostCard, java.util.List<SpellAbility> abilities, ITriggerEvent triggerEvent) {
            if (abilities == null || abilities.isEmpty()) {
                throw failClosed("getAbilityToPlay:EMPTY");
            }
            if (abilities.size() == 1) {
                broker.recordAutomatic("SINGLE_NATIVE_SPELL_VARIANT");
                return abilities.get(0);
            }
            java.util.List<String> labels = new ArrayList<>();
            for (SpellAbility option : abilities) {
                String text = option.getDescription() == null ? "null" : option.getDescription();
                labels.add("SPELL_VARIANT:" + option.getHostCard().getName() + ":"
                    + text.replace("|", "/").replace(",", ";"));
            }
            String selectedId = broker.choose("getAbilityToPlay", this.player, labels);
            int selectedIndex = Integer.parseInt(selectedId.substring(1));
            if (selectedIndex < 0 || selectedIndex >= abilities.size()) {
                throw failClosed("getAbilityToPlay:STALE_SELECTION");
            }
            return abilities.get(selectedIndex);
        }"""


def patch_provider(path: Path, forge_src: Path) -> None:
    java = path.read_text(encoding="utf-8")
    java = replace_once(java, PRIORITY_LABEL_OLD, PRIORITY_LABEL_NEW, "priority labels")
    java = replace_once(java, CHOOSE_OBJECT_OLD, CHOOSE_OBJECT_NEW, "chooseObject labels")
    anchor = "        String choose(String kind, Player actor, java.util.List<String> labels) {"
    java = replace_once(java, anchor, BROKER_HELPERS + anchor, "broker semantic helpers")
    java = replace_once(java, CHOOSE_GATE_OLD, CHOOSE_GATE_NEW, "unsupported family gate")
    java = replace_once(java, FRAME_HOOK_OLD, FRAME_HOOK_NEW, "decision frame event")
    java = replace_once(java, SNAPSHOT_HOOK_OLD, SNAPSHOT_HOOK_NEW, "checkpoint hook")
    java = replace_once(java, SUBSCRIBE_OLD, SUBSCRIBE_NEW, "event subscription")
    java = replace_once(java, RESULT_EVENTS_OLD, RESULT_EVENTS_NEW, "result events")
    anchor2 = "    static String sessionSnapshot(Game game) {"
    helpers = COST_HELPERS.replace("__WS48_COST_VISITS__", cost_visit_methods(forge_src))
    java = replace_once(java, anchor2, helpers + "\n" + anchor2, "cost helpers")
    java = replace_once(java, anchor2, EVENTS_CLASS + "\n" + anchor2, "events class")
    new_java, n = DECLARE_ATTACKERS_PATTERN.subn(DECLARE_ATTACKERS_NEW, java, count=1)
    if n != 1:
        raise SystemExit(
            "WS48_BEHAVIOR_SURFACE:declareAttackers:expected 1 anchor, found " + str(n)
        )
    java = new_java
    new_java, n = DECLARE_BLOCKERS_PATTERN.subn(DECLARE_BLOCKERS_NEW, java, count=1)
    if n != 1:
        raise SystemExit("WS48_BEHAVIOR_SURFACE:declareBlockers:expected 1 anchor, found " + str(n))
    java = new_java
    new_java, n = GET_ABILITY_PATTERN.subn(GET_ABILITY_NEW, java, count=1)
    if n != 1:
        raise SystemExit(
            "WS48_BEHAVIOR_SURFACE:getAbilityToPlay:expected 1 anchor, found " + str(n)
        )
    java = new_java
    new_java, n = CHOOSE_TARGETS_PATTERN.subn(CHOOSE_TARGETS_NEW, java, count=1)
    if n != 1:
        raise SystemExit(
            "WS48_BEHAVIOR_SURFACE:chooseTargetsFor:expected 1 anchor, found " + str(n)
        )
    java = new_java
    for pattern, replacement, label in (
        (COST_PATTERN, COST_NEW, "getCostDecisionMaker"),
        (PAY_MANA_PATTERN, PAY_MANA_NEW, "payManaCost"),
        (ORDER_COSTS_PATTERN, ORDER_COSTS_NEW, "orderCosts"),
    ):
        new_java, n = pattern.subn(replacement, java, count=1)
        if n != 1:
            raise SystemExit(f"WS48_BEHAVIOR_SURFACE:{label}:expected 1 anchor, found {n}")
        java = new_java
    if "import forge.ai" in java or "import forge.gui" in java:
        raise SystemExit("WS48_BEHAVIOR_SURFACE:forbidden engine import present")
    path.write_text(java, encoding="utf-8")


def patch_state(path: Path) -> None:
    java = path.read_text(encoding="utf-8")
    java = replace_once(java, STATE_HELPERS_OLD, STATE_HELPERS_NEW, "state semantic helpers")
    path.write_text(java, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, required=True)
    ap.add_argument("--state-java", type=Path, required=True)
    ap.add_argument("--forge-src", type=Path, required=True)
    a = ap.parse_args()
    patch_provider(a.provider, a.forge_src)
    patch_state(a.state_java)
    print("WS48_V105_BEHAVIOR_SURFACE=PASS")
    return 0


if __name__ == "__main__":
    main()
