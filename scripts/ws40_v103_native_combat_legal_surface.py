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
        "import forge.game.combat.Combat;\n",
        "import forge.game.combat.Combat;\nimport forge.game.combat.CombatUtil;\n",
        "native combat legality import",
    )

    old = '''    private static String combatJson(Game game) {\n        Combat combat = game.getCombat();\n        if (combat == null) return "null";\n        StringBuilder a = new StringBuilder("{");\n        boolean first = true;\n        for (Card c : combat.getAttackers()) {\n            String sid = semanticOf(c); if (sid == null) continue;\n            if (!first) a.append(','); first = false;\n            GameEntity def = combat.getDefenderByAttacker(c);\n            String dk = def instanceof Player ? playerId(game,(Player)def) : semanticOf((Card)def);\n            a.append(Ws23ForgeVerticalProvider.esc(sid)).append(':').append(Ws23ForgeVerticalProvider.esc(dk));\n        }\n        a.append('}');\n        StringBuilder bl = new StringBuilder("{"); first = true;\n        for (Card blocker : combat.getAllBlockers()) {\n            String bsid = semanticOf(blocker); if (bsid == null) continue;\n            List<Card> blocked = combat.getAttackersBlockedBy(blocker);\n            if (blocked.isEmpty()) continue;\n            if (!first) bl.append(','); first = false;\n            bl.append(Ws23ForgeVerticalProvider.esc(bsid)).append(':').append(Ws23ForgeVerticalProvider.esc(semanticOf(blocked.get(0))));\n        }\n        bl.append('}');\n        return "{\\\"attackers\\\":" + a + ",\\\"blockers\\\":" + bl + "}";\n    }\n'''
    new = '''    private static String eligibleAttackersJson(Game game) {\n        Player active = game.getPhaseHandler().getPlayerTurn();\n        if (active == null) {\n            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_COMBAT_NATIVE_ACTIVE_PLAYER_UNAVAILABLE");\n        }\n        List<String> ids = new ArrayList<>();\n        for (Card card : CombatUtil.getPossibleAttackers(active)) {\n            String sid = semanticOf(card);\n            if (sid == null) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_COMBAT_NATIVE_ELIGIBLE_ATTACKER_IDENTITY_UNAVAILABLE:" + card);\n            }\n            ids.add(sid);\n        }\n        ids.sort(String::compareTo);\n        StringBuilder b = new StringBuilder("[");\n        for (int i = 0; i < ids.size(); i++) {\n            if (i > 0) b.append(',');\n            b.append(Ws23ForgeVerticalProvider.esc(ids.get(i)));\n        }\n        return b.append(']').toString();\n    }\n\n    private static String combatJson(Game game) {\n        Combat combat = game.getCombat();\n        StringBuilder a = new StringBuilder("{");\n        boolean first = true;\n        if (combat != null) for (Card c : combat.getAttackers()) {\n            String sid = semanticOf(c);\n            if (sid == null) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_COMBAT_NATIVE_ATTACKER_IDENTITY_UNAVAILABLE:" + c);\n            }\n            if (!first) a.append(','); first = false;\n            GameEntity def = combat.getDefenderByAttacker(c);\n            String dk = def instanceof Player ? playerId(game,(Player)def) : semanticOf((Card)def);\n            if (dk == null) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_COMBAT_NATIVE_DEFENDER_IDENTITY_UNAVAILABLE:" + def);\n            }\n            a.append(Ws23ForgeVerticalProvider.esc(sid)).append(':').append(Ws23ForgeVerticalProvider.esc(dk));\n        }\n        a.append('}');\n        StringBuilder bl = new StringBuilder("{"); first = true;\n        if (combat != null) for (Card blocker : combat.getAllBlockers()) {\n            String bsid = semanticOf(blocker);\n            if (bsid == null) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_COMBAT_NATIVE_BLOCKER_IDENTITY_UNAVAILABLE:" + blocker);\n            }\n            List<Card> blocked = combat.getAttackersBlockedBy(blocker);\n            if (blocked.isEmpty()) continue;\n            String asid = semanticOf(blocked.get(0));\n            if (asid == null) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_COMBAT_NATIVE_BLOCKED_ATTACKER_IDENTITY_UNAVAILABLE:" + blocked.get(0));\n            }\n            if (!first) bl.append(','); first = false;\n            bl.append(Ws23ForgeVerticalProvider.esc(bsid)).append(':').append(Ws23ForgeVerticalProvider.esc(asid));\n        }\n        bl.append('}');\n        return "{\\\"attackers\\\":" + a + ",\\\"blockers\\\":" + bl\n            + ",\\\"eligible_attackers\\\":" + eligibleAttackersJson(game) + "}";\n    }\n'''
    s = once(s, old, new, "native eligible-attacker observer")
    path.write_text(s, encoding="utf-8")


