#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, got {n}")
    return text.replace(old, new, 1)


def patch_state_java(path: Path) -> None:
    s = path.read_text(encoding="utf-8")
    s = once(
        s,
        "import forge.game.GameEntity;\n",
        "import forge.game.GameEntity;\nimport forge.game.GameObject;\n",
        "GameObject import",
    )
    s = once(
        s,
        "import forge.game.spellability.SpellAbility;\n",
        "import forge.game.spellability.SpellAbility;\nimport forge.game.zone.RestoredSpellCastHistory;\n",
        "native restore history import",
    )
    s = once(
        s,
        '''    private static GameEntity target(Game game, String key) {\n        if (key.matches("P[1-5]")) return player(game, Integer.parseInt(key.substring(1)));\n        Card c = semanticCards.get(key);\n        if (c == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_TARGET_UNBOUND:" + key);\n        return c;\n    }\n''',
        '''    private static GameObject target(Game game, String key) {\n        if (key.matches("P[1-5]")) return player(game, Integer.parseInt(key.substring(1)));\n        SpellAbility stackTarget = stackAbilities.get(key);\n        if (stackTarget != null) return stackTarget;\n        Card c = semanticCards.get(key);\n        if (c == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_TARGET_UNBOUND:" + key);\n        return c;\n    }\n''',
        "stack-spell target identity mapping",
    )
    s = once(
        s,
        "            game.getStack().addAndUnfreeze(sa);\n",
        "            RestoredSpellCastHistory.restoreCompletedPaidSpell(game, sa);\n",
        "native completed-paid stack restore",
    )
    s = once(
        s,
        '''    private static String semanticOf(Card c) {\n        if (c == null) return null;\n        for (Map.Entry<String,Card> e : semanticCards.entrySet()) if (e.getValue() == c) return e.getKey();\n        return null;\n    }\n''',
        '''    private static String semanticOf(Card c) {\n        if (c == null) return null;\n        for (Map.Entry<String,Card> e : semanticCards.entrySet()) if (e.getValue() == c) return e.getKey();\n        return null;\n    }\n\n    private static String semanticOf(SpellAbility sa) {\n        if (sa == null) return null;\n        for (Map.Entry<String,SpellAbility> e : stackAbilities.entrySet()) {\n            if (e.getValue() == sa || e.getValue().getId() == sa.getId()) return e.getKey();\n        }\n        return null;\n    }\n\n    private static String stackTargetSemantic(Game game, GameObject target) {\n        String key = null;\n        if (target instanceof Player) key = playerId(game, (Player) target);\n        else if (target instanceof SpellAbility) key = semanticOf((SpellAbility) target);\n        else if (target instanceof Card) key = semanticOf((Card) target);\n        if (key == null) {\n            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STACK_TARGET_IDENTITY_UNAVAILABLE:" + target);\n        }\n        return key;\n    }\n\n    private static String stackTargetsJson(Game game, SpellAbility sa) {\n        StringBuilder b = new StringBuilder("[");\n        boolean first = true;\n        for (GameObject target : sa.getTargets()) {\n            if (!first) b.append(',');\n            first = false;\n            b.append(Ws23ForgeVerticalProvider.esc(stackTargetSemantic(game, target)));\n        }\n        return b.append(']').toString();\n    }\n''',
        "native stack target observation helpers",
    )
    s = once(
        s,
        '''    private static String stackJson(Game game) {\n        StringBuilder b = new StringBuilder("[");\n        boolean first = true;\n        for (Map.Entry<String,SpellAbility> e : stackAbilities.entrySet()) {\n            SpellAbility sa = e.getValue();\n            if (!first) b.append(','); first = false;\n            b.append("{\\\"source_semantic_id\\\":").append(Ws23ForgeVerticalProvider.esc(e.getKey()))\n                .append(",\\\"native_stack_present\\\":").append(game.getStack().getInstanceMatchingSpellAbilityID(sa) != null)\n                .append(",\\\"controller\\\":").append(Ws23ForgeVerticalProvider.esc(playerId(game,sa.getActivatingPlayer())))\n                .append('}');\n        }\n        return b.append(']').toString();\n    }\n''',
        '''    private static String stackJson(Game game) {\n        StringBuilder b = new StringBuilder("[");\n        boolean first = true;\n        for (Map.Entry<String,SpellAbility> e : stackAbilities.entrySet()) {\n            SpellAbility sa = e.getValue();\n            boolean nativePresent = game.getStack().getInstanceMatchingSpellAbilityID(sa) != null;\n            if (!nativePresent || !RestoredSpellCastHistory.hasNativeHistory(sa)) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STACK_NATIVE_HISTORY_MISSING:" + e.getKey());\n            }\n            if (sa.getChosenList() != null && !sa.getChosenList().isEmpty()) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STACK_MODE_OBSERVATION_UNSUPPORTED_NONEMPTY:" + e.getKey());\n            }\n            if (!first) b.append(','); first = false;\n            b.append("{\\\"source_semantic_id\\\":").append(Ws23ForgeVerticalProvider.esc(e.getKey()))\n                .append(",\\\"native_stack_present\\\":true")\n                .append(",\\\"cast_complete\\\":").append(RestoredSpellCastHistory.isCastComplete(sa))\n                .append(",\\\"controller\\\":").append(Ws23ForgeVerticalProvider.esc(playerId(game,sa.getActivatingPlayer())))\n                .append(",\\\"costs_paid\\\":").append(RestoredSpellCastHistory.areCostsPaid(sa))\n                .append(",\\\"modes\\\":[]")\n                .append(",\\\"targets\\\":").append(stackTargetsJson(game, sa))\n                .append(",\\\"history_source\\\":\\\"FORGE_NATIVE_RESTORED_SPELL_CAST_HISTORY\\\"")\n                .append('}');\n        }\n        return b.append(']').toString();\n    }\n''',
        "native stack history snapshot",
    )
    path.write_text(s, encoding="utf-8")


