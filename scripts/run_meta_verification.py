from __future__ import annotations

import argparse
import json
from pathlib import Path

from commander_lab.meta_qualification import run_meta_verification

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAPE = Path("qualification/ws218-semantic-replay-tape-v1/tapes/ws218-tape-4p.json")
DEFAULT_OUTPUT = Path("artifacts/meta-verification/META_VERIFICATION_RESULT.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tape", type=Path, default=DEFAULT_TAPE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--runtime-hidden-killed",
        action="store_true",
        help="Credit MQ-HIDDEN-001 only after the live XMage detector passed on this source head.",
    )
    args = parser.parse_args()

    tape_path = args.tape if args.tape.is_absolute() else ROOT / args.tape
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    tape = json.loads(tape_path.read_text())
    source_tape = str(tape_path.relative_to(ROOT))
    runtime_kills = {"MQ-HIDDEN-001"} if args.runtime_hidden_killed else set()
    report = run_meta_verification(
        tape,
        source_tape=source_tape,
        runtime_kills=runtime_kills,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    if report["survived"] != 0:
        return 2
    if report["killed"] != report["attempted"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
