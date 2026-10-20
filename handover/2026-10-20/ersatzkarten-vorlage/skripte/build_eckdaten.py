#!/usr/bin/env python3
"""Assemble the M2 key-data (Eckdaten) table for all 31 missing cards.

Per card: Scryfall facts (EXTERNAL_DATA, fetched 2026-10-20), stub facts from
the old fork patches (SYNTHETIC), the stub reliability verdict, and presence in
the repo's own card knowledge (data/cards/*.json - measured: 0 of 31).
"""
import json
from pathlib import Path

BASE = Path("/home/hatch/workspace/tmp/m2")


def main() -> int:
    idx = json.loads((BASE / "scryfall/index.json").read_text())
    pruefung = json.loads((BASE / "stub_pruefung.json").read_text())
    raw = json.loads((BASE / "stub_facts_raw.json").read_text())
    by_file = {}
    for cls, facts in raw.items():
        by_file[Path(facts["path"]).name] = {**facts, "class": cls}
    out = []
    for entry in idx["found"]:
        name = entry["name"]
        p = json.loads((BASE / "scryfall" / entry["file"]).read_text())
        chk = pruefung.get(name, {})
        stub = chk.get("stub", {})
        raw_stub = by_file.get(stub.get("file", ""), {})
        out.append({
            "name": name,
            "scryfall": {
                "mana_cost": p.get("mana_cost"),
                "cmc": p.get("cmc"),
                "type_line": p.get("type_line"),
                "power": p.get("power"),
                "toughness": p.get("toughness"),
                "loyalty": p.get("loyalty"),
                "keywords": p.get("keywords"),
                "oracle_text": p.get("oracle_text"),
                "set": p.get("set"),
                "set_name": p.get("set_name"),
                "released_at": p.get("released_at"),
                "color_identity": p.get("color_identity"),
                "commander_legality": (p.get("legalities") or {}).get("commander"),
                "rarity": p.get("rarity"),
                "source": "Scryfall API GET /cards/named?exact= (EXTERNAL_DATA, Abruf 2026-10-20)",
            },
            "stub": {
                "file": stub.get("file"),
                "patch_file": raw_stub.get("patch_file"),
                "mana_cost": stub.get("mana_cost"),
                "types": stub.get("types"),
                "p_t": stub.get("p_t"),
                "ability_lines": raw_stub.get("add_ability_lines"),
                "keyword_hints": raw_stub.get("keyword_hints"),
                "source": "Fork-Patches auf muse/claude-handover, handover/2026-10-19/fork-patches/ (SYNTHETIC)",
            },
            "stub_reliability": chk.get("verdict", "UNKNOWN"),
            "stub_diffs": chk.get("diffs", []),
            "in_repo_card_knowledge": False,
            "in_repo_card_knowledge_source": "data/cards/*.json @ ed2fbae26, strukturierter Namensindex + Rohtextsuche (LOCAL_OBSERVED 2026-10-20): 0 von 31",
        })
    (BASE / "eckdaten.json").write_text(
        json.dumps({"cards": out, "count": len(out)}, indent=1, ensure_ascii=False), encoding="utf-8")
    print("eckdaten cards:", len(out))
    print("stub verdicts:", {v: sum(1 for c in out if c["stub_reliability"] == v)
                             for v in {c["stub_reliability"] for c in out}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