def patch_runner(path: Path) -> None:
    s = path.read_text(encoding="utf-8")
    s = once(
        s,
        '''        "stack_semantics": [\n            {k: st[k] for k in ("source_semantic_id", "cast_complete", "costs_paid", "modes", "targets") if k in st}\n            for st in record.get("stack_state") or []\n        ],\n''',
        '''        # Stack rules state is deliberately excluded. Only provider-neutral identity is bound.\n        "stack_semantics": [\n            {"source_semantic_id": st["source_semantic_id"]}\n            for st in record.get("stack_state") or []\n        ],\n''',
        "remove stack rules state from provider-bound config",
    )
    s = once(
        s,
        '''def _stack_from_native(raw: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:\n    native = {s["source_semantic_id"]: s for s in raw.get("stack") or []}\n    out = []\n    for meta in b.get("stack_semantics") or []:\n        got = native.get(meta["source_semantic_id"])\n        if got is None or not got.get("native_stack_present"):\n            raise AssertionError(f"native stack object missing {meta['source_semantic_id']}")\n        row = dict(meta)\n        row["controller"] = got["controller"]\n        out.append(row)\n    return out\n''',
        '''def _stack_from_native(raw: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:\n    native = {s["source_semantic_id"]: s for s in raw.get("stack") or []}\n    out = []\n    for meta in b.get("stack_semantics") or []:\n        sid = meta["source_semantic_id"]\n        got = native.get(sid)\n        if got is None or not got.get("native_stack_present"):\n            raise AssertionError(f"native stack object missing {sid}")\n        if got.get("history_source") != "FORGE_NATIVE_RESTORED_SPELL_CAST_HISTORY":\n            raise AssertionError(f"native stack history source missing {sid}")\n        row = {\n            "source_semantic_id": sid,\n            "cast_complete": bool(got["cast_complete"]),\n            "controller": got["controller"],\n            "costs_paid": bool(got["costs_paid"]),\n            "modes": list(got.get("modes") or []),\n            "targets": list(got.get("targets") or []),\n        }\n        out.append(row)\n    return out\n''',
        "normalize stack solely from native observations",
    )
    path.write_text(s, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-java", type=Path)
    ap.add_argument("--runner", type=Path)
    args = ap.parse_args()
    if bool(args.state_java) == bool(args.runner):
        raise SystemExit("pass exactly one of --state-java or --runner")
    if args.state_java:
        patch_state_java(args.state_java)
        print("WS40_V103_NATIVE_STACK_STATE_PATCH=PASS")
    else:
        patch_runner(args.runner)
        print("WS40_V103_NATIVE_STACK_RUNNER_PATCH=PASS")


if __name__ == "__main__":
    main()
