#!/usr/bin/env python3
"""221-Nachmessung: Precon-Import ueber den PRODUKTIVEN Pfad.

Importiert jedes Precon-Deck ausschliesslich ueber
ExternalRulesAdapter.import_deck() (JSONL -> XmageDeckImporter),
ohne ein Spiel zu starten. Erfasst pro Deck: OK oder Fehlertext.

Usage:
    python3 scripts/measure_precon_imports.py --jar <jar> --workdir <dir> \
        --out <json> [--limit N]
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from run_real_4p_full_game_smoke import _ensure_deck_hash  # noqa: E402

from commander_lab.engine.rules.bridge import ExternalRulesAdapter  # noqa: E402
from commander_lab.engine.rules.project import load_rules_deck_snapshot  # noqa: E402
from commander_lab.models import RulesBackend  # noqa: E402

PRECON_DIR = REPO / "data" / "decks" / "precons"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jar", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    jar = Path(args.jar).resolve()
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    deck_paths = sorted(PRECON_DIR.glob("*.json"))
    if args.limit:
        deck_paths = deck_paths[: args.limit]

    command = ("java", "-jar", str(jar))
    adapter = ExternalRulesAdapter(
        RulesBackend.XMAGE, command, cwd=workdir, request_timeout_seconds=300.0
    )

    results: list[dict] = []
    started = time.monotonic()
    try:
        probe = adapter.probe()
        print(f"probe: availability={probe.availability}", flush=True)
        for path in deck_paths:
            t0 = time.monotonic()
            row: dict = {"deck": path.stem}
            try:
                loaded = load_rules_deck_snapshot(path)
                deck, _ = _ensure_deck_hash(loaded)
                handle = adapter.import_deck(deck)
                row["status"] = "OK"
                row["handle"] = str(handle)[:200]
            except Exception as exc:  # per-deck failure is a result row
                row["status"] = "FAILED"
                row["error"] = f"{type(exc).__name__}: {exc}"[:600]
            row["wall_s"] = round(time.monotonic() - t0, 2)
            results.append(row)
            print(json.dumps(row), flush=True)
    finally:
        with contextlib.suppress(Exception):
            adapter.close()

    ok = sum(1 for r in results if r["status"] == "OK")
    summary = {
        "jar": str(jar),
        "jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
        "decks_total": len(results),
        "decks_ok": ok,
        "decks_failed": len(results) - ok,
        "total_wall_s": round(time.monotonic() - started, 1),
        "results": results,
    }
    Path(args.out).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"FERTIG: {ok}/{len(results)} OK -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
