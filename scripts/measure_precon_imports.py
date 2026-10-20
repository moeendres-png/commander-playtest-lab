#!/usr/bin/env python3
"""Measure how many decks import through the productive path, without playing a game.

Every deck goes through ``ExternalRulesAdapter.import_deck()`` (JSONL -> ``XmageDeckImporter``:
card resolution and commander validation). A row is ``OK``, ``FAILED`` (the importer rejected the
deck) or ``INFRASTRUCTURE_ERROR`` (timeout, dead bridge, protocol break: says nothing about the
deck). The run stops with exit code 2 when the bridge probe is not ``AVAILABLE`` and ends with
exit code 3 when any row is an infrastructure error, so a missing JAR cannot pass as 195 deck
failures.

Usage:
    python3 scripts/measure_precon_imports.py --jar <jar> --workdir <dir> --out <json> \
        [--deck-dir data/decks/custom] [--limit N] [--enumerate-missing]

``--enumerate-missing`` re-imports each failed deck as an in-memory variant (the deck file stays
untouched), replaces every card the engine does not know with a filler and repeats, so the report
lists ALL unknown card names of a deck, not only the first one the importer names.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from run_real_4p_full_game_smoke import _ensure_deck_hash  # noqa: E402

from commander_lab.engine.rules.bridge import ExternalRulesAdapter  # noqa: E402
from commander_lab.engine.rules.project import load_rules_deck_snapshot  # noqa: E402
from commander_lab.models import RulesBackend, RulesEngineAvailability  # noqa: E402

PRECON_DIR = REPO / "data" / "decks" / "precons"
UNKNOWN_CARD = re.compile(r"UNKNOWN_CARD_NAME: (.+)$", re.M)
FILLER_MAINBOARD = "Plains"
FILLER_COMMANDER = "Isamaru, Hound of Konda"  # a plain legend, only a placeholder for the probe
MAX_ENUMERATION_STEPS = 60


def classify_error(error: str) -> str:
    """``FAILED`` when the importer rejected the deck, else ``INFRASTRUCTURE_ERROR``."""
    return "FAILED" if "deck_import_failed" in error else "INFRASTRUCTURE_ERROR"


def unknown_card_name(error: str) -> str | None:
    match = UNKNOWN_CARD.search(error)
    return match.group(1).strip() if match else None


def replace_card(deck: dict[str, Any], card: str) -> str | None:
    """Replace ``card`` by a filler in place; return its role or None when it is not in the deck."""
    role = None
    for entry in deck.get("cards", []):
        if (entry.get("oracle_name") or entry.get("name")) == card:
            entry["oracle_name"] = FILLER_MAINBOARD
            if "name" in entry:
                entry["name"] = FILLER_MAINBOARD
            role = "mainboard"
    commander = deck.get("commander")
    if isinstance(commander, dict) and card in commander.get("commanders", []):
        commander["commanders"] = [
            FILLER_COMMANDER if name == card else name for name in commander["commanders"]
        ]
        role = "commander"
    return role


def enumerate_missing(
    deck: dict[str, Any], try_import: Callable[[dict[str, Any]], tuple[str, str]]
) -> dict[str, Any]:
    """Name every unknown card of ``deck``; ``try_import`` returns ``(status, error)``."""
    variant = copy.deepcopy(deck)
    missing: list[dict[str, str]] = []
    for _ in range(MAX_ENUMERATION_STEPS):
        status, error = try_import(variant)
        if status == "OK":
            return {"missing_cards": missing, "final_status": "OK_AFTER_REPLACEMENT"}
        card = unknown_card_name(error)
        if card is None:
            return {"missing_cards": missing, "final_status": f"OTHER_ERROR: {error[:200]}"}
        role = replace_card(variant, card)
        if role is None:
            return {"missing_cards": missing, "final_status": f"NOT_REPLACEABLE: {card}"}
        missing.append({"card": card, "role": role})
    return {"missing_cards": missing, "final_status": "STEP_LIMIT"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jar", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--deck-dir", type=Path, default=PRECON_DIR)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--enumerate-missing", action="store_true")
    args = parser.parse_args()

    jar = Path(args.jar).resolve()
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    deck_paths = sorted(args.deck_dir.glob("*.json"))
    if args.limit:
        deck_paths = deck_paths[: args.limit]
    if not deck_paths:
        print(f"no deck files in {args.deck_dir}", file=sys.stderr)
        return 2

    adapter = ExternalRulesAdapter(
        RulesBackend.XMAGE,
        ("java", "-jar", str(jar)),
        cwd=workdir,
        request_timeout_seconds=300.0,
    )

    def try_import(deck_json: dict[str, Any], tag: str) -> tuple[str, str]:
        diag = workdir / "variants"
        diag.mkdir(exist_ok=True)
        path = diag / f"{tag}.json"
        path.write_text(json.dumps(deck_json, ensure_ascii=False), encoding="utf-8")
        deck, _ = _ensure_deck_hash(load_rules_deck_snapshot(path))
        try:
            adapter.import_deck(deck)
        except Exception as exc:
            return "FAILED", f"{type(exc).__name__}: {exc}"
        return "OK", ""

    results: list[dict[str, Any]] = []
    started = time.monotonic()
    engine_version = "unknown"
    try:
        probe = adapter.probe()
        engine_version = str(probe.backend_version)
        print(
            f"probe: availability={probe.availability.value} engine={engine_version}",
            flush=True,
        )
        if probe.availability is not RulesEngineAvailability.AVAILABLE:
            print("bridge is not available: no deck was measured", file=sys.stderr)
            return 2
        for path in deck_paths:
            t0 = time.monotonic()
            row: dict[str, Any] = {"deck": path.stem}
            try:
                deck, _ = _ensure_deck_hash(load_rules_deck_snapshot(path))
                row["handle"] = str(adapter.import_deck(deck))[:200]
                row["status"] = "OK"
            except Exception as exc:  # a failed deck is a result row, not a crash
                row["error"] = f"{type(exc).__name__}: {exc}"[:600]
                row["status"] = classify_error(row["error"])
            if row["status"] == "FAILED" and args.enumerate_missing:
                original = json.loads(path.read_text(encoding="utf-8"))
                row |= enumerate_missing(original, lambda d, stem=path.stem: try_import(d, stem))
            row["wall_s"] = round(time.monotonic() - t0, 2)
            results.append(row)
            print(json.dumps(row), flush=True)
    finally:
        with contextlib.suppress(Exception):
            adapter.close()

    count = {
        status: sum(1 for r in results if r["status"] == status)
        for status in ("OK", "FAILED", "INFRASTRUCTURE_ERROR")
    }
    summary = {
        "jar": str(jar),
        "jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
        "engine_version": engine_version,
        "deck_dir": str(args.deck_dir),
        "decks_total": len(results),
        "decks_ok": count["OK"],
        "decks_failed": count["FAILED"],
        "decks_infrastructure_error": count["INFRASTRUCTURE_ERROR"],
        "total_wall_s": round(time.monotonic() - started, 1),
        "results": results,
    }
    Path(args.out).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"DONE: {count['OK']}/{len(results)} OK -> {args.out}", flush=True)
    return 3 if count["INFRASTRUCTURE_ERROR"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
