from __future__ import annotations

import argparse
import json
from pathlib import Path

from commander_lab.model_resolution_measurement import (
    ModelResolutionMeasurementProtocol,
    measure_current_model_resolution,
)
from commander_lab.model_resolution_software_identity import model_resolution_software_identity
from commander_lab.storage import sha256_value


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure current Structural model resolution")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=2026081517)
    parser.add_argument("--blocks", type=int, default=4)
    parser.add_argument("--games-per-block", type=int, default=56)
    parser.add_argument("--pilot-games", type=int, default=56)
    parser.add_argument("--max-turns", type=int, default=35)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--calibrated-sesoi", type=float, default=0.05)
    args = parser.parse_args()

    protocol = ModelResolutionMeasurementProtocol(
        seed=args.seed,
        independent_seed_blocks=args.blocks,
        games_per_seed_block=args.games_per_block,
        pilot_axis_games=args.pilot_games,
        max_turns=args.max_turns,
        workers=args.workers,
        calibrated_sesoi=args.calibrated_sesoi,
    )
    raw_report = measure_current_model_resolution(args.root, protocol=protocol)
    report = {key: value for key, value in raw_report.items() if key != "report_hash"}
    report["software_identity"] = model_resolution_software_identity(args.root)
    report["report_hash"] = sha256_value(report)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "effective_resolution": report["effective_resolution"],
                "report_hash": report["report_hash"],
                "software_identity_sha256": report["software_identity"]["identity_sha256"],
                "output": str(output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
