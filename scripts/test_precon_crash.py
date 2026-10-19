#!/usr/bin/env python3
"""Systematic precon deck crash test.

Tests each precon deck by running a single game with it.
Uses the benchmark infrastructure (_play, _setup, bridge_command).

IMPORTANT: Run only when no other benchmark is running (CPU contention).
Check with: pgrep -f benchmark_xmage

Usage:
    # Test single deck
    python3 scripts/test_precon_crash.py --deck 2011_counterpunch --jar <jar>
    
    # Test all 195 decks (takes ~2-3 hours)
    python3 scripts/test_precon_crash.py --all --jar <jar> --out ~/workspace/tmp/precon_results.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Add repo to path
REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

from benchmark_xmage_full_games import _play, _setup, bridge_command

PRECON_DIR = REPO / "data" / "decks" / "precons"


def test_single_deck(
    deck_path: Path, command: tuple[str, ...], seed: int = 1
) -> dict:
    """Test a single precon deck in a 4-player game.
    
    All 4 players use the same precon deck to isolate deck-specific
    crashes from interaction effects.
    """
    deck_name = deck_path.stem
    
    # All 4 players use the same deck (_setup expects Path objects)
    deck_rel = deck_path.relative_to(REPO)
    setup = _setup((deck_rel,) * 4)
    
    # _play returns a row dict with status, semantic, decisions, winners, etc.
    # A failed game has status="failed" with error details.
    row = _play(command, f"precon-{deck_name}", setup, seed, private=False)
    
    return {
        "deck": deck_name,
        "status": "OK" if row["status"] == "ok" else "ENGINE_FAILURE",
        "error": row.get("error"),
        "decisions": row.get("decisions"),
        "winners": row.get("winners"),
        "wall_s": row.get("wall_s"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Test precon decks for ENGINE_FAILURE")
    parser.add_argument("--deck", help="Deck name (e.g., 2011_counterpunch)")
    parser.add_argument("--all", action="store_true", help="Test all precon decks")
    parser.add_argument("--out", default="precon_crash_results.json")
    parser.add_argument("--jar", required=True, help="Path to bridge JAR")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    # Check no other benchmark is running
    import subprocess
    ps = subprocess.run(
        ["pgrep", "-f", "benchmark_xmage"], capture_output=True
    )
    if ps.returncode == 0:
        print(
            "WARNING: Another benchmark is running! CPU contention causes false failures.",
            file=sys.stderr,
        )
        print("Wait for it to complete first.", file=sys.stderr)
        return 1

    jar = Path(args.jar)
    if not jar.exists():
        print(f"JAR not found: {jar}", file=sys.stderr)
        return 1

    if args.deck:
        decks = [PRECON_DIR / f"{args.deck}.json"]
    elif args.all:
        decks = sorted(PRECON_DIR.glob("*.json"))
    else:
        print("Use --deck NAME or --all", file=sys.stderr)
        return 1

    decks = [d for d in decks if d.exists()]
    if not decks:
        print("No decks found!", file=sys.stderr)
        return 1

    print(f"Testing {len(decks)} precon decks...", file=sys.stderr)
    print(f"JAR: {jar}", file=sys.stderr)

    command = bridge_command(jar, [])
    results = []
    out_path = Path(args.out)
    
    for i, deck_path in enumerate(decks, 1):
        print(f"[{i}/{len(decks)}] {deck_path.stem}...", file=sys.stderr, flush=True)
        try:
            result = test_single_deck(deck_path, command, args.seed)
        except Exception as e:
            result = {
                "deck": deck_path.stem,
                "status": "ERROR",
                "error": f"{type(e).__name__}: {e}"[:500],
            }
        results.append(result)
        status_icon = "✓" if result["status"] == "OK" else "✗"
        print(f"  {status_icon} {result['status']}", file=sys.stderr)
        
        # Save incrementally (in case of interruption)
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2)

    # Summary
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    
    print("\n=== Summary ===", file=sys.stderr)
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}", file=sys.stderr)
    
    failures = [r for r in results if r["status"] != "OK"]
    if failures:
        print(f"\n⚠️  {len(failures)} decks failed:", file=sys.stderr)
        for f in failures[:20]:
            err = (f.get("error") or "")[:80]
            print(f"  - {f['deck']}: {err}", file=sys.stderr)
    
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
