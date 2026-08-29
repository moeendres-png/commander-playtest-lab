#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ws19_generate_forge_probe import abstract_methods

NONDISCRETIONARY_VOID = {
    "reveal",
    "notifyOfValue",
    "revealAnte",
    "revealAISkipCards",
    "revealUnsupported",
    "autoPassCancel",
    "awaitNextInput",
    "cancelAwaitNextInput",
}


def method_body(name: str, signature: str) -> list[str]:
    if name in NONDISCRETIONARY_VOID:
        return [f'        broker.recordAutomatic("{name}");', "        return;"]
    if name == "chooseStartingPlayer":
        return [
            '        return broker.choosePlayer("chooseStartingPlayer", player, getGame().getPlayers());'
        ]
    if name == "mulliganKeepHand":
        return [
            '        return broker.chooseBoolean("mulliganKeepHand", player, "KEEP", "MULLIGAN");'
        ]
    if name == "chooseSaToActivateFromOpeningHand":
        return [
            "        if (usableFromOpeningHand == null || usableFromOpeningHand.isEmpty()) {",
            '            broker.recordAutomatic("chooseSaToActivateFromOpeningHand:EMPTY");',
            "            return java.util.List.of();",
            "        }",
            '        throw failClosed("chooseSaToActivateFromOpeningHand");',
        ]
    if name == "chooseSpellAbilityToPlay":
        return ["        return broker.choosePriority(player, getGame());"]
    if name == "playChosenSpellAbility":
        return ["        return PlaySpellAbility.playSpellAbility(this, player, sa);"]
    if name == "confirmAction":
        return [
            '        return broker.chooseBoolean("confirmAction", player, "YES", "NO");'
        ]
    if name == "chooseBinary":
        return [
            '        return broker.chooseBoolean("chooseBinary", player, "TRUE", "FALSE");'
        ]
    if name == "confirmPayment":
        return [
            '        return broker.chooseBoolean("confirmPayment", player, "PAY", "DECLINE");'
        ]
    if name == "chooseManaFromPool":
        return [
            '        return broker.chooseObject("chooseManaFromPool", player, manaChoices, false);'
        ]
    if name == "chooseModeForAbility":
        return [
            "        if (possible == null || possible.isEmpty()) throw failClosed(\"chooseModeForAbility:EMPTY\");",
            "        if (min == 1 && num == 1 && !allowRepeat) {",
            '            AbilitySub chosen = broker.chooseObject("chooseModeForAbility", player, possible, false);',
            "            return java.util.List.of(chosen);",
            "        }",
            '        throw failClosed("chooseModeForAbility:DEPENDENT_MULTI_CHOICE");',
        ]
    if name == "chooseSingleReplacementEffect":
        return [
            '        return broker.chooseObject("chooseSingleReplacementEffect", player, possibleReplacers, false);'
        ]
    if name == "chooseSingleStaticAbility":
        return [
            '        return broker.chooseObject("chooseSingleStaticAbility", player, possibleReplacers, false);'
        ]
    if name == "orderSimultaneousSa":
        return [
            "        if (activePlayerSAs == null || activePlayerSAs.size() <= 1) {",
            '            broker.recordAutomatic("orderSimultaneousSa:ZERO_OR_ONE");',
            "            return activePlayerSAs;",
            "        }",
            '        throw failClosed("orderSimultaneousSa:MULTI_ORDER");',
        ]
    if name == "orderAndPlaySimultaneousSa":
        return [
            "        if (activePlayerSAs == null || activePlayerSAs.isEmpty()) {",
            '            broker.recordAutomatic("orderAndPlaySimultaneousSa:EMPTY");',
            "            return;",
            "        }",
            '        throw failClosed("orderAndPlaySimultaneousSa");',
        ]
    if name == "chooseStartingHand":
        return [
            '        return broker.chooseObject("chooseStartingHand", player, zones, false);'
        ]
    return [f'        throw failClosed("{name}");']