def patch_runner(path: Path) -> None:
    s = path.read_text(encoding="utf-8")
    old = '''def _combat_from_native(raw: dict[str, Any], b: dict[str, Any]) -> Any:\n    fields = set(b.get("combat_fields") or [])\n    if not fields:\n        return None\n    unsupported = sorted(fields.intersection({"eligible_attackers", "eligible_blockers"}))\n    if unsupported:\n        raise AssertionError(\n            "CANONICAL_SETUP_UNSUPPORTED_PROVIDER:COMBAT_LEGAL_SURFACE_NATIVE_OBSERVATION_UNAVAILABLE:"\n            + ",".join(unsupported)\n        )\n    got = raw.get("combat") or {"attackers": {}, "blockers": {}}\n    attackers = dict(got.get("attackers") or {})\n    blockers = dict(got.get("blockers") or {})\n    out: dict[str, Any] = {}\n    if "attackers" in fields:\n        out["attackers"] = attackers\n    if "blockers" in fields:\n        out["blockers"] = blockers\n    blocked = set(blockers.values())\n    unblocked = [sid for sid in attackers if sid not in blocked]\n    if "unblocked" in fields:\n        out["unblocked"] = unblocked\n    if "unblocked_attackers" in fields:\n        out["unblocked_attackers"] = unblocked\n    unknown = fields.difference({"attackers", "blockers", "unblocked", "unblocked_attackers"})\n    if unknown:\n        raise AssertionError("CANONICAL_SETUP_UNSUPPORTED_PROVIDER:COMBAT_FIELD_NATIVE_OBSERVATION_UNAVAILABLE:" + ",".join(sorted(unknown)))\n    return out\n'''
    new = '''def _combat_from_native(raw: dict[str, Any], b: dict[str, Any]) -> Any:\n    fields = set(b.get("combat_fields") or [])\n    if not fields:\n        return None\n    unsupported = sorted(fields.intersection({"eligible_blockers"}))\n    if unsupported:\n        raise AssertionError(\n            "CANONICAL_SETUP_UNSUPPORTED_PROVIDER:COMBAT_LEGAL_SURFACE_NATIVE_OBSERVATION_UNAVAILABLE:"\n            + ",".join(unsupported)\n        )\n    got = raw.get("combat") or {}\n    attackers = dict(got.get("attackers") or {})\n    blockers = dict(got.get("blockers") or {})\n    out: dict[str, Any] = {}\n    if "attackers" in fields:\n        out["attackers"] = attackers\n    if "blockers" in fields:\n        out["blockers"] = blockers\n    if "eligible_attackers" in fields:\n        native_eligible = got.get("eligible_attackers")\n        if not isinstance(native_eligible, list) or any(not isinstance(x, str) for x in native_eligible):\n            raise AssertionError("CANONICAL_SETUP_UNSUPPORTED_PROVIDER:COMBAT_ELIGIBLE_ATTACKERS_NATIVE_OBSERVATION_INVALID")\n        if len(native_eligible) != len(set(native_eligible)):\n            raise AssertionError("CANONICAL_SETUP_UNSUPPORTED_PROVIDER:COMBAT_ELIGIBLE_ATTACKERS_NATIVE_OBSERVATION_DUPLICATE")\n        out["eligible_attackers"] = sorted(native_eligible)\n    blocked = set(blockers.values())\n    unblocked = [sid for sid in attackers if sid not in blocked]\n    if "unblocked" in fields:\n        out["unblocked"] = unblocked\n    if "unblocked_attackers" in fields:\n        out["unblocked_attackers"] = unblocked\n    unknown = fields.difference({"attackers", "blockers", "eligible_attackers", "unblocked", "unblocked_attackers"})\n    if unknown:\n        raise AssertionError("CANONICAL_SETUP_UNSUPPORTED_PROVIDER:COMBAT_FIELD_NATIVE_OBSERVATION_UNAVAILABLE:" + ",".join(sorted(unknown)))\n    return out\n'''
    s = once(s, old, new, "native eligible-attacker normalization")
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
        print("WS40_V103_NATIVE_COMBAT_ELIGIBLE_ATTACKERS_JAVA_PATCH=PASS")
    else:
        patch_runner(args.runner)
        print("WS40_V103_NATIVE_COMBAT_ELIGIBLE_ATTACKERS_RUNNER_PATCH=PASS")


if __name__ == "__main__":
    main()
