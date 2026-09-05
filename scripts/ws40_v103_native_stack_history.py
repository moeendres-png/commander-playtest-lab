#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

WS41_COMMIT = "24152acf36b5a560c23ccacfed3f31d3039537eb"
WS41_TREE = "428bbe58b2ea7b869200521092a8768108029b47"
WS41_SCHEMA = "commander-lab.semantic-fixture-materialization/1.0.3"
WS41_BUNDLE = "545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b"
WS41_FILE_SHA = "8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5"
FORGE_COMMIT = "f83b77aa75e4f90852bef9243f3c5b32c37dc7e0"
FORGE_TREE = "e2f124f30d55e43f838615a969af4e09e7009471"
PREVIOUS_FORGE_COMMIT = "49ea6df753fa6c749138296a1fe9421467136dda"
PREVIOUS_FORGE_TREE = "37ef36359cef74273ca40a2c1c676b8ede84a431"


def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, got {n}")
    return text.replace(old, new, 1)


def patch_state_java(path: Path) -> None:
    s = path.read_text(encoding="utf-8")
    s = once(s, "import forge.game.GameEntity;\n", "import forge.game.GameEntity;\nimport forge.game.GameObject;\n", "GameObject import")
    s = once(s, "import forge.game.spellability.SpellAbility;\n", "import forge.game.spellability.SpellAbility;\nimport forge.game.zone.RestoredSpellCastHistory;\n", "native restore history import")
    s = once(
        s,
        '''    private static GameEntity target(Game game, String key) {\n        if (key.matches("P[1-5]")) return player(game, Integer.parseInt(key.substring(1)));\n        Card c = semanticCards.get(key);\n        if (c == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_TARGET_UNBOUND:" + key);\n        return c;\n    }\n''',
        '''    private static GameObject target(Game game, String key) {\n        if (key.matches("P[1-5]")) return player(game, Integer.parseInt(key.substring(1)));\n        SpellAbility stackTarget = stackAbilities.get(key);\n        if (stackTarget != null) return stackTarget;\n        Card c = semanticCards.get(key);\n        if (c == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_TARGET_UNBOUND:" + key);\n        return c;\n    }\n''',
        "stack-spell target identity mapping",
    )
    s = once(s, "            game.getStack().addAndUnfreeze(sa);\n", "            RestoredSpellCastHistory.restoreCompletedPaidSpell(game, sa);\n", "native completed-paid stack restore")
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

    # Bind the generated executable runner to the immutable WS41 successor and the freshly
    # requalified Forge source. The earlier hardening patch has already advanced Forge to the
    # historical 49ea lock; this patch advances it once more to the stack-history remediation.
    replacements = {
        'WS32_COMMIT = "038d0f38635eecee4e331c99af41f148de267a26"': f'WS32_COMMIT = "{WS41_COMMIT}"',
        'WS32_TREE = "0d160128119f2bad30b220a17c43419b50b7edbe"': f'WS32_TREE = "{WS41_TREE}"',
        'WS32_SCHEMA = "commander-lab.semantic-fixture-materialization/1.0.2"': f'WS32_SCHEMA = "{WS41_SCHEMA}"',
        'WS32_BUNDLE = "ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23"': f'WS32_BUNDLE = "{WS41_BUNDLE}"',
        'WS32_FILE_SHA = "0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261"': f'WS32_FILE_SHA = "{WS41_FILE_SHA}"',
        f'FORGE_COMMIT = "{PREVIOUS_FORGE_COMMIT}"': f'FORGE_COMMIT = "{FORGE_COMMIT}"',
        f'FORGE_TREE = "{PREVIOUS_FORGE_TREE}"': f'FORGE_TREE = "{FORGE_TREE}"',
    }
    for old, new in replacements.items():
        s = once(s, old, new, f"source lock replacement {old.split(' = ')[0]}")

    # The no-request-echo hardening patch already removed stack rules-state values from bound
    # configuration and intentionally replaced the normalizer with this fail-closed function.
    # v1.0.3 restores support by consuming only native Forge observations.
    s = once(
        s,
        '''def _stack_from_native(raw: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:\n    source_ids = list(b.get("stack_source_ids") or [])\n    if not source_ids:\n        return []\n    native = {s["source_semantic_id"]: s for s in raw.get("stack") or []}\n    for sid in source_ids:\n        got = native.get(sid)\n        if got is None or not got.get("native_stack_present"):\n            raise AssertionError(f"native stack object missing {sid}")\n    # The qualification loader can prove current native stack presence/controller, but it\n    # directly materializes the stack and therefore cannot independently prove the frozen\n    # historical facts cast_complete/costs_paid or selected Charm modes. Emitting those\n    # request values would be request echo. Fail closed instead of manufacturing credit.\n    raise AssertionError("CANONICAL_SETUP_UNSUPPORTED_PROVIDER:STACK_CAST_HISTORY_NATIVE_OBSERVATION_UNAVAILABLE")''',
        '''def _stack_from_native(raw: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:\n    source_ids = list(b.get("stack_source_ids") or [])\n    if not source_ids:\n        return []\n    native = {s["source_semantic_id"]: s for s in raw.get("stack") or []}\n    out = []\n    for sid in source_ids:\n        got = native.get(sid)\n        if got is None or not got.get("native_stack_present"):\n            raise AssertionError(f"native stack object missing {sid}")\n        if got.get("history_source") != "FORGE_NATIVE_RESTORED_SPELL_CAST_HISTORY":\n            raise AssertionError(f"native stack history source missing {sid}")\n        out.append({\n            "source_semantic_id": sid,\n            "cast_complete": bool(got["cast_complete"]),\n            "controller": got["controller"],\n            "costs_paid": bool(got["costs_paid"]),\n            "modes": list(got.get("modes") or []),\n            "targets": list(got.get("targets") or []),\n        })\n    return out''',
        "native stack normalization after fail-closed hardening",
    )

    s = once(
        s,
        '    ap.add_argument("--output", type=Path, required=True)\n',
        '    ap.add_argument("--output", type=Path, required=True)\n    ap.add_argument("--denominator", type=Path, required=True)\n',
        "denominator argument",
    )
    s = once(
        s,
        '''    if hashlib.sha256(raw_bytes).hexdigest() != WS32_FILE_SHA:\n        raise SystemExit("immutable WS32 materialization file digest mismatch")\n    doc = json.loads(raw_bytes)\n    if doc["schema_version"] != WS32_SCHEMA or doc["canonical_bundle_digest"] != WS32_BUNDLE:\n        raise SystemExit("immutable WS32 materialization identity mismatch")\n    records = [r for r in doc["records"] if r.get("fixture_family") != "actual_card" or r["fixture_id"] == "CARD_02"]\n    if len(records) != 107:\n        raise SystemExit(f"denominator mismatch {len(records)}")\n''',
        '''    if hashlib.sha256(raw_bytes).hexdigest() != WS32_FILE_SHA:\n        raise SystemExit("immutable WS41 v1.0.3 materialization file digest mismatch")\n    doc = json.loads(raw_bytes)\n    if doc["schema_version"] != WS32_SCHEMA or doc["canonical_bundle_digest"] != WS32_BUNDLE:\n        raise SystemExit("immutable WS41 v1.0.3 materialization identity mismatch")\n    denominator = json.loads(args.denominator.read_text(encoding="utf-8"))\n    ids = denominator.get("fixture_ids") or []\n    if denominator.get("provider_denominator_count") != 107 or len(ids) != 107 or len(set(ids)) != 107:\n        raise SystemExit("immutable WS41 provider denominator is not exactly 107 unique IDs")\n    by_id = {r["fixture_id"]: r for r in doc["records"]}\n    records = [by_id[fid] for fid in ids]\n    if [r["fixture_id"] for r in records] != ids:\n        raise SystemExit("provider denominator order mismatch")\n''',
        "exact WS41 denominator consumption",
    )
    s = once(
        s,
        '        "ws32_commit": WS32_COMMIT, "ws32_tree": WS32_TREE, "ws32_bundle_digest": WS32_BUNDLE,\n',
        '        "ws41_commit": WS32_COMMIT, "ws41_tree": WS32_TREE, "ws41_bundle_digest": WS32_BUNDLE,\n        "contract_version": WS32_SCHEMA,\n        "historical_successor_credit_imported": 0,\n',
        "v1.0.3 result source lock",
    )
    s = s.replace("immutable WS32", "immutable WS41 v1.0.3")
    # Source hardening metadata should no longer list stack history as an unresolved proof gap.
    s = s.replace(
        '                "stack_state historical cast/payment/mode facts",\n',
        '',
        1,
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
        print("WS40_V103_SOURCE_LOCK_RETARGET=PASS")


if __name__ == "__main__":
    main()
