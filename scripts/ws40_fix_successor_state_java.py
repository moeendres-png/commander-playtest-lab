#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, got {n}")
    return text.replace(old, new, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--state-java', type=Path, required=True)
    args = ap.parse_args()
    p = args.state_java
    s = p.read_text(encoding='utf-8')

    s = once(s,
        '    private Ws40SuccessorState() {}\n',
        '    private Ws40SuccessorState() {}\n\n'
        '    /** Qualification-only synchronous entry into Forge GameState on the game thread. */\n'
        '    private static final class Ws40GameState extends GameState {\n'
        '        void applySynchronously(Game game) {\n'
        '            applyGameOnThread(game);\n'
        '        }\n'
        '    }\n',
        'synchronous native GameState adapter')

    s = once(s,
        '    private static String decodeB64Env(String name) {\n'
        '        String value = env(name);\n'
        '        if (value.isEmpty()) return "";\n'
        '        return new String(Base64.getDecoder().decode(value), StandardCharsets.UTF_8);\n'
        '    }\n',
        '    private static String decodeB64Env(String name) {\n'
        '        String value = env(name);\n'
        '        if (value.isEmpty()) return "";\n'
        '        return new String(Base64.getDecoder().decode(value), StandardCharsets.UTF_8);\n'
        '    }\n\n'
        '    private static String sha256(String value) {\n'
        '        try {\n'
        '            byte[] digest = java.security.MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));\n'
        '            return java.util.HexFormat.of().formatHex(digest);\n'
        '        } catch (java.security.NoSuchAlgorithmException e) {\n'
        '            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_SHA256_UNAVAILABLE");\n'
        '        }\n'
        '    }\n\n'
        '    private static String boundConfigJson() {\n'
        '        String json = decodeB64Env("COMMANDER_LAB_WS40_BOUND_CONFIG_B64");\n'
        '        if (json.isEmpty()) {\n'
        '            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_BOUND_CONFIG_MISSING");\n'
        '        }\n'
        '        String digest = sha256(json);\n'
        '        if (!digest.equals(env("COMMANDER_LAB_WS40_CONFIG_BINDING_DIGEST"))) {\n'
        '            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_BOUND_CONFIG_DIGEST_MISMATCH");\n'
        '        }\n'
        '        return json;\n'
        '    }\n',
        'provider-bound configuration state')

    s = once(s,
        '            if (candidates.size() != 1) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_BIND_NONUNIQUE:" + s.semanticId + ":" + candidates.size());\n            }\n            Card c = candidates.get(0);',
        '            if (candidates.isEmpty()) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_BIND_MISSING:" + s.semanticId);\n            }\n            // Equal physical cards are intentionally indistinguishable to Forge. Semantic identity is a\n            // provider-neutral mapping layer only; choose the first still-unbound card in native zone order.\n            Card c = candidates.get(0);',
        'duplicate physical card binding')

    s = once(s,
        '        GameState state = new GameState();\n        state.parse(buildGameStateLines(game));\n        state.applyToGame(game);',
        '        Ws40GameState state = new Ws40GameState();\n        state.parse(buildGameStateLines(game));\n        // This hook already executes during Forge game initialization. Calling the protected native\n        // implementation synchronously avoids racing GameAction.invoke while preserving GameState semantics.\n        state.applySynchronously(game);',
        'synchronous native state application')

    s = once(s,
        '            for (Card c : player(game, s.controller).getCardsIn(zoneType(s.zone), false)) {',
        '            for (Card c : new ArrayList<>(player(game, s.controller).getCardsIn(zoneType(s.zone), false))) {',
        'stable native zone binding iteration')

    s = once(s,
        '        for (String[] p : rows("COMMANDER_LAB_WS40_STACK_SPECS_B64")) {',
        '        List<String[]> ws40StackRows = rows("COMMANDER_LAB_WS40_STACK_SPECS_B64");\n        java.util.Collections.reverse(ws40StackRows);\n        for (String[] p : ws40StackRows) {',
        'stack construction order')

    s = once(s,
        '        for (var e : c.getCounters().entrySet()) entries.add(Map.entry(e.getKey(), e.getValue()));',
        '        for (var e : c.getCounters().entrySet()) entries.add(Map.entry(e.getElement(), e.getCount()));',
        'guava multiset counter entries')

    s = s.replace('c.isSick()', 'c.hasSickness()')

    # Natural registration is a real provider construction surface. Emit native players/decks and the
    # provider-bound non-rules configuration, with the digest recomputed inside the isolated GPL JVM.
    s = once(s,
        '        String raw = "{\\\"natural_registration\\\":true,\\\"player_count\\\":" + game.getPlayers().size()\n'
        '            + ",\\\"decks\\\":" + decks + ",\\\"rules_commander\\\":" + game.getRules().hasAppliedVariant(forge.game.GameType.Commander) + "}";',
        '        String ws40BoundConfig = boundConfigJson();\n'
        '        String raw = "{\\\"natural_registration\\\":true,\\\"provider_entry_mode\\\":\\\"NATURAL_GAME_START\\\",\\\"player_count\\\":" + game.getPlayers().size()\n'
        '            + ",\\\"players\\\":" + playersJson(game)\n'
        '            + ",\\\"decks\\\":" + decks + ",\\\"rules_commander\\\":" + game.getRules().hasAppliedVariant(forge.game.GameType.Commander)\n'
        '            + ",\\\"rules_seed_configured\\\":" + Ws23ForgeVerticalProvider.esc(env("COMMANDER_LAB_FORGE_RULES_SEED"))\n'
        '            + ",\\\"bound_config\\\":" + ws40BoundConfig\n'
        '            + ",\\\"config_binding_digest\\\":" + Ws23ForgeVerticalProvider.esc(sha256(ws40BoundConfig)) + "}";',
        'natural provider-bound configuration')

    # Native-state-load snapshots likewise carry the configuration as state owned by the isolated provider;
    # Python normalization consumes this emitted state instead of copying values from the requested record.
    s = once(s,
        '        String raw = "{\\\"natural_registration\\\":" + natural\n'
        '            + ",\\\"player_count\\\":" + game.getPlayers().size()',
        '        String ws40BoundConfig = boundConfigJson();\n'
        '        String raw = "{\\\"natural_registration\\\":" + natural\n'
        '            + ",\\\"provider_entry_mode\\\":\\\"NATIVE_STATE_LOAD\\\""\n'
        '            + ",\\\"player_count\\\":" + game.getPlayers().size()',
        'native entry-mode evidence')

    s = once(s,
        '            + ",\\\"rules_commander\\\":" + game.getRules().hasAppliedVariant(forge.game.GameType.Commander)\n'
        '            + ",\\\"config_binding_digest\\\":" + Ws23ForgeVerticalProvider.esc(env("COMMANDER_LAB_WS40_CONFIG_BINDING_DIGEST")) + "}";',
        '            + ",\\\"rules_commander\\\":" + game.getRules().hasAppliedVariant(forge.game.GameType.Commander)\n'
        '            + ",\\\"rules_seed_configured\\\":" + Ws23ForgeVerticalProvider.esc(env("COMMANDER_LAB_FORGE_RULES_SEED"))\n'
        '            + ",\\\"bound_config\\\":" + ws40BoundConfig\n'
        '            + ",\\\"config_binding_digest\\\":" + Ws23ForgeVerticalProvider.esc(sha256(ws40BoundConfig)) + "}";',
        'native provider-bound configuration')

    p.write_text(s, encoding='utf-8')
    print('WS40_SUCCESSOR_STATE_JAVA_FIX=PASS')


if __name__ == '__main__':
    main()
