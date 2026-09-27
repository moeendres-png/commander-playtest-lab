#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from commander_lab.engine.rules import run_phase8_validation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase-8 rules validation")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=Path("data/runs/phase8_validation"))
    parser.add_argument("--seed", type=int, default=20260804)
    args = parser.parse_args()
    summary = run_phase8_validation(
        args.root,
        output_directory=args.root / args.output,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["local_acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
