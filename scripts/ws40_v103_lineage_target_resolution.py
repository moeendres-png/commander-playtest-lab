#!/usr/bin/env python3
"""Apply the WS40 v1.0.3 adjudicated target-identity remediation.

Only provider-neutral card_lineage_id is added to the state-loader transport.
Target lookup remains exact first, then permits one case-sensitive lineage-base
match (card_lineage_id == 'line:' + requested target id). Zero matches remain
unbound; multiple distinct matches fail closed. No card-name/case-fold/owner
heuristics are permitted.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "WS40_V103_LINEAGE_TARGET_RESOLUTION"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one patch target, got {count}")
    return text.replace(old, new, 1)


def patch_state_java(path: Path) -> None:
    text = path.read_text()
    if MARKER in text:
        print(f"{path}: lineage target resolution already applied")
        return

    text = replace_once(
        text,
        "        final String commanderId;\n        final boolean controlledSinceTurnBegan;\n        final boolean emitSemantic;",
        "        final String commanderId;\n        final boolean controlledSinceTurnBegan;\n        final boolean emitSemantic;\n        final String cardLineageId;",
        "ObjSpec field",
    )
    text = replace_once(
        text,
        "            commanderId = dec(p[10]);\n            controlledSinceTurnBegan = Boolean.parseBoolean(p[11]);\n            emitSemantic = Boolean.parseBoolean(p[12]);",
        "            commanderId = dec(p[10]);\n            controlledSinceTurnBegan = Boolean.parseBoolean(p[11]);\n            emitSemantic = Boolean.parseBoolean(p[12]);\n            cardLineageId = dec(p[13]);",
        "ObjSpec constructor",
    )
    text = replace_once(
        text,
        "            if (p.length != 13) throw new Ws23ForgeVerticalProvider.ControlledStop(\"WS40_STATE_OBJECT_SPEC_ARITY:\" + p.length);",
        "            if (p.length != 14) throw new Ws23ForgeVerticalProvider.ControlledStop(\"WS40_STATE_OBJECT_SPEC_ARITY:\" + p.length);",
        "object spec arity",
    )
    old_target = '''    private static GameEntity target(Game game, String key) {
        if (key.matches("P[1-5]")) return player(game, Integer.parseInt(key.substring(1)));
        Card c = semanticCards.get(key);
        if (c == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_TARGET_UNBOUND:" + key);
        return c;
    }'''
    new_target = '''    // WS40_V103_LINEAGE_TARGET_RESOLUTION: exact semantic identity first;
    // one frozen provider-neutral lineage-base alias is permitted, fail closed otherwise.
    private static GameEntity target(Game game, String key) {
        if (key.matches("P[1-5]")) return player(game, Integer.parseInt(key.substring(1)));
        Card exact = semanticCards.get(key);
        if (exact != null) return exact;

        String wantedLineage = "line:" + key;
        Card lineageMatch = null;
        for (ObjSpec spec : objectSpecs) {
            if (!wantedLineage.equals(spec.cardLineageId)) continue;
            Card candidate = semanticCards.get(spec.semanticId);
            if (candidate == null) continue;
            if (lineageMatch != null && lineageMatch != candidate) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_TARGET_AMBIGUOUS:" + key);
            }
            lineageMatch = candidate;
        }
        if (lineageMatch != null) return lineageMatch;
        throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_TARGET_UNBOUND:" + key);
    }'''
    text = replace_once(text, old_target, new_target, "target resolver")
    path.write_text(text)
    print(f"{path}: applied {MARKER}")


def patch_runner(path: Path) -> None:
    text = path.read_text()
    marker = "# WS40_V103_LINEAGE_TARGET_TRANSPORT"
    if marker in text:
        print(f"{path}: lineage transport already applied")
        return
    old = '''            str(bool(o.get("controlled_since_turn_began", False))).lower(), str(bool(o["emit_semantic"])).lower(),
        ])'''
    new = '''            str(bool(o.get("controlled_since_turn_began", False))).lower(), str(bool(o["emit_semantic"])).lower(),
            enc(o.get("card_lineage_id")),  # WS40_V103_LINEAGE_TARGET_TRANSPORT
        ])'''
    text = replace_once(text, old, new, "runner object-row lineage transport")
    path.write_text(text)
    print(f"{path}: applied WS40_V103_LINEAGE_TARGET_TRANSPORT")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-java", type=Path)
    ap.add_argument("--runner", type=Path)
    args = ap.parse_args()
    if bool(args.state_java) == bool(args.runner):
        raise SystemExit("provide exactly one of --state-java or --runner")
    if args.state_java:
        patch_state_java(args.state_java)
    else:
        patch_runner(args.runner)


if __name__ == "__main__":
    main()