def render(source: str, forge_commit: str, forge_tree: str) -> tuple[str, dict]:
    methods = abstract_methods(source)
    package = re.search(r"(?m)^package\s+([^;]+);", source)
    if not package:
        raise ValueError("missing package")
    imports = re.findall(r"(?m)^import\s+[^;]+;", source)
    classifications = []
    implemented = {
        "chooseStartingPlayer",
        "mulliganKeepHand",
        "chooseSpellAbilityToPlay",
        "playChosenSpellAbility",
        "confirmAction",
        "chooseBinary",
        "confirmPayment",
        "chooseManaFromPool",
        "chooseModeForAbility",
        "chooseSingleReplacementEffect",
        "chooseSingleStaticAbility",
        "chooseStartingHand",
    }
    automatic = NONDISCRETIONARY_VOID | {
        "chooseSaToActivateFromOpeningHand",
        "orderSimultaneousSa",
        "orderAndPlaySimultaneousSa",
    }
    for item in methods:
        name = item["name"]
        if name in implemented:
            cls = "EXTERNALLY_IMPLEMENTED"
        elif name in automatic:
            cls = "RULES_AUTOMATIC_NONDISCRETIONARY"
        else:
            cls = "FAIL_CLOSED_UNSUPPORTED"
        classifications.append({**item, "classification": cls})

    lines = [
        "// SPDX-License-Identifier: GPL-3.0-or-later",
        "// Generated WS-23 GPL-side qualification provider. Never import this class into the proprietary process.",
        f"package {package.group(1)};",
        "",
        *imports,
        "import forge.game.GameType;",
        "import forge.game.Match;",
        "import forge.game.player.RegisteredPlayer;",
        "import forge.game.player.IGameEntitiesFactory;",
        "import forge.deck.Deck;",
        "import forge.item.PaperCard;",
        "import java.io.*;",
        "import java.nio.charset.StandardCharsets;",
        "import java.security.MessageDigest;",
        "import java.util.ArrayList;",
        "import java.util.IdentityHashMap;",
        "import java.util.LinkedHashMap;",
        "import java.util.LinkedHashSet;",
        "import java.util.Locale;",
        "import java.util.regex.Matcher;",
        "import java.util.regex.Pattern;",
        "",
        "public final class Ws23ForgeVerticalProvider {",
        '    static final String PROTOCOL = "commander-lab.rules-service/1.1.0";',
        f'    static final String FORGE_COMMIT = "{forge_commit}";',
        f'    static final String FORGE_TREE = "{forge_tree}";',
        '    static final String SESSION_ID = "ws23-forge-session-1";',
        "",
        "    static String esc(String s) {",
        '        if (s == null) return "null";',
        '        return "\\\"" + s.replace("\\\\", "\\\\\\\\").replace("\\\"", "\\\\\\\"").replace("\\n", "\\\\n") + "\\\"";',
        "    }",
        "",
        "    static String field(String line, String key) {",
        '        Pattern p = Pattern.compile("\\\"" + Pattern.quote(key) + "\\\"\\\\s*:\\s*\\\"((?:\\\\\\\\.|[^\\\"\\\\\\\\])*)\\\"");',
        "        Matcher m = p.matcher(line);",
        "        if (!m.find()) return null;",
        '        return m.group(1).replace("\\\\\\\"", "\\\"").replace("\\\\n", "\\n").replace("\\\\\\\\", "\\\\");',
        "    }",
        "",
        "    static final class ControlledStop extends RuntimeException {",
        "        ControlledStop(String message) { super(message); }",
        "    }",
        "",
        "    static final class Broker {",
        "        final BufferedReader in;",
        "        final PrintWriter out;",
        "        long revision = 0;",
        "        long decisionSeq = 0;",
        "        long priorityDecisions = 0;",
        "        final int stopAfterPriorityDecisions;",
        "        final java.util.List<String> automatic = new ArrayList<>();",
        "",
        "        Broker(BufferedReader in, PrintWriter out, int stopAfterPriorityDecisions) {",
        "            this.in = in; this.out = out; this.stopAfterPriorityDecisions = stopAfterPriorityDecisions;",
        "        }",
        "",
        "        void recordAutomatic(String name) { automatic.add(name); }",
        "",
        "        String digest(java.util.List<String> ids) {",
        "            try {",
        '                MessageDigest md = MessageDigest.getInstance("SHA-256");',
        '                byte[] raw = md.digest(String.join("\\n", ids).getBytes(StandardCharsets.UTF_8));',
        "                StringBuilder sb = new StringBuilder();",
        '                for (byte b : raw) sb.append(String.format(Locale.ROOT, "%02x", b));',
        "                return sb.toString();",
        "            } catch (Exception e) { throw new RuntimeException(e); }",
        "        }",
        "",
        "        String choose(String kind, Player actor, java.util.List<String> labels) {",
        "            long seq = ++decisionSeq;",
        '            String did = "d" + seq;',
        "            java.util.List<String> ids = new ArrayList<>();",
        "            StringBuilder opts = new StringBuilder();",
        "            for (int i = 0; i < labels.size(); i++) {",
        '                String id = "o" + i; ids.add(id);',
        "                if (i > 0) opts.append(',');",
        '                opts.append("{\\\"option_id\\\":").append(esc(id)).append(",\\\"kind\\\":").append(esc(labels.get(i))).append("}");',
        "            }",
        '            out.println("{\\\"protocol\\\":" + esc(PROTOCOL) + ",\\\"message_type\\\":\\\"DECISION_FRAME\\\",\\\"request_id\\\":" + esc(did) + ",\\\"session_id\\\":" + esc(SESSION_ID) + ",\\\"actor_id\\\":" + esc(actor.getName()) + ",\\\"state_revision\\\":" + revision + ",\\\"payload\\\":{\\\"decision_id\\\":" + esc(did) + ",\\\"decision_kind\\\":" + esc(kind) + ",\\\"options_digest\\\":" + esc(digest(ids)) + ",\\\"options\\\":[" + opts + "]}}");',
        "            out.flush();",
        "            try {",
        "                String answer = in.readLine();",
        '                if (answer == null) throw new ControlledStop("WS23_EXTERNAL_EOF");',
        '                if (!"SUBMIT_DECISION".equals(field(answer, "message_type"))) throw new ControlledStop("WS23_EXPECTED_SUBMIT_DECISION");',
        '                if (!did.equals(field(answer, "decision_id"))) throw new ControlledStop("WS23_STALE_OR_WRONG_DECISION_ID");',
        '                String choice = field(answer, "option_id");',
        '                if (choice == null || !ids.contains(choice)) throw new ControlledStop("WS23_OPTION_NOT_OFFERED");',
        "                revision++;",
        "                return choice;",
        "            } catch (IOException e) { throw new RuntimeException(e); }",
        "        }",
        "",
        "        boolean chooseBoolean(String kind, Player actor, String trueLabel, String falseLabel) {",
        "            return \"o0\".equals(choose(kind, actor, java.util.List.of(trueLabel, falseLabel)));",
        "        }",
        "",
        "        Player choosePlayer(String kind, Player actor, Iterable<Player> players) {",
        "            java.util.List<Player> nativeOptions = new ArrayList<>();",
        "            java.util.List<String> labels = new ArrayList<>();",
        "            for (Player p : players) { nativeOptions.add(p); labels.add(\"PLAYER\"); }",
        "            String id = choose(kind, actor, labels);",
        '            return nativeOptions.get(Integer.parseInt(id.substring(1)));',
        "        }",
        "",
        "        <T> T chooseObject(String kind, Player actor, java.util.List<T> options, boolean optional) {",
        "            java.util.List<String> labels = new ArrayList<>();",
        '            if (optional) labels.add("NONE");',
        '            for (int i = 0; i < options.size(); i++) labels.add("NATIVE_OPTION");',
        "            String id = choose(kind, actor, labels);",
        "            int idx = Integer.parseInt(id.substring(1));",
        "            if (optional) { if (idx == 0) return null; idx--; }",
        "            return options.get(idx);",
        "        }",
        "",
        "        java.util.List<SpellAbility> choosePriority(Player actor, Game game) {",
        "            priorityDecisions++;",
        "            if (priorityDecisions > stopAfterPriorityDecisions) throw new ControlledStop(\"WS23_CONTROLLED_AFTER_PRIORITY_\" + stopAfterPriorityDecisions);",
        "            java.util.List<SpellAbility> nativeOptions = new ArrayList<>();",
        "            java.util.List<String> labels = new ArrayList<>();",
        '            labels.add("PASS");',
        "            java.util.Set<SpellAbility> seen = java.util.Collections.newSetFromMap(new IdentityHashMap<>());",
        "            ZoneType[] zones = new ZoneType[] { ZoneType.Hand, ZoneType.Battlefield, ZoneType.Graveyard, ZoneType.Exile, ZoneType.Command };",
        "            for (ZoneType zone : zones) {",
        "                for (Card c : actor.getCardsIn(zone)) {",
        "                    for (SpellAbility sa : c.getAllPossibleAbilities(actor, true)) {",
        "                        if (seen.add(sa)) { nativeOptions.add(sa); labels.add(\"FORGE_LEGAL_ACTION\"); }",
        "                    }",
        "                }",
        "            }",
        "            String id = choose(\"priority\", actor, labels);",
        "            int idx = Integer.parseInt(id.substring(1));",
        "            if (idx == 0) return java.util.List.of();",
        "            return java.util.List.of(nativeOptions.get(idx - 1));",
        "        }",
        "    }",
        "",
        "    static final class HeadlessLobbyPlayer extends LobbyPlayer implements IGameEntitiesFactory {",
        "        final Broker broker;",
        "        HeadlessLobbyPlayer(String name, Broker broker) { super(name); this.broker = broker; }",
        "        @Override public void hear(LobbyPlayer from, String message) { broker.recordAutomatic(\"hear\"); }",
        "        @Override public Player createIngamePlayer(Game game, int id) {",
        "            Player p = new Player(getName(), game, id);",
        "            p.dangerouslySetController(new Ws23Controller(game, p, this, broker));",
        "            return p;",
        "        }",
        "        @Override public PlayerController createMindSlaveController(Player master, Player slave) {",
        '            throw new UnsupportedOperationException("WS23_FAIL_CLOSED_UNSUPPORTED:createMindSlaveController");',
        "        }",
        "    }",
        "",
        "    static final class Ws23Controller extends PlayerController {",
        "        final Broker broker;",
        "        Ws23Controller(Game game, Player player, LobbyPlayer lobby, Broker broker) { super(game, player, lobby); this.broker = broker; }",
        "        RuntimeException failClosed(String method) { return new UnsupportedOperationException(\"WS23_FAIL_CLOSED_UNSUPPORTED:\" + method); }",
        "",
    ]
    for item in methods:
        lines.extend(["        @Override", f"        {item['signature']} {{"])
        for body_line in method_body(item["name"], item["signature"]):
            lines.append("    " + body_line)
        lines.extend(["        }", ""])
    lines.extend(
        [
            "    }",
            "",
            "    static String sessionSnapshot(Game game) {",
            "        String phase = String.valueOf(game.getPhaseHandler().getPhase());",
            "        String turn = String.valueOf(game.getPhaseHandler().getTurn());",
            "        StringBuilder players = new StringBuilder();",
            "        int i = 0;",
            "        for (Player p : game.getPlayers()) {",
            "            if (i++ > 0) players.append(',');",
            '            players.append("{\\\"actor_id\\\":").append(esc(p.getName())).append(",\\\"life\\\":").append(p.getLife()).append(",\\\"hand_count\\\":").append(p.getCardsIn(ZoneType.Hand).size()).append(",\\\"library_count\\\":").append(p.getCardsIn(ZoneType.Library).size()).append("}");',
            "        }",
            '        return "{\\\"player_count\\\":" + game.getPlayers().size() + ",\\\"turn\\\":" + esc(turn) + ",\\\"phase\\\":" + esc(phase) + ",\\\"players\\\":[" + players + "]}";',
            "    }",
            "",
            "    static void runSession(BufferedReader in, PrintWriter out) throws Exception {",
            "        Broker broker = new Broker(in, out, 16);",
            "        GameRules rules = new GameRules(GameType.Constructed);",
            "        java.util.List<RegisteredPlayer> registrations = new ArrayList<>();",
            "        for (int i = 1; i <= 4; i++) {",
            '            Deck deck = new Deck("WS23-SEAT-" + i);',
            "            deck.getMain().add(PaperCard.FAKE_CARD, 40);",
            "            RegisteredPlayer rp = new RegisteredPlayer(deck);",
            '            rp.setPlayer(new HeadlessLobbyPlayer("seat-" + i, broker));',
            "            registrations.add(rp);",
            "        }",
            '        Match match = new Match(rules, registrations, "WS23 Forge vertical slice");',
            "        Game game = match.createGame();",
            '        out.println("{\\\"protocol\\\":" + esc(PROTOCOL) + ",\\\"message_type\\\":\\\"SESSION_CREATED\\\",\\\"request_id\\\":\\\"ws23-session\\\",\\\"session_id\\\":" + esc(SESSION_ID) + ",\\\"payload\\\":{\\\"forge_commit\\\":" + esc(FORGE_COMMIT) + ",\\\"forge_tree\\\":" + esc(FORGE_TREE) + ",\\\"snapshot\\\":" + sessionSnapshot(game) + "}}");',
            "        out.flush();",
            "        String stopReason = null;",
            "        try {",
            "            match.startGame(game);",
            '            stopReason = "FORGE_GAME_RETURNED";',
            "        } catch (ControlledStop expected) {",
            "            stopReason = expected.getMessage();",
            "        } catch (UnsupportedOperationException unsupported) {",
            "            stopReason = unsupported.getMessage();",
            "        }",
            '        out.println("{\\\"protocol\\\":" + esc(PROTOCOL) + ",\\\"message_type\\\":\\\"SESSION_RESULT\\\",\\\"request_id\\\":\\\"ws23-result\\\",\\\"session_id\\\":" + esc(SESSION_ID) + ",\\\"state_revision\\\":" + broker.revision + ",\\\"payload\\\":{\\\"stop_reason\\\":" + esc(stopReason) + ",\\\"priority_decisions\\\":" + broker.priorityDecisions + ",\\\"snapshot\\\":" + sessionSnapshot(game) + "}}");',
            "        out.flush();",
            "    }",
            "",
            "    public static void main(String[] args) throws Exception {",
            "        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));",
            "        PrintWriter out = new PrintWriter(new OutputStreamWriter(System.out, StandardCharsets.UTF_8), true);",
            "        String first = in.readLine();",
            "        if (first == null || !PROTOCOL.equals(field(first, \"protocol\"))) { System.exit(2); return; }",
            "        String type = field(first, \"message_type\");",
            "        if (\"HANDSHAKE\".equals(type)) {",
            '            out.println("{\\\"protocol\\\":" + esc(PROTOCOL) + ",\\\"message_type\\\":\\\"HANDSHAKE_RESULT\\\",\\\"request_id\\\":" + esc(field(first, "request_id")) + ",\\\"payload\\\":{\\\"verdict\\\":\\\"PASS\\\",\\\"provider\\\":\\\"forge\\\",\\\"forge_commit\\\":" + esc(FORGE_COMMIT) + ",\\\"real_session_capable\\\":true}}");',
            "            return;",
            "        }",
            "        if (!\"CREATE_SESSION\".equals(type)) { System.exit(3); return; }",
            "        runSession(in, out);",
            "    }",
            "}",
            "",
        ]
    )
    return "\n".join(lines), {
        "schema_version": "ws23-player-controller-mapping/1.0.0",
        "forge_commit": forge_commit,
        "forge_tree": forge_tree,
        "abstract_method_count": len(methods),
        "callbacks": classifications,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player-controller", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--forge-commit", required=True)
    ap.add_argument("--forge-tree", required=True)
    args = ap.parse_args()
    source = args.player_controller.read_text(encoding="utf-8")
    java, mapping = render(source, args.forge_commit, args.forge_tree)
    out = args.output_dir
    java_dir = out / "java" / "forge" / "game" / "player"
    java_dir.mkdir(parents=True, exist_ok=True)
    (java_dir / "Ws23ForgeVerticalProvider.java").write_text(java, encoding="utf-8")
    (out / "player_controller_mapping.json").write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"abstract_method_count": mapping["abstract_method_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
