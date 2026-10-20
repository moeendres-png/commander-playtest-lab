#!/usr/bin/env python3
"""Diagnose-Vertiefung zur 221-Nachmessung.

Fuer jedes Deck, das im Hauptlauf fehlschlug: iterativ in-memory-Varianten
importieren (Originaldateien bleiben unveraendert), um ALLE fehlenden Karten
zu enumerieren, nicht nur den ersten Fehler.
- UNKNOWN_CARD_NAME X  -> X notieren, aus der Variante entfernen, erneut.
- CARD_IDENTITY_MISMATCH -> Commander-Name auf Frontform reduzieren, erneut.

Usage:
    python3 scripts/measure_precon_imports_deep.py --jar <jar> \
        --workdir <dir> --main <imports_base|fork.json> --out <json>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from commander_lab.engine.rules.bridge import ExternalRulesAdapter  # noqa: E402
from commander_lab.engine.rules.project import load_rules_deck_snapshot  # noqa: E402
from commander_lab.models import RulesBackend  # noqa: E402
from run_real_4p_full_game_smoke import _ensure_deck_hash  # noqa: E402

PRECON_DIR = REPO / "data" / "decks" / "precons"
DIAG_DIR = Path.home() / "workspace" / "tmp" / "measure221" / "diag"
UNKNOWN_RE = re.compile(r"UNKNOWN_CARD_NAME: (.+)$", re.M)


def import_variant(adapter, deck_json: dict, tag: str) -> tuple[str, str]:
    """Write a temp deck file, load via production loader, import. Returns (status, error)."""
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DIAG_DIR / f"{tag}.json"
    tmp.write_text(json.dumps(deck_json, ensure_ascii=False))
    loaded = load_rules_deck_snapshot(tmp)
    deck, _ = _ensure_deck_hash(loaded)
    try:
        adapter.import_deck(deck)
        return "OK", ""
    except Exception as exc:
        return "FAILED", f"{type(exc).__name__}: {exc}"


FILLER_MAINBOARD = "Plains"  # existiert ueberall, Basisland-Duplikate sind legal
FILLER_COMMANDER = "Isamaru, Hound of Konda"  # simple Legende, nur Diagnose-Platzhalter


def remove_card(deck_json: dict, card_name: str) -> bool:
    """Ersetzt die Karte durch einen Fueller (Deck muss exakt 100 Karten behalten)."""
    replaced = False
    for c in deck_json.get("cards", []):
        if (c.get("oracle_name") or c.get("name")) == card_name:
            c["oracle_name"] = FILLER_MAINBOARD
            if "name" in c:
                c["name"] = FILLER_MAINBOARD
            replaced = True
    cmd = deck_json.get("commander", {})
    if isinstance(cmd, dict) and card_name in cmd.get("commanders", []):
        cmd["commanders"] = [
            FILLER_COMMANDER if c == card_name else c for c in cmd["commanders"]
        ]
        replaced = True
    return replaced


def card_role(deck_json: dict, card_name: str) -> str:
    cmd = deck_json.get("commander", {})
    if isinstance(cmd, dict) and card_name in cmd.get("commanders", []):
        return "commander"
    return "mainboard"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jar", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--main", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    main_run = json.loads(Path(args.main).read_text())
    failing = [r["deck"] for r in main_run["results"] if r["status"] != "OK"]
    print(f"Vertiefung fuer {len(failing)} fehlgeschlagene Decks", flush=True)

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    adapter = ExternalRulesAdapter(
        RulesBackend.XMAGE,
        ("java", "-jar", str(Path(args.jar).resolve())),
        cwd=workdir,
        request_timeout_seconds=300.0,
    )

    report: dict[str, dict] = {}
    try:
        adapter.probe()
        for deck_name in failing:
            original = json.loads((PRECON_DIR / f"{deck_name}.json").read_text())
            variant = json.loads(json.dumps(original))  # deep copy
            missing: list[dict] = []
            identity_fixed = False
            final = "UNKNOWN"
            for attempt in range(45):
                status, error = import_variant(
                    adapter, variant, f"{deck_name}_v{attempt}"
                )
                if status == "OK":
                    final = "OK_NACH_ENTFERNUNG" if missing or identity_fixed else "OK"
                    break
                m = UNKNOWN_RE.search(error)
                if m:
                    card = m.group(1).strip()
                    missing.append(
                        {"card": card, "role": card_role(original, card)}
                    )
                    if not remove_card(variant, card):
                        final = f"NICHT_ENTFERNBAR: {card}"
                        break
                    continue
                if "CARD_IDENTITY_MISMATCH" in error and not identity_fixed:
                    cmd = variant.get("commander", {})
                    if isinstance(cmd, dict):
                        cmd["commanders"] = [
                            c.split(" // ")[0].strip() for c in cmd.get("commanders", [])
                        ]
                    identity_fixed = True
                    continue
                final = f"ANDERER_FEHLER: {error[:200]}"
                break
            else:
                final = "ITERATIONSLIMIT"
            report[deck_name] = {
                "missing_cards": missing,
                "identity_mismatch_fixed_by_front_name": identity_fixed,
                "final_status": final,
            }
            print(json.dumps({deck_name: report[deck_name]}), flush=True)
    finally:
        try:
            adapter.close()
        except Exception:
            pass

    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"FERTIG -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
